"""Add verified service passages to the new Changzhou graph namespace."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from scripts.official_policy_data import load_curated_faq, load_official_policies

ROOT = Path(__file__).resolve().parents[1]


async def build() -> None:
    """Index quoted evidence with explicit source boundaries, then check disk status."""
    from app.agents.packs.graph_retriever.node import GraphRetrieverAgent
    from app.models.policy import PolicyDocument, PolicyType

    policies = load_official_policies(ROOT)
    faq = load_curated_faq(ROOT, policies)
    services = [item for item in policies if "/services/" in item["markdown_path"]]
    blocks = []
    records = []
    for item in services:
        quotes = list(
            dict.fromkeys(
                entry["source_quote"] for entry in faq if entry["source"] == item["url"]
            )
        )
        if not quotes:
            quotes = [item["body"]]
        blocks.append(
            f"## {item['title']}\n适用地区：{item['scope']}\n"
            f"来源：{item['url']}\n原文核验日期：{item['retrieved_date']}\n"
            f"官方原文摘录（非全文，办理以现行官方要求为准）：\n" + "\n\n".join(quotes)
        )
        records.append(
            {
                "title": item["title"],
                "url": item["url"],
                "scope": item["scope"],
                "body_sha256": item["body_sha256"],
                "passage_count": len(quotes),
                "markdown_path": item["markdown_path"],
            }
        )
    text = "# 常州政务服务官方来源证据摘录\n\n" + "\n\n".join(blocks)
    seed = ROOT / "resources/data/graph_seed"
    seed.mkdir(parents=True, exist_ok=True)
    path = seed / "changzhou_services_20261121.md"
    path.write_text(text + "\n", encoding="utf-8")
    document = PolicyDocument(
        title="常州政务服务官方来源证据摘录",
        content=text,
        source=path.relative_to(ROOT).as_posix(),
        doc_type=PolicyType.GUIDELINE,
    )
    workdir = Path(os.environ["LIGHTRAG_WORKDIR"])
    agent = GraphRetrieverAgent(working_dir=str(workdir))
    try:
        await agent.add_documents([document])
    finally:
        await agent.close()
    docs = json.loads((workdir / "kv_store_full_docs.json").read_text(encoding="utf-8"))
    status = json.loads(
        (workdir / "kv_store_doc_status.json").read_text(encoding="utf-8")
    )
    matches = [
        identity
        for identity, row in docs.items()
        if row["content"] == document.title + "\n" + document.content
    ]
    if len(matches) != 1 or status[matches[0]]["status"] != "processed":
        raise RuntimeError("Service graph document did not reach processed status")
    report = {
        "status": "verified",
        "date": "2026-11-21",
        "workdir": str(workdir),
        "service_sources": records,
        "service_source_count": len(records),
        "service_corpus_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "service_graph_document_id": matches[0],
        "coverage": "10 complete housing documents plus selected source-verified service passages",
    }
    (ROOT / "resources/data/policy_catalog/changzhou_graph_20261121.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Verified service source passages:", len(records), flush=True)


def main() -> None:
    """Use the project runtime profile without the known unavailable local proxy."""
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env.siliconflow.local", override=True)
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
    asyncio.run(build())


if __name__ == "__main__":
    main()
