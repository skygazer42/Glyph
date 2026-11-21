#!/usr/bin/env python3
"""
政策知识服务命令行：python -m scripts.agent_cli。
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import AsyncExitStack
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from app.agents.service.agent_service import AgentService


async def interactive_mode(service: AgentService) -> None:
    """交互模式"""
    print("\n=== Glyph 政策知识服务 ===")
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
            query = (await asyncio.to_thread(input, "\n您: ")).strip()

            if query.lower() in ['quit', 'exit', '退出', 'q']:
                print("\n助手：感谢使用，再见！")
                break

            if not query:
                continue

            print("\n助手：正在智能分析并处理...")
            response = await service.process_query(query, session_id=session_id)

            # 更新会话ID
            session_id = response.metadata.get("session_id")

            # 显示处理信息
            chain = response.metadata["route"]
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
                print("\n📄 政策来源:")
                for i, source in enumerate(response.sources[:3], 1):
                    print(f"  {i}. {source.title[:50]}...")

        except (KeyboardInterrupt, EOFError):
            print("\n\n程序被中断，正在退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            logging.error(f"Error in interactive mode: {e}", exc_info=True)


async def demo_mode(service: AgentService) -> None:
    """演示模式 - 展示不同智能体的能力"""
    print("\n=== 演示模式 ===")

    demo_scenarios = [
        {
            "name": "对话测试",
            "query": "你好，请介绍一下自己",
            "expected_chain": "dialogue",
            "description": "测试聊天智能体"
        },
        {
            "name": "简单查询",
            "query": "申请家电补贴需要什么条件？",
            "expected_chain": "knowledge",
            "description": "测试政策查询链"
        },
        {
            "name": "计算测试",
            "query": "我想买台5000元的电视，能补贴多少钱？",
            "expected_chain": "rule_engine",
            "description": "测试计算智能体"
        },
        {
            "name": "比较测试",
            "query": "汽车补贴和家电补贴有什么区别？",
            "expected_chain": "knowledge",
            "description": "测试比较智能体"
        },
        {
            "name": "上下文测试",
            "query": "那申请材料有哪些？",
            "expected_chain": "graph",
            "description": "测试会话上下文"
        }
    ]

    session_id = None
    for i, scenario in enumerate(demo_scenarios, 1):
        print(f"\n{'='*50}")
        print(f"\n🔍 测试 {i}/{len(demo_scenarios)}: {scenario['name']}")
        print(f"   查询: {scenario['query']}")
        print(f"   期望: {scenario['description']}")
        print(f"   预期链: {scenario['expected_chain']}")

        response = await service.process_query(scenario['query'], session_id=session_id)
        session_id = response.metadata["session_id"]

        actual_chain = response.metadata["route"]
        confidence = response.confidence

        print(f"\nActual route: {actual_chain}")
        print(f"   置信度: {confidence:.1%}")
        print(f"   回答: {response.answer[:100]}...")

        # 检查是否符合预期
        if actual_chain == scenario['expected_chain']:
            print("[OK] Test passed")
        else:
            print(f"[WARNING] Chain mismatch (expected: {scenario['expected_chain']})")

        await asyncio.sleep(1)  # 演示效果

    print(f"\n{'='*50}")
    print("\n[OK] Demo completed!")


async def batch_mode(service: AgentService, query_file: str) -> None:
    """批量处理模式"""
    print(f"\n批量处理模式: {query_file}")

    try:
        query_text = await asyncio.to_thread(Path(query_file).read_text, encoding="utf-8")
        queries = [line.strip() for line in query_text.splitlines() if line.strip()]

        print(f"共{len(queries)}个查询待处理")

        results = []
        chain_stats: dict[str, int] = {}
        intent_stats: dict[str, int] = {}

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 处理: {query[:50]}...")
            response = await service.process_query(query)

            # 统计处理链
            chain = response.metadata["route"]
            chain_stats[chain] = chain_stats.get(chain, 0) + 1

            # 统计意图类型
            intent = response.metadata["intent"]["intent"]
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
        query_path = Path(query_file)
        output_file = (
            query_path.with_name(f"{query_path.stem}.results.json")
            if query_path.suffix.lower() == ".json" else query_path.with_suffix(".json")
        )
        if await asyncio.to_thread(output_file.exists) and await asyncio.to_thread(output_file.samefile, query_path):
            raise ValueError("Batch output must not overwrite the input file")
        output_text = json.dumps({
                "results": results,
                "chain_statistics": chain_stats,
                "intent_statistics": intent_stats
            }, ensure_ascii=False, indent=2)
        await asyncio.to_thread(output_file.write_text, output_text, encoding="utf-8")

        print(f"\n[OK] Results saved to: {output_file}")

        # 显示统计
        print("\n[STATS] Processing statistics:")
        print("\n处理链分布:")
        for chain, count in chain_stats.items():
            percentage = count / len(queries) * 100
            print(f"  {chain}: {count} ({percentage:.1f}%)")

        print("\n意图分布:")
        for intent, count in intent_stats.items():
            percentage = count / len(queries) * 100
            print(f"  {intent}: {count} ({percentage:.1f}%)")

        if not results:
            return

        # 计算平均置信度
        avg_confidence = sum(r["confidence"] for r in results) / len(results)
        print(f"\n平均置信度: {avg_confidence:.1%}")

    except Exception as e:
        print(f"[ERROR]: {e}")
        raise


def metrics_mode(service: AgentService) -> None:
    """Show this CLI's constructed components, without inventing runtime metrics."""
    components = [service.rewrite_agent, service.knowledge_agent, service.graph_agent,
                  service.rule_agent, service.workflow_agent]
    print("\n=== 当前 CLI 组件清单 ===")
    print(f"   已构造组件数: {len(components)}")
    for component in components:
        print(f"   - {type(component).__name__}")


async def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='Glyph 政策知识服务')
    parser.add_argument('--config', '-c', default=None, help='配置文件路径（未指定时尝试 config/config.yaml）')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互模式')
    parser.add_argument('--batch', '-b', help='批量处理模式，查询文件路径')
    parser.add_argument('--demo', '-d', action='store_true', help='演示模式')
    parser.add_argument('--metrics', '-m', action='store_true', help='显示当前 CLI 组件清单')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    args = parser.parse_args()

    # 设置日志
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        from app.config.app_config import settings
        from app.config.agent_config import AgentServiceConfig
        config_path = Path("config/config.yaml") if args.config is None else Path(args.config)
        if await asyncio.to_thread(config_path.exists):
            config = await asyncio.to_thread(AgentServiceConfig.from_file, str(config_path))
        else:
            if args.config is not None:
                raise FileNotFoundError(config_path)
            config = await anyio.to_thread.run_sync(AgentServiceConfig)

        # 全局客户端首次导入前应用 CLI 模型配置，避免读取配置后仍使用另一个模型。
        settings.model = settings.model.model_copy(update={
            "llm_model_name": config.model.model_name,
            "llm_api_key": config.model.api_key,
            "llm_base_url": config.model.base_url,
            "llm_temperature": config.model.temperature,
            "llm_max_tokens": config.model.max_tokens,
            "llm_timeout": config.model.timeout,
        })
        from app.core.llms import model_client
        from app.utils.lifecycle import close_with_timeout

        async with AsyncExitStack() as stack:
            stack.push_async_callback(close_with_timeout, model_client.close)
            from app.agents.service.agent_service import AgentService
            service = await anyio.to_thread.run_sync(lambda: AgentService(config=config))
            stack.push_async_callback(close_with_timeout, service.aclose)
            # 根据模式运行
            if args.metrics:
                metrics_mode(service)
            else:
                await service.initialize()
                if args.demo:
                    await demo_mode(service)
                elif args.interactive or not args.batch:
                    await interactive_mode(service)
                elif args.batch:
                    await batch_mode(service, args.batch)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
