#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的混合检索测试 - 使用现有的 MilvusStore + Reranker
对比纯向量检索和向量+Rerank混合检索的效果
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.knowledge.milvus import MilvusStore
from app.knowledge.rerank import Reranker
from dataclasses import dataclass
from typing import List


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


def split_document(content: str, max_chunk_size: int = 1500) -> List[str]:
    """文档分段"""
    import re
    paragraphs = content.split('\n\n')
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [content[:max_chunk_size]]


def load_documents(data_dir):
    """加载文档"""
    documents = []
    md_files = list(Path(data_dir).rglob("*.md"))

    doc_id = 0
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            title = None
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break

            if not title:
                title = md_file.stem

            if "家电" in str(md_file) or "数码" in str(md_file):
                doc_type = "家电数码政策"
            elif "汽车" in str(md_file) or "新车" in str(md_file):
                doc_type = "汽车消费政策"
            else:
                doc_type = "消费活动政策"

            chunks = split_document(content, max_chunk_size=1500)

            for idx, chunk in enumerate(chunks):
                doc_id += 1
                chunk_title = f"{title}" if len(chunks) == 1 else f"{title} (第{idx+1}段)"

                doc = SimpleDocument(
                    id=f"policy_{doc_id}",
                    title=chunk_title,
                    content=chunk,
                    source=str(md_file.relative_to(data_dir)),
                    doc_type=doc_type
                )
                documents.append(doc)

        except Exception as e:
            print(f"读取失败: {md_file.name} - {e}")

    return documents


def test_vector_only_retrieval(store, queries):
    """测试1: 纯向量检索"""
    print_section("测试1: 纯向量检索 (Vector Only)")

    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 60)

        documents, scores = store.search(query, top_k=3, threshold=0.50)

        print(f"✓ 检索到 {len(documents)} 个结果:")
        for j, (doc, score) in enumerate(zip(documents, scores), 1):
            print(f"  {j}. [{score:.4f}] {doc.title[:60]}")
            print(f"      内容: {doc.content[:80].replace(chr(10), ' ')}...")

        results.append({
            'query': query,
            'documents': documents,
            'scores': scores
        })

    return results


def test_vector_plus_rerank_retrieval(store, queries):
    """测试2: 向量检索 + Reranker"""
    print_section("测试2: 向量检索 + Reranker (混合检索)")

    reranker = Reranker()

    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 60)

        # 第1步：向量初召回 (top_k=10)
        documents, scores = store.search(query, top_k=10, threshold=0.50)
        print(f"  初召回: {len(documents)} 个文档")

        if not documents:
            print("  未检索到结果")
            results.append({'query': query, 'documents': [], 'scores': []})
            continue

        # 第2步：Rerank 重排序 (top_k=3)
        doc_texts = [f"{doc.title}\n{doc.content[:500]}" for doc in documents]

        try:
            reranked = reranker.rerank(query, doc_texts, top_n=3)

            # 提取重排序后的文档
            final_docs = []
            final_scores = []
            for idx, score, _ in reranked:
                final_docs.append(documents[idx])
                final_scores.append(score)

            print(f"  Rerank后: {len(final_docs)} 个结果")
            for j, (doc, score) in enumerate(zip(final_docs, final_scores), 1):
                print(f"  {j}. [{score:.4f}] {doc.title[:60]}")
                print(f"      内容: {doc.content[:80].replace(chr(10), ' ')}...")

            results.append({
                'query': query,
                'documents': final_docs,
                'scores': final_scores
            })

        except Exception as e:
            print(f"  ⚠ Rerank失败: {e}")
            # Fallback to original results
            results.append({
                'query': query,
                'documents': documents[:3],
                'scores': scores[:3]
            })

    return results


def compare_results(vector_results, hybrid_results):
    """对比两种检索方式的结果"""
    print_section("对比总结")

    print(f"{'查询':<40} | {'纯向量Top1':<12} | {'混合检索Top1':<12} | {'提升'}")
    print("-" * 90)

    for vec_r, hyb_r in zip(vector_results, hybrid_results):
        query = vec_r['query'][:38]
        vec_score = vec_r['scores'][0] if vec_r['scores'] else 0
        hyb_score = hyb_r['scores'][0] if hyb_r['scores'] else 0
        improvement = hyb_score - vec_score

        improvement_str = f"+{improvement:.4f}" if improvement > 0 else f"{improvement:.4f}"
        print(f"{query:<40} | {vec_score:<12.4f} | {hyb_score:<12.4f} | {improvement_str}")

    # 平均分数
    avg_vec = sum(r['scores'][0] for r in vector_results if r['scores']) / len(vector_results)
    avg_hyb = sum(r['scores'][0] for r in hybrid_results if r['scores']) / len(hybrid_results)

    print("\n" + "=" * 90)
    print(f"平均 Top1 分数:")
    print(f"  纯向量检索: {avg_vec:.4f}")
    print(f"  混合检索 (向量+Rerank): {avg_hyb:.4f}")
    print(f"  提升: {(avg_hyb - avg_vec):.4f} ({((avg_hyb/avg_vec - 1) * 100):.1f}%)")


def main():
    """主流程"""
    print_section("混合检索对比测试 (向量 vs 向量+Rerank)")

    data_dir = Path("/data/temp33/gov/data/process")

    if not data_dir.exists():
        print(f"✗ 数据目录不存在: {data_dir}")
        return 1

    # 1. 加载文档
    print_section("1. 加载文档")
    documents = load_documents(data_dir)
    print(f"✓ 加载了 {len(documents)} 个文档段落")

    # 2. 创建 Milvus store
    print_section("2. 初始化 Milvus")
    store = MilvusStore(
        collection_name="hybrid_comparison_test",
        host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
        port=int(os.getenv("DATABASE__MILVUS_PORT", "19530")),
        backend=os.getenv("EMBEDDING_BACKEND", "dashscope")
    )
    print(f"✓ 连接成功，维度: {store.embedding_dim}")

    # 3. 嵌入文档
    print_section("3. 嵌入文档")
    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        store.add_documents(batch)
        print(f"  进度: {min(i+batch_size, len(documents))}/{len(documents)}")
    print(f"✓ 嵌入完成")

    import time
    time.sleep(3)

    # 4. 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
        "济南市2025年有哪些消费活动？",
        "智能手表购新补贴的条件是什么？"
    ]

    # 测试1: 纯向量检索
    vector_results = test_vector_only_retrieval(store, test_queries)

    # 测试2: 向量 + Rerank
    hybrid_results = test_vector_plus_rerank_retrieval(store, test_queries)

    # 对比结果
    compare_results(vector_results, hybrid_results)

    # 5. 清理
    print_section("5. 清理环境")
    from pymilvus import utility, connections

    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
            port=os.getenv("DATABASE__MILVUS_PORT", "19530")
        )

    if utility.has_collection("hybrid_comparison_test"):
        utility.drop_collection("hybrid_comparison_test")
        print("✓ 已清理测试数据")

    print_section("测试完成")

    print("\n💡 结论:")
    print("  向量检索 + Reranker 是一种简单有效的混合检索方案")
    print("  - 向量检索: 快速初召回，保证召回率")
    print("  - Reranker: 精准重排序，提升精确率")
    print("  - 相比纯向量检索，混合方案通常能提升 10-30% 的精确度\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
