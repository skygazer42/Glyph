"""
Agent Registry - Agent注册中心
"""

from typing import Dict, List, Type, Optional, Any
import logging
import asyncio
from datetime import datetime
from functools import partial

from app.utils.lifecycle import close_with_timeout

from ..models.base import AgentType
from .agent_base import AgentBase

logger = logging.getLogger(__name__)


class AgentInfo:
    """Agent信息"""

    def __init__(
        self,
        agent_class: Type[AgentBase],
        agent_type: AgentType,
        name: str,
        description: str,
        version: str,
        dependencies: Optional[List[str]] = None,
        config_schema: Optional[Dict[str, Any]] = None
    ):
        self.agent_class = agent_class
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.version = version
        self.dependencies = dependencies or []
        self.config_schema = config_schema or {}
        self.registered_at = datetime.now()


class AgentRegistry:
    """Agent注册中心 - 管理所有Agent的注册和发现"""

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}  # agent_id -> AgentInfo
        self._agents_by_type: Dict[AgentType, List[AgentInfo]] = {}
        self._instances: Dict[str, AgentBase] = {}  # agent_id -> Agent instance
        self._creation_locks: Dict[str, asyncio.Lock] = {}
        self._shutdown_tasks: List[asyncio.Task] = []
        self._enabled_agents: Dict[str, bool] = {}  # agent_id -> enabled

    def register(
        self,
        agent_id: str,
        agent_class: Type[AgentBase],
        agent_type: AgentType,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        config_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册Agent

        Args:
            agent_id: Agent唯一标识
            agent_class: Agent类
            agent_type: Agent类型
            name: Agent名称
            description: 描述
            version: 版本
            dependencies: 依赖的Agent列表
            config_schema: 配置模式
        """
        if not issubclass(agent_class, AgentBase):
            raise TypeError("Registry agents must implement the framework AgentBase protocol")
        if agent_id in self._agents:
            logger.warning(f"Agent {agent_id} already registered, updating...")
            self.unregister(agent_id)

        agent_info = AgentInfo(
            agent_class=agent_class,
            agent_type=agent_type,
            name=name,
            description=description,
            version=version,
            dependencies=dependencies,
            config_schema=config_schema
        )

        self._agents[agent_id] = agent_info
        self._enabled_agents[agent_id] = True

        # 按类型索引
        if agent_type not in self._agents_by_type:
            self._agents_by_type[agent_type] = []
        self._agents_by_type[agent_type].append(agent_info)

        logger.info(f"Registered agent {agent_id} ({name})")

    def unregister(self, agent_id: str) -> None:
        """
        注销Agent

        Args:
            agent_id: Agent ID
        """
        if agent_id not in self._agents:
            logger.warning(f"Agent {agent_id} not registered")
            return

        agent_info = self._agents[agent_id]
        # Validate ownership before changing indexes or creating a coroutine.
        loop = asyncio.get_running_loop() if agent_id in self._instances else None

        # 从类型索引中移除
        if agent_info.agent_type in self._agents_by_type:
            self._agents_by_type[agent_info.agent_type] = [
                info for info in self._agents_by_type[agent_info.agent_type]
                if info is not agent_info
            ]

        # 销毁实例
        if agent_id in self._instances:
            instance = self._instances[agent_id]
            assert loop is not None
            self._shutdown_tasks.append(loop.create_task(close_with_timeout(instance.shutdown)))
            del self._instances[agent_id]

        # 移除注册信息
        del self._agents[agent_id]
        del self._enabled_agents[agent_id]

        logger.info(f"Unregistered agent {agent_id}")

    async def create_instance(self, agent_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[AgentBase]:
        lock = self._creation_locks.setdefault(agent_id, asyncio.Lock())
        async with lock:
            info = self._agents.get(agent_id)
            if info is None or not self.is_enabled(agent_id):
                return None
            if agent_id in self._instances:
                return self._instances[agent_id]
            instance = info.agent_class(agent_id=agent_id, agent_type=info.agent_type,
                name=info.name, description=info.description, version=info.version)
            published = False
            try:
                if not await instance.initialize({} if config is None else config):
                    return None
                if self._agents.get(agent_id) is not info or not self.is_enabled(agent_id):
                    return None
                self._instances[agent_id] = instance
                published = True
                return instance
            except Exception:
                logger.exception("Failed to create instance for agent %s", agent_id)
                return None
            finally:
                if not published:
                    await close_with_timeout(instance.shutdown)

    async def get_instance(self, agent_id: str) -> Optional[AgentBase]:
        """
        获取Agent实例

        Args:
            agent_id: Agent ID

        Returns:
            Optional[AgentBase]: Agent实例
        """
        return self._instances.get(agent_id)

    def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """
        获取Agent信息

        Args:
            agent_id: Agent ID

        Returns:
            Optional[AgentInfo]: Agent信息
        """
        return self._agents.get(agent_id)

    def list_agent_ids(self) -> List[str]:
        """Return enabled registry identities without confusing them with display names."""
        return [agent_id for agent_id in self._agents if self.is_enabled(agent_id)]

    def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        enabled_only: bool = True
    ) -> List[AgentInfo]:
        """
        列出所有Agent

        Args:
            agent_type: 过滤特定类型
            enabled_only: 只列出启用的Agent

        Returns:
            List[AgentInfo]: Agent信息列表
        """
        return [info for agent_id, info in self._agents.items()
                if (agent_type is None or info.agent_type == agent_type)
                and (not enabled_only or self.is_enabled(agent_id))]

    def enable_agent(self, agent_id: str) -> None:
        """启用Agent"""
        if agent_id in self._agents:
            self._enabled_agents[agent_id] = True
            logger.info(f"Enabled agent {agent_id}")

    def disable_agent(self, agent_id: str) -> None:
        """禁用Agent"""
        if agent_id in self._agents:
            self._enabled_agents[agent_id] = False
            logger.info(f"Disabled agent {agent_id}")

    def is_enabled(self, agent_id: str) -> bool:
        """检查Agent是否启用"""
        return self._enabled_agents.get(agent_id, False)

    def get_dependencies(self, agent_id: str) -> List[str]:
        """获取Agent依赖"""
        agent_info = self._agents.get(agent_id)
        return agent_info.dependencies if agent_info else []

    def validate_dependencies(self, agent_id: str) -> bool:
        """
        验证Agent依赖是否满足

        Args:
            agent_id: Agent ID

        Returns:
            bool: 依赖是否满足
        """
        dependencies = self.get_dependencies(agent_id)
        for dep in dependencies:
            if dep not in self._agents:
                logger.error(f"Dependency {dep} not found for agent {agent_id}")
                return False
            if not self._enabled_agents.get(dep, False):
                logger.error(f"Dependency {dep} is disabled for agent {agent_id}")
                return False
        return True

    async def create_dependency_chain(self, agent_id: str) -> List[AgentBase]:
        """
        创建依赖链

        Args:
            agent_id: Agent ID

        Returns:
            List[AgentBase]: 按依赖顺序排列的Agent实例列表
        """
        chain: List[AgentBase] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        async def visit(current_id: str) -> None:
            if current_id in visiting:
                raise ValueError(f"Cyclic agent dependency: {current_id}")
            if current_id in visited:
                return
            if current_id not in self._agents or not self.is_enabled(current_id):
                raise ValueError(f"Unavailable agent dependency: {current_id}")
            visiting.add(current_id)
            for dependency in self.get_dependencies(current_id):
                await visit(dependency)
            instance = await self.create_instance(current_id)
            if instance is None:
                raise RuntimeError(f"Agent initialization failed: {current_id}")
            chain.append(instance)
            visiting.remove(current_id)
            visited.add(current_id)

        await visit(agent_id)
        return chain

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_agents": len(self._agents),
            "enabled_agents": sum(1 for enabled in self._enabled_agents.values() if enabled),
            "active_instances": len(self._instances),
            "agents_by_type": {
                agent_type.value: len(agents)
                for agent_type, agents in self._agents_by_type.items()
            }
        }

    async def shutdown_all(self) -> None:
        """关闭所有Agent实例"""
        instances, self._instances = self._instances, {}
        pending, self._shutdown_tasks = self._shutdown_tasks, []
        results = await close_with_timeout(partial(
            asyncio.gather,
            *(close_with_timeout(instance.shutdown) for instance in instances.values()),
            *pending,
            return_exceptions=True,
        ))
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, Exception):
                raise result
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            for error in errors:
                logger.error(
                    "Agent shutdown failure: %s", error,
                    exc_info=(type(error), error, error.__traceback__),
                )
            raise RuntimeError(f"{len(errors)} agent shutdowns failed") from errors[0]
