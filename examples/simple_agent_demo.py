"""
简单的Agent使用示例
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """主函数 - 演示如何使用Agent模块"""

    # 1. 创建Agent管理器
    from app.agents.modules.manager import create_default_manager
    manager = await create_default_manager()

    print("=" * 60)
    print("政策问答系统 - Agent演示")
    print("=" * 60)

    # 2. 测试查询
    test_queries = [
        "我想了解大学生创业补贴政策",
        "申请创业补贴需要什么条件？",
        "个人技能培训有什么补贴吗？",
        "怎么申请科技创新券？",
        "房租补贴需要准备什么材料？"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n【查询 {i}】")
        print(f"用户：{query}")
        print("-" * 40)

        # 运行处理流水线
        result = await manager.run_pipeline(
            "policy_qa",
            {"query": query}
        )

        # 输出结果
        print("\n系统回答：")
        print(result.get("answer", "抱歉，无法生成答案"))

        # 显示处理信息
        print(f"\n处理信息：")
        print(f"  - 意图识别：{result.get('intent', 'N/A')}")
        print(f"  - 关键词：{', '.join(result.get('keywords', []))}")
        print(f"  - 找到政策：{result.get('result_count', 0)} 条")
        print(f"  - 处理时间：{result.get('processing_time', 0):.2f} 秒")

        # 显示后续建议
        if result.get('suggestions'):
            print(f"\n建议您还可以了解：")
            for j, suggestion in enumerate(result['suggestions'], 1):
                print(f"  {j}. {suggestion}")

    # 3. 显示模块状态
    print("\n" + "=" * 60)
    print("模块状态")
    print("=" * 60)
    status = manager.get_status()
    for module_name, module_info in status['modules'].items():
        print(f"\n{module_name}:")
        print(f"  - 版本：{module_info['version']}")
        print(f"  - 状态：{'运行中' if module_info['is_running'] else '已停止'}")
        print(f"  - 处理次数：{module_info['metrics']['processed_count']}")
        print(f"  - 平均时间：{module_info['avg_time']:.3f} 秒")

    # 4. 停止管理器
    await manager.stop_all()
    print("\n系统已停止")


if __name__ == "__main__":
    asyncio.run(main())