"""Separate AutoGen's tool-decision stream from confirmed assistant answers."""

from __future__ import annotations

import re

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    ModelClientStreamingChunkEvent,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
)

from app.agents.service.progress import emit_progress


_TOOL_CONTROL = re.compile(r"<\s*/?\s*tool_call\b|<\|(?:tool_call|im_start|im_end)\b", re.IGNORECASE)


class AgentChatAnswerStream:
    """Release only confirmed text or the SDK's final, tool-disabled reflection."""

    def __init__(self, *, reflect_on_tool_use: bool, max_tool_iterations: int) -> None:
        self._reflect_on_tool_use = reflect_on_tool_use
        self._max_tool_iterations = max_tool_iterations
        self._tool_rounds = 0
        self._pending_tools: dict[str, str] = {}
        self._reflection_source: str | None = None
        self.text = ""
        self.chunk_count = 0

    def consume(self, event: BaseAgentEvent | BaseChatMessage | TaskResult) -> str | None:
        """Observe a native event and return at most one real answer fragment."""
        if isinstance(event, ToolCallRequestEvent):
            self._reflection_source = None
            self.text = ""
            self._tool_rounds += 1
            for call in event.content:
                self._pending_tools[call.id] = call.name
                emit_progress("tool_started", tool_call_id=call.id, name=call.name)
        elif isinstance(event, ToolCallExecutionEvent):
            had_pending = bool(self._pending_tools)
            for result in event.content:
                self._pending_tools.pop(result.call_id, None)
                emit_progress("tool_finished", tool_call_id=result.call_id, name=result.name,
                              status="error" if result.is_error else "completed")
            # AutoGen 0.7.5 enables tool_choice="none" only in this final reflection.
            # Earlier model calls may still emit another tool decision as string chunks.
            if (had_pending and not self._pending_tools and self._reflect_on_tool_use
                    and self._tool_rounds == self._max_tool_iterations):
                self._reflection_source = event.source
        elif isinstance(event, ModelClientStreamingChunkEvent):
            if event.content and event.source == self._reflection_source:
                self.chunk_count += 1
                return event.content
        else:
            messages = reversed(event.messages) if isinstance(event, TaskResult) else (event,)
            for message in messages:
                if isinstance(message, TextMessage) and message.source != "user" and not message.source.startswith("user_"):
                    self._reflection_source = None
                    content = message.content.strip()
                    if _TOOL_CONTROL.search(content):
                        raise ValueError("AgentChat produced tool control text instead of an answer")
                    self.text = content
                    if content and self.chunk_count == 0:
                        self.chunk_count += 1
                        return content
                    break
        return None

    def finish_pending(self, status: str) -> None:
        """Close interrupted tool observations without replaying any operation."""
        for call_id, name in self._pending_tools.items():
            emit_progress("tool_finished", tool_call_id=call_id, name=name, status=status)
        self._pending_tools.clear()
