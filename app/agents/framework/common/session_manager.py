"""
会话管理器：统一管理多轮对话与持久化聊天历史。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from copy import deepcopy
from threading import RLock
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.utils.lifecycle import close_with_timeout

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

        self._lock = RLock()
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
        """先按配置保存会话元数据，再登记新的内存会话；返回管理器持有的可变会话对象。"""
        with self._lock:
            if session_id is None:
                session_id = str(uuid.uuid4())

            session = Session(
                session_id=session_id,
                title=title or "",
                connection_id=connection_id,
                user_id=user_id,
            )
            if self.history_store:
                self.history_store.ensure_session(
                    session_id,
                    title=title or "新会话",
                    connection_id=connection_id,
                )

            self.sessions[session_id] = session
            logger.info("创建会话: %s", session_id)
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """返回并刷新缓存会话的活跃时间；缓存未命中时尝试从历史库恢复元数据，仍未找到则返回 None。"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_active = time.time()
                return session

            if self.history_store:
                record = self.history_store.fetch_session(session_id)
                if record:
                    session = Session(
                        session_id=record["session_id"],
                        title=record["title"],
                        connection_id=record["connection_id"],
                        created_at=self._datetime_to_ts(record["created_at"]),
                        last_active=self._datetime_to_ts(
                            record["updated_at"] or record["created_at"]
                        ),
                        message_count=record["message_count"],
                        status="active" if record["is_active"] else "inactive",
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
        """复用或恢复指定会话，未找到时创建；返回共享内存对象而非独立副本。"""
        with self._lock:
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
        """先完成配置的历史持久化，再追加消息深拷贝并更新内存计数；存储错误不被吞掉。"""
        with self._lock:
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

            title = content[:50] if role == "user" and not session.title else session.title
            if self.history_store is not None and title != session.title:
                self.history_store.update_title(session_id, title)

            if self.history_store:
                self.history_store.record_message(
                    session_id,
                    role=role,
                    content=content,
                    order_index=session.message_count + 1,
                    metadata=metadata,
                    region=region,
                )
            session.messages.append(deepcopy(payload))
            session.message_count += 1
            session.title = title

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """优先返回内存消息的深拷贝，否则读取历史库；limit 为零返回空列表，负数报错。"""
        with self._lock:
            if limit is not None and limit < 0:
                raise ValueError("limit must be non-negative")
            if limit == 0:
                return []
            session = self.get_session(session_id)
            if session and session.messages:
                return deepcopy(session.messages if limit is None else session.messages[-limit:])

            if self.history_store:
                records = self.history_store.list_messages(session_id, limit=limit)
                return [
                    {
                        "role": item["role"],
                        "content": item["content"],
                        "timestamp": self._datetime_to_ts(item["created_at"]),
                        "metadata": item["metadata"],
                        "region": item["region"],
                    }
                    for item in records
                ]
            return []

    def update_context(self, session_id: str, context: Dict[str, Any]) -> None:
        """仅更新已存在会话，将传入上下文深拷贝后合并到管理器缓存。"""
        with self._lock:
            session = self.get_session(session_id)
            if session:
                session.context.update(deepcopy(context))

    def get_context(self, session_id: str) -> Dict[str, Any]:
        """返回会话上下文的深拷贝；未找到会话时返回空字典。"""
        with self._lock:
            session = self.get_session(session_id)
            return deepcopy(session.context) if session else {}

    def delete_session(self, session_id: str) -> None:
        """先删除配置的持久化历史，再移除内存会话与消息队列；存储失败保留内存条目。"""
        with self._lock:
            if self.history_store is not None:
                self.history_store.delete_session(session_id)
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info("删除会话: %s", session_id)

            if session_id in self.message_queues:
                del self.message_queues[session_id]


    # ------------------------------------------------------------------
    # 查询 & 统计
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[Session]:
        """有历史库时以活跃记录为列表来源并复用已缓存对象，否则列出内存会话。"""
        with self._lock:
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
                            title=record["title"],
                            connection_id=record["connection_id"],
                            created_at=self._datetime_to_ts(record["created_at"]),
                            last_active=self._datetime_to_ts(
                                record["updated_at"] or record["created_at"]
                            ),
                            message_count=record["message_count"],
                            status="active" if record["is_active"] else "inactive",
                        )
                    )
                return sessions
            return list(self.sessions.values())

    def get_session_count(self) -> int:
        with self._lock:
            if self.history_store:
                return len(self.list_sessions())
            return len(self.sessions)

    # ------------------------------------------------------------------
    # 清理任务
    # ------------------------------------------------------------------
    async def cleanup_expired_sessions(self) -> None:
        """在线程中清理过期内存会话及队列，不删除持久化聊天历史。"""
        await asyncio.to_thread(self._cleanup_expired_sessions)

    def _cleanup_expired_sessions(self) -> None:
        with self._lock:
            current_time = time.time()
            expired = [
                session_id
                for session_id, session in self.sessions.items()
                if current_time - session.last_active > self.timeout
            ]
            for session_id in expired:
                # Expiry evicts the cache; only an explicit delete removes saved history.
                del self.sessions[session_id]
                self.message_queues.pop(session_id, None)
                logger.info("清理过期会话: %s", session_id)

    async def _run_cleanup(self) -> None:
        logger.info("启动会话自动清理任务")
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                logger.info("会话清理任务已取消")
                raise
            except Exception:
                logger.exception("会话清理任务异常")

    def start(self) -> None:
        """在当前事件循环启动唯一的会话过期清理任务。"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._run_cleanup())

    async def stop(self) -> None:
        """取消并有界等待本管理器的清理任务；非取消异常继续传播。"""
        if self._cleanup_task is not None:
            task = self._cleanup_task
            task.cancel()
            results = await close_with_timeout(
                partial(asyncio.gather, task, return_exceptions=True)
            )
            self._cleanup_task = None
            result = results[0]
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                raise result

    # ------------------------------------------------------------------
    # SSE 消息队列
    # ------------------------------------------------------------------
    def create_message_queue(self, session_id: str) -> asyncio.Queue:
        """为会话新建并登记队列；同标识原队列会被替换。"""
        with self._lock:
            queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
            self.message_queues[session_id] = queue
            return queue

    def get_message_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        with self._lock:
            return self.message_queues.get(session_id)

    async def put_message(self, session_id: str, message: Any) -> None:
        """向已登记队列放入消息；会话没有队列时不做操作。"""
        queue = self.get_message_queue(session_id)
        if queue:
            await queue.put(message)

    async def get_message(self, session_id: str, timeout: Optional[float] = None) -> Any:
        """等待会话队列消息；超时、队列不存在或零超时取空队列时返回 None。"""
        queue = self.get_message_queue(session_id)
        if not queue:
            return None
        try:
            if timeout == 0:
                return queue.get_nowait()
            if timeout is not None:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            return await queue.get()
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
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
        raise TypeError(f"Unsupported session timestamp: {type(value).__name__}")
