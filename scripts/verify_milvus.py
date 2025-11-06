#!/usr/bin/env python3
"""
验证 Milvus 数据脚本

检查 Milvus 中的数据是否正确嵌入
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection, utility
from config.settings import settings


def check_milvus_connection():
    """检查 Milvus 连接"""
    print("=" * 70)
    print(" 连接 Milvus")
    print("=" * 70)
    print()

    try:
        connections.connect(
            alias="default",
            host=settings.database.milvus_host,
            port=str(settings.database.milvus_port)
        )
        print(f"✓ 连接成功: {settings.database.milvus_host}:{settings.database.milvus_port}")
        return True
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def list_collections():
    """列出所有集合"""
    print("\n" + "=" * 70)
    print(" 集合列表")
    print("=" * 70)
    print()

    try:
        collections = utility.list_collections()
        print(f"找到 {len(collections)} 个集合:\n")

        for i, name in enumerate(collections, 1):
            print(f"  {i}. {name}")

        return collections
    except Exception as e:
        print(f"❌ 获取集合列表失败: {e}")
        return []


def check_collection(collection_name: str):
    """检查集合详情"""
    print("\n" + "=" * 70)
    print(f" 集合详情: {collection_name}")
    print("=" * 70)
    print()

    try:
        if not utility.has_collection(collection_name):
            print(f"❌ 集合不存在: {collection_name}")
            return

        collection = Collection(collection_name)

        # 加载集合
        collection.load()

        # 基本信息
        print("📊 基本信息:")
        print(f"  - 集合名称: {collection.name}")
        print(f"  - 文档数量: {collection.num_entities}")

        # 模式信息
        schema = collection.schema
        print(f"\n📝 模式信息:")
        print(f"  - 描述: {schema.description or '无'}")
        print(f"  - 字段数量: {len(schema.fields)}")

        print(f"\n  字段详情:")
        for field in schema.fields:
            field_info = f"    - {field.name}"
            field_info += f" ({field.dtype.name})"
            if field.is_primary:
                field_info += " [主键]"
            if hasattr(field, 'dim'):
                field_info += f" [维度: {field.dim}]"
            print(field_info)

        # 索引信息
        print(f"\n🔍 索引信息:")
        indexes = collection.indexes
        if indexes:
            for index in indexes:
                print(f"  - 字段: {index.field_name}")
                print(f"    类型: {index.params.get('index_type', 'N/A')}")
                print(f"    度量: {index.params.get('metric_type', 'N/A')}")
        else:
            print("  - 无索引")

        # 查询示例数据
        print(f"\n📄 示例数据 (前 3 条):")
        try:
            results = collection.query(
                expr="",
                output_fields=["*"],
                limit=3
            )

            if results:
                for i, item in enumerate(results, 1):
                    print(f"\n  记录 {i}:")
                    for key, value in item.items():
                        if key == "embedding":
                            print(f"    - {key}: <向量 {len(value)} 维>")
                        elif isinstance(value, str) and len(value) > 100:
                            print(f"    - {key}: {value[:100]}...")
                        else:
                            print(f"    - {key}: {value}")
            else:
                print("  - 无数据")

        except Exception as e:
            print(f"  ✗ 无法查询数据: {e}")

        # 统计信息
        print(f"\n📈 统计信息:")

        # 尝试按类型统计
        try:
            # 统计各类型节点数量
            for node_type in ['document', 'section', 'chunk', 'image']:
                expr = f'type == "{node_type}"'
                try:
                    count = collection.query(
                        expr=expr,
                        output_fields=["id"],
                        limit=1
                    )
                    # 使用 num_entities 作为近似
                    print(f"  - {node_type} 节点: 需要完整扫描统计")
                except:
                    pass

        except Exception as e:
            print(f"  ✗ 统计失败: {e}")

    except Exception as e:
        print(f"❌ 检查集合失败: {e}")
        import traceback
        traceback.print_exc()


def test_search(collection_name: str, query_text: str = "家电补贴"):
    """测试搜索功能"""
    print("\n" + "=" * 70)
    print(f" 测试搜索: {query_text}")
    print("=" * 70)
    print()

    try:
        if not utility.has_collection(collection_name):
            print(f"❌ 集合不存在: {collection_name}")
            return

        # 注意：这里需要实际的 embedding 向量
        # 由于我们没有直接访问 embedding 服务，这里只做连接测试
        print("✓ 集合存在且可访问")
        print("  (完整搜索测试需要在应用代码中进行)")

    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")


def main():
    """主函数"""
    print("=" * 70)
    print(" Milvus 数据验证")
    print("=" * 70)
    print()

    # 1. 检查连接
    if not check_milvus_connection():
        print("\n❌ 无法连接到 Milvus，请确保服务已启动")
        print("   启动命令: docker-compose up -d")
        return 1

    # 2. 列出集合
    collections = list_collections()

    if not collections:
        print("\n⚠️  Milvus 中没有集合")
        print("   请先运行嵌入脚本: python scripts/embed_documents.py")
        return 0

    # 3. 检查每个集合
    for collection_name in collections:
        check_collection(collection_name)

    # 4. 测试搜索
    if collections:
        test_search(collections[0])

    print("\n" + "=" * 70)
    print(" ✓ 验证完成")
    print("=" * 70)
    print()
    print("🌐 访问管理界面:")
    print(f"  - Attu (Milvus): http://localhost:8000")
    print(f"  - Neo4j: http://localhost:7474 (neo4j/password123)")
    print()

    # 清理连接
    connections.disconnect("default")

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
