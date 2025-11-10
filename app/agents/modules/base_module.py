"""
Agent模块基类 - 定义通用的接口和行为
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgentModule(ABC):
    """Agent模块基类"""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.description = ""
        self.is_running = False
        self.config: Dict[str, Any] = {}
        self.metrics = {
            "processed_count": 0,
            "error_count": 0,
            "total_time": 0.0
        }

    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理数据的核心方法，子类必须实现

        Args:
            data: 输入数据

        Returns:
            Dict[str, Any]: 处理后的数据
        """
        pass

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """初始化模块"""
        if config:
            self.config.update(config)
        self.is_running = True
        logger.info(f"Module {self.name} initialized")
        return True

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理请求的入口，包含错误处理和指标统计"""
        if not self.is_running:
            return {"error": f"Module {self.name} is not running"}

        start_time = datetime.now()
        self.metrics["processed_count"] += 1

        try:
            # 调用子类实现
            result = await self.process(data)

            # 记录处理时间
            elapsed = (datetime.now() - start_time).total_seconds()
            self.metrics["total_time"] += elapsed

            return result

        except Exception as e:
            self.metrics["error_count"] += 1
            logger.error(f"Error in {self.name}: {e}")
            return {"error": str(e), "module": self.name}

    async def start(self):
        """启动模块"""
        await self.initialize()
        logger.info(f"Module {self.name} started")

    async def stop(self):
        """停止模块"""
        self.is_running = False
        logger.info(f"Module {self.name} stopped")

    def get_info(self) -> Dict[str, Any]:
        """获取模块信息"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "is_running": self.is_running,
            "metrics": self.metrics.copy(),
            "avg_time": (
                self.metrics["total_time"] / self.metrics["processed_count"]
                if self.metrics["processed_count"] > 0 else 0
            )
        }

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} v{self.version}>"