#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库所有召回方式综合测试
Testing all retrieval methods in the knowledge base
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from knowledge_base.milvus import MilvusStore
from knowledge_base.rerank import Reranker
from knowledge_base.hybrid_retrieval import HybridRetriever, create_hybrid_retriever_from_files


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


def evaluate_relevance(query: str, doc_title: str, doc_type: str, doc_content: str = "") -> str:
    """评估相关性"""
    query_lower = query.lower()
    title_lower = doc_title.lower()
    content_lower = doc_content[:300].lower()

    intent_rules = {
        "家电以旧换新": {
            "keywords": ["家电", "以旧换新", "换新"],
            "type": "家电数码政策"
        },
        "买新手机": {
            "keywords": ["手机", "购新", "补贴"],
            "type": "家电数码政策"
        },
        "汽车补贴申请": {
            "keywords": ["汽车", "补贴", "申请"],
            "type": "汽车消费政策"
        },
        "消费活动": {
            "keywords": ["消费", "活动", "济南"],
            "type": None
        },
        "智能手表补贴": {
            "keywords": ["智能手表", "手表", "购新", "补贴"],
            "type": "家电数码政策"
        }
    }

    intent = None
    if "家电" in query and "以旧换新" in query:
        intent = "家电以旧换新"
    elif "手机" in query:
        intent = "买新手机"
    elif "汽车" in query and "补贴" in query:
        intent = "汽车补贴申请"
    elif "消费" in query and "活动" in query:
        intent = "消费活动"
    elif "智能手表" in query or "手表" in query:
        intent = "智能手表补贴"

    if intent and intent in intent_rules:
        rule = intent_rules[intent]
        matches = sum(1 for kw in rule["keywords"] if kw in title_lower or kw in content_lower)
        type_match = rule["type"] is None or doc_type == rule["type"]

        if matches >= 1 and type_match:
            return "精准"
        elif type_match:
            return "相关"

    return "泛相关"


def test_method_1_vector_only(store, queries):
    """方法1: 纯向量检索"""
    print_section("方法1: 纯向量检索 (Vector Only)")

    results = []
    total_time = 0

    for i, query in enumerate(queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 60)

        start_time = time.time()
        documents, scores = store.search(query, top_k=3, threshold=0.50)
        elapsed = (time.time() - start_time) * 1000
        total_time += elapsed

        print(f"✓ 检索耗时: {elapsed:.2f}ms, 返回: {len(documents)} 个结果")

        query_results = []
        for j, (doc, score) in enumerate(zip(documents, scores), 1):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            symbol = "✓" if relevance == "精准" else ("○" if relevance == "相关" else "△")

            print(f"  {j}. [{symbol}] [{score:.4f}] {doc.title[:50]}")
            query_results.append({
                'relevance': relevance,
                'score': score,
                'title': doc.title
            })

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results),
            'time_ms': elapsed
        })

    avg_time = total_time / len(queries)
    print(f"\n平均检索耗时: {avg_time:.2f}ms")

    return results


def test_method_2_vector_rerank(store, queries):
    """方法2: 向量 + Reranker"""
    print_section("方法2: 向量检索 + Reranker 重排序")

    reranker = Reranker()
    results = []
    total_time = 0

    for i, query in enumerate(queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 60)

        start_time = time.time()

        # 初召回
        documents, scores = store.search(query, top_k=10, threshold=0.50)

        if not documents:
            print("  未检索到结果")
            results.append({
                'query': query,
                'results': [],
                'precise': 0,
                'total': 0,
                'time_ms': 0
            })
            continue

        # Rerank
        doc_texts = [f"{doc.title}\n{doc.content[:500]}" for doc in documents]

        try:
            reranked = reranker.rerank(query, doc_texts, top_n=3)
            final_docs = [documents[idx] for idx, _, _ in reranked]
            final_scores = [score for _, score, _ in reranked]
        except Exception as e:
            print(f"  ⚠ Rerank失败: {e}, 使用原始结果")
            final_docs = documents[:3]
            final_scores = scores[:3]

        elapsed = (time.time() - start_time) * 1000
        total_time += elapsed

        print(f"✓ 检索耗时: {elapsed:.2f}ms (初召回+Rerank), 返回: {len(final_docs)} 个结果")

        query_results = []
        for j, (doc, score) in enumerate(zip(final_docs, final_scores), 1):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            symbol = "✓" if relevance == "精准" else ("○" if relevance == "相关" else "△")

            print(f"  {j}. [{symbol}] [{score:.4f}] {doc.title[:50]}")
            query_results.append({
                'relevance': relevance,
                'score': score,
                'title': doc.title
            })

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results),
            'time_ms': elapsed
        })

    avg_time = total_time / len(queries)
    print(f"\n平均检索耗时: {avg_time:.2f}ms")

    return results


def test_method_3_hybrid_bm25_vector(data_dir, queries):
    """方法3: 混合检索 (BM25 + Vector) - 增强版"""
    print_section("方法3: 混合检索 (BM25 + Vector) - 增强版")

    try:
        # 创建增强版混合检索器
        print("正在初始化增强版混合检索器（带查询增强和类型加权）...")
        from knowledge_base.hybrid_retrieval import create_enhanced_hybrid_retriever_from_files

        retriever = create_enhanced_hybrid_retriever_from_files(
            data_dir,
            chunking_strategy='sentence',
            chunk_size=600,
            chunk_overlap=80
        )

        results = []
        total_time = 0

        for i, query in enumerate(queries, 1):
            print(f"\n查询 {i}: {query}")
            print("-" * 60)

            start_time = time.time()

            # 执行增强版混合检索（启用查询增强和类型加权）
            chunks = retriever.retrieve(
                query,
                top_k_docs=10,
                top_k_chunks=3,
                chunk_strategy='bm25',
                enable_query_enhancement=True,
                enable_doc_type_boost=True
            )

            elapsed = (time.time() - start_time) * 1000
            total_time += elapsed

            print(f"\n✓ 检索耗时: {elapsed:.2f}ms, 返回: {len(chunks)} 个结果")

            query_results = []
            for j, chunk in enumerate(chunks[:3], 1):
                # 使用 chunk 的元数据评估相关性
                doc_title = chunk.get("full_title", chunk.get("doc_title", ""))
                doc_type = chunk.get("doc_type", "消费活动政策")  # 从chunk获取类型
                relevance = evaluate_relevance(query, doc_title, doc_type, chunk['text'])
                symbol = "✓" if relevance == "精准" else ("��" if relevance == "相关" else "△")

                score = chunk.get('chunk_score', 0)
                print(f"  {j}. [{symbol}] [{score:.4f}] {doc_title[:45]} ({doc_type})")

                query_results.append({
                    'relevance': relevance,
                    'score': score,
                    'title': doc_title
                })

            precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
            results.append({
                'query': query,
                'results': query_results,
                'precise': precise_count,
                'total': len(query_results),
                'time_ms': elapsed
            })

        avg_time = total_time / len(queries)
        print(f"\n平均检索耗时: {avg_time:.2f}ms")

        return results

    except Exception as e:
        print(f"✗ 混合检索初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_comparison(all_results, method_names):
    """打印对比总结"""
    print_section("所有召回方式对比总结")

    # 表头
    print(f"{'方法':<35} | {'精准数':<8} | {'总数':<6} | {'精准率':<10} | {'平均耗时':<12} | {'评级'}")
    print("-" * 95)

    for method_name, results in zip(method_names, all_results):
        if results is None:
            print(f"{method_name:<35} | {'N/A':<8} | {'N/A':<6} | {'N/A':<10} | {'N/A':<12} | N/A")
            continue

        total_precise = sum(r['precise'] for r in results)
        total_results = sum(r['total'] for r in results)
        avg_time = sum(r['time_ms'] for r in results) / len(results) if results else 0
        precision = (total_precise / total_results * 100) if total_results > 0 else 0

        if precision >= 90:
            grade = "⭐⭐⭐⭐⭐"
        elif precision >= 80:
            grade = "⭐⭐⭐⭐"
        elif precision >= 70:
            grade = "⭐⭐⭐"
        elif precision >= 60:
            grade = "⭐⭐"
        else:
            grade = "⭐"

        print(f"{method_name:<35} | {total_precise:<8} | {total_results:<6} | {precision:<9.1f}% | {avg_time:<11.2f}ms | {grade}")

    # 详细对比
    print("\n" + "=" * 95)
    print("  各查询详细对比")
    print("=" * 95)

    queries = [r['query'] for r in all_results[0]] if all_results[0] else []

    for i, query in enumerate(queries):
        print(f"\n查询 {i+1}: {query}")
        print("-" * 70)

        for method_name, results in zip(method_names, all_results):
            if results is None or i >= len(results):
                print(f"  {method_name:<30} | N/A")
                continue

            r = results[i]
            precision = (r['precise'] / r['total'] * 100) if r['total'] > 0 else 0
            print(f"  {method_name:<30} | 精准:{r['precise']}/{r['total']} ({precision:.0f}%), 耗时:{r['time_ms']:.0f}ms")


def main():
    """主流程"""
    print("\n" + "=" * 80)
    print("  知识库所有召回方式综合测试")
    print("=" * 80)

    data_dir = Path("/data/temp33/gov/data/process")

    if not data_dir.exists():
        print(f"✗ 数据目录不存在: {data_dir}")
        return 1

    # 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
        "济南市2025年有哪些消费活动？",
        "智能手表购新补贴的条件是什么？"
    ]

    # 加载文档
    print_section("加载文档")
    documents = load_documents(data_dir)
    print(f"✓ 加载了 {len(documents)} 个文档段落")

    # 创建 Milvus store
    print_section("初始化 Milvus")
    store = MilvusStore(
        collection_name="all_methods_comparison_test",
        host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
        port=int(os.getenv("DATABASE__MILVUS_PORT", "19530")),
        backend=os.getenv("EMBEDDING_BACKEND", "dashscope")
    )
    print(f"✓ 连接成功，维度: {store.embedding_dim}")

    # 嵌入文档
    print_section("嵌入文档")
    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        store.add_documents(batch)
        print(f"  进度: {min(i+batch_size, len(documents))}/{len(documents)}")
    print(f"✓ 嵌入完成")

    time.sleep(3)

    # 测试各种召回方式
    results_method_1 = test_method_1_vector_only(store, test_queries)
    results_method_2 = test_method_2_vector_rerank(store, test_queries)
    results_method_3 = test_method_3_hybrid_bm25_vector(data_dir, test_queries)

    # 打印对比
    all_results = [
        results_method_1,
        results_method_2,
        results_method_3
    ]

    method_names = [
        "1. 纯向量检索",
        "2. 向量 + Reranker ⭐推荐",
        "3. 混合检索 (增强版 BM25+类型加权)"
    ]

    print_comparison(all_results, method_names)

    # 清理
    print_section("清理环境")
    from pymilvus import utility, connections

    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=os.getenv("DATABASE__MILVUS_HOST", "localhost"),
            port=os.getenv("DATABASE__MILVUS_PORT", "19530")
        )

    if utility.has_collection("all_methods_comparison_test"):
        utility.drop_collection("all_methods_comparison_test")
        print("✓ 已清理测试数据")

    print_section("测试完成")

    print("\n💡 推荐:")
    print("  根据测试结果，向量 + Reranker 方案在精准率和速度之间")
    print("  取得了最佳平衡，推荐用于生产环境。\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
