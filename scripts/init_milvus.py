#!/usr/bin/env python
"""Initialize the Milvus collection with python -m scripts.init_milvus."""

import sys

from app.knowledge.milvus import MilvusStore

def init_milvus_collection() -> bool:
    """Initialize Milvus collection."""
    print("正在初始化 Milvus 集合...")

    store = None
    try:
        # 创建 MilvusStore 实例，会自动创建集合
        store = MilvusStore()
        print(f"[OK] Collection '{store.collection_name}' is ready")

        # 显示统计信息
        stats = store.get_stats()
        print("[STATS] Statistics:")
        print(f"  - 集合名称: {stats['collection_name']}")
        print(f"  - 文档数量: {stats['total_documents']}")
        print(f"  - 嵌入维度: {stats['dim']}")
        print(f"  - 后端: {stats['backend']}")
        print(f"  - 模型: {stats['model']}")

    except Exception as e:
        print(f"[ERROR] Initialization failed: {e}")
        return False
    finally:
        if store is not None:
            store.close()

    return True

if __name__ == "__main__":
    success = init_milvus_collection()
    sys.exit(0 if success else 1)
