"""
Agent 问答相关端点
支持普通问答和 SSE 流式响应
"""

import json
import os
import logging
from pathlib import Path
from typing import Annotated
from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ChatStreamChunk,
    SessionInfo,
    SessionResponse,
    ListSessionsResponse,
    DeleteSessionResponse,
    SessionMessagesResponse,
    SessionMessagesQuery,
)
from app.api.deps import get_session_manager, get_agent_service
from app.api.agui import AGUIStreamingResponse, consultation_request, stream_agui_events
from app.api.endpoints.uploads import attachment_directory
from app.agents.framework.common.session_manager import SessionManager
from app.agents.service.agent_service import AgentService
from app.models.policy import Attachment
from app.core.access import ChatAccess, ChatSessionKey, get_chat_access, require_staff, resolve_chat_session
from app.utils.lifecycle import close_with_timeout

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_uploaded_attachment_paths(attachments: list[Attachment], access: ChatAccess) -> None:
    """检查附件属于当前身份的上传目录，或使用允许的远程地址协议；无效路径返回 400。"""
    upload_root = attachment_directory(access).resolve()
    for attachment in attachments:
        if not attachment.path:
            if not attachment.url or not attachment.url.lower().startswith(("http://", "https://", "data:image/", "oss://")):
                raise HTTPException(status_code=400, detail="请使用已上传的附件或有效的远程图片地址")
            continue
        try:
            path = Path(attachment.path).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="附件路径无效，请重新上传") from exc
        if not path.is_relative_to(upload_root) or not path.is_file():
            raise HTTPException(status_code=400, detail="附件不属于可用的上传文件")


def _resolve_request_session(request: ChatRequest | ChatStreamRequest, access: ChatAccess) -> ChatSessionKey:
    """拒绝公共访问使用工作人员专属字段，并解析身份命名空间内的会话键。"""
    if not access.is_staff and (
        request.connection_id is not None or request.text2sql_mode or request.user_id is not None
    ):
        raise HTTPException(status_code=403, detail="数据库查询与用户资料仅供已登录工作人员使用")
    return resolve_chat_session(access, request.session_id)


async def _prepare_chat_request(
    request: ChatRequest, access: ChatAccess = Depends(get_chat_access)
) -> ChatSessionKey:
    """解析普通聊天会话并在线程池校验附件路径，校验通过后返回会话键。"""
    session_key = _resolve_request_session(request, access)
    if request.attachments:
        await run_in_threadpool(_validate_uploaded_attachment_paths, request.attachments, access)
    return session_key


async def _prepare_stream_request(
    request: ChatStreamRequest, access: ChatAccess = Depends(get_chat_access)
) -> ChatSessionKey:
    """解析流式聊天会话并在线程池校验附件路径，响应流建立前暴露校验失败。"""
    session_key = _resolve_request_session(request, access)
    if request.attachments:
        await run_in_threadpool(_validate_uploaded_attachment_paths, request.attachments, access)
    return session_key


async def _prepare_agui_request(
    input_data: RunAgentInput,
    access: ChatAccess = Depends(get_chat_access),
) -> tuple[ChatStreamRequest, ChatSessionKey]:
    """Validate the run and access before acquiring application services."""
    request = consultation_request(input_data)
    session_key = _resolve_request_session(request, access)
    if request.attachments:
        await run_in_threadpool(_validate_uploaded_attachment_paths, request.attachments, access)
    return request, session_key


@router.post("/ag-ui")
async def agent_chat_agui(
    input_data: RunAgentInput,
    http_request: Request,
    access: ChatAccess = Depends(get_chat_access),
    prepared: tuple[ChatStreamRequest, ChatSessionKey] = Depends(_prepare_agui_request),
    session_manager: SessionManager = Depends(get_session_manager),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Run one authenticated consultation using the official AG-UI SSE binding."""
    request, session_key = prepared
    encoder = EventEncoder(accept=http_request.headers.get("accept"))

    async def encode_events():
        stream = stream_agui_events(
            input_data, request, session_key, session_manager, agent_service,
            allow_private_tools=access.is_staff,
        )
        try:
            async for event in stream:
                yield encoder.encode(event)
        finally:
            await close_with_timeout(stream.aclose)

    return AGUIStreamingResponse(
        encode_events(), media_type=encoder.get_content_type(),
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    access: ChatAccess = Depends(get_chat_access),
    session_key: ChatSessionKey = Depends(_prepare_chat_request),
    session_manager: SessionManager = Depends(get_session_manager),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Agent 问答接口（非流式）

    支持多轮对话，通过 session_id 维持上下文
    """
    try:
        # 获取或创建会话
        session = await run_in_threadpool(
            session_manager.get_or_create_session,
            session_key.storage_id,
            connection_id=request.connection_id,
            user_id=request.user_id,
        )

        # 添加用户消息到会话
        user_metadata: dict[str, object] = {"connection_id": request.connection_id}
        if request.user_id:
            user_metadata["user_id"] = request.user_id
        if request.attachments:
            user_metadata["attachments"] = [attachment.model_dump() for attachment in request.attachments]

        await run_in_threadpool(
            session_manager.add_message,
            session.session_id,
            "user",
            request.message,
            metadata=user_metadata,
        )

        # 调用统一 AgentService
        final = await agent_service.process_query(
            request.message,
            session_id=session.session_id,
            user_id=request.user_id,
            connection_id=request.connection_id,
            attachments=request.attachments,
            force_text2sql=request.text2sql_mode,
            allow_private_tools=access.is_staff,
        )

        # 添加助手消息到会话
        await run_in_threadpool(
            session_manager.add_message,
            session.session_id,
            "assistant",
            final.answer,
            metadata=final.metadata,
        )

        logger.info(f"会话 {session.session_id} 完成问答，路由：{final.metadata.get('route')}")

        metadata = dict(final.metadata)
        metadata.update(
            {
                "confidence": final.confidence,
                "message_count": session.message_count,
                "session_id": session_key.client_id,
            }
        )

        return ChatResponse(
            success=True,
            message=final.answer,
            session_id=session_key.client_id,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Agent 问答失败")
        raise HTTPException(status_code=500, detail="咨询服务暂时不可用，请稍后重试") from e


@router.post("/chat/stream")
async def agent_chat_stream(
    request: ChatStreamRequest,
    access: ChatAccess = Depends(get_chat_access),
    session_key: ChatSessionKey = Depends(_prepare_stream_request),
    session_manager: SessionManager = Depends(get_session_manager),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Agent 问答接口（SSE 流式响应）

    使用 Server-Sent Events 推送 AgentService 的处理结果
    """

    async def event_generator():
        """事件生成器"""
        try:
            # 获取或创建会话
            session = await run_in_threadpool(
                session_manager.get_or_create_session,
                session_key.storage_id,
                connection_id=request.connection_id,
                user_id=request.user_id,
            )
            session_id = session.session_id
            user_metadata: dict[str, object] = {"connection_id": request.connection_id}
            if request.user_id:
                user_metadata["user_id"] = request.user_id
            if request.attachments:
                user_metadata["attachments"] = [attachment.model_dump() for attachment in request.attachments]

            # 添加用户消息到会话
            await run_in_threadpool(
                session_manager.add_message,
                session_id,
                "user",
                request.message,
                metadata=user_metadata,
            )

            # 发送会话信息
            yield {
                "event": "session",
                "data": json.dumps({
                    "session_id": session_key.client_id,
                    "message_count": session.message_count
                }, ensure_ascii=False)
            }
            logger.info(f"会话 {session_id} 开始流式问答")
            # 若开启 AgentChat 流式，优先尝试流式；否则回退一次性推送
            use_agentchat_stream = os.getenv("AGENTCHAT_STREAM_ENABLED", "").lower() in {"1", "true", "yes", "on"}
            if use_agentchat_stream and agent_service.agentchat_streaming_enabled:
                stream = agent_service.process_query_stream(
                    request.message,
                    session_id=session_id,
                    user_id=request.user_id,
                    connection_id=request.connection_id,
                    attachments=request.attachments,
                    force_text2sql=request.text2sql_mode,
                    allow_private_tools=access.is_staff,
                )
                try:
                    async for event in stream:
                        if event["type"] == "chunk":
                            chunk = ChatStreamChunk(
                                content=event["content"],
                                done=False,
                                session_id=session_key.client_id,
                                metadata={},
                            )
                            yield {"event": "message", "data": chunk.model_dump_json(ensure_ascii=False)}
                        elif event["type"] == "final":
                            final = event["answer"]
                            full_metadata = dict(final.metadata)
                            full_metadata.update({"confidence": final.confidence, "session_id": session_key.client_id})
                            # 推送最终内容
                            chunk = ChatStreamChunk(
                                content=final.answer,
                                done=False,
                                session_id=session_key.client_id,
                                metadata=full_metadata,
                            )
                            yield {"event": "message", "data": chunk.model_dump_json(ensure_ascii=False)}

                            await run_in_threadpool(
                                session_manager.add_message,
                                session_id,
                                "assistant",
                                final.answer,
                                metadata=final.metadata,
                            )

                            done_metadata = dict(full_metadata)
                            done_metadata.update(
                                {
                                    "message_count": session.message_count,
                                    "total_length": len(final.answer),
                                }
                            )
                            done_chunk = ChatStreamChunk(
                                content="",
                                done=True,
                                session_id=session_key.client_id,
                                metadata=done_metadata,
                            )
                            yield {"event": "done", "data": done_chunk.model_dump_json(ensure_ascii=False)}
                            logger.info(f"会话 {session_id} 流式问答完成 (agentchat_stream)")
                finally:
                    await close_with_timeout(stream.aclose)
            else:
                final = await agent_service.process_query(
                    request.message,
                    session_id=session_id,
                    user_id=request.user_id,
                    connection_id=request.connection_id,
                    attachments=request.attachments,
                    force_text2sql=request.text2sql_mode,
                    allow_private_tools=access.is_staff,
                )

                # 发送内容片段（一次性推送最终答案）
                full_metadata = dict(final.metadata)
                full_metadata.update({"confidence": final.confidence, "session_id": session_key.client_id})
                chunk = ChatStreamChunk(
                    content=final.answer,
                    done=False,
                    session_id=session_key.client_id,
                    metadata=full_metadata,
                )
                yield {
                    "event": "message",
                    "data": chunk.model_dump_json(ensure_ascii=False)
                }

                # 添加助手完整响应到会话
                await run_in_threadpool(
                    session_manager.add_message,
                    session_id,
                    "assistant",
                    final.answer,
                    metadata=final.metadata,
                )

                # 发送完成信号
                done_metadata = dict(full_metadata)
                done_metadata.update(
                    {
                        "message_count": session.message_count,
                        "total_length": len(final.answer),
                    }
                )
                done_chunk = ChatStreamChunk(
                    content="",
                    done=True,
                    session_id=session_key.client_id,
                    metadata=done_metadata,
                )

                yield {
                    "event": "done",
                    "data": done_chunk.model_dump_json(ensure_ascii=False)
                }

                logger.info(f"会话 {session_id} 流式问答完成")

        except Exception:
            logger.exception("流式问答失败")

            # 发送错误信息
            error_chunk = ChatStreamChunk(
                content="",
                done=True,
                error="咨询服务暂时不可用，请稍后重试"
            )

            yield {
                "event": "error",
                "data": error_chunk.model_dump_json(ensure_ascii=False)
            }

    return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-store"})


# ==================== 会话管理端点 ====================

@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    access: ChatAccess = Depends(require_staff),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话信息"""
    session_key = resolve_chat_session(access, session_id, create=False)
    session = session_manager.get_session(session_key.storage_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    return SessionResponse(
        success=True,
        session=SessionInfo(
            session_id=session.session_id,
            created_at=session.created_at,
            last_active=session.last_active,
            message_count=session.message_count,
            status=session.status
        )
    )


@router.get("/sessions", response_model=ListSessionsResponse)
def list_sessions(
    access: ChatAccess = Depends(require_staff),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取所有活跃会话列表"""
    sessions = session_manager.list_sessions()

    session_infos = [
        SessionInfo(
            session_id=session.session_id,
            created_at=session.created_at,
            last_active=session.last_active,
            message_count=session.message_count,
            status=session.status
        )
        for session in sessions
        if session.session_id.startswith(access.namespace)
    ]

    return ListSessionsResponse(
        success=True,
        sessions=session_infos,
        total=len(session_infos)
    )


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
def delete_session(
    session_id: str,
    access: ChatAccess = Depends(require_staff),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """删除会话"""
    session_key = resolve_chat_session(access, session_id, create=False)
    session_manager.delete_session(session_key.storage_id)
    return {"success": True, "message": "会话已删除"}


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    query: Annotated[SessionMessagesQuery, Query()],
    access: ChatAccess = Depends(require_staff),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话消息历史"""
    session_key = resolve_chat_session(access, session_id, create=False)
    session = session_manager.get_session(session_key.storage_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = session_manager.get_messages(session_key.storage_id, limit=query.limit)

    return {
        "success": True,
        "session_id": session_key.client_id,
        "messages": messages,
        "total": len(messages)
    }
