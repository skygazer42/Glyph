"""示例 AG Workflow：演示如何用 AutoGen 组装轻量团队。"""

import asyncio
from typing import Dict, Any, List, Optional
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import SingleThreadedAgentRuntime, MessageContext
import logging

from app.agents.ag_prompt import (
    POLICY_ANSWER_PROMPT,
    POLICY_COMPARATOR_PROMPT,
    POLICY_QUERY_ANALYZER_PROMPT,
    POLICY_RETRIEVER_PROMPT,
    POLICY_SELECTOR_PROMPT,
    POLICY_SUMMARY_PROMPT,
)
from app.core import logging_manager

logger = logging.getLogger(__name__)


class AGWorkflow:
    """使用 AutoGen 搭建的演示级 Workflow（原 AutoGenOrchestrator）。"""

    def __init__(self, model_client: OpenAIChatCompletionClient):
        self.model_client = model_client
        self.runtime = SingleThreadedAgentRuntime()
        self.agents: Dict[str, AssistantAgent] = {}
        self.teams: Dict[str, Any] = {}

    async def initialize(self):
        """初始化运行时"""
        await self.runtime.start()

    async def shutdown(self):
        """关闭运行时"""
        await self.runtime.stop()

    def add_agent(
        self,
        name: str,
        system_message: str,
        description: str = ""
    ) -> AssistantAgent:
        """添加Agent到编排器"""
        agent = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=system_message
        )
        self.agents[name] = agent
        logger.info(f"Added agent: {name}")
        return agent

    def create_round_robin_team(
        self,
        team_name: str,
        agent_names: List[str],
        max_turns: int = 10
    ) -> RoundRobinGroupChat:
        """创建轮询团队 - Agent按顺序轮流发言"""
        team_agents = [self.agents[name] for name in agent_names if name in self.agents]

        # 创建终止条件
        termination = MaxMessageTermination(max_messages=max_turns)

        # 创建轮询团队
        team = RoundRobinGroupChat(
            participants=team_agents,
            termination_condition=termination
        )

        self.teams[team_name] = team
        logger.info(f"Created round-robin team: {team_name}")
        return team

    def create_selector_team(
        self,
        team_name: str,
        agent_names: List[str],
        selector_prompt: str,
        max_turns: int = 20
    ) -> SelectorGroupChat:
        """创建选择器团队 - 智能选择下一个发言的Agent"""
        team_agents = [self.agents[name] for name in agent_names if name in self.agents]

        # 创建终止条件
        termination = TextMentionTermination("TERMINATE")

        # 创建选择器团队
        team = SelectorGroupChat(
            participants=team_agents,
            model_client=self.model_client,
            selector_prompt=selector_prompt,
            termination_condition=termination
        )

        self.teams[team_name] = team
        logger.info(f"Created selector team: {team_name}")
        return team

    async def run_team(
        self,
        team_name: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[TextMessage]:
        """运行团队"""
        if team_name not in self.teams:
            raise ValueError(f"Team {team_name} not found")

        team = self.teams[team_name]

        # 创建消息
        text_message = TextMessage(content=message, source="user")

        # 运行团队
        logging_manager.log_message_event(
            payload=message,
            sender="user",
            receiver=team_name,
        )

        message_stream = team.run_stream(task=text_message)

        messages = []
        try:
            async for item in message_stream:
                messages.append(item)
                logging_manager.log_message_event(
                    payload=item.content,
                    sender=item.source,
                    receiver=team_name,
                )
                logger.info("Message from %s: %s", item.source, item.content[:100])
        except Exception as exc:
            logging_manager.log_handler_exception(
                payload=message,
                handling_agent=team_name,
                exception=exc,
            )
            raise

        return messages

    async def create_policy_qa_team(self):
        """创建政策问答团队"""
        # 添加专门的政策Agent
        self.add_agent(
            name="query_analyzer",
            system_message=POLICY_QUERY_ANALYZER_PROMPT,
            description="分析用户查询意图",
        )

        self.add_agent(
            name="policy_retriever",
            system_message=POLICY_RETRIEVER_PROMPT,
            description="检索相关政策信息",
        )

        self.add_agent(
            name="answer_generator",
            system_message=POLICY_ANSWER_PROMPT,
            description="生成最终答案",
        )

        # 创建选择器团队，智能选择发言者
        self.create_selector_team(
            team_name="policy_qa",
            agent_names=["query_analyzer", "policy_retriever", "answer_generator"],
            selector_prompt=POLICY_SELECTOR_PROMPT,
        )

    async def create_comparison_team(self):
        """创建政策比较团队"""
        self.add_agent(
            name="policy_comparator",
            system_message=POLICY_COMPARATOR_PROMPT,
            description="比较不同政策",
        )

        self.add_agent(
            name="summary_generator",
            system_message=POLICY_SUMMARY_PROMPT,
            description="生成总结",
        )

        # 创建轮询团队
        self.create_round_robin_team(
            team_name="policy_comparison",
            agent_names=["policy_comparator", "summary_generator"],
            max_turns=6
        )


async def example_usage():
    """使用示例"""
    import os
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    # 创建模型客户端
    model_client = OpenAIChatCompletionClient(
        model="gpt-4",
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # 创建编排器
    orchestrator = AGWorkflow(model_client)
    await orchestrator.initialize()

    try:
        # 创建政策问答团队
        await orchestrator.create_policy_qa_team()

        # 测试查询
        test_query = "我想了解小微企业的创业补贴政策，需要什么条件？"

        print("=" * 60)
        print("AutoGen编排器演示")
        print("=" * 60)
        print(f"\n用户查询：{test_query}\n")

        # 运行团队
        messages = await orchestrator.run_team("policy_qa", test_query)

        # 打印结果
        print("\n对话过程：")
        for i, msg in enumerate(messages, 1):
            print(f"\n{i}. 【{msg.source}】")
            print(f"{msg.content}")

    finally:
        await orchestrator.shutdown()


# 高级编排示例 - 带有条件分支的复杂流程
class AdvancedOrchestrator:
    """高级编排器 - 支持条件分支和复杂流程"""

    def __init__(self, model_client: OpenAIChatCompletionClient):
        self.model_client = model_client
        self.runtime = SingleThreadedAgentRuntime()
        self.agents = {}
        self.workflows = {}

    async def create_conditional_workflow(self):
        """创建条件工作流"""
        # 创建路由Agent
        router = AssistantAgent(
            name="router",
            model_client=self.model_client,
            system_message="""你是路由Agent。根据用户问题，选择处理路径：
- 如果是补贴金额问题，路由到 calculation_path
- 如果是资格条件问题，路由到 eligibility_path
- 如果是申请流程问题，路由到 application_path
- 其他情况路由到 general_path

请回答路径名称。"""
        )

        # 创建不同的处理路径
        paths = {
            "calculation_path": ["subsidy_calculator", "answer_formatter"],
            "eligibility_path": ["eligibility_checker", "policy_matcher", "answer_formatter"],
            "application_path": ["process_guide", "document_checker", "answer_formatter"],
            "general_path": ["general_advisor", "answer_formatter"]
        }

        # 为每个路径创建团队
        for path_name, agent_names in paths.items():
            await self._create_path_team(path_name, agent_names)

        self.agents["router"] = router
        self.workflows = paths

    async def _create_path_team(self, path_name: str, agent_names: List[str]):
        """为特定路径创建团队"""
        # 这里简化实现，实际需要为每个路径创建专门的Agent
        for name in agent_names:
            if name not in self.agents:
                self.agents[name] = AssistantAgent(
                    name=name,
                    model_client=self.model_client,
                    system_message=f"你是{name}专家，专门处理相关任务。"
                )

    async def execute_workflow(self, user_query: str) -> Dict[str, Any]:
        """执行条件工作流"""
        # 1. 路由决策
        router = self.agents["router"]
        routing_message = TextMessage(
            content=f"用户问题：{user_query}\n请选择处理路径。",
            source="system"
        )

        # 获取路由决策
        # (这里需要实现路由决策逻辑)
        selected_path = "eligibility_path"  # 示例

        # 2. 执行选定的路径
        if selected_path in self.workflows:
            agent_names = self.workflows[selected_path]
            # 创建临时团队执行
            team = RoundRobinGroupChat(
                participants=[self.agents[name] for name in agent_names],
                termination_condition=MaxMessageTermination(max_messages=len(agent_names) * 2)
            )

            # 运行团队
            message_stream = team.run_stream(
                task=TextMessage(content=user_query, source="user")
            )

            results = []
            async for msg in message_stream:
                results.append(msg)

            return {
                "path": selected_path,
                "messages": results,
                "agent_sequence": agent_names
            }


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())
