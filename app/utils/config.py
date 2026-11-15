"""
Configuration management for the policy QA system.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Model configuration bound to LLM_* environment variables."""

    model_name: str = Field(
        default="deepseek-chat",
        description="Model name",
        validation_alias=AliasChoices('LLM_MODEL_NAME', 'model_name'),
    )
    api_key: str = Field(default="", description="API key", validation_alias=AliasChoices('LLM_API_KEY', 'api_key'))
    base_url: str = Field(
        default="https://api.deepseek.com",
        description="API base URL",
        validation_alias=AliasChoices('LLM_BASE_URL', 'base_url'),
    )
    temperature: float = Field(default=0.1, ge=0, le=2, validation_alias=AliasChoices('LLM_TEMPERATURE', 'temperature'))
    max_tokens: int = Field(default=4000, ge=1, le=32000, validation_alias=AliasChoices('LLM_MAX_TOKENS', 'max_tokens'))
    timeout: int = Field(default=120, ge=1, validation_alias=AliasChoices('LLM_TIMEOUT', 'timeout'))


class VectorStoreConfig(BaseSettings):
    """Vector store configuration."""
    model_name: str = Field(default="BAAI/bge-large-zh-v1.5", description="Embedding model")
    index_path: str = Field(default="resources/data/vector_store/policy_index.faiss")
    metadata_path: str = Field(default="resources/data/vector_store/metadata.pkl")
    embedding_dim: int = Field(default=1024)
    similarity_threshold: float = Field(default=0.7, ge=0, le=1)
    top_k: int = Field(default=10, ge=1, le=100)
    cache_size: int = Field(default=1000, ge=1)


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    level: str = Field(default="INFO")
    file: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "resources" / "logs" / "policy_qa.log")
    )
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    max_size: str = Field(default="10MB")
    backup_count: int = Field(default=5)


class ConversationConfig(BaseSettings):
    """Conversation (multi-turn) configuration."""
    max_turns: int = Field(default=20, ge=1, description="Maximum turns kept per session")
    history_window: int = Field(default=5, ge=1, description="How many recent turns to include in context")


class VisionConfig(BaseSettings):
    """Vision / multimodal model configuration."""

    enabled: bool = Field(default=False, description="Enable multimodal vision reasoning")
    model: str = Field(default="gpt-4o-mini", description="Vision-capable model name")
    api_key: str | None = Field(default=None, description="API key for the vision model")
    base_url: str | None = Field(default=None, description="Optional custom base URL for the vision model")
    prompt_template: str = Field(
        default="请结合用户问题，描述图片中的关键信息（地点、票据、金额、日期、主体等），并输出结构化要点。",
        description="Prompt template used when asking the vision model to describe attachments.",
    )
    max_images: int = Field(default=2, ge=1, le=5, description="Maximum number of images to inspect per request")
    max_output_tokens: int = Field(
        default=800, ge=100, le=2000, description="Maximum output tokens for a single vision call"
    )

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def empty_setting_is_unconfigured(cls, value: Any) -> Any:
        """Treat empty .env entries as absent optional vision settings."""
        return None if value == "" else value


class WebSearchConfig(BaseSettings):
    """Fallback web search configuration."""

    enabled: bool = Field(default=False, description="Enable fallback web search via external APIs")
    provider: str = Field(default="tavily", description="Search provider identifier")
    tavily_api_key: str | None = Field(default=None, description="API key for Tavily")
    search_depth: str = Field(default="basic", description="Tavily search depth, e.g., basic/advanced")
    max_results: int = Field(default=3, ge=1, le=10, description="Maximum number of web results to request")
    site_filter: str = Field(
        default="",
        description="Optional site/domain limiter, e.g., gov.cn (will be appended as site:gov.cn).",
    )

    @field_validator("tavily_api_key", mode="before")
    @classmethod
    def empty_api_key_is_unconfigured(cls, value: Any) -> Any:
        """Treat an empty .env entry as an absent optional search key."""
        return None if value == "" else value


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    model_config = SettingsConfigDict(extra='ignore')

    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="")
    use_neo4j: bool = Field(default=False)


class PerformanceConfig(BaseSettings):
    """Performance tuning knobs (PERFORMANCE__* env vars)."""

    max_concurrent_queries: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices('PERFORMANCE__MAX_CONCURRENT_QUERIES', 'max_concurrent_queries'),
    )
    query_timeout: int = Field(default=30, ge=1, validation_alias=AliasChoices('PERFORMANCE__QUERY_TIMEOUT', 'query_timeout'))
    batch_size: int = Field(default=10, ge=1, validation_alias=AliasChoices('PERFORMANCE__BATCH_SIZE', 'batch_size'))
    batch_timeout: int = Field(default=300, ge=1, validation_alias=AliasChoices('PERFORMANCE__BATCH_TIMEOUT', 'batch_timeout'))
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        validation_alias=AliasChoices('PERFORMANCE__EMBEDDING_BATCH_SIZE', 'embedding_batch_size'),
    )
    vector_search_timeout: int = Field(
        default=10,
        ge=1,
        validation_alias=AliasChoices('PERFORMANCE__VECTOR_SEARCH_TIMEOUT', 'vector_search_timeout'),
    )
    enable_cache: bool = Field(default=True, validation_alias=AliasChoices('PERFORMANCE__ENABLE_CACHE', 'enable_cache'))
    cache_ttl: int = Field(default=3600, ge=0, validation_alias=AliasChoices('PERFORMANCE__CACHE_TTL', 'cache_ttl'))
    trace_latency: bool = Field(default=True, validation_alias=AliasChoices('PERFORMANCE__TRACE_LATENCY', 'trace_latency'))
    slow_threshold_ms: int = Field(default=4000, ge=0, validation_alias=AliasChoices('PERFORMANCE__SLOW_THRESHOLD_MS', 'slow_threshold_ms'))
    log_timing_breakdown: bool = Field(
        default=False,
        validation_alias=AliasChoices('PERFORMANCE__LOG_TIMING_BREAKDOWN', 'log_timing_breakdown'),
    )


class Config(BaseSettings):
    """Main configuration class."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    model: ModelConfig = Field(default_factory=ModelConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    user_profile_db_path: str = Field(
        default="resources/data/user_profiles.json",
        description="Path to the mock user profile database (JSON).",
        alias="USER_PROFILE_DB_PATH",
    )
    lightrag_seed_data_dir: Optional[str] = Field(
        default=None,
        description="Optional directory containing seed documents for LightRAG.",
        alias="LIGHTRAG_SEED_DATA_DIR",
    )
    answer_plain_output: bool = Field(
        default=False,
        description="If true, strip Markdown markers and return plain text to frontend.",
        alias="ANSWER__PLAIN_OUTPUT",
    )

    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load configuration from file."""
        with open(file_path, 'r', encoding='utf-8') as config_file:
            data = yaml.safe_load(config_file)
        return cls(**data)

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "model": self.model.model_dump(),
            "vector_store": self.vector_store.model_dump(),
            "logging": self.logging.model_dump(),
            "conversation": self.conversation.model_dump(),
            "database": self.database.model_dump(),
            "performance": self.performance.model_dump(),
            "vision": self.vision.model_dump(),
            "web_search": self.web_search.model_dump(),
            "user_profile_db_path": self.user_profile_db_path,
            "answer_plain_output": self.answer_plain_output,
        }

    @property
    def embedding_model(self) -> str:
        """Backward-compatible accessor for legacy code/tests."""
        return self.vector_store.model_name

    @property
    def rerank_model(self) -> str:
        """Expose the configured reranker model name, if any."""
        return os.getenv("RERANKER_MODEL", "")
