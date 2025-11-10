#!/usr/bin/env python3
"""
测试完整的问答流程: 检索 + LLM 回答
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
from openai import OpenAI
from app.config import settings

print("=" * 70)
print(" 政策问答系统测试")
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

# 3. 配置 LLM
print("🔧 配置 LLM...")
llm_client = OpenAI(
    api_key=settings.model.llm_api_key,
    base_url=settings.model.llm_base_url
)
print(f"✓ LLM 配置成功 ({settings.model.llm_model_name})")
print()

# 测试问题
test_questions = [
    "济南市家电以旧换新的补贴标准是多少？",
    "购买手机可以享受多少补贴？需要什么条件？",
    "汽车消费券有哪些档位？每个档位能领多少钱？",
]

for i, question in enumerate(test_questions, 1):
    print("=" * 70)
    print(f" 问题 {i}: {question}")
    print("=" * 70)
    print()

    # Step 1: 向量检索
    print("🔍 检索相关文档...")
    query_vec = embed_model.get_text_embedding(question)

    results = collection.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "IP"},
        limit=5,  # 检索 Top 5
        output_fields=["text", "file_name", "source"]
    )

    # 提取检索结果
    contexts = []
    print(f"✓ 找到 {len(results[0])} 个相关文档:\n")

    for j, hit in enumerate(results[0], 1):
        text = hit.entity.get('text', '')
        file_name = hit.entity.get('file_name', '未知')
        score = hit.score

        contexts.append(text)
        print(f"  [{j}] 相似度: {score:.4f} | {file_name[:50]}...")

    print()

    # Step 2: 构建 Prompt
    print("💭 生成回答...")

    context_text = "\n\n---\n\n".join(contexts)

    prompt = f"""你是一个政策咨询助手，专门解答济南市的消费补贴政策问题。

请根据以下政策文档内容回答用户的问题。要求：
1. 回答要准确、具体，直接引用政策原文的数字和条件
2. 如果有多个档位或标准，请分条列出
3. 如果文档中没有相关信息，请明确说明
4. 保持简洁专业的语气

政策文档内容：
{context_text}

用户问题：{question}

回答："""

    # Step 3: LLM 生成回答
    try:
        response = llm_client.chat.completions.create(
            model=settings.model.llm_model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的政策咨询助手，擅长解答消费补贴政策问题。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )

        answer = response.choices[0].message.content

        print("=" * 70)
        print(" 📝 回答")
        print("=" * 70)
        print()
        print(answer)
        print()

    except Exception as e:
        print(f"❌ LLM 回答失败: {e}")
        print()

print("=" * 70)
print(" ✓ 测试完成")
print("=" * 70)
print()
print("📊 统计:")
print(f"  - 测试问题: {len(test_questions)} 个")
print(f"  - 向量数据库: Milvus ({collection.num_entities} 文档)")
print(f"  - Embedding: DashScope text-embedding-v3 (1024维)")
print(f"  - LLM: {settings.model.llm_model_name}")
print()

# 清理
connections.disconnect("default")
