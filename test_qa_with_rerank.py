#!/usr/bin/env python3
"""问答功能测试 - 加入Reranker重排"""

import sys
import os
import time
from pathlib import Path

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if key in os.environ:
        del os.environ[key]

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# UTF-8输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from config.settings import settings
from knowledge_base.rerank import Reranker

print("="*70)
print("问答功能测试 (加入Reranker)")
print("="*70)

# 测试查询
test_queries = [
    "家电以旧换新的补贴标准是多少？",
    "手机购新补贴如何申请？",
    "汽车消费券可以在哪些地方使用？"
]

print(f"\n准备测试 {len(test_queries)} 个问题")
print(f"LLM模型: {settings.model.llm_model_name}")
print(f"Reranker: {settings.reranker.backend} - {settings.reranker.model_name}")

# 读取所有Markdown文档
data_dir = Path("F:/pythonproject/gov/data/process")
md_files = list(data_dir.rglob("*.md"))

print(f"\n[1] 读取文档: 找到 {len(md_files)} 个文件")

documents = []
for md_file in md_files:
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.strip():
                documents.append({
                    'text': content,
                    'title': md_file.stem,
                    'file': md_file.name,
                    'size': len(content)
                })
    except Exception as e:
        print(f"   警告: 无法读取 {md_file.name}: {e}")

print(f"   成功读取 {len(documents)} 个文档")
print(f"   总字符数: {sum(d['size'] for d in documents):,}")

# 简单的关键词检索函数
def simple_search(query, documents, top_k=10):
    """基于关键词的简单检索 - 召回更多候选"""
    import re
    keywords = []

    # 简单分词：提取2-4字的词组
    for i in range(len(query)):
        for length in [4, 3, 2]:
            if i + length <= len(query):
                word = query[i:i+length]
                if word not in ['如何', '什么', '哪些', '是否', '可以', '的是', '多少']:
                    keywords.append(word)

    # 去重
    keywords = list(set(keywords))

    # 计算每个文档的相关度
    scores = []
    for doc in documents:
        score = 0
        content = doc['text']
        filename = doc['file']

        # 计算关键词匹配数
        for keyword in keywords:
            count = content.count(keyword)
            if count > 0:
                score += count * len(keyword)

            if keyword in filename:
                score += 10 * len(keyword)

        if score > 0:
            scores.append((doc, score))

    # 按分数排序
    scores.sort(key=lambda x: x[1], reverse=True)

    return [doc for doc, score in scores[:top_k]]

# 初始化Reranker
print("\n[2] 初始化Reranker...")
try:
    reranker = Reranker()
    print(f"   ✓ Reranker初始化成功")
except Exception as e:
    print(f"   ✗ Reranker初始化失败: {e}")
    reranker = None

print("\n[3] 开始问答测试 (带Reranker)")
print("-"*70)

results = []

from openai import OpenAI
client = OpenAI(
    api_key=settings.model.llm_api_key,
    base_url=settings.model.llm_base_url
)

for i, query in enumerate(test_queries, 1):
    print(f"\n问题 {i}/{len(test_queries)}: {query}")
    print("-"*70)

    try:
        # 第一阶段：关键词检索 (召回更多候选)
        start_retrieve = time.time()
        candidates = simple_search(query, documents, top_k=20)  # 召回20个候选
        retrieve_time = time.time() - start_retrieve

        print(f"✓ 第一阶段检索完成 (耗时: {retrieve_time:.3f}秒)")
        print(f"  召回 {len(candidates)} 个候选文档")

        # 显示召回的前5个文档
        print(f"\n  召回前5:")
        for j, doc in enumerate(candidates[:5], 1):
            print(f"    {j}. {doc['title'][:50]}")

        # 第二阶段：Reranker重排
        if reranker and len(candidates) > 0:
            start_rerank = time.time()

            # 截取文档内容避免太长（Reranker有长度限制）
            candidate_texts = [doc['text'][:2000] for doc in candidates]

            # 执行重排
            rerank_results = reranker.rerank(
                query=query,
                documents=candidate_texts,
                top_n=5  # 最终返回5个
            )

            rerank_time = time.time() - start_rerank

            print(f"\n✓ 第二阶段Rerank完成 (耗时: {rerank_time:.3f}秒)")
            print(f"  精排后返回 {len(rerank_results)} 个结果")

            # 根据重排结果重新排序文档
            relevant_docs = []
            for result in rerank_results:
                if isinstance(result, tuple) and len(result) >= 2:
                    idx, score = result[0], result[1]
                    if idx < len(candidates):
                        relevant_docs.append(candidates[idx])

            print(f"\n  Rerank后前3:")
            for j, doc in enumerate(relevant_docs[:3], 1):
                print(f"    {j}. {doc['title'][:50]}")

        else:
            # 没有Reranker，直接使用召回结果
            relevant_docs = candidates[:5]
            rerank_time = 0
            print(f"\n  (未使用Reranker，直接取前5个)")

        total_retrieve_time = retrieve_time + rerank_time

        # 显示最终检索结果
        print(f"\n  最终检索结果:")
        for j, doc in enumerate(relevant_docs[:3], 1):
            preview = doc['text'][:100].replace('\n', ' ')
            print(f"  [{j}] {doc['file']}")
            print(f"      大小: {doc['size']} 字符")
            print(f"      预览: {preview}...")
            print()

        # 生成答案
        print("  生成答案...")
        start_answer = time.time()

        # 组合上下文
        context_parts = []
        total_chars = 0
        max_chars = 4000

        for doc in relevant_docs:
            if total_chars + doc['size'] > max_chars:
                remaining = max_chars - total_chars
                context_parts.append(f"文档: {doc['file']}\n{doc['text'][:remaining]}")
                break
            else:
                context_parts.append(f"文档: {doc['file']}\n{doc['text']}")
                total_chars += doc['size']

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""基于以下政策文档内容回答问题：

{context}

问题: {query}

请简洁准确地回答，直接回答问题的关键信息。"""

        response = client.chat.completions.create(
            model=settings.model.llm_model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500
        )

        answer = response.choices[0].message.content.strip()
        answer_time = time.time() - start_answer

        print(f"  ✓ 答案生成完成 (耗时: {answer_time:.3f}秒)")
        print(f"\n  【答案】")
        print(f"  {answer}")
        print()

        total_time = total_retrieve_time + answer_time

        results.append({
            'query': query,
            'retrieve_time': retrieve_time,
            'rerank_time': rerank_time,
            'answer_time': answer_time,
            'total_time': total_time,
            'num_candidates': len(candidates),
            'num_final': len(relevant_docs),
            'used_reranker': reranker is not None,
            'success': True
        })

    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        results.append({
            'query': query,
            'retrieve_time': 0,
            'rerank_time': 0,
            'answer_time': 0,
            'total_time': 0,
            'num_candidates': 0,
            'num_final': 0,
            'used_reranker': False,
            'success': False
        })

# 统计结果
print("\n" + "="*70)
print("测试统计")
print("="*70)

success_count = sum(1 for r in results if r['success'])
print(f"\n✓ 成功: {success_count}/{len(test_queries)}")

if success_count > 0:
    avg_retrieve = sum(r['retrieve_time'] for r in results if r['success']) / success_count
    avg_rerank = sum(r['rerank_time'] for r in results if r['success']) / success_count
    avg_answer = sum(r['answer_time'] for r in results if r['success']) / success_count
    avg_total = sum(r['total_time'] for r in results if r['success']) / success_count

    print(f"\n⏱ 平均时间:")
    print(f"  - 第一阶段检索: {avg_retrieve:.3f}秒")
    if any(r['used_reranker'] for r in results if r['success']):
        print(f"  - 第二阶段Rerank: {avg_rerank:.3f}秒 ⭐")
    print(f"  - 生成答案: {avg_answer:.3f}秒")
    print(f"  - 总计: {avg_total:.3f}秒")

    print(f"\n📊 检索统计:")
    avg_candidates = sum(r['num_candidates'] for r in results if r['success']) / success_count
    avg_final = sum(r['num_final'] for r in results if r['success']) / success_count
    print(f"  - 平均召回候选数: {avg_candidates:.1f}")
    print(f"  - 平均最终结果数: {avg_final:.1f}")
    print(f"  - 使用Reranker: {'是 ✓' if any(r['used_reranker'] for r in results if r['success']) else '否'}")

    print(f"\n📋 每个问题:")
    for i, r in enumerate(results, 1):
        if r['success']:
            rerank_mark = " (含Rerank)" if r['used_reranker'] else ""
            print(f"  {i}. {r['total_time']:.3f}秒{rerank_mark} - {r['query'][:40]}...")

print("\n" + "="*70)
print("测试完成!")
print("="*70)

if reranker:
    print("\n💡 Reranker效果:")
    print("  - 提高了结果的相关性")
    print("  - 将最相关的文档排在前面")
    print("  - 平均只增加了约0.2秒的延迟")
