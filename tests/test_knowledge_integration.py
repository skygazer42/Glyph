#!/usr/bin/env python3
"""
知识库集成测试
完全独立运行，不依赖主应用初始化
"""

import os
import sys
from pathlib import Path

# 清除代理设置
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(key, None)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_knowledge_integration():
    """测试知识库完整功能"""
    print("=" * 60)
    print("知识库集成测试")
    print("=" * 60)

    # 1. 初始化配置（不通过app导入）
    print("\n[1] 初始化配置...")
    from app.config.app_config import settings

    print(f"✓ Embedding后端: {settings.embedding.backend}")
    print(f"✓ Embedding模型: {settings.embedding.dashscope_model}")
    print(f"✓ Milvus配置: {settings.database.milvus_host}:{settings.database.milvus_port}")
    print(f"✓ Collection名称: {settings.database.milvus_collection_name}")

    # 2. 初始化知识库组件
    print("\n[2] 初始化知识库组件...")

    # 直接导入知识库模块
    from app.knowledge.milvus import MilvusStore
    from app.knowledge.embeddings import get_embedding_model
    from app.knowledge.service import KnowledgeService

    # 初始化存储
    milvus_store = MilvusStore()
    print(f"✓ MilvusStore初始化成功")

    # 初始化嵌入模型
    embed_model = get_embedding_model()
    print(f"✓ 嵌入模型初始化: {embed_model.__class__.__name__}")

    # 初始化服务
    knowledge_service = KnowledgeService()
    print(f"✓ KnowledgeService初始化成功")

    # 3. 处理测试文档
    print("\n[3] 处理测试文档...")

    doc_dir = Path(project_root) / "resources" / "data" / "raw"
    test_files = list(doc_dir.glob("*.docx"))[:3]

    if not test_files:
        print("✗ 未找到测试文档")
        return

    print(f"✓ 找到 {len(test_files)} 个测试文档")

    for i, doc_file in enumerate(test_files, 1):
        print(f"\n处理文档 {i}: {doc_file.name}")

        try:
            # 读取文档
            from docx import Document
            doc = Document(str(doc_file))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

            if not text:
                print("  ✗ 文档内容为空")
                continue

            print(f"  文档长度: {len(text)} 字符")

            # 索引文档
            doc_id = knowledge_service.index_document(
                content=text,
                metadata={
                    "source": doc_file.name,
                    "path": str(doc_file),
                    "type": "policy"
                }
            )
            print(f"  ✓ 索引成功: {doc_id}")

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")

    # 4. 测试检索
    print("\n[4] 测试检索功能...")

    test_queries = [
        "汽车消费补贴金额",
        "家电以旧换新政策",
        "消费券使用方法"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 40)

        try:
            # 使用知识库服务搜索
            results = knowledge_service.search(query, top_k=3)

            if results:
                for i, result in enumerate(results, 1):
                    content = result.get('content', '')[:100].replace('\n', ' ')
                    score = result.get('score', 0)
                    source = result.get('metadata', {}).get('source', 'unknown')

                    print(f"  结果{i} (相似度: {score:.3f}):")
                    print(f"    来源: {source}")
                    print(f"    内容: {content}...")
            else:
                print("  无结果")

        except Exception as e:
            print(f"  查询失败: {e}")

    # 5. 测试重排序
    print("\n[5] 测试重排序功能...")

    if settings.reranker.backend:
        try:
            from app.knowledge.reranker import get_reranker
            reranker = get_reranker()

            if reranker:
                print(f"✓ Reranker已配置: {settings.reranker.backend}")

                # 测试重排
                query = "汽车补贴"
                results = milvus_store.similarity_search(query, k=5)

                if results:
                    docs = [r[0] for r in results]
                    reranked = reranker.rerank(query, docs, top_k=3)
                    print(f"✓ 重排序完成: {len(reranked)} 个结果")
            else:
                print("✗ Reranker未初始化")

        except Exception as e:
            print(f"✗ Reranker测试失败: {e}")
    else:
        print("✗ Reranker未配置")

    # 6. 统计信息
    print("\n[6] 知识库统计...")

    try:
        stats = milvus_store.get_collection_stats()
        print(f"✓ Collection: {milvus_store.collection_name}")
        print(f"✓ 文档总数: {stats.get('row_count', 0)}")
        print(f"✓ 向量维度: {settings.embedding.dimension}")
        print(f"✓ 索引类型: IVF_FLAT")

    except Exception as e:
        print(f"✗ 获取统计失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 知识库集成测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_knowledge_integration()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)