"""AgentChat Team: UserProxy + Router Assistant with tools."""

from __future__ import annotations

import os
import logging
import asyncio
from collections.abc import AsyncIterator, Iterable
from app.utils.lifecycle import close_with_timeout
import time
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import uuid4

from autogen_agentchat.base import TaskResult
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage, ModelClientStreamingChunkEvent, ToolCallRequestEvent, ToolCallExecutionEvent
from autogen_core.models import ChatCompletionClient

from app.agents.framework.common import autogen_memory_store
from app.models.policy import FinalAnswer


logger = logging.getLogger(__name__)


class AgentChatTeam:
    SYSTEM_PROMPT = (
        "你是政策问答的工具调度助手，必须选择唯一工具并直接给出答案：\n"
        " knowledge_tool（政策内容/流程/依据）、graph_tool（关系/对比/多文档融合）、\n"
        " rule_tool（补贴资格/金额）、text2sql_tool（数据库查询）、workflow_tool（多模态/档案/流程协作）。\n"
        "政策解释/流程优先使用 knowledge_tool；关系/对比/串讲类问题用 graph_tool；仅当用户提供价格/能效/数量等可计算要素时才调用 rule_tool，"
        "text2sql 仅用于显式数据库/表字段问题，workflow 仅处理多模态或跨档案流程。\n"
        "调用后整理简洁答案（金额/条件/流程要点），失败时说明原因并给出下一步建议。"
    )

    def __init__(
        self,
        *,
        model_client: ChatCompletionClient,
        knowledge_tool: Callable[[str], Any],
        graph_tool: Callable[[str], Any],
        rule_tool: Callable[[str], Any],
        text2sql_tool: Callable[[str], Any],
        workflow_tool: Callable[[str], Any],
        memory_buffer_size: int = 10,
    ) -> None:
        self._model_client = model_client
        self._tools = [knowledge_tool, graph_tool, rule_tool, text2sql_tool, workflow_tool]
        self._buffer_size = memory_buffer_size
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._teams: Dict[str, RoundRobinGroupChat] = {}
        self._reflect_on_tool_use = os.getenv("AGENTCHAT_REFLECT", "").lower() in {"1", "true", "yes", "on"}
        self._max_tool_iterations = int(os.getenv("AGENTCHAT_MAX_TOOL_ITERATIONS", "1"))
        if self._max_tool_iterations < 1:
            raise ValueError("AGENTCHAT_MAX_TOOL_ITERATIONS must be positive")

    async def _get_or_create_team(self, session_id: str) -> RoundRobinGroupChat:
        # Agent 名称必须是合法的 python identifier，简单清洗 session_id
        safe_id = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in session_id)
        if not safe_id or safe_id[0].isdigit():
            safe_id = f"sess_{safe_id}"

        team = self._teams.get(session_id)
        if team is not None:
            return team

        model_context = await autogen_memory_store.build_buffered_context(session_id, buffer_size=self._buffer_size)

        router = AssistantAgent(
            name=f"router_{safe_id}",
            system_message=self.SYSTEM_PROMPT,
            model_client=self._model_client,
            tools=[*self._tools],
            model_context=model_context,
            reflect_on_tool_use=self._reflect_on_tool_use,
            max_tool_iterations=self._max_tool_iterations,
            model_client_stream=True,
        )

        # 禁止在后端终端里等待人工输入，API 场景下直接返回空串
        user = UserProxyAgent(
            name=f"user_{safe_id}",
            description="api_user",
            input_func=lambda prompt: "",
        )

        team = RoundRobinGroupChat(participants=[user, router], max_turns=2)
        self._teams[session_id] = team
        return team

    async def run(self, session_id: str, query: str) -> Tuple[Optional[FinalAnswer], Dict[str, Any]]:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            started_at = time.perf_counter()
            team = await self._get_or_create_team(session_id)
            debug: Dict[str, Any] = {"agentchat_team": True, "memory_key": session_id}
            try:
                result = await team.run(task=TextMessage(content=query, source="user"))
            except Exception as exc:
                logger.exception("AgentChat request failed")
                debug["error"] = str(exc)
                debug["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
                return None, debug

            debug["stop_reason"] = result.stop_reason
            debug["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            debug["message_count"] = len(result.messages)
            traces = self._extract_tool_traces(result.messages)
            debug["tool_traces"] = traces
            if traces.get("primary_tool"):
                debug["primary_tool"] = traces["primary_tool"]

            content = ""
            for msg in reversed(result.messages):
                if isinstance(msg, TextMessage) and msg.source != "user":
                    content = msg.content.strip()
                    break

            if not content:
                debug["error"] = "AgentChat completed without an assistant answer"
                return None, debug

            final = FinalAnswer(
                query_id=uuid4(),
                answer=content,
                sources=[],
                confidence=0.5,
                verification_passed=False,
                metadata={
                    "route": "agentchat_team",
                    "agentchat_stop_reason": result.stop_reason,
                    "agentchat_tool": traces.get("primary_tool"),
                },
                total_processing_time=0.0,
            )
            return final, debug

    @staticmethod
    def _extract_tool_traces(messages: Iterable[Any]) -> Dict[str, Any]:
        calls: list[str] = []
        for message in messages:
            if isinstance(message, (ToolCallRequestEvent, ToolCallExecutionEvent)):
                calls.extend(item.name for item in message.content)
        return {"calls": calls, "count": len(calls), "primary_tool": calls[0] if calls else None}

    async def run_stream(self, session_id: str, query: str) -> AsyncIterator[Dict[str, Any]]:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            started_at = time.perf_counter()
            team = await self._get_or_create_team(session_id)
            meta: Dict[str, Any] = {"agentchat_team": True, "memory_key": session_id}
            chunks: list[str] = []
            events = []
            result = None
            stream = team.run_stream(task=TextMessage(content=query, source="user"))
            try:
                try:
                    async for event in stream:
                        events.append(event)
                        if isinstance(event, TaskResult):
                            result = event
                        elif isinstance(event, ModelClientStreamingChunkEvent) and event.content:
                            chunks.append(event.content)
                            yield {"type": "chunk", "content": event.content}
                finally:
                    await close_with_timeout(stream.aclose)
            except Exception as exc:
                logger.exception("AgentChat request failed")
                meta["error"] = str(exc)
            meta["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            meta["stream_chunks"] = len(chunks)
            meta.update(self._extract_tool_traces(events))
            content = ""
            if result is not None:
                for message in reversed(result.messages):
                    if isinstance(message, TextMessage) and message.source != "user":
                        content = message.content.strip()
                        break
                meta["stop_reason"] = result.stop_reason
            if not content and chunks:
                content = "".join(chunks).strip()
            if not content:
                meta.setdefault("error", "AgentChat stream completed without an assistant answer")
            failed = "error" in meta
            final = FinalAnswer(query_id=uuid4(), answer=content or "抱歉，当前流式问答失败，请稍后再试。",
                sources=[], confidence=0.2 if failed else 0.5, verification_passed=False,
                metadata={"route": "agentchat_team_error" if failed else "agentchat_team_stream",
                          "agentchat_meta": meta, "agentchat_tool": meta["primary_tool"]})
            yield {"type": "final", "answer": final, "meta": meta}


def agentchat_team_enabled() -> bool:
    return os.getenv("AGENTCHAT_TEAM_ENABLED", "").lower() in {"1", "true", "yes", "on"}


__all__ = ["AgentChatTeam", "agentchat_team_enabled"]
