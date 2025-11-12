"""Persistence helpers for chat sessions and messages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.persistence.db.session import SessionLocal
from app.persistence.crud import (
    chat_session as chat_session_crud,
    chat_message as chat_message_crud,
    chat_history_snapshot as snapshot_crud,
    db_connection as db_connection_crud,
)
from app.schemas.chat_history import (
    ChatSessionCreate,
    ChatMessageCreate,
    ChatHistorySnapshotCreate,
)

ROLE_TO_MESSAGE_TYPE = {
    "user": "user_query",
    "assistant": "assistant_response",
    "system": "system_event",
}
MESSAGE_TYPE_TO_ROLE = {value: key for key, value in ROLE_TO_MESSAGE_TYPE.items()}


class ChatHistoryStore:
    """DB-backed helper to store chat sessions and messages."""

    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def _get_db(self) -> Session:
        return self._session_factory()

    def ensure_session(
        self,
        session_id: str,
        *,
        title: str,
        connection_id: Optional[int] = None,
    ) -> None:
        db = self._get_db()
        try:
            valid_connection_id = self._sanitize_connection_id(db, connection_id)
            existing = chat_session_crud.get(db, session_id)
            if existing:
                updates = {}
                if title and existing.title != title:
                    updates["title"] = title
                if (
                    valid_connection_id is not None
                    and existing.connection_id != valid_connection_id
                ):
                    updates["connection_id"] = valid_connection_id
                if updates:
                    chat_session_crud.update(db, db_obj=existing, obj_in=updates)
            else:
                chat_session_crud.create(
                    db,
                    obj_in=ChatSessionCreate(
                        id=session_id,
                        title=title or "新会话",
                        connection_id=valid_connection_id,
                        is_active=True,
                    ),
                )
        finally:
            db.close()

    def update_title(self, session_id: str, title: str) -> None:
        db = self._get_db()
        try:
            existing = chat_session_crud.get(db, session_id)
            if existing and existing.title != title:
                chat_session_crud.update(db, db_obj=existing, obj_in={"title": title})
        finally:
            db.close()

    def record_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        order_index: int,
        metadata: Optional[Dict[str, Any]] = None,
        region: Optional[str] = None,
    ) -> None:
        db = self._get_db()
        try:
            message_type = ROLE_TO_MESSAGE_TYPE.get(role, role)
            chat_message_crud.create(
                db,
                obj_in=ChatMessageCreate(
                    session_id=session_id,
                    message_type=message_type,
                    content=content,
                    order_index=order_index,
                    message_metadata=metadata or {},
                    region=region,
                ),
            )
            chat_session_crud.update_activity(db, session_id=session_id)
        finally:
            db.close()

    def list_sessions(self, *, limit: int = 100, connection_id: Optional[int] = None) -> List[Dict[str, Any]]:
        db = self._get_db()
        try:
            records = chat_session_crud.get_by_user_sessions(
                db, limit=limit, connection_id=connection_id
            )
            results: List[Dict[str, Any]] = []
            for record in records:
                results.append(
                    {
                        "session_id": record.id,
                        "title": record.title,
                        "connection_id": record.connection_id,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                        "is_active": record.is_active,
                        "message_count": len(record.messages or []),
                    }
                )
            return results
        finally:
            db.close()

    def fetch_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        db = self._get_db()
        try:
            record = chat_session_crud.get(db, session_id)
            if not record:
                return None
            return {
                "session_id": record.id,
                "title": record.title,
                "connection_id": record.connection_id,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "is_active": record.is_active,
                "message_count": len(record.messages or []),
            }
        finally:
            db.close()

    def list_messages(self, session_id: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        db = self._get_db()
        try:
            records = chat_message_crud.get_by_session(db, session_id=session_id)
            if limit:
                records = records[-limit:]
            return [
                {
                    "session_id": m.session_id,
                    "role": MESSAGE_TYPE_TO_ROLE.get(m.message_type, m.message_type),
                    "content": m.content,
                    "region": m.region,
                    "metadata": m.message_metadata,
                    "order_index": m.order_index,
                    "created_at": m.created_at,
                }
                for m in records
            ]
        finally:
            db.close()

    def delete_session(self, session_id: str) -> None:
        db = self._get_db()
        try:
            existing = chat_session_crud.get(db, session_id)
            if existing:
                db.delete(existing)
                db.commit()
        finally:
            db.close()

    def create_snapshot(self, session_id: str, *, query: str, response_data: Dict[str, Any]) -> None:
        db = self._get_db()
        try:
            snapshot_crud.create(
                db,
                obj_in=ChatHistorySnapshotCreate(
                    session_id=session_id,
                    query=query,
                    response_data=response_data,
                ),
            )
        finally:
            db.close()

    @staticmethod
    def _sanitize_connection_id(db: Session, connection_id: Optional[int]) -> Optional[int]:
        if connection_id is None:
            return None
        record = db_connection_crud.get(db, connection_id)
        if record is None:
            return None
        return connection_id
