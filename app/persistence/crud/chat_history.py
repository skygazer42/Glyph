"""Chat sessions, messages, and saved response snapshots."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.chat_history import ChatHistorySnapshot, ChatMessage, ChatSession
from app.persistence.crud.base import CRUDBase
from app.schemas.chat_history import (
    ChatHistorySnapshotCreate,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatSessionCreate,
    ChatSessionUpdate,
)


class CRUDChatSession(CRUDBase[ChatSession, ChatSessionCreate, ChatSessionUpdate]):
    """在调用方 Session 中维护聊天会话及其查询操作。"""

    def list_active(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        connection_id: Optional[int] = None
    ) -> List[ChatSession]:
        """List active sessions, optionally scoped to a database connection."""
        query = db.query(self.model).filter(self.model.is_active.is_(True))
        
        if connection_id is not None:
            query = query.filter(self.model.connection_id == connection_id)
            
        return query.order_by(desc(self.model.updated_at)).offset(skip).limit(limit).all()

    def update_activity(self, db: Session, *, session_id: str) -> Optional[ChatSession]:
        """更新会话活动时间"""
        session = db.query(self.model).filter(self.model.id == session_id).first()
        if session is not None:
            session.updated_at = datetime.utcnow()
            self._commit(db)
            db.refresh(session)
        return session


class CRUDChatMessage(CRUDBase[ChatMessage, ChatMessageCreate, ChatMessageUpdate]):
    """在调用方 Session 中维护会话消息与消息顺序。"""

    def get_by_session(
        self, 
        db: Session, 
        *, 
        session_id: str,
        skip: int = 0,
        limit: Optional[int] = 100
    ) -> List[ChatMessage]:
        """获取会话的消息列表"""
        query = db.query(self.model).filter(
            self.model.session_id == session_id
        ).order_by(self.model.order_index).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def get_latest_by_session(self, db: Session, *, session_id: str) -> Optional[ChatMessage]:
        """获取会话的最新消息"""
        return db.query(self.model).filter(
            self.model.session_id == session_id
        ).order_by(desc(self.model.order_index)).first()

    def create_batch(
        self, 
        db: Session, 
        *, 
        messages: List[ChatMessageCreate]
    ) -> List[ChatMessage]:
        """批量创建消息"""
        db_messages = []
        for message_data in messages:
            db_message = self.model(**message_data.model_dump())
            db.add(db_message)
            db_messages.append(db_message)
        
        self._commit(db)
        for db_message in db_messages:
            db.refresh(db_message)
        return db_messages


class CRUDChatHistorySnapshot(CRUDBase[ChatHistorySnapshot, ChatHistorySnapshotCreate, ChatHistorySnapshotCreate]):
    """维护按会话关联的查询响应快照。"""

    def get_by_session(self, db: Session, *, session_id: str) -> List[ChatHistorySnapshot]:
        """获取会话的历史快照"""
        return db.query(self.model).filter(
            self.model.session_id == session_id
        ).order_by(desc(self.model.created_at)).all()

    def get_latest_by_session(self, db: Session, *, session_id: str) -> Optional[ChatHistorySnapshot]:
        """获取会话的最新快照"""
        return db.query(self.model).filter(
            self.model.session_id == session_id
        ).order_by(desc(self.model.created_at)).first()


# 创建CRUD实例
chat_session = CRUDChatSession(ChatSession)
chat_message = CRUDChatMessage(ChatMessage)
chat_history_snapshot = CRUDChatHistorySnapshot(ChatHistorySnapshot)
