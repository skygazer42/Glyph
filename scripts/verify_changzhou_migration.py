"""Verify actual active sources, retired IDs and authenticated Changzhou APIs."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml
from dotenv import load_dotenv
from pymilvus import Collection, connections

from scripts.official_policy_data import load_curated_faq, load_official_policies

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "resources/data/policy_catalog"
ARCHIVE = ROOT / "resources/archive/pre_changzhou_20261121"


def source_type_counts(policies: list[dict[str, Any]]) -> dict[str, int]:
    """Keep first-party product evidence distinct from government publications."""
    counts = {
        "official_government_sources": 0,
        "first_party_insurance_sources": 0,
        "official_public_institution_sources": 0,
        "official_media_sources": 0,
        "official_housing_platform_sources": 0,
    }
    for item in policies:
        host = urlparse(item["url"]).hostname or ""
        if item.get("source_type") == "first_party_insurance_product":
            counts["first_party_insurance_sources"] += 1
        elif item.get("source_type") == "official_media_release":
            counts["official_media_sources"] += 1
        elif item.get("source_type") == "first_party_official_housing_platform":
            counts["official_housing_platform_sources"] += 1
        elif host.endswith(".gov.cn"):
            counts["official_government_sources"] += 1
        else:
            counts["official_public_institution_sources"] += 1
    return counts


def load_corpus_manifest(catalog: Path) -> dict[str, Any] | None:
    """Accept only a completed corpus import with independently checkable files."""
    path = catalog / "import_changzhou_corpus_20261121.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "verified":
        raise ValueError("Corpus import is not verified")
    required = {
        "upload_path", "source_version", "parsed_version", "vector_ids",
        "source_url", "raw_path", "raw_sha256", "records_count", "vector_sha256",
    }
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("Incomplete corpus file manifest")
    for item in manifest["files"]:
        if not required.issubset(item) or not item["vector_ids"]:
            raise ValueError("Incomplete corpus file evidence")
        if set(item["vector_sha256"]) != set(item["vector_ids"]):
            raise ValueError("Incomplete corpus file vector checksums")
    return manifest


def expected_vector_ids(*groups: list[dict[str, Any]]) -> set[str]:
    """Reject overlapping source ownership instead of silently deduplicating IDs."""
    identities: set[str] = set()
    for group in groups:
        for item in group:
            for identity in item["vector_ids"]:
                if identity in identities:
                    raise ValueError(f"Duplicate manifest vector: {identity}")
                identities.add(identity)
    return identities


def read_library_rows(collection: Any) -> dict[str, dict[str, Any]]:
    """Read every live primary key without the query offset/window limit."""
    iterator = collection.query_iterator(
        expr="", batch_size=512, limit=-1,
        output_fields=["id", "title", "content", "source", "doc_type"],
        consistency_level="Strong",
    )
    actual: dict[str, dict[str, Any]] = {}
    try:
        while rows := iterator.next():
            for row in rows:
                if row["id"] in actual:
                    raise ValueError(f"Duplicate live vector: {row['id']}")
                actual[row["id"]] = row
    finally:
        iterator.close()
    return actual


def vector_sha256(row: dict[str, Any]) -> str:
    """Match the import receipt's exact title/content/source byte digest."""
    text = "\0".join(row[field] for field in ("title", "content", "source"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_corpus_record_counts(root: Path, files: list[dict[str, Any]]) -> None:
    """Check that the receipt includes every eligible structured source record."""
    archive = root / "resources/data/raw/changzhou_user_corpus_20261121"
    records_path = root / "resources/data/process/changzhou_user_corpus_20261121/records.jsonl"
    counts: Counter[str] = Counter()
    hashes: dict[str, set[str]] = {}
    with records_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if not row["eligible_for_retrieval"]:
                continue
            path = root / row["raw_path"]
            if not path.is_relative_to(archive):
                path = archive / row["raw_path"]
            if not path.resolve().is_relative_to(archive.resolve()):
                raise ValueError("Corpus path escapes archive")
            key = path.relative_to(root).as_posix()
            counts[key] += 1
            hashes.setdefault(key, set()).add(row["raw_sha256"])
    manifest_files = {item["raw_path"]: item for item in files}
    if len(manifest_files) != len(files) or set(counts) != set(manifest_files):
        raise ValueError("Corpus record file set mismatch")
    for key, count in counts.items():
        item = manifest_files[key]
        if item["records_count"] != count:
            raise ValueError(f"Corpus record count mismatch: {key}")
        if hashes[key] != {item["raw_sha256"]}:
            raise ValueError(f"Corpus structured source hash mismatch: {key}")


def main() -> None:
    """Read back all source IDs and exercise saved rules, FAQ and vector search."""
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env.siliconflow.local", override=True)
    from app.config.app_config import settings
    from app.knowledge.document_workspace import DocumentWorkspace
    from app.knowledge.faq_responder import FAQResponder

    policies = load_official_policies(ROOT)
    faq = load_curated_faq(ROOT, policies)
    master = FAQResponder()
    assert len(master.entries) == len(faq) >= 146
    assert all(
        master.maybe_answer(entry.question) is not None for entry in master.entries
    )
    records = []
    for name in [
        "import_20261121.json",
        "import_expansion_20261121.json",
        "import_changzhou_20261121.json",
    ]:
        records.extend(
            json.loads((CATALOG / name).read_text(encoding="utf-8"))["policies"]
        )
    assert {item["url"] for item in records} == {item["url"] for item in policies}
    corpus = load_corpus_manifest(CATALOG)
    corpus_files = corpus["files"] if corpus is not None else []
    if corpus is not None:
        verify_corpus_record_counts(ROOT, corpus_files)
    all_files = records + corpus_files
    workspace = DocumentWorkspace(
        ROOT / "uploads",
        ROOT / "uploads/parsed",
        ROOT / "uploads/.status/parsed",
        ROOT / "uploads/.status/embedded",
    )
    for item in all_files:
        filename = Path(item["upload_path"]).name
        assert workspace.embedded(filename, workspace.source_version(filename)), (
            filename
        )
        assert workspace.source_version(filename) == item["source_version"]
        if item in corpus_files:
            assert workspace.parsed_content(filename, item["source_version"]).version == item["parsed_version"]
            marker = json.loads(
                workspace.marker_path(workspace.embedded_dir, filename).read_text(encoding="utf-8")
            )
            assert set(marker["vector_ids"]) == set(item["vector_ids"])
            assert hashlib.sha256((ROOT / item["raw_path"]).read_bytes()).hexdigest() == item["raw_sha256"]
    expected_ids = expected_vector_ids(records, corpus_files)
    retired = json.loads((ARCHIVE / "retirement_plan.json").read_text(encoding="utf-8"))
    baseline = json.loads((ARCHIVE / "milvus_before.json").read_text(encoding="utf-8"))
    before = {row["id"]: row for row in baseline["records"]}
    connections.connect(
        alias="changzhou-final-verification",
        host=settings.database.milvus_host,
        port=str(settings.database.milvus_port),
    )
    try:
        collection = Collection(
            settings.database.milvus_collection_name,
            using="changzhou-final-verification",
        )
        collection.load()
        actual = read_library_rows(collection)
        assert set(actual) == expected_ids
        assert not expected_ids.intersection(retired["retired_vector_ids"])
        superseded = json.loads(
            (ARCHIVE / "superseded_changzhou_vectors.json").read_text(encoding="utf-8")
        )
        assert not expected_ids.intersection(row["id"] for row in superseded["records"])
        retained_ids = retired["retained_national_ids"]
        retained_embeddings = {}
        for offset in range(0, len(retained_ids), 256):
            batch = retained_ids[offset:offset + 256]
            retained_embeddings.update({
                row["id"]: row["embedding"] for row in collection.query(
                    expr="id in " + json.dumps(batch),
                    output_fields=["id", "embedding"], limit=len(batch),
                    consistency_level="Strong",
                )
            })
        assert set(retained_embeddings) == set(retained_ids)
        for identity in retained_ids:
            for field in ["title", "content", "source", "doc_type"]:
                assert actual[identity][field] == before[identity][field]
            assert [float(value) for value in retained_embeddings[identity]] == before[
                identity
            ]["embedding"]
        for item in records:
            assert all(
                actual[identity]["source"] == item["url"]
                for identity in item["vector_ids"]
            )
        for item in corpus_files:
            for identity in item["vector_ids"]:
                assert actual[identity]["source"] == item["source_url"]
                assert vector_sha256(actual[identity]) == item["vector_sha256"][identity]
    finally:
        connections.disconnect("changzhou-final-verification")
    report = {
        "date": "2026-11-21",
        "sources": len(policies),
        **source_type_counts(policies),
        "local_sources": sum(not item["scope"].startswith("全国") for item in policies),
        "national_sources": sum(item["scope"].startswith("全国") for item in policies),
        "curated_faq": len(faq),
        "all_faq_sources_and_exact_matches_verified": True,
        "live_vectors": len(expected_ids),
        "retired_wrong_region_vectors": len(retired["retired_vector_ids"]),
        "retained_national_vectors_unchanged": len(retired["retained_national_ids"]),
        "official_vectors": sum(len(item["vector_ids"]) for item in records),
        "corpus_files": len(corpus_files),
        "corpus_records": sum(item["records_count"] for item in corpus_files),
        "corpus_vectors": sum(len(item["vector_ids"]) for item in corpus_files),
        "all_upload_markers_verified": len(all_files),
        "rules": [],
        "searches": [],
        "faq_api": [],
        "corpus_searches": [],
        "corpus_source_downloads": [],
    }
    base = "http://127.0.0.1:8002"
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(
            base + "/api/auth/login",
            json={
                "username": settings.security.api_default_username,
                "password": settings.security.api_default_password,
            },
            timeout=(5, 30),
        )
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        response = client.get(base + "/api/dsl/list", timeout=(5, 30))
        response.raise_for_status()
        visible = {row["rule_id"] for row in response.json()["rules"]}
        files = list((ROOT / "rules").glob("*.yaml"))
        assert len(files) == len(visible) >= 8
        assert all(
            identity.startswith(("Rule_Changzhou_", "Rule_National_"))
            for identity in visible
        )
        for path in sorted(files):
            raw = path.read_text(encoding="utf-8")
            rule = yaml.safe_load(raw)
            identity = rule["rule_id"]
            assert identity in visible
            response = client.post(
                base + "/api/dsl/test",
                json={"rule_id": identity, "inputs": rule["example_inputs"]},
                timeout=(5, 30),
            )
            response.raise_for_status()
            saved = response.json()["result"]
            expected_status = rule["example_expected"].get("status", "CALCULATED")
            assert saved["status"] == expected_status, saved
            expected = rule["example_expected"]["amount"]
            assert float(saved["final_result"]) == expected
            response = client.post(
                base + "/api/dsl/preview",
                json={"yaml_content": raw, "inputs": rule["example_inputs"]},
                timeout=(5, 30),
            )
            response.raise_for_status()
            assert response.json()["result"] == saved
            report["rules"].append(
                {
                    "rule_id": identity,
                    "amount_yuan": expected,
                    "status": expected_status,
                    "saved_and_draft_identical": True,
                }
            )
        response = client.get(base + "/api/knowledge/documents", timeout=(5, 30))
        response.raise_for_status()
        listed = response.json()
        names = {row["id"] for row in listed["documents"]}
        expected_names = {Path(item["upload_path"]).name for item in all_files}
        assert expected_names.issubset(names)
        assert (
            len(names) == listed["total"] == len(expected_names) + 1
        )  # Accepted official sources plus the unrelated user math document.
        report["visible_documents"] = listed["total"]
        for query in [
            "常州公积金装修提取条件",
            "常州异地就医备案材料",
            "常州2026居民医保政策",
        ]:
            response = client.post(
                base + "/api/knowledge/search",
                json={"query": query, "top_k": 8, "threshold": 0.2},
                timeout=(5, 60),
            )
            response.raise_for_status()
            results = response.json()["results"]
            assert results and all(row["id"] in expected_ids for row in results)
            assert any("changzhou.gov.cn" in row["source"] for row in results)
            report["searches"].append(
                {"query": query, "sources": [row["source"] for row in results]}
            )
        if corpus_files:
            corpus_ids = {identity for item in corpus_files for identity in item["vector_ids"]}
            for query in [
                "天宁区 出生一件事 办理材料",
                "钟楼区 企业开办 办理地点",
                "常州高效办成一件事 新出生儿 出生",
                "常州公积金 线上业务 服务网点",
            ]:
                response = client.post(
                    base + "/api/knowledge/search",
                    json={"query": query, "top_k": 20, "threshold": 0.2},
                    timeout=(5, 60),
                )
                response.raise_for_status()
                results = response.json()["results"]
                assert results and all(row["id"] in expected_ids for row in results)
                assert any(row["id"] in corpus_ids for row in results), query
                report["corpus_searches"].append({
                    "query": query,
                    "corpus_hits": sum(row["id"] in corpus_ids for row in results),
                    "sources": [row["source"] for row in results],
                })
            for item in corpus_files:
                source_url = item["source_url"]
                assert source_url.startswith("/api/knowledge/documents/")
                response = client.get(base + source_url, timeout=(5, 30))
                response.raise_for_status()
                assert hashlib.sha256(response.content).hexdigest() == item["source_version"]
                report["corpus_source_downloads"].append(Path(item["upload_path"]).name)
        examples = [
            faq[0],
            next(entry for entry in faq if "异地就医" in entry["topic"]),
            next(entry for entry in faq if "苏州" in entry["question"]),
            faq[-1],
        ]
        for entry in examples:
            response = client.post(
                base + "/api/agent/chat",
                json={"message": entry["question"]},
                timeout=(5, 60),
            )
            response.raise_for_status()
            answer = response.json()
            assert answer["metadata"]["route"] == "faq_cache", {
                "query": entry["question"], "route": answer["metadata"].get("route")
            }
            assert answer["message"] == entry["answer"]
            assert (
                answer["metadata"]["source_body_sha256"] == entry["source_body_sha256"]
            )
            report["faq_api"].append(
                {
                    "question": entry["question"],
                    "source": entry["source"],
                    "route": "faq_cache",
                }
            )
        response = client.get(
            base + "/api/knowledge-graph/graph/stats", timeout=(5, 30)
        )
        response.raise_for_status()
        report["graph_api"] = response.json()
        assert report["graph_api"]["exists"] and report["graph_api"]["nodes"] > 0
    report["status"] = "verified"
    report["source_manifest_sha256"] = hashlib.sha256(
        (CATALOG / "import_changzhou_20261121.json").read_bytes()
    ).hexdigest()
    if corpus_files:
        report["corpus_manifest_sha256"] = hashlib.sha256(
            (CATALOG / "import_changzhou_corpus_20261121.json").read_bytes()
        ).hexdigest()
    (CATALOG / "changzhou_verification_20261121.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"rules", "searches", "faq_api"}
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
