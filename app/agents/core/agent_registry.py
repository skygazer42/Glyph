"""
Agent Registry - Agent注册中心
"""

from typing import Dict, List, Type, Optional, Any
import logging
from datetime import datetime

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
        dependencies: List[str] = None,
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
        self._enabled_agents: Dict[str, bool] = {}  # agent_id -> enabled

    def register(
        self,
        agent_id: str,
        agent_class: Type[AgentBase],
        agent_type: AgentType,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        dependencies: List[str] = None,
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

        # 从类型索引中移除
        if agent_info.agent_type in self._agents_by_type:
            self._agents_by_type[agent_info.agent_type] = [
                info for info in self._agents_by_type[agent_info.agent_type]
                if info.name != agent_id
            ]

        # 销毁实例
        if agent_id in self._instances:
            instance = self._instances[agent_id]
            asyncio.create_task(instance.shutdown())
            del self._instances[agent_id]

        # 移除注册信息
        del self._agents[agent_id]
        del self._enabled_agents[agent_id]

        logger.info(f"Unregistered agent {agent_id}")

    async def create_instance(
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
        if agent_id not in self._agents:
            logger.error(f"Agent {agent_id} not registered")
            return None

        if not self._enabled_agents[agent_id]:
            logger.error(f"Agent {agent_id} is disabled")
            return None

        if agent_id in self._instances:
            logger.warning(f"Agent {agent_id} instance already exists")
            return self._instances[agent_id]

        agent_info = self._agents[agent_id]

        try:
            # 创建实例
            instance = agent_info.agent_class(
                agent_id=agent_id,
                agent_type=agent_info.agent_type,
                name=agent_info.name,
                description=agent_info.description,
                version=agent_info.version
            )

            # 初始化
            config = config or {}
            success = await instance.initialize(config)
            if not success:
                logger.error(f"Failed to initialize agent {agent_id}")
                return None

            self._instances[agent_id] = instance
            logger.info(f"Created instance for agent {agent_id}")
            return instance

        except Exception as e:
            logger.error(f"Failed to create instance for agent {agent_id}: {e}")
            return None

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
        agents = []

        if agent_type:
            agents = self._agents_by_type.get(agent_type, [])
        else:
            agents = list(self._agents.values())

        if enabled_only:
            agents = [a for a in agents if self._enabled_agents.get(a.name, True)]

        return agents

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
        if not self.validate_dependencies(agent_id):
            return []

        chain = []
        visited = set()

        def dfs(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)

            # 先创建依赖
            for dep_id in self.get_dependencies(current_id):
                dfs(dep_id)

            # 创建当前Agent
            if current_id not in self._instances:
                asyncio.create_task(self.create_instance(current_id))

            if current_id in self._instances:
                chain.append(self._instances[current_id])

        dfs(agent_id)
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
        for agent_id, instance in self._instances.items():
            await instance.shutdown()
            logger.info(f"Shutdown agent {agent_id}")

        self._instances.clear()