"""Translate the consultation service into official AG-UI protocol events."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ag_ui.core import (
    PROTOCOL_VERSION,
    BaseEvent,
    CustomEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from app.agents.service.progress import capture_progress
from app.api.schemas import ChatStreamRequest
from app.models.policy import Attachment
from app.utils.lifecycle import close_with_timeout

if TYPE_CHECKING:
    from app.agents.framework.common.session_manager import SessionManager
    from app.agents.service.agent_service import AgentService
    from app.core.access import ChatSessionKey

logger = logging.getLogger(__name__)
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
HEARTBEAT_SECONDS = 15


class AGUIStreamingResponse(StreamingResponse):
    """Close the owned event generator even when ASGI send fails at a yield."""

    def __init__(
        self, content: AsyncGenerator[str, None], *, media_type: str, headers: Mapping[str, str]
    ) -> None:
        super().__init__(content, media_type=media_type, headers=headers)
        self._events = content

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await close_with_timeout(self._events.aclose)


class ConsultationOptions(BaseModel):
    """The supported application fields within standard forwardedProps."""

    model_config = ConfigDict(extra="forbid", strict=True)

    connection_id: int | None = None
    user_id: str | None = None
    text2sql_mode: bool = False
    attachments: list[Attachment] | None = None


def consultation_request(input_data: RunAgentInput) -> ChatStreamRequest:
    """Use only the latest user text; history and authority remain server-owned."""
    if not RUN_ID_PATTERN.fullmatch(input_data.run_id):
        raise HTTPException(status_code=422, detail="运行标识格式不正确")
    if not input_data.thread_id or len(input_data.thread_id) > 2048:
        raise HTTPException(status_code=422, detail="会话标识格式不正确")
    if input_data.tools or input_data.context or input_data.state or input_data.resume:
        raise HTTPException(status_code=422, detail="当前咨询不接受客户端工具、状态或上下文覆盖")
    if not input_data.messages or input_data.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="请提供本轮用户问题")
    content = input_data.messages[-1].content
    if not isinstance(content, str) or not content.strip() or len(content) > 10000:
        raise HTTPException(status_code=422, detail="用户问题须为 1 至 10000 字的文本，附件请使用上传入口")
    try:
        options = ConsultationOptions.model_validate(
            {} if input_data.forwarded_props is None else input_data.forwarded_props
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="咨询选项格式不正确或包含不支持的字段") from exc
    return ChatStreamRequest(
        message=content, session_id=input_data.thread_id, **options.model_dump()
    )


def _answer_metadata(metadata: dict[str, Any], *, is_staff: bool) -> dict[str, Any]:
    """Expose presentation fields, without internal session or provider traces."""
    fields = {
        "route", "route_display", "sources", "inputs", "engine_result", "rule_id",
        "domain_context", "verification", "verification_status", "timings_ms",
    }
    if is_staff:
        fields.update({"sql", "rows", "columns", "visualization", "visualization_type"})
    return {key: value for key, value in metadata.items() if key in fields}


async def stream_agui_events(
    input_data: RunAgentInput,
    request: ChatStreamRequest,
    session_key: ChatSessionKey,
    session_manager: SessionManager,
    agent_service: AgentService,
    *,
    allow_private_tools: bool,
) -> AsyncIterator[BaseEvent]:
    """Own one service task, forwarding real progress and cancelling it on close."""
    yield RunStartedEvent(
        thread_id=input_data.thread_id, run_id=input_data.run_id,
        protocol_version=PROTOCOL_VERSION,
    )
    worker: asyncio.Task[None] | None = None
    message_id = f"answer_{uuid4().hex}"
    text_started = False
    text_received = False
    final = None
    steps: dict[str, str] = {}
    tools: set[str] = set()
    try:
        session = await run_in_threadpool(
            session_manager.get_or_create_session, session_key.storage_id,
            connection_id=request.connection_id, user_id=request.user_id,
        )
        user_metadata: dict[str, Any] = {"connection_id": request.connection_id}
        if request.user_id is not None:
            user_metadata["user_id"] = request.user_id
        if request.attachments:
            user_metadata["attachments"] = [item.model_dump() for item in request.attachments]
        await run_in_threadpool(
            session_manager.add_message, session.session_id, "user", request.message,
            metadata=user_metadata,
        )
        yield CustomEvent(name="glyph.session", value={"session_id": session_key.client_id})

        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def receive_progress(event: dict[str, Any]) -> None:
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            item = ("progress", dict(event))
            if current is loop:
                queue.put_nowait(item)
            elif not loop.is_closed():
                loop.call_soon_threadsafe(queue.put_nowait, item)

        async def run_service() -> None:
            try:
                with capture_progress(receive_progress):
                    stream = agent_service.process_query_stream(
                        request.message, session_id=session.session_id,
                        user_id=request.user_id, connection_id=request.connection_id,
                        attachments=request.attachments, force_text2sql=request.text2sql_mode,
                        allow_private_tools=allow_private_tools,
                    )
                    try:
                        async for event in stream:
                            queue.put_nowait(("service", event))
                    finally:
                        await close_with_timeout(stream.aclose)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AG-UI consultation execution failed")
                queue.put_nowait(("error", {}))
            finally:
                queue.put_nowait(("closed", {}))

        worker = asyncio.create_task(run_service())
        while True:
            try:
                kind, event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield CustomEvent(name="glyph.heartbeat", value={})
                continue
            if kind == "closed":
                break
            if kind == "error":
                raise RuntimeError("Consultation execution failed")
            event_type = event["type"]
            if kind == "progress":
                if event_type == "step_started":
                    name, label = event["name"], event["label"]
                    if name not in steps:
                        steps[name] = label
                        yield StepStartedEvent(step_name=label, metadata={"name": name})
                elif event_type == "step_finished":
                    label = steps.pop(event["name"], None)
                    if label is not None:
                        yield StepFinishedEvent(step_name=label, metadata={
                            "name": event["name"], "status": event.get("status", "completed"),
                        })
                elif event_type == "tool_started":
                    call_id = event["tool_call_id"]
                    if call_id not in tools:
                        tools.add(call_id)
                        yield ToolCallStartEvent(tool_call_id=call_id, tool_call_name=event["name"])
                elif event_type == "tool_finished":
                    call_id = event["tool_call_id"]
                    if call_id in tools:
                        tools.remove(call_id)
                        status = event.get("status", "completed")
                        yield ToolCallEndEvent(tool_call_id=call_id, metadata={
                            "status": status,
                        })
                        completion = {
                            "completed": "工具执行已完成",
                            "cancelled": "工具执行已停止",
                        }.get(status, "工具执行未完成")
                        yield ToolCallResultEvent(
                            message_id=f"tool_result_{uuid4().hex}", tool_call_id=call_id,
                            content=completion, role="tool", metadata={"status": status},
                        )
                elif event_type == "sources":
                    yield CustomEvent(name="glyph.sources", value={"sources": event["sources"]})
                continue
            if event_type == "chunk" and event["content"]:
                if not text_started:
                    yield TextMessageStartEvent(message_id=message_id, role="assistant")
                    text_started = True
                text_received = True
                yield TextMessageContentEvent(message_id=message_id, delta=event["content"])
            elif event_type == "final":
                if final is not None:
                    raise RuntimeError("Consultation returned multiple final answers")
                final = event["answer"]

        await worker
        if final is None or not final.answer.strip() or str(final.metadata.get("route", "")).endswith("_error"):
            raise RuntimeError("Consultation completed without a successful answer")
        for call_id in tools:
            yield ToolCallEndEvent(tool_call_id=call_id, metadata={"status": "error"})
            yield ToolCallResultEvent(
                message_id=f"tool_result_{uuid4().hex}", tool_call_id=call_id,
                content="工具未返回执行结果", role="tool", metadata={"status": "error"},
            )
        tools.clear()
        if not text_started:
            yield TextMessageStartEvent(message_id=message_id, role="assistant")
        if not text_received:
            yield TextMessageContentEvent(message_id=message_id, delta=final.answer)
        yield TextMessageEndEvent(message_id=message_id)
        await run_in_threadpool(
            session_manager.add_message, session.session_id, "assistant", final.answer,
            metadata=final.metadata,
        )
        metadata = _answer_metadata(final.metadata, is_staff=allow_private_tools)
        metadata.update({"confidence": final.confidence, "session_id": session_key.client_id})
        yield CustomEvent(name="glyph.answer", value={
            "content": final.answer, "metadata": metadata, "session_id": session_key.client_id,
        })
        yield RunFinishedEvent(thread_id=input_data.thread_id, run_id=input_data.run_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("AG-UI consultation failed")
        for call_id in tools:
            yield ToolCallEndEvent(tool_call_id=call_id, metadata={"status": "error"})
            yield ToolCallResultEvent(
                message_id=f"tool_result_{uuid4().hex}", tool_call_id=call_id,
                content="工具执行未完成", role="tool", metadata={"status": "error"},
            )
        yield RunErrorEvent(message="咨询暂时未能完成，请稍后重试。", code="CONSULTATION_FAILED")
    finally:
        if worker is not None and not worker.done():
            worker.cancel()
        if worker is not None:
            with suppress(asyncio.CancelledError):
                await close_with_timeout(lambda: worker)
