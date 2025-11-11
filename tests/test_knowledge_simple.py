#!/usr/bin/env python3
"""
知识库功能测试脚本（简化版）
测试流程：切块 -> 嵌入 -> 存储 -> 检索
"""

import os
import sys
from pathlib import Path

# 清除代理设置
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

sys.path.insert(0, str(Path(__file__).parent))

def test_knowledge_simple():
    print("=" * 60)
    print("知识库功能测试（简化版）")
    print("=" * 60)

    # 1. 直接加载环境变量
    print("\n[1] 加载环境配置...")
    from dotenv import load_dotenv
    load_dotenv()

    embedding_backend = os.getenv('EMBEDDING_BACKEND', 'dashscope')
    embedding_model = os.getenv('EMBEDDING_DASHSCOPE_MODEL', 'text-embedding-v3')
    api_key = os.getenv('EMBEDDING_DASHSCOPE_API_KEY', '')

    print(f"✓ Embedding后端: {embedding_backend}")
    print(f"✓ Embedding模型: {embedding_model}")
    print(f"✓ API Key配置: {'已设置' if api_key else '未设置'}")

    # 2. 测试DashScope连接
    print("\n[2] 测试DashScope嵌入服务...")

    import dashscope
    dashscope.api_key = api_key

    from dashscope import TextEmbedding

    # 测试生成嵌入
    test_text = "济南市汽车消费补贴政策"

    try:
        response = TextEmbedding.call(
            model=embedding_model,
            input=test_text,
            dimension=1024  # 指定维度
        )

        if response.status_code == 200:
            embedding = response.output['embeddings'][0]['embedding']
            print(f"✓ 嵌入生成成功")
            print(f"✓ 向量维度: {len(embedding)}")
            print(f"✓ 向量示例: [{embedding[0]:.4f}, {embedding[1]:.4f}, ..., {embedding[-1]:.4f}]")
        else:
            print(f"✗ 嵌入失败: {response}")
            return
    except Exception as e:
        print(f"✗ DashScope调用失败: {e}")
        return

    # 3. 测试Milvus连接
    print("\n[3] 测试Milvus连接...")
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

    try:
        # 连接Milvus
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )
        print("✓ Milvus连接成功")

        # 检查集合
        collection_name = "test_knowledge"

        # 如果集合存在则删除
        if utility.has_collection(collection_name):
            Collection(collection_name).drop()
            print(f"✓ 删除旧集合: {collection_name}")

        # 创建新集合
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024)
        ]
        schema = CollectionSchema(fields, description="Test knowledge base")
        collection = Collection(name=collection_name, schema=schema)
        print(f"✓ 创建新集合: {collection_name}")

    except Exception as e:
        print(f"✗ Milvus连接失败: {e}")
        return

    # 4. 测试文档切块
    print("\n[4] 测试文档切块...")

    # 读取测试文档
    test_file = Path("/data/temp33/Glyph/resources/data/raw/关于追加2025年政府汽车消费补贴资金额度的公告.docx")

    try:
        from docx import Document
        doc = Document(str(test_file))

        # 提取所有段落文本
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        print(f"✓ 读取文档: {test_file.name}")
        print(f"✓ 文档长度: {len(full_text)} 字符")

        # 简单切块（每500字符）
        chunk_size = 500
        chunks = []
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i+chunk_size]
            if chunk.strip():
                chunks.append(chunk)

        print(f"✓ 切块数量: {len(chunks)}")
        print(f"\n前2个切块预览:")
        for i, chunk in enumerate(chunks[:2], 1):
            preview = chunk[:100].replace('\n', ' ')
            print(f"  切块{i}: {preview}...")

    except Exception as e:
        print(f"✗ 文档处理失败: {e}")
        return

    # 5. 生成嵌入并存储
    print("\n[5] 生成嵌入并存储到Milvus...")

    embeddings = []
    texts = chunks[:5]  # 只处理前5个切块用于测试

    for i, text in enumerate(texts):
        try:
            response = TextEmbedding.call(
                model=embedding_model,
                input=text,
                dimension=1024
            )
            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                embeddings.append(embedding)
                print(f"  ✓ 切块{i+1}嵌入生成成功")
        except Exception as e:
            print(f"  ✗ 切块{i+1}嵌入失败: {e}")
            return

    # 插入到Milvus
    try:
        data = [
            texts,  # text字段
            embeddings  # embedding字段
        ]

        collection.insert(data)
        collection.flush()
        print(f"✓ 插入{len(texts)}条数据到Milvus")

        # 创建索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        print("✓ 创建索引并加载集合")

    except Exception as e:
        print(f"✗ 存储失败: {e}")
        return

    # 6. 测试检索
    print("\n[6] 测试向量检索...")

    query_text = "汽车消费补贴金额"
    print(f"查询: {query_text}")

    try:
        # 生成查询向量
        response = TextEmbedding.call(
            model=embedding_model,
            input=query_text,
            dimension=1024
        )

        if response.status_code == 200:
            query_embedding = response.output['embeddings'][0]['embedding']
            print("✓ 查询向量生成成功")

            # 执行搜索
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }

            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=3,
                output_fields=["text"]
            )

            print(f"\n检索结果 (Top 3):")
            for i, hit in enumerate(results[0], 1):
                score = hit.score
                text = hit.entity.get("text", "")
                preview = text[:100].replace('\n', ' ')
                print(f"\n  结果{i} (相似度: {score:.4f}):")
                print(f"    {preview}...")

    except Exception as e:
        print(f"✗ 检索失败: {e}")
        return

    # 7. 清理
    print("\n[7] 清理测试数据...")
    try:
        collection.drop()
        print(f"✓ 删除测试集合: {collection_name}")
    except:
        pass

    print("\n" + "=" * 60)
    print("✅ 知识库功能测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_knowledge_simple()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)