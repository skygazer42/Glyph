"""
Agent 问答相关端点
支持普通问答和 SSE 流式响应
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from autogen_agentchat.agents import AssistantAgent

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ChatStreamChunk,
    SessionInfo,
    SessionResponse,
    ListSessionsResponse
)
from app.api.deps import get_model_client, get_session_manager
from app.services.session_manager import SessionManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Agent 问答接口（非流式）

    支持多轮对话，通过 session_id 维持上下文
    """
    try:
        # 获取或创建会话
        session = session_manager.get_or_create_session(request.session_id)

        # 添加用户消息到会话
        session_manager.add_message(session.session_id, "user", request.message)

        # 获取模型客户端
        model_client = get_model_client()

        # 创建 Assistant Agent
        agent = AssistantAgent(
            name="PolicyAssistant",
            model_client=model_client,
            description="政策问答助手，能够回答各种政策相关问题",
            system_message="你是一个专业的政策咨询助手，名叫小政。你能够回答用户关于政策的各种问题。请用简洁、专业的语言回答。"
        )

        # 执行问答
        result = await agent.run(task=request.message)

        # 提取回答内容
        response_text = ""
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            if hasattr(last_message, 'content'):
                response_text = last_message.content

        # 添加助手消息到会话
        session_manager.add_message(session.session_id, "assistant", response_text)

        logger.info(f"会话 {session.session_id} 完成问答")

        return ChatResponse(
            success=True,
            message=response_text,
            session_id=session.session_id,
            metadata={
                "agent": "PolicyAssistant",
                "model": "deepseek-chat",
                "message_count": session.message_count
            }
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Agent 问答失败: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(
    request: ChatStreamRequest,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Agent 问答接口（SSE 流式响应）

    使用 Server-Sent Events 实时推送 Agent 响应
    支持多轮对话
    """

    async def event_generator():
        """事件生成器"""
        try:
            # 获取或创建会话
            session = session_manager.get_or_create_session(request.session_id)
            session_id = session.session_id

            # 添加用户消息到会话
            session_manager.add_message(session_id, "user", request.message)

            # 发送会话信息
            yield {
                "event": "session",
                "data": json.dumps({
                    "session_id": session_id,
                    "message_count": session.message_count
                }, ensure_ascii=False)
            }

            # 获取模型客户端
            model_client = get_model_client()

            # 创建 Assistant Agent
            agent = AssistantAgent(
                name="PolicyAssistant",
                model_client=model_client,
                description="政策问答助手，能够回答各种政策相关问题",
                system_message="你是一个专业的政策咨询助手，名叫小政。你能够回答用户关于政策的各种问题。请用简洁、专业的语言回答。"
            )

            # 流式执行
            logger.info(f"会话 {session_id} 开始流式问答")
            stream = agent.run_stream(task=request.message)

            # 收集完整响应
            full_response = ""

            async for msg in stream:
                if hasattr(msg, 'content'):
                    content = msg.content
                    full_response += content

                    # 发送内容片段
                    chunk = ChatStreamChunk(
                        content=content,
                        done=False,
                        session_id=session_id
                    )

                    yield {
                        "event": "message",
                        "data": chunk.model_dump_json(ensure_ascii=False)
                    }

            # 添加助手完整响应到会话
            session_manager.add_message(session_id, "assistant", full_response)

            # 发送完成信号
            done_chunk = ChatStreamChunk(
                content="",
                done=True,
                session_id=session_id,
                metadata={
                    "agent": "PolicyAssistant",
                    "model": "deepseek-chat",
                    "message_count": session.message_count,
                    "total_length": len(full_response)
                }
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
