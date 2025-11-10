"""
独立运行的Agent演示 - 不依赖autogen
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接使用我们的简化模块
from app.agents.modules.base_module import BaseAgentModule
from app.agents.modules.manager import AgentManager


# 创建一个简单的查询分析Agent
class SimpleQueryAgent(BaseAgentModule):
    """简单的查询分析Agent"""

    def __init__(self):
        super().__init__("query_analyzer", "1.0.0")
        self.description = "分析用户查询意图"

    async def process(self, data: dict) -> dict:
        query = data.get("query", "")

        # 简单的意图识别
        if "补贴" in query:
            intent = "补贴查询"
        elif "条件" in query or "资格" in query:
            intent = "资格查询"
        elif "申请" in query:
            intent = "申请查询"
        else:
            intent = "一般咨询"

        data["intent"] = intent
        data["keywords"] = query.split()[:5]  # 简单分词

        print(f"  [{self.name}] 识别意图: {intent}")
        return data


# 创建一个简单的答案生成Agent
class SimpleAnswerAgent(BaseAgentModule):
    """简单的答案生成Agent"""

    def __init__(self):
        super().__init__("answer_generator", "1.0.0")
        self.description = "生成答案"

    async def process(self, data: dict) -> dict:
        query = data.get("query", "")
        intent = data.get("intent", "")

        # 根据意图生成简单答案
        if intent == "补贴查询":
            answer = f"关于补贴查询：{query}\n\n根据相关政策，您可以申请以下补贴：\n1. 创业补贴：最高10万元\n2. 场地补贴：房租50%补贴\n3. 培训补贴：最高3000元\n\n请准备相关材料进行申请。"
        elif intent == "资格查询":
            answer = f"关于资格查询：{query}\n\n申请条件包括：\n1. 本地户籍或居住证\n2. 注册满1年的企业\n3. 无不良信用记录\n\n具体条件请咨询相关部门。"
        elif intent == "申请查询":
            answer = f"关于申请流程：{query}\n\n申请步骤：\n1. 准备身份证、营业执照等材料\n2. 到政务服务中心提交申请\n3. 等待审核（5-10个工作日）\n4. 审核通过后领取补贴\n\n咨询电话：12345"
        else:
            answer = f"关于您的咨询：{query}\n\n抱歉，暂时无法直接回答。请提供更多详细信息或拨打服务热线：12345"

        data["answer"] = answer
        print(f"  [{self.name}] 生成答案完成")
        return data


async def main():
    """主函数"""
    print("=" * 60)
    print("简化版Agent演示（不依赖AutoGen）")
    print("=" * 60)

    # 创建Agent管理器
    manager = AgentManager()

    # 注册Agent
    manager.register(SimpleQueryAgent())
    manager.register(SimpleAnswerAgent())

    # 创建处理流水线
    manager.create_pipeline("qa_pipeline", [
        "query_analyzer",
        "answer_generator"
    ])

    # 启动所有Agent
    await manager.start_all()

    # 测试查询
    test_queries = [
        "我想了解创业补贴政策",
        "申请补贴需要什么条件？",
        "怎么申请创业补贴？",
        "个人培训有什么补贴吗？"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n【查询 {i}】")
        print(f"用户：{query}")
        print("-" * 40)

        # 运行流水线
        result = await manager.run_pipeline("qa_pipeline", {"query": query})

        # 输出答案
        print(f"\n回答：")
        print(result.get("answer", "抱歉，无法生成答案"))
        print(f"\n处理时间：{result.get('processing_time', 0):.3f} 秒")

    # 显示状态
    print("\n" + "=" * 60)
    print("Agent状态")
    print("=" * 60)
    status = manager.get_status()
    for name, info in status["modules"].items():
        print(f"\n{name}:")
        print(f"  - 处理次数：{info['metrics']['processed_count']}")
        print(f"  - 错误次数：{info['metrics']['error_count']}")
        print(f"  - 平均时间：{info['avg_time']:.3f} 秒")

    # 停止管理器
    await manager.stop_all()
    print("\n演示完成！")


if __name__ == "__main__":
    asyncio.run(main())