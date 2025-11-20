"""AgentChat Team: UserProxy + Router Assistant with tools."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import uuid4

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage, ModelClientStreamingChunkEvent
from autogen_core.model_context import BufferedChatCompletionContext

from app.agents.framework.common import autogen_memory_store
from app.models.base import FinalAnswer


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
        model_client,
        knowledge_tool: Callable[[str], Any],
        graph_tool: Callable[[str], Any],
        rule_tool: Callable[[str], Any],
        text2sql_tool: Callable[[str], Any],
        workflow_tool: Callable[[str], Any],
        memory_buffer_size: int = 10,
    ) -> None:
        self._model_client = model_client
        self._make_tools = [knowledge_tool, graph_tool, rule_tool, text2sql_tool, workflow_tool]
        self._buffer_size = memory_buffer_size
        self._teams: Dict[str, RoundRobinGroupChat] = {}
        self._reflect_on_tool_use = os.getenv("AGENTCHAT_REFLECT", "").lower() in {"1", "true", "yes", "on"}
        self._max_tool_iterations = int(os.getenv("AGENTCHAT_MAX_TOOL_ITERATIONS", "1") or "1")

    async def _build_context(self, session_id: str) -> BufferedChatCompletionContext:
        try:
            return await autogen_memory_store.build_buffered_context(session_id, buffer_size=self._buffer_size)
        except Exception:
            return BufferedChatCompletionContext(buffer_size=self._buffer_size)

    async def _ensure_team(self, session_id: str) -> RoundRobinGroupChat:
        # Agent 名称必须是合法的 python identifier，简单清洗 session_id
        safe_id = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in session_id)
        if not safe_id or safe_id[0].isdigit():
            safe_id = f"sess_{safe_id}"

        team = self._teams.get(safe_id)
        if team:
            return team

        ctx = await self._build_context(session_id)

        router = AssistantAgent(
            name=f"router_{safe_id}",
            system_message=self.SYSTEM_PROMPT,
            model_client=self._model_client,
            tools=self._make_tools,
            model_context=ctx,
            reflect_on_tool_use=self._reflect_on_tool_use,
            max_tool_iterations=max(1, self._max_tool_iterations),
        )

        # 禁止在后端终端里等待人工输入，API 场景下直接返回空串
        user = UserProxyAgent(
            name=f"user_{safe_id}",
            description="api_user",
            input_func=lambda prompt: "",
        )

        team = RoundRobinGroupChat(participants=[user, router], max_turns=2)
        self._teams[safe_id] = team
        return team

    async def run(self, session_id: str, query: str) -> Tuple[Optional[FinalAnswer], Dict[str, Any]]:
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
        traces = self._extract_tool_traces(result.messages)
        debug["tool_traces"] = traces
        if traces.get("primary_tool"):
            debug["primary_tool"] = traces["primary_tool"]

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
            metadata={
                "route": "agentchat_team",
                "agentchat_stop_reason": result.stop_reason,
                "agentchat_tool": traces.get("primary_tool"),
            },
            total_processing_time=0.0,
        )
        return final, debug

    def _extract_tool_traces(self, messages) -> Dict[str, Any]:
        traces: Dict[str, Any] = {"calls": [], "count": 0}
        for msg in messages:
            name = getattr(msg, "tool_name", None) or getattr(msg, "__class__", None)
            text = str(msg)
            if isinstance(name, str) and "Tool" in name:
                traces["calls"].append(text)
                traces["count"] += 1
            elif "tool" in text.lower():
                traces["calls"].append(text)
                traces["count"] += 1
            if not traces.get("primary_tool"):
                candidate = None
                if isinstance(name, str):
                    candidate = name
                else:
                    m = re.search(r"tool_name='([^']+)'", text)
                    if m:
                        candidate = m.group(1)
                if candidate and "tool" in candidate:
                    traces["primary_tool"] = candidate
        return traces

    async def run_stream(self, session_id: str, query: str):
        t0 = time.perf_counter()
        team = await self._ensure_team(session_id)
        debug: Dict[str, Any] = {"agentchat_team": True, "memory_key": session_id}
        final_content: list[str] = []
        meta: Dict[str, Any] = {}
        try:
            stream = team.run_stream(task=TextMessage(content=query, source="user"))
            async for evt in stream:
                if isinstance(evt, ModelClientStreamingChunkEvent):
                    chunk = evt.content or ""
                    if chunk:
                        final_content.append(chunk)
                        yield {"type": "chunk", "content": chunk}
                if primary_tool is None and hasattr(evt, "tool_name"):
                    primary_tool = getattr(evt, "tool_name", None)
        except Exception as exc:
            debug["error"] = str(exc)
            debug["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            yield {
                "type": "final",
                "answer": FinalAnswer(
                    query_id=uuid4(),
                    answer="抱歉，当前流式问答失败，请稍后再试。",
                    sources=[],
                    confidence=0.2,
                    verification_passed=False,
                    metadata={"route": "agentchat_team_error", "agentchat_meta": debug},
                ),
                "meta": debug,
            }
            return

        if final_content:
            joined = "".join(final_content).strip()
            meta_final = {
                "agentchat_team": True,
                "memory_key": session_id,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "stream_chunks": len(final_content),
                "primary_tool": primary_tool,
            }
            full_final = FinalAnswer(
                query_id=uuid4(),
                answer=joined or "抱歉，目前未能生成有效答复。",
                sources=[],
                confidence=0.5,
                verification_passed=False,
                metadata={
                    "route": "agentchat_team_stream",
                    "agentchat_meta": meta_final,
                    "agentchat_tool": primary_tool,
                },
            )
            yield {"type": "final", "answer": full_final, "meta": meta_final}
        else:
            try:
                full_final, meta_full = await self.run(session_id, query)
                meta_full["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                meta_full["stream_chunks"] = len(final_content)
                meta_full["memory_key"] = session_id
                if primary_tool:
                    meta_full["primary_tool"] = primary_tool
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
