"""Chat history schemas used by CRUD helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    """创建持久化聊天会话所需的元数据。"""

    id: str = Field(..., description="会话ID")
    title: str
    connection_id: Optional[int] = None
    is_active: bool = True


class ChatSessionUpdate(BaseModel):
    """表达会话元数据的部分更新；未设置字段与显式 None 由调用方区分。"""

    title: Optional[str] = None
    connection_id: Optional[int] = None
    is_active: Optional[bool] = None


class ChatMessageCreate(BaseModel):
    """创建会话内带顺序位置的消息记录。"""

    session_id: str
    message_type: str
    content: str
    order_index: int
    message_metadata: Optional[Dict[str, Any]] = None
    region: Optional[str] = None


class ChatMessageUpdate(BaseModel):
    """表达消息内容、位置及附加信息的部分更新。"""

    message_type: Optional[str] = None
    content: Optional[str] = None
    order_index: Optional[int] = None
    message_metadata: Optional[Dict[str, Any]] = None
    region: Optional[str] = None


class ChatHistorySnapshotCreate(BaseModel):
    """保存一次查询及完整响应数据的历史快照输入。"""

    session_id: str
    query: str
    response_data: Dict[str, Any]


__all__ = [
    "ChatSessionCreate",
    "ChatSessionUpdate",
    "ChatMessageCreate",
    "ChatMessageUpdate",
    "ChatHistorySnapshotCreate",
]
