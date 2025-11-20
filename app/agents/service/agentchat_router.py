"""AutoGen AgentChat Router Assistant (single assistant with tools)."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import uuid4

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import ModelClientStreamingChunkEvent
from autogen_core.model_context import BufferedChatCompletionContext

from app.agents.framework.common import autogen_memory_store
from app.models.base import FinalAnswer


class AgentChatRouter:
    SYSTEM_PROMPT = (
        "你是政策问答的工具调度助手，必须选择唯一工具并直接给出答案：\n"
        " knowledge_tool（政策内容/流程/依据）；rule_tool（补贴资格/金额计算）；"
        " text2sql_tool（数据库查询）；workflow_tool（多模态/档案/流程协作）。\n"
        "优先使用 knowledge_tool 进行政策解读/流程；只有在用户提供金额/价格/能效等计算要素时才用 rule_tool；"
        "text2sql 仅用于显式数据库/表字段查询，workflow 仅用于多模态/档案处理。\n"
        "调用后整理简洁答案（金额/条件/流程要点），失败时说明原因并给出下一步建议。"
    )

    def __init__(
        self,
        *,
        model_client,
        knowledge_tool: Callable[[str], Any],
        rule_tool: Callable[[str], Any],
        text2sql_tool: Callable[[str], Any],
        workflow_tool: Callable[[str], Any],
        memory_buffer_size: int = 10,
    ) -> None:
        self._model_client = model_client
        self._make_tools = {
            "knowledge_tool": knowledge_tool,
            "rule_tool": rule_tool,
            "text2sql_tool": text2sql_tool,
            "workflow_tool": workflow_tool,
        }
        self._buffer_size = memory_buffer_size
        self._agents: Dict[str, AssistantAgent] = {}
        self._reflect_on_tool_use = os.getenv("AGENTCHAT_REFLECT", "").lower() in {"1", "true", "yes", "on"}
        self._max_tool_iterations = int(os.getenv("AGENTCHAT_MAX_TOOL_ITERATIONS", "1") or "1")

    async def _build_model_context(self, session_id: str) -> BufferedChatCompletionContext:
        try:
            return await autogen_memory_store.build_buffered_context(session_id, buffer_size=self._buffer_size)
        except Exception:
            return BufferedChatCompletionContext(buffer_size=self._buffer_size)

    async def _ensure_agent(self, session_id: str) -> AssistantAgent:
        agent = self._agents.get(session_id)
        if agent:
            return agent

        # Agent 名称必须是合法的 python identifier，简单清洗 session_id
        safe_id = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in session_id)
        if not safe_id or safe_id[0].isdigit():
            safe_id = f"sess_{safe_id}"

        model_context = await self._build_model_context(session_id)
        tools = list(self._make_tools.values())
        agent = AssistantAgent(
            name=f"router_{safe_id}",
            system_message=self.SYSTEM_PROMPT,
            model_client=self._model_client,
            tools=tools,
            model_context=model_context,
            reflect_on_tool_use=self._reflect_on_tool_use,
            max_tool_iterations=max(1, self._max_tool_iterations),
        )
        self._agents[session_id] = agent
        return agent

    async def run(self, session_id: str, query: str) -> Tuple[Optional[FinalAnswer], Dict[str, Any]]:
        t0 = time.perf_counter()
        agent = await self._ensure_agent(session_id)
        debug_meta: Dict[str, Any] = {"agentchat": True, "memory_key": session_id}
        try:
            result = await agent.run(task=query)
        except Exception as exc:
            debug_meta["error"] = str(exc)
            debug_meta["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            return None, debug_meta

        debug_meta["stop_reason"] = result.stop_reason
        debug_meta["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        debug_meta["message_count"] = len(result.messages)
        debug_meta["tool_traces"] = self._extract_tool_traces(result.messages)

        content = ""
        for msg in reversed(result.messages):
            maybe = getattr(msg, "content", None)
            if isinstance(maybe, str) and maybe.strip():
                content = maybe.strip()
                break

        final = FinalAnswer(
            query_id=uuid4(),
            answer=content or "抱歉，目前未能生成有效答复。",
            sources=[],
            confidence=0.5,
            verification_passed=False,
            metadata={"route": "agentchat", "agentchat_stop_reason": result.stop_reason},
            total_processing_time=0.0,
        )
        return final, debug_meta

    def _extract_tool_traces(self, messages) -> Dict[str, Any]:
        traces: Dict[str, Any] = {"calls": [], "count": 0}
        for msg in messages:
            name = getattr(msg, "type", None) or getattr(msg, "__class__", None)
            if isinstance(name, str) and "Tool" in name:
                traces["calls"].append(str(msg))
                traces["count"] += 1
        return traces

    async def run_stream(self, session_id: str, query: str):
        t0 = time.perf_counter()
        agent = await self._ensure_agent(session_id)
        debug_meta: Dict[str, Any] = {"agentchat": True, "memory_key": session_id}
        chunks: list[str] = []
        try:
            stream = agent.run_stream(task=query)
            async for evt in stream:
                if isinstance(evt, ModelClientStreamingChunkEvent):
                    chunk = (evt.content or "")
                    if chunk:
                        chunks.append(chunk)
                        yield {"type": "chunk", "content": chunk}
        except Exception as exc:
            debug_meta["error"] = str(exc)
            debug_meta["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            yield {
                "type": "final",
                "answer": FinalAnswer(
                    query_id=uuid4(),
                    answer="抱歉，当前流式问答失败，请稍后再试。",
                    sources=[],
                    confidence=0.2,
                    verification_passed=False,
                    metadata={"route": "agentchat_error", "agentchat_meta": debug_meta},
                ),
                "meta": debug_meta,
            }
            return

        if chunks:
            content = "".join(chunks).strip()
            meta_full = {
                "agentchat": True,
                "memory_key": session_id,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "stream_chunks": len(chunks),
            }
            final = FinalAnswer(
                query_id=uuid4(),
                answer=content or "抱歉，目前未能生成有效答复。",
                sources=[],
                confidence=0.5,
                verification_passed=False,
                metadata={"route": "agentchat_stream", "agentchat_meta": meta_full},
                total_processing_time=0.0,
            )
            yield {"type": "final", "answer": final, "meta": meta_full}
        else:
            # no chunk produced, fallback to non-stream
            final, meta_full = await self.run(session_id, query)
            meta_full["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            meta_full["stream_chunks"] = len(chunks)
            meta_full["memory_key"] = session_id
            yield {"type": "final", "answer": final, "meta": meta_full}


def agentchat_enabled() -> bool:
    return os.getenv("AGENTCHAT_ENABLED", "").lower() in {"1", "true", "yes", "on"}


__all__ = ["AgentChatRouter", "agentchat_enabled"]
