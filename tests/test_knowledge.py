#!/usr/bin/env python3
"""
知识库功能测试脚本
测试流程：切块 -> 嵌入 -> 存储 -> 检索
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_knowledge_pipeline():
    print("=" * 60)
    print("知识库功能测试")
    print("=" * 60)

    # 1. 测试配置加载
    print("\n[1] 加载配置...")
    from app.config import settings
    print(f"✓ Embedding后端: {settings.embedding.backend}")
    print(f"✓ Embedding模型: {settings.embedding.dashscope_model}")
    print(f"✓ 切块策略: {settings.llamaindex.chunk_strategy}")
    print(f"✓ 切块大小: {settings.llamaindex.chunk_size}")
    print(f"✓ Milvus地址: {settings.database.milvus_host}:{settings.database.milvus_port}")

    # 2. 初始化组件
    print("\n[2] 初始化组件...")
    from app.knowledge import VectorStore, MilvusStore
    from app.knowledge.llamaindex_integration import LlamaIndexIntegration

    # 初始化向量存储
    milvus_store = MilvusStore()
    print(f"✓ MilvusStore初始化成功")

    # 初始化LlamaIndex
    llama_index = LlamaIndexIntegration()
    print(f"✓ LlamaIndex初始化成功")

    # 3. 选择测试文档
    test_file = Path("/data/temp33/Glyph/resources/data/raw/关于追加2025年政府汽车消费补贴资金额度的公告.docx")
    print(f"\n[3] 测试文档: {test_file.name}")

    # 4. 文档解析和切块
    print("\n[4] 文档解析和切块...")
    from llama_index.core import SimpleDirectoryReader

    # 读取文档
    reader = SimpleDirectoryReader(input_files=[str(test_file)])
    documents = reader.load_data()
    print(f"✓ 读取文档数: {len(documents)}")

    # 切块
    chunks = llama_index.chunk_documents(documents)
    print(f"✓ 切块数量: {len(chunks)}")

    # 显示前3个切块
    print("\n前3个切块预览:")
    for i, chunk in enumerate(chunks[:3], 1):
        text_preview = chunk.text[:100].replace('\n', ' ')
        print(f"  切块{i}: {text_preview}...")

    # 5. 生成嵌入向量
    print("\n[5] 生成嵌入向量...")
    from app.knowledge.embeddings import get_embedding_model

    embed_model = get_embedding_model()
    print(f"✓ 嵌入模型: {embed_model.__class__.__name__}")

    # 测试单个文本的嵌入
    test_text = chunks[0].text if chunks else "测试文本"
    embedding = embed_model.get_text_embedding(test_text)
    print(f"✓ 向量维度: {len(embedding)}")
    print(f"✓ 向量示例: [{embedding[0]:.4f}, {embedding[1]:.4f}, ..., {embedding[-1]:.4f}]")

    # 6. 存储到Milvus
    print("\n[6] 存储到Milvus...")

    # 准备数据
    texts = [chunk.text for chunk in chunks[:5]]  # 只存储前5个用于测试
    metadatas = [{
        "source": test_file.name,
        "chunk_id": i,
        "text": text[:200]  # 存储文本预览
    } for i, text in enumerate(texts)]

    # 存储
    ids = milvus_store.add_texts(texts, metadatas)
    print(f"✓ 存储文档数: {len(ids)}")
    print(f"✓ 文档ID示例: {ids[:3]}")

    # 7. 测试检索
    print("\n[7] 测试检索...")

    # 测试查询
    query = "汽车消费补贴的金额是多少"
    print(f"查询: {query}")

    # 执行检索
    results = milvus_store.similarity_search(query, k=3)

    print(f"\n✓ 检索结果数: {len(results)}")
    for i, (doc, score) in enumerate(results, 1):
        text_preview = doc.page_content[:100].replace('\n', ' ')
        print(f"\n  结果{i} (相似度: {score:.4f}):")
        print(f"    {text_preview}...")

    # 8. 统计信息
    print("\n[8] 统计信息...")
    try:
        collection_stats = milvus_store.get_collection_stats()
        print(f"✓ Collection名称: {milvus_store.collection_name}")
        print(f"✓ 文档总数: {collection_stats.get('row_count', 'N/A')}")
    except:
        print("✓ Collection创建成功")

    print("\n" + "=" * 60)
    print("✅ 知识库功能测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_knowledge_pipeline()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)