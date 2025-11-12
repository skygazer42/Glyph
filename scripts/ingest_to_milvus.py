#!/usr/bin/env python3
"""
导入政策文档到Milvus向量数据库
"""

import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.knowledge.milvus import MilvusStore
from app.agents.framework.base.types import PolicyDocument
from app.utils.document_loader import DocumentLoader


def ingest_documents():
    """导入文档到Milvus"""
    print("开始导入政策文档到Milvus...")

    # 创建MilvusStore
    store = MilvusStore()
    loader = DocumentLoader()

    # 导入的目录
    paths = [
        "resources/data/process/md2025年家电和数码以旧换新政策文件",
        "resources/data/process/md市级消费活动政策"
    ]

    total_docs = 0
    for path in paths:
        print(f"\n处理目录: {path}")

        if not Path(path).exists():
            print(f"  ❌ 目录不存在: {path}")
            continue

        # 加载文档
        docs = []
        try:
            for doc in loader.iter_documents_from_directory(path):
                docs.append(doc)
        except Exception as e:
            print(f"  ❌ 加载失败: {e}")
            continue

        if docs:
            # 批量添加到Milvus
            store.add_documents(docs)
            total_docs += len(docs)
            print(f"  ✅ 导入 {len(docs)} 个文档")
        else:
            print(f"  ⚠️ 没有找到文档")

    # 显示统计
    stats = store.get_stats()
    print(f"\n📊 导入完成!")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  新增文档: {total_docs}")
    print(f"  集合名称: {stats['collection_name']}")
    print(f"  嵌入维度: {stats['dim']}")


if __name__ == "__main__":
    ingest_documents()