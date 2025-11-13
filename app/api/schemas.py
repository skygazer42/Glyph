"""
API 请求/响应模型
使用 Pydantic 进行数据验证
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.base import Attachment as AttachmentModel


# ==================== DSL 相关模型 ====================

class GenerateDSLRequest(BaseModel):
    """生成DSL请求"""
    text: str = Field(..., description="政策文本内容", max_length=20000)


class GenerateDSLResponse(BaseModel):
    """生成DSL响应"""
    success: bool
    dsl_data: Dict[str, Any]
    yaml_content: str


class SaveDSLRequest(BaseModel):
    """保存DSL请求"""
    rule_id: str = Field(..., description="规则ID")
    yaml_content: str = Field(..., description="YAML内容")
    filename: Optional[str] = Field(None, description="文件名（可选）")


class SaveDSLResponse(BaseModel):
    """保存DSL响应"""
    success: bool
    file_path: str
    rule_id: str


class TestDSLRequest(BaseModel):
    """测试DSL请求"""
    rule_id: str = Field(..., description="规则ID")
    inputs: Dict[str, Any] = Field(..., description="测试输入数据")


class TestDSLResponse(BaseModel):
    """测试DSL响应"""
    success: bool
    result: Dict[str, Any]


class DSLRuleInfo(BaseModel):
    """DSL规则信息"""
    rule_id: str
    name: str
    description: Optional[str] = None
    file_path: str
    created_at: Optional[str] = None
    modified_at: Optional[str] = None


class ListDSLResponse(BaseModel):
    """DSL规则列表响应"""
    success: bool
    rules: List[Dict[str, Any]]
    total: int


class GetDSLResponse(BaseModel):
    """获取DSL规则响应"""
    success: bool
    rule: Dict[str, Any]


# ==================== 知识库相关模型 ====================

class EmbedRequest(BaseModel):
    """嵌入文档请求"""
    doc_id: str = Field(..., description="文档ID")


class EmbedResponse(BaseModel):
    """嵌入文档响应"""
    success: bool
    doc_id: str
    message: str


class SearchRequest(BaseModel):
    """搜索知识库请求"""
    query: str = Field(..., description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值")


class SearchResult(BaseModel):
    """搜索结果项"""
    id: str
    title: str
    content: str
    source: str
    score: float


class SearchResponse(BaseModel):
    """搜索知识库响应"""
    success: bool
    results: List[SearchResult]
    total: int


class UploadResponse(BaseModel):
    """上传文档响应"""
    success: bool
    doc_id: str
    file_path: str
    content_length: int


class AttachmentUploadResponse(BaseModel):
    """聊天附件上传响应"""
    success: bool
    filename: str
    stored_filename: str
    path: str
    url: str
    mime_type: Optional[str] = None
    size: Optional[int] = None


class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    name: str
    size: int
    modified: float


class ListDocumentsResponse(BaseModel):
    """文档列表响应"""
    success: bool
    documents: List[DocumentInfo]
    total: int


class DeleteDocumentResponse(BaseModel):
    """删除文档响应"""
    success: bool
    message: str


class StatsResponse(BaseModel):
    """知识库统计响应"""
    success: bool
    stats: Dict[str, Any]


# ==================== Agent 问答相关模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")
    user_id: Optional[str] = Field(None, description="调用方传入的用户ID，用于画像/上下文关联")
    stream: bool = Field(default=False, description="是否使用流式响应")
    connection_id: Optional[int] = Field(
        default=None,
        description="Text2SQL 场景使用的数据库连接ID"
    )
    attachments: Optional[List[AttachmentModel]] = Field(
        default=None,
        description="可选附件列表，例如图片路径/URL，用于多模态任务",
    )


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str
    session_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatStreamRequest(BaseModel):
    """流式聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")
    user_id: Optional[str] = Field(None, description="调用方传入的用户ID，用于画像/上下文关联")
    connection_id: Optional[int] = Field(
        default=None,
        description="Text2SQL 场景使用的数据库连接ID"
    )
    attachments: Optional[List[AttachmentModel]] = Field(
        default=None,
        description="可选附件列表，例如图片路径/URL，用于多模态任务",
    )


class ChatStreamChunk(BaseModel):
    """流式响应数据块"""
    content: str = Field(default="", description="内容片段")
    done: bool = Field(default=False, description="是否完成")
    error: Optional[str] = Field(None, description="错误信息")
    session_id: Optional[str] = Field(None, description="会话ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ==================== 会话管理相关模型 ====================

class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: float
    last_active: float
    message_count: int
    status: str = Field(default="active")


class SessionResponse(BaseModel):
    """会话响应"""
    success: bool
    session: SessionInfo


class ListSessionsResponse(BaseModel):
    """会话列表响应"""
    success: bool
    sessions: List[SessionInfo]
    total: int


# ==================== 通用响应模型 ====================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    version: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None
