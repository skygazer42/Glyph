"""Import accepted Changzhou sources with exact vector and upload readback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv

from scripts.import_changzhou_corpus import query_chunks, upsert_batch
from scripts.official_policy_data import load_curated_faq, load_official_policies

ROOT = Path(__file__).resolve().parents[1]


def build_source_header(item: dict[str, Any]) -> str:
    """Keep the source's jurisdiction, document type and annual limits in search."""
    context = ""
    for field, label in (("effective_date", "施行日期"), ("expires_date", "到期日期")):
        if item.get(field) is not None:
            context += f"{label}：{item[field]}\n"
    if item.get("coverage_year") is not None:
        context += f"保障年度：{item['coverage_year']}\n"
    if item.get("retrieval_note"):
        context += f"适用说明：{item['retrieval_note']}\n"
    if item.get("snapshot_finished_at"):
        context += f"数据快照时间：{item['snapshot_finished_at']}\n"
    identity_note = (
        "说明：商业保险产品平台正式销售文件快照；按保障年度、版本和实际保单约定适用。\n\n"
        if item.get("source_type") == "first_party_insurance_product"
        else "说明：官方公开资料快照；后续修改、受理条件及实际审核以发布机关现行规定为准。\n\n"
    )
    if item.get("source_type") == "official_media_release":
        identity_note = "说明：官方传媒第一方操作指南快照，发布主体和发布链单独核验；具体申请按办理平台现行要求。\n\n"
    elif item.get("source_type") == "first_party_official_housing_platform":
        identity_note = "说明：官方住房平台公开项目列表的采集快照；项目记录不等于逐套房源，也不是实时可售库存保证。\n\n"
        if item.get("snapshot_kind") == "housing_unit_details":
            identity_note = "说明：官方住房平台公开逐套列表的采集快照；ZT仅保留源状态代码，不是实时可售库存或2026年A/B/C全量保证。预备房源转入专项库后方可按规定使用资助。\n\n"
    return (
        f"资料名称：{item['title']}\n发布机关：{item['issuer']}\n"
        f"适用地区：{item['scope']}\n资料类型：{item['document_kind']}\n"
        f"发布日期：{item.get('published_date')}\n来源：{item['url']}\n"
        + context
        + identity_note
    )


def split_body(body: str) -> list[tuple[int, int, str]]:
    """Cover the whole source with overlaps while preserving Markdown tables."""
    tables = [
        (match.start(), match.end())
        for match in re.finditer(r"(?m)^\|.*\n(?:\|.*\n)+", body)
    ]
    parts = []
    start = 0
    while start < len(body):
        end = min(start + 1800, len(body))
        if end < len(body):
            newline = body.rfind("\n", start + 900, end)
            if newline > start:
                end = newline + 1
        for first, last in tables:
            if first < end < last:
                end = first if first > start + 160 else last
        if not start < end <= start + 8000:
            raise ValueError("Official source cannot fit the accepted chunk boundary")
        parts.append((start, end, body[start:end]))
        if end == len(body):
            break
        next_start = end - 160
        for first, last in tables:
            if first < next_start < last:
                next_start = first
        if next_start <= start:
            raise ValueError("Chunk overlap failed to advance")
        start = next_start
    return parts


def import_document_groups(
    store: Any,
    document_groups: list[list[Any]],
    publish_verified: Callable[[int], None],
    *,
    workers: int = 2,
) -> int:
    """Batch across sources, then publish only after every exact Strong readback."""
    collection = store.collection
    if collection is None:
        raise RuntimeError("Milvus collection was not initialized")
    documents = [document for group in document_groups for document in group]
    ids = [str(document.id) for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate official document identity")
    for document in documents:
        for field, limit in (("title", 2048), ("content", 65535), ("source", 1024)):
            if len(getattr(document, field).encode("utf-8")) > limit:
                raise ValueError(f"Official source exceeds UTF-8 capacity: {field}")
    indexed = query_chunks(collection, ids)
    changed = [
        document for document in documents
        if str(document.id) not in indexed or any(
            indexed[str(document.id)][field] != getattr(document, field)
            for field in ("title", "content", "source")
        )
    ]
    batches = [changed[offset:offset + 16] for offset in range(0, len(changed), 16)]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for count, _ in enumerate(executor.map(lambda batch: upsert_batch(store, batch), batches), start=1):
            if count % 10 == 0 or count == len(batches):
                print(f"Importing official segments: {min(count * 16, len(changed))}/{len(changed)}", flush=True)
    if changed:
        collection.flush()
    actual = query_chunks(collection, ids)
    if set(actual) != set(ids) or any(
        any(actual[str(document.id)][field] != getattr(document, field) for field in ("title", "content", "source"))
        for document in documents
    ):
        raise RuntimeError("Official vector readback mismatch; no source completion published")
    for index in range(len(document_groups)):
        publish_verified(index)
    return len(changed)


def validate_prior_source_ids(receipt: dict[str, Any], expected: dict[str, set[str]]) -> None:
    """Require an explicit retirement plan when old official IDs would be orphaned."""
    for prior in receipt["policies"]:
        if prior["url"] not in expected or set(prior["vector_ids"]) != expected[prior["url"]]:
            raise ValueError(f"Prior official vectors require withdrawal review: {prior['url']}")


def main(root: Path = ROOT) -> None:
    """Load accepted files, upsert new source IDs, then publish verified markers."""
    os.chdir(root)
    load_dotenv(root / ".env.siliconflow.local", override=True)
    for key in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        if "127.0.0.1" in os.environ.get(key, ""):
            os.environ.pop(key)
    from app.config.app_config import settings
    from app.knowledge.document_workspace import DocumentWorkspace, atomic_write
    from app.knowledge.milvus import MilvusStore
    from app.models.policy import PolicyDocument, PolicyType
    from pymilvus import Collection, connections

    policies = load_official_policies(root)
    faq = load_curated_faq(root, policies)
    # The first 112 nationally applicable sources already have a verified import.
    old_urls = set()
    catalog = root / "resources/data/policy_catalog"
    for name in ["import_20261121.json", "import_expansion_20261121.json"]:
        for item in json.loads((catalog / name).read_text(encoding="utf-8"))[
            "policies"
        ]:
            if item["scope"] == "全国":
                old_urls.add(item["url"])
    pending = [item for item in policies if item["url"] not in old_urls]
    workspace = DocumentWorkspace(
        root / "uploads",
        root / "uploads/parsed",
        root / "uploads/.status/parsed",
        root / "uploads/.status/embedded",
    )
    output = catalog / "import_changzhou_20261121.json"
    result: dict[str, Any] = {
        "status": "importing",
        "date": "2026-11-21",
        "policies": [],
        "collection": settings.database.milvus_collection_name,
    }
    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
    result.update(status="importing", collection=settings.database.milvus_collection_name)
    atomic_write(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    store = MilvusStore()
    try:
        collection = store.collection
        if collection is None:
            raise RuntimeError("Milvus collection was not initialized")
        prepared: list[dict[str, Any]] = []
        for item in pending:
            title = (
                re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", item["title"]).strip().rstrip(".")
            )
            filename = f"官方_{item['scope']}_{title[:65]}_{hashlib.sha256(item['url'].encode()).hexdigest()[:10]}.md"
            source = root / "uploads" / filename
            if source.exists():
                if source.read_bytes() != item["markdown"].encode("utf-8"):
                    raise ValueError(f"Uploaded source changed: {filename}")
            else:
                atomic_write(source, item["markdown"])
            version = workspace.source_version(filename)
            parsed = workspace.store_parsed(
                filename, item["markdown"], version, "official-source-text"
            )
            spans = split_body(item["body"])
            header = build_source_header(item)
            documents = [
                PolicyDocument(
                    id=uuid5(
                        NAMESPACE_URL,
                        f"glyph:official-policy:{item['url']}:chunk:{index}",
                    ),
                    title=f"{item['title']}（第{index + 1}/{len(spans)}段）",
                    content=header + text,
                    source=item["url"],
                    doc_type=PolicyType.GUIDELINE,
                    regions=[item["scope"]],
                )
                for index, (_, _, text) in enumerate(spans)
            ]
            prepared.append({
                "item": item, "filename": filename, "source": source,
                "version": version, "parsed_version": parsed.version,
                "documents": documents,
            })
        validate_prior_source_ids(result, {
            entry["item"]["url"]: {str(document.id) for document in entry["documents"]}
            for entry in prepared
        })

        def publish_verified(index: int) -> None:
            entry = prepared[index]
            item = entry["item"]
            filename = entry["filename"]
            source = entry["source"]
            version = entry["version"]
            parsed_version = entry["parsed_version"]
            ids = [str(document.id) for document in entry["documents"]]
            marker = {
                "doc_id": filename,
                "updated_at": time.time(),
                "source_version": version,
                "parsed_version": parsed_version,
                "vector_id": ids[0],
                "vector_ids": ids,
                "collection_name": store.collection_name,
                "source_url": item["url"],
                "import_batch": "changzhou_20261121",
            }
            atomic_write(
                workspace.marker_path(workspace.embedded_dir, filename),
                json.dumps(marker, ensure_ascii=False),
            )
            record = {
                key: value
                for key, value in item.items()
                if key not in {"body", "markdown"}
            }
            record.update(
                upload_path=source.relative_to(root).as_posix(),
                vector_ids=ids,
                source_version=version,
                parsed_version=parsed_version,
                status="source_and_vector_verified",
                application_import_status="source_and_vector_verified",
            )
            result["policies"] = [
                prior for prior in result["policies"] if prior["url"] != item["url"]
            ] + [record]
            atomic_write(
                output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
            print("Verified:", len(result["policies"]), item["title"], flush=True)
        changed_count = import_document_groups(
            store, [entry["documents"] for entry in prepared], publish_verified
        )
        atomic_write(
            root / "resources/faq/qa_pairs.json",
            json.dumps(faq, ensure_ascii=False, indent=2) + "\n",
        )
        result.update(
            status="verified",
            total_accepted_sources=len(policies),
            curated_faq=len(faq),
            new_source_count=len(pending),
            imported_vector_count=sum(
                len(row["vector_ids"]) for row in result["policies"]
            ),
            changed_vector_count=changed_count,
        )
        atomic_write(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {key: value for key, value in result.items() if key != "policies"},
                ensure_ascii=False,
            )
        )
    finally:
        store.close()
        alias = "changzhou-import-reload"
        connections.connect(
            alias=alias,
            host=settings.database.milvus_host,
            port=str(settings.database.milvus_port),
        )
        try:
            Collection(settings.database.milvus_collection_name, using=alias).load()
        finally:
            connections.disconnect(alias)


if __name__ == "__main__":
    main()
