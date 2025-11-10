#!/usr/bin/env python3
"""
测试 Reranker 召回功能
"""

import sys
import os
from pathlib import Path

# 清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if key in os.environ:
        del os.environ[key]

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection
from llama_index.embeddings.dashscope import DashScopeEmbedding, DashScopeTextEmbeddingModels
from app.config import settings
import requests

print("=" * 70)
print(" Reranker 召回功能测试")
print("=" * 70)
print()

# 1. 连接 Milvus
print("🔗 连接 Milvus...")
connections.connect(
    alias="default",
    host=settings.database.milvus_host,
    port=str(settings.database.milvus_port)
)

collection = Collection(settings.database.milvus_collection_name)
collection.load()
print(f"✓ 已连接 (文档数: {collection.num_entities})")
print()

# 2. 配置 Embedding 模型
print("🔧 配置 Embedding 模型...")
embed_model = DashScopeEmbedding(
    model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
    api_key=settings.embedding.dashscope_api_key,
    embed_batch_size=10
)
print("✓ Embedding 配置成功")
print()

# 测试问题
question = "购买手机可以享受多少补贴？需要什么条件？"

print("=" * 70)
print(f" 测试问题: {question}")
print("=" * 70)
print()

# Step 1: 向量检索 (召回更多候选)
print("🔍 第一阶段: 向量检索 (召回 Top 20)...")
query_vec = embed_model.get_text_embedding(question)

results = collection.search(
    data=[query_vec],
    anns_field="embedding",
    param={"metric_type": "IP"},
    limit=20,  # 召回 20 个候选
    output_fields=["text", "file_name", "source"]
)

# 提取召回结果
candidates = []
print(f"✓ 召回 {len(results[0])} 个候选文档:\n")

for j, hit in enumerate(results[0][:10], 1):  # 只显示前 10 个
    text = hit.entity.get('text', '')
    file_name = hit.entity.get('file_name', '未知')
    score = hit.score

    candidates.append({
        'text': text,
        'file_name': file_name,
        'vector_score': score
    })

    print(f"  [{j}] 向量相似度: {score:.4f} | {file_name[:50]}...")

# 为所有 20 个候选准备数据
for hit in results[0][10:]:
    candidates.append({
        'text': hit.entity.get('text', ''),
        'file_name': hit.entity.get('file_name', '未知'),
        'vector_score': hit.score
    })

print()

# Step 2: Reranker 重排序
print("🎯 第二阶段: Reranker 重排序 (Top 5)...")
print()

try:
    # 使用 DashScope Reranker API
    url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    headers = {
        "Authorization": f"Bearer {settings.embedding.dashscope_api_key}",
        "Content-Type": "application/json"
    }

    # 限制每个文档的长度（DashScope 限制）
    truncated_docs = [c['text'][:500] for c in candidates]

    payload = {
        "model": "gte-rerank-v2",
        "input": {
            "query": question,
            "documents": truncated_docs
        },
        "parameters": {
            "top_n": 5,
            "return_documents": False
        }
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)

    # 打印详细错误信息
    if response.status_code != 200:
        print(f"❌ API 错误 ({response.status_code}):")
        print(f"响应: {response.text}")
        response.raise_for_status()

    result = response.json()

    if result.get("output") and result["output"].get("results"):
        rerank_results = result["output"]["results"]

        print(f"✓ Reranker 返回 Top {len(rerank_results)} 结果:\n")

        # 显示重排序后的结果
        print("=" * 70)
        print(" 📊 对比: 重排序前 vs 重排序后")
        print("=" * 70)
        print()

        for i, rerank_item in enumerate(rerank_results, 1):
            index = rerank_item['index']
            rerank_score = rerank_item['relevance_score']

            original_candidate = candidates[index]
            vector_score = original_candidate['vector_score']
            file_name = original_candidate['file_name']

            print(f"[{i}] Rerank分数: {rerank_score:.4f} (原向量排名: {index+1}, 分数: {vector_score:.4f})")
            print(f"    文件: {file_name[:60]}...")
            print(f"    内容: {original_candidate['text'][:150]}...")
            print()

        # 统计分析
        print("=" * 70)
        print(" 📈 召回效果分析")
        print("=" * 70)
        print()

        # 检查排序变化
        original_top5_indices = list(range(5))
        reranked_indices = [r['index'] for r in rerank_results]

        changes = sum(1 for i, idx in enumerate(reranked_indices) if idx != i)

        print(f"原始 Top 5 索引: {original_top5_indices}")
        print(f"Rerank Top 5 索引: {reranked_indices}")
        print(f"排序变化: {changes}/5 个结果位置改变")
        print()

        # 显示从后面提升上来的文档
        promoted = [idx for idx in reranked_indices if idx >= 5]
        if promoted:
            print(f"✨ 从后面提升的文档索引: {promoted} (原排名: {[p+1 for p in promoted]})")
        else:
            print("ℹ️  Top 5 内部重排序，无新文档提升")

    else:
        print("❌ Reranker 返回结果异常")
        print(f"响应: {result}")

except Exception as e:
    print(f"❌ Reranker 调用失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print(" ✓ 测试完成")
print("=" * 70)
print()
print("📊 总结:")
print(f"  - 第一阶段: 向量检索召回 20 个候选")
print(f"  - 第二阶段: Reranker 重排序选出 Top 5")
print(f"  - Reranker 模型: gte-rerank-v2 (DashScope)")
print()

# 清理
connections.disconnect("default")
