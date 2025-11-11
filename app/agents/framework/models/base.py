"""
Framework模型基础类定义
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AgentType(str, Enum):
    """Agent类型枚举"""
    QUESTION_UNDERSTANDER = "question_understander"
    POLICY_RETRIEVER = "policy_retriever"
    ANSWER_GENERATOR = "answer_generator"
    POLICY_ANALYZER = "policy_analyzer"
    COORDINATOR = "coordinator"
    KNOWLEDGE = "knowledge"
    WEB_SEARCH = "web_search"


class MessageType(str, Enum):
    """消息类型枚举"""
    USER_QUERY = "user_query"
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    ERROR_MESSAGE = "error_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DATA = "data"


class QueryIntent(str, Enum):
    """查询意图枚举"""
    POLICY_INQUIRY = "policy_inquiry"
    ELIGIBILITY_CHECK = "eligibility_check"
    APPLICATION_PROCESS = "application_process"
    BENEFIT_CALCULATION = "benefit_calculation"
    GENERAL_QUESTION = "general_question"
    COMPARISON = "comparison"


class AgentMessage(BaseModel):
    """Agent消息模型"""
    type: MessageType = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    sender: str = Field(..., description="发送者")
    receiver: Optional[str] = Field(None, description="接收者")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class TaskResult(BaseModel):
    """任务结果模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    result: Any = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="完成时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class WorkflowState(BaseModel):
    """工作流状态模型"""
    workflow_id: str = Field(..., description="工作流ID")
    current_step: str = Field(..., description="当前步骤")
    completed_steps: List[str] = Field(default_factory=list, description="已完成步骤")
    pending_steps: List[str] = Field(default_factory=list, description="待处理步骤")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文")
    timestamp: datetime = Field(default_factory=datetime.now, description="更新时间")
