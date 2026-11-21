#!/usr/bin/env python3
"""
Embed policy process documents into the knowledge store.

Usage examples:
    python -m scripts.embed_process_documents
    python -m scripts.embed_process_documents --input-dir data/custom --batch-size 5
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Optional

import anyio
from loguru import logger

from app.knowledge.document_loader import DocumentLoader
from app.knowledge.service import KnowledgeService
from app.models.policy import PolicyDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed documents into Milvus; build hierarchical indexes separately.")
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
    """分批解析目录文档并追加到向量库，不构建分级索引。

    limit=None 表示不限数量，0 表示不读取或写入；dry_run 仅解析和报告。
    入库失败向调用方传播，已完成批次不回滚，退出时关闭本函数创建的服务。
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if limit is not None and limit < 0:
        raise ValueError("limit must not be negative")
    loader = DocumentLoader()

    source_path = Path(input_dir)
    if not await asyncio.to_thread(source_path.is_dir):
        raise NotADirectoryError(f"输入目录无效：{input_dir}")
    if limit == 0:
        logger.info("limit=0: 未读取或写入文档")
        return

    knowledge_service = None if dry_run else await anyio.to_thread.run_sync(
        lambda: KnowledgeService(use_hierarchical=False),
    )
    try:
        logger.info("开始读取目录：{}", source_path)
        batch: list[PolicyDocument] = []
        loaded = 0
        indexed = 0

        async def flush_batch() -> None:
            nonlocal batch, indexed
            if not batch:
                return
            if dry_run:
                logger.info("Dry-run 模式：跳过向量入库，批次大小 {}", len(batch))
            else:
                assert knowledge_service is not None
                inserted = await knowledge_service.index_documents(batch)
                indexed += inserted
                logger.info("已写入 {} 篇文档到向量存储", inserted)
            batch = []

        documents = iter(loader.iter_documents_from_directory(str(source_path), limit=limit))
        while True:
            document = await asyncio.to_thread(next, documents, None)
            if document is None:
                break
            batch.append(document)
            loaded += 1
            if len(batch) >= batch_size:
                await flush_batch()

        if batch:
            await flush_batch()

        logger.success(
            "处理完成：读取 {} 篇文档，{}",
            loaded,
            "dry-run 模式未写入向量库" if dry_run else f"成功写入 {indexed} 篇到向量库",
        )
    finally:
        if knowledge_service is not None:
            with anyio.fail_after(5, shield=True):
                await knowledge_service.close()


def main() -> None:
    """解析命令行选项并运行文档入库；错误由命令行进程暴露。"""
    args = parse_args()
    asyncio.run(
        ingest_documents(
            input_dir=args.input_dir,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
