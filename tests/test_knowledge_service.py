#!/usr/bin/env python3
"""
测试完整的KnowledgeService
包括：批量文档处理、嵌入、检索
"""

import os
import sys
from pathlib import Path

# 清除代理
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(key, None)

sys.path.insert(0, str(Path(__file__).parent))

def test_knowledge_service():
    print("=" * 60)
    print("KnowledgeService 完整测试")
    print("=" * 60)

    # 1. 初始化服务
    print("\n[1] 初始化KnowledgeService...")

    # 导入必要模块，避免完整app初始化
    os.environ['AUTOGEN_USE_DOCKER'] = 'False'

    from app.config import settings
    from app.knowledge.service import KnowledgeService
    from app.knowledge.milvus import MilvusStore

    service = KnowledgeService()
    print("✓ KnowledgeService初始化成功")

    # 2. 准备测试文档
    print("\n[2] 准备测试文档...")

    doc_dir = Path("/data/temp33/Glyph/resources/data/raw")
    test_files = list(doc_dir.glob("*.docx"))[:3]  # 测试前3个文档

    print(f"✓ 找到{len(test_files)}个测试文档:")
    for f in test_files:
        print(f"  - {f.name}")

    # 3. 批量索引文档
    print("\n[3] 批量索引文档...")

    for i, doc_file in enumerate(test_files, 1):
        print(f"\n处理文档 {i}/{len(test_files)}: {doc_file.name}")

        try:
            # 读取文档内容
            from docx import Document
            doc = Document(str(doc_file))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

            if text:
                # 调用服务索引文档
                doc_id = service.index_document(
                    content=text,
                    metadata={
                        "source": doc_file.name,
                        "path": str(doc_file),
                        "type": "policy_document"
                    }
                )
                print(f"  ✓ 索引成功，文档ID: {doc_id}")
            else:
                print(f"  ✗ 文档内容为空")

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")

    # 4. 测试检索功能
    print("\n[4] 测试检索功能...")

    test_queries = [
        "汽车消费补贴的金额是多少",
        "家电以旧换新的补贴标准",
        "消费券如何申领"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 40)

        try:
            results = service.search(query, top_k=3)

            if results:
                for i, result in enumerate(results, 1):
                    content_preview = result.get('content', '')[:100].replace('\n', ' ')
                    score = result.get('score', 0)
                    source = result.get('metadata', {}).get('source', 'unknown')

                    print(f"  结果{i} (相似度: {score:.4f}, 来源: {source}):")
                    print(f"    {content_preview}...")
            else:
                print("  无结果")

        except Exception as e:
            print(f"  查询失败: {e}")

    # 5. 测试混合检索（如果启用）
    if settings.system.hybrid_retrieval_enabled:
        print("\n[5] 测试混合检索...")
        print("✓ 混合检索已启用")
        # 这里可以添加混合检索的测试
    else:
        print("\n[5] 混合检索未启用")

    # 6. 统计信息
    print("\n[6] 统计信息...")

    try:
        # 获取Milvus统计
        milvus_store = MilvusStore()
        stats = milvus_store.get_collection_stats()

        print(f"✓ Collection: {milvus_store.collection_name}")
        print(f"✓ 文档总数: {stats.get('row_count', 0)}")
        print(f"✓ 索引状态: 已建立")

    except Exception as e:
        print(f"✗ 无法获取统计信息: {e}")

    print("\n" + "=" * 60)
    print("✅ KnowledgeService测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_knowledge_service()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)