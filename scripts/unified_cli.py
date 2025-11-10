#!/usr/bin/env python3
"""
统一智能体版Gove政策问答系统 - 集成ChatDB和Gove的所有智能体
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.services.orchestrator import AgentOrchestratorService, ProcessingMode
from app.utils.config import Config


async def interactive_mode(orchestrator: AgentOrchestratorService):
    """交互模式"""
    print("\n=== Gove统一智能体系统 ===")
    print("🤖 集成ChatDB和Gove的智能体架构")
    print("✨ 支持功能：")
    print("   • 日常对话和问候")
    print("   • 政策咨询（KB检索）")
    print("   • 补贴金额计算")
    print("   • 政策比较分析")
    print("   • 复杂查询（并行处理）")
    print("   • 会话上下文管理")
    print("\n输入 'quit' 或 'exit' 退出")
    print("-" * 50)

    session_id = None

    while True:
        try:
            query = input("\n您: ").strip()

            if query.lower() in ['quit', 'exit', '退出', 'q']:
                print("\n助手：感谢使用，再见！")
                break

            if not query:
                continue

            print("\n助手：正在智能分析并处理...")
            response = await orchestrator.process_query(query, session_id)

            # 更新会话ID
            session_id = response.metadata.get("session_id")

            # 显示处理信息
            chain = response.metadata.get("chain", "unknown")
            retrieved = response.metadata.get("retrieved_count", 0)
            analyzed = response.metadata.get("analyzed_count", 0)

            print(f"\n[处理链: {chain}]")
            if retrieved > 0:
                print(f"[检索到 {retrieved} 个政策]")
            if analyzed > 0:
                print(f"[分析了 {analyzed} 个政策]")

            # 显示答案
            print("\n" + response.answer)

            # 显示额外信息
            if response.metadata:
                metadata = response.metadata

                # 计算结果
                if "calculated_amount" in metadata:
                    print(f"\n💰 补贴金额: {metadata['calculated_amount']:.2f}元")

                # 比较结果
                if "compared_count" in metadata:
                    print(f"\n📊 比较了 {metadata['compared_count']} 个政策")

                # 置信度
                if response.confidence > 0:
                    emoji = "🟢" if response.confidence > 0.8 else "🟡" if response.confidence > 0.5 else "🔴"
                    print(f"\n{emoji} 置信度: {response.confidence:.1%}")

            # 显示来源
            if response.sources:
                print(f"\n📄 政策来源:")
                for i, source in enumerate(response.sources[:3], 1):
                    print(f"  {i}. {source.title[:50]}...")

        except KeyboardInterrupt:
            print("\n\n程序被中断，正在退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            logging.error(f"Error in interactive mode: {e}", exc_info=True)


async def demo_mode(orchestrator: AgentOrchestratorService):
    """演示模式 - 展示不同智能体的能力"""
    print("\n=== 演示模式 ===")

    demo_scenarios = [
        {
            "name": "对话测试",
            "query": "你好，请介绍一下自己",
            "expected_chain": "chat",
            "description": "测试聊天智能体"
        },
        {
            "name": "简单查询",
            "query": "申请家电补贴需要什么条件？",
            "expected_chain": "policy",
            "description": "测试政策查询链"
        },
        {
            "name": "计算测试",
            "query": "我想买台5000元的电视，能补贴多少钱？",
            "expected_chain": "calculation",
            "description": "测试计算智能体"
        },
        {
            "name": "比较测试",
            "query": "汽车补贴和家电补贴有什么区别？",
            "expected_chain": "comparison",
            "description": "测试比较智能体"
        },
        {
            "name": "上下文测试",
            "query": "那申请材料有哪些？",
            "expected_chain": "policy",
            "description": "测试会话上下文"
        }
    ]

    for i, scenario in enumerate(demo_scenarios, 1):
        print(f"\n{'='*50}")
        print(f"\n🔍 测试 {i}/{len(demo_scenarios)}: {scenario['name']}")
        print(f"   查询: {scenario['query']}")
        print(f"   期望: {scenario['description']}")
        print(f"   预期链: {scenario['expected_chain']}")

        response = await orchestrator.process_query(scenario['query'])

        actual_chain = response.metadata.get("chain", "unknown")
        confidence = response.confidence

        print(f"\n✅ 实际链: {actual_chain}")
        print(f"   置信度: {confidence:.1%}")
        print(f"   回答: {response.answer[:100]}...")

        # 检查是否符合预期
        if actual_chain == scenario['expected_chain']:
            print("✅ 测试通过")
        else:
            print(f"⚠️  链不匹配 (期望: {scenario['expected_chain']})")

        await asyncio.sleep(1)  # 演示效果

    print(f"\n{'='*50}")
    print("\n✅ 演示完成！")


async def batch_mode(orchestrator: AgentOrchestratorService, query_file: str):
    """批量处理模式"""
    print(f"\n批量处理模式: {query_file}")

    try:
        with open(query_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]

        print(f"共{len(queries)}个查询待处理")

        results = []
        chain_stats = {}
        intent_stats = {}

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 处理: {query[:50]}...")
            response = await orchestrator.process_query(query)

            # 统计处理链
            chain = response.metadata.get("chain", "unknown")
            chain_stats[chain] = chain_stats.get(chain, 0) + 1

            # 统计意图类型
            intent = response.metadata.get("intent", "unknown")
            intent_stats[intent] = intent_stats.get(intent, 0) + 1

            results.append({
                "query": query,
                "answer": response.answer,
                "confidence": response.confidence,
                "chain": chain,
                "intent": intent,
                "sources": [s.title for s in response.sources]
            })

        # 保存结果
        output_file = Path(query_file).with_suffix('.json')
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "results": results,
                "chain_statistics": chain_stats,
                "intent_statistics": intent_stats
            }, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 结果已保存到: {output_file}")

        # 显示统计
        print("\n📊 处理统计:")
        print("\n处理链分布:")
        for chain, count in chain_stats.items():
            percentage = count / len(queries) * 100
            print(f"  {chain}: {count} ({percentage:.1f}%)")

        print("\n意图分布:")
        for intent, count in intent_stats.items():
            percentage = count / len(queries) * 100
            print(f"  {intent}: {count} ({percentage:.1f}%)")

        # 计算平均置信度
        avg_confidence = sum(r["confidence"] for r in results) / len(results)
        print(f"\n平均置信度: {avg_confidence:.1%}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        logging.error(f"Error in batch mode: {e}", exc_info=True)


async def metrics_mode(orchestrator: AgentOrchestratorService):
    """指标模式 - 显示系统指标"""
    print("\n=== 系统指标 ===")

    # 获取指标
    metrics = await orchestrator.get_metrics()

    print(f"\n📊 智能体统计:")
    print(f"   总智能体数: {metrics['total_agents']}")
    print(f"   处理链数: {metrics['processing_chains']}")

    print("\n🤖 智能体详情:")
    for name, agent_metrics in metrics["agent_metrics"].items():
        if hasattr(agent_metrics, "metrics"):
            print(f"\n   {name}:")
            for key, value in agent_metrics.items():
                if isinstance(value, dict):
                    print(f"     {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"       - {sub_key}: {sub_value}")
                else:
                    print(f"     {key}: {value}")
        else:
            print(f"   {name}: 已初始化")

    print("\n✅ 指标获取完成")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Gove统一智能体系统')
    parser.add_argument('--config', '-c', default='config/config.yaml', help='配置文件路径')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互模式')
    parser.add_argument('--batch', '-b', help='批量处理模式，查询文件路径')
    parser.add_argument('--demo', '-d', action='store_true', help='演示模式')
    parser.add_argument('--metrics', '-m', action='store_true', help='显示系统指标')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    parser.add_argument('--mode', choices=['single', 'sequential', 'parallel', 'adaptive'],
                        help='处理模式', default='adaptive')

    args = parser.parse_args()

    # 设置日志
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        # 加载配置
        config = Config.from_file(args.config) if Path(args.config).exists() else Config.from_env()

        # 初始化编排服务
        orchestrator = AgentOrchestratorService(config)

        # 根据模式运行
        if args.metrics:
            await metrics_mode(orchestrator)
        elif args.demo:
            await demo_mode(orchestrator)
        elif args.interactive or not args.batch:
            await interactive_mode(orchestrator)
        elif args.batch:
            await batch_mode(orchestrator, args.batch)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
