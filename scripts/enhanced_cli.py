#!/usr/bin/env python3
"""
增强版Gove政策智能问答系统主程序
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.orchestrators.enhanced import EnhancedPolicyQAOrchestrator
from utils.config import Config


async def interactive_mode(orchestrator: EnhancedPolicyQAOrchestrator):
    """交互模式"""
    print("\n=== Gove政策智能问答系统 v2.0 ===")
    print("输入您的问题，输入 'quit' 或 'exit' 退出")
    print("-" * 50)

    session_id = None

    while True:
        try:
            query = input("\n请输入您的问题: ").strip()

            if query.lower() in ['quit', 'exit', '退出', 'q']:
                print("感谢使用！")
                break

            if not query:
                continue

            print("\n正在处理您的问题...")
            response = await orchestrator.process_query(query, session_id)

            # 更新会话ID
            session_id = response.metadata.get("session_id")

            # 显示答案
            print("\n" + "=" * 50)
            print(response.answer)
            print("=" * 50)

            # 显示置信度
            if response.confidence > 0:
                print(f"\n置信度: {response.confidence:.1%}")

            # 显示来源
            if response.sources:
                print(f"\n政策来源:")
                for i, source in enumerate(response.sources[:3], 1):
                    print(f"{i}. {source.title}")
                    print(f"   发布机构: {source.source}")
                    if source.publish_date:
                        print(f"   发布日期: {source.publish_date.strftime('%Y-%m-%d')}")

        except KeyboardInterrupt:
            print("\n\n程序被中断，正在退出...")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            logging.error(f"Error in interactive mode: {e}", exc_info=True)


async def batch_mode(orchestrator: EnhancedPolicyQAOrchestrator, query_file: str):
    """批量处理模式"""
    print(f"\n批量处理模式: {query_file}")

    try:
        with open(query_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]

        print(f"共{len(queries)}个查询待处理")

        results = []
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] 处理: {query[:50]}...")
            response = await orchestrator.process_query(query)
            results.append({
                "query": query,
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": [s.title for s in response.sources]
            })

        # 保存结果
        output_file = Path(query_file).with_suffix('.json')
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {output_file}")

    except Exception as e:
        print(f"错误: {e}")
        logging.error(f"Error in batch mode: {e}", exc_info=True)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Gove政策智能问答系统 v2.0')
    parser.add_argument('--config', '-c', default='config/config.yaml', help='配置文件路径')
    parser.add_argument('--load-docs', nargs='+', help='加载文档目录')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互模式')
    parser.add_argument('--batch', '-b', help='批量处理模式，查询文件路径')
    parser.add_argument('--init-data', action='store_true', help='初始化数据')
    parser.add_argument('--log-level', default='INFO', help='日志级别')

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        # 加载配置
        config = Config.from_file(args.config) if Path(args.config).exists() else Config.from_env()

        # 初始化编排器
        async with EnhancedPolicyQAOrchestrator(
            model_config=config.model,
            vector_store_config=config.vector_store,
            logging_config=config.logging
        ) as orchestrator:
            # 初始化数据（如果需要）
            if args.init_data:
                print("初始化数据中...")
                await orchestrator.load_documents([])
                print("数据初始化完成！")

            # 加载文档
            if args.load_docs:
                print(f"加载文档: {args.load_docs}")
                await orchestrator.load_documents(args.load_docs)

            # 根据模式运行
            if args.interactive or not args.batch:
                await interactive_mode(orchestrator)
            elif args.batch:
                await batch_mode(orchestrator, args.batch)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
