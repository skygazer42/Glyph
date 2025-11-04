"""
AG Builder - Agent构建器模块示例
"""

import asyncio
from typing import Dict, Any, Optional
import logging

from ...models.base import AgentType, MessageType
from ..core.agent_base import AgentBase
from ..core.message_bus import Message

logger = logging.getLogger(__name__)


class AgentBuilder(AgentBase):
    """
    Agent构建器 - 负责动态创建和配置其他Agent
    """

    def __init__(self):
        super().__init__(
            agent_id="agent_builder",
            agent_type=AgentType.SPECIALIZED,
            name="Agent Builder",
            description="动态构建和配置Agent模块"
        )
        self.capabilities = [
            "create_agent",
            "configure_agent",
            "destroy_agent",
            "list_agents",
            "validate_config"
        ]
        self._agent_templates: Dict[str, Dict[str, Any]] = {}
        self._load_default_templates()

    async def process(self, message: Message) -> Optional[Message]:
        """处理构建请求"""
        try:
            action = message.content.get("action")
            agent_type = message.content.get("agent_type")
            config = message.content.get("config", {})

            logger.info(f"Processing builder action: {action} for agent type: {agent_type}")

            # 根据动作执行相应操作
            if action == "create":
                result = await self._create_agent(agent_type, config)
            elif action == "configure":
                result = await self._configure_agent(message.content.get("agent_id"), config)
            elif action == "destroy":
                result = await self._destroy_agent(message.content.get("agent_id"))
            elif action == "list":
                result = await self._list_agents()
            elif action == "validate_config":
                result = self._validate_config(agent_type, config)
            else:
                result = {"error": f"Unknown action: {action}"}

            return message.create_reply(
                content={
                    "action": action,
                    "result": result,
                    "status": "success" if "error" not in result else "failed"
                },
                sender=self.agent_id
            )

        except Exception as e:
            logger.error(f"Error in agent builder: {e}")
            return message.create_reply(
                content={"error": str(e)},
                sender=self.agent_id
            )

    async def _create_agent(self, agent_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """创建新的Agent实例"""
        # 检查模板
        if agent_type not in self._agent_templates:
            return {"error": f"Unknown agent type: {agent_type}"}

        template = self._agent_templates[agent_type]

        # 生成唯一的Agent ID
        agent_id = f"{agent_type}_{config.get('name', 'unnamed')}_{asyncio.get_event_loop().time()}"

        # 这里应该通过总控制器来创建Agent
        # 示例实现
        try:
            # 模拟创建过程
            logger.info(f"Creating agent {agent_id} with type {agent_type}")

            # 保存Agent配置
            created_agent = {
                "id": agent_id,
                "type": agent_type,
                "config": config,
                "template": template,
                "created_at": asyncio.get_event_loop().time()
            }

            return {
                "agent": created_agent,
                "message": f"Agent {agent_id} created successfully"
            }

        except Exception as e:
            return {"error": f"Failed to create agent: {e}"}

    async def _configure_agent(self, agent_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """配置现有Agent"""
        if not agent_id:
            return {"error": "Agent ID is required"}

        # 模拟配置过程
        logger.info(f"Configuring agent {agent_id}")

        return {
            "agent_id": agent_id,
            "config_applied": config,
            "message": f"Agent {agent_id} configured successfully"
        }

    async def _destroy_agent(self, agent_id: str) -> Dict[str, Any]:
        """销毁Agent实例"""
        if not agent_id:
            return {"error": "Agent ID is required"}

        # 模拟销毁过程
        logger.info(f"Destroying agent {agent_id}")

        return {
            "agent_id": agent_id,
            "message": f"Agent {agent_id} destroyed successfully"
        }

    async def _list_agents(self) -> Dict[str, Any]:
        """列出所有Agent"""
        # 模拟列出Agent
        agents = [
            {
                "id": "query_analyzer_001",
                "type": "query_analyzer",
                "status": "running",
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "policy_analyzer_001",
                "type": "policy_analyzer",
                "status": "running",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]

        return {"agents": agents}

    def _validate_config(self, agent_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证Agent配置"""
        if agent_type not in self._agent_templates:
            return {"valid": False, "error": f"Unknown agent type: {agent_type}"}

        template = self._agent_templates[agent_type]
        required_fields = template.get("required_fields", [])

        # 检查必填字段
        missing_fields = []
        for field in required_fields:
            if field not in config:
                missing_fields.append(field)

        if missing_fields:
            return {
                "valid": False,
                "error": f"Missing required fields: {missing_fields}"
            }

        # 验证字段类型
        field_types = template.get("field_types", {})
        for field, expected_type in field_types.items():
            if field in config and not isinstance(config[field], expected_type):
                return {
                    "valid": False,
                    "error": f"Field {field} must be of type {expected_type.__name__}"
                }

        return {
            "valid": True,
            "message": "Configuration is valid"
        }

    def _load_default_templates(self) -> None:
        """加载默认Agent模板"""
        self._agent_templates = {
            "query_analyzer": {
                "description": "分析用户查询并提取关键信息",
                "required_fields": ["model_name"],
                "field_types": {
                    "model_name": str,
                    "temperature": float,
                    "max_tokens": int
                },
                "default_config": {
                    "model_name": "gpt-3.5-turbo",
                    "temperature": 0.0,
                    "max_tokens": 1000
                }
            },
            "policy_analyzer": {
                "description": "分析政策内容并提供解答",
                "required_fields": ["model_name", "knowledge_base"],
                "field_types": {
                    "model_name": str,
                    "knowledge_base": str,
                    "temperature": float
                },
                "default_config": {
                    "model_name": "gpt-4",
                    "knowledge_base": "policy_db",
                    "temperature": 0.1
                }
            },
            "retriever": {
                "description": "从知识库检索相关信息",
                "required_fields": ["vector_store", "embedding_model"],
                "field_types": {
                    "vector_store": str,
                    "embedding_model": str,
                    "top_k": int
                },
                "default_config": {
                    "vector_store": "chroma",
                    "embedding_model": "text-embedding-ada-002",
                    "top_k": 5
                }
            },
            "generator": {
                "description": "生成最终答案",
                "required_fields": ["model_name"],
                "field_types": {
                    "model_name": str,
                    "temperature": float,
                    "max_tokens": int
                },
                "default_config": {
                    "model_name": "gpt-3.5-turbo",
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
            }
        }