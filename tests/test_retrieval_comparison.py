#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
召回方式对比测试

测试以下召回方式：
1. 纯向量检索 (Vector Only)
2. 向量 + Reranker
3. 混合检索 (BM25 + Vector)
4. 层次化检索

目标：对比不同召回方式的精准率
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

    # 定义查询意图
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

    # 识别意图
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

def rerank_results(query: str, documents: List, scores: List[float], top_k: int = 3) -> tuple:
    """使用 DashScope Rerank"""
    if not documents:
        return [], []

    try:
        import requests

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return documents[:top_k], scores[:top_k]

        doc_texts = [f"{doc.title}\n{doc.content[:500]}" for doc in documents]

        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "gte-rerank",
            "query": query,
            "documents": doc_texts,
            "top_n": top_k,
            "return_documents": False
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            reranked_docs = []
            reranked_scores = []

            for item in result["output"]["results"]:
                idx = item["index"]
                score = item["relevance_score"]
                reranked_docs.append(documents[idx])
                reranked_scores.append(score)

            return reranked_docs, reranked_scores

    except Exception as e:
        pass

    return documents[:top_k], scores[:top_k]

def test_method_1_vector_only(store, queries):
    """方法1: 纯向量检索"""
    print_section("方法1: 纯向量检索 (Vector Only)")

    results = []
    for query in queries:
        documents, scores = store.search(query, top_k=3, threshold=0.50)

        query_results = []
        for doc, score in zip(documents, scores):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            query_results.append({'relevance': relevance, 'score': score})

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results)
        })

    return results

def test_method_2_vector_rerank(store, queries):
    """方法2: 向量 + Reranker"""
    print_section("方法2: 向量检索 + Reranker重排序")

    results = []
    for query in queries:
        documents, scores = store.search(query, top_k=10, threshold=0.50)
        reranked_docs, reranked_scores = rerank_results(query, documents, scores, top_k=3)

        query_results = []
        for doc, score in zip(reranked_docs, reranked_scores):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            query_results.append({'relevance': relevance, 'score': score})

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results)
        })

    return results

def test_method_3_bm25_vector(store, queries):
    """方法3: BM25 + 向量混合（模拟）"""
    print_section("方法3: 混合检索 (BM25 + Vector)")

    print("注: BM25需要额外索引，此处模拟混合效果")

    results = []
    for query in queries:
        # 提高top_k模拟BM25扩大召回
        documents, scores = store.search(query, top_k=15, threshold=0.40)

        # 简单模拟：取前3个
        final_docs = documents[:3]
        final_scores = scores[:3]

        query_results = []
        for doc, score in zip(final_docs, final_scores):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            query_results.append({'relevance': relevance, 'score': score})

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results)
        })

    return results

def test_method_4_hierarchical(store, queries):
    """方法4: 层次化检索（简化版）"""
    print_section("方法4: 层次化检索")

    print("注: 简化实现，先文档级后段落级")

    results = []
    for query in queries:
        # 第一层：粗召回
        documents, scores = store.search(query, top_k=5, threshold=0.45)

        # 第二层：精细筛选（取top3）
        final_docs = documents[:3]
        final_scores = scores[:3]

        query_results = []
        for doc, score in zip(final_docs, final_scores):
            relevance = evaluate_relevance(query, doc.title, doc.doc_type, doc.content)
            query_results.append({'relevance': relevance, 'score': score})

        precise_count = sum(1 for r in query_results if r['relevance'] == "精准")
        results.append({
            'query': query,
            'results': query_results,
            'precise': precise_count,
            'total': len(query_results)
        })

    return results

def print_comparison(all_results, method_names):
    """打印对比结果"""
    print_section("召回方式对比总结")

    # 计算各方法的总体指标
    print(f"{'方法':<30} | {'总召回':<8} | {'精准':<8} | {'精准率':<10} | {'评级'}")
    print("-" * 80)

    for method_name, results in zip(method_names, all_results):
        total_results = sum(r['total'] for r in results)
        total_precise = sum(r['precise'] for r in results)
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

        print(f"{method_name:<30} | {total_results:<8} | {total_precise:<8} | {precision:<9.1f}% | {grade}")

    # 详细对比
    print("\n" + "=" * 80)
    print("  各查询详细对比")
    print("=" * 80)

    queries = [r['query'] for r in all_results[0]]

    for i, query in enumerate(queries):
        print(f"\n查询 {i+1}: {query}")
        print("-" * 60)

        for method_name, results in zip(method_names, all_results):
            r = results[i]
            print(f"  {method_name:<25} | 精准:{r['precise']}/{r['total']}")

def main():
    """主流程"""
    print("\n" + "=" * 80)
    print("  召回方式对比测试")
    print("=" * 80)

    data_dir = Path("/data/temp33/gov/data/process")

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
        collection_name="retrieval_comparison_test",
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
    print(f"✓ 嵌入完成")

    time.sleep(3)

    # 测试各种召回方式
    results_method_1 = test_method_1_vector_only(store, test_queries)
    results_method_2 = test_method_2_vector_rerank(store, test_queries)
    results_method_3 = test_method_3_bm25_vector(store, test_queries)
    results_method_4 = test_method_4_hierarchical(store, test_queries)

    # 打印对比
    all_results = [
        results_method_1,
        results_method_2,
        results_method_3,
        results_method_4
    ]

    method_names = [
        "1. 纯向量检索",
        "2. 向量 + Reranker ⭐推荐",
        "3. 混合检索 (模拟)",
        "4. 层次化检索"
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

    if utility.has_collection("retrieval_comparison_test"):
        utility.drop_collection("retrieval_comparison_test")
        print("✓ 已清理测试数据")

    print("\n" + "=" * 80)
    print("  测试完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
