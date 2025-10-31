"""
Gove项目配置设置
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class DatabaseSettings(BaseSettings):
    """数据库配置"""
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")
    use_neo4j: bool = Field(default=False)

    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: Optional[str] = Field(default=None)

    # ChromaDB
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8000)
    chroma_api_key: Optional[str] = Field(default=None)

    # Pinecone
    pinecone_api_key: Optional[str] = Field(default=None)
    pinecone_environment: str = Field(default="us-west1-gcp-free")


class ModelSettings(BaseSettings):
    """模型配置"""
    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.1, ge=0, le=2)
    openai_max_tokens: int = Field(default=4000)

    # Anthropic Claude
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-sonnet-20240229", env="ANTHROPIC_MODEL")
    anthropic_max_tokens: int = Field(default=4096)

    # MinerU (vLLM)
    mineru_api_key: str = Field(default="mineru")
    mineru_base_url: str = Field(default="http://localhost:8000/v1", env="MINERU_BASE_URL")
    mineru_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct", env="MINERU_MODEL")
    mineru_temperature: float = Field(default=0.1, ge=0, le=1)
    mineru_max_tokens: int = Field(default=4096)

    # Ollama (本地)
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2:7b", env="OLLAMA_MODEL")


class DocumentSettings(BaseSettings):
    """文档处理配置"""
    # OCR服务
    ocr_api_key: Optional[str] = Field(default=None)
    ocr_base_url: str = Field(default="https://api.ocr.space")

    # 启用功能
    enable_ocr: bool = Field(default=True)
    enable_table_extraction: bool = Field(default=True)
    enable_image_extraction: bool = Field(default=True)
    enable_formula_extraction: bool = Field(default=True)

    # 文档限制
    max_file_size_mb: int = Field(default=50)
    max_pages: int = Field(default=100)
    supported_formats: list = Field(
        default=[".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".html", ".xml", ".json", ".csv"]
    )


class MinerUSettings(BaseSettings):
    """MinerU特定配置"""
    # 文档理解
    extract_images: bool = Field(default=True)
    extract_tables: bool = Field(default=True)
    extract_lists: bool = Field(default=True)
    extract_formulas: bool = Field(default=True)

    # 处理选项
    preserve_layout: bool = Field(default=True)
    ocr_all_images: bool = Field(default=True)
    ocr_dpi: int = Field(default=300)

    # 输出格式
    output_format: str = Field(default="markdown")
    include_raw_ocr: bool = Field(default=True)

    # 分块配置
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    min_chunk_length: int = Field(default=100)


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
    project_root: Path = Field(default=Path(__file__).parent)
    data_dir: Path = Field(default=Path(__file__).parent / "resources" / "data")
    logs_dir: Path = Field(default=Path(__file__).parent / "resources" / "logs")

    # 调试选项
    debug: bool = Field(default=False, env="DEBUG")
    verbose: bool = Field(default=False)
    profile: bool = Field(default=False)

    # 开发选项
    auto_reload: bool = Field(default=False)
    enable_profiler: bool = Field(default=False)
    enable_hot_reload: bool = Field(default=False)


class Settings(BaseSettings):
    """主配置类"""
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    document: DocumentSettings = Field(default_factory=DocumentSettings)
    mineru: MinerUSettings = Field(default_factory=MinerUSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)

    class Config:
        env_file = ".env"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()

# 确保必要的目录存在
settings.system.data_dir.mkdir(parents=True, exist_ok=True)
settings.system.logs_dir.mkdir(parents=True, exist_ok=True)