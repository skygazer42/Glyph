"""
会话管理器：统一管理多轮对话与持久化聊天历史。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from app.agents.service.chat_history_store import ChatHistoryStore


@dataclass
class Session:
    """内存态的会话对象，用于 SSE / 上下文缓存。"""

    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "active"
    title: str = ""
    connection_id: Optional[int] = None
    user_id: Optional[str] = None


class SessionManager:
    """会话管理器：支持内存 + DB 双存储。"""

    def __init__(
        self,
        timeout: int = 3600,
        cleanup_interval: int = 300,
        history_store: Optional["ChatHistoryStore"] = None,
    ) -> None:
        self.timeout = timeout
        self.cleanup_interval = cleanup_interval
        self.history_store = history_store

        self.sessions: Dict[str, Session] = {}
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            "会话管理器已初始化，timeout=%s cleanup_interval=%s store=%s",
            timeout,
            cleanup_interval,
            bool(history_store),
        )

    # ------------------------------------------------------------------
    # 会话创建 / 获取
    # ------------------------------------------------------------------
    def create_session(
        self,
        session_id: Optional[str] = None,
        *,
        title: Optional[str] = None,
        connection_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> Session:
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = Session(
            session_id=session_id,
            title=title or "",
            connection_id=connection_id,
            user_id=user_id,
        )
        self.sessions[session_id] = session

        if self.history_store:
            self.history_store.ensure_session(
                session_id,
                title=title or "新会话",
                connection_id=connection_id,
            )

        logger.info("创建会话: %s", session_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session:
            session.last_active = time.time()
            return session

        if self.history_store:
            record = self.history_store.fetch_session(session_id)
            if record:
                session = Session(
                    session_id=record["session_id"],
                    title=record.get("title") or "",
                    connection_id=record.get("connection_id"),
                    created_at=self._datetime_to_ts(record.get("created_at")),
                    last_active=self._datetime_to_ts(
                        record.get("updated_at") or record.get("created_at")
                    ),
                    message_count=record.get("message_count", 0),
                    status="active" if record.get("is_active") else "inactive",
                )
                self.sessions[session_id] = session
                return session
        return None

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        *,
        title: Optional[str] = None,
        connection_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> Session:
        if session_id:
            existing = self.sessions.get(session_id)
            if existing:
                existing.last_active = time.time()
                if connection_id is not None:
                    existing.connection_id = connection_id
                if user_id and not existing.user_id:
                    existing.user_id = user_id
                return existing

            session = self.get_session(session_id)
            if session:
                if connection_id is not None:
                    session.connection_id = connection_id
                return session

        return self.create_session(
            session_id,
            title=title,
            connection_id=connection_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # 消息管理
    # ------------------------------------------------------------------
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        region: Optional[str] = None,
    ) -> None:
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)

        payload: Dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if metadata:
            payload["metadata"] = metadata
        if region:
            payload["region"] = region

        session.messages.append(payload)
        session.message_count += 1

        if role == "user" and not session.title:
            session.title = content[:50]
            if self.history_store:
                self.history_store.update_title(session_id, session.title)

        if self.history_store:
            self.history_store.record_message(
                session_id,
                role=role,
                content=content,
                order_index=session.message_count,
                metadata=metadata,
                region=region,
            )

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        session = self.get_session(session_id)
        if session and session.messages:
            return session.messages[-limit:] if limit else session.messages

        if self.history_store:
            records = self.history_store.list_messages(session_id, limit=limit)
            return [
                {
                    "role": item["role"],
                    "content": item["content"],
                    "timestamp": self._datetime_to_ts(item.get("created_at")),
                    "metadata": item.get("metadata"),
                    "region": item.get("region"),
                }
                for item in records
            ]
        return []

    def update_context(self, session_id: str, context: Dict[str, Any]) -> None:
        session = self.get_session(session_id)
        if session:
            session.context.update(context)

    def get_context(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        return session.context if session else {}

    def delete_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info("删除会话: %s", session_id)

        if session_id in self.message_queues:
            del self.message_queues[session_id]

        if self.history_store:
            self.history_store.delete_session(session_id)

    # ------------------------------------------------------------------
    # 查询 & 统计
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[Session]:
        if self.history_store:
            sessions: List[Session] = []
            for record in self.history_store.list_sessions():
                cached = self.sessions.get(record["session_id"])
                if cached:
                    sessions.append(cached)
                    continue
                sessions.append(
                    Session(
                        session_id=record["session_id"],
                        title=record.get("title") or "",
                        connection_id=record.get("connection_id"),
                        created_at=self._datetime_to_ts(record.get("created_at")),
                        last_active=self._datetime_to_ts(
                            record.get("updated_at") or record.get("created_at")
                        ),
                        message_count=record.get("message_count", 0),
                        status="active" if record.get("is_active") else "inactive",
                    )
                )
            return sessions
        return list(self.sessions.values())

    def get_session_count(self) -> int:
        if self.history_store:
            return len(self.list_sessions())
        return len(self.sessions)

    # ------------------------------------------------------------------
    # 清理任务
    # ------------------------------------------------------------------
    async def cleanup_expired_sessions(self) -> None:
        current_time = time.time()
        expired = [
            session_id
            for session_id, session in self.sessions.items()
            if current_time - session.last_active > self.timeout
        ]
        for session_id in expired:
            self.delete_session(session_id)
            logger.info("清理过期会话: %s", session_id)

    async def start_cleanup_task(self) -> None:
        logger.info("启动会话自动清理任务")
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                logger.info("会话清理任务已取消")
                break
            except Exception as exc:
                logger.error("会话清理任务异常: %s", exc)

    def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self.start_cleanup_task())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    # ------------------------------------------------------------------
    # SSE 消息队列
    # ------------------------------------------------------------------
    def create_message_queue(self, session_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.message_queues[session_id] = queue
        return queue

    def get_message_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        return self.message_queues.get(session_id)

    async def put_message(self, session_id: str, message: Any) -> None:
        queue = self.get_message_queue(session_id)
        if queue:
            await queue.put(message)

    async def get_message(self, session_id: str, timeout: Optional[float] = None) -> Any:
        queue = self.get_message_queue(session_id)
        if not queue:
            return None
        try:
            if timeout:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            return await queue.get()
        except asyncio.TimeoutError:
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _datetime_to_ts(value: Optional[Any]) -> float:
        if value is None:
            return time.time()
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if hasattr(value, "timestamp"):
            return value.timestamp()
        return time.time()
