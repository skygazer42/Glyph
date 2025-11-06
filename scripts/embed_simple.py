#!/usr/bin/env python3
"""
简化版数据嵌入脚本 - 直接嵌入到 Milvus

跳过复杂的导入，直接使用核心组件
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print(" 政策文档嵌入系统 (简化版)")
print("=" * 70)
print()

# 查找 Markdown 文件
data_dir = "/data/temp33/gov/data/process"
md_files = list(Path(data_dir).rglob("*.md"))

print(f"📁 数据目录: {data_dir}")
print(f"✓ 找到 {len(md_files)} 个 Markdown 文件\n")

for i, file in enumerate(md_files[:10], 1):
    print(f"  {i}. {file.name}")

if len(md_files) > 10:
    print(f"  ... 还有 {len(md_files) - 10} 个文件")

print("\n" + "=" * 70)
print(" 加载配置")
print("=" * 70)
print()

from config.settings import settings

print("📋 配置信息:")
print(f"  - LLM: {settings.model.llm_model_name}")
print(f"  - Embedding: {settings.embedding.backend} - {settings.embedding.dashscope_model if settings.embedding.backend == 'dashscope' else settings.embedding.openai_model}")
print(f"  - Dimension: {settings.embedding.dimension}")
print(f"  - Milvus: {settings.database.milvus_host}:{settings.database.milvus_port}")
print(f"  - Collection: {settings.database.milvus_collection_name}")

print("\n" + "=" * 70)
print(" 直接使用 LlamaIndex + Milvus")
print("=" * 70)
print()

try:
    from llama_index.core import (
        Document,
        VectorStoreIndex,
        Settings,
        StorageContext
    )
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.vector_stores.milvus import MilvusVectorStore
    from llama_index.embeddings.dashscope import (
        DashScopeEmbedding,
        DashScopeTextEmbeddingModels,
        DashScopeTextEmbeddingType,
    )

    print("✓ LlamaIndex 模块导入成功")

except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("\n请安装依赖:")
    print("  pip install llama-index llama-index-vector-stores-milvus llama-index-embeddings-dashscope")
    sys.exit(1)

print()

# 配置 DashScope Embedding
print("🔧 配置 Embedding 模型...")

try:
    # DashScope API batch size limit is 10
    embed_model = DashScopeEmbedding(
        model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
        api_key=settings.embedding.dashscope_api_key,
        embed_batch_size=10  # DashScope 最大批量大小为 10
    )

    Settings.embed_model = embed_model
    print("✓ DashScope Embedding 配置成功")

except Exception as e:
    print(f"❌ Embedding 配置失败: {e}")
    sys.exit(1)

print()

# 配置 Milvus
print("🔧 配置 Milvus 向量存储...")

try:
    # DashScope text-embedding-v3 返回 1024 维向量
    embedding_dim = 1024

    vector_store = MilvusVectorStore(
        uri=f"http://{settings.database.milvus_host}:{settings.database.milvus_port}",
        collection_name=settings.database.milvus_collection_name,
        dim=embedding_dim,  # 使用 DashScope 的实际维度
        overwrite=True  # 重新创建集合
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    print(f"✓ Milvus 连接成功 (向量维度: {embedding_dim})")

except Exception as e:
    print(f"❌ Milvus 连接失败: {e}")
    print("\n请确保 Milvus 服务已启动:")
    print("  docker-compose ps")
    sys.exit(1)

print()

# 配置文本分割器
print("🔧 配置文本分割器...")

text_splitter = SentenceSplitter(
    chunk_size=800,
    chunk_overlap=100
)

Settings.text_splitter = text_splitter
print("✓ 文本分割器配置成功")

print()

# 加载文档
print("=" * 70)
print(" 加载文档")
print("=" * 70)
print()

documents = []

for md_file in md_files:
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 创建 Document
        doc = Document(
            text=content,
            metadata={
                'file_name': md_file.name,
                'file_path': str(md_file),
                'source': str(md_file.parent.name)
            }
        )

        documents.append(doc)
        print(f"✓ {md_file.name}")

    except Exception as e:
        print(f"✗ {md_file.name}: {e}")

print(f"\n共加载 {len(documents)} 个文档")

print()

# 构建索引
print("=" * 70)
print(" 构建索引并嵌入到 Milvus")
print("=" * 70)
print()

print("🚀 开始处理...")
print("  - 分割文本")
print("  - 生成向量")
print("  - 存储到 Milvus")
print()

try:
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True
    )

    print()
    print("=" * 70)
    print(" ✓ 索引构建完成！")
    print("=" * 70)
    print()

    # 测试检索
    print("🧪 测试检索功能:")
    print()

    test_queries = [
        "家电补贴申请条件",
        "手机以旧换新",
        "汽车消费券"
    ]

    query_engine = index.as_query_engine(
        similarity_top_k=3
    )

    for i, query in enumerate(test_queries, 1):
        print(f"  查询 {i}: {query}")

        try:
            response = query_engine.query(query)
            print(f"  ✓ 响应: {str(response)[:150]}...")

        except Exception as e:
            print(f"  ✗ 查询失败: {e}")

        print()

    print("=" * 70)
    print(" 🎉 数据嵌入完成！")
    print("=" * 70)
    print()
    print("📝 下一步:")
    print(f"  1. 访问 Attu: http://localhost:8000")
    print(f"  2. 验证数据: python scripts/verify_milvus.py")
    print()

    sys.exit(0)

except Exception as e:
    print()
    print("=" * 70)
    print(" ❌ 错误")
    print("=" * 70)
    print(f"\n{type(e).__name__}: {str(e)}")
    import traceback
    print("\n详细错误信息:")
    traceback.print_exc()
    sys.exit(1)
