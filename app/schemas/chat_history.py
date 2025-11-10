"""Chat history schemas used by CRUD helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    id: str = Field(..., description="会话ID")
    title: str
    connection_id: Optional[int] = None
    is_active: bool = True


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    connection_id: Optional[int] = None
    is_active: Optional[bool] = None


class ChatMessageCreate(BaseModel):
    session_id: str
    message_type: str
    content: str
    order_index: int
    message_metadata: Optional[Dict[str, Any]] = None
    region: Optional[str] = None


class ChatMessageUpdate(BaseModel):
    message_type: Optional[str] = None
    content: Optional[str] = None
    order_index: Optional[int] = None
    message_metadata: Optional[Dict[str, Any]] = None
    region: Optional[str] = None


class ChatHistorySnapshotCreate(BaseModel):
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
