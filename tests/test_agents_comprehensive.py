"""
全面的Agent测试 - 包括逻辑测试和实际问题场景测试
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import json

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("\n" + "="*70)
print("全面 Agent Pipeline 测试")
print("="*70 + "\n")


# ============================================================================
# 第一部分：基础Agent逻辑测试
# ============================================================================

def test_dialogue_agent_all_intents():
    """测试DialogAgent所有意图"""
    print("\n" + "="*70)
    print("测试 1: DialogueAgent - 所有意图类型")
    print("="*70)

    try:
        from app.agents.pipeline.dialog_agent import DialogueAgent

        agent = DialogueAgent()
        intents = ["greeting", "farewell", "chit_chat"]

        for intent in intents:
            result = agent.respond(intent)
            print(f"\n✓ 意图: {intent}")
            print(f"  回答: {result.answer}")
            print(f"  置信度: {result.confidence}")
            print(f"  元数据: {result.metadata}")
            assert result.confidence > 0.5
            assert result.answer is not None

        print("\n✓ DialogueAgent 所有意图测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ DialogueAgent 测试失败: {e}\n")
        return False


def test_clarifier_agent_multiple_queries():
    """测试ClarifierAgent多个模糊问题"""
    print("="*70)
    print("测试 2: ClarifierAgent - 多个模糊问题")
    print("="*70)

    try:
        from app.agents.pipeline.dialog_agent import ClarifierAgent

        agent = ClarifierAgent()
        queries = [
            "我想了解一下",
            "这个怎么弄",
            "能告诉我吗",
            "想问下"
        ]

        for query in queries:
            result = agent.ask(query)
            print(f"\n✓ 原问题: {query}")
            print(f"  澄清问题: {result.answer[:80]}...")
            print(f"  置信度: {result.confidence}")
            assert result.confidence == 0.4
            assert query in result.answer

        print("\n✓ ClarifierAgent 多问题测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ ClarifierAgent 测试失败: {e}\n")
        return False


async def test_rewrite_agent_various_queries():
    """测试RewriteAgent多种查询类型"""
    print("="*70)
    print("测试 3: RewriteAgent - 多种查询类型")
    print("="*70)

    try:
        from app.agents.pipeline.rewrite_agent import RewriteAgent

        agent = RewriteAgent(max_length=256)
        queries = [
            "想问下补贴怎么算",
            "我符合条件吗",
            "这个政策啥时候开始的",
            "能拿多少钱",
            "需要准备啥材料"
        ]

        for query in queries:
            try:
                rewritten = await agent.rewrite(query)
                print(f"\n✓ 原查询: {query}")
                print(f"  改写后: {rewritten}")
                assert rewritten is not None
                assert len(rewritten) > 0
            except Exception as e:
                print(f"\n⚠ 查询改写失败: {query} - {e}")

        print("\n✓ RewriteAgent 多查询测试完成!\n")
        return True
    except Exception as e:
        print(f"\n✗ RewriteAgent 测试失败: {e}\n")
        return False


async def test_rule_engine_agent_logic():
    """测试RuleEngineAgent规则逻辑"""
    print("="*70)
    print("测试 4: RuleEngineAgent - 规则引擎逻辑")
    print("="*70)

    try:
        from app.agents.pipeline.rule_agent import RuleEngineAgent

        agent = RuleEngineAgent(rule_dir="rules", max_rules=5)

        # 测试规则列表
        rules = agent.engine.list_rules()
        print(f"\n✓ 加载的规则数量: {len(rules)}")

        for rule in rules[:3]:  # 显示前3个规则
            print(f"\n  规则ID: {rule.get('rule_id')}")
            print(f"  标题: {rule.get('title')}")
            print(f"  是否激活: {rule.get('is_active')}")

        # 测试规则查询
        test_queries = [
            "北京市家电以旧换新补贴怎么算",
            "我想计算补贴金额",
            "能帮我算一下能拿多少钱吗"
        ]

        for query in test_queries:
            result = await agent.compute(query)
            print(f"\n✓ 查询: {query}")
            print(f"  答案预览: {result.answer[:100]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  路由: {result.metadata.get('route')}")
            assert result.metadata.get('route') == 'rule_engine'

        print("\n✓ RuleEngineAgent 测试完成!\n")
        return True
    except Exception as e:
        print(f"\n✗ RuleEngineAgent 测试失败: {e}\n")
        return False


async def test_knowledge_agent_logic():
    """测试KnowledgeAgent知识检索逻辑"""
    print("="*70)
    print("测试 5: KnowledgeAgent - 知识检索逻辑")
    print("="*70)

    try:
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
            "家电以旧换新申请条件",
            "小微企业税收优惠政策"
        ]

        for query in test_queries:
            result = await agent.answer(query)
            print(f"\n✓ 查询: {query}")
            print(f"  答案预览: {result.answer[:100]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  来源数量: {len(result.sources)}")
            print(f"  来源类型: {result.metadata.get('origin')}")
            assert result.metadata.get('route') == 'knowledge'

        print("\n✓ KnowledgeAgent 测试完成!\n")
        return True
    except Exception as e:
        print(f"\n✗ KnowledgeAgent 测试跳过: {e}\n")
        return False


async def test_text2sql_agent_logic():
    """测试Text2SQLAgent逻辑"""
    print("="*70)
    print("测试 6: Text2SQLAgent - SQL生成逻辑")
    print("="*70)

    try:
        from app.agents.pipeline.text2sql_agent import Text2SQLAgent

        agent = Text2SQLAgent()

        # 测试无connection_id的情况
        result = await agent.answer("查询所有用户", connection_id=None)
        print(f"\n✓ 无connection_id测试")
        print(f"  答案: {result.answer}")
        print(f"  置信度: {result.confidence}")
        assert "connection_id" in result.answer

        print("\n✓ Text2SQLAgent 基础测试完成!\n")
        return True
    except Exception as e:
        print(f"\n✗ Text2SQLAgent 测试失败: {e}\n")
        return False


async def test_graph_agent_logic():
    """测试GraphAgent图谱逻辑"""
    print("="*70)
    print("测试 7: GraphAgent - 图谱关系查询")
    print("="*70)

    try:
        from app.agents.pipeline.graph_agent import GraphAgent
        from app.agents.pipeline.knowledge_agent import KnowledgeAgent
        from app.agents.service.tools import KnowledgeTool

        knowledge_tool = KnowledgeTool()
        knowledge_agent = KnowledgeAgent(knowledge_tool=knowledge_tool, top_k=5)
        agent = GraphAgent(knowledge_agent=knowledge_agent)

        test_queries = [
            "创业补贴和税收优惠的关系",
            "家电以旧换新政策的实施部门",
            "小微企业补贴的申请流程"
        ]

        for query in test_queries:
            result = await agent.answer(query)
            print(f"\n✓ 查询: {query}")
            print(f"  答案预览: {result.answer[:100]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  路由: {result.metadata.get('route')}")

        print("\n✓ GraphAgent 测试完成!\n")
        return True
    except Exception as e:
        print(f"\n✗ GraphAgent 测试跳过: {e}\n")
        return False


# ============================================================================
# 第二部分：实际问题场景测试
# ============================================================================

async def test_scenario_greeting_farewell():
    """场景1: 问候和告别"""
    print("\n" + "="*70)
    print("场景测试 1: 问候和告别场景")
    print("="*70)

    try:
        from app.agents.pipeline.dialog_agent import DialogueAgent

        agent = DialogueAgent()

        conversation = [
            ("你好", "greeting"),
            ("再见", "farewell")
        ]

        for query, intent in conversation:
            result = agent.respond(intent)
            print(f"\n用户: {query}")
            print(f"助手: {result.answer}")

        print("\n✓ 问候告别场景测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ 场景测试失败: {e}\n")
        return False


async def test_scenario_ambiguous_query():
    """场景2: 模糊查询需要澄清"""
    print("="*70)
    print("场景测试 2: 模糊查询澄清场景")
    print("="*70)

    try:
        from app.agents.pipeline.dialog_agent import ClarifierAgent
        from app.agents.pipeline.rewrite_agent import RewriteAgent

        clarifier = ClarifierAgent()
        rewriter = RewriteAgent()

        # 模糊问题
        ambiguous_query = "我想了解一下政策"
        print(f"\n用户: {ambiguous_query}")

        # 澄清
        clarification = clarifier.ask(ambiguous_query)
        print(f"助手: {clarification.answer}")

        # 假设用户提供更多信息
        clarified_query = "我想了解北京市创业补贴政策"
        print(f"\n用户: {clarified_query}")

        # 改写
        rewritten = await rewriter.rewrite(clarified_query)
        print(f"系统改写: {rewritten}")

        print("\n✓ 模糊查询澄清场景测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ 场景测试失败: {e}\n")
        return False


async def test_scenario_subsidy_calculation():
    """场景3: 补贴计算场景"""
    print("="*70)
    print("场景测试 3: 补贴计算场景")
    print("="*70)

    try:
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

        print("\n✓ 补贴计算场景测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ 场景测试失败: {e}\n")
        return False


async def test_scenario_policy_inquiry():
    """场景4: 政策咨询场景"""
    print("="*70)
    print("场景测试 4: 政策咨询场景")
    print("="*70)

    try:
        from app.agents.pipeline.knowledge_agent import KnowledgeAgent
        from app.agents.pipeline.rewrite_agent import RewriteAgent
        from app.agents.service.tools import KnowledgeTool, WebSearchTool

        rewriter = RewriteAgent()
        knowledge_tool = KnowledgeTool()
        web_search_tool = WebSearchTool()
        knowledge_agent = KnowledgeAgent(
            knowledge_tool=knowledge_tool,
            top_k=5,
            web_search_tool=web_search_tool
        )

        # 用户问题
        user_query = "小微企业有什么税收优惠政策"
        print(f"\n用户: {user_query}")

        # 改写问题
        rewritten = await rewriter.rewrite(user_query)
        print(f"系统改写: {rewritten}")

        # 知识检索
        result = await knowledge_agent.answer(rewritten)
        print(f"\n助手: {result.answer[:200]}...")
        print(f"置信度: {result.confidence}")
        print(f"来源: {result.metadata.get('origin')}")

        print("\n✓ 政策咨询场景测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ 场景测试跳过: {e}\n")
        return False


async def test_scenario_multi_turn_conversation():
    """场景5: 多轮对话场景"""
    print("="*70)
    print("场景测试 5: 多轮对话场景")
    print("="*70)

    try:
        from app.agents.pipeline.dialog_agent import DialogueAgent
        from app.agents.pipeline.rewrite_agent import RewriteAgent
        from app.agents.pipeline.rule_agent import RuleEngineAgent

        dialogue_agent = DialogueAgent()
        rewriter = RewriteAgent()
        rule_agent = RuleEngineAgent(rule_dir="rules")

        conversation_flow = [
            ("你好", "greeting", dialogue_agent),
            ("我想了解家电以旧换新补贴", "policy_query", rule_agent),
            ("需要什么条件", "policy_query", rule_agent),
            ("谢谢", "farewell", dialogue_agent),
        ]

        print("\n开始多轮对话:")
        for turn, (query, intent_type, agent) in enumerate(conversation_flow, 1):
            print(f"\n第{turn}轮:")
            print(f"用户: {query}")

            if intent_type in ["greeting", "farewell"]:
                result = agent.respond(intent_type)
                print(f"助手: {result.answer}")
            else:
                rewritten = await rewriter.rewrite(query)
                result = await agent.compute(rewritten)
                print(f"助手: {result.answer[:100]}...")

        print("\n✓ 多轮对话场景测试通过!\n")
        return True
    except Exception as e:
        print(f"\n✗ 场景测试失败: {e}\n")
        return False


# ============================================================================
# 测试统计和报告
# ============================================================================

def print_test_summary(results: List[tuple]):
    """打印测试摘要"""
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\n通过率: {passed}/{total} ({percentage:.1f}%)\n")

    print("详细结果:")
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print("\n" + "="*70)


def print_agent_capabilities():
    """打印Agent能力矩阵"""
    print("\n" + "="*70)
    print("Agent 能力矩阵")
    print("="*70)

    capabilities = {
        "DialogueAgent": {
            "功能": "问候/告别/闲聊",
            "输入": "意图标签",
            "输出": "模板化响应",
            "依赖": "无",
            "适用场景": "对话开始/结束/小谈"
        },
        "ClarifierAgent": {
            "功能": "澄清模糊问题",
            "输入": "不明确的查询",
            "输出": "澄清性问题",
            "依赖": "无",
            "适用场景": "意图不明确时"
        },
        "RewriteAgent": {
            "功能": "查询改写",
            "输入": "口语化查询",
            "输出": "专业化表述",
            "依赖": "LLM",
            "适用场景": "查询预处理"
        },
        "RuleEngineAgent": {
            "功能": "DSL规则计算",
            "输入": "计算类查询",
            "输出": "计算结果",
            "依赖": "规则库",
            "适用场景": "补贴/折扣计算"
        },
        "KnowledgeAgent": {
            "功能": "知识检索+生成",
            "输入": "知识查询",
            "输出": "综合答案",
            "依赖": "向量库+LLM+联网",
            "适用场景": "政策咨询"
        },
        "Text2SQLAgent": {
            "功能": "自然语言转SQL",
            "输入": "数据查询",
            "输出": "SQL结果",
            "依赖": "数据库连接",
            "适用场景": "结构化数据查询"
        },
        "GraphAgent": {
            "功能": "图谱关系查询",
            "输入": "关系查询",
            "输出": "实体关系",
            "依赖": "LightRAG",
            "适用场景": "关系探索"
        },
        "WorkflowAgent": {
            "功能": "复杂工作流编排",
            "输入": "复杂任务",
            "输出": "综合结果",
            "依赖": "多个Agent+工具",
            "适用场景": "多模态任务"
        }
    }

    for agent_name, info in capabilities.items():
        print(f"\n{agent_name}:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    print("\n" + "="*70)


async def run_all_tests():
    """运行所有测试"""
    results = []

    print("\n" + "#"*70)
    print("# 第一部分: Agent 逻辑测试")
    print("#"*70)

    # 基础逻辑测试
    results.append(("DialogueAgent - 所有意图", test_dialogue_agent_all_intents()))
    results.append(("ClarifierAgent - 多问题", test_clarifier_agent_multiple_queries()))
    results.append(("RewriteAgent - 多查询", await test_rewrite_agent_various_queries()))
    results.append(("RuleEngineAgent - 规则逻辑", await test_rule_engine_agent_logic()))
    results.append(("KnowledgeAgent - 知识检索", await test_knowledge_agent_logic()))
    results.append(("Text2SQLAgent - SQL逻辑", await test_text2sql_agent_logic()))
    results.append(("GraphAgent - 图谱逻辑", await test_graph_agent_logic()))

    print("\n" + "#"*70)
    print("# 第二部分: 实际场景测试")
    print("#"*70)

    # 场景测试
    results.append(("场景1: 问候告别", await test_scenario_greeting_farewell()))
    results.append(("场景2: 模糊查询", await test_scenario_ambiguous_query()))
    results.append(("场景3: 补贴计算", await test_scenario_subsidy_calculation()))
    results.append(("场景4: 政策咨询", await test_scenario_policy_inquiry()))
    results.append(("场景5: 多轮对话", await test_scenario_multi_turn_conversation()))

    # 打印摘要
    print_test_summary(results)
    print_agent_capabilities()

    return results


def main():
    """主函数"""
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
