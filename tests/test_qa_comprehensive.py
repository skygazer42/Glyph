"""
大规模问答测试 - 模拟真实用户场景
测试所有Agent的综合能力
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, List, Any
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("\n" + "="*80)
print("大规模 Agent 问答测试")
print("="*80 + "\n")


class QATestSuite:
    """问答测试套件"""

    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.total_time = 0

    def add_result(self, test_name: str, query: str, response: str,
                   agent_used: str, confidence: float, time_taken: float,
                   passed: bool, notes: str = ""):
        """记录测试结果"""
        self.results.append({
            "test_name": test_name,
            "query": query,
            "response": response,
            "agent_used": agent_used,
            "confidence": confidence,
            "time_taken": time_taken,
            "passed": passed,
            "notes": notes
        })
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        self.total_time += time_taken

    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "="*80)
        print("测试摘要")
        print("="*80)
        print(f"\n总测试数: {self.total_tests}")
        print(f"通过: {self.passed_tests}")
        print(f"失败: {self.total_tests - self.passed_tests}")
        print(f"通过率: {self.passed_tests/self.total_tests*100:.1f}%")
        print(f"总耗时: {self.total_time:.2f}秒")
        print(f"平均耗时: {self.total_time/self.total_tests:.2f}秒/测试")

        # 按Agent统计
        agent_stats = {}
        for result in self.results:
            agent = result["agent_used"]
            if agent not in agent_stats:
                agent_stats[agent] = {"total": 0, "passed": 0, "time": 0}
            agent_stats[agent]["total"] += 1
            if result["passed"]:
                agent_stats[agent]["passed"] += 1
            agent_stats[agent]["time"] += result["time_taken"]

        print("\n" + "-"*80)
        print("Agent使用统计:")
        print("-"*80)
        for agent, stats in agent_stats.items():
            pass_rate = stats["passed"]/stats["total"]*100
            avg_time = stats["time"]/stats["total"]
            print(f"{agent:20} | 使用{stats['total']:2}次 | "
                  f"通过率{pass_rate:5.1f}% | 平均耗时{avg_time:5.2f}s")

        # 失败的测试
        failed_tests = [r for r in self.results if not r["passed"]]
        if failed_tests:
            print("\n" + "-"*80)
            print("失败的测试:")
            print("-"*80)
            for r in failed_tests:
                print(f"\n测试: {r['test_name']}")
                print(f"  查询: {r['query']}")
                print(f"  Agent: {r['agent_used']}")
                print(f"  原因: {r['notes']}")


# ============================================================================
# 问答测试用例
# ============================================================================

async def test_basic_greetings(suite: QATestSuite):
    """测试类别1: 基础问候和告别"""
    print("\n" + "="*80)
    print("测试类别 1: 基础问候和告别")
    print("="*80)

    from app.agents.pipeline.dialog_agent import DialogueAgent

    agent = DialogueAgent()

    test_cases = [
        ("你好", "greeting"),
        ("您好", "greeting"),
        ("Hi", "greeting"),
        ("再见", "farewell"),
        ("拜拜", "farewell"),
        ("谢谢", "farewell"),
    ]

    for query, intent in test_cases:
        start = time.time()
        result = agent.respond(intent)
        elapsed = time.time() - start

        passed = result.confidence >= 0.8

        print(f"\n✓ 查询: {query}")
        print(f"  回答: {result.answer[:80]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  耗时: {elapsed:.3f}s")

        suite.add_result(
            test_name=f"问候测试-{query}",
            query=query,
            response=result.answer,
            agent_used="DialogueAgent",
            confidence=result.confidence,
            time_taken=elapsed,
            passed=passed
        )


async def test_ambiguous_queries(suite: QATestSuite):
    """测试类别2: 模糊查询和澄清"""
    print("\n" + "="*80)
    print("测试类别 2: 模糊查询和澄清")
    print("="*80)

    from app.agents.pipeline.dialog_agent import ClarifierAgent

    agent = ClarifierAgent()

    test_cases = [
        "我想了解一下",
        "这个怎么办",
        "能告诉我吗",
        "有什么要求",
        "需要准备什么",
        "怎么申请",
    ]

    for query in test_cases:
        start = time.time()
        result = agent.ask(query)
        elapsed = time.time() - start

        passed = result.confidence == 0.4 and "确认" in result.answer

        print(f"\n✓ 查询: {query}")
        print(f"  澄清: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence}")
        print(f"  耗时: {elapsed:.3f}s")

        suite.add_result(
            test_name=f"澄清测试-{query}",
            query=query,
            response=result.answer,
            agent_used="ClarifierAgent",
            confidence=result.confidence,
            time_taken=elapsed,
            passed=passed
        )


async def test_query_rewriting(suite: QATestSuite):
    """测试类别3: 查询改写"""
    print("\n" + "="*80)
    print("测试类别 3: 查询改写")
    print("="*80)

    from app.agents.pipeline.rewrite_agent import RewriteAgent

    agent = RewriteAgent()

    test_cases = [
        "想问下补贴咋算",
        "这政策啥时候开始的呀",
        "我能拿多少钱不",
        "需要啥材料啊",
        "符合条件吗我",
        "怎么申请这个呢",
        "有没有什么优惠政策",
        "小微企业能享受啥",
    ]

    for query in test_cases:
        start = time.time()
        rewritten = await agent.rewrite(query)
        elapsed = time.time() - start

        passed = len(rewritten) > 0 and rewritten != query

        print(f"\n✓ 原查询: {query}")
        print(f"  改写后: {rewritten}")
        print(f"  耗时: {elapsed:.3f}s")

        suite.add_result(
            test_name=f"改写测试-{query[:10]}",
            query=query,
            response=rewritten,
            agent_used="RewriteAgent",
            confidence=1.0 if passed else 0.0,
            time_taken=elapsed,
            passed=passed
        )


async def test_policy_consultation(suite: QATestSuite):
    """测试类别4: 政策咨询（知识检索+联网）"""
    print("\n" + "="*80)
    print("测试类别 4: 政策咨询（知识检索+联网）")
    print("="*80)

    from app.agents.pipeline.knowledge_agent import KnowledgeAgent
    from app.agents.service.tools import KnowledgeTool, WebSearchTool

    knowledge_tool = KnowledgeTool()
    web_search_tool = WebSearchTool()
    agent = KnowledgeAgent(
        knowledge_tool=knowledge_tool,
        top_k=5,
        web_search_tool=web_search_tool
    )

    test_cases = [
        # 创业相关
        "北京市创业补贴政策有哪些",
        "大学生创业有什么优惠政策",
        "创业失业保险金领取条件",

        # 税收相关
        "小微企业税收优惠政策",
        "个体工商户税收减免",
        "高新技术企业税收政策",

        # 社保相关
        "灵活就业人员社保缴纳",
        "企业社保补贴申请条件",

        # 培训相关
        "职业技能培训补贴",
        "企业员工培训补贴政策",
    ]

    for query in test_cases:
        start = time.time()
        try:
            result = await agent.answer(query)
            elapsed = time.time() - start

            passed = (result.confidence > 0.3 and
                     len(result.answer) > 50 and
                     result.metadata.get('route') == 'knowledge')

            print(f"\n✓ 查询: {query}")
            print(f"  回答: {result.answer[:150]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  来源: {result.metadata.get('origin')}")
            print(f"  耗时: {elapsed:.3f}s")

            suite.add_result(
                test_name=f"政策咨询-{query[:15]}",
                query=query,
                response=result.answer[:200],
                agent_used="KnowledgeAgent",
                confidence=result.confidence,
                time_taken=elapsed,
                passed=passed
            )
        except Exception as e:
            elapsed = time.time() - start
            print(f"\n✗ 查询失败: {query}")
            print(f"  错误: {e}")

            suite.add_result(
                test_name=f"政策咨询-{query[:15]}",
                query=query,
                response=f"错误: {str(e)}",
                agent_used="KnowledgeAgent",
                confidence=0.0,
                time_taken=elapsed,
                passed=False,
                notes=str(e)
            )


async def test_subsidy_calculation(suite: QATestSuite):
    """测试类别5: 补贴计算"""
    print("\n" + "="*80)
    print("测试类别 5: 补贴计算")
    print("="*80)

    from app.agents.pipeline.rule_agent import RuleEngineAgent

    agent = RuleEngineAgent(rule_dir="rules")

    test_cases = [
        # 家电补贴
        "济南市买冰箱能拿多少补贴",
        "家电以旧换新补贴怎么算",
        "空调补贴政策是什么",

        # 消费券
        "济南市消费券怎么使用",
        "消费券满减规则",

        # 汽车补贴
        "济南市汽车以旧换新补贴",

        # 一般性查询
        "我想计算补贴金额",
        "这个政策有多少补贴",
    ]

    for query in test_cases:
        start = time.time()
        try:
            result = await agent.compute(query)
            elapsed = time.time() - start

            passed = result.metadata.get('route') == 'rule_engine'

            print(f"\n✓ 查询: {query}")
            print(f"  回答: {result.answer[:150]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  匹配规则: {result.metadata.get('rule_id')}")
            print(f"  耗时: {elapsed:.3f}s")

            suite.add_result(
                test_name=f"补贴计算-{query[:15]}",
                query=query,
                response=result.answer[:200],
                agent_used="RuleEngineAgent",
                confidence=result.confidence,
                time_taken=elapsed,
                passed=passed
            )
        except Exception as e:
            elapsed = time.time() - start
            print(f"\n✗ 查询失败: {query}")
            print(f"  错误: {e}")

            suite.add_result(
                test_name=f"补贴计算-{query[:15]}",
                query=query,
                response=f"错误: {str(e)}",
                agent_used="RuleEngineAgent",
                confidence=0.0,
                time_taken=elapsed,
                passed=False,
                notes=str(e)
            )


async def test_multi_turn_conversations(suite: QATestSuite):
    """测试类别6: 多轮对话场景"""
    print("\n" + "="*80)
    print("测试类别 6: 多轮对话场景")
    print("="*80)

    from app.agents.pipeline.dialog_agent import DialogueAgent
    from app.agents.pipeline.rewrite_agent import RewriteAgent
    from app.agents.pipeline.rule_agent import RuleEngineAgent
    from app.agents.pipeline.knowledge_agent import KnowledgeAgent
    from app.agents.service.tools import KnowledgeTool, WebSearchTool

    dialogue_agent = DialogueAgent()
    rewrite_agent = RewriteAgent()
    rule_agent = RuleEngineAgent(rule_dir="rules")
    knowledge_tool = KnowledgeTool()
    web_search_tool = WebSearchTool()
    knowledge_agent = KnowledgeAgent(
        knowledge_tool=knowledge_tool,
        top_k=5,
        web_search_tool=web_search_tool
    )

    conversations = [
        # 对话1: 政策咨询 -> 详细了解 -> 计算
        [
            ("你好", "dialogue", dialogue_agent),
            ("我想了解创业补贴", "knowledge", knowledge_agent),
            ("谢谢", "dialogue", dialogue_agent),
        ],

        # 对话2: 补贴计算 -> 申请条件 -> 告别
        [
            ("您好", "dialogue", dialogue_agent),
            ("济南市家电补贴怎么算", "rule", rule_agent),
            ("需要什么条件", "knowledge", knowledge_agent),
            ("再见", "dialogue", dialogue_agent),
        ],
    ]

    for conv_idx, conversation in enumerate(conversations, 1):
        print(f"\n{'─'*80}")
        print(f"对话 {conv_idx}:")
        print(f"{'─'*80}")

        for turn, (query, agent_type, agent) in enumerate(conversation, 1):
            start = time.time()

            try:
                if agent_type == "dialogue":
                    intent = "greeting" if any(word in query for word in ["你好", "您好"]) else "farewell"
                    result = agent.respond(intent)
                    response = result.answer
                    confidence = result.confidence
                    agent_name = "DialogueAgent"

                elif agent_type == "knowledge":
                    rewritten = await rewrite_agent.rewrite(query)
                    result = await agent.answer(rewritten)
                    response = result.answer
                    confidence = result.confidence
                    agent_name = "KnowledgeAgent"

                elif agent_type == "rule":
                    rewritten = await rewrite_agent.rewrite(query)
                    result = await agent.compute(rewritten)
                    response = result.answer
                    confidence = result.confidence
                    agent_name = "RuleEngineAgent"

                elapsed = time.time() - start
                passed = confidence > 0.3

                print(f"\n第{turn}轮:")
                print(f"  用户: {query}")
                print(f"  助手: {response[:100]}...")
                print(f"  Agent: {agent_name}")
                print(f"  置信度: {confidence}")
                print(f"  耗时: {elapsed:.3f}s")

                suite.add_result(
                    test_name=f"对话{conv_idx}-第{turn}轮",
                    query=query,
                    response=response[:200],
                    agent_used=agent_name,
                    confidence=confidence,
                    time_taken=elapsed,
                    passed=passed
                )

            except Exception as e:
                elapsed = time.time() - start
                print(f"\n第{turn}轮失败:")
                print(f"  用户: {query}")
                print(f"  错误: {e}")

                suite.add_result(
                    test_name=f"对话{conv_idx}-第{turn}轮",
                    query=query,
                    response=f"错误: {str(e)}",
                    agent_used="Unknown",
                    confidence=0.0,
                    time_taken=elapsed,
                    passed=False,
                    notes=str(e)
                )


async def test_complex_queries(suite: QATestSuite):
    """测试类别7: 复杂组合查询"""
    print("\n" + "="*80)
    print("测试类别 7: 复杂组合查询")
    print("="*80)

    from app.agents.pipeline.rewrite_agent import RewriteAgent
    from app.agents.pipeline.knowledge_agent import KnowledgeAgent
    from app.agents.service.tools import KnowledgeTool, WebSearchTool

    rewrite_agent = RewriteAgent()
    knowledge_tool = KnowledgeTool()
    web_search_tool = WebSearchTool()
    knowledge_agent = KnowledgeAgent(
        knowledge_tool=knowledge_tool,
        top_k=5,
        web_search_tool=web_search_tool
    )

    test_cases = [
        "北京市创业补贴和小微企业税收优惠可以同时享受吗",
        "大学生创业有哪些补贴政策，申请条件是什么，需要准备什么材料",
        "灵活就业人员社保缴纳标准和企业社保有什么区别",
        "高新技术企业申请条件及税收优惠政策详解",
        "职业技能培训补贴的申请流程、金额标准和注意事项",
    ]

    for query in test_cases:
        start = time.time()

        try:
            # 先改写
            rewritten = await rewrite_agent.rewrite(query)

            # 再查询
            result = await knowledge_agent.answer(rewritten)

            elapsed = time.time() - start
            passed = result.confidence > 0.3 and len(result.answer) > 100

            print(f"\n✓ 查询: {query}")
            print(f"  改写: {rewritten}")
            print(f"  回答: {result.answer[:200]}...")
            print(f"  置信度: {result.confidence}")
            print(f"  耗时: {elapsed:.3f}s")

            suite.add_result(
                test_name=f"复杂查询-{query[:20]}",
                query=query,
                response=result.answer[:300],
                agent_used="Rewrite+Knowledge",
                confidence=result.confidence,
                time_taken=elapsed,
                passed=passed
            )

        except Exception as e:
            elapsed = time.time() - start
            print(f"\n✗ 查询失败: {query[:50]}...")
            print(f"  错误: {e}")

            suite.add_result(
                test_name=f"复杂查询-{query[:20]}",
                query=query,
                response=f"错误: {str(e)}",
                agent_used="Rewrite+Knowledge",
                confidence=0.0,
                time_taken=elapsed,
                passed=False,
                notes=str(e)
            )


async def run_all_qa_tests():
    """运行所有问答测试"""
    suite = QATestSuite()

    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行所有测试
    await test_basic_greetings(suite)
    await test_ambiguous_queries(suite)
    await test_query_rewriting(suite)
    await test_policy_consultation(suite)
    await test_subsidy_calculation(suite)
    await test_multi_turn_conversations(suite)
    await test_complex_queries(suite)

    # 打印摘要
    suite.print_summary()

    print(f"\n测试结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return suite


def main():
    """主函数"""
    suite = asyncio.run(run_all_qa_tests())

    # 保存结果到文件
    import json
    result_file = "tests/qa_test_results.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "total_tests": suite.total_tests,
            "passed_tests": suite.passed_tests,
            "total_time": suite.total_time,
            "results": suite.results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n测试结果已保存到: {result_file}")

    return suite


if __name__ == "__main__":
    main()
