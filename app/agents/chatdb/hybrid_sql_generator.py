"""
混合SQL生成智能体
保留混合模式入口，在检索引擎尚未接入时使用标准提示生成SQL。
"""
from autogen_core import message_handler, MessageContext, TopicId, type_subscription
from autogen_agentchat.agents import AssistantAgent

from app.config.app_config import settings
from app.schemas.text2sql import AnalysisMessage, SqlMessage
from .base import BaseAgent
from .sql_generator import SqlGeneratorAgent
from .types import AgentTypes, AGENT_NAMES, TopicTypes


@type_subscription(topic_type=TopicTypes.SQL_GENERATOR.value)
class HybridSqlGeneratorAgent(BaseAgent):
    """混合模式的SQL生成入口，当前尚未装配检索引擎。"""

    def __init__(self, model_client_instance=None, db_type=None):
        """初始化混合SQL生成智能体

        Args:
            model_client_instance: 模型客户端实例
            db_type: 数据库类型
        """
        super().__init__(
            description="hybrid_sql_generator_agent",
            agent_name=AGENT_NAMES[AgentTypes.SQL_GENERATOR.value],
            model_client_instance=model_client_instance,
            db_type=db_type
        )

        # 构建基础提示模板
        self._prompt_template = SqlGeneratorAgent.PROMPT_TEMPLATE

    @message_handler
    async def handle_analysis_message(self, message: AnalysisMessage, ctx: MessageContext) -> None:
        """处理AnalysisMessage类型的消息，使用混合检索生成SQL"""
        try:
            if settings.system.hybrid_retrieval_enabled:
                await self.send_response("混合检索引擎尚未配置，暂使用标准模式。\n\n")

            # 从memory_content重建ListMemory对象
            memory = self.rebuild_memory_from_content(message.memory_content)

            system_message = self._prompt_template.format(db_type=self.db_type)

            # 生成SQL
            agent = AssistantAgent(
                name="hybrid_sql_generator",
                description="Generates SQL from the existing analysis context.",
                model_client=self.model_client,
                system_message=system_message,
                memory=[memory],
                model_client_stream=True,
            )

            result = await agent.run(task="严格根据上下文信息生成SQL语句")
            sql_content = self.final_text(result)

            # 首先将SQL内容发送为流式消息，供前端实时更新
            await self.send_response(sql_content)

            # 发送SQL内容为final_sql类型，触发前端SQL语句区域显示
            await self.send_response(
                "SQL语句已生成",
                is_final=True,
                result={"sql": sql_content, "examples_used": 0}
            )

            # 构造SqlMessage并传递给下一个智能体
            sql_message = SqlMessage(
                query=message.query,
                sql=sql_content,
                connection_id=message.connection_id
            )

            await self.publish_message(
                sql_message,
                topic_id=TopicId(type=TopicTypes.SQL_EXPLAINER.value, source=self.id.key)
            )

        except Exception as e:
            await self.handle_exception("handle_analysis_message", e)
