"""
Base models and data structures for the policy QA system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4
from pydantic_settings import BaseSettings
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy import Any
class AgentType(str, Enum):
    """Agent type enumeration."""
    QUERY_ANALYZER = "query_analyzer"
    POLICY_RETRIEVER = "policy_retriever"
    POLICY_ANALYZER = "policy_analyzer"
    REQUIREMENT_EXTRACTOR = "requirement_extractor"
    ANSWER_GENERATOR = "answer_generator"
    FACT_CHECKER = "fact_checker"
    CONSISTENCY_CHECKER = "consistency_checker"
    COORDINATOR = "coordinator"


class MessageType(str, Enum):
    """Message type enumeration."""
    USER_QUERY = "user_query"
    QUERY_ANALYSIS = "query_analysis"
    RETRIEVAL_REQUEST = "retrieval_request"
    RETRIEVAL_RESULT = "retrieval_result"
    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_RESULT = "analysis_result"
    REQUIREMENT_EXTRACTION = "requirement_extraction"
    ANSWER_GENERATION = "answer_generation"
    FACT_CHECK = "fact_check"
    CONSISTENCY_CHECK = "consistency_check"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


class RetrievalMethod(str, Enum):
    """Retrieval method enumeration."""
    SEMANTIC_SEARCH = "semantic_search"
    KEYWORD_SEARCH = "keyword_search"
    HYBRID_SEARCH = "hybrid_search"
    GRAPH_TRAVERSAL = "graph_traversal"


class PolicyType(str, Enum):
    """Policy type enumeration."""
    SUBSIDY = "subsidy"  # 补贴
    TAX_EXEMPTION = "tax_exemption"  # 税收减免
    VOUCHER = "voucher"  # 消费券
    REPLACEMENT = "replacement"  # 以旧换新
    ALLOWANCE = "allowance"  # 津贴
    DISCOUNT = "discount"  # 折扣
    REGULATION = "regulation"  # 法规
    GUIDELINE = "guideline"  # 指南


class QueryIntent(str, Enum):
    """Query intent enumeration."""
    ELIGIBILITY_CHECK = "eligibility_check"  # 资格查询
    BENEFIT_CALCULATION = "benefit_calculation"  # 补贴计算
    APPLICATION_PROCESS = "application_process"  # 申请流程
    DEADLINE_QUERY = "deadline_query"  # 截止日期查询
    POLICY_COMPARISON = "policy_comparison"  # 政策比较
    GENERAL_INQUIRY = "general_inquiry"  # 一般咨询


class Attachment(BaseModel):
    """User attachment metadata (image, file, url)."""

    type: str = Field(default="file", description="Attachment type, e.g., image/file/audio")
    path: Optional[str] = Field(
        default=None, description="Server-accessible local path for the attachment (if uploaded)."
    )
    url: Optional[str] = Field(default=None, description="Remote URL pointing to the attachment resource.")
    mime_type: Optional[str] = Field(default=None, description="Optional MIME type hint.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata supplied by the client.")

    def is_image(self) -> bool:
        """Return True if the attachment looks like an image."""
        mime = (self.mime_type or "").lower()
        if mime.startswith("image/"):
            return True
        if self.path:
            return any(self.path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
        if self.url:
            return any(self.url.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
        return False


class PolicyDocument(BaseModel):
    """Policy document model."""
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., description="政策标题")
    content: str = Field(..., description="政策内容")
    summary: Optional[str] = Field(None, description="政策摘要")
    source: str = Field(..., description="发布机构")
    doc_type: PolicyType = Field(..., description="政策类型")
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    effective_date: Optional[datetime] = Field(None, description="生效日期")
    expiry_date: Optional[datetime] = Field(None, description="失效日期")
    relevant_departments: List[str] = Field(..., description="相关部门")
    target_groups: List[str] = Field(..., description="目标群体")
    regions: List[str] = Field(..., description="适用地区")
    keywords: List[str] = Field(..., description="关键词")
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")
    metadata: Dict[str, Any] = Field(..., description="元数据")

    @validator('expiry_date')
    def validate_dates(cls, v, values):
        if v and 'effective_date' in values and v <= values['effective_date']:
            raise ValueError("失效日期必须晚于生效日期")
        return v


class UserQuery(BaseModel):
    """User query model."""
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(..., description="查询文本")
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = Field(..., description="会话ID")
    user_id: Optional[str] = Field(..., description="用户ID")
    context: Dict[str, Any] = Field(..., description="上下文信息")


class QueryAnalysis(BaseModel):
    """Query analysis result."""
    query_id: UUID
    intent: QueryIntent = Field(..., description="查询意图")
    entities: List[str] = Field(..., description="提取的实体")
    keywords: List[str] = Field(..., description="关键词")
    policy_types: List[PolicyType] = Field(..., description="相关政策类型")
    time_constraints: Optional[str] = Field(..., description="时间约束")
    location_constraints: Optional[str] = Field(..., description="地点约束")
    target_groups: List[str] = Field(..., description="目标群体")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    reasoning: Optional[str] = Field(None, description="推理过程")


class RetrievalRequest(BaseModel):
    """Retrieval request model."""
    query_id: UUID
    query_embedding: Optional[List[float]] = Field(None, description="查询向量")
    filters: Dict[str, Any] = Field(..., description="过滤条件")
    method: RetrievalMethod = Field(RetrievalMethod.HYBRID_SEARCH)
    top_k: int = Field(10, ge=1, le=100, description="返回数量")
    threshold: float = Field(0.7, ge=0, le=1, description="相似度阈值")


class RetrievalResult(BaseModel):
    """Retrieval result model."""
    query_id: UUID
    documents: List[PolicyDocument] = Field(...)
    scores: List[float] = Field(...)
    method: RetrievalMethod
    total_searched: int = Field(0, description="搜索总数")
    search_time: float = Field(0, description="搜索耗时(秒)")


class PolicyAnalysis(BaseModel):
    """Policy analysis result."""
    document_id: UUID
    query_id: UUID
    relevance_score: float = Field(..., ge=0, le=1)
    eligibility_criteria: List[str] = Field(...,)
    benefit_details: Optional[str] = Field(None, description="福利详情")
    application_steps: List[str] = Field(..., description="申请步骤")
    required_documents: List[str] = Field(..., description="所需文件")
    deadlines: List[str] = Field(..., description="截止日期")
    contact_info: List[str] = Field(..., description="联系信息")
    limitations: List[str] = Field(..., description="限制条件")
    related_policies: List[UUID] = Field(..., description="相关政策")
    analysis_confidence: float = Field(..., ge=0, le=1)


class GeneratedAnswer(BaseModel):
    """Generated answer model."""
    query_id: UUID
    answer: str = Field(..., description="答案内容")
    sources: List[UUID] = Field(..., description="来源文档ID")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    evidence: List[str] = Field(..., description="证据列表")
    assumptions: List[str] = Field(..., description="假设列表")
    limitations: List[str] = Field(..., description="局限性")
    followup_questions: List[str] = Field(..., description="后续问题")
    generation_time: float = Field(0, description="生成耗时(秒)")


class FactCheck(BaseModel):
    """Fact check result."""
    answer_id: UUID
    claims: List[str] = Field(..., description="声明列表")
    verified_claims: List[str] = Field(..., description="已验证声明")
    unverified_claims: List[str] = Field(..., description="未验证声明")
    confidence_score: float = Field(..., ge=0, le=1, description="置信度")
    issues: List[str] = Field(..., description="问题列表")
    suggestions: List[str] = Field(..., description="建议列表")


class ConsistencyCheck(BaseModel):
    """Consistency check result."""
    answer_id: UUID
    sources_analyzed: int = Field(0)
    consistency_score: float = Field(..., ge=0, le=1)
    contradictions: List[str] = Field(..., description="矛盾点")
    missing_information: List[str] = Field(..., description="缺失信息")
    recommendations: List[str] = Field(..., description="建议")


class FinalAnswer(BaseModel):
    """Final answer model."""
    query_id: UUID
    answer: str = Field(..., description="最终答案")
    sources: List[PolicyDocument] = Field(..., description="来源文档")
    confidence: float = Field(..., ge=0, le=1)
    verification_passed: bool = Field(False, description="是否通过验证")
    fact_check: Optional[FactCheck] = Field(None)
    consistency_check: Optional[ConsistencyCheck] = Field(None)
    metadata: Dict[str, Any] = Field(..., description="元数据")
    total_processing_time: float = Field(0, description="总处理时间")


class AgentMessage(BaseModel):
    """Agent communication message."""
    id: UUID = Field(default_factory=uuid4)
    type: MessageType = Field(..., description="消息类型")
    sender: AgentType = Field(..., description="发送者")
    recipient: Optional[AgentType] = Field(None, description="接收者")
    content: Dict[str, Any] = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[UUID] = Field(None, description="关联ID")
    requires_response: bool = Field(False, description="是否需要响应")
    response_topic: Optional[str] = Field(None, description="响应主题")


@as_declarative()
class Base:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
