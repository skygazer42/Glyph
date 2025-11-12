#!/usr/bin/env python3
"""
综合测试 - Agent 完整流程
测试 Intent Router, Text2SQL, GraphRetriever, VectorRetriever, Answer Generator
"""
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.packs.intent_router.node import IntentRouterAgent
from app.agents.packs.graph_retriever.node import GraphRetrieverAgent
from app.agents.packs.vector_retriever.node import VectorRetrieverAgent
from app.agents.packs.answer_generator.node import AnswerGeneratorAgent
from app.agents.packs.chat_agent.node import ChatAgent

print("=" * 80)
print("Agent 完整流程测试")
print("=" * 80)

async def test_intent_router():
    """测试意图路由"""
    print("\n" + "=" * 80)
    print("1. 测试 Intent Router (意图路由)")
    print("=" * 80)

    try:
        agent = IntentRouterAgent()
        print("✅ IntentRouterAgent 初始化成功\n")

        test_queries = [
            "济南市有哪些汽车补贴政策？",
            "数据库中有多少条政策记录？",
            "新能源汽车补贴的申请条件是什么？"
        ]

        for idx, query in enumerate(test_queries, 1):
            print(f"📝 查询 {idx}: {query}")
            result = await agent.process(query)

            if isinstance(result, dict):
                intent = result.get("intent", "unknown")
                confidence = result.get("confidence", 0)
                print(f"   ➤ 意图: {intent}")
                print(f"   ➤ 置信度: {confidence:.2f}")
                if "reasoning" in result:
                    print(f"   ➤ 推理: {result['reasoning'][:100]}...")
            print()

        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_graph_retriever():
    """测试图谱检索"""
    print("\n" + "=" * 80)
    print("2. 测试 GraphRetriever (图谱检索)")
    print("=" * 80)

    try:
        agent = GraphRetrieverAgent()
        print("✅ GraphRetrieverAgent 初始化成功\n")

        test_queries = [
            "济南市商务局负责哪些政策？",
            "新能源汽车补贴和谁相关？"
        ]

        for idx, query in enumerate(test_queries, 1):
            print(f"📝 查询 {idx}: {query}")
            result = await agent.query(query, mode="hybrid")

            if result:
                print(f"   ➤ 检索到内容: {result[:200]}...")
            else:
                print(f"   ➤ 未找到相关内容")
            print()

        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_vector_retriever():
    """测试向量检索"""
    print("\n" + "=" * 80)
    print("3. 测试 VectorRetriever (向量检索)")
    print("=" * 80)

    try:
        agent = VectorRetrieverAgent()
        print("✅ VectorRetrieverAgent 初始化成功\n")

        query = "新能源汽车补贴政策"
        print(f"📝 查询: {query}")

        results = await agent.retrieve(query, top_k=3)

        if results:
            print(f"   ➤ 找到 {len(results)} 个相关文档:")
            for i, doc in enumerate(results[:2], 1):
                if hasattr(doc, 'title'):
                    print(f"      {i}. {doc.title}")
                elif isinstance(doc, dict):
                    print(f"      {i}. {doc.get('title', 'N/A')}")
        else:
            print(f"   ➤ 未找到相关文档")
        print()

        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_answer_generator():
    """测试答案生成"""
    print("\n" + "=" * 80)
    print("4. 测试 Answer Generator (答案生成)")
    print("=" * 80)

    try:
        agent = AnswerGeneratorAgent()
        print("✅ AnswerGeneratorAgent 初始化成功\n")

        query = "新能源汽车补贴的金额是多少？"
        context = "济南市新能源汽车消费补贴政策规定，购买新能源汽车的个人可以申请最高8000元的补贴。"

        print(f"📝 问题: {query}")
        print(f"📄 上下文: {context}\n")

        answer = await agent.generate(query, context)

        if answer:
            print(f"💬 生成答案:")
            print(f"   {answer[:300]}...")
        else:
            print(f"   ➤ 未能生成答案")
        print()

        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_chat_agent():
    """测试完整的聊天 Agent"""
    print("\n" + "=" * 80)
    print("5. 测试 ChatAgent (完整流程)")
    print("=" * 80)

    try:
        agent = ChatAgent()
        print("✅ ChatAgent 初始化成功\n")

        test_queries = [
            "济南市有哪些汽车补贴政策？",
            "新能源汽车补贴的申请条件是什么？"
        ]

        for idx, query in enumerate(test_queries, 1):
            print(f"📝 查询 {idx}: {query}")
            print("-" * 80)

            response = await agent.chat(query)

            if response:
                if isinstance(response, dict):
                    answer = response.get('answer', response.get('response', str(response)))
                else:
                    answer = str(response)

                print(f"💬 回答:")
                print(f"   {answer[:400]}...")
            else:
                print(f"   ➤ 未能获取回答")
            print()

        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """运行所有测试"""
    results = {}

    # 测试各个组件
    results['intent_router'] = await test_intent_router()
    results['graph_retriever'] = await test_graph_retriever()
    results['vector_retriever'] = await test_vector_retriever()
    results['answer_generator'] = await test_answer_generator()
    results['chat_agent'] = await test_chat_agent()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:20s}: {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
