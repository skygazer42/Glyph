#!/usr/bin/env python3
"""
数据嵌入脚本 - 将 Markdown 文档嵌入到 Milvus（分级索引）

功能：
1. 读取指定目录下的 Markdown 文件
2. 使用分级索引构建器处理文档
3. 存储到 Milvus 向量数据库
4. 验证嵌入结果
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

# 清除代理环境变量，避免在离线环境触发网络请求
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.knowledge.hierarchical_index import HierarchicalIndexBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed markdown documents into hierarchical index.")
    parser.add_argument(
        "--data-dir",
        default=str(PROJECT_ROOT / "resources/data/process"),
        help="Directory containing markdown documents (default: resources/data/process).",
    )
    parser.add_argument(
        "--storage-dir",
        default=str(PROJECT_ROOT / "storage/policy_index"),
        help="Directory to store the hierarchical index (default: storage/policy_index).",
    )
    parser.add_argument(
        "--disable-images",
        action="store_true",
        help="Disable image extraction from markdown documents.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-based summarization when building index.",
    )
    return parser.parse_args()


def find_markdown_files(data_dir: Path) -> List[str]:
    """查找所有 Markdown 文件"""
    md_files: List[str] = []

    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return []

    print(f"[扫描目录] {data_dir}")

    for md_file in data_dir.rglob("*.md"):
        md_files.append(str(md_file))

    print(f"[完成] 找到 {len(md_files)} 个 Markdown 文件\n")

    for i, file in enumerate(md_files[:10], 1):
        print(f"  {i}. {Path(file).name}")
    if len(md_files) > 10:
        print(f"  ... 还有 {len(md_files) - 10} 个文件")

    return md_files


def main(args: argparse.Namespace) -> int:
    """主函数"""
    print("=" * 70)
    print(" 政策文档嵌入系统")
    print("=" * 70)
    print()

    data_dir = Path(args.data_dir).resolve()
    storage_dir = Path(args.storage_dir).resolve()

    print("[配置信息]")
    print(f"  - 数据目录: {data_dir}")
    print(f"  - 存储目录: {storage_dir}")
    print(f"  - LLM 模型: {settings.model.llm_model_name}")
    print(f"  - Embedding: {settings.embedding.backend} - {settings.embedding.dashscope_model}")
    print(f"  - Reranker: {settings.reranker.backend} - {settings.reranker.model_name}")
    print(f"  - Milvus: {settings.database.milvus_host}:{settings.database.milvus_port}")
    print()

    md_files = find_markdown_files(data_dir)
    if not md_files:
        print("❌ 未找到 Markdown 文件")
        return 1

    print("\n" + "=" * 70)
    print(" 开始构建分级索引")
    print("=" * 70)
    print()

    try:
        print("🔧 初始化索引构建器...")
        builder = HierarchicalIndexBuilder(storage_dir=str(storage_dir), embed_model_name=None)
        print("✓ 索引构建器初始化成功\n")

        print("🚀 开始处理文档...")
        stats = builder.build_from_markdown_files(
            md_files,
            use_llm=not args.no_llm,
            enable_images=not args.disable_images,
        )

        print("\n" + "=" * 70)
        print(" 索引构建完成！")
        print("=" * 70)
        print("📊 统计信息:")
        print(f"  - 处理文档数: {stats.get('total_documents', 0)}")
        print(f"  - 总节点数: {stats.get('total_nodes', 0)}")
        print(f"  - 文档节点: {stats.get('doc_nodes', 0)}")
        print(f"  - 章节节点: {stats.get('section_nodes', 0)}")
        print(f"  - Chunk 节点: {stats.get('chunk_nodes', 0)}")
        print(f"  - 图片节点: {stats.get('image_nodes', 0)}")
        print(f"  - 存储位置: {storage_dir}")
        print()

        from app.knowledge.hierarchical_index import HierarchicalRetriever

        print("=" * 70)
        print(" 验证索引")
        print("=" * 70)
        print("🔍 加载检索器...")
        retriever = HierarchicalRetriever(
            storage_dir=str(storage_dir),
            use_rerank="dashscope",
            enable_images=not args.disable_images,
        )
        print("✓ 检索器加载成功\n")

        test_queries = ["家电补贴申请条件", "手机以旧换新政策", "汽车消费券领取方式"]
        print("🧪 测试检索功能:")
        for i, query in enumerate(test_queries, 1):
            print(f"\n  查询 {i}: {query}")
            try:
                results = retriever.retrieve(query=query, top_k=3, use_rerank=True, retrieval_mode="hybrid")
                print(f"  ✓ 找到 {len(results)} 个结果")
                for j, node in enumerate(results[:2], 1):
                    title = node.metadata.get("title", "未知")
                    node_type = node.metadata.get("type", "unknown")
                    preview = node.text[:60] + "..." if len(node.text) > 60 else node.text
                    print(f"    {j}. [{node_type}] {title}")
                    print(f"       {preview}")
            except Exception as exc:
                print(f"  ✗ 检索失败: {exc}")

        print("\n" + "=" * 70)
        print(" 🎉 数据嵌入完成！")
        print("=" * 70)
        print("📝 下一步:")
        print("  1. 访问 Attu 管理界面: http://localhost:8000")
        print("  2. 连接 Milvus: localhost:19530")
        print("  3. 查看集合: policy_documents")
        print("  4. 访问 Neo4j 浏览器（若使用 LightRAG）")
        print()
        return 0

    except Exception as exc:  # pragma: no cover - CLI 直接输出
        import traceback

        print("\n" + "=" * 70)
        print(" ❌ 错误")
        print("=" * 70)
        print(f"\n{type(exc).__name__}: {exc}")
        print("\n详细错误信息:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    cli_args = parse_args()
    sys.exit(main(cli_args))
