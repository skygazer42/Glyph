"""
Agent Base Class - 所有Agent的基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from enum import Enum
from datetime import datetime
import asyncio
import logging

from ..models.base import AgentType, MessageType
from .message_bus import Message

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"


class AgentBase(ABC):
    """Agent基类 - 所有Agent都应继承此类"""

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        name: str,
        description: str = "",
        version: str = "1.0.0"
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.version = version
        self.status = AgentStatus.IDLE
        self.capabilities: List[str] = []
        self.dependencies: List[str] = []
        self.config: Dict[str, Any] = {}
        self.message_bus: Optional[Any] = None
        self._start_time: Optional[datetime] = None
        self._metrics: Dict[str, Any] = {
            "processed_count": 0,
            "error_count": 0,
            "avg_processing_time": 0.0
        }

    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化Agent

        Args:
            config: 配置参数

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.config.update(config)
            self.status = AgentStatus.IDLE
            logger.info(f"Agent {self.name} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize agent {self.name}: {e}")
            self.status = AgentStatus.ERROR
            return False

    @abstractmethod
    async def process(self, message: Message) -> Optional[Message]:
        """
        处理消息的核心方法，子类必须实现

        Args:
            message: 输入消息

        Returns:
            Optional[Message]: 处理后的消息
        """
        pass

    async def handle_message(self, message: Message) -> Optional[Message]:
        """
        消息处理入口，包含状态管理和错误处理

        Args:
            message: 输入消息

        Returns:
            Optional[Message]: 处理后的消息
        """
        if self.status == AgentStatus.DISABLED:
            logger.warning(f"Agent {self.name} is disabled, skipping message")
            return None

        if self.status == AgentStatus.ERROR:
            logger.warning(f"Agent {self.name} is in error state, skipping message")
            return None

        self.status = AgentStatus.BUSY
        self._start_time = datetime.now()

        try:
            # 记录处理开始
            logger.debug(f"Agent {self.name} processing message {message.id}")

            # 调用子类实现的process方法
            result = await self.process(message)

            # 更新指标
            self._update_metrics(True)

            # 发送结果到消息总线
            if result and self.message_bus:
                await self.message_bus.publish(result)

            return result

        except Exception as e:
            logger.error(f"Error in agent {self.name} processing message: {e}")
            self._update_metrics(False)

            # 创建错误消息
            error_message = Message(
                type=MessageType.ERROR,
                content={"error": str(e), "agent": self.name},
                sender=self.agent_id,
                recipient=message.sender,
                metadata={"original_message_id": message.id}
            )

            if self.message_bus:
                await self.message_bus.publish(error_message)

            return error_message

        finally:
            self.status = AgentStatus.IDLE

    async def send_message(
        self,
        recipient_id: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.DATA
    ) -> None:
        """
        发送消息到指定Agent

        Args:
            recipient_id: 接收者ID
            content: 消息内容
            message_type: 消息类型
        """
        if not self.message_bus:
            logger.warning(f"Agent {self.name} has no message bus configured")
            return

        message = Message(
            type=message_type,
            content=content,
            sender=self.agent_id,
            recipient=recipient_id
        )

        await self.message_bus.publish(message)

    def subscribe_to_messages(self, message_types: List[MessageType]) -> None:
        """
        订阅特定类型的消息

        Args:
            message_types: 要订阅的消息类型列表
        """
        if self.message_bus:
            for msg_type in message_types:
                self.message_bus.subscribe(msg_type, self.handle_message)

    def get_capabilities(self) -> List[str]:
        """获取Agent能力列表"""
        return self.capabilities.copy()

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态信息"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "type": self.agent_type.value,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "metrics": self._metrics,
            "uptime": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        }

    def _update_metrics(self, success: bool) -> None:
        """更新性能指标"""
        self._metrics["processed_count"] += 1
        if not success:
            self._metrics["error_count"] += 1

        # 更新平均处理时间
        if self._start_time:
            processing_time = (datetime.now() - self._start_time).total_seconds()
            count = self._metrics["processed_count"]
            self._metrics["avg_processing_time"] = (
                (self._metrics["avg_processing_time"] * (count - 1) + processing_time) / count
            )

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            bool: Agent是否健康
        """
        return self.status != AgentStatus.ERROR

    async def shutdown(self) -> None:
        """关闭Agent，清理资源"""
        self.status = AgentStatus.DISABLED
        logger.info(f"Agent {self.name} shutdown completed")

    def __repr__(self) -> str:
        return f"<AgentBase(id={self.agent_id}, name={self.name}, type={self.agent_type.value})>"