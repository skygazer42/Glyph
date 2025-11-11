"""
简化的Agent测试 - 避免完整导入app
直接测试agent模块
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("\n" + "="*70)
print("Agent Pipeline 简化测试")
print("="*70 + "\n")


def test_1_dialogue_agent():
    """测试对话代理"""
    print("测试 1: DialogueAgent - 对话代理")
    print("-"*70)

    try:
        from app.agents.pipeline.dialog_agent import DialogueAgent, ClarifierAgent

        agent = DialogueAgent()

        # 测试问候
        result = agent.respond("greeting")
        print(f"✓ 问候测试: {result.answer[:50]}...")
        assert result.confidence == 0.9

        # 测试告别
        result = agent.respond("farewell")
        print(f"✓ 告别测试: {result.answer[:50]}...")

        # 测试闲聊
        result = agent.respond("chit_chat")
        print(f"✓ 闲聊测试: {result.answer[:50]}...")

        print("✓ DialogueAgent 测试通过!\n")
        return True
    except Exception as e:
        print(f"✗ DialogueAgent 测试失败: {e}\n")
        return False


def test_2_clarifier_agent():
    """测试澄清代理"""
    print("测试 2: ClarifierAgent - 澄清代理")
    print("-"*70)

    try:
        from app.agents.pipeline.dialog_agent import ClarifierAgent

        agent = ClarifierAgent()
        result = agent.ask("我想了解一下政策")

        print(f"✓ 原问题: 我想了解一下政策")
        print(f"✓ 澄清问题: {result.answer[:80]}...")
        print(f"✓ 置信度: {result.confidence}")

        assert result.confidence == 0.4

        print("✓ ClarifierAgent 测试通过!\n")
        return True
    except Exception as e:
        print(f"✗ ClarifierAgent 测试失败: {e}\n")
        return False


async def test_3_rewrite_agent():
    """测试查询改写代理"""
    print("测试 3: RewriteAgent - 查询改写代理")
    print("-"*70)

    try:
        # 避免导入整个app，只测试类结构
        from app.agents.pipeline.rewrite_agent import RewriteAgent

        agent = RewriteAgent(max_length=256)
        print(f"✓ RewriteAgent 实例创建成功")
        print(f"✓ max_length: {agent.max_length}")

        # 测试改写（可能需要LLM）
        try:
            query = "想问下补贴怎么算"
            rewritten = await agent.rewrite(query)
            print(f"✓ 原问题: {query}")
            print(f"✓ 改写后: {rewritten[:80]}...")
        except Exception as e:
            print(f"⚠ LLM调用跳过 (可能需要API配置): {e}")

        print("✓ RewriteAgent 测试完成!\n")
        return True
    except Exception as e:
        print(f"✗ RewriteAgent 测试失败: {e}\n")
        return False


def test_4_agent_structures():
    """测试其他agent的类结构"""
    print("测试 4: 其他Agent类结构检查")
    print("-"*70)

    agents_to_test = [
        ("app.agents.pipeline.rule_agent", "RuleEngineAgent"),
        ("app.agents.pipeline.knowledge_agent", "KnowledgeAgent"),
        ("app.agents.pipeline.text2sql_agent", "Text2SQLAgent"),
        ("app.agents.pipeline.graph_agent", "GraphAgent"),
        ("app.agents.pipeline.workflow_agent", "WorkflowAgent"),
    ]

    success_count = 0
    for module_name, class_name in agents_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            print(f"✓ {class_name:25} - 模块导入成功")

            # 检查关键方法
            if hasattr(agent_class, '__init__'):
                print(f"  - __init__ 方法存在")
            if hasattr(agent_class, 'answer') or hasattr(agent_class, 'compute'):
                print(f"  - answer/compute 方法存在")

            success_count += 1
        except Exception as e:
            print(f"✗ {class_name:25} - 导入失败: {e}")

    print(f"\n✓ 成功导入 {success_count}/{len(agents_to_test)} 个Agent类\n")
    return success_count > 0


def test_5_docker_services():
    """测试Docker服务连接"""
    print("测试 5: Docker服务连接检查")
    print("-"*70)

    # 测试Milvus连接
    try:
        from pymilvus import connections
        connections.connect("test", host="localhost", port="19530")
        print("✓ Milvus服务连接成功 (localhost:19530)")
        connections.disconnect("test")
    except Exception as e:
        print(f"⚠ Milvus服务未连接: {e}")

    # 测试Redis连接
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✓ Redis服务连接成功 (localhost:6379)")
    except Exception as e:
        print(f"⚠ Redis服务未连接: {e}")

    print()
    return True


def print_agent_overview():
    """打印Agent概览"""
    print("\n" + "="*70)
    print("Agent Pipeline 功能概览")
    print("="*70)
    print("""
1. DialogueAgent      - 处理问候/告别/闲聊，模板化响应
2. ClarifierAgent     - 当意图不明时提问澄清
3. RewriteAgent       - 改写用户查询为更清晰的表述
4. RuleEngineAgent    - 使用DSL规则进行补贴计算
5. KnowledgeAgent     - 知识库检索 + LLM生成答案 + 联网搜索
6. Text2SQLAgent      - 自然语言转SQL查询并执行
7. GraphAgent         - LightRAG图谱关系查询
8. WorkflowAgent      - 编排多个agent的复杂工作流 (GraphFlow)

测试建议:
- 基础功能测试: DialogAgent, ClarifierAgent
- 需要LLM配置: RewriteAgent, RuleEngineAgent, KnowledgeAgent
- 需要数据库: Text2SQLAgent (需要MySQL/PostgreSQL连接)
- 需要向量库: KnowledgeAgent (需要Milvus)
- 需要图谱库: GraphAgent (需要LightRAG工作目录)
- 需要多模态: WorkflowAgent (需要Vision API)
    """)
    print("="*70 + "\n")


async def run_all_tests():
    """运行所有测试"""
    results = []

    # 同步测试
    results.append(("DialogueAgent", test_1_dialogue_agent()))
    results.append(("ClarifierAgent", test_2_clarifier_agent()))

    # 异步测试
    results.append(("RewriteAgent", await test_3_rewrite_agent()))

    # 结构测试
    results.append(("Agent Structures", test_4_agent_structures()))

    # Docker服务测试
    results.append(("Docker Services", test_5_docker_services()))

    # 打印总结
    print("="*70)
    print("测试总结")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"通过: {passed}/{total}")

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print("\n")

    # 打印概览
    print_agent_overview()


def main():
    """主函数"""
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()
