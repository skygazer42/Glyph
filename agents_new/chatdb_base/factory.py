"""
智能体工厂 - 基于ChatDB的工厂模式适配到Gove
"""

from typing import Dict, Any, Optional, Type
import logging
import uuid

from .base_agent import BaseAgent


class AgentFactory:
    """智能体工厂 - 管理所有智能体的创建和配置"""

    def __init__(self):
        """初始化工厂"""
        self.logger = logging.getLogger(__name__)
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._agent_instances: Dict[str, BaseAgent] = {}
        self._config: Dict[str, Any] = {}

    def register_agent_class(
        self,
        name: str,
        agent_class: Type[BaseAgent]
    ) -> None:
        """注册智能体类"""
        self._agent_classes[name] = agent_class
        self.logger.info(f"Registered agent class: {name}")

    def create_agent(
        self,
        name: str,
        agent_type: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """创建智能体实例"""
        if name not in self._agent_classes:
            raise ValueError(f"Agent class '{name}' not registered")

        # 获取配置
        config = self.get_agent_config(name, agent_type, **kwargs)

        # 创建实例
        agent_class = self._agent_classes[name]
        agent_id = f"{name}_{uuid.uuid4().hex[:8]}"
        instance = agent_class(
            agent_id=agent_id,
            **config
        )

        self.logger.info(f"Created agent instance: {agent_id}")

        return instance

    def get_or_create_agent(
        self,
        name: str,
        agent_type: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """获取或创建智能体实例（单例模式）"""
        cache_key = f"{name}_{agent_type or 'default'}"

        if cache_key not in self._agent_instances:
            self._agent_instances[cache_key] = self.create_agent(
                name, agent_type, **kwargs
            )

        return self._agent_instances[cache_key]

    def get_agent_config(
        self,
        name: str,
        agent_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """获取智能体配置"""
        config = self._config.get(name, {}).copy()
        config.update(kwargs)

        # 根据智能体类型添加特定配置
        if agent_type:
            type_config = self._config.get(f"{name}_{agent_type}", {})
            config.update(type_config)

        return config

    def set_config(self, name: str, config: Dict[str, Any]) -> None:
        """设置智能体配置"""
        self._config[name] = config

    def set_global_config(self, config: Dict[str, Any]) -> None:
        """设置全局配置"""
        self._config.update(config)

    def list_registered_agents(self) -> List[str]:
        """列出所有已注册的智能体"""
        return list(self._agent_classes.keys())

    def clear_cache(self) -> None:
        """清空实例缓存"""
        self._agent_instances.clear()
        self.logger.info("Cleared agent instance cache")

    def register_default_agents(self):
        """注册默认的智能体"""
        # 这里注册Gove系统需要的智能体
        from ..specialized.chat_agent import ChatAgent
        from ..specialized.calculation_agent import CalculationAgent
        from ..retrieval.query_analyzer import QueryAnalyzerAgent
        from ..analysis.policy_analyzer import PolicyAnalyzerAgent
        from ..generation.answer_generator import AnswerGeneratorAgent

        # 注册ChatDB风格的智能体
        self.register_agent_class("ChatAgent", ChatAgent)
        self.register_agent_class("CalculationAgent", CalculationAgent)
        self.register_agent_class("QueryAnalyzerAgent", QueryAnalyzerAgent)
        self.register_agent_class("PolicyAnalyzerAgent", PolicyAnalyzerAgent)
        self.register_agent_class("AnswerGeneratorAgent", AnswerGeneratorAgent)

        # 注册ChatDB原始智能体（稍后添加）
        # self.register_agent_class("SchemaRetrieverAgent", SchemaRetrieverAgent)
        # self.register_agent_class("SqlGeneratorAgent", SqlGeneratorAgent)
        # self.register_agent_class("SqlExplainerAgent", SqlExplainerAgent)
        # self.register_agent_class("SqlExecutorAgent", SqlExecutorAgent)
        # self.register_agent_class("VisualizationRecommenderAgent", VisualizationRecommenderAgent)

        self.logger.info("Registered default agents")

    def create_agent_chain(
        self,
        chain_name: str,
        agent_configs: List[Dict[str, Any]]
    ) -> List[BaseAgent]:
        """创建智能体链"""
        agents = []
        for config in agent_configs:
            name = config.pop("name")
            agent = self.create_agent(name, **config)
            agents.append(agent)

        self.logger.info(f"Created agent chain '{chain_name}' with {len(agents)} agents")
        return agents

    def get_metrics(self) -> Dict[str, Any]:
        """获取工厂指标"""
        return {
            "registered_classes": len(self._agent_classes),
            "active_instances": len(self._agent_instances),
            "config_count": len(self._config)
        }


# 全局工厂实例
agent_factory = AgentFactory()


def get_agent_factory() -> AgentFactory:
    """获取全局智能体工厂实例"""
    return agent_factory


def create_agent(name: str, **kwargs) -> BaseAgent:
    """便捷函数：创建智能体"""
    return agent_factory.create_agent(name, **kwargs)


def get_agent(name: str, **kwargs) -> BaseAgent:
    """便捷函数：获取智能体（单例）"""
    return agent_factory.get_or_create_agent(name, **kwargs)