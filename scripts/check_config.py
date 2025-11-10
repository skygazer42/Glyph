#!/usr/bin/env python3
"""
系统配置检查脚本
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from pymilvus import connections, utility

print("=" * 70)
print(" 系统配置检查")
print("=" * 70)
print()

# 1. LLM 配置
print("🤖 LLM 配置:")
print(f"  模型: {settings.model.llm_model_name}")
print(f"  API: {settings.model.llm_base_url}")
print(f"  Key: {'✅ 已配置' if settings.model.llm_api_key else '❌ 未配置'}")
print()

# 2. Embedding 配置
print("🔤 Embedding 配置:")
print(f"  后端: {settings.embedding.backend}")
print(f"  模型: {settings.embedding.dashscope_model if settings.embedding.backend == 'dashscope' else settings.embedding.openai_model}")
print(f"  维度: {settings.embedding.dimension}")
print(f"  批量大小: {settings.embedding.batch_size}")
print(f"  Key: {'✅ 已配置' if settings.embedding.dashscope_api_key else '❌ 未配置'}")
print()

# 3. Reranker 配置
print("🎯 Reranker 配置:")
try:
    # 检查配置文件中的 reranker 设置
    reranker_backend = os.getenv("RERANKER_BACKEND", "dashscope")
    reranker_model = os.getenv("RERANKER_MODEL", "gte-rerank-v2")
    reranker_top_k = os.getenv("RERANKER_TOP_K", "20")
    reranker_top_n = os.getenv("RERANKER_TOP_N", "5")

    print(f"  后端: {reranker_backend}")
    print(f"  模型: {reranker_model}")
    print(f"  召回策略: 向量检索(Top {reranker_top_k}) → Reranker(Top {reranker_top_n})")
    print(f"  Key: {'✅ 已配置' if os.getenv('DASHSCOPE_API_KEY') else '❌ 未配置'}")
except Exception as e:
    print(f"  ⚠️  配置读取失败: {e}")
print()

# 4. Milvus 配置
print("💾 Milvus 配置:")
print(f"  地址: {settings.database.milvus_host}:{settings.database.milvus_port}")
print(f"  集合: {settings.database.milvus_collection_name}")

try:
    connections.connect(
        alias="check",
        host=settings.database.milvus_host,
        port=str(settings.database.milvus_port)
    )

    # 检查集合
    if utility.has_collection(settings.database.milvus_collection_name):
        from pymilvus import Collection
        collection = Collection(settings.database.milvus_collection_name)
        collection.load()
        print(f"  状态: ✅ 运行中")
        print(f"  文档数: {collection.num_entities}")
    else:
        print(f"  状态: ⚠️  集合不存在")

    connections.disconnect("check")

except Exception as e:
    print(f"  状态: ❌ 连接失败 ({e})")
print()

# 5. Neo4j 配置
print("🕸️  Neo4j 配置:")
neo4j_enabled = os.getenv("DATABASE__USE_NEO4J", "false").lower() == "true"
neo4j_uri = os.getenv("DATABASE__NEO4J_URI", "bolt://localhost:7687")

if neo4j_enabled:
    print(f"  状态: ✅ 已启用")
    print(f"  地址: {neo4j_uri}")
    print(f"  用户: {os.getenv('DATABASE__NEO4J_USER', 'neo4j')}")
else:
    print(f"  状态: ⚠️  未启用")
print()

# 6. 文档处理器配置
print("📄 文档处理器:")
doc_processor = os.getenv("DOCUMENT_PROCESSOR", "rapid_ocr")
rapidocr_enabled = os.getenv("RAPIDOCR_ENABLED", "false").lower() == "true"

print(f"  当前: {doc_processor}")
if rapidocr_enabled:
    print(f"  RapidOCR: ✅ 已启用")
    print(f"  模型目录: {os.getenv('RAPIDOCR_MODEL_DIR', './models')}")
else:
    print(f"  RapidOCR: ⚠️  未启用")
print()

# 7. 性能配置
print("⚡ 性能配置:")
print(f"  并发查询: {settings.performance.max_concurrent_queries}")
print(f"  批量大小: {settings.performance.batch_size}")
print(f"  缓存: {'✅ 启用' if settings.performance.enable_cache else '❌ 禁用'}")
print()

print("=" * 70)
print(" 配置检查完成")
print("=" * 70)
print()

# 推荐操作
print("💡 推荐操作:")
print("  1. 测试 Reranker: python scripts/test_reranker.py")
print("  2. 测试问答: python scripts/test_qa.py")
print("  3. 验证数据: python scripts/verify_milvus.py")
print("  4. 查看文档: docs/OPTIMIZATION_SUMMARY.md")
print()
