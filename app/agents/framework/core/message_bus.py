"""
Message Bus - 消息总线系统
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
import logging
from collections import defaultdict
import uuid

from ..models.base import MessageType

logger = logging.getLogger(__name__)


class Message:
    """消息对象"""

    def __init__(
        self,
        type: MessageType,
        content: Dict[str, Any],
        sender: str,
        recipient: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = str(uuid.uuid4())
        self.type = type
        self.content = content
        self.sender = sender
        self.recipient = recipient  # None表示广播
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.reply_to: Optional[str] = None
        self.correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "sender": self.sender,
            "recipient": self.recipient,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "correlation_id": self.correlation_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        message = cls(
            type=MessageType(data["type"]),
            content=data["content"],
            sender=data["sender"],
            recipient=data.get("recipient"),
            metadata=data.get("metadata", {})
        )
        message.id = data["id"]
        message.timestamp = datetime.fromisoformat(data["timestamp"])
        message.reply_to = data.get("reply_to")
        message.correlation_id = data.get("correlation_id")
        return message

    def create_reply(self, content: Dict[str, Any], sender: str) -> "Message":
        """创建回复消息"""
        reply = Message(
            type=self.type,
            content=content,
            sender=sender,
            recipient=self.sender,
            metadata=self.metadata.copy()
        )
        reply.reply_to = self.id
        reply.correlation_id = self.correlation_id or self.id
        return reply

    def __repr__(self) -> str:
        return f"<Message(id={self.id[:8]}, type={self.type.value}, sender={self.sender})>"


class MessageBus:
    """消息总线 - 实现Agent间的消息传递"""

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self._subscribers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._agent_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._message_history: Dict[str, Message] = {}
        self._max_history = 1000
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0
        }

    async def start(self, num_workers: int = 3) -> None:
        """启动消息总线"""
        if self._running:
            return

        self._running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)

        logger.info(f"Message bus started with {num_workers} workers")

    async def stop(self) -> None:
        """停止消息总线"""
        self._running = False

        # 取消所有worker任务
        for task in self._worker_tasks:
            task.cancel()

        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        logger.info("Message bus stopped")

    def subscribe(
        self,
        message_type: MessageType,
        handler: Callable,
        agent_id: Optional[str] = None
    ) -> None:
        """
        订阅消息

        Args:
            message_type: 要订阅的消息类型
            handler: 处理函数
            agent_id: Agent ID（可选）
        """
        self._subscribers[message_type].append(handler)
        if agent_id:
            self._agent_subscribers[agent_id].append(handler)
        logger.debug(f"Subscribed to {message_type.value}")

    def unsubscribe(
        self,
        message_type: MessageType,
        handler: Callable,
        agent_id: Optional[str] = None
    ) -> None:
        """
        取消订阅

        Args:
            message_type: 消息类型
            handler: 处理函数
            agent_id: Agent ID（可选）
        """
        if handler in self._subscribers[message_type]:
            self._subscribers[message_type].remove(handler)

        if agent_id and agent_id in self._agent_subscribers:
            if handler in self._agent_subscribers[agent_id]:
                self._agent_subscribers[agent_id].remove(handler)

        logger.debug(f"Unsubscribed from {message_type.value}")

    async def publish(self, message: Message) -> None:
        """
        发布消息

        Args:
            message: 要发布的消息
        """
        try:
            # 将消息放入队列
            await self._message_queue.put(message)
            self._stats["messages_sent"] += 1

            # 记录消息历史
            self._record_message(message)

            logger.debug(f"Published message {message.id} of type {message.type.value}")

        except asyncio.QueueFull:
            self._stats["messages_failed"] += 1
            logger.error("Message queue is full, dropping message")

    async def request(
        self,
        recipient: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.DATA,
        timeout: float = 5.0
    ) -> Optional[Message]:
        """
        发送请求并等待响应

        Args:
            recipient: 接收者
            content: 请求内容
            message_type: 消息类型
            timeout: 超时时间

        Returns:
            Optional[Message]: 响应消息
        """
        # 创建请求消息
        request = Message(
            type=message_type,
            content=content,
            sender="requester",
            recipient=recipient
        )

        # 创建响应等待器
        response_future = asyncio.Future()

        # 临时订阅响应
        def response_handler(message: Message):
            if message.reply_to == request.id:
                response_future.set_result(message)

        self.subscribe(message_type, response_handler)

        try:
            # 发送请求
            await self.publish(request)

            # 等待响应
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning(f"Request to {recipient} timed out")
            return None
        finally:
            # 取消订阅
            self.unsubscribe(message_type, response_handler)

    async def _worker(self, worker_name: str) -> None:
        """工作进程 - 处理消息队列"""
        logger.info(f"Message bus worker {worker_name} started")

        while self._running:
            try:
                # 从队列获取消息
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )

                # 分发消息
                await self._dispatch_message(message)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")

        logger.info(f"Message bus worker {worker_name} stopped")

    async def _dispatch_message(self, message: Message) -> None:
        """分发消息到订阅者"""
        delivered = False

        # 获取所有相关的订阅者
        subscribers = []

        # 添加类型订阅者
        subscribers.extend(self._subscribers[message.type])

        # 添加特定Agent订阅者
        if message.recipient:
            subscribers.extend(self._agent_subscribers.get(message.recipient, []))

        # 并发调用所有订阅者
        if subscribers:
            tasks = []
            for handler in subscribers:
                task = asyncio.create_task(self._safe_call_handler(handler, message))
                tasks.append(task)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 检查是否有成功的处理
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Handler error: {result}")
                    else:
                        delivered = True

        if delivered:
            self._stats["messages_delivered"] += 1
        else:
            self._stats["messages_failed"] += 1
            logger.warning(f"No subscribers for message {message.id}")

    async def _safe_call_handler(self, handler: Callable, message: Message) -> None:
        """安全调用处理函数"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
        except Exception as e:
            logger.error(f"Handler error: {e}")

    def _record_message(self, message: Message) -> None:
        """记录消息历史"""
        self._message_history[message.id] = message

        # 清理旧消息
        if len(self._message_history) > self._max_history:
            oldest_key = min(self._message_history.keys())
            del self._message_history[oldest_key]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "queue_size": self._message_queue.qsize(),
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values()),
            "history_size": len(self._message_history)
        }

    def get_message(self, message_id: str) -> Optional[Message]:
        """获取历史消息"""
        return self._message_history.get(message_id)

    def clear_history(self) -> None:
        """清空消息历史"""
        self._message_history.clear()
        logger.info("Message history cleared")