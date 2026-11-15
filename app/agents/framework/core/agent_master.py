"""
Agent Master Controller - Agent总控制器
"""

import asyncio
from typing import Dict, Any, Optional, Type, Callable
import logging
from datetime import datetime
from functools import partial
import json
from pathlib import Path
from contextlib import AsyncExitStack

from app.utils.lifecycle import close_with_timeout

from ..models.base import AgentType, MessageType, QueryIntent
from .agent_base import AgentBase
from .agent_registry import AgentRegistry
from .message_bus import MessageBus, Message
from .orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class AgentMasterController:
    """
    Agent总控制器 - 统一管理所有Agent的生命周期和协作
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.registry = AgentRegistry()
        self.message_bus = MessageBus()
        self.orchestrator = AgentOrchestrator(self.registry, self.message_bus)
        self.running = False
        self.start_time: Optional[datetime] = None
        self._shutdown_event = asyncio.Event()
        self._creation_tasks: set[asyncio.Task[Optional[AgentBase]]] = set()

        # 内置工作流
        self.built_in_workflows: Dict[str, Callable] = {}
        self._load_builtin_workflows()

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        初始化控制器

        Args:
            config: 配置参数

        Returns:
            bool: 初始化是否成功
        """
        try:
            # 加载配置
            if config is not None:
                self.config.update(config)
            elif self.config_path:
                await self._load_config()

            # 启动消息总线
            await self.message_bus.start()

            # 自动注册Agent
            await self._auto_register_agents()

            # 初始化默认Agent实例
            await self._initialize_default_agents()

            self._shutdown_event.clear()
            self.running = True
            self.start_time = datetime.now()

            logger.info("Agent Master Controller initialized successfully")
            return True

        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception:
            logger.exception("Failed to initialize controller")
            try:
                await self.stop()
            except Exception:
                logger.exception("Failed to clean up partially initialized controller")
            return False

    async def start(self) -> None:
        """启动控制器"""
        if not self.running:
            if not await self.initialize():
                raise RuntimeError("Agent Master Controller initialization failed")

        logger.info("Agent Master Controller started")

        # 等待关闭信号
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """停止控制器"""
        logger.info("Stopping Agent Master Controller...")

        self.running = False
        self._shutdown_event.set()

        async with AsyncExitStack() as stack:
            stack.push_async_callback(close_with_timeout, self.message_bus.stop)
            stack.push_async_callback(close_with_timeout, self.registry.shutdown_all)
            tasks, self._creation_tasks = self._creation_tasks, set()
            for task in tasks:
                task.cancel()
            if tasks:
                results = await close_with_timeout(
                    partial(asyncio.gather, *tasks, return_exceptions=True)
                )
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(
                            "Agent creation failed during shutdown: %s", result,
                            exc_info=(type(result), result, result.__traceback__),
                        )

        logger.info("Agent Master Controller stopped")

    def register_agent_module(
        self,
        agent_id: str,
        agent_class: Type[AgentBase],
        agent_type: AgentType,
        name: str,
        description: str = "",
        auto_create: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册Agent模块

        Args:
            agent_id: Agent唯一标识
            agent_class: Agent类
            agent_type: Agent类型
            name: Agent名称
            description: 描述
            auto_create: 是否自动创建实例
            config: 配置参数
        """
        loop = asyncio.get_running_loop() if auto_create else None
        # 注册到注册中心
        self.registry.register(
            agent_id=agent_id,
            agent_class=agent_class,
            agent_type=agent_type,
            name=name,
            description=description
        )

        # 自动创建实例
        if loop is not None:
            self._creation_tasks.add(loop.create_task(self.create_agent_instance(agent_id, config)))

    async def create_agent_instance(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentBase]:
        """
        创建Agent实例

        Args:
            agent_id: Agent ID
            config: 配置参数

        Returns:
            Optional[AgentBase]: Agent实例
        """
        instance = await self.registry.create_instance(agent_id, config)
        if instance:
            # 设置消息总线
            instance.message_bus = self.message_bus

            # 订阅消息
            instance.subscribe_to_messages([MessageType.USER_QUERY, MessageType.DATA])

        return instance

    async def process_request(
        self,
        request: Dict[str, Any],
        workflow_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        处理用户请求

        Args:
            request: 请求数据
            workflow_name: 指定的工作流名称

        Returns:
            Optional[Dict[str, Any]]: 处理结果
        """
        # 创建消息
        message = Message(
            type=MessageType.USER_QUERY,
            content=request,
            sender="user",
            recipient="system"
        )

        # 如果指定了工作流，使用编排器执行
        if workflow_name is not None:
            result = await self.orchestrator.execute_workflow(
                workflow_name,
                message,
                {"request": request}
            )
            return result.content if result else None

        # 否则使用默认处理流程
        return await self._default_process(message)

    async def _default_process(self, message: Message) -> Optional[Dict[str, Any]]:
        """默认处理流程"""
        # 1. 路由到意图识别Agent
        router_instance = await self.registry.get_instance("intent_router")
        if not router_instance:
            logger.error("Intent router not found")
            return None

        # 处理消息
        router_result = await router_instance.handle_message(message)
        if not router_result:
            return None

        # 2. 根据意图选择处理流程
        intent = QueryIntent(router_result.content["intent"])
        context = router_result.content.get("context", {})

        # 选择合适的工作流
        workflow_name = self._select_workflow(intent, context)

        if workflow_name:
            result = await self.orchestrator.execute_workflow(
                workflow_name,
                message,
                context
            )
            return result.content if result else None

        # 3. 直接路由到合适的Agent
        target_agent_id = self._route_to_agent(intent)
        if target_agent_id:
            target_agent = await self.registry.get_instance(target_agent_id)
            if target_agent:
                result = await target_agent.handle_message(message)
                return result.content if result else None

        return None

    def _select_workflow(self, intent: QueryIntent, context: Dict[str, Any]) -> Optional[str]:
        """根据意图选择工作流"""
        workflow_mapping = {
            QueryIntent.ELIGIBILITY_CHECK: "eligibility_workflow",
            QueryIntent.BENEFIT_CALCULATION: "calculation_workflow",
            QueryIntent.APPLICATION_PROCESS: "application_workflow",
            QueryIntent.COMPARISON: "comparison_workflow",
            QueryIntent.POLICY_INQUIRY: "documentation_workflow"
        }
        return workflow_mapping.get(intent)

    def _route_to_agent(self, intent: QueryIntent) -> Optional[str]:
        """直接路由到Agent"""
        agent_mapping = {
            QueryIntent.ELIGIBILITY_CHECK: "policy_analyzer",
            QueryIntent.BENEFIT_CALCULATION: "calculation_agent",
            QueryIntent.APPLICATION_PROCESS: "application_agent",
            QueryIntent.POLICY_INQUIRY: "retrieval_agent"
        }
        return agent_mapping.get(intent)

    async def create_workflow_from_config(
        self,
        workflow_name: str,
        config: Dict[str, Any]
    ) -> None:
        """
        从配置创建工作流

        Args:
            workflow_name: 工作流名称
            config: 工作流配置
        """
        workflow_type = config.get("type", "sequential")

        if workflow_type == "sequential":
            agents = config["agents"]
            self.orchestrator.create_simple_workflow(
                workflow_name,
                agents,
                config.get("description", "")
            )
        elif workflow_type == "conditional":
            branches = config["branches"]
            default = config.get("default_branch")
            self.orchestrator.create_conditional_workflow(
                workflow_name,
                branches,
                default,
                config.get("description", "")
            )
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

    async def _auto_register_agents(self) -> None:
        """Core controllers require explicit Core-protocol agent registration."""
        if not self.registry.list_agents():
            raise ValueError("Register AgentBase subclasses before initialization; policy packs use AgentChatTeam")

    async def _initialize_default_agents(self) -> None:
        """初始化默认Agent实例"""
        tasks = tuple(self._creation_tasks)
        if tasks:
            try:
                results = await asyncio.gather(*tasks)
            finally:
                self._creation_tasks.difference_update(task for task in tasks if task.done())
            if any(instance is None for instance in results):
                raise RuntimeError("An automatically created agent failed initialization")
        for agent_id in self.registry.list_agent_ids():
            if await self.create_agent_instance(agent_id) is None:
                raise RuntimeError(f"Agent {agent_id} failed initialization")

    def _load_builtin_workflows(self) -> None:
        """加载内置工作流"""
        # 资格查询工作流
        self.built_in_workflows["eligibility_workflow"] = lambda: self.orchestrator.create_simple_workflow(
            "eligibility_workflow",
            ["query_analyzer", "policy_analyzer", "answer_generator"],
            "政策资格查询流程"
        )

        # 补贴计算工作流
        self.built_in_workflows["calculation_workflow"] = lambda: self.orchestrator.create_simple_workflow(
            "calculation_workflow",
            ["query_analyzer", "calculation_agent", "answer_generator"],
            "补贴金额计算流程"
        )

        # 申请流程工作流
        self.built_in_workflows["application_workflow"] = lambda: self.orchestrator.create_simple_workflow(
            "application_workflow",
            ["query_analyzer", "application_agent", "document_retriever", "answer_generator"],
            "申请流程指导流程"
        )

    async def _load_config(self) -> None:
        """Read owned filesystem configuration outside the event loop."""
        if self.config_path is not None:
            self.config = await asyncio.to_thread(self._read_config, self.config_path)

    @staticmethod
    def _read_config(path: str) -> Dict[str, Any]:
        with Path(path).open(encoding="utf-8") as config_file:
            return json.load(config_file)

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        uptime = 0.0
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()

        return {
            "controller": {
                "running": self.running,
                "uptime": uptime,
                "start_time": self.start_time.isoformat() if self.start_time else None
            },
            "registry": self.registry.get_stats(),
            "message_bus": self.message_bus.get_stats(),
            "orchestrator": self.orchestrator.get_stats()
        }

    async def health_check(self) -> bool:
        """健康检查"""
        if not self.running:
            return False

        # 检查关键组件
        try:
            # 检查消息总线
            bus_stats = self.message_bus.get_stats()
            if bus_stats["queue_size"] > bus_stats["subscriber_count"] * 10:
                logger.warning("Message bus queue size is too large")

            # 检查Agent实例
            for agent_id, instance in self.registry._instances.items():
                if not await instance.health_check():
                    logger.warning(f"Agent {agent_id} is unhealthy")
                    return False

            return True

        except Exception:
            logger.exception("Health check failed")
            return False

    async def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            await self._load_config()
            logger.info("Configuration reloaded")
            return True
        except Exception:
            logger.exception("Failed to reload configuration")
            return False

    def save_config(self, path: str) -> bool:
        """保存配置"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            logger.exception("Failed to save configuration")
            return False
