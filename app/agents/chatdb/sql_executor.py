"""
SQL执行智能体
负责执行SQL并返回结果
"""
import asyncio
import logging
from typing import Optional

from autogen_core import message_handler, MessageContext, TopicId, type_subscription

from app.persistence.db.dbaccess import DBAccess
from app.schemas.text2sql import SqlExplanationMessage, SqlResultMessage
from .base import BaseAgent
from .types import AgentTypes, AGENT_NAMES, TopicTypes

logger = logging.getLogger(__name__)


@type_subscription(topic_type=TopicTypes.SQL_EXECUTOR.value)
class SqlExecutorAgent(BaseAgent):
    """SQL执行智能体，负责执行SQL并返回结果"""

    def __init__(self, *, db_access: DBAccess, model_client_instance=None, db_type=None):
        """初始化SQL执行智能体

        Args:
            model_client_instance: 模型客户端实例
            db_type: 数据库类型
            db_access: 已连接的数据库访问对象，由调用方管理生命周期
        """
        super().__init__(
            agent_id="sql_executor_agent",
            agent_name=AGENT_NAMES[AgentTypes.SQL_EXECUTOR.value],
            model_client_instance=model_client_instance,
            db_type=db_type
        )
        self.db_access = db_access

    async def _execute_sql(self, sql: str) -> tuple[list, Optional[str]]:
        """Execute on the injected connection and report query errors to the pipeline."""
        try:
            cleaned_sql = sql.replace("```sql", "").replace("```", "").strip()
            results = await asyncio.to_thread(self.db_access.run_sql, cleaned_sql)
            return results.to_dict("records"), None
        except Exception as exc:
            logger.exception("SQL execution failed")
            return [], f"SQL执行错误: {exc}"

    @message_handler
    async def handle_message(self, message: SqlExplanationMessage, ctx: MessageContext) -> None:
        """处理接收到的消息，执行SQL查询"""
        try:
            results, error_message = await self._execute_sql(message.sql)
            if error_message:
                await self.send_error(error_message)
            else:
                if not results:
                    await self.send_response("查询执行成功，但没有返回任何结果\n\n")
                else:
                    await self.send_response(f"SQL执行完成，获取到{len(results)}条结果\n\n")
                await self.send_response(
                    f"查询执行完成，返回{len(results)}条数据",
                    is_final=True,
                    result={"results": results}
                )

            await self.publish_message(
                SqlResultMessage(
                    query=message.query,
                    sql=message.sql,
                    explanation=message.explanation,
                    results=results,
                    error=error_message,
                    connection_id=message.connection_id,
                ),
                topic_id=TopicId(type=TopicTypes.VISUALIZATION_RECOMMENDER.value, source=self.id.key),
            )

        except Exception as e:
            await self.handle_exception("handle_message", e)
