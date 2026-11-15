"""
智能体基础类和通用功能
"""
import logging
import time
from typing import Dict, List, Optional, Any, Awaitable, Callable
from abc import ABC

from autogen_core import RoutedAgent, TopicId, MessageContext, ClosureContext
from autogen_core.memory import ListMemory, MemoryContent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage

from app.core.llms import model_client
from app.schemas.text2sql import ResponseMessage
from .types import DEFAULT_DB_TYPE, TopicTypes

logger = logging.getLogger(__name__)


class BaseAgent(RoutedAgent, ABC):
    """所有智能体的基类，提供共享功能"""

    def __init__(self, agent_id: str, agent_name: str, model_client_instance=None, db_type=None):
        """初始化基础智能体

        Args:
            agent_id: 智能体ID
            agent_name: 智能体名称（用于显示）
            model_client_instance: 模型客户端实例，如果为None则使用全局model_client
            db_type: 数据库类型，如果为None则使用默认DB_TYPE
        """
        super().__init__(agent_id)
        self.agent_name = agent_name
        self.model_client = model_client if model_client_instance is None else model_client_instance
        self.db_type = DEFAULT_DB_TYPE if db_type is None else db_type
        self.db_schema = ""

    @staticmethod
    def final_text(result: TaskResult) -> str:
        """SQL/prompts require a final text message, not a tool or runtime event."""
        if not result.messages or not isinstance(result.messages[-1], TextMessage):
            raise TypeError("Expected a final text model message")
        content = result.messages[-1].content
        if not content.strip():
            raise ValueError("Final model text must not be empty")
        return content

    async def send_response(self, content: str, is_final: bool = False, result: Optional[Dict[str, Any]] = None) -> None:
        """发送响应消息到流输出主题

        Args:
            content: 消息内容
            is_final: 是否是最终消息
            result: 可选的结果数据
        """
        await self.publish_message(
            ResponseMessage(
                source=self.agent_name,
                content=content,
                is_final=is_final,
                result=result
            ),
            topic_id=TopicId(type=TopicTypes.STREAM_OUTPUT.value, source=self.id.key)
        )

    async def send_error(self, error_message: str) -> None:
        """发送错误消息

        Args:
            error_message: 错误消息内容
        """
        logger.error("[%s] %s", self.agent_name, error_message)
        await self.send_response(f"错误: {error_message}", is_final=True)

    async def handle_exception(self, func_name: str, exception: Exception) -> None:
        """处理异常并发送错误消息

        Args:
            func_name: 发生异常的函数名
            exception: 异常对象
        """
        error_msg = f"在{func_name}中发生错误: {str(exception)}"
        logger.error("[%s] %s failed", self.agent_name, func_name,
                     exc_info=(type(exception), exception, exception.__traceback__))
        await self.send_error(error_msg)

    @staticmethod
    def format_schema_context(schema_context: Dict[str, Any]) -> str:
        """将表结构信息格式化为SQL DDL字符串

        Args:
            schema_context: 表结构信息字典

        Returns:
            str: 格式化后的SQL DDL字符串
        """
        if not schema_context or not schema_context['tables']:
            return ""

        db_schema_str = ""
        for table in schema_context['tables']:
            table_name = table['name']
            db_schema_str += f"CREATE TABLE [{table_name}]\n(\n"

            # 添加列信息
            columns = [col for col in schema_context['columns'] if col['table_name'] == table_name]
            for column in columns:
                pk_flag = "PRIMARY KEY" if column['is_primary_key'] else ""
                fk_flag = "FOREIGN KEY" if column['is_foreign_key'] else ""
                db_schema_str += f"    [{column['name']}] {column['type']} {pk_flag} {fk_flag},\n"

            db_schema_str += ");\n\n"

        # 添加关系信息
        if schema_context['relationships']:
            db_schema_str += "/* 表关系 */\n"
            for rel in schema_context['relationships']:
                db_schema_str += f"-- {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']} ({rel['relationship_type'] or 'unknown'})\n"

        return db_schema_str

    @staticmethod
    def format_schema_as_markdown(schema_context: Dict[str, Any]) -> str:
        """将表结构信息格式化为Markdown，适用于LLM提示中

        Args:
            schema_context: 表结构信息字典

        Returns:
            str: 格式化后的Markdown字符串
        """
        if not schema_context or not schema_context['tables']:
            return ""

        schema_info = "\n## 相关表结构\n"

        # 添加表信息
        for table in schema_context['tables']:
            table_name = table['name']
            table_desc = f" - {table['description']}" if table['description'] else ""
            schema_info += f"### 表: {table_name}{table_desc}\n"

            # 添加列信息
            columns = [col for col in schema_context['columns'] if col['table_name'] == table_name]
            if columns:
                schema_info += "| 列名 | 类型 | 主键 | 外键 | 描述 |\n"
                schema_info += "| --- | --- | --- | --- | --- |\n"
                for column in columns:
                    pk = "是" if column['is_primary_key'] else "否"
                    fk = "是" if column['is_foreign_key'] else "否"
                    desc = column['description']
                    schema_info += f"| {column['name']} | {column['type']} | {pk} | {fk} | {desc} |\n"
            schema_info += "\n"

        # 添加关系信息
        if schema_context['relationships']:
            schema_info += "### 表关系\n"
            for rel in schema_context['relationships']:
                rel_type = f" ({rel['relationship_type']})" if rel['relationship_type'] else ""
                schema_info += f"- {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}{rel_type}\n"

        return schema_info

    @staticmethod
    def rebuild_memory_from_content(memory_content: List[Dict[str, Any]]) -> ListMemory:
        """从序列化的内容重建ListMemory对象

        Args:
            memory_content: 序列化的内存内容

        Returns:
            ListMemory: 重建的内存对象
        """
        memory = ListMemory()
        memory_contents = []
        for item in memory_content:
            memory_contents.append(MemoryContent(
                content=item["content"],
                mime_type=item["mime_type"],
                metadata=item.get("metadata", None)
            ))
        memory.content = memory_contents
        return memory

    @staticmethod
    def serialize_memory_content(memory: ListMemory) -> List[Dict[str, Any]]:
        """将ListMemory序列化为可传输的格式

        Args:
            memory: 内存对象

        Returns:
            List[Dict[str, Any]]: 序列化的内存内容
        """
        memory_content = []
        for content in memory.content:
            memory_content.append({
                "content": content.content,
                "mime_type": content.mime_type,
                "metadata": content.metadata
            })
        return memory_content


class StreamResponseCollector:
    """流式响应收集器，用于收集智能体产生的流式输出"""

    def __init__(self):
        """初始化流式响应收集器"""
        self.callback: Optional[Callable[[Optional[ClosureContext], ResponseMessage, Optional[MessageContext]], Awaitable[None]]] = None
        self.user_input: Optional[Callable[[str, Any], Awaitable[str]]] = None
        self.message_buffers: Dict[str, str] = {}  # 用于缓存各智能体的消息
        self.last_flush_time: Dict[str, float] = {}  # 记录最后一次刷新缓冲区的时间
        self.buffer_flush_interval: float = 0.3  # 缓冲区刷新间隔（秒）

    def set_callback(self, callback: Callable[[Optional[ClosureContext], ResponseMessage, Optional[MessageContext]], Awaitable[None]]) -> None:
        """设置回调函数

        Args:
            callback: 用于处理响应消息的异步回调函数
        """
        self.callback = callback

    def set_user_input(self, user_input: Callable[[str, Any], Awaitable[str]]) -> None:
        """设置用户输入函数

        Args:
            user_input: 用于获取用户输入的异步函数
        """
        self.user_input = user_input

    async def buffer_message(self, ctx: Optional[ClosureContext], source: str, content: str,
                          is_final: bool = False, result: Optional[Dict[str, Any]] = None) -> None:
        """缓冲消息并在达到一定条件时发送

        Args:
            ctx: 闭包上下文
            source: 消息来源
            content: 消息内容
            is_final: 是否最终消息
            result: 可选的结果数据
        """
        if not self.callback:
            return

        current_time = time.time()

        # 如果是最终消息或结果不为空，直接发送，不经过缓冲
        if is_final or result is not None:
            # 先发送缓冲区中的消息
            buffered = self.message_buffers.pop(source, "")
            self.last_flush_time.pop(source, None)
            if buffered:
                await self.callback(ctx, ResponseMessage(source=source, content=buffered), None)

            # 再发送当前消息
            await self.callback(ctx, ResponseMessage(
                source=source,
                content=content,
                is_final=is_final,
                result=result
            ), None)
            return

        # 累积消息到缓冲区
        if source not in self.message_buffers:
            self.message_buffers[source] = ""
            self.last_flush_time[source] = current_time

        self.message_buffers[source] += content

        # 检查是否需要刷新缓冲区
        if current_time - self.last_flush_time.get(source, 0) >= self.buffer_flush_interval:
            buffered = self.message_buffers.pop(source)
            self.last_flush_time.pop(source, None)
            await self.callback(ctx, ResponseMessage(source=source, content=buffered), None)

    async def flush_all_buffers(self, ctx: Optional[ClosureContext] = None) -> None:
        """刷新所有消息缓冲区

        Args:
            ctx: 可选的闭包上下文
        """
        if not self.callback:
            return

        buffers = self.message_buffers
        self.message_buffers = {}
        self.last_flush_time = {}
        for source, content in buffers.items():
            if content:
                await self.callback(ctx, ResponseMessage(source=source, content=content), None)
