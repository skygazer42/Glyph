"""
Configuration management for the policy QA system.
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field
from pydantic_settings import SettingsConfigDict


class ModelConfig(BaseSettings):
    """Model configuration."""
    model_name: str = Field(default="deepseek-chat", description="Model name")
    api_key: str = Field(default="", description="API key")
    base_url: str = Field(default="https://api.deepseek.com", description="API base URL")
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=4000, ge=1, le=32000)
    timeout: int = Field(default=120, ge=1)


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
    file: str = Field(default="logs/policy_qa.log")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    max_size: str = Field(default="10MB")
    backup_count: int = Field(default=5)


class ConversationConfig(BaseSettings):
    """Conversation (multi-turn) configuration."""
    max_turns: int = Field(default=20, ge=1, description="Maximum turns kept per session")
    history_window: int = Field(default=5, ge=1, description="How many recent turns to include in context")


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="")
    use_neo4j: bool = Field(default=False)


class Config(BaseSettings):
    """Main configuration class."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False
    )

    model: ModelConfig = Field(default_factory=ModelConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load configuration from file."""
        import yaml
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "model": self.model.dict(),
            "vector_store": self.vector_store.dict(),
            "logging": self.logging.dict(),
            "conversation": self.conversation.dict(),
            "database": self.database.dict()
        }
