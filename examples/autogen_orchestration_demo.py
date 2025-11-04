"""
AutoGen编排功能演示
展示AutoGen的各种编排模式
"""

import asyncio
import os
from typing import List

# AutoGen导入
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import SingleThreadedAgentRuntime

# 项目导入
from agents.coordination.coordinator import Coordinator
from agents.orchestrators.smart import SmartOrchestrator


async def demo_round_robin():
    """演示RoundRobin编排模式"""
    print("\n" + "="*60)
    print("1. RoundRobin 编排模式演示")
    print("="*60)

    # 创建模型客户端
    model_client = OpenAIChatCompletionClient(
        model="gpt-3.5-turbo",
        api_key=os.getenv("OPENAI_API_KEY", "sk-test")
    )

    # 创建Agent
    agents = [
        AssistantAgent(
            name="analyzer",
            model_client=model_client,
            system_message="你是分析专家。分析用户的问题并提取关键信息。"
        ),
        AssistantAgent(
            name="researcher",
            model_client=model_client,
            system_message="你是研究专家。基于分析结果研究相关政策。"
        ),
        AssistantAgent(
            name="summarizer",
            model_client=model_client,
            system_message="你是总结专家。总结研究结果并给出建议。完成后说'总结完毕'。"
        )
    ]

    # 创建RoundRobin团队
    team = RoundRobinGroupChat(
        participants=agents,
        termination_condition=TextMentionTermination("总结完毕")
    )

    # 运行团队
    task = TextMessage(
        content="我想了解创业补贴政策，特别是针对大学生的补贴。",
        source="user"
    )

    print("\n开始处理...")
    message_stream = team.run_stream(task=task)

    async for message in message_stream:
        print(f"\n【{message.source}】")
        print(message.content)


async def demo_selector_team():
    """演示Selector智能选择编排模式"""
    print("\n" + "="*60)
    print("2. Selector 智能选择编排模式演示")
    print("="*60)

    model_client = OpenAIChatCompletionClient(
        model="gpt-3.5-turbo",
        api_key=os.getenv("OPENAI_API_KEY", "sk-test")
    )

    # 创建专业Agent
    agents = [
        AssistantAgent(
            name="subsidy_expert",
            model_client=model_client,
            system_message="你是补贴政策专家。专门解答补贴金额、标准等问题。"
        ),
        AssistantAgent(
            name="eligibility_expert",
            model_client=model_client,
            system_message="你是资格条件专家。专门解答申请条件、资格要求等问题。"
        ),
        AssistantAgent(
            name="process_expert",
            model_client=model_client,
            system_message="你是流程专家。专门解答申请流程、材料准备等问题。"
        ),
        AssistantAgent(
            name="coordinator",
            model_client=model_client,
            system_message="你是协调员。负责总结并给出最终建议。完成后说'任务完成'。"
        )
    ]

    # 创建选择器提示
    selector_prompt = """请根据用户问题，选择最合适的专家回答：

1. 补贴金额、标准、范围 -> subsidy_expert
2. 申请条件、资格要求 -> eligibility_expert
3. 申请流程、材料准备 -> process_expert
4. 需要总结或协调 -> coordinator

请只回答专家的名字。"""

    # 创建选择器团队
    team = SelectorGroupChat(
        participants=agents,
        model_client=model_client,
        selector_prompt=selector_prompt,
        termination_condition=TextMentionTermination("任务完成")
    )

    # 测试不同类型的问题
    questions = [
        "创业补贴能申请多少钱？",
        "申请补贴需要什么条件？",
        "申请流程复杂吗？需要什么材料？"
    ]

    for question in questions:
        print(f"\n用户问题：{question}")
        print("-"*40)

        task = TextMessage(content=question, source="user")
        message_stream = team.run_stream(task=task)

        async for message in message_stream:
            print(f"\n【{message.source}】")
            print(message.content)
            if "任务完成" in message.content:
                break


async def demo_parallel_execution():
    """演示并行执行编排"""
    print("\n" + "="*60)
    print("3. 并行执行编排演示")
    print("="*60)

    # 使用项目中的SmartOrchestrator
    model_config = {
        "model": "gpt-3.5-turbo",
        "api_key": os.getenv("OPENAI_API_KEY", "sk-test")
    }

    orchestrator = SmartOrchestrator(
        model_config=model_config,
        vector_store_config={},
        logging_config={"level": "INFO"}
    )

    # 模拟并行处理
    from models.base import UserQuery, QueryIntent
    from datetime import datetime

    query = UserQuery(
        text="比较一下不同地区的创业补贴政策",
        timestamp=datetime.now()
    )

    print(f"\n用户查询：{query.text}")
    print("\n并行处理中...")

    # 这里应该调用orchestrator的并行处理方法
    # 由于需要完整的环境，这里只是演示概念
    print("\n并行任务：")
    print("1. 检索北京政策...")
    print("2. 检索上海政策...")
    print("3. 检索深圳政策...")
    print("\n并行执行完成，开始整合结果...")


async def demo_existing_coordinator():
    """演示项目中现有的协调器"""
    print("\n" + "="*60)
    print("4. 项目现有协调器演示")
    print("="*60)

    # 使用项目中的Coordinator
    llm_config = {
        "model": "gpt-3.5-turbo",
        "api_key": os.getenv("OPENAI_API_KEY", "sk-test")
    }

    # 这里需要完整的Agent实例，简化演示
    print("\n现有协调器特性：")
    print("1. 基于AutoGen GroupChat的多Agent协作")
    print("2. 支持动态Agent注册和发现")
    print("3. 智能路由和负载均衡")
    print("4. 会话状态管理")
    print("5. 错误处理和恢复机制")


async def demo_custom_workflow():
    """演示自定义工作流"""
    print("\n" + "="*60)
    print("5. 自定义工作流编排演示")
    print("="*60)

    # 创建运行时
    runtime = SingleThreadedAgentRuntime()
    await runtime.start()

    try:
        model_client = OpenAIChatCompletionClient(
            model="gpt-3.5-turbo",
            api_key=os.getenv("OPENAI_API_KEY", "sk-test")
        )

        # 定义工作流步骤
        workflow_steps = [
            ("intent_router", "识别用户意图"),
            ("policy_retriever", "检索相关政策"),
            ("policy_analyzer", "分析政策内容"),
            ("answer_generator", "生成最终答案")
        ]

        print("\n自定义工作流：")
        for step, description in workflow_steps:
            print(f"  {step} -> {description}")

        print("\n执行工作流...")

        # 模拟执行
        user_input = "小微企业能申请哪些补贴？"
        print(f"输入：{user_input}")

        for step, _ in workflow_steps:
            print(f"\n执行步骤：{step}")
            await asyncio.sleep(0.5)  # 模拟处理时间
            print(f"✓ {step} 完成")

        print("\n工作流执行完成！")

    finally:
        await runtime.stop()


async def main():
    """主函数 - 演示所有编排模式"""
    print("\nAutoGen 编排功能完整演示")
    print("="*60)

    # 1. RoundRobin模式
    # await demo_round_robin()

    # 2. Selector智能选择模式
    # await demo_selector_team()

    # 3. 并行执行模式
    await demo_parallel_execution()

    # 4. 现有协调器
    await demo_existing_coordinator()

    # 5. 自定义工作流
    await demo_custom_workflow()

    print("\n" + "="*60)
    print("演示完成！")
    print("="*60)

    print("\n总结：")
    print("1. AutoGen提供了丰富的编排模式：")
    print("   - RoundRobinGroupChat: 轮询执行")
    print("   - SelectorGroupChat: 智能选择")
    print("   - 自定义终止条件")
    print("   - 流式处理支持")
    print("\n2. 项目中的编排架构：")
    print("   - 基于AutoGen Core的Agent基类")
    print("   - 智能路由器(SmartOrchestrator)")
    print("   - 支持串行、并行、混合执行")
    print("   - 完善的状态管理")
    print("\n3. 使用建议：")
    print("   - 简单场景使用RoundRobin")
    print("   - 复杂场景使用Selector")
    print("   - 利用项目现有的编排器")
    print("   - 根据需要自定义工作流")


if __name__ == "__main__":
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)

    # 运行演示
    asyncio.run(main())