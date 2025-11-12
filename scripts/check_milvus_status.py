#!/usr/bin/env python
"""检查Milvus数据库状态"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from pymilvus import connections, utility, Collection
from app.config import settings

# 连接Milvus
connections.connect(
    alias="default",
    host=settings.database.milvus_host,
    port=str(settings.database.milvus_port)
)

print("=" * 60)
print("Milvus 数据库状态")
print("=" * 60)
print()

# 列出所有集合
collections = utility.list_collections()
print(f"集合列表: {collections}")
print()

# 检查主要集合
for collection_name in collections:
    try:
        collection = Collection(collection_name)
        collection.load()

        print(f"集合: {collection_name}")
        print(f"  - 文档数量: {collection.num_entities}")
        print(f"  - 架构: {[f.name for f in collection.schema.fields]}")

        # 如果是policy_documents，显示更多信息
        if collection_name == "policy_documents":
            # 获取几个样本
            results = collection.query(
                expr="",
                limit=5,
                output_fields=["title", "source"]
            )
            if results:
                print(f"  - 样本数据:")
                for i, doc in enumerate(results[:3], 1):
                    title = doc.get("title", "无标题")[:50]
                    source = doc.get("source", "未知")[:50]
                    print(f"    {i}. {title}... (来源: {source})")
        print()

    except Exception as e:
        print(f"  错误: {e}")
        print()