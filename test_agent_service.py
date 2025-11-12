#!/usr/bin/env python3
"""
通过 AgentService 测试完整的 Agent 流程
"""
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.service.agent_service import AgentService
from app.knowledge.service import KnowledgeService

print("=" * 80)
print("AgentService 完整流程测试")
print("=" * 80)

async def test_agent_service():
    """测试 AgentService"""
    try:
        # 初始化服务
        print("\n📦 初始化 AgentService...")
        knowledge_service = KnowledgeService()
        agent_service = AgentService(knowledge_service=knowledge_service)
        print("✅ AgentService 初始化成功！\n")

        # 测试不同类型的查询
        test_queries = [
            {
                "query": "济南市有哪些汽车补贴政策？",
                "description": "知识检索查询"
            },
            {
                "query": "数据库中有多少条政策记录？",
                "description": "SQL查询"
            },
            {
                "query": "新能源汽车补贴的申请条件是什么？",
                "description": "政策详情查询"
            },
            {
                "query": "济南市商务局负责哪些政策？",
                "description": "图谱查询"
            }
        ]

        for idx, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            desc = test_case["description"]

            print("=" * 80)
            print(f"测试 {idx}/{len(test_queries)}: {desc}")
            print("=" * 80)
            print(f"📝 问题: {query}\n")

            try:
                # 调用 process_query
                result = await agent_service.process_query(
                    query=query,
                    session_id=f"test_session_{idx}"
                )

                print(f"✅ 处理成功")
                print(f"💬 回答:")
                print(f"   {result.answer[:500]}...")
                print(f"\n📊 元数据:")
                if result.metadata:
                    print(f"   - 路由: {result.metadata.get('route', 'N/A')}")
                    print(f"   - 意图: {result.metadata.get('intent', 'N/A')}")
                    print(f"   - 置信度: {result.confidence:.2f}")
                print()

            except Exception as e:
                print(f"❌ 处理失败: {e}")
                import traceback
                traceback.print_exc()
                print()

        print("=" * 80)
        print("测试完成")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_service())
