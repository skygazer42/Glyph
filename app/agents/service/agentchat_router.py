"""AutoGen AgentChat Router Assistant (single assistant with tools)."""

from __future__ import annotations

import os
import logging
import asyncio
from app.utils.lifecycle import close_with_timeout
import time
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import uuid4

from autogen_agentchat.base import TaskResult
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage, ModelClientStreamingChunkEvent, ToolCallRequestEvent, ToolCallExecutionEvent

from app.agents.framework.common import autogen_memory_store
from app.models.base import FinalAnswer


logger = logging.getLogger(__name__)


class AgentChatRouter:
    SYSTEM_PROMPT = (
        "你是政策问答的工具调度助手，必须选择唯一工具并直接给出答案：\n"
        " knowledge_tool（政策内容/流程/依据）；graph_tool（关系/对比/多文档融合）；"
        " rule_tool（补贴资格/金额计算）；text2sql_tool（数据库查询）；"
        " workflow_tool（多模态/档案/流程协作）。\n"
        "优先使用 knowledge_tool 进行政策解读/流程；只有在用户提供金额/价格/能效等计算要素时才用 rule_tool；"
        "graph_tool 适用于政策关系/比较/串讲类问题；text2sql 仅用于显式数据库/表字段查询，workflow 仅用于多模态/档案处理。\n"
        "调用后整理简洁答案（金额/条件/流程要点），失败时说明原因并给出下一步建议。"
    )

    def __init__(
        self,
        *,
        model_client,
        knowledge_tool: Callable[[str], Any],
        graph_tool: Callable[[str], Any],
        rule_tool: Callable[[str], Any],
        text2sql_tool: Callable[[str], Any],
        workflow_tool: Callable[[str], Any],
        memory_buffer_size: int = 10,
    ) -> None:
        self._model_client = model_client
        self._tools = {
            "knowledge_tool": knowledge_tool,
            "graph_tool": graph_tool,
            "rule_tool": rule_tool,
            "text2sql_tool": text2sql_tool,
            "workflow_tool": workflow_tool,
        }
        self._buffer_size = memory_buffer_size
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._agents: Dict[str, AssistantAgent] = {}
        self._reflect_on_tool_use = os.getenv("AGENTCHAT_REFLECT", "").lower() in {"1", "true", "yes", "on"}
        self._max_tool_iterations = int(os.getenv("AGENTCHAT_MAX_TOOL_ITERATIONS", "1"))
        if self._max_tool_iterations < 1:
            raise ValueError("AGENTCHAT_MAX_TOOL_ITERATIONS must be positive")

    async def _get_or_create_agent(self, session_id: str) -> AssistantAgent:
        agent = self._agents.get(session_id)
        if agent is not None:
            return agent

        # Agent 名称必须是合法的 python identifier，简单清洗 session_id
        safe_id = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in session_id)
        if not safe_id or safe_id[0].isdigit():
            safe_id = f"sess_{safe_id}"

        model_context = await autogen_memory_store.build_buffered_context(session_id, buffer_size=self._buffer_size)
        agent = AssistantAgent(
            name=f"router_{safe_id}",
            system_message=self.SYSTEM_PROMPT,
            model_client=self._model_client,
            tools=[*self._tools.values()],
            model_context=model_context,
            reflect_on_tool_use=self._reflect_on_tool_use,
            max_tool_iterations=self._max_tool_iterations,
            model_client_stream=True,
        )
        self._agents[session_id] = agent
        return agent

    async def run(self, session_id: str, query: str) -> Tuple[Optional[FinalAnswer], Dict[str, Any]]:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            started_at = time.perf_counter()
            agent = await self._get_or_create_agent(session_id)
            debug_meta: Dict[str, Any] = {"agentchat": True, "memory_key": session_id}
            try:
                result = await agent.run(task=query)
            except Exception as exc:
                logger.exception("AgentChat request failed")
                debug_meta["error"] = str(exc)
                debug_meta["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
                return None, debug_meta

            debug_meta["stop_reason"] = result.stop_reason
            debug_meta["duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            debug_meta["message_count"] = len(result.messages)
            traces = self._extract_tool_traces(result.messages)
            debug_meta["tool_traces"] = traces
            if traces.get("primary_tool"):
                debug_meta["primary_tool"] = traces["primary_tool"]

            content = ""
            for msg in reversed(result.messages):
                if isinstance(msg, TextMessage) and msg.source != "user":
                    content = msg.content.strip()
                    break

            if not content:
                debug_meta["error"] = "AgentChat completed without an assistant answer"
                return None, debug_meta

            final = FinalAnswer(
                query_id=uuid4(),
                answer=content,
                sources=[],
                confidence=0.5,
                verification_passed=False,
                metadata={
                    "route": "agentchat",
                    "agentchat_stop_reason": result.stop_reason,
                    "agentchat_tool": traces.get("primary_tool"),
                },
                total_processing_time=0.0,
            )
            return final, debug_meta

    def _extract_tool_traces(self, messages) -> Dict[str, Any]:
        calls: list[str] = []
        for message in messages:
            if isinstance(message, (ToolCallRequestEvent, ToolCallExecutionEvent)):
                calls.extend(item.name for item in message.content)
        return {"calls": calls, "count": len(calls), "primary_tool": calls[0] if calls else None}

    async def run_stream(self, session_id: str, query: str):
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            started_at = time.perf_counter()
            agent = await self._get_or_create_agent(session_id)
            meta: Dict[str, Any] = {"agentchat": True, "memory_key": session_id}
            chunks: list[str] = []
            events = []
            result = None
            stream = agent.run_stream(task=query)
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
                metadata={"route": "agentchat_error" if failed else "agentchat_stream",
                          "agentchat_meta": meta, "agentchat_tool": meta["primary_tool"]})
            yield {"type": "final", "answer": final, "meta": meta}


def agentchat_enabled() -> bool:
    return os.getenv("AGENTCHAT_ENABLED", "").lower() in {"1", "true", "yes", "on"}


__all__ = ["AgentChatRouter", "agentchat_enabled"]
