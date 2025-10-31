#!/usr/bin/env python3
"""
智能路由版Gove政策问答系统主程序
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from smart_orchestrator import SmartOrchestrator
from utils.config import Config


async def interactive_mode(orchestrator: SmartOrchestrator):
    """交互模式"""
    print("\n=== Gove智能路由政策问答系统 ===")
    print("我可以处理：")
    print("- 日常对话和问候")
    print("- 政策咨询")
    print("- 补贴金额计算")
    print("- 政策比较")
    print("- 进度查询")
    print("- 其他政策相关问题")
    print("\n输入 'quit' 或 'exit' 退出")
    print("-" * 50)

    session_id = None
    conversation_history = []

    while True:
        try:
            query = input("\n您: ").strip()

            if query.lower() in ['quit', 'exit', '退出', 'q']:
                print("\n助手：感谢使用，再见！")
                break

            if not query:
                continue

            print("\n助手：正在处理您的问题...")
            response = await orchestrator.process_query(query, session_id)

            # 更新会话ID
            session_id = response.metadata.get("session_id")

            # 显示路由信息（调试用）
            chain = response.metadata.get("chain", "unknown")
            if logging.getLogger().level <= logging.DEBUG:
                print(f"\n[路由到: {chain}]")

            # 显示答案
            print("\n" + response.answer)

            # 显示额外信息
            if response.metadata:
                metadata = response.metadata

                # 计算结果
                if "calculated_amount" in metadata:
                    print(f"\n💰 计算金额: {metadata['calculated_amount']:.2f}元")

                # 置信度
                if response.confidence > 0:
                    emoji = "🟢" if response.confidence > 0.8 else "🟡" if response.confidence > 0.5 else "🔴"
                    print(f"\n{emoji} 置信度: {response.confidence:.1%}")

            # 显示来源
            if response.sources:
                print(f"\n📄 政策来源:")
                for i, source in enumerate(response.sources[:3], 1):
                    print(f"  {i}. {source.title[:50]}...")
                    if source.source:
                        print(f"     发布机构: {source.source}")

        except KeyboardInterrupt:
            print("\n\n程序被中断，正在退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            logging.error(f"Error in interactive mode: {e}", exc_info=True)


async def batch_mode(orchestrator: SmartOrchestrator, query_file: str):
    """批量处理模式"""
    print(f"\n批量处理模式: {query_file}")

    try:
        with open(query_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]

        print(f"共{len(queries)}个查询待处理")

        results = []
        routing_stats = {}

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 处理: {query[:50]}...")
            response = await orchestrator.process_query(query)

            # 统计路由
            chain = response.metadata.get("chain", "unknown")
            routing_stats[chain] = routing_stats.get(chain, 0) + 1

            results.append({
                "query": query,
                "answer": response.answer,
                "confidence": response.confidence,
                "chain": chain,
                "sources": [s.title for s in response.sources]
            })

        # 保存结果
        output_file = Path(query_file).with_suffix('.json')
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "results": results,
                "routing_statistics": routing_stats
            }, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 结果已保存到: {output_file}")

        # 显示路由统计
        print("\n📊 路由统计:")
        for chain, count in routing_stats.items():
            percentage = count / len(queries) * 100
            print(f"  {chain}: {count} ({percentage:.1f}%)")

    except Exception as e:
        print(f"❌ 错误: {e}")
        logging.error(f"Error in batch mode: {e}", exc_info=True)


async def demo_mode(orchestrator: SmartOrchestrator):
    """演示模式"""
    print("\n=== 演示模式 ===")

    demo_queries = [
        ("你好", "greeting"),
        ("我想买台冰箱，能补贴多少钱？", "calculation"),
        ("汽车补贴和家电补贴有什么区别？", "comparison"),
        ("申请补贴需要什么条件？", "policy_inquiry"),
        ("谢谢你的帮助", "farewell")
    ]

    for query, expected_intent in demo_queries:
        print(f"\n🔍 查询: {query}")
        print(f"   预期意图: {expected_intent}")

        response = await orchestrator.process_query(query)

        chain = response.metadata.get("chain", "unknown")
        confidence = response.confidence

        print(f"   实际路由: {chain}")
        print(f"   置信度: {confidence:.1%}")
        print(f"   回答: {response.answer[:100]}...")

        print("-" * 50)
        await asyncio.sleep(1)  # 演示效果


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Gove智能路由政策问答系统')
    parser.add_argument('--config', '-c', default='config/config.yaml', help='配置文件路径')
    parser.add_argument('--load-docs', nargs='+', help='加载文档目录')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互模式')
    parser.add_argument('--batch', '-b', help='批量处理模式，查询文件路径')
    parser.add_argument('--demo', '-d', action='store_true', help='演示模式')
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
        # 加载配置
        config = Config.from_file(args.config) if Path(args.config).exists() else Config.from_env()

        # 初始化编排器
        orchestrator = SmartOrchestrator(
            model_config=config.model,
            vector_store_config=config.vector_store,
            logging_config=config.logging
        )

        await orchestrator.initialize()

        # 根据模式运行
        if args.demo:
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