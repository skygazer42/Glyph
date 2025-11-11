"""
Agent模型基础类定义
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class UserQuery(BaseModel):
    """用户查询模型"""
    query: str = Field(..., description="用户查询内容")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="查询时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class FinalAnswer(BaseModel):
    """最终答案模型"""
    answer: str = Field(..., description="最终答案内容")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="答案置信度")
    sources: List[str] = Field(default_factory=list, description="信息来源")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="答案生成时间")


class AgentResponse(BaseModel):
    """Agent响应模型"""
    content: str = Field(..., description="响应内容")
    agent_name: str = Field(..., description="Agent名称")
    agent_type: str = Field(..., description="Agent类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="响应元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PolicyDocument(BaseModel):
    """政策文档模型"""
    doc_id: str = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    source: str = Field(..., description="文档来源")
    doc_type: str = Field("policy", description="文档类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class RetrievalResult(BaseModel):
    """检索结果模型"""
    doc_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="内容片段")
    score: float = Field(..., description="相似度分数")
    source: str = Field(..., description="来源")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="结果元数据")