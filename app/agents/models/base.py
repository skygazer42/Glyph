"""
Compatibility shims for agent-side models.

Historically `app.agents.models` duplicated a subset of `app.models.base`.
To avoid双重维护，这里直接重用主模型定义，并仅保留 agent 独有的响应结构。
"""

from datetime import datetime
from typing import Dict, Any

from pydantic import Field

from app.models.base import (
    BaseModel,
    UserQuery as CoreUserQuery,
    FinalAnswer as CoreFinalAnswer,
    PolicyDocument as CorePolicyDocument,
    RetrievalResult as CoreRetrievalResult,
)


# 直接复用核心模型，确保所有字段/验证逻辑一致
UserQuery = CoreUserQuery
FinalAnswer = CoreFinalAnswer
PolicyDocument = CorePolicyDocument
RetrievalResult = CoreRetrievalResult


class AgentResponse(BaseModel):
    """Agent 响应模型（仅在多 Agent 协作场景下使用）"""

    content: str = Field(..., description="响应内容")
    agent_name: str = Field(..., description="Agent 名称")
    agent_type: str = Field(..., description="Agent 类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="响应元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


__all__ = [
    "BaseModel",
    "UserQuery",
    "FinalAnswer",
    "AgentResponse",
    "PolicyDocument",
    "RetrievalResult",
]
