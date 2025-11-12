#!/usr/bin/env python3
"""
简化的政策问答测试 - 直接使用Milvus和LLM
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from pymilvus import Collection
from openai import OpenAI
from app.knowledge.milvus import MilvusStore
from app.config import settings
from llama_index.embeddings.dashscope import DashScopeEmbedding, DashScopeTextEmbeddingModels


def test_policy_qa():
    """测试政策问答"""
    print("=" * 80)
    print("政策问答准确性测试")
    print("=" * 80)
    print()

    # 初始化组件
    print("初始化组件...")
    store = MilvusStore()
    embed_model = DashScopeEmbedding(
        model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
        api_key=settings.embedding.dashscope_api_key,
        embed_batch_size=10
    )
    llm_client = OpenAI(
        api_key=settings.model.llm_api_key,
        base_url=settings.model.llm_base_url
    )

    # 测试问题
    test_cases = [
        # 家电补贴相关
        {
            "query": "济南市购买一级能效冰箱补贴多少",
            "expected": "20%（15%基础+5%额外），最高2000元"
        },
        {
            "query": "济南市二级能效洗衣机补贴比例",
            "expected": "15%，最高2000元"
        },
        {
            "query": "济南市家电以旧换新包括哪些产品",
            "expected": "12类家电"
        },
        {
            "query": "每个人可以买几件家电享受补贴",
            "expected": "每类1件，空调最多3件"
        },
        # 手机补贴相关
        {
            "query": "济南市买手机补贴多少",
            "expected": "15%，最高500元"
        },
        {
            "query": "手机补贴的价格上限是多少",
            "expected": "6000元"
        },
        # 具体计算
        {
            "query": "济南市买一台5000元的一级能效冰箱能补贴多少钱",
            "expected": "1000元（5000*20%）"
        },
        {
            "query": "济南市买一个4000元的手机能补贴多少钱",
            "expected": "500元（上限）"
        },
        # 申领流程
        {
            "query": "在哪里领取济南市家电补贴资格",
            "expected": "泉城购服务平台"
        },
        {
            "query": "家电补贴资格领取后多久内要使用",
            "expected": "2个自然日"
        }
    ]

    print(f"开始测试 {len(test_cases)} 个问题...\n")

    # 统计
    correct = 0
    total = len(test_cases)

    for i, case in enumerate(test_cases, 1):
        query = case["query"]
        expected = case["expected"]

        print(f"[{i}/{total}] 问题: {query}")

        # 1. 向量检索
        try:
            # 生成查询向量
            query_vec = embed_model.get_text_embedding(query)

            # 在Milvus中搜索
            collection = Collection(settings.database.milvus_collection_name)
            results = collection.search(
                data=[query_vec],
                anns_field="embedding",
                param={"metric_type": "IP"},
                limit=3,
                output_fields=["content", "title", "source"]
            )

            # 提取上下文
            contexts = []
            for hit in results[0]:
                content = hit.entity.get('content', '')
                if content:
                    contexts.append(content[:500])

            context_text = "\n\n".join(contexts) if contexts else "未找到相关文档"

        except Exception as e:
            context_text = f"检索错误: {e}"
            print(f"  ⚠️ 检索失败: {e}")

        # 2. LLM生成答案
        try:
            prompt = f"""基于以下政策文档回答问题：

上下文:
{context_text}

问题: {query}

请简洁准确地回答，如果涉及数字和百分比请明确给出。"""

            response = llm_client.chat.completions.create(
                model=settings.model.llm_model_name,
                messages=[
                    {"role": "system", "content": "你是政策问答助手，请基于提供的文档内容准确回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=200
            )

            answer = response.choices[0].message.content.strip()

        except Exception as e:
            answer = f"生成错误: {e}"
            print(f"  ⚠️ LLM生成失败: {e}")

        # 3. 检查答案
        # 提取关键信息判断
        answer_correct = False
        if "20%" in expected and ("20%" in answer or "20" in answer):
            answer_correct = True
        elif "15%" in expected and ("15%" in answer or "15" in answer):
            answer_correct = True
        elif "12类" in expected and ("12" in answer or "十二" in answer):
            answer_correct = True
        elif "500元" in expected and ("500" in answer):
            answer_correct = True
        elif "1000元" in expected and ("1000" in answer or "一千" in answer):
            answer_correct = True
        elif "6000" in expected and ("6000" in answer or "六千" in answer):
            answer_correct = True
        elif "2个自然日" in expected and ("2" in answer or "两" in answer) and "日" in answer:
            answer_correct = True
        elif "泉城购" in expected and "泉城购" in answer:
            answer_correct = True
        elif "空调最多3件" in expected and "3" in answer and "空调" in answer:
            answer_correct = True

        if answer_correct:
            correct += 1
            print(f"  ✅ 回答正确")
        else:
            print(f"  ❌ 回答错误")

        print(f"  期望: {expected}")
        print(f"  回答: {answer[:100]}...")
        print()

    # 统计结果
    print("=" * 80)
    print("测试结果")
    print("=" * 80)
    accuracy = correct / total * 100
    print(f"总问题数: {total}")
    print(f"回答正确: {correct}")
    print(f"回答错误: {total - correct}")
    print(f"准确率: {accuracy:.1f}%")

    if accuracy >= 80:
        print("\n✅ 测试通过！系统能够准确回答大部分政策问题。")
    elif accuracy >= 60:
        print("\n⚠️ 测试部分通过。系统基本能回答政策问题，但准确率有待提高。")
    else:
        print("\n❌ 测试未通过。系统回答准确率较低，需要优化。")


if __name__ == "__main__":
    test_policy_qa()