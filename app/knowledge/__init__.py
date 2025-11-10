"""
Knowledge base module for the policy QA system.
优化后仅包含核心模块，文档解析和向量存储已整合到 LlamaIndex
"""

from .mineru_adapter import MinerUAdapter
from .rapid_ocr_processor import RapidOCRProcessor
from .image_retrieval import ImageExtractor, ImageIndexer
from .hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)
from .llamaindex_integration import LlamaIndexIntegration
from .milvus import MilvusStore
from .rerank import Reranker
from .doc_enhanced import EnhancedDocumentProcessor

__all__ = [
    # 文档解析
    "MinerUAdapter",
    "EnhancedDocumentProcessor",

    # OCR 处理
    "RapidOCRProcessor",

    # 图片检索
    "ImageExtractor",
    "ImageIndexer",

    # 分层索引
    "HierarchicalIndexBuilder",
    "HierarchicalRetriever",
    "ChunkConfig",

    # LlamaIndex 集成
    "LlamaIndexIntegration",

    # 向量存储
    "MilvusStore",

    # 重排序
    "Reranker",
]
