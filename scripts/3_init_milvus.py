#!/usr/bin/env python
"""Initialize Milvus collection for testing."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.knowledge.milvus import MilvusStore
from app.config import settings

def init_milvus_collection():
    """Initialize Milvus collection."""
    print("正在初始化 Milvus 集合...")

    try:
        # 创建 MilvusStore 实例，会自动创建集合
        store = MilvusStore()
        print(f"✅ 集合 '{store.collection_name}' 已准备就绪")

        # 显示统计信息
        stats = store.get_stats()
        print(f"📊 统计信息:")
        print(f"  - 集合名称: {stats['collection_name']}")
        print(f"  - 文档数量: {stats['total_documents']}")
        print(f"  - 嵌入维度: {stats['dim']}")
        print(f"  - 后端: {stats['backend']}")
        print(f"  - 模型: {stats['model']}")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False

    return True

if __name__ == "__main__":
    success = init_milvus_collection()
    sys.exit(0 if success else 1)