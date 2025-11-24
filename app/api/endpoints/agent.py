"""
Agent 问答相关端点
支持普通问答和 SSE 流式响应
"""

import json
import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ChatStreamChunk,
    SessionInfo,
    SessionResponse,
    ListSessionsResponse
)
from app.api.deps import get_session_manager, get_agent_service
from app.agents.framework.common.session_manager import SessionManager
from app.agents.service import AgentService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    Agent 问答接口（非流式）

    支持多轮对话，通过 session_id 维持上下文
    """
    try:
        # 获取或创建会话
        session = session_manager.get_or_create_session(
            request.session_id,
            connection_id=request.connection_id,
            user_id=request.user_id,
        )

        # 添加用户消息到会话
        user_metadata = {"connection_id": request.connection_id}
        if request.user_id:
            user_metadata["user_id"] = request.user_id
        if request.attachments:
            user_metadata["attachments"] = [att.model_dump() for att in request.attachments]

        session_manager.add_message(
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
        )

        # 添加助手消息到会话
        session_manager.add_message(
            session.session_id,
            "assistant",
            final.answer,
            metadata=final.metadata,
        )

        logger.info(f"会话 {session.session_id} 完成问答，路由：{final.metadata.get('route')}")

        metadata = final.metadata or {}
        metadata.update(
            {
                "confidence": final.confidence,
                "message_count": session.message_count,
            }
        )

        session_id = metadata.get("session_id") or session.session_id

        return ChatResponse(
            success=True,
            message=final.answer,
            session_id=session_id,
            metadata=metadata,
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Agent 问答失败: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(
    request: ChatStreamRequest,
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
            session = session_manager.get_or_create_session(
                request.session_id,
                connection_id=request.connection_id,
                user_id=request.user_id,
            )
            session_id = session.session_id
            user_metadata = {"connection_id": request.connection_id}
            if request.user_id:
                user_metadata["user_id"] = request.user_id
            if request.attachments:
                user_metadata["attachments"] = [att.model_dump() for att in request.attachments]

            # 添加用户消息到会话
            session_manager.add_message(
                session_id,
                "user",
                request.message,
                metadata=user_metadata,
            )

            # 发送会话信息
            yield {
                "event": "session",
                "data": json.dumps({
                    "session_id": session_id,
                    "message_count": session.message_count
                }, ensure_ascii=False)
            }
            logger.info(f"会话 {session_id} 开始流式问答")
            # 若开启 AgentChat 流式，优先尝试流式；否则回退一次性推送
            use_agentchat_stream = os.getenv("AGENTCHAT_STREAM_ENABLED", "").lower() in {"1", "true", "yes", "on"}
            if use_agentchat_stream and getattr(agent_service, "_agentchat_team_enabled", False):
                async for evt in agent_service.process_query_stream(
                    request.message,
                    session_id=session_id,
                    user_id=request.user_id,
                    connection_id=request.connection_id,
                    attachments=request.attachments,
                    force_text2sql=request.text2sql_mode,
                ):
                    if evt.get("type") == "chunk":
                        chunk = ChatStreamChunk(
                            content=evt.get("content", ""),
                            done=False,
                            session_id=session_id,
                            metadata={},
                        )
                        yield {"event": "message", "data": chunk.model_dump_json(ensure_ascii=False)}
                    elif evt.get("type") == "final":
                        final = evt["answer"]
                        full_metadata = final.metadata or {}
                        full_metadata.update({"confidence": final.confidence})
                        # 推送最终内容
                        chunk = ChatStreamChunk(
                            content=final.answer,
                            done=False,
                            session_id=session_id,
                            metadata=full_metadata,
                        )
                        yield {"event": "message", "data": chunk.model_dump_json(ensure_ascii=False)}

                        session_manager.add_message(
                            session_id,
                            "assistant",
                            final.answer,
                            metadata=full_metadata,
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
                            session_id=session_id,
                            metadata=done_metadata,
                        )
                        yield {"event": "done", "data": done_chunk.model_dump_json(ensure_ascii=False)}
                        logger.info(f"会话 {session_id} 流式问答完成 (agentchat_stream)")
            else:
                final = await agent_service.process_query(
                    request.message,
                    session_id=session_id,
                    user_id=request.user_id,
                    connection_id=request.connection_id,
                    attachments=request.attachments,
                    force_text2sql=request.text2sql_mode,
                )

                # 发送内容片段（一次性推送最终答案）
                full_metadata = final.metadata or {}
                full_metadata.update({"confidence": final.confidence})
                chunk = ChatStreamChunk(
                    content=final.answer,
                    done=False,
                    session_id=session_id,
                    metadata=full_metadata,
                )
                yield {
                    "event": "message",
                    "data": chunk.model_dump_json(ensure_ascii=False)
                }

                # 添加助手完整响应到会话
                session_manager.add_message(
                    session_id,
                    "assistant",
                    final.answer,
                    metadata=full_metadata,
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
                    session_id=session_id,
                    metadata=done_metadata,
                )

                yield {
                    "event": "done",
                    "data": done_chunk.model_dump_json(ensure_ascii=False)
                }

                logger.info(f"会话 {session_id} 流式问答完成")

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"流式问答失败: {error_detail}")

            # 发送错误信息
            error_chunk = ChatStreamChunk(
                content="",
                done=True,
                error=str(e)
            )

            yield {
                "event": "error",
                "data": error_chunk.model_dump_json(ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


# ==================== 会话管理端点 ====================

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话信息"""
    session = session_manager.get_session(session_id)
    if not session:
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
async def list_sessions(
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取所有活跃会话列表"""
    sessions = session_manager.list_sessions()

    session_infos = [
        SessionInfo(
            session_id=s.session_id,
            created_at=s.created_at,
            last_active=s.last_active,
            message_count=s.message_count,
            status=s.status
        )
        for s in sessions
    ]

    return ListSessionsResponse(
        success=True,
        sessions=session_infos,
        total=len(session_infos)
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """删除会话"""
    session_manager.delete_session(session_id)
    return {"success": True, "message": "会话已删除"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: Optional[int] = None,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """获取会话消息历史"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = session_manager.get_messages(session_id, limit=limit)

    return {
        "success": True,
        "session_id": session_id,
        "messages": messages,
        "total": len(messages)
    }
