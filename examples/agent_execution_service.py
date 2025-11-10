"""
智能体执行服务 - 基于AutoGen 0.6.1
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_core.models import ChatCompletionClient

from app.models.agent_config import AgentConfig
from app.models.template import WritingFieldConfig
from app.services.agent_service import agent_service
from app.core.model_clients import get_model_client, get_default_model_client

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """智能体执行服务"""

    def __init__(self):
        # 不再需要自己管理模型客户端，使用统一的模型客户端管理器
        pass

    def _get_model_client(self, model_name: str) -> ChatCompletionClient:
        """获取模型客户端"""
        try:
            # 使用统一的模型客户端管理器
            return get_model_client(model_name=model_name)
        except Exception as e:
            logger.warning(f"获取指定模型客户端失败，使用默认客户端: {e}")
            return get_default_model_client()

    def _create_agent_from_config(self, agent_config: AgentConfig) -> AssistantAgent:
        """根据配置创建智能体"""
        try:
            # 获取模型客户端
            model_client = self._get_model_client(agent_config.model_name)

            if not model_client:
                raise ValueError(f"无法找到模型 {agent_config.model_name} 的客户端")

            # 生成符合AutoGen要求的英文名称
            safe_name = self._generate_safe_agent_name(agent_config.name)

            # 创建智能体
            agent = AssistantAgent(
                name=safe_name,
                model_client=model_client,
                system_message=agent_config.system_prompt,
                description=agent_config.description or agent_config.name
            )

            logger.info(f"智能体 {agent_config.name} (内部名称: {safe_name}) 创建成功")
            return agent

        except Exception as e:
            logger.error(f"创建智能体失败: {e}")
            raise

    def _generate_safe_agent_name(self, original_name: str) -> str:
        """生成符合AutoGen要求的安全名称"""
        # 定义中文到英文的映射
        name_mapping = {
            "标题生成助手": "title_generator",
            "表彰原因生成助手": "commendation_generator",
            "关键词提取助手": "keyword_extractor",
            "批评通报生成助手": "criticism_generator",
            "会议纪要生成助手": "meeting_minutes_generator",
            "文档审核助手": "document_reviewer",
            "内容优化助手": "content_optimizer"
        }

        # 如果有预定义的映射，使用映射
        if original_name in name_mapping:
            return name_mapping[original_name]

        # 否则生成一个安全的名称
        import re
        import hashlib

        # 移除所有非字母数字字符，替换为下划线
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', original_name)

        # 如果名称为空或只有下划线，使用hash
        if not safe_name or safe_name.replace('_', '').replace('-', '') == '':
            # 使用原始名称的hash生成唯一标识
            hash_obj = hashlib.md5(original_name.encode('utf-8'))
            safe_name = f"agent_{hash_obj.hexdigest()[:8]}"

        # 确保名称以字母开头
        if safe_name and not safe_name[0].isalpha():
            safe_name = f"agent_{safe_name}"

        return safe_name

    def _format_user_prompt(self, agent_config: AgentConfig, context: Dict[str, Any]) -> str:
        """格式化用户提示词"""
        try:
            if agent_config.user_prompt_template:
                # 使用模板格式化，处理缺失的键
                template = agent_config.user_prompt_template
                # 替换模板中的占位符
                for key, value in context.items():
                    placeholder = "{" + key + "}"
                    if placeholder in template:
                        template = template.replace(placeholder, str(value or ""))

                # 移除未替换的占位符
                import re
                template = re.sub(r'\{[^}]+\}', '', template)
                return template.strip()
            else:
                # 如果没有模板，使用默认格式
                content_parts = []
                for key, value in context.items():
                    if value and key != 'user_input':
                        content_parts.append(f"{key}: {value}")

                if context.get('user_input'):
                    content_parts.append(f"用户输入: {context['user_input']}")

                return "\n".join(content_parts) if content_parts else context.get('user_input', '请生成内容')

        except Exception as e:
            logger.warning(f"格式化提示词失败，使用默认内容: {e}")
            user_input = context.get('user_input', '')
            if user_input:
                return user_input
            else:
                # 构建基本提示词
                content_type = context.get('content_type', '文档')
                field_name = context.get('field_name', '内容')
                return f"请为{content_type}生成{field_name}"

    async def execute_agent_for_field(
        self, 
        db: Session, 
        field_id: int, 
        context: Dict[str, Any],
        user_input: Optional[str] = None
    ) -> Dict[str, Any]:
        """为字段执行智能体"""
        try:
            # 获取字段配置
            field_config = db.query(WritingFieldConfig).filter(
                WritingFieldConfig.id == field_id
            ).first()
            
            if not field_config or not field_config.agent_config_id:
                return {
                    "success": False,
                    "error": "字段未配置智能体"
                }

            # 获取智能体配置
            agent_config = agent_service.get_agent_config(db, field_config.agent_config_id)
            if not agent_config:
                return {
                    "success": False,
                    "error": "智能体配置不存在"
                }

            # 创建智能体
            agent = self._create_agent_from_config(agent_config)

            # 准备上下文
            execution_context = {
                "field_name": field_config.field_name,
                "field_type": field_config.field_type,
                "user_input": user_input or "",
                **context
            }

            # 格式化用户提示词
            user_prompt = self._format_user_prompt(agent_config, execution_context)

            # 执行智能体
            logger.info(f"开始执行智能体 {agent_config.name} 为字段 {field_config.field_name}")
            
            # 创建团队（即使只有一个智能体）
            team = RoundRobinGroupChat([agent])

            # 发送消息并获取响应
            result = await team.run(task=user_prompt)

            # 提取生成的内容
            if result and result.messages:
                # 获取最后一条消息的内容
                last_message = result.messages[-1]
                if hasattr(last_message, 'content'):
                    content = last_message.content
                else:
                    content = str(last_message)
                
                logger.info(f"智能体执行成功，生成内容长度: {len(content)}")
                
                return {
                    "success": True,
                    "content": content,
                    "agent_name": agent_config.name,
                    "field_name": field_config.field_name
                }
            else:
                return {
                    "success": False,
                    "error": "智能体未返回有效内容"
                }

        except Exception as e:
            logger.error(f"智能体执行失败: {e}")
            return {
                "success": False,
                "error": f"执行失败: {str(e)}"
            }

    async def execute_agent_by_id(
        self,
        db: Session,
        agent_id: int,
        user_prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """直接通过智能体ID执行"""
        try:
            # 获取智能体配置
            agent_config = agent_service.get_agent_config(db, agent_id)
            if not agent_config:
                return {
                    "success": False,
                    "error": "智能体配置不存在"
                }

            # 创建智能体
            agent = self._create_agent_from_config(agent_config)

            # 准备执行上下文
            execution_context = context or {}
            execution_context["user_input"] = user_prompt

            # 格式化提示词
            formatted_prompt = self._format_user_prompt(agent_config, execution_context)

            # 执行智能体
            logger.info(f"直接执行智能体 {agent_config.name}")
            
            team = RoundRobinGroupChat([agent])
            result = await agent.run(task=formatted_prompt)

            # 处理结果
            if result and result.messages:
                last_message = result.messages[-1]
                content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                
                return {
                    "success": True,
                    "content": content,
                    "agent_name": agent_config.name
                }
            else:
                return {
                    "success": False,
                    "error": "智能体未返回有效内容"
                }

        except Exception as e:
            logger.error(f"智能体直接执行失败: {e}")
            return {
                "success": False,
                "error": f"执行失败: {str(e)}"
            }

    def get_available_tools(self, db: Session) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        try:
            tools = agent_service.get_agent_tools(db)
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "function_name": tool.function_name,
                    "parameters_schema": tool.parameters_schema
                }
                for tool in tools
            ]
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            return []


# 创建服务实例
agent_execution_service = AgentExecutionService()
