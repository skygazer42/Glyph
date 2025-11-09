"""
Configuration module for the policy QA system.
"""
from .app_config import (
    Settings,
    DatabaseSettings,
    ModelSettings,
    EmbeddingSettings,
    LlamaIndexSettings,
    RerankerSettings,
    DocumentSettings,
    MinerUSettings,
    AutoGenSettings,
    PerformanceSettings,
    SystemSettings,
    settings  # 全局配置实例
)

__all__ = [
    'Settings',
    'DatabaseSettings',
    'ModelSettings',
    'EmbeddingSettings',
    'LlamaIndexSettings',
    'RerankerSettings',
    'DocumentSettings',
    'MinerUSettings',
    'AutoGenSettings',
    'PerformanceSettings',
    'SystemSettings',
    'settings',
]