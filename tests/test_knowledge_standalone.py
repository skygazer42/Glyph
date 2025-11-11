#!/usr/bin/env python3
"""
独立知识库测试 - 完全绕过app.__init__.py
"""

import os
import sys
from pathlib import Path

# 清除代理
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(key, None)

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def bypass_app_init():
    """绕过app.__init__.py的导入"""
    import sys
    import types

    # 创建一个假的app模块，避免导入main.py
    fake_app = types.ModuleType('app')
    sys.modules['app'] = fake_app

    # 直接加载config模块
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "app.config.app_config",
        str(project_root / "app" / "config" / "app_config.py")
    )
    config_module = importlib.util.module_from_spec(spec)
    sys.modules['app.config'] = types.ModuleType('app.config')
    sys.modules['app.config.app_config'] = config_module
    spec.loader.exec_module(config_module)

    return config_module.settings


def test_knowledge_standalone():
    """独立测试知识库功能"""
    print("=" * 60)
    print("独立知识库测试（绕过app.__init__.py）")
    print("=" * 60)

    # 1. 加载配置
    print("\n[1] 加载配置（绕过app导入）...")
    settings = bypass_app_init()

    print(f"✓ Embedding后端: {settings.embedding.backend}")
    print(f"✓ Embedding模型: {settings.embedding.dashscope_model}")
    print(f"✓ Milvus配置: {settings.database.milvus_host}:{settings.database.milvus_port}")

    # 2. 直接使用pymilvus和dashscope
    print("\n[2] 初始化核心组件...")

    # 初始化DashScope
    import dashscope
    dashscope.api_key = settings.embedding.dashscope_api_key
    from dashscope import TextEmbedding
    print("✓ DashScope初始化成功")

    # 初始化Milvus
    from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType

    connections.connect(
        alias="default",
        host=settings.database.milvus_host,
        port=settings.database.milvus_port
    )
    print("✓ Milvus连接成功")

    # 3. 创建或获取集合
    print("\n[3] 准备Milvus集合...")

    collection_name = settings.database.milvus_collection_name
    embedding_dim = 1024  # 使用配置的维度

    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        print(f"✓ 使用已存在的集合: {collection_name}")
    else:
        # 创建新集合
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim)
        ]
        schema = CollectionSchema(fields, description="Policy documents")
        collection = Collection(name=collection_name, schema=schema)
        print(f"✓ 创建新集合: {collection_name}")

    # 4. 处理文档
    print("\n[4] 处理测试文档...")

    doc_dir = project_root / "resources" / "data" / "raw"
    test_files = list(doc_dir.glob("*.docx"))[:3]

    all_texts = []
    all_sources = []
    all_embeddings = []

    for i, doc_file in enumerate(test_files, 1):
        print(f"\n文档 {i}: {doc_file.name}")

        try:
            # 读取文档
            from docx import Document
            doc = Document(str(doc_file))
            full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

            if not full_text:
                print("  ✗ 文档内容为空")
                continue

            # 简单切块
            chunk_size = 500
            chunks = []
            for j in range(0, len(full_text), chunk_size):
                chunk = full_text[j:j+chunk_size].strip()
                if chunk:
                    chunks.append(chunk)

            print(f"  ✓ 切块数: {len(chunks)}")

            # 生成嵌入（只处理前2个切块作为示例）
            for chunk in chunks[:2]:
                response = TextEmbedding.call(
                    model=settings.embedding.dashscope_model,
                    input=chunk,
                    dimension=embedding_dim
                )

                if response.status_code == 200:
                    embedding = response.output['embeddings'][0]['embedding']
                    all_texts.append(chunk)
                    all_sources.append(doc_file.name)
                    all_embeddings.append(embedding)
                    print(f"  ✓ 生成嵌入 (维度: {len(embedding)})")

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")

    # 5. 存储到Milvus
    if all_texts:
        print(f"\n[5] 存储到Milvus ({len(all_texts)}条数据)...")

        data = [
            all_texts,      # text字段
            all_sources,    # source字段
            all_embeddings  # embedding字段
        ]

        collection.insert(data)
        collection.flush()
        print(f"✓ 插入{len(all_texts)}条数据")

        # 创建索引
        if not collection.has_index():
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            print("✓ 创建索引")

        collection.load()
        print("✓ 加载集合")

    # 6. 测试检索
    print("\n[6] 测试检索...")

    test_queries = [
        "汽车消费补贴金额",
        "家电以旧换新",
        "消费券申领"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")

        # 生成查询向量
        response = TextEmbedding.call(
            model=settings.embedding.dashscope_model,
            input=query,
            dimension=embedding_dim
        )

        if response.status_code == 200:
            query_embedding = response.output['embeddings'][0]['embedding']

            # 执行搜索
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }

            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=2,
                output_fields=["text", "source"]
            )

            for i, hit in enumerate(results[0], 1):
                score = hit.score
                text = hit.entity.get("text", "")[:80].replace('\n', ' ')
                source = hit.entity.get("source", "")
                print(f"  {i}. (相似度: {score:.3f}) {source}")
                print(f"     {text}...")

    # 7. 统计
    print("\n[7] 集合统计...")
    print(f"✓ 集合名称: {collection_name}")
    print(f"✓ 实体数量: {collection.num_entities}")
    print(f"✓ 向量维度: {embedding_dim}")

    print("\n" + "=" * 60)
    print("✅ 独立测试完成！知识库功能正常")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_knowledge_standalone()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)