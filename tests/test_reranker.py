#!/usr/bin/env python3
"""测试DashScope Reranker功能"""

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
print("Reranker功能测试")
print("="*70)

print(f"\n配置信息:")
print(f"  Backend: {settings.reranker.backend}")
print(f"  Model: {settings.reranker.model_name}")
print(f"  Top N: {settings.reranker.top_n if hasattr(settings.reranker, 'top_n') else 5}")

# 读取一些文档作为候选
data_dir = Path("F:/pythonproject/gov/data/process")
md_files = list(data_dir.rglob("*.md"))[:5]  # 只取5个文档

documents = []
for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # 截取前500字符作为文档片段
        documents.append({
            'text': content[:500],
            'title': md_file.stem
        })

print(f"\n准备了 {len(documents)} 个文档片段进行测试")

# 测试查询
test_query = "家电以旧换新的补贴标准和申请流程"

print(f"\n测试查询: {test_query}")
print("-"*70)

print("\n[1] 原始文档顺序:")
for i, doc in enumerate(documents, 1):
    print(f"  {i}. {doc['title'][:50]}")

# 测试Reranker
print("\n[2] 初始化Reranker...")
try:
    from knowledge_base.rerank import Reranker

    reranker = Reranker()
    print(f"  ✓ Reranker初始化成功")

    # 提取文档文本
    texts = [doc['text'] for doc in documents]

    print(f"\n[3] 执行Rerank (查询: {test_query})...")
    start_time = time.time()

    results = reranker.rerank(
        query=test_query,
        documents=texts,
        top_n=len(documents)  # 返回所有文档，查看完整排序
    )

    rerank_time = time.time() - start_time
    print(f"  ✓ Rerank完成 (耗时: {rerank_time:.3f}秒)")

    print(f"\n[4] Rerank后的排序 (按相关度):")

    # 检查结果格式
    if results and len(results) > 0:
        first_result = results[0]
        print(f"  调试: 结果类型={type(first_result)}, 内容={first_result if isinstance(first_result, dict) else 'tuple/other'}")

        for i, result in enumerate(results, 1):
            if isinstance(result, dict):
                idx = result.get('index', i-1)
                score = result.get('relevance_score', result.get('score', 0))
            elif isinstance(result, tuple) and len(result) >= 2:
                idx, score = result[0], result[1]
            else:
                print(f"  未知结果格式: {type(result)}")
                continue

            doc = documents[idx]
            print(f"  {i}. [分数: {score:.4f}] {doc['title'][:50]}")
            if i <= 3:
                # 显示前3个文档的部分内容
                preview = doc['text'][:100].replace('\n', ' ')
                print(f"      预览: {preview}...")

    print(f"\n[5] 对比分析:")
    print(f"  原始顺序前3:")
    for i in range(min(3, len(documents))):
        print(f"    {i+1}. {documents[i]['title'][:40]}")

    print(f"\n  Rerank后前3:")
    for i in range(min(3, len(results))):
        if isinstance(results[i], tuple) and len(results[i]) >= 2:
            idx, score = results[i][0], results[i][1]
        else:
            continue
        print(f"    {i+1}. {documents[idx]['title'][:40]} (分数: {score:.4f})")

    # 计算顺序变化
    original_order = list(range(len(documents)))
    rerank_order = [r[0] if isinstance(r, tuple) else r.get('index', i) for i, r in enumerate(results)]

    if original_order != rerank_order:
        print(f"\n  ✓ 顺序发生了变化，Reranker生效！")
        print(f"    原始: {original_order}")
        print(f"    重排: {rerank_order}")
    else:
        print(f"\n  ⚠ 顺序未变化")

    print(f"\n[6] 性能统计:")
    print(f"  - 文档数量: {len(documents)}")
    print(f"  - Rerank时间: {rerank_time:.3f}秒")
    print(f"  - 平均每文档: {rerank_time/len(documents)*1000:.1f}毫秒")

except Exception as e:
    print(f"  ✗ Reranker初始化或执行失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("测试完成")
print("="*70)
