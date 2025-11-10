#!/usr/bin/env python3
"""
批量处理脚本 - 构建和测试分级索引
"""

import argparse
import sys
import os
from pathlib import Path
import json
from typing import List, Optional

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.knowledge.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)


def build_index(data_dir: str,
                storage_dir: str,
                chunk_size: int = 800,
                chunk_overlap: int = 100,
                embed_model: Optional[str] = None,
                use_llm: bool = False,
                enable_images: bool = True):
    """构建分级索引"""

    print(f"="*60)
    print("构建分级索引")
    print(f"="*60)
    print(f"数据目录: {data_dir}")
    print(f"存储目录: {storage_dir}")
    print(f"切块大小: {chunk_size} 字符")
    print(f"重叠大小: {chunk_overlap} 字符")
    print(f"嵌入模型: {embed_model or '默认'}")
    print(f"LLM 摘要: {'是' if use_llm else '否'}")
    print(f"图片索引: {'是' if enable_images else '否'}")
    print(f"-"*60)

    # 查找所有 Markdown 文件
    md_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))

    if not md_files:
        print(f"错误: 在 {data_dir} 中未找到 Markdown 文件")
        return False

    print(f"找到 {len(md_files)} 个 Markdown 文件:")
    for i, f in enumerate(md_files[:5], 1):
        print(f"  {i}. {Path(f).name}")
    if len(md_files) > 5:
        print(f"  ... 还有 {len(md_files) - 5} 个文件")

    # 配置切块参数
    config = ChunkConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        section_summary_size=250,
        include_tables=True,
        include_code_blocks=True
    )

    # 构建索引
    builder = HierarchicalIndexBuilder(
        storage_dir=storage_dir,
        embed_model_name=embed_model
    )
    builder.processor.config = config

    try:
        stats = builder.build_from_markdown_files(md_files, use_llm=use_llm, enable_images=enable_images)
        print(f"\n✅ 索引构建成功!")
        print(f"  - 文档数: {stats['total_docs']}")
        print(f"  - 章节数: {stats['total_sections']}")
        print(f"  - 块数: {stats['total_chunks']}")
        if 'total_images' in stats:
            print(f"  - 图片数: {stats['total_images']}")
        print(f"  - 存储位置: {stats['storage_dir']}")
        return True
    except Exception as e:
        print(f"\n❌ 索引构建失败: {e}")
        return False


def test_retrieval(storage_dir: str,
                  queries: Optional[List[str]] = None,
                  top_k: int = 5,
                  retrieval_mode: str = "hybrid"):
    """测试检索功能"""

    print(f"="*60)
    print("测试检索功能")
    print(f"="*60)
    print(f"存储目录: {storage_dir}")
    print(f"检索模式: {retrieval_mode}")
    print(f"返回数量: {top_k}")
    print(f"-"*60)

    # 默认测试查询
    if not queries:
        queries = [
            "家电以旧换新补贴标准是什么？",
            "手机购新补贴的申请条件有哪些？",
            "补贴金额如何计算？",
            "济南市消费券如何领取？",
            "哪些产品可以享受补贴？"
        ]

    try:
        # 初始化检索器
        retriever = HierarchicalRetriever(storage_dir=storage_dir)

        for query_idx, query in enumerate(queries, 1):
            print(f"\n[查询 {query_idx}] {query}")
            print("-" * 50)

            # 执行检索
            nodes = retriever.retrieve(
                query,
                top_k=top_k,
                use_rerank=True,
                retrieval_mode=retrieval_mode
            )

            if not nodes:
                print("  未找到相关结果")
                continue

            for i, node in enumerate(nodes, 1):
                print(f"\n  结果 {i}:")
                print(f"    类型: {node.metadata.get('type', 'unknown')}")
                print(f"    文档: {node.metadata.get('title', 'N/A')}")
                print(f"    路径: {node.metadata.get('path', 'N/A')}")
                print(f"    内容摘要: {node.text[:150]}...")
                if node.metadata.get('type') == 'chunk':
                    print(f"    块索引: {node.metadata.get('chunk_idx', 'N/A')}")

        return True
    except Exception as e:
        print(f"\n❌ 检索测试失败: {e}")
        return False


def query_interactive(storage_dir: str,
                     retrieval_mode: str = "hybrid",
                     top_k: int = 5):
    """交互式查询"""

    print(f"="*60)
    print("交互式查询模式")
    print(f"="*60)
    print(f"存储目录: {storage_dir}")
    print(f"检索模式: {retrieval_mode}")
    print(f"返回数量: {top_k}")
    print("输入 'quit' 或 'exit' 退出")
    print(f"-"*60)

    try:
        # 初始化检索器
        retriever = HierarchicalRetriever(storage_dir=storage_dir)
        print("✅ 检索器初始化成功")

        # 获取查询引擎
        engine = retriever.get_query_engine(
            retrieval_mode=retrieval_mode,
            response_mode="compact"
        )

        while True:
            query = input("\n请输入查询 > ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("退出交互式查询")
                break

            if not query:
                continue

            try:
                # 使用查询引擎
                print("\n正在检索...")
                response = engine.query(query)
                print("\n回答:")
                print("-" * 50)
                print(response)

                # 显示源文档
                if hasattr(response, 'source_nodes') and response.source_nodes:
                    print("\n参考文档:")
                    for i, source in enumerate(response.source_nodes[:3], 1):
                        node = source.node
                        print(f"  [{i}] {node.metadata.get('path', 'N/A')}")

            except Exception as e:
                print(f"查询出错: {e}")

        return True
    except Exception as e:
        print(f"\n❌ 交互式查询失败: {e}")
        return False


def show_stats(storage_dir: str):
    """显示索引统计信息"""

    print(f"="*60)
    print("索引统计信息")
    print(f"="*60)
    print(f"存储目录: {storage_dir}")
    print(f"-"*60)

    storage_path = Path(storage_dir)
    if not storage_path.exists():
        print(f"错误: 存储目录 {storage_dir} 不存在")
        return False

    # 检查各个索引目录
    indices = ['doc_index', 'section_index', 'chunk_index', 'summary_index']
    for index_name in indices:
        index_path = storage_path / index_name
        if index_path.exists():
            # 计算目录大小
            size = sum(f.stat().st_size for f in index_path.rglob('*') if f.is_file())
            size_mb = size / (1024 * 1024)
            print(f"  ✓ {index_name}: {size_mb:.2f} MB")
        else:
            print(f"  ✗ {index_name}: 不存在")

    # 检查文档存储
    docstore_path = storage_path / 'docstore.json'
    if docstore_path.exists():
        size_mb = docstore_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ docstore: {size_mb:.2f} MB")

        # 尝试读取文档数量
        try:
            with open(docstore_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'docs' in data:
                    print(f"    文档数量: {len(data['docs'])}")
        except:
            pass

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="LlamaIndex 分级索引批处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 构建索引
  python batch_process.py build --data-dir /data/process --storage-dir ./storage

  # 测试检索
  python batch_process.py test --storage-dir ./storage

  # 交互式查询
  python batch_process.py query --storage-dir ./storage

  # 显示统计信息
  python batch_process.py stats --storage-dir ./storage
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # build 命令
    build_parser = subparsers.add_parser('build', help='构建分级索引')
    build_parser.add_argument('--data-dir', type=str, required=True,
                            help='Markdown 文档目录')
    build_parser.add_argument('--storage-dir', type=str,
                            default='/data/temp33/gov/storage/hierarchical',
                            help='索引存储目录')
    build_parser.add_argument('--chunk-size', type=int, default=800,
                            help='切块大小（字符数）')
    build_parser.add_argument('--chunk-overlap', type=int, default=100,
                            help='切块重叠大小（字符数）')
    build_parser.add_argument('--embed-model', type=str,
                            help='嵌入模型名称')
    build_parser.add_argument('--use-llm', action='store_true',
                            help='使用 LLM 生成章节摘要（更准确但更慢）')
    build_parser.add_argument('--enable-images', action='store_true', default=True,
                            help='提取和索引图片（默认启用）')
    build_parser.add_argument('--no-images', dest='enable_images', action='store_false',
                            help='禁用图片提取')

    # test 命令
    test_parser = subparsers.add_parser('test', help='测试检索功能')
    test_parser.add_argument('--storage-dir', type=str,
                           default='/data/temp33/gov/storage/hierarchical',
                           help='索引存储目录')
    test_parser.add_argument('--queries', type=str, nargs='+',
                           help='测试查询列表')
    test_parser.add_argument('--top-k', type=int, default=5,
                           help='返回结果数量')
    test_parser.add_argument('--mode', type=str,
                           choices=['hybrid', 'hierarchical', 'direct'],
                           default='hybrid',
                           help='检索模式')

    # query 命令
    query_parser = subparsers.add_parser('query', help='交互式查询')
    query_parser.add_argument('--storage-dir', type=str,
                            default='/data/temp33/gov/storage/hierarchical',
                            help='索引存储目录')
    query_parser.add_argument('--mode', type=str,
                            choices=['hybrid', 'hierarchical', 'direct'],
                            default='hybrid',
                            help='检索模式')
    query_parser.add_argument('--top-k', type=int, default=5,
                            help='返回结果数量')

    # stats 命令
    stats_parser = subparsers.add_parser('stats', help='显示索引统计信息')
    stats_parser.add_argument('--storage-dir', type=str,
                            default='/data/temp33/gov/storage/hierarchical',
                            help='索引存储目录')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    if args.command == 'build':
        success = build_index(
            args.data_dir,
            args.storage_dir,
            args.chunk_size,
            args.chunk_overlap,
            args.embed_model,
            args.use_llm,  # 添加 use_llm 参数
            args.enable_images  # 添加 enable_images 参数
        )
    elif args.command == 'test':
        success = test_retrieval(
            args.storage_dir,
            args.queries,
            args.top_k,
            args.mode
        )
    elif args.command == 'query':
        success = query_interactive(
            args.storage_dir,
            args.mode,
            args.top_k
        )
    elif args.command == 'stats':
        success = show_stats(args.storage_dir)
    else:
        print(f"未知命令: {args.command}")
        success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())