#!/usr/bin/env python3
"""直接读取Markdown测试问答功能 - 不需要向量索引"""

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

from config import settings

print("="*70)
print("问答功能测试 (直接读取文档)")
print("="*70)

# 测试查询
test_queries = [
    "家电以旧换新的补贴标准是多少？",
    "手机购新补贴如何申请？",
    "汽车消费券可以在哪些地方使用？"
]

print(f"\n准备测试 {len(test_queries)} 个问题")
print(f"LLM模型: {settings.model.llm_model_name}")

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
                    'file': md_file.name,
                    'content': content,
                    'size': len(content)
                })
    except Exception as e:
        print(f"   警告: 无法读取 {md_file.name}: {e}")

print(f"   成功读取 {len(documents)} 个文档")
print(f"   总字符数: {sum(d['size'] for d in documents):,}")

# 简单的关键词检索函数
def simple_search(query, documents, top_k=3):
    """基于关键词的简单检索"""
    # 提取查询中的关键词（分词）
    import re
    keywords = []

    # 简单分词：提取2-4字的词组
    for i in range(len(query)):
        for length in [4, 3, 2]:
            if i + length <= len(query):
                word = query[i:i+length]
                if word not in ['如何', '什么', '哪些', '是否', '可以', '的是']:
                    keywords.append(word)

    # 去重
    keywords = list(set(keywords))
    print(f"  检索关键词: {', '.join(keywords[:10])}")

    # 计算每个文档的相关度
    scores = []
    for doc in documents:
        score = 0
        content = doc['content']
        filename = doc['file']

        # 计算关键词匹配数
        for keyword in keywords:
            # 在内容中查找
            count = content.count(keyword)
            if count > 0:
                score += count * len(keyword)  # 长词权重更高

            # 在文件名中查找（权重加倍）
            if keyword in filename:
                score += 10 * len(keyword)

        if score > 0:
            scores.append((doc, score))

    # 按分数排序
    scores.sort(key=lambda x: x[1], reverse=True)

    return [doc for doc, score in scores[:top_k]]

print("\n[2] 开始问答测试")
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
        # 检索相关文档
        start_retrieve = time.time()
        relevant_docs = simple_search(query, documents, top_k=3)
        retrieve_time = time.time() - start_retrieve

        print(f"✓ 检索完成 (耗时: {retrieve_time:.3f}秒)")
        print(f"  找到 {len(relevant_docs)} 个相关文档\n")

        # 显示检索到的文档
        for j, doc in enumerate(relevant_docs, 1):
            preview = doc['content'][:100].replace('\n', ' ')
            print(f"  [{j}] {doc['file']}")
            print(f"      大小: {doc['size']} 字符")
            print(f"      预览: {preview}...")
            print()

        # 生成答案
        print("  生成答案...")
        start_answer = time.time()

        # 组合上下文 (限制长度避免超出token限制)
        context_parts = []
        total_chars = 0
        max_chars = 4000  # 限制上下文长度

        for doc in relevant_docs:
            if total_chars + doc['size'] > max_chars:
                # 只取部分内容
                remaining = max_chars - total_chars
                context_parts.append(f"文档: {doc['file']}\n{doc['content'][:remaining]}")
                break
            else:
                context_parts.append(f"文档: {doc['file']}\n{doc['content']}")
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

        total_time = retrieve_time + answer_time

        results.append({
            'query': query,
            'retrieve_time': retrieve_time,
            'answer_time': answer_time,
            'total_time': total_time,
            'num_docs': len(relevant_docs),
            'success': True
        })

    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        results.append({
            'query': query,
            'retrieve_time': 0,
            'answer_time': 0,
            'total_time': 0,
            'num_docs': 0,
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
    avg_answer = sum(r['answer_time'] for r in results if r['success']) / success_count
    avg_total = sum(r['total_time'] for r in results if r['success']) / success_count

    print(f"\n⏱ 平均时间:")
    print(f"  - 检索: {avg_retrieve:.3f}秒")
    print(f"  - 生成答案: {avg_answer:.3f}秒")
    print(f"  - 总计: {avg_total:.3f}秒")

    print(f"\n📋 每个问题:")
    for i, r in enumerate(results, 1):
        if r['success']:
            print(f"  {i}. {r['total_time']:.3f}秒 - {r['query'][:40]}...")

print("\n" + "="*70)
print("测试完成!")
print("="*70)
