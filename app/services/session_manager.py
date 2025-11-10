"""
会话管理器
负责管理用户会话、上下文和自动清理
"""

import asyncio
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """会话对象"""
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, str]] = field(default_factory=list)
    status: str = "active"


class SessionManager:
    """
    会话管理器

    功能：
    - 创建和管理用户会话
    - 自动清理过期会话
    - 支持多轮对话上下文
    - 消息队列管理
    """

    def __init__(self, timeout: int = 3600, cleanup_interval: int = 300):
        """
        初始化会话管理器

        Args:
            timeout: 会话超时时间（秒），默认1小时
            cleanup_interval: 清理检查间隔（秒），默认5分钟
        """
        self.timeout = timeout
        self.cleanup_interval = cleanup_interval

        # 会话存储
        self.sessions: Dict[str, Session] = {}

        # 消息队列（用于流式响应）
        self.message_queues: Dict[str, asyncio.Queue] = {}

        # 启动自动清理任务
        self._cleanup_task = None

        logger.info(f"会话管理器已初始化，超时时间: {timeout}秒")

    def create_session(self, session_id: Optional[str] = None) -> Session:
        """
        创建新会话

        Args:
            session_id: 会话ID（可选，不提供则自动生成）

        Returns:
            创建的会话对象
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = Session(session_id=session_id)
        self.sessions[session_id] = session

        logger.info(f"创建会话: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话对象，不存在则返回None
        """
        session = self.sessions.get(session_id)
        if session:
            # 更新最后活跃时间
            session.last_active = time.time()
        return session

    def get_or_create_session(self, session_id: Optional[str] = None) -> Session:
        """
        获取或创建会话

        Args:
            session_id: 会话ID（可选）

        Returns:
            会话对象
        """
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_active = time.time()
            return session
        else:
            return self.create_session(session_id)

    def add_message(self, session_id: str, role: str, content: str):
        """
        添加消息到会话

        Args:
            session_id: 会话ID
            role: 角色（user/assistant/system）
            content: 消息内容
        """
        session = self.get_session(session_id)
        if session:
            session.messages.append({
                "role": role,
                "content": content,
                "timestamp": time.time()
            })
            session.message_count += 1
            logger.debug(f"会话 {session_id} 添加消息: {role}")

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取会话消息历史

        Args:
            session_id: 会话ID
            limit: 限制返回数量（可选）

        Returns:
            消息列表
        """
        session = self.get_session(session_id)
        if not session:
            return []

        messages = session.messages
        if limit:
            messages = messages[-limit:]

        return messages

    def update_context(self, session_id: str, context: Dict[str, Any]):
        """
        更新会话上下文

        Args:
            session_id: 会话ID
            context: 上下文数据
        """
        session = self.get_session(session_id)
        if session:
            session.context.update(context)
            logger.debug(f"会话 {session_id} 更新上下文")

    def get_context(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话上下文

        Args:
            session_id: 会话ID

        Returns:
            上下文数据
        """
        session = self.get_session(session_id)
        return session.context if session else {}

    def delete_session(self, session_id: str):
        """
        删除会话

        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"删除会话: {session_id}")

        # 清理消息队列
        if session_id in self.message_queues:
            del self.message_queues[session_id]

    def list_sessions(self) -> List[Session]:
        """
        获取所有活跃会话

        Returns:
            会话列表
        """
        return list(self.sessions.values())

    def get_session_count(self) -> int:
        """
        获取活跃会话数量

        Returns:
            会话数量
        """
        return len(self.sessions)

    async def cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if current_time - session.last_active > self.timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self.delete_session(session_id)
            logger.info(f"清理过期会话: {session_id}")

        if expired_sessions:
            logger.info(f"清理了 {len(expired_sessions)} 个过期会话")

    async def start_cleanup_task(self):
        """启动自动清理任务"""
        logger.info("启动会话自动清理任务")
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                logger.info("会话清理任务已取消")
                break
            except Exception as e:
                logger.error(f"会话清理任务出错: {e}")

    def start(self):
        """启动会话管理器"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self.start_cleanup_task())
            logger.info("会话管理器已启动")

    async def stop(self):
        """停止会话管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("会话管理器已停止")

    # ==================== 消息队列管理（用于SSE） ====================

    def create_message_queue(self, session_id: str) -> asyncio.Queue:
        """
        为会话创建消息队列

        Args:
            session_id: 会话ID

        Returns:
            消息队列
        """
        queue = asyncio.Queue()
        self.message_queues[session_id] = queue
        logger.debug(f"为会话 {session_id} 创建消息队列")
        return queue

    def get_message_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        """
        获取会话消息队列

        Args:
            session_id: 会话ID

        Returns:
            消息队列
        """
        return self.message_queues.get(session_id)

    async def put_message(self, session_id: str, message: Any):
        """
        向会话队列发送消息

        Args:
            session_id: 会话ID
            message: 消息内容
        """
        queue = self.get_message_queue(session_id)
        if queue:
            await queue.put(message)
            logger.debug(f"向会话 {session_id} 队列发送消息")

    async def get_message(self, session_id: str, timeout: Optional[float] = None) -> Any:
        """
        从会话队列获取消息

        Args:
            session_id: 会话ID
            timeout: 超时时间（秒）

        Returns:
            消息内容
        """
        queue = self.get_message_queue(session_id)
        if queue:
            try:
                if timeout:
                    message = await asyncio.wait_for(queue.get(), timeout=timeout)
                else:
                    message = await queue.get()
                return message
            except asyncio.TimeoutError:
                return None
        return None
