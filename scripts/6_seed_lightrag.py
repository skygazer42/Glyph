#!/usr/bin/env python3
"""
Seed LightRAG storage with documents from resources/data/process (or a custom directory).

This is a lightweight CLI wrapper around GraphRetrieverAgent.add_documents so you can
rebuild the LightRAG working directory without启动整个服务。
"""

from __future__ import annotations

import argparse
import asyncio
import anyio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger  # noqa: E402 - executable script bootstraps the repository path

from app.agents.packs.graph_retriever.node import GraphRetrieverAgent  # noqa: E402 - executable script bootstraps the repository path
from app.knowledge.document_loader import DocumentLoader  # noqa: E402 - executable script bootstraps the repository path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed documents into LightRAG storage (resources/data/lightrag by default)."
    )
    parser.add_argument(
        "--input-dir",
        default="resources/data/process",
        help="Directory containing docs to ingest (default: resources/data/process).",
    )
    parser.add_argument(
        "--workdir",
        default=os.getenv("LIGHTRAG_WORKDIR", "resources/data/lightrag"),
        help="LightRAG working directory (default: env LIGHTRAG_WORKDIR or resources/data/lightrag).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Documents per ingestion batch (default: 5).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max documents to ingest (default: unlimited).",
    )
    return parser.parse_args()


async def seed_lightrag(
    input_dir: str,
    workdir: str,
    batch_size: int,
    limit: Optional[int],
) -> None:
    source_path = Path(input_dir)
    if not await asyncio.to_thread(source_path.exists):
        raise FileNotFoundError(f"输入目录不存在：{input_dir}")

    loader = DocumentLoader()
    agent = await asyncio.to_thread(GraphRetrieverAgent, working_dir=workdir)

    try:
        docs: list[Any] = []
        loaded = 0

        async def flush():
            nonlocal docs
            if not docs:
                return
            await agent.add_documents(docs)
            logger.info("已向 LightRAG 写入 {} 篇文档", len(docs))
            docs = []

        documents = iter(loader.iter_documents_from_directory(str(source_path), limit=limit))
        while True:
            document = await asyncio.to_thread(next, documents, None)
            if document is None:
                break
            docs.append(document)
            loaded += 1
            if len(docs) >= batch_size:
                await flush()

        if docs:
            await flush()

        await asyncio.to_thread(write_seed_manifest, source_path, Path(workdir))
        logger.success("LightRAG 导入完成，共处理 {} 篇文档，工作目录：{}", loaded, workdir)
    finally:
        with anyio.fail_after(5, shield=True):
            await agent.close()


def write_seed_manifest(source_dir: Path, workdir: Path) -> None:
    manifest = {}
    for file in source_dir.rglob("*"):
        if file.is_file():
            stat = file.stat()
            manifest[str(file.relative_to(source_dir))] = {
                "size": int(stat.st_size),
                "mtime": int(stat.st_mtime),
            }
    payload = {
        "seed_dir": str(source_dir.resolve()),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "files": manifest,
    }
    workdir.mkdir(parents=True, exist_ok=True)
    manifest_path = workdir / "seed_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已更新种子清单：{}", manifest_path)


def main() -> None:
    args = parse_args()
    asyncio.run(
        seed_lightrag(
            input_dir=args.input_dir,
            workdir=args.workdir,
            batch_size=max(1, args.batch_size),
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
