"""
API 请求/响应模型
使用 Pydantic 进行数据验证
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.policy import Attachment as AttachmentModel


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
    filename: Optional[str] = Field(default=None, description="文件名（可选）")


class SaveDSLResponse(BaseModel):
    """保存DSL响应"""
    success: bool
    file_path: str
    rule_id: str


class TestDSLRequest(BaseModel):
    """测试DSL请求"""
    rule_id: str = Field(..., description="规则ID")
    inputs: Dict[str, Any] = Field(..., description="测试输入数据")


class PreviewDSLRequest(BaseModel):
    """在内存中试算未保存的规则。"""
    yaml_content: str = Field(..., min_length=1, max_length=64000, strict=True, description="待试算的 YAML 内容")
    inputs: Dict[str, Any] = Field(..., description="试算输入数据")


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


class AttachmentUploadResponse(BaseModel):
    """聊天附件上传响应"""
    success: bool
    filename: str
    stored_filename: str
    path: str
    url: str
    mime_type: Optional[str] = None
    size: Optional[int] = None


# ==================== Agent 问答相关模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(default=None, description="会话ID（用于多轮对话）")
    user_id: Optional[str] = Field(default=None, description="调用方传入的用户ID，用于画像/上下文关联")
    stream: bool = Field(default=False, description="是否使用流式响应")
    connection_id: Optional[int] = Field(
        default=None,
        description="Text2SQL 场景使用的数据库连接ID"
    )
    text2sql_mode: bool = Field(
        default=False,
        description="显式开启 Text2SQL 模式（需要 connection_id 或默认连接）"
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
    session_id: Optional[str] = Field(default=None, description="会话ID（用于多轮对话）")
    user_id: Optional[str] = Field(default=None, description="调用方传入的用户ID，用于画像/上下文关联")
    connection_id: Optional[int] = Field(
        default=None,
        description="Text2SQL 场景使用的数据库连接ID"
    )
    text2sql_mode: bool = Field(
        default=False,
        description="显式开启 Text2SQL 模式（需要 connection_id 或默认连接）"
    )
    attachments: Optional[List[AttachmentModel]] = Field(
        default=None,
        description="可选附件列表，例如图片路径/URL，用于多模态任务",
    )


class ChatStreamChunk(BaseModel):
    """流式响应数据块"""
    content: str = Field(default="", description="内容片段")
    done: bool = Field(default=False, description="是否完成")
    error: Optional[str] = Field(default=None, description="错误信息")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


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


class DeleteSessionResponse(BaseModel):
    """返回会话删除操作的结果与提示信息。"""

    success: bool
    message: str


class SessionMessagesQuery(BaseModel):
    """限制读取会话消息的数量；None 表示不在该参数层指定上限。"""

    limit: int | None = Field(default=None, ge=0)


class SessionMessagesResponse(BaseModel):
    """返回会话消息列表及总量，用于历史记录读取。"""

    success: bool
    session_id: str
    messages: List[Dict[str, Any]]
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
