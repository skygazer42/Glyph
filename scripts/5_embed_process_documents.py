#!/usr/bin/env python3
"""
Embed policy process documents under resources/data/process into the knowledge store.

Usage examples:
    python scripts/5_embed_process_documents.py
    python scripts/5_embed_process_documents.py --input-dir data/custom --batch-size 5
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from app.knowledge.service import KnowledgeService
from app.knowledge import DocumentLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed documents from resources/data/process into Milvus / hierarchical index."
    )
    parser.add_argument(
        "--input-dir",
        default="resources/data/process",
        help="Directory that contains process documents (default: resources/data/process).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="How many documents to send per indexing batch (default: 10).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of documents to ingest (default: unlimited).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report documents without sending them to the vector store.",
    )
    return parser.parse_args()


async def ingest_documents(
    input_dir: str,
    batch_size: int,
    limit: Optional[int],
    dry_run: bool,
) -> None:
    loader = DocumentLoader()
    knowledge_service = KnowledgeService()

    source_path = Path(input_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"输入目录不存在：{input_dir}")

    logger.info("开始读取目录：%s", source_path.resolve())
    batch = []
    loaded = 0
    indexed = 0

    async def flush_batch():
        nonlocal batch, indexed
        if not batch:
            return
        if dry_run:
            logger.info("Dry-run 模式：跳过向量入库，批次大小 %s", len(batch))
        else:
            inserted = await knowledge_service.index_documents(batch)
            indexed += inserted
            logger.info("已写入 %s 篇文档到向量存储", inserted)
        batch = []

    for document in loader.iter_documents_from_directory(str(source_path), limit=limit):
        batch.append(document)
        loaded += 1
        if len(batch) >= batch_size:
            await flush_batch()

    if batch:
        await flush_batch()

    logger.success(
        "处理完成：读取 %s 篇文档，%s",
        loaded,
        "dry-run 模式未写入向量库" if dry_run else f"成功写入 {indexed} 篇到向量库",
    )


def main() -> None:
    args = parse_args()
    asyncio.run(
        ingest_documents(
            input_dir=args.input_dir,
            batch_size=max(1, args.batch_size),
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
