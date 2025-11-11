"""GraphFlow-powered workflow agent for multimodal + policy tasks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import SourceMatchTermination
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_core.tools import FunctionTool
from typing_extensions import Annotated

from app.agents.pipeline.knowledge_agent import KnowledgeAgent
from app.agents.pipeline.rule_agent import RuleEngineAgent
from app.agents.service.tools import VisionTool, UserProfileTool
from app.core.llms import model_client
from app.models.base import Attachment, FinalAnswer


class WorkflowAgent:
    """Orchestrates a small GraphFlow to handle multimodal + policy workflows."""

    def __init__(
        self,
        *,
        vision_tool: VisionTool,
        knowledge_agent: KnowledgeAgent,
        rule_agent: RuleEngineAgent,
        user_profile_tool: UserProfileTool,
        max_turns: int = 12,
    ) -> None:
        self.vision_tool = vision_tool
        self.knowledge_agent = knowledge_agent
        self.rule_agent = rule_agent
        self.user_profile_tool = user_profile_tool
        self.model_client = model_client
        self.max_turns = max_turns

    async def answer(
        self,
        query: str,
        *,
        attachments: Optional[List[Attachment]] = None,
        intent: Optional[Dict[str, Any]] = None,
    ) -> FinalAnswer:
        attachments = attachments or []
        context: Dict[str, Any] = {
            "vision_summary": "",
            "knowledge_result": None,
            "rule_result": None,
            "user_profile": None,
        }

        flow = self._build_flow(context, attachments, intent)
        last_message: Optional[BaseChatMessage] = None

        try:
            async for event in flow.run_stream(  # type: ignore[attr-defined]
                task=self._build_task_prompt(query, attachments)
            ):
                if isinstance(event, BaseChatMessage):
                    last_message = event
        except Exception as exc:  # pragma: no cover - defensive
            # 回退：若 GraphFlow 失败，直接返回兜底答案
            return self._fallback_answer(query, f"GraphFlow 执行异常：{exc}")

        final = self._select_final_answer(
            query,
            last_message,
            context["knowledge_result"],
            context["rule_result"],
            context["user_profile"],
        )
        metadata = final.metadata or {}
        workflow_meta = metadata.get("workflow") or {}
        if context["vision_summary"]:
            workflow_meta["vision_summary"] = context["vision_summary"]
        if context["knowledge_result"]:
            workflow_meta["knowledge_routed"] = True
        if context["rule_result"]:
            workflow_meta["rule_routed"] = True
        if context["user_profile"]:
            workflow_meta["user_profile_requested"] = True
            workflow_meta["user_profile_found"] = context["user_profile"].get("found")
        workflow_meta["graph_flow"] = True
        metadata["workflow"] = workflow_meta
        if metadata.get("route") and metadata["route"] != "workflow":
            metadata["downstream_route"] = metadata["route"]
        metadata["route"] = "workflow"
        final.metadata = metadata
        return final

    def _build_flow(
        self,
        context: Dict[str, Any],
        attachments: List[Attachment],
        intent: Optional[Dict[str, Any]],
    ) -> GraphFlow:
        builder = DiGraphBuilder()
        participants: List[AssistantAgent] = []
        previous_agent: Optional[AssistantAgent] = None

        # 工具闭包
        async def extract_image_facts(
            instruction: Annotated[str, "Describe what to inspect from the images."],
        ) -> str:
            summary = await self.vision_tool.describe(instruction, attachments)
            context["vision_summary"] = summary
            return summary or "未能识别出有效的视觉信息，请根据现有文本继续。"

        async def query_policy_knowledge(
            question: Annotated[str, "Policy question that需要知识检索"],
        ) -> str:
            result = await self.knowledge_agent.answer(question, intent=intent)
            context["knowledge_result"] = result
            return result.answer

        async def execute_rule_engine(
            requirement: Annotated[str, "包含计算所需关键信息的描述"],
        ) -> str:
            result = await self.rule_agent.compute(requirement, intent=intent)
            context["rule_result"] = result
            return result.answer

        if attachments and self.vision_tool.enabled:
            vision_agent = AssistantAgent(
                "vision_analyzer",
                model_client=self.model_client,
                system_message="你负责读取用户提供的图片。务必调用 extract_image_facts 工具，并仅在获取结果后将要点告知下游。",
                tools=[FunctionTool(extract_image_facts, description="解析用户上传的图片并输出关键信息。")],
                max_tool_iterations=2,
            )
            builder.add_node(vision_agent)
            participants.append(vision_agent)
            previous_agent = vision_agent

        async def fetch_user_profile(
            user_id: Annotated[str, "需要查询的用户唯一ID"],
        ) -> str:
            profile = await self.user_profile_tool.fetch(user_id.strip())
            context["user_profile"] = profile
            return self.user_profile_tool.format_profile(profile)

        router_tools = [
            FunctionTool(query_policy_knowledge, description="当需要检索政策或知识库信息时调用。"),
            FunctionTool(execute_rule_engine, description="当需要根据票据/参数计算优惠、折扣、补贴时调用。"),
            FunctionTool(fetch_user_profile, description="查询指定用户ID的历史、等级与最近活动。"),
        ]
        router_agent = AssistantAgent(
            "task_router",
            model_client=self.model_client,
            system_message=(
                "你负责根据现有信息决定下一步操作。可调用知识检索或规则计算工具，"
                "最多调用一次即可；若已有足够信息，请整理要点交给最终答复者。"
            ),
            tools=router_tools,
            max_tool_iterations=3,
        )
        builder.add_node(router_agent)
        participants.append(router_agent)
        if previous_agent:
            builder.add_edge(previous_agent, router_agent)
        previous_agent = router_agent

        answer_agent = AssistantAgent(
            "answer_composer",
            model_client=self.model_client,
            system_message=(
                "你是最终答复者。综合之前的视觉解析、用户历史资料、知识检索或规则计算结果，"
                "回答用户问题，列出关键结论与后续建议。对用户隐私保持谨慎，只输出任务相关信息。"
            ),
        )
        builder.add_node(answer_agent)
        if previous_agent:
            builder.add_edge(previous_agent, answer_agent)
        participants.append(answer_agent)

        graph = builder.build()
        termination = SourceMatchTermination(sources=[answer_agent.name])
        return GraphFlow(
            participants=participants,
            graph=graph,
            termination_condition=termination,
            max_turns=self.max_turns,
        )

    def _build_task_prompt(self, query: str, attachments: List[Attachment]) -> str:
        parts = [f"用户问题：{query}"]
        if attachments:
            refs = []
            for idx, att in enumerate(attachments, 1):
                ref = att.metadata.get("label") if att.metadata else None
                refs.append(ref or att.path or att.url or f"附件{idx}")
            parts.append("附件： " + ", ".join(refs))
        parts.append("请按图→工具→答复的顺序完成任务。")
        return "\n".join(parts)

    def _select_final_answer(
        self,
        query: str,
        last_message: Optional[BaseChatMessage],
        knowledge_result: Optional[FinalAnswer],
        rule_result: Optional[FinalAnswer],
        user_profile: Optional[Dict[str, Any]],
    ) -> FinalAnswer:
        if rule_result:
            return rule_result
        if knowledge_result:
            return knowledge_result
        if user_profile:
            profile_text = self.user_profile_tool.format_profile(user_profile)
            return FinalAnswer(
                query_id=uuid4(),
                answer=f"以下是该用户的历史资料：\n{profile_text}",
                sources=[],
                confidence=0.5 if user_profile.get("found") else 0.25,
                verification_passed=False,
                metadata={
                    "route": "workflow",
                    "origin": "user_profile",
                    "user_id": user_profile.get("user_id"),
                    "found": user_profile.get("found"),
                },
                total_processing_time=0.0,
            )
        if isinstance(last_message, TextMessage):
            return FinalAnswer(
                query_id=uuid4(),
                answer=last_message.content,
                sources=[],
                confidence=0.45,
                verification_passed=False,
                metadata={"route": "workflow", "origin": "graph_flow"},
                total_processing_time=0.0,
            )
        return self._fallback_answer(query, "GraphFlow 未生成有效答复。")

    def _fallback_answer(self, query: str, reason: str) -> FinalAnswer:
        return FinalAnswer(
            query_id=uuid4(),
            answer=f"暂时无法根据图片与问题生成答案。原因：{reason}",
            sources=[],
            confidence=0.2,
            verification_passed=False,
            metadata={"route": "workflow", "reason": reason, "query": query},
            total_processing_time=0.0,
        )


__all__ = ["WorkflowAgent"]
