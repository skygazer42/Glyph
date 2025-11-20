"""AgentChat Team orchestration (UserProxy + Router Assistant)."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import uuid4

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage, ModelClientStreamingChunkEvent
from autogen_core.model_context import BufferedChatCompletionContext

from app.agents.framework.common import autogen_memory_store
from app.config import settings
from app.models.base import FinalAnswer


class AgentChatTeam:
    """UserProxy -> Router Assistant (with tools) using AgentChat Team."""

    SYSTEM_PROMPT = (
        "你是政策问答工具调度助手，只做两件事：\n"
        "1) 判断应调用哪一个工具：knowledge_tool（内容/流程/依据）、rule_tool（补贴资格与金额计算）、"
        "text2sql_tool（数据库查询）、workflow_tool（多模态/档案/流程协作）。\n"
        "2) 调用后把工具结果整理成简洁答案，保留金额/条件/流程要点。\n"
        "失败时要明确说明原因并给出下一步建议，不要空回复。"
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
        self._make_tools = [knowledge_tool, rule_tool, text2sql_tool, workflow_tool]
        self._buffer_size = memory_buffer_size
        self._teams: Dict[str, RoundRobinGroupChat] = {}

    async def _build_context(self, session_id: str) -> BufferedChatCompletionContext:
        try:
            return await autogen_memory_store.build_buffered_context(
                session_id, buffer_size=self._buffer_size
            )
        except Exception:
            return BufferedChatCompletionContext(buffer_size=self._buffer_size)

    async def _ensure_team(self, session_id: str) -> RoundRobinGroupChat:
        team = self._teams.get(session_id)
        if team:
            return team

        ctx = await self._build_context(session_id)

        router = AssistantAgent(
            name=f"router-{session_id}",
            system_message=self.SYSTEM_PROMPT,
            model_client=self._model_client,
            tools=self._make_tools,
            model_context=ctx,
            reflect_on_tool_use=True,
            max_tool_iterations=2,
        )

        user = UserProxyAgent(name=f"user-{session_id}")

        team = RoundRobinGroupChat(
            participants=[user, router],
            max_turns=2,
        )
        self._teams[session_id] = team
        return team

    async def run(self, session_id: str, query: str) -> Tuple[Optional[FinalAnswer], Dict[str, Any]]:
        import time

        t0 = time.perf_counter()
        team = await self._ensure_team(session_id)
        debug: Dict[str, Any] = {"agentchat_team": True, "memory_key": session_id}
        try:
            result = await team.run(task=TextMessage(content=query, source="user"))
        except Exception as exc:
            debug["error"] = str(exc)
            debug["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            return None, debug

        debug["stop_reason"] = result.stop_reason
        debug["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        debug["message_count"] = len(result.messages)
        debug["tool_traces"] = self._extract_tool_traces(result.messages)

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
            metadata={"route": "agentchat_team", "agentchat_stop_reason": result.stop_reason},
            total_processing_time=0.0,
        )
        return final, debug

    def _extract_tool_traces(self, messages) -> Dict[str, Any]:
        traces: Dict[str, Any] = {"calls": [], "count": 0}
        for msg in messages:
            name = getattr(msg, "type", None) or getattr(msg, "__class__", None)
            if isinstance(name, str) and "Tool" in name:
                traces["calls"].append(str(msg))
                traces["count"] += 1
        return traces

    async def run_stream(self, session_id: str, query: str):
        """
        Streaming wrapper over RoundRobinGroupChat.run_stream.
        Yields dicts: {"type": "chunk", "content": "..."} and final {"type": "final", "answer": FinalAnswer, "meta": {...}}.
        """
        import time

        t0 = time.perf_counter()
        team = await self._ensure_team(session_id)
        debug: Dict[str, Any] = {"agentchat_team": True, "memory_key": session_id}
        final_content: List[str] = []
        meta: Dict[str, Any] = {}
        try:
            stream = team.run_stream(task=TextMessage(content=query, source="user"))
            async for evt in stream:
                if isinstance(evt, ModelClientStreamingChunkEvent):
                    chunk = evt.content or ""
                    if chunk:
                        final_content.append(chunk)
                        yield {"type": "chunk", "content": chunk}
                # TaskResult will come last; collect after loop
        except Exception as exc:
            debug["error"] = str(exc)
            meta.update(debug)
            yield {
                "type": "final",
                "answer": FinalAnswer(
                    query_id=uuid4(),
                    answer="抱歉，当前流式问答失败，请稍后再试。",
                    sources=[],
                    confidence=0.2,
                    verification_passed=False,
                    metadata={"route": "agentchat_team_error", "agentchat_meta": meta},
                ),
                "meta": meta,
            }
            return

        # 若有 chunk，直接拼接作为最终答案；否则跑一次非流式兜底
        if final_content:
            joined = "".join(final_content).strip()
            meta_final = {
                "agentchat_team": True,
                "memory_key": session_id,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "stream_chunks": len(final_content),
            }
            full_final = FinalAnswer(
                query_id=uuid4(),
                answer=joined or "抱歉，目前未能生成有效答复。",
                sources=[],
                confidence=0.5,
                verification_passed=False,
                metadata={"route": "agentchat_team_stream", "agentchat_meta": meta_final},
            )
            yield {"type": "final", "answer": full_final, "meta": meta_final}
        else:
            try:
                full_final, meta_full = await self.run(session_id, query)
                meta_full["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                meta_full["stream_chunks"] = len(final_content)
                meta_full["memory_key"] = session_id
                yield {"type": "final", "answer": full_final, "meta": meta_full}
            except Exception as exc:
                meta["error_fallback"] = str(exc)
                meta["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                meta["stream_chunks"] = len(final_content)
                yield {
                    "type": "final",
                    "answer": FinalAnswer(
                        query_id=uuid4(),
                        answer="抱歉，当前流式问答失败，请稍后再试。",
                        sources=[],
                        confidence=0.2,
                        verification_passed=False,
                        metadata={"route": "agentchat_team_error", "agentchat_meta": meta},
                    ),
                    "meta": meta,
                }


def agentchat_team_enabled() -> bool:
    return os.getenv("AGENTCHAT_TEAM_ENABLED", "").lower() in {"1", "true", "yes", "on"}


__all__ = ["AgentChatTeam", "agentchat_team_enabled"]
