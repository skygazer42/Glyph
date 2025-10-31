"""
ChatDB基础智能体类 - 适配到Gove系统
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Union, Awaitable, Callable
from abc import ABC, abstractmethod

from autogen_core import RoutedAgent, TopicId, MessageContext, ClosureContext
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

from autogen_agentchat.messages import TextMessage

# 导入Gove的类型定义
from ..base.types import DEFAULT_DB_TYPE, TopicTypes


class StreamResponseCollector:
    """流式响应收集器 - 从ChatDB复用"""

    def __init__(self):
        self.responses = []
        self.is_complete = False
        self.start_time = time.time()
        self.user_input = None

    def add_response(self, content: str, is_final: bool = False, source: str = None):
        """添加响应内容"""
        self.responses.append({
            "content": content,
            "timestamp": time.time(),
            "source": source,
            "is_final": is_final
        })

        if is_final:
            self.is_complete = True

    def get_full_response(self) -> str:
        """获取完整响应"""
        return "\n".join(r["content"] for r in self.responses)

    def get_duration(self) -> float:
        """获取响应时长"""
        return time.time() - self.start_time


class BaseAgent(RoutedAgent, ABC):
    """基础智能体类 - 基于ChatDB的BaseAgent适配到Gove"""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        model_client_instance=None,
        db_type=None
    ):
        """初始化基础智能体"""
        super().__init__(agent_id)
        self.agent_name = agent_name
        self.model_client = model_client_instance
        self.db_type = db_type or DEFAULT_DB_TYPE
        self.db_schema = ""

    async def send_response(
        self,
        content: str,
        is_final: bool = False,
        result: Dict[str, Any] = None
    ) -> None:
        """发送响应消息到流输出主题"""
        await self.publish_message(
            TextMessage(
                content=content,
                source=self.agent_name
            ),
            topic_id=TopicId(
                type=TopicTypes.STREAM_OUTPUT.value,
                source=self.id.key
            )
        )

    async def send_error(self, error_message: str) -> None:
        """发送错误消息"""
        print(f"[{self.agent_name}] 错误: {error_message}")
        await self.send_response(f"错误: {error_message}", is_final=True)

    async def handle_exception(self, func_name: str, exception: Exception) -> None:
        """处理异常并发送错误消息"""
        error_msg = f"在{func_name}中发生错误: {str(exception)}"
        print(f"[{self.agent_name}] {error_msg}")
        await self.send_error(error_msg)

    def format_schema_as_markdown(self, schema_context: Dict[str, Any]) -> str:
        """将表结构信息格式化为Markdown字符串"""
        if not schema_context or not schema_context.get('tables'):
            return ""

        md_output = "## 知识库结构\n\n"

        # 格式化表结构
        for table in schema_context['tables']:
            table_name = table['name']
            md_output += f"### {table_name}\n\n"

            # 添加列信息
            columns = [col for col in schema_context['columns']
                      if col['table_name'] == table_name]

            if columns:
                md_output += "| 列名 | 类型 | 主键 | 说明 |\n"
                md_output += "|------|------|------|------|\n"

                for column in columns:
                    pk_flag = "✓" if column['is_primary_key'] else ""
                    fk_flag = "FK" if column['is_foreign_key'] else ""
                    md_output += f"| {column['name']} | {column['type']} | {pk_flag} | {column.get('description', '')} |\n"

            md_output += "\n"

        return md_output

    def format_policy_as_markdown(self, policy_data: Dict[str, Any]) -> str:
        """将政策数据格式化为Markdown字符串"""
        if not policy_data:
            return ""

        md_output = "## 政策信息\n\n"

        # 政策标题
        if policy_data.get('title'):
            md_output += f"### {policy_data['title']}\n\n"

        # 发布机构
        if policy_data.get('source'):
            md_output += f"**发布机构**: {policy_data['source']}\n\n"

        # 申请条件
        if policy_data.get('eligibility_criteria'):
            md_output += "#### 申请条件\n"
            for i, condition in enumerate(policy_data['eligibility_criteria'], 1):
                md_output += f"{i}. {condition}\n"
            md_output += "\n"

        # 补贴标准
        if policy_data.get('benefit_details'):
            md_output += f"#### 补贴标准\n{policy_data['benefit_details']}\n\n"

        # 申请流程
        if policy_data.get('application_steps'):
            md_output += "#### 申请流程\n"
            for i, step in enumerate(policy_data['application_steps'], 1):
                md_output += f"{i}. {step}\n"
            md_output += "\n"

        # 所需材料
        if policy_data.get('required_documents'):
            md_output += "#### 所需材料\n"
            for doc in policy_data['required_documents']:
                md_output += f"- {doc}\n"
            md_output += "\n"

        # 时间节点
        if policy_data.get('deadlines'):
            md_output += "#### 重要时间\n"
            for deadline in policy_data['deadlines']:
                md_output += f"- {deadline}\n"
            md_output += "\n"

        # 联系方式
        if policy_data.get('contact_info'):
            md_output += "#### 联系方式\n"
            for contact in policy_data['contact_info']:
                md_output += f"- {contact}\n"
            md_output += "\n"

        return md_output

    async def serialize_memory_content(
        self,
        content: Any,
        mime_type: str = "text/plain"
    ) -> MemoryContent:
        """序列化内存内容"""
        return MemoryContent(
            content=str(content),
            mime_type=mime_type
        )

    def _build_system_message(self, system_prompt: str) -> str:
        """构建系统消息"""
        return f"""你是一个专业的政策智能助手。

{system_prompt}

请用清晰、准确的语言回答用户的问题。"""

    def _build_prompt_template(
        self,
        task_description: str,
        context: Dict[str, Any],
        examples: Optional[str] = None
    ) -> str:
        """构建提示模板"""
        prompt_parts = [
            f"## 任务描述\n{task_description}\n",
            "## 上下文信息\n"
        ]

        # 添加上下文
        if context:
            for key, value in context.items():
                if value:
                    prompt_parts.append(f"**{key}**:\n{value}\n")

        # 添加示例
        if examples:
            prompt_parts.append(f"\n## 示例\n{examples}\n")

        # 添加指令
        prompt_parts.append("\n## 请基于以上信息完成你的任务。")

        return "\n".join(prompt_parts)

    async def _prepare_task(
        self,
        user_query: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """准备任务请求"""
        return {
            "query": user_query,
            "context": context or {},
            "timestamp": time.time(),
            "agent": self.agent_name
        }