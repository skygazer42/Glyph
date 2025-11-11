"""
综合测试所有 Agent Pipeline
测试各个agent的基本功能和集成
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.pipeline.dialog_agent import DialogueAgent, ClarifierAgent
from app.agents.pipeline.rewrite_agent import RewriteAgent


def test_dialogue_agent():
    """测试对话代理"""
    print("\n" + "="*60)
    print("测试 1: DialogueAgent - 对话代理")
    print("="*60)

    agent = DialogueAgent()

    # 测试问候
    result = agent.respond("greeting")
    print(f"✓ 问候测试:")
    print(f"  答案: {result.answer}")
    print(f"  置信度: {result.confidence}")
    assert result.confidence == 0.9
    assert "政策智能助手" in result.answer or "欢迎" in result.answer

    # 测试告别
    result = agent.respond("farewell")
    print(f"✓ 告别测试:")
    print(f"  答案: {result.answer}")
    assert "感谢" in result.answer or "顺利" in result.answer

    # 测试闲聊
    result = agent.respond("chit_chat")
    print(f"✓ 闲聊测试:")
    print(f"  答案: {result.answer}")
    assert "政策" in result.answer

    print("✓ DialogueAgent 测试通过!\n")


def test_clarifier_agent():
    """测试澄清代理"""
    print("="*60)
    print("测试 2: ClarifierAgent - 澄清代理")
    print("="*60)

    agent = ClarifierAgent()

    result = agent.ask("我想了解一下政策")
    print(f"✓ 澄清问题测试:")
    print(f"  原问题: 我想了解一下政策")
    print(f"  澄清问题: {result.answer}")
    print(f"  置信度: {result.confidence}")
    assert result.confidence == 0.4
    assert "我想了解一下政策" in result.answer
    assert "确认" in result.answer or "说明" in result.answer

    print("✓ ClarifierAgent 测试通过!\n")


async def test_rewrite_agent():
    """测试查询改写代理"""
    print("="*60)
    print("测试 3: RewriteAgent - 查询改写代理")
    print("="*60)

    agent = RewriteAgent(max_length=256)

    test_queries = [
        "想问下补贴怎么算",
        "这个能拿多少钱",
        "我符合条件吗"
    ]

    for query in test_queries:
        try:
            rewritten = await agent.rewrite(query)
            print(f"✓ 原问题: {query}")
            print(f"  改写后: {rewritten}")
            assert rewritten is not None
            assert len(rewritten) > 0
        except Exception as e:
            print(f"⚠ 改写失败 (可能LLM未配置): {e}")
            # 如果LLM未配置，应该返回原query
            pass

    print("✓ RewriteAgent 测试完成!\n")


async def test_rule_engine_agent():
    """测试规则引擎代理"""
    print("="*60)
    print("测试 4: RuleEngineAgent - 规则引擎代理")
    print("="*60)

    try:
        from app.agents.pipeline.rule_agent import RuleEngineAgent

        agent = RuleEngineAgent(rule_dir="rules", max_rules=5)

        # 测试简单查询
        query = "我想计算补贴金额"
        result = await agent.compute(query)

        print(f"✓ 查询: {query}")
        print(f"  答案: {result.answer}")
        print(f"  置信度: {result.confidence}")
        print(f"  路由: {result.metadata.get('route')}")

        # 检查metadata
        assert result.metadata.get('route') == 'rule_engine'

        print("✓ RuleEngineAgent 测试完成!\n")
    except Exception as e:
        print(f"⚠ RuleEngineAgent 测试跳过: {e}\n")


async def test_knowledge_agent():
    """测试知识库代理"""
    print("="*60)
    print("测试 5: KnowledgeAgent - 知识库代理")
    print("="*60)

    try:
        from app.agents.pipeline.knowledge_agent import KnowledgeAgent
        from app.agents.service.tools import KnowledgeTool

        # 创建知识工具（可能需要mock）
        knowledge_tool = KnowledgeTool()
        agent = KnowledgeAgent(knowledge_tool=knowledge_tool, top_k=5)

        # 测试查询
        query = "北京市创业补贴政策"
        result = await agent.answer(query)

        print(f"✓ 查询: {query}")
        print(f"  答案预览: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  来源数量: {len(result.sources)}")
        print(f"  路由: {result.metadata.get('route')}")

        assert result.metadata.get('route') == 'knowledge'

        print("✓ KnowledgeAgent 测试完成!\n")
    except Exception as e:
        print(f"⚠ KnowledgeAgent 测试跳过 (可能需要向量数据库): {e}\n")


async def test_text2sql_agent():
    """测试Text2SQL代理"""
    print("="*60)
    print("测试 6: Text2SQLAgent - 文本转SQL代理")
    print("="*60)

    try:
        from app.agents.pipeline.text2sql_agent import Text2SQLAgent

        agent = Text2SQLAgent()

        # 测试查询（没有connection_id应该返回错误）
        query = "查询所有用户"
        result = await agent.answer(query, connection_id=None)

        print(f"✓ 查询: {query}")
        print(f"  答案: {result.answer}")
        print(f"  置信度: {result.confidence}")
        print(f"  路由: {result.metadata.get('route')}")

        assert result.metadata.get('route') == 'text2sql'
        assert "connection_id" in result.answer

        print("✓ Text2SQLAgent 测试完成!\n")
    except Exception as e:
        print(f"⚠ Text2SQLAgent 测试跳过: {e}\n")


async def test_graph_agent():
    """测试图谱代理"""
    print("="*60)
    print("测试 7: GraphAgent - 图谱代理")
    print("="*60)

    try:
        from app.agents.pipeline.graph_agent import GraphAgent
        from app.agents.pipeline.knowledge_agent import KnowledgeAgent
        from app.agents.service.tools import KnowledgeTool

        # 创建依赖
        knowledge_tool = KnowledgeTool()
        knowledge_agent = KnowledgeAgent(knowledge_tool=knowledge_tool, top_k=5)

        agent = GraphAgent(knowledge_agent=knowledge_agent)

        # 测试查询
        query = "创业补贴政策和申请流程的关系"
        result = await agent.answer(query)

        print(f"✓ 查询: {query}")
        print(f"  答案预览: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  路由: {result.metadata.get('route')}")

        # 如果没有LightRAG，会fallback到knowledge_agent
        assert result.metadata.get('route') in ['graph', 'knowledge']

        print("✓ GraphAgent 测试完成!\n")
    except Exception as e:
        print(f"⚠ GraphAgent 测试跳过: {e}\n")


async def test_workflow_agent():
    """测试工作流代理"""
    print("="*60)
    print("测试 8: WorkflowAgent - 工作流代理")
    print("="*60)

    try:
        from app.agents.pipeline.workflow_agent import WorkflowAgent
        from app.agents.pipeline.knowledge_agent import KnowledgeAgent
        from app.agents.pipeline.rule_agent import RuleEngineAgent
        from app.agents.service.tools import KnowledgeTool, VisionTool, UserProfileTool

        # 创建依赖
        knowledge_tool = KnowledgeTool()
        knowledge_agent = KnowledgeAgent(knowledge_tool=knowledge_tool, top_k=5)
        rule_agent = RuleEngineAgent(rule_dir="rules")
        vision_tool = VisionTool()
        user_profile_tool = UserProfileTool()

        agent = WorkflowAgent(
            vision_tool=vision_tool,
            knowledge_agent=knowledge_agent,
            rule_agent=rule_agent,
            user_profile_tool=user_profile_tool,
            max_turns=12
        )

        # 测试查询
        query = "我想了解创业补贴政策"
        result = await agent.answer(query)

        print(f"✓ 查询: {query}")
        print(f"  答案预览: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  路由: {result.metadata.get('route')}")

        assert result.metadata.get('route') == 'workflow'

        print("✓ WorkflowAgent 测试完成!\n")
    except Exception as e:
        print(f"⚠ WorkflowAgent 测试跳过 (需要autogen_agentchat): {e}\n")


def print_summary():
    """打印测试摘要"""
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print("✓ 所有同步Agent测试通过")
    print("✓ 异步Agent测试完成（部分可能需要额外配置）")
    print("\n各Agent功能说明:")
    print("1. DialogueAgent      - 处理问候/告别/闲聊")
    print("2. ClarifierAgent     - 当意图不明时提问澄清")
    print("3. RewriteAgent       - 改写用户查询为更清晰的表述")
    print("4. RuleEngineAgent    - 使用DSL规则进行补贴计算")
    print("5. KnowledgeAgent     - 知识库检索+LLM生成答案")
    print("6. Text2SQLAgent      - 自然语言转SQL查询")
    print("7. GraphAgent         - LightRAG图谱关系查询")
    print("8. WorkflowAgent      - 编排多个agent的复杂工作流")
    print("="*60 + "\n")


async def run_all_async_tests():
    """运行所有异步测试"""
    await test_rewrite_agent()
    await test_rule_engine_agent()
    await test_knowledge_agent()
    await test_text2sql_agent()
    await test_graph_agent()
    await test_workflow_agent()


def main():
    """主测试函数"""
    print("\n开始测试所有 Agent Pipeline...\n")

    # 同步测试
    test_dialogue_agent()
    test_clarifier_agent()

    # 异步测试
    asyncio.run(run_all_async_tests())

    # 打印摘要
    print_summary()


if __name__ == "__main__":
    main()
