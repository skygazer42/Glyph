#!/usr/bin/env python3
"""
测试 Milvus 检索功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection
from llama_index.embeddings.dashscope import DashScopeEmbedding, DashScopeTextEmbeddingModels
from config import settings

print("=" * 70)
print(" 测试 Milvus 检索功能")
print("=" * 70)
print()

# 连接 Milvus
print("🔗 连接 Milvus...")
connections.connect(
    alias="default",
    host=settings.database.milvus_host,
    port=str(settings.database.milvus_port)
)
print("✓ 连接成功")
print()

# 加载集合
collection = Collection(settings.database.milvus_collection_name)
collection.load()
print(f"📊 集合: {collection.name}")
print(f"   文档数量: {collection.num_entities}")
print()

# 配置 Embedding 模型
print("🔧 配置 Embedding 模型...")
embed_model = DashScopeEmbedding(
    model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
    api_key=settings.embedding.dashscope_api_key,
    embed_batch_size=10
)
print("✓ Embedding 配置成功")
print()

# 测试查询
test_queries = [
    "家电补贴申请条件",
    "手机以旧换新",
    "汽车消费券如何领取"
]

for i, query in enumerate(test_queries, 1):
    print("=" * 70)
    print(f" 查询 {i}: {query}")
    print("=" * 70)
    print()

    # 生成查询向量
    query_vec = embed_model.get_text_embedding(query)

    # 向量检索
    results = collection.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "IP"},
        limit=3,
        output_fields=["text", "file_name", "source"]
    )

    # 显示结果
    print(f"找到 {len(results[0])} 个相关结果:\n")

    for j, hit in enumerate(results[0], 1):
        score = hit.score
        text = hit.entity.get('text', '')
        file_name = hit.entity.get('file_name', '未知')
        source = hit.entity.get('source', '未知')

        print(f"  [{j}] 相似度: {score:.4f}")
        print(f"      文件: {file_name}")
        print(f"      来源: {source}")
        print(f"      内容: {text[:150]}...")
        print()

print("=" * 70)
print(" ✓ 检索测试完成")
print("=" * 70)
print()
print("📋 总结:")
print(f"  - 集合: {collection.name}")
print(f"  - 文档数量: {collection.num_entities}")
print(f"  - 向量维度: 1024")
print(f"  - 测试查询: {len(test_queries)} 个")
print()

# 清理
connections.disconnect("default")
