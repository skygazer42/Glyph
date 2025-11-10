#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用真实政策数据测试 Milvus 嵌入和检索功能
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.knowledge.milvus import MilvusStore

@dataclass
class SimpleDocument:
    """简化的文档类型"""
    id: str
    title: str
    content: str
    source: str = ""
    doc_type: str = ""

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def load_policy_documents(data_dir):
    """从 markdown 文件加载政策文档"""
    print_section("1. 加载政策文档")

    documents = []
    md_files = list(Path(data_dir).rglob("*.md"))

    print(f"找到 {len(md_files)} 个 markdown 文件")

    for idx, md_file in enumerate(md_files, 1):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取标题（第一行或文件名）
            lines = content.split('\n')
            title = None
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break

            if not title:
                title = md_file.stem

            # 确定文档类型
            if "家电" in str(md_file) or "数码" in str(md_file):
                doc_type = "家电数码政策"
            elif "汽车" in str(md_file) or "新车" in str(md_file):
                doc_type = "汽车消费政策"
            else:
                doc_type = "消费活动政策"

            doc = SimpleDocument(
                id=f"policy_{idx}",
                title=title,
                content=content[:5000],  # 限制长度避免太长
                source=str(md_file.relative_to(data_dir)),
                doc_type=doc_type
            )

            documents.append(doc)
            print(f"  {idx}. {title[:60]}... ({doc_type})")

        except Exception as e:
            print(f"  ✗ 读取失败: {md_file.name} - {e}")

    print(f"\n✓ 成功加载 {len(documents)} 个文档")
    return documents

def test_embedding(store, documents):
    """测试文档嵌入"""
    print_section("2. 文档嵌入到 Milvus")

    try:
        print(f"准备插入 {len(documents)} 条政策文档...")
        print(f"  - Backend: {store.backend}")
        print(f"  - Model: {store.model_name}")
        print(f"  - Dimension: {store.embedding_dim}")

        # 插入文档
        store.add_documents(documents)

        print(f"\n✓ 成功插入 {len(documents)} 条文档")

        # 验证
        stats = store.collection.num_entities
        print(f"  - 集合中总文档数: {stats}")

        return True

    except Exception as e:
        print(f"✗ 嵌入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_policy_queries(store):
    """测试政策查询"""
    print_section("3. 测试政策问答召回")

    # 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
        "济南市2025年有哪些消费活动？",
        "智能手表购新补贴的条件是什么？"
    ]

    results_summary = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 60)

        try:
            documents, scores = store.search(query, top_k=3, threshold=0.0)

            if documents:
                print(f"✓ 检索到 {len(documents)} 条结果:")
                for j, (doc, score) in enumerate(zip(documents, scores), 1):
                    print(f"\n  结果 {j}:")
                    print(f"    相似度: {score:.4f}")
                    print(f"    标题: {doc.title[:80]}")
                    print(f"    类型: {doc.doc_type}")
                    print(f"    来源: {doc.source[:60]}")

                results_summary.append({
                    'query': query,
                    'count': len(documents),
                    'top_score': scores[0] if scores else 0
                })
            else:
                print("  ✗ 未检索到结果")
                results_summary.append({
                    'query': query,
                    'count': 0,
                    'top_score': 0
                })

        except Exception as e:
            print(f"  ✗ 查询失败: {e}")
            results_summary.append({
                'query': query,
                'count': 0,
                'top_score': 0
            })

    return results_summary

def test_filtered_search(store):
    """测试带过滤的搜索"""
    print_section("4. 测试分类过滤搜索")

    filters_tests = [
        ("家电数码相关政策", {"doc_type": "家电数码政策"}),
        ("汽车消费相关政策", {"doc_type": "汽车消费政策"}),
    ]

    for query, filters in filters_tests:
        print(f"\n查询: {query}")
        print(f"过滤: {filters}")
        print("-" * 60)

        try:
            documents, scores = store.search(query, top_k=5, threshold=0.0, filters=filters)

            if documents:
                print(f"✓ 检索到 {len(documents)} 条符合条件的结果:")
                for i, (doc, score) in enumerate(zip(documents, scores), 1):
                    print(f"  {i}. [{score:.4f}] {doc.title[:60]}... ({doc.doc_type})")
            else:
                print("  ✗ 未检索到结果")

        except Exception as e:
            print(f"  ✗ 搜索失败: {e}")

def print_summary(results_summary, total_docs):
    """打印测试总结"""
    print_section("测试总结")

    print(f"文档统计:")
    print(f"  - 总文档数: {total_docs}")

    print(f"\n查询统计:")
    total_queries = len(results_summary)
    successful_queries = sum(1 for r in results_summary if r['count'] > 0)
    avg_score = sum(r['top_score'] for r in results_summary) / total_queries if total_queries > 0 else 0

    print(f"  - 总查询数: {total_queries}")
    print(f"  - 成功查询: {successful_queries}")
    print(f"  - 成功率: {successful_queries/total_queries*100:.1f}%")
    print(f"  - 平均最高分: {avg_score:.4f}")

    print(f"\n查询结果详情:")
    for r in results_summary:
        status = "✓" if r['count'] > 0 else "✗"
        print(f"  {status} {r['query'][:50]:50s} - {r['count']}条结果 (最高分:{r['top_score']:.4f})")

    if successful_queries == total_queries:
        print("\n✓ 所有查询都成功返回结果！")
    else:
        print(f"\n⚠ {total_queries - successful_queries} 个查询未返回结果")

def cleanup(store):
    """清理测试数据"""
    print_section("5. 清理测试环境")

    try:
        from pymilvus import utility, connections

        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
                port=os.getenv("DATABASE__MILVUS_PORT", "19530")
            )

        collection_name = "policy_documents_test"
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            print(f"✓ 已删除测试集合: {collection_name}")

    except Exception as e:
        print(f"⚠ 清理警告: {e}")

def main():
    """主测试流程"""
    print("\n" + "=" * 80)
    print("  真实政策数据测试")
    print("  数据目录: /data/temp33/gov/data/process")
    print("=" * 80)

    data_dir = Path("/data/temp33/gov/data/process")

    if not data_dir.exists():
        print(f"✗ 数据目录不存在: {data_dir}")
        return 1

    try:
        # 1. 加载文档
        documents = load_policy_documents(data_dir)

        if not documents:
            print("✗ 没有找到任何文档")
            return 1

        # 2. 创建 Milvus store
        print_section("连接 Milvus")
        store = MilvusStore(
            collection_name="policy_documents_test",
            host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
            port=int(os.getenv("DATABASE__MILVUS_PORT", "19530")),
            backend=os.getenv("EMBEDDING_BACKEND", "dashscope")
        )
        print(f"✓ 已连接到 Milvus")
        print(f"  - Collection: {store.collection_name}")
        print(f"  - Dimension: {store.embedding_dim}")

        # 3. 嵌入文档
        if not test_embedding(store, documents):
            return 1

        # 等待索引完成
        import time
        print("\n等待索引完成...")
        time.sleep(3)

        # 4. 测试查询
        results_summary = test_policy_queries(store)

        # 5. 测试过滤搜索
        test_filtered_search(store)

        # 6. 打印总结
        print_summary(results_summary, len(documents))

        # 7. 清理
        cleanup(store)

        print("\n" + "=" * 80)
        print("  测试完成")
        print("=" * 80)

        return 0

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
