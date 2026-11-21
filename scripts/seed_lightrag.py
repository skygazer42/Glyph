#!/usr/bin/env python3
"""
Seed LightRAG with python -m scripts.seed_lightrag.

This is a lightweight CLI wrapper around GraphRetrieverAgent.add_documents so you can
rebuild the LightRAG working directory without启动整个服务。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import anyio
from loguru import logger

from app.agents.packs.graph_retriever.node import GraphRetrieverAgent
from app.knowledge.document_loader import DocumentLoader
from app.models.policy import PolicyDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed official Changzhou documents into the configured LightRAG storage."
    )
    parser.add_argument(
        "--input-dir",
        default="resources/data/process/changzhou_20261121",
        help="Directory containing official Changzhou docs to ingest.",
    )
    parser.add_argument(
        "--workdir",
        default=os.getenv("LIGHTRAG_WORKDIR", "resources/data/lightrag_changzhou_20261121"),
        help="LightRAG working directory for the accepted Changzhou corpus.",
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
    """将目录文档分批写入 LightRAG，退出时关闭本次创建的图谱智能体。

    limit=None 才在完成后更新完整种子清单，0 表示不导入；批次失败直接传播，
    此前写入的批次不会回滚。
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if limit is not None and limit < 0:
        raise ValueError("limit must not be negative")
    source_path = Path(input_dir)
    if not await asyncio.to_thread(source_path.is_dir):
        raise NotADirectoryError(f"输入目录无效：{input_dir}")
    if limit == 0:
        logger.info("limit=0: 未读取或写入文档")
        return

    loader = DocumentLoader()
    agent = await anyio.to_thread.run_sync(lambda: GraphRetrieverAgent(working_dir=workdir))

    try:
        docs: list[PolicyDocument] = []
        loaded = 0

        async def flush() -> None:
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

        if limit is None:
            await asyncio.to_thread(
                write_seed_manifest, source_path, Path(workdir), loader.supported_extensions,
            )
        logger.success("LightRAG 导入完成，共处理 {} 篇文档，工作目录：{}", loaded, workdir)
    finally:
        with anyio.fail_after(5, shield=True):
            await agent.close()


def write_seed_manifest(source_dir: Path, workdir: Path, supported_extensions: set[str]) -> None:
    """记录目录内支持格式文件的大小和修改时间；清单用于识别种子状态，不包含内容哈希。"""
    manifest = {}
    for file in source_dir.rglob("*"):
        if file.is_file() and file.suffix.lower() in supported_extensions:
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
    """读取命令行选项并执行 LightRAG 导入，保留失败退出语义。"""
    args = parse_args()
    asyncio.run(
        seed_lightrag(
            input_dir=args.input_dir,
            workdir=args.workdir,
            batch_size=args.batch_size,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
