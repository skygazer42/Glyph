"""
Gove项目配置设置
"""

from pathlib import Path
from typing import Literal, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from dotenv import load_dotenv

load_dotenv()

class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow",
        "env_nested_delimiter": "__"
    }

    # Neo4j 知识图谱
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")
    use_neo4j: bool = Field(default=False)

    # Milvus 向量数据库
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530)
    milvus_user: Optional[str] = Field(default=None)
    milvus_password: Optional[str] = Field(default=None)
    milvus_db_name: str = Field(default="default")
    milvus_collection_name: str = Field(default="policy_documents")
    milvus_use_secure: bool = Field(default=False)

    # 关系型数据库（默认MySQL）用于存储结构化元数据
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="root")
    mysql_password: str = Field(default="mysql")
    mysql_db: str = Field(default="policy_db")


class ModelSettings(BaseSettings):
    """模型配置 - 使用 OpenAI 兼容接口"""
    # LLM 主配置（支持所有 OpenAI 兼容的 API）
    llm_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('LLM_API_KEY', 'llm_api_key'))
    llm_base_url: str = Field(default="https://api.deepseek.com", validation_alias=AliasChoices('LLM_BASE_URL', 'llm_base_url'))
    llm_model_name: str = Field(default="deepseek-chat", validation_alias=AliasChoices('LLM_MODEL_NAME', 'llm_model_name'))
    llm_temperature: float = Field(default=0, validation_alias=AliasChoices('LLM_TEMPERATURE', 'llm_temperature'))
    llm_ctx_buffer_size: int = Field(default=10, validation_alias=AliasChoices('LLM_CTX_BUFFER_SIZE', 'llm_ctx_buffer_size'))
    llm_max_tokens: int | None = Field(
        default=None, ge=1, validation_alias=AliasChoices("LLM_MAX_TOKENS", "llm_max_tokens")
    )
    llm_timeout: float | None = Field(
        default=None, gt=0, allow_inf_nan=False,
        validation_alias=AliasChoices("LLM_TIMEOUT", "llm_timeout"),
    )


class EmbeddingSettings(BaseSettings):
    """Embedding API 配置"""
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow"
    }

    # Embedding 后端: openai, dashscope
    backend: str = Field(default="openai", validation_alias="EMBEDDING_BACKEND")

    # OpenAI Embedding
    openai_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('EMBEDDING_OPENAI_API_KEY', 'openai_api_key'))
    openai_base_url: Optional[str] = Field(default=None, validation_alias=AliasChoices('EMBEDDING_OPENAI_BASE_URL', 'openai_base_url'))
    openai_model: str = Field(default="text-embedding-3-small", validation_alias=AliasChoices('EMBEDDING_OPENAI_MODEL', 'openai_model'))

    # DashScope Embedding（阿里云）
    dashscope_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('EMBEDDING_DASHSCOPE_API_KEY', 'dashscope_api_key'))
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
        validation_alias=AliasChoices('EMBEDDING_DASHSCOPE_BASE_URL', 'dashscope_base_url')
    )
    dashscope_model: str = Field(default="text-embedding-v3", validation_alias=AliasChoices('EMBEDDING_DASHSCOPE_MODEL', 'dashscope_model'))
    dashscope_dimension: Optional[int] = Field(default=None, validation_alias=AliasChoices('EMBEDDING_DASHSCOPE_DIMENSION', 'dashscope_dimension'))
    dashscope_output_type: str = Field(default="dense", validation_alias=AliasChoices('EMBEDDING_DASHSCOPE_OUTPUT_TYPE', 'dashscope_output_type'))

    # 通用配置
    dimension: int = Field(default=1536, validation_alias=AliasChoices('EMBEDDING_DIM', 'dimension'))
    batch_size: int = Field(default=32, validation_alias=AliasChoices('EMBEDDING_BATCH_SIZE', 'batch_size'))
    timeout: int = Field(default=30, validation_alias=AliasChoices('EMBEDDING_TIMEOUT', 'timeout'))


class LlamaIndexSettings(BaseSettings):
    """LlamaIndex 文档切块配置"""
    # 切块策略: sentence, semantic, fixed
    chunk_strategy: str = Field(default="sentence", validation_alias=AliasChoices('LLAMAINDEX_CHUNK_STRATEGY', 'chunk_strategy'))

    # 切块大小配置
    chunk_size: int = Field(default=1000, validation_alias=AliasChoices('LLAMAINDEX_CHUNK_SIZE', 'chunk_size'))
    chunk_overlap: int = Field(default=200, validation_alias=AliasChoices('LLAMAINDEX_CHUNK_OVERLAP', 'chunk_overlap'))

    # Sentence Splitter 配置
    sentence_chunk_size: int = Field(default=1024, validation_alias=AliasChoices('LLAMAINDEX_SENTENCE_CHUNK_SIZE', 'sentence_chunk_size'))
    sentence_chunk_overlap: int = Field(default=200, validation_alias=AliasChoices('LLAMAINDEX_SENTENCE_CHUNK_OVERLAP', 'sentence_chunk_overlap'))

    # Semantic Splitter 配置
    semantic_buffer_size: int = Field(default=1, validation_alias=AliasChoices('LLAMAINDEX_SEMANTIC_BUFFER_SIZE', 'semantic_buffer_size'))
    semantic_breakpoint_threshold: float = Field(default=0.5, validation_alias=AliasChoices('LLAMAINDEX_SEMANTIC_THRESHOLD', 'semantic_breakpoint_threshold'))

    # Token 配置
    separator: str = Field(default=" ", validation_alias=AliasChoices('LLAMAINDEX_SEPARATOR', 'separator'))
    paragraph_separator: str = Field(default="\n\n", validation_alias=AliasChoices('LLAMAINDEX_PARAGRAPH_SEPARATOR', 'paragraph_separator'))

    # 其他选项
    include_metadata: bool = Field(default=True, validation_alias=AliasChoices('LLAMAINDEX_INCLUDE_METADATA', 'include_metadata'))
    include_prev_next_rel: bool = Field(default=True, validation_alias=AliasChoices('LLAMAINDEX_INCLUDE_PREV_NEXT', 'include_prev_next_rel'))
    storage_dir: str = Field(
        default="resources/storage/hierarchical",
        validation_alias=AliasChoices('LLAMAINDEX_STORAGE_DIR', 'storage_dir'),
        description="Hierarchical index storage directory",
    )


class RerankerSettings(BaseSettings):
    """文本重排模型配置"""
    model_config = {"protected_namespaces": ("settings_",)}

    # Reranker backend: dashscope, xinference, llamaindex
    backend: str = Field(default="dashscope", validation_alias=AliasChoices('RERANKER_BACKEND', 'backend'))
    model_name: str = Field(default="gte-rerank-v2", validation_alias=AliasChoices('RERANKER_MODEL', 'model_name'))
    api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('DASHSCOPE_API_KEY', 'api_key'))
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        validation_alias=AliasChoices('RERANKER_ENDPOINT', 'base_url'),
    )
    top_n: int = Field(default=5, ge=1, validation_alias=AliasChoices('RERANKER_TOP_N', 'top_n'))
    timeout: int = Field(default=30, ge=1, validation_alias=AliasChoices('RERANKER_TIMEOUT', 'timeout'))
    return_documents: bool = Field(default=False, validation_alias=AliasChoices('RERANKER_RETURN_DOCUMENTS', 'return_documents'))

    # DashScope specific settings
    dashscope_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices('DASHSCOPE_API_KEY', 'dashscope_api_key'))
    dashscope_rerank_model: str = Field(default="gte-rerank-v2", validation_alias=AliasChoices('DASHSCOPE_RERANK_MODEL', 'dashscope_rerank_model'))

    # LlamaIndex rerank settings
    llama_index_rerank_enabled: bool = Field(default=True, validation_alias=AliasChoices('LLAMA_INDEX_RERANK_ENABLED', 'llama_index_rerank_enabled'))
    similarity_top_k: int = Field(default=50, validation_alias=AliasChoices('SIMILARITY_TOP_K', 'similarity_top_k'))
    rerank_top_k: int = Field(default=5, validation_alias=AliasChoices('RERANK_TOP_K', 'rerank_top_k'))


class DocumentSettings(BaseSettings):
    """文档处理配置"""
    # 文档限制
    max_file_size_mb: int = Field(default=50, validation_alias=AliasChoices('DOCUMENT__MAX_FILE_SIZE_MB', 'max_file_size_mb'))
    max_pages: int = Field(default=100, validation_alias=AliasChoices('DOCUMENT__MAX_PAGES', 'max_pages'))
    supported_formats: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".html", ".xml", ".json", ".csv"]
    )


class MinerUSettings(BaseSettings):
    """MinerU 文档解析配置

    支持两种运行模式：
    1. 官方云服务 API (https://mineru.net) - 需要 API Key
    2. 本地服务 API (http://localhost:30001) - 需要本地部署

    使用 mode="auto" 可自动选择最佳模式
    """
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow"
    }

    # 基础配置
    enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("MINERU_ENABLED", "MINERU__ENABLED"),
    )

    # 运行模式: "official", "local", "auto"
    mode: Literal["auto", "local", "official"] = Field(
        default="auto",
        validation_alias=AliasChoices("MINERU_MODE", "MINERU__MODE"),
    )

    # 官方 API 配置
    api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MINERU_API_KEY", "MINERU__API_KEY"),
    )
    official_base_url: str = Field(
        default="https://mineru.net/api/v4",
        validation_alias=AliasChoices(
            "MINERU_OFFICIAL_BASE_URL", "MINERU__OFFICIAL_BASE_URL"
        ),
    )

    # 本地服务配置
    api_base_url: str = Field(
        default="http://localhost:30001",
        validation_alias=AliasChoices("MINERU_API_BASE_URL", "MINERU__API_BASE_URL"),
    )
    backend: str = Field(
        default="vlm-http-client",
        validation_alias=AliasChoices("MINERU_BACKEND", "MINERU__BACKEND"),
    )
    vlm_server_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MINERU_VLM_SERVER_URL", "MINERU__VLM_SERVER_URL"),
    )

    # 通用配置
    timeout: int = Field(
        default=600,
        validation_alias=AliasChoices("MINERU_TIMEOUT", "MINERU__TIMEOUT"),
    )
    language: str = Field(
        default="ch",
        validation_alias=AliasChoices("MINERU_LANGUAGE", "MINERU__LANGUAGE"),
    )

    # 文档解析选项
    extract_images: bool = Field(
        default=True,
        validation_alias=AliasChoices("MINERU_EXTRACT_IMAGES", "MINERU__EXTRACT_IMAGES"),
    )
    extract_tables: bool = Field(
        default=True,
        validation_alias=AliasChoices("MINERU_EXTRACT_TABLES", "MINERU__EXTRACT_TABLES"),
    )
    extract_formulas: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "MINERU_EXTRACT_FORMULAS", "MINERU__EXTRACT_FORMULAS"
        ),
    )

    # OCR 配置
    ocr_all_images: bool = Field(
        default=True,
        validation_alias=AliasChoices("MINERU_OCR_ALL_IMAGES", "MINERU__OCR_ALL_IMAGES"),
    )

    # 批量处理配置
    max_concurrent: int = Field(
        default=3,
        validation_alias=AliasChoices("MINERU_MAX_CONCURRENT", "MINERU__MAX_CONCURRENT"),
    )

    # 旧版兼容配置（保留用于向后兼容）
    extract_lists: bool = Field(
        default=True,
        validation_alias=AliasChoices("MINERU_EXTRACT_LISTS", "MINERU__EXTRACT_LISTS"),
    )
    preserve_layout: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "MINERU_PRESERVE_LAYOUT", "MINERU__PRESERVE_LAYOUT"
        ),
    )
    ocr_dpi: int = Field(
        default=300,
        validation_alias=AliasChoices("MINERU_OCR_DPI", "MINERU__OCR_DPI"),
    )
    output_format: str = Field(
        default="markdown",
        validation_alias=AliasChoices("MINERU_OUTPUT_FORMAT", "MINERU__OUTPUT_FORMAT"),
    )
    include_raw_ocr: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "MINERU_INCLUDE_RAW_OCR", "MINERU__INCLUDE_RAW_OCR"
        ),
    )
    model_version: str = Field(
        default="vlm",
        validation_alias=AliasChoices("MINERU_MODEL_VERSION", "MINERU__MODEL_VERSION"),
    )
    poll_interval: int = Field(
        default=3,
        validation_alias=AliasChoices("MINERU_POLL_INTERVAL", "MINERU__POLL_INTERVAL"),
    )
    poll_timeout: int = Field(
        default=300,
        validation_alias=AliasChoices("MINERU_POLL_TIMEOUT", "MINERU__POLL_TIMEOUT"),
    )

    def get_effective_base_url(self) -> str:
        """获取有效的基础 URL（根据模式）"""
        if self.get_effective_mode() == "official":
            return self.official_base_url
        return self.api_base_url

    def get_effective_mode(self) -> str:
        """获取有效的运行模式"""
        if self.mode == "auto":
            return "official" if self.api_key else "local"
        return self.mode


class AutoGenSettings(BaseSettings):
    """AutoGen配置"""
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow"
    }

    # 基础配置
    enabled: bool = Field(default=True, validation_alias=AliasChoices('AUTOGEN_ENABLED', 'enabled'))
    cache_enabled: bool = Field(default=True, validation_alias=AliasChoices('AUTOGEN_CACHE_ENABLED', 'cache_enabled'))
    cache_duration: int = Field(default=3600, validation_alias=AliasChoices('AUTOGEN_CACHE_DURATION', 'cache_duration'))
    max_rounds: int = Field(default=10, validation_alias=AliasChoices('AUTOGEN_MAX_ROUNDS', 'max_rounds'))
    timeout: int = Field(default=300, validation_alias=AliasChoices('AUTOGEN_TIMEOUT', 'timeout'))

    # 监控配置
    enable_metrics: bool = Field(default=True, validation_alias=AliasChoices('AUTOGEN_ENABLE_METRICS', 'enable_metrics'))

    # 环境配置
    environment: str = Field(default="development", validation_alias=AliasChoices('ENVIRONMENT', 'environment'))

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.environment.lower() in ("testing", "test")


class PerformanceSettings(BaseSettings):
    """性能配置"""
    # 并发处理
    max_concurrent_queries: int = Field(default=5)
    query_timeout: int = Field(default=30)

    # 文档处理
    batch_size: int = Field(default=10)
    batch_timeout: int = Field(default=300)

    # 向量操作
    embedding_batch_size: int = Field(default=32)
    vector_search_timeout: int = Field(default=10)

    # 缓存
    enable_cache: bool = Field(default=True)
    cache_ttl: int = Field(default=3600)
    trace_latency: bool = Field(default=True)
    slow_threshold_ms: int = Field(default=4000)
    log_timing_breakdown: bool = Field(default=False)


class SystemSettings(BaseSettings):
    """系统配置"""
    # 项目路径
    project_root: Path = Field(default=Path(__file__).resolve().parents[2])
    data_dir: Path = Field(default=Path(__file__).resolve().parents[2] / "resources" / "data")
    logs_dir: Path = Field(default=Path(__file__).resolve().parents[2] / "resources" / "logs")

    # 调试选项
    debug: bool = Field(default=False, validation_alias=AliasChoices('DEBUG', 'debug'))
    verbose: bool = Field(default=False, validation_alias=AliasChoices('VERBOSE', 'verbose'))
    verbose_debug: bool = Field(default=False, validation_alias=AliasChoices('VERBOSE_DEBUG', 'verbose_debug'))

    # 日志配置
    log_dir: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "resources" / "logs"),
        validation_alias=AliasChoices('LOG_DIR', 'log_dir')
    )
    log_max_bytes: int = Field(default=10485760, validation_alias=AliasChoices('LOG_MAX_BYTES', 'log_max_bytes'))
    log_backup_count: int = Field(default=5, validation_alias=AliasChoices('LOG_BACKUP_COUNT', 'log_backup_count'))

    # 多轮对话配置
    conversation_max_turns: int = Field(default=20, validation_alias=AliasChoices('CONVERSATION__MAX_TURNS', 'conversation_max_turns'))
    conversation_history_window: int = Field(default=5, validation_alias=AliasChoices('CONVERSATION__HISTORY_WINDOW', 'conversation_history_window'))

    # 并行/早停配置
    early_stop_conf: float = Field(default=0.80, validation_alias=AliasChoices('EARLY_STOP_CONF', 'early_stop_conf'))

    # LightRAG 配置
    lightrag_workdir: str = Field(default="resources/data/lightrag_changzhou_20261121", validation_alias=AliasChoices('LIGHTRAG_WORKDIR', 'lightrag_workdir'))
    lightrag_seed_data_dir: Optional[str] = Field(default=None, validation_alias=AliasChoices('LIGHTRAG_SEED_DATA_DIR', 'lightrag_seed_data_dir'))
    max_embed_tokens: int = Field(default=8192, validation_alias=AliasChoices('MAX_EMBED_TOKENS', 'max_embed_tokens'))

    # 知识检索上下文配置
    knowledge_max_context_per_doc: int = Field(
        default=6000,
        gt=0,
        validation_alias=AliasChoices('KNOWLEDGE_MAX_CONTEXT_PER_DOC', 'knowledge_max_context_per_doc'),
    )

    # LlamaIndex 配置
    llama_index_embedding_model: str = Field(default="text-embedding-3-small", validation_alias=AliasChoices('LLAMA_INDEX_EMBEDDING_MODEL', 'llama_index_embedding_model'))
    llama_index_llm_model: str = Field(default="deepseek-chat", validation_alias=AliasChoices('LLAMA_INDEX_LLM_MODEL', 'llama_index_llm_model'))

    # 智能体/服务功能开关
    hybrid_retrieval_enabled: bool = Field(default=False, validation_alias=AliasChoices('SYSTEM__HYBRID_RETRIEVAL_ENABLED', 'hybrid_retrieval_enabled'))
    auto_learning_enabled: bool = Field(default=False, validation_alias=AliasChoices('SYSTEM__AUTO_LEARNING_ENABLED', 'auto_learning_enabled'))
    max_examples_per_query: int = Field(default=5, validation_alias=AliasChoices('SYSTEM__MAX_EXAMPLES_PER_QUERY', 'max_examples_per_query'))


class SecuritySettings(BaseSettings):
    """API 安全配置"""
    model_config = {
        "extra": "ignore",
        "env_nested_delimiter": "__"
    }

    jwt_secret_key: str | None = Field(default=None)
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_exp_minutes: int = Field(default=60, ge=1)
    api_default_username: str | None = Field(default=None)
    api_default_password: str | None = Field(default=None)
    api_default_fullname: str = Field(default="Administrator")
    auth_cookie_secure: bool = Field(default=False)
    public_session_exp_hours: int = Field(default=24, ge=1)
    rate_limit_query_times: int = Field(default=30)
    rate_limit_query_seconds: int = Field(default=60)
    rate_limit_docs_times: int = Field(default=5)
    rate_limit_docs_seconds: int = Field(default=60)
    rate_limit_redis_url: str = Field(default="redis://localhost:6379/0")
    rate_limit_disable: bool = Field(default=True)
    disable_auth: bool = Field(default=False)


class Settings(BaseSettings):
    """主配置类"""
    model_config = {
        "extra": "ignore",
        "env_file": ".env",
        "case_sensitive": False,
        "env_nested_delimiter": "__"
    }

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llamaindex: LlamaIndexSettings = Field(default_factory=LlamaIndexSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    document: DocumentSettings = Field(default_factory=DocumentSettings)
    mineru: MinerUSettings = Field(default_factory=MinerUSettings)
    autogen: AutoGenSettings = Field(default_factory=AutoGenSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)


# 创建全局配置实例
settings = Settings()
