#!/usr/bin/env python3
"""问答功能测试 - 测试检索和响应时间"""

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

from app.config import settings

print("="*70)
print("问答功能测试")
print("="*70)

# 测试查询列表
test_queries = [
    "家电以旧换新的补贴标准是多少？",
    "手机购新补贴如何申请？",
    "汽车消费券可以在哪些地方使用？",
    "济南市消费券的发放时间是什么时候？",
    "以旧换新需要满足什么条件？"
]

print(f"\n准备测试 {len(test_queries)} 个问题")
print(f"LLM模型: {settings.model.llm_model_name}")
print(f"Reranker: {settings.reranker.backend} - {settings.reranker.model_name}")

# 尝试加载已有的索引
storage_dir = "./storage/policy_index"
storage_path = Path(storage_dir)

if not storage_path.exists():
    print(f"\n⚠ 索引目录不存在: {storage_dir}")
    print("需要先运行嵌入脚本创建索引")
    sys.exit(1)

print(f"\n[1] 加载索引: {storage_dir}")
try:
    from app.knowledge.hierarchical_index import HierarchicalRetriever

    # 配置LlamaIndex embedding (即使出错也继续)
    try:
        from llama_index.core import Settings as LISettings
        from llama_index.embeddings.openai import OpenAIEmbedding

        LISettings.embed_model = OpenAIEmbedding(
            model="text-embedding-ada-002",
            api_key=settings.embedding.dashscope_api_key,
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        print("   Embedding配置完成")
    except Exception as e:
        print(f"   Embedding配置失败: {e}")
        print("   继续测试...")

    start_load = time.time()
    retriever = HierarchicalRetriever(
        storage_dir=storage_dir,
        use_rerank="dashscope",
        enable_images=True
    )
    load_time = time.time() - start_load
    print(f"   加载完成 (耗时: {load_time:.2f}秒)")

except Exception as e:
    print(f"   加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[2] 开始问答测试")
print("-"*70)

results = []
for i, query in enumerate(test_queries, 1):
    print(f"\n问题 {i}/{len(test_queries)}: {query}")
    print("-"*70)

    try:
        # 记录检索开始时间
        start_retrieve = time.time()

        # 执行检索
        nodes = retriever.retrieve(
            query=query,
            top_k=3,
            use_rerank=True,
            retrieval_mode="hybrid"
        )

        retrieve_time = time.time() - start_retrieve

        print(f"✓ 检索完成 (耗时: {retrieve_time:.2f}秒)")
        print(f"  返回 {len(nodes)} 个结果块\n")

        # 显示检索结果
        for j, node in enumerate(nodes, 1):
            node_type = node.metadata.get('type', 'unknown')
            title = node.metadata.get('title', '无标题')
            doc_id = node.metadata.get('doc_id', 'unknown')
            path = node.metadata.get('path', '')

            # 内容预览
            text_preview = node.text[:150].replace('\n', ' ')
            if len(node.text) > 150:
                text_preview += "..."

            print(f"  [{j}] 类型: {node_type}")
            print(f"      文档: {title}")
            if path:
                print(f"      路径: {path}")
            print(f"      节点ID: {node.id_}")
            print(f"      内容: {text_preview}")
            print()

        # 尝试生成答案
        print("  生成答案...")
        start_answer = time.time()

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.model.llm_api_key,
                base_url=settings.model.llm_base_url
            )

            # 组合上下文
            context = "\n\n".join([
                f"[文档{i+1}] {node.metadata.get('title', '')}:\n{node.text}"
                for i, node in enumerate(nodes)
            ])

            prompt = f"""基于以下政策文档内容回答问题：

{context}

问题: {query}

请简洁准确地回答，如果文档中没有相关信息，请说明。"""

            response = client.chat.completions.create(
                model=settings.model.llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500
            )

            answer = response.choices[0].message.content.strip()
            answer_time = time.time() - start_answer

            print(f"  ✓ 答案生成完成 (耗时: {answer_time:.2f}秒)")
            print(f"\n  【答案】")
            print(f"  {answer}")

            total_time = retrieve_time + answer_time

            results.append({
                'query': query,
                'retrieve_time': retrieve_time,
                'answer_time': answer_time,
                'total_time': total_time,
                'num_chunks': len(nodes),
                'success': True
            })

        except Exception as e:
            print(f"  ✗ 答案生成失败: {e}")
            results.append({
                'query': query,
                'retrieve_time': retrieve_time,
                'answer_time': 0,
                'total_time': retrieve_time,
                'num_chunks': len(nodes),
                'success': False
            })

    except Exception as e:
        print(f"✗ 检索失败: {e}")
        import traceback
        traceback.print_exc()
        results.append({
            'query': query,
            'retrieve_time': 0,
            'answer_time': 0,
            'total_time': 0,
            'num_chunks': 0,
            'success': False
        })

# 统计结果
print("\n" + "="*70)
print("测试统计")
print("="*70)

success_count = sum(1 for r in results if r['success'])
print(f"\n成功问题数: {success_count}/{len(test_queries)}")

if success_count > 0:
    avg_retrieve = sum(r['retrieve_time'] for r in results if r['success']) / success_count
    avg_answer = sum(r['answer_time'] for r in results if r['success']) / success_count
    avg_total = sum(r['total_time'] for r in results if r['success']) / success_count

    print(f"\n平均时间:")
    print(f"  - 检索时间: {avg_retrieve:.2f}秒")
    print(f"  - 答案生成: {avg_answer:.2f}秒")
    print(f"  - 总时间: {avg_total:.2f}秒")

    print(f"\n每个问题详情:")
    for i, r in enumerate(results, 1):
        if r['success']:
            print(f"  {i}. {r['query'][:30]}... - {r['total_time']:.2f}秒 ({r['num_chunks']}块)")

print("\n" + "="*70)
print("测试完成!")
print("="*70)
