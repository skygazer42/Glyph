"""Knowledge workspace, parsing, chunking, indexing, and search contracts."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EmbedRequest(BaseModel):
    """嵌入文档请求"""
    model_config = ConfigDict(extra="forbid")
    doc_id: str = Field(..., description="文档ID")
    source_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    parsed_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class EmbedResponse(BaseModel):
    """嵌入文档响应"""
    success: bool
    doc_id: str
    message: str


class ParseRequest(BaseModel):
    """解析文档请求"""
    model_config = ConfigDict(extra="forbid")
    doc_id: str = Field(..., description="上传后的文档ID（文件名）")
    options: "ProcessingConfig | None" = None
    parser: Literal["auto", "mineru", "llamaindex", "text"] | None = None
    ocr: Literal["auto", "on", "off"] | None = None
    source_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ParseResponse(BaseModel):
    """解析文档响应"""
    success: bool
    doc_id: str
    markdown_path: str
    content_length: int
    message: Optional[str] = None
    source_version: str | None = None
    parsed_version: str | None = None


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
    parsed: bool = False
    source_version: str | None = None


class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    name: str
    size: int
    modified: float
    embedded: bool = Field(default=False, description="是否已成功嵌入知识库")
    parsed: bool = Field(default=False, description="最近目录校验的解析状态；打开工作区和写操作重新检查内容版本")
    source_version: str | None = None
    content_length: int = 0


class ChunkingConfig(BaseModel):
    """预览按 Unicode 字符计数，独立于向量服务的 token 切块。"""

    model_config = ConfigDict(extra="forbid")
    size: int = Field(default=800, ge=16, le=20000, strict=True)
    overlap: int = Field(default=100, ge=0, strict=True)
    boundary: Literal["sentence", "fixed"] = "sentence"

    @model_validator(mode="after")
    def require_overlap_smaller_than_size(self) -> "ChunkingConfig":
        if self.overlap >= self.size:
            raise ValueError("overlap must be smaller than size")
        return self


class ProcessingConfig(ChunkingConfig):
    """文档解析、分块与索引偏好；具体可用性仍由工作区按能力校验。"""

    index: Literal["document", "hierarchical"] = "document"
    parser: Literal["auto", "mineru", "llamaindex", "text"] = "auto"
    ocr: Literal["auto", "on", "off"] = "auto"


class ParserCapability(BaseModel):
    """向工作区描述一个解析器选项及当前配置可用标记。"""

    value: Literal["auto", "mineru", "llamaindex", "text"]
    label: str
    available: bool


class ProcessingCapabilities(BaseModel):
    """声明当前解析器与 OCR、分级索引能力，不代表运行时健康探测。"""

    parsers: list[ParserCapability]
    ocr: bool
    hierarchical_index: bool


class CapabilitiesResponse(BaseModel):
    """封装工作区处理能力的接口响应。"""

    success: bool
    capabilities: ProcessingCapabilities


class WorkspacePage(BaseModel):
    """原文单页文本及其 Unicode 字符区间，图像地址可缺省。"""

    number: int
    text: str
    start: int
    end: int
    image_url: str | None = None
    has_text: bool


class ParsedContent(BaseModel):
    """描述解析缓存是否有效及版本；不可用时正文和版本可以为 None。"""

    available: bool
    text: str | None = None
    version: str | None = None
    source_version: str | None = None
    parser: str | None = None
    content_length: int = 0
    page_mapping: Literal["exact", "unavailable"] = "unavailable"


class DocumentWorkspaceResponse(BaseModel):
    """汇总文档原文版本、页面、解析缓存、配置与嵌入标记的工作区响应。"""

    success: bool
    doc_id: str
    name: str
    format: str
    size: int
    modified: float
    source_version: str
    source_url: str
    page_count: int
    pages: list[WorkspacePage]
    parsed: ParsedContent
    config: ProcessingConfig
    config_revision: str
    saved_at: str | None
    embedded: bool
    capabilities: ProcessingCapabilities


class ChunkPreviewRequest(ChunkingConfig):
    """使用指定原文及解析版本预览分块的请求，不触发嵌入。"""

    source_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    parsed_version: str = Field(pattern=r"^[a-f0-9]{64}$")


class ChunkPreview(BaseModel):
    """描述解析正文中的一个字符区间及可确认的页号映射。"""

    id: str
    number: int
    text: str
    start: int
    end: int
    pages: list[int]
    overlap: int


class ChunkPreviewResponse(BaseModel):
    """返回分块预览、所用配置和版本，不表示索引已写入。"""

    success: bool
    source_version: str
    parsed_version: str
    config: ChunkingConfig
    chunks: list[ChunkPreview]
    total: int


class SaveProcessingConfigRequest(ProcessingConfig):
    """携带原文版本与预期配置修订的保存请求，用于冲突检查。"""

    source_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: str = Field(min_length=1, max_length=64)


class SaveProcessingConfigResponse(BaseModel):
    """返回成功保存的配置、新修订及对应原文版本。"""

    success: bool
    config: ProcessingConfig
    revision: str
    saved_at: str
    source_version: str


class DocumentListQuery(BaseModel):
    """资料目录查询；不传页码时兼容完整目录读取。"""

    model_config = ConfigDict(extra="forbid")
    page: int | None = Field(default=None, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    query: str = Field(default="", max_length=200)
    parsed: Literal["all", "parsed", "unparsed"] = "all"
    indexed: Literal["all", "indexed", "pending"] = "all"
    sort: Literal["newest", "oldest"] = "newest"


class DocumentSummary(BaseModel):
    """全目录统计，不随当前页或筛选变化。"""

    total: int
    parsed: int
    embedded: int


class ListDocumentsResponse(BaseModel):
    """文档列表响应"""
    success: bool
    documents: List[DocumentInfo]
    total: int
    page: int | None = None
    page_size: int | None = None
    summary: DocumentSummary | None = None


class DeleteDocumentResponse(BaseModel):
    """删除文档响应"""
    success: bool
    message: str


class StatsResponse(BaseModel):
    """知识库统计响应"""
    success: bool
    stats: Dict[str, Any]
