#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 LlamaIndex 混合检索 (BM25 + Vector)
对比不同 alpha 值的检索效果
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from knowledge_base.llamaindex_hybrid_retrieval import (
    LlamaIndexHybridRetriever,
    load_documents_from_dir
)


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_hybrid_retrieval_with_different_alphas():
    """测试不同 alpha 值的混合检索效果"""

    print_section("LlamaIndex 混合检索测试")

    data_dir = Path("/data/temp33/gov/data/process")

    if not data_dir.exists():
        print(f"✗ 数据目录不存在: {data_dir}")
        return 1

    # 1. 加载文档
    print_section("1. 加载文档")
    documents = load_documents_from_dir(data_dir)

    if not documents:
        print("✗ 没有找到任何文档")
        return 1

    # 2. 创建混合检索器
    print_section("2. 创建混合检索器")

    retriever = LlamaIndexHybridRetriever(
        collection_name="policy_hybrid_search_test",
        alpha=0.5,  # 初始值：均衡混合
        similarity_top_k=5,
        overwrite=True
    )

    # 3. 构建索引
    print_section("3. 构建索引")
    retriever.build_index(documents)

    # 4. 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
        "济南市2025年有哪些消费活动？",
        "智能手表购新补贴的条件是什么？"
    ]

    # 测试不同的 alpha 值
    alphas_to_test = [
        (0.0, "纯关键词检索 (BM25)"),
        (0.3, "偏关键词混合"),
        (0.5, "均衡混合"),
        (0.7, "偏语义混合"),
        (1.0, "纯语义检索 (向量)")
    ]

    print_section("4. 测试不同 Alpha 值的检索效果")

    results_summary = {}

    for alpha, alpha_desc in alphas_to_test:
        print(f"\n{'=' * 80}")
        print(f"  Alpha = {alpha:.1f} - {alpha_desc}")
        print('=' * 80)

        retriever.update_alpha(alpha)

        query_results = []

        for i, query in enumerate(test_queries, 1):
            print(f"\n查询 {i}: {query}")
            print("-" * 60)

            try:
                # 执行检索
                nodes = retriever.retrieve(query)

                print(f"✓ 检索到 {len(nodes)} 个结果")

                # 显示 Top 3 结果
                print(f"\nTop 3 结果:")
                for j, node in enumerate(nodes[:3], 1):
                    # 提取文档标题（如果有）
                    metadata = node.node.metadata
                    file_name = metadata.get('file_name', 'Unknown')

                    print(f"\n  结果 {j}:")
                    print(f"    Score: {node.score:.4f}")
                    print(f"    Source: {file_name}")
                    print(f"    Text: {node.node.text[:100].replace(chr(10), ' ')}...")

                query_results.append({
                    'query': query,
                    'nodes': nodes,
                    'top_score': nodes[0].score if nodes else 0
                })

            except Exception as e:
                print(f"  ✗ 查询失败: {e}")
                import traceback
                traceback.print_exc()

        results_summary[alpha] = query_results

    # 5. 对比总结
    print_section("5. Alpha 对比总结")

    print(f"{'Alpha':<10} | {'描述':<20} | {'平均Top1分数':<15}")
    print("-" * 60)

    for alpha, alpha_desc in alphas_to_test:
        query_results = results_summary.get(alpha, [])
        avg_top_score = sum(r['top_score'] for r in query_results) / len(query_results) if query_results else 0

        print(f"{alpha:<10.1f} | {alpha_desc:<20} | {avg_top_score:<15.4f}")

    # 6. 详细对比某个查询
    print_section("6. 单查询详细对比")

    test_query = "家电以旧换新补贴"
    print(f"查询: {test_query}\n")

    print(f"{'Alpha':<10} | {'Top1 Score':<12} | {'Top1 内容预览':<50}")
    print("-" * 80)

    for alpha, alpha_desc in alphas_to_test:
        retriever.update_alpha(alpha)
        nodes = retriever.retrieve(test_query)

        if nodes:
            top_node = nodes[0]
            preview = top_node.node.text[:50].replace('\n', ' ')
            print(f"{alpha:<10.1f} | {top_node.score:<12.4f} | {preview}...")

    # 7. 清理
    print_section("7. 清理测试环境")

    try:
        from pymilvus import utility, connections

        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
                port=os.getenv("DATABASE__MILVUS_PORT", "19530")
            )

        if utility.has_collection("policy_hybrid_search_test"):
            utility.drop_collection("policy_hybrid_search_test")
            print("✓ 已删除测试集合")

    except Exception as e:
        print(f"⚠ 清理警告: {e}")

    print_section("测试完成")

    return 0


def test_hybrid_vs_pure_vector():
    """对比混合检索和纯向量检索的效果"""

    print_section("混合检索 vs 纯向量检索对比")

    data_dir = Path("/data/temp33/gov/data/process")

    # 1. 加载文档
    print("加载文档...")
    documents = load_documents_from_dir(data_dir)

    # 2. 创建检索器
    print("\n创建检索器...")

    # 混合检索 (alpha=0.5)
    hybrid_retriever = LlamaIndexHybridRetriever(
        collection_name="hybrid_comparison_test",
        alpha=0.5,
        similarity_top_k=5,
        overwrite=True
    )
    hybrid_retriever.build_index(documents)

    # 纯向量检索 (alpha=1.0)
    vector_retriever = LlamaIndexHybridRetriever(
        collection_name="vector_comparison_test",
        alpha=1.0,
        similarity_top_k=5,
        overwrite=True
    )
    vector_retriever.build_index(documents)

    # 3. 测试查询
    test_queries = [
        "家电以旧换新",
        "手机补贴",
        "汽车消费券"
    ]

    print("\n" + "=" * 80)
    print("  对比测试")
    print("=" * 80)

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 60)

        # 混合检索
        print("\n[混合检索 Alpha=0.5]")
        hybrid_nodes = hybrid_retriever.retrieve(query)
        for j, node in enumerate(hybrid_nodes[:3], 1):
            print(f"  {j}. [{node.score:.4f}] {node.node.text[:60]}...")

        # 纯向量检索
        print("\n[纯向量检索 Alpha=1.0]")
        vector_nodes = vector_retriever.retrieve(query)
        for j, node in enumerate(vector_nodes[:3], 1):
            print(f"  {j}. [{node.score:.4f}] {node.node.text[:60]}...")

    # 清理
    from pymilvus import utility, connections

    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
            port=os.getenv("DATABASE__MILVUS_PORT", "19530")
        )

    for coll in ["hybrid_comparison_test", "vector_comparison_test"]:
        if utility.has_collection(coll):
            utility.drop_collection(coll)

    print("\n✓ 对比测试完成")


def main():
    """主流程"""

    print("\n" + "=" * 80)
    print("  LlamaIndex 混合检索测试")
    print("=" * 80)

    # 测试1: 不同 alpha 值
    result1 = test_hybrid_retrieval_with_different_alphas()

    # 测试2: 混合 vs 纯向量
    # test_hybrid_vs_pure_vector()

    return result1


if __name__ == "__main__":
    sys.exit(main())
