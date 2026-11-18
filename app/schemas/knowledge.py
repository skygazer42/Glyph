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
    parsed: bool = Field(default=False, description="是否存在与原文版本匹配的真实解析正文")
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
    index: Literal["document", "hierarchical"] = "document"
    parser: Literal["auto", "mineru", "llamaindex", "text"] = "auto"
    ocr: Literal["auto", "on", "off"] = "auto"


class ParserCapability(BaseModel):
    value: Literal["auto", "mineru", "llamaindex", "text"]
    label: str
    available: bool


class ProcessingCapabilities(BaseModel):
    parsers: list[ParserCapability]
    ocr: bool
    hierarchical_index: bool


class CapabilitiesResponse(BaseModel):
    success: bool
    capabilities: ProcessingCapabilities


class WorkspacePage(BaseModel):
    number: int
    text: str
    start: int
    end: int
    image_url: str | None = None
    has_text: bool


class ParsedContent(BaseModel):
    available: bool
    text: str | None = None
    version: str | None = None
    source_version: str | None = None
    parser: str | None = None
    content_length: int = 0
    page_mapping: Literal["exact", "unavailable"] = "unavailable"


class DocumentWorkspaceResponse(BaseModel):
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
    source_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    parsed_version: str = Field(pattern=r"^[a-f0-9]{64}$")


class ChunkPreview(BaseModel):
    id: str
    number: int
    text: str
    start: int
    end: int
    pages: list[int]
    overlap: int


class ChunkPreviewResponse(BaseModel):
    success: bool
    source_version: str
    parsed_version: str
    config: ChunkingConfig
    chunks: list[ChunkPreview]
    total: int


class SaveProcessingConfigRequest(ProcessingConfig):
    source_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: str = Field(min_length=1, max_length=64)


class SaveProcessingConfigResponse(BaseModel):
    success: bool
    config: ProcessingConfig
    revision: str
    saved_at: str
    source_version: str


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
