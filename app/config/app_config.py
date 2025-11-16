"""
Gove项目配置设置
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
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
    llm_api_key: Optional[str] = Field(default=None, env="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.deepseek.com", env="LLM_BASE_URL")
    llm_model_name: str = Field(default="deepseek-chat", env="LLM_MODEL_NAME")
    llm_temperature: float = Field(default=0, env="LLM_TEMPERATURE")
    llm_ctx_buffer_size: int = Field(default=10, env="LLM_CTX_BUFFER_SIZE")


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
    openai_api_key: Optional[str] = Field(default=None, env="EMBEDDING_OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="EMBEDDING_OPENAI_BASE_URL")
    openai_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_OPENAI_MODEL")

    # DashScope Embedding（阿里云）
    dashscope_api_key: Optional[str] = Field(default=None, env="EMBEDDING_DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
        env="EMBEDDING_DASHSCOPE_BASE_URL"
    )
    dashscope_model: str = Field(default="text-embedding-v3", env="EMBEDDING_DASHSCOPE_MODEL")
    dashscope_dimension: Optional[int] = Field(default=None, env="EMBEDDING_DASHSCOPE_DIMENSION")
    dashscope_output_type: str = Field(default="dense", env="EMBEDDING_DASHSCOPE_OUTPUT_TYPE")

    # 通用配置
    dimension: int = Field(default=1536, env="EMBEDDING_DIM")
    batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    timeout: int = Field(default=30, env="EMBEDDING_TIMEOUT")


class LlamaIndexSettings(BaseSettings):
    """LlamaIndex 文档切块配置"""
    # 切块策略: sentence, semantic, fixed
    chunk_strategy: str = Field(default="sentence", env="LLAMAINDEX_CHUNK_STRATEGY")

    # 切块大小配置
    chunk_size: int = Field(default=1000, env="LLAMAINDEX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="LLAMAINDEX_CHUNK_OVERLAP")

    # Sentence Splitter 配置
    sentence_chunk_size: int = Field(default=1024, env="LLAMAINDEX_SENTENCE_CHUNK_SIZE")
    sentence_chunk_overlap: int = Field(default=200, env="LLAMAINDEX_SENTENCE_CHUNK_OVERLAP")

    # Semantic Splitter 配置
    semantic_buffer_size: int = Field(default=1, env="LLAMAINDEX_SEMANTIC_BUFFER_SIZE")
    semantic_breakpoint_threshold: float = Field(default=0.5, env="LLAMAINDEX_SEMANTIC_THRESHOLD")

    # Token 配置
    separator: str = Field(default=" ", env="LLAMAINDEX_SEPARATOR")
    paragraph_separator: str = Field(default="\n\n", env="LLAMAINDEX_PARAGRAPH_SEPARATOR")

    # 其他选项
    include_metadata: bool = Field(default=True, env="LLAMAINDEX_INCLUDE_METADATA")
    include_prev_next_rel: bool = Field(default=True, env="LLAMAINDEX_INCLUDE_PREV_NEXT")
    storage_dir: str = Field(
        default="resources/storage/hierarchical",
        env="LLAMAINDEX_STORAGE_DIR",
        description="Hierarchical index storage directory",
    )


class RerankerSettings(BaseSettings):
    """文本重排模型配置"""
    model_config = {"protected_namespaces": ("settings_",)}

    # Reranker backend: dashscope, xinference, llamaindex
    backend: str = Field(default="dashscope", env="RERANKER_BACKEND")
    model_name: str = Field(default="gte-rerank-v2", env="RERANKER_MODEL")
    api_key: Optional[str] = Field(default=None, env="DASHSCOPE_API_KEY")
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        env="RERANKER_ENDPOINT",
    )
    top_n: int = Field(default=5, ge=1, env="RERANKER_TOP_N")
    timeout: int = Field(default=30, ge=1, env="RERANKER_TIMEOUT")
    return_documents: bool = Field(default=False, env="RERANKER_RETURN_DOCUMENTS")
    normalize_scores: bool = Field(default=False, env="RERANKER_NORMALIZE_SCORES")

    # DashScope specific settings
    dashscope_api_key: Optional[str] = Field(default=None, env="DASHSCOPE_API_KEY")
    dashscope_rerank_model: str = Field(default="gte-rerank-v2", env="DASHSCOPE_RERANK_MODEL")

    # LlamaIndex rerank settings
    llama_index_rerank_enabled: bool = Field(default=True, env="LLAMA_INDEX_RERANK_ENABLED")
    similarity_top_k: int = Field(default=50, env="SIMILARITY_TOP_K")
    rerank_top_k: int = Field(default=5, env="RERANK_TOP_K")


class DocumentSettings(BaseSettings):
    """文档处理配置"""
    # 文档限制
    max_file_size_mb: int = Field(default=50, env="DOCUMENT__MAX_FILE_SIZE_MB")
    max_pages: int = Field(default=100, env="DOCUMENT__MAX_PAGES")
    supported_formats: list = Field(
        default=[".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".html", ".xml", ".json", ".csv"]
    )


class MinerUSettings(BaseSettings):
    """MinerU 文档解析配置

    支持两种运行模式：
    1. 官方云服务 API (https://mineru.net) - 需要 API Key
    2. 本地服务 API (http://localhost:30001) - 需要本地部署

    使用 mode="auto" 可自动选择最佳模式
    """
    # 基础配置
    enabled: bool = Field(default=False, env="MINERU_ENABLED")

    # 运行模式: "official", "local", "auto"
    mode: str = Field(default="auto", env="MINERU_MODE")

    # 官方 API 配置
    api_key: Optional[str] = Field(default=None, env="MINERU_API_KEY")
    official_base_url: str = Field(
        default="https://mineru.net/api/v4",
        env="MINERU_OFFICIAL_BASE_URL"
    )

    # 本地服务配置
    api_base_url: str = Field(default="http://localhost:30001", env="MINERU_API_BASE_URL")
    backend: str = Field(default="vlm-http-client", env="MINERU_BACKEND")
    vlm_server_url: Optional[str] = Field(default=None, env="MINERU_VLM_SERVER_URL")

    # 通用配置
    timeout: int = Field(default=600, env="MINERU_TIMEOUT")
    language: str = Field(default="ch", env="MINERU_LANGUAGE")

    # 文档解析选项
    extract_images: bool = Field(default=True, env="MINERU_EXTRACT_IMAGES")
    extract_tables: bool = Field(default=True, env="MINERU_EXTRACT_TABLES")
    extract_formulas: bool = Field(default=True, env="MINERU_EXTRACT_FORMULAS")

    # OCR 配置
    ocr_all_images: bool = Field(default=True, env="MINERU_OCR_ALL_IMAGES")

    # 批量处理配置
    max_concurrent: int = Field(default=3, env="MINERU_MAX_CONCURRENT")

    # 旧版兼容配置（保留用于向后兼容）
    extract_lists: bool = Field(default=True, env="MINERU_EXTRACT_LISTS")
    preserve_layout: bool = Field(default=True, env="MINERU_PRESERVE_LAYOUT")
    ocr_dpi: int = Field(default=300, env="MINERU_OCR_DPI")
    output_format: str = Field(default="markdown", env="MINERU_OUTPUT_FORMAT")
    include_raw_ocr: bool = Field(default=True, env="MINERU_INCLUDE_RAW_OCR")

    def get_effective_base_url(self) -> str:
        """获取有效的基础 URL（根据模式）"""
        if self.mode == "official":
            return self.official_base_url
        elif self.mode == "local":
            return self.api_base_url
        else:  # auto
            # 有 API Key 使用官方，否则使用本地
            if self.api_key:
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
    enabled: bool = Field(default=True, env="AUTOGEN_ENABLED")
    cache_enabled: bool = Field(default=True, env="AUTOGEN_CACHE_ENABLED")
    cache_duration: int = Field(default=3600, env="AUTOGEN_CACHE_DURATION")
    max_rounds: int = Field(default=10, env="AUTOGEN_MAX_ROUNDS")
    timeout: int = Field(default=300, env="AUTOGEN_TIMEOUT")

    # 监控配置
    enable_metrics: bool = Field(default=True, env="AUTOGEN_ENABLE_METRICS")

    # 环境配置
    environment: str = Field(default="development", env="ENVIRONMENT")

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


class SystemSettings(BaseSettings):
    """系统配置"""
    # 项目路径
    project_root: Path = Field(default=Path(__file__).resolve().parents[2])
    data_dir: Path = Field(default=Path(__file__).resolve().parents[2] / "resources" / "data")
    logs_dir: Path = Field(default=Path(__file__).resolve().parents[2] / "resources" / "logs")

    # 调试选项
    debug: bool = Field(default=False, env="DEBUG")
    verbose: bool = Field(default=False, env="VERBOSE")
    verbose_debug: bool = Field(default=False, env="VERBOSE_DEBUG")

    # 日志配置
    log_dir: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "resources" / "logs"),
        env="LOG_DIR"
    )
    log_max_bytes: int = Field(default=10485760, env="LOG_MAX_BYTES")
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")

    # 多轮对话配置
    conversation_max_turns: int = Field(default=20, env="CONVERSATION__MAX_TURNS")
    conversation_history_window: int = Field(default=5, env="CONVERSATION__HISTORY_WINDOW")

    # 并行/早停配置
    early_stop_conf: float = Field(default=0.80, env="EARLY_STOP_CONF")

    # LightRAG 配置
    lightrag_workdir: str = Field(default="resources/data/lightrag", env="LIGHTRAG_WORKDIR")
    lightrag_seed_data_dir: Optional[str] = Field(default=None, env="LIGHTRAG_SEED_DATA_DIR")
    max_embed_tokens: int = Field(default=8192, env="MAX_EMBED_TOKENS")

    # 知识检索上下文配置
    knowledge_max_context_per_doc: int = Field(
        default=6000,
        env="KNOWLEDGE_MAX_CONTEXT_PER_DOC",
    )

    # LlamaIndex 配置
    llama_index_embedding_model: str = Field(default="text-embedding-3-small", env="LLAMA_INDEX_EMBEDDING_MODEL")
    llama_index_llm_model: str = Field(default="deepseek-chat", env="LLAMA_INDEX_LLM_MODEL")

    # 智能体/服务功能开关
    hybrid_retrieval_enabled: bool = Field(default=False, env="SYSTEM__HYBRID_RETRIEVAL_ENABLED")
    auto_learning_enabled: bool = Field(default=False, env="SYSTEM__AUTO_LEARNING_ENABLED")
    max_examples_per_query: int = Field(default=5, env="SYSTEM__MAX_EXAMPLES_PER_QUERY")


class SecuritySettings(BaseSettings):
    """API 安全配置"""
    model_config = {
        "extra": "ignore",
        "env_nested_delimiter": "__"
    }

    jwt_secret_key: str = Field(default="dev-secret")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_exp_minutes: int = Field(default=60)
    api_default_username: str = Field(default="admin")
    api_default_password: str = Field(default="admin123")
    api_default_fullname: str = Field(default="Administrator")
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

# 确保必要的目录存在
settings.system.data_dir.mkdir(parents=True, exist_ok=True)
settings.system.logs_dir.mkdir(parents=True, exist_ok=True)
Path(settings.llamaindex.storage_dir).mkdir(parents=True, exist_ok=True)
