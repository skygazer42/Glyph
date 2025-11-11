#!/usr/bin/env python3
"""
直接测试知识库模块
避免导入整个应用
"""

import os
import sys
from pathlib import Path

# 清除代理
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(key, None)

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

def test_direct_import():
    print("=" * 60)
    print("知识库模块直接测试")
    print("=" * 60)

    # 1. 加载配置
    print("\n[1] 加载配置...")
    from dotenv import load_dotenv
    load_dotenv()

    # 2. 直接导入知识库模块（绕过app.__init__）
    print("\n[2] 导入知识库模块...")

    # 直接导入milvus模块
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "milvus_module",
        "/data/temp33/Glyph/app/knowledge/milvus.py"
    )
    milvus_module = importlib.util.module_from_spec(spec)

    # 先导入依赖
    sys.modules['app.config'] = __import__('app.config.app_config', fromlist=['Settings', 'settings'])
    sys.modules['app.knowledge.embeddings'] = __import__('app.knowledge.embeddings', fromlist=['get_embedding_model'])

    spec.loader.exec_module(milvus_module)
    MilvusStore = milvus_module.MilvusStore

    print("✓ MilvusStore类导入成功")

    # 3. 初始化Milvus
    print("\n[3] 初始化MilvusStore...")
    store = MilvusStore()
    print(f"✓ 连接到Milvus")
    print(f"✓ Collection: {store.collection_name}")

    # 4. 测试基本操作
    print("\n[4] 测试基本操作...")

    # 测试文本
    test_texts = [
        "济南市汽车消费补贴政策，补贴金额3000万元",
        "家电以旧换新补贴，最高补贴15%",
        "消费券发放活动，每人最高200元"
    ]

    test_metadata = [
        {"source": "test1.docx", "type": "policy"},
        {"source": "test2.docx", "type": "policy"},
        {"source": "test3.docx", "type": "activity"}
    ]

    # 添加文本
    print("\n添加测试文本...")
    ids = store.add_texts(test_texts, test_metadata)
    print(f"✓ 添加{len(ids)}条记录")
    print(f"  IDs: {ids[:3]}")

    # 5. 测试检索
    print("\n[5] 测试检索...")

    queries = [
        "汽车补贴多少钱",
        "家电以旧换新",
        "消费券怎么领"
    ]

    for query in queries:
        print(f"\n查询: {query}")
        results = store.similarity_search(query, k=2)

        for i, (doc, score) in enumerate(results, 1):
            content = doc.page_content[:50].replace('\n', ' ')
            source = doc.metadata.get('source', 'unknown')
            print(f"  {i}. (相似度: {score:.3f}) {source}")
            print(f"     {content}...")

    # 6. 统计信息
    print("\n[6] 统计信息...")
    stats = store.get_collection_stats()
    print(f"✓ 文档总数: {stats.get('row_count', 0)}")

    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_direct_import()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)