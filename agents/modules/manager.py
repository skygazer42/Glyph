"""
Agent管理器 - 管理和协调所有Agent模块
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging

from .base_module import BaseAgentModule

logger = logging.getLogger(__name__)


class AgentManager:
    """Agent管理器 - 简化的总控制器"""

    def __init__(self):
        self.modules: Dict[str, BaseAgentModule] = {}
        self.pipelines: Dict[str, List[str]] = {}
        self.is_running = False
        self.message_handlers: Dict[str, List[Callable]] = {}

    def register(self, module: BaseAgentModule) -> None:
        """注册Agent模块"""
        self.modules[module.name] = module
        logger.info(f"Registered module: {module.name}")

    def create_pipeline(self, name: str, module_names: List[str]) -> None:
        """创建处理流水线"""
        # 验证所有模块都存在
        for module_name in module_names:
            if module_name not in self.modules:
                raise ValueError(f"Module {module_name} not found")

        self.pipelines[name] = module_names
        logger.info(f"Created pipeline: {name} -> {module_names}")

    async def run_pipeline(self, pipeline_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """运行处理流水线"""
        if pipeline_name not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_name} not found")

        module_names = self.pipelines[pipeline_name]
        current_data = data.copy()

        # 记录开始时间
        start_time = datetime.now()

        # 依次执行每个模块
        for module_name in module_names:
            module = self.modules[module_name]
            if not module.is_running:
                logger.warning(f"Module {module_name} is not running, skipping")
                continue

            logger.info(f"Running module: {module_name}")
            current_data = await module.handle(current_data)

            # 如果模块返回错误，停止流水线
            if current_data.get("error"):
                logger.error(f"Module {module_name} returned error")
                break

        # 记录处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        current_data["processing_time"] = processing_time
        current_data["pipeline_name"] = pipeline_name

        return current_data

    async def start_all(self) -> None:
        """启动所有模块"""
        for module in self.modules.values():
            await module.start()
        self.is_running = True
        logger.info("AgentManager started")

    async def stop_all(self) -> None:
        """停止所有模块"""
        for module in self.modules.values():
            await module.stop()
        self.is_running = False
        logger.info("AgentManager stopped")

    def get_module(self, name: str) -> Optional[BaseAgentModule]:
        """获取模块实例"""
        return self.modules.get(name)

    def get_status(self) -> Dict[str, Any]:
        """获取所有模块状态"""
        return {
            "manager_running": self.is_running,
            "modules": {
                name: module.get_info()
                for name, module in self.modules.items()
            },
            "pipelines": self.pipelines
        }

    async def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        health_status = {}
        for name, module in self.modules.items():
            health_status[name] = module.is_running
        return health_status


# 便捷的使用函数
async def create_default_manager() -> AgentManager:
    """创建包含默认模块的管理器"""
    from .query_agent import QueryAgent
    from .retrieval_agent import RetrievalAgent
    from .generation_agent import GenerationAgent

    # 创建管理器
    manager = AgentManager()

    # 注册模块
    manager.register(QueryAgent())
    manager.register(RetrievalAgent())
    manager.register(GenerationAgent())

    # 创建默认流水线
    manager.create_pipeline("policy_qa", [
        "query_analyzer",
        "retrieval_agent",
        "generation_agent"
    ])

    # 启动所有模块
    await manager.start_all()

    return manager