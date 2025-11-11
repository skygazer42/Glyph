"""
pytest测试用例 - 针对RuleEngine和Knowledge的专项测试
"""
import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_rule_engine_agent():
    """测试RuleEngineAgent的规则引擎流程"""
    from app.agents.pipeline.rule_agent import RuleEngineAgent

    agent = RuleEngineAgent(rule_dir="rules", max_rules=5)

    # 测试1: 检查规则加载
    rules = agent.engine.list_rules()
    print(f"\n✓ 加载的规则数量: {len(rules)}")
    assert len(rules) > 0, "应该至少有一个规则被加载"

    # 测试2: 测试规则信息获取
    for rule in rules[:3]:
        rule_id = rule.get('rule_id')
        rule_info = agent.engine.get_rule_info(rule_id)
        print(f"\n规则ID: {rule_id}")
        print(f"  标题: {rule.get('title')}")
        print(f"  是否激活: {rule.get('is_active')}")
        print(f"  输入参数: {rule_info.get('inputs', [])}")
        assert rule_info is not None, f"规则 {rule_id} 的信息应该存在"

    # 测试3: 测试规则计算
    test_queries = [
        "北京市家电以旧换新补贴怎么算",
        "我想计算补贴金额"
    ]

    for query in test_queries:
        print(f"\n测试查询: {query}")
        result = await agent.compute(query)
        print(f"  答案: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  路由: {result.metadata.get('route')}")
        print(f"  规则ID: {result.metadata.get('rule_id')}")

        assert result is not None, "应该返回结果"
        assert result.metadata.get('route') == 'rule_engine', "路由应该是rule_engine"

        # 检查是否有PolicyEngine错误
        if 'engine_result' in result.metadata:
            engine_result = result.metadata['engine_result']
            print(f"  引擎状态: {engine_result.get('status')}")
            if engine_result.get('status') == 'ERROR':
                print(f"  ⚠ 错误信息: {engine_result.get('message')}")
                pytest.fail(f"RuleEngine执行失败: {engine_result.get('message')}")

    print("\n✅ RuleEngineAgent测试通过!")


@pytest.mark.asyncio
async def test_knowledge_agent():
    """测试KnowledgeAgent的知识检索流程"""
    from app.agents.pipeline.knowledge_agent import KnowledgeAgent
    from app.agents.service.tools import KnowledgeTool, WebSearchTool

    knowledge_tool = KnowledgeTool()
    web_search_tool = WebSearchTool()
    agent = KnowledgeAgent(
        knowledge_tool=knowledge_tool,
        top_k=5,
        web_search_tool=web_search_tool
    )

    test_queries = [
        "北京市创业补贴政策",
        "小微企业税收优惠"
    ]

    for query in test_queries:
        print(f"\n测试查询: {query}")

        # 调用agent
        result = await agent.answer(query)

        print(f"  答案: {result.answer[:150]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  来源数量: {len(result.sources)}")
        print(f"  来源类型: {result.metadata.get('origin')}")
        print(f"  路由: {result.metadata.get('route')}")

        # 基本断言
        assert result is not None, "应该返回结果"
        assert result.answer is not None, "应该有答案"
        assert result.metadata.get('route') == 'knowledge', "路由应该是knowledge"

        # 检查sources类型
        print(f"  Sources类型: {type(result.sources)}")
        if result.sources:
            print(f"  第一个source类型: {type(result.sources[0])}")
            print(f"  第一个source: {result.sources[0]}")

        # 验证没有Pydantic错误
        # 如果sources不为空，检查是否是正确的类型
        if result.sources:
            from app.models.base import PolicyDocument
            for idx, source in enumerate(result.sources):
                assert isinstance(source, PolicyDocument), \
                    f"Source {idx} 应该是PolicyDocument类型，实际是 {type(source)}"

    print("\n✅ KnowledgeAgent测试通过!")


@pytest.mark.asyncio
async def test_scenario_subsidy_calculation():
    """场景3: 补贴计算场景"""
    from app.agents.pipeline.rule_agent import RuleEngineAgent
    from app.agents.pipeline.rewrite_agent import RewriteAgent

    rewriter = RewriteAgent()
    rule_agent = RuleEngineAgent(rule_dir="rules")

    # 用户问题
    user_query = "我买了一台旧冰箱换新的，能拿多少补贴"
    print(f"\n用户: {user_query}")

    # 改写问题
    rewritten = await rewriter.rewrite(user_query)
    print(f"系统改写: {rewritten}")

    # 规则计算
    result = await rule_agent.compute(rewritten)
    print(f"\n助手: {result.answer}")
    print(f"置信度: {result.confidence}")

    assert result is not None, "应该返回结果"
    assert result.metadata.get('route') == 'rule_engine', "路由应该是rule_engine"

    # 检查引擎执行状态
    if 'engine_result' in result.metadata:
        engine_result = result.metadata['engine_result']
        if engine_result.get('status') == 'ERROR':
            pytest.fail(f"场景3失败: {engine_result.get('message')}")

    print("\n✅ 场景3: 补贴计算场景测试通过!")


@pytest.mark.asyncio
async def test_scenario_multi_turn():
    """场景5: 多轮对话场景"""
    from app.agents.pipeline.dialog_agent import DialogueAgent
    from app.agents.pipeline.rewrite_agent import RewriteAgent
    from app.agents.pipeline.rule_agent import RuleEngineAgent

    dialogue_agent = DialogueAgent()
    rewriter = RewriteAgent()
    rule_agent = RuleEngineAgent(rule_dir="rules")

    print("\n开始多轮对话:")

    # 第1轮: 问候
    print(f"\n第1轮:")
    print(f"用户: 你好")
    result = dialogue_agent.respond("greeting")
    print(f"助手: {result.answer}")
    assert result.confidence == 0.9

    # 第2轮: 政策查询
    print(f"\n第2轮:")
    query = "我想了解家电以旧换新补贴"
    print(f"用户: {query}")
    rewritten = await rewriter.rewrite(query)
    print(f"系统改写: {rewritten}")
    result = await rule_agent.compute(rewritten)
    print(f"助手: {result.answer[:100]}...")

    # 检查引擎执行状态
    if 'engine_result' in result.metadata:
        engine_result = result.metadata['engine_result']
        if engine_result.get('status') == 'ERROR':
            pytest.fail(f"场景5第2轮失败: {engine_result.get('message')}")

    # 第3轮: 告别
    print(f"\n第3轮:")
    print(f"用户: 谢谢")
    result = dialogue_agent.respond("farewell")
    print(f"助手: {result.answer}")
    assert result.confidence == 0.9

    print("\n✅ 场景5: 多轮对话场景测试通过!")


if __name__ == "__main__":
    # 直接运行测试
    import asyncio

    async def run_tests():
        print("="*70)
        print("开始针对性测试")
        print("="*70)

        try:
            print("\n[测试1] RuleEngineAgent")
            await test_rule_engine_agent()
        except Exception as e:
            print(f"\n❌ RuleEngineAgent测试失败: {e}")

        try:
            print("\n[测试2] KnowledgeAgent")
            await test_knowledge_agent()
        except Exception as e:
            print(f"\n❌ KnowledgeAgent测试失败: {e}")

        try:
            print("\n[测试3] 场景3: 补贴计算")
            await test_scenario_subsidy_calculation()
        except Exception as e:
            print(f"\n❌ 场景3测试失败: {e}")

        try:
            print("\n[测试4] 场景5: 多轮对话")
            await test_scenario_multi_turn()
        except Exception as e:
            print(f"\n❌ 场景5测试失败: {e}")

    asyncio.run(run_tests())
