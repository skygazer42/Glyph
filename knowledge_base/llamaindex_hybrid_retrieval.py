#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 LlamaIndex 的混合检索 (BM25 + Vector)
使用 Milvus enable_sparse 功能实现真正的混合检索
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from llama_index.core import (
    Document,
    VectorStoreIndex,
    StorageContext,
    Settings
)
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.milvus import MilvusVectorStore

from config.settings import settings


class LlamaIndexHybridRetriever:
    """
    基于 LlamaIndex 和 Milvus 的混合检索器

    特性:
    1. 使用 Milvus enable_sparse=True 实现 BM25 全文检索
    2. 结合向量语义检索
    3. 支持 alpha 参数调节关键词和语义检索的权重
    4. 与现有 MilvusStore 兼容
    """

    def __init__(
        self,
        collection_name: str = "hybrid_search",
        uri: Optional[str] = None,
        token: Optional[str] = None,
        dim: Optional[int] = None,
        alpha: float = 0.5,
        similarity_top_k: int = 10,
        overwrite: bool = False
    ):
        """
        初始化混合检索器

        Args:
            collection_name: Milvus 集合名称
            uri: Milvus URI (默认从 settings 读取)
            token: Milvus token (可选)
            dim: 向量维度 (默认从 settings 读取)
            alpha: 权重参数 (0-1)
                   0.0 = 纯 BM25 关键词检索
                   1.0 = 纯向量语义检索
                   0.5 = 均衡混合
            similarity_top_k: 返回结果数量
            overwrite: 是否覆盖已存在的集合
        """
        # 从 settings 读取配置
        self.uri = uri or f"http://{settings.database.milvus_host}:{settings.database.milvus_port}"
        self.token = token
        self.dim = dim or self._infer_dim()
        self.collection_name = collection_name
        self.alpha = alpha
        self.similarity_top_k = similarity_top_k

        # 配置 LlamaIndex Settings
        self._setup_llama_settings()

        # 创建 Milvus Vector Store (支持稀疏向量)
        print(f"[LlamaIndexHybridRetriever] 初始化")
        print(f"  URI: {self.uri}")
        print(f"  Collection: {self.collection_name}")
        print(f"  Dimension: {self.dim}")
        print(f"  Alpha: {self.alpha} (0=BM25, 1=Vector)")
        print(f"  Top-K: {self.similarity_top_k}")

        # 配置索引参数
        index_config = {
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {"M": 16, "efConstruction": 256}
        }

        # 配置稀疏索引参数
        sparse_index_config = {
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "IP"  # 稀疏索引必须使用 IP
        }

        self.vector_store = MilvusVectorStore(
            uri=self.uri,
            token=self.token,
            collection_name=self.collection_name,
            dim=self.dim,
            enable_sparse=True,  # 启用 BM25 全文检索
            hybrid_ranker="RRFRanker",  # 使用 RRF (Reciprocal Rank Fusion) 混合排序
            hybrid_ranker_params={"k": 60},  # RRF 参数
            similarity_metric="IP",  # 向量索引使用 IP
            index_config=index_config,  # 向量索引配置
            sparse_index_config=sparse_index_config,  # 稀疏索引配置
            overwrite=overwrite
        )

        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )

        self.index: Optional[VectorStoreIndex] = None
        self.query_engine = None

        print(f"✓ 混合检索器初始化完成")

    def _infer_dim(self) -> int:
        """从 settings 推断向量维度"""
        backend = settings.embedding.backend

        if backend == "openai":
            model_name = settings.embedding.openai_model or "text-embedding-3-small"
            if "3-large" in model_name:
                return 3072
            elif "3-small" in model_name:
                return 1536
            return 1536
        elif backend == "dashscope":
            # DashScope 默认使用配置的维度
            if settings.embedding.dashscope_dimension:
                return settings.embedding.dashscope_dimension
            return 1024

        # 默认使用 settings 中的配置
        return settings.embedding.dimension or 1024

    def _setup_llama_settings(self):
        """配置 LlamaIndex 全局设置"""
        backend = settings.embedding.backend

        # 禁用代理（如果环境变量设置了代理）
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)

        if backend == "dashscope":
            # 使用 DashScope (阿里云) - 优先处理
            from llama_index.embeddings.dashscope import (
                DashScopeEmbedding,
                DashScopeTextEmbeddingModels,
                DashScopeTextEmbeddingType
            )

            api_key = settings.embedding.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY")

            if not api_key:
                raise ValueError("DashScope API key is required. Set EMBEDDING_DASHSCOPE_API_KEY in .env")

            Settings.embed_model = DashScopeEmbedding(
                model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
                text_type=DashScopeTextEmbeddingType.TEXT_TYPE_DOCUMENT,
                api_key=api_key
            )

            # LLM 配置（如果使用 DeepSeek 或其他 OpenAI 兼容 API）
            llm_api_key = settings.model.llm_api_key or os.getenv("LLM_API_KEY")
            if llm_api_key:
                from llama_index.llms.openai import OpenAI

                Settings.llm = OpenAI(
                    model=settings.model.llm_model_name or "qwen-turbo",
                    api_key=llm_api_key,
                    api_base=settings.model.llm_base_url
                )

            print(f"  Embedding: DashScope {DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3}")
            print(f"  LLM: {settings.model.llm_model_name} via {settings.model.llm_base_url}")

        elif backend == "openai":
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.llms.openai import OpenAI

            Settings.embed_model = OpenAIEmbedding(
                model=settings.embedding.openai_model or "text-embedding-3-small",
                api_key=settings.embedding.openai_api_key or os.getenv("OPENAI_API_KEY")
            )

            # LLM 配置（使用 ModelSettings）
            llm_api_key = settings.model.llm_api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if llm_api_key:
                Settings.llm = OpenAI(
                    model=settings.model.llm_model_name or "gpt-4",
                    api_key=llm_api_key,
                    api_base=settings.model.llm_base_url if settings.model.llm_base_url != "https://api.deepseek.com" else None
                )

            print(f"  Embedding: OpenAI {settings.embedding.openai_model}")
            print(f"  LLM: {settings.model.llm_model_name}")

    def build_index(self, documents: List[Document]):
        """
        从文档构建索引

        Args:
            documents: LlamaIndex Document 对象列表
        """
        print(f"\n[构建索引] 开始嵌入 {len(documents)} 个文档...")

        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context,
            show_progress=True
        )

        print(f"✓ 索引构建完成")

        # 创建混合检索查询引擎
        self._create_query_engine()

    def load_index(self):
        """
        加载已存在的索引
        """
        print(f"\n[加载索引] 从 {self.collection_name} 加载...")

        self.index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            storage_context=self.storage_context
        )

        print(f"✓ 索引加载完成")

        # 创建混合检索查询引擎
        self._create_query_engine()

    def _create_query_engine(self):
        """创建混合检索查询引擎"""
        if self.index is None:
            raise ValueError("Index not built or loaded. Call build_index() or load_index() first.")

        # 创建混合检索器
        retriever = self.index.as_retriever(
            vector_store_query_mode="hybrid",  # 混合模式
            similarity_top_k=self.similarity_top_k,
            alpha=self.alpha  # 权重参数
        )

        # 创建查询引擎
        self.query_engine = RetrieverQueryEngine.from_args(
            retriever=retriever
        )

    def query(self, query_str: str) -> Dict[str, Any]:
        """
        执行混合检索查询

        Args:
            query_str: 查询字符串

        Returns:
            查询结果字典，包含 response 和 source_nodes
        """
        if self.query_engine is None:
            raise ValueError("Query engine not initialized. Call build_index() or load_index() first.")

        print(f"\n[混合检索] 查询: {query_str}")
        print(f"  模式: 混合 (alpha={self.alpha})")
        print(f"  Top-K: {self.similarity_top_k}")

        response = self.query_engine.query(query_str)

        print(f"✓ 检索完成，返回 {len(response.source_nodes)} 个结果")

        return {
            "response": str(response),
            "source_nodes": response.source_nodes
        }

    def retrieve(self, query_str: str) -> List[NodeWithScore]:
        """
        仅执行检索，不生成回答

        Args:
            query_str: 查询字符串

        Returns:
            NodeWithScore 列表
        """
        if self.index is None:
            raise ValueError("Index not built or loaded. Call build_index() or load_index() first.")

        retriever = self.index.as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=self.similarity_top_k,
            alpha=self.alpha
        )

        nodes = retriever.retrieve(query_str)

        print(f"\n[混合检索] 查询: {query_str}")
        print(f"  检索到 {len(nodes)} 个结果")

        return nodes

    def update_alpha(self, alpha: float):
        """
        更新 alpha 权重参数

        Args:
            alpha: 新的权重 (0-1)
        """
        if not 0 <= alpha <= 1:
            raise ValueError("Alpha must be between 0 and 1")

        self.alpha = alpha
        print(f"[更新] Alpha 权重: {self.alpha}")

        # 重新创建查询引擎
        if self.index is not None:
            self._create_query_engine()


def load_documents_from_dir(data_dir: Path) -> List[Document]:
    """
    从目录加载文档

    Args:
        data_dir: 数据目录路径

    Returns:
        LlamaIndex Document 对象列表
    """
    from llama_index.core import SimpleDirectoryReader

    print(f"\n[加载文档] 从 {data_dir} 加��...")

    reader = SimpleDirectoryReader(
        input_dir=str(data_dir),
        recursive=True,
        required_exts=[".md", ".txt"]
    )

    documents = reader.load_data()

    print(f"✓ 加载了 {len(documents)} 个文档")

    return documents


# ===== 使用示例 =====

if __name__ == "__main__":
    """测试混合检索"""

    # 1. 创建混合检索器
    retriever = LlamaIndexHybridRetriever(
        collection_name="policy_hybrid_search",
        alpha=0.5,  # 均衡混合
        similarity_top_k=10,
        overwrite=True
    )

    # 2. 加载文档
    data_dir = Path("/data/temp33/gov/data/process")
    documents = load_documents_from_dir(data_dir)

    # 3. 构建索引
    retriever.build_index(documents)

    # 4. 测试查询
    test_queries = [
        "家电以旧换新有什么补贴政策？",
        "买新手机有什么优惠活动？",
        "汽车消费补贴怎么申请？",
        "济南市2025年有哪些消费活动？",
        "智能手表购新补贴的条件是什么？"
    ]

    print("\n" + "=" * 80)
    print("  测试混合检索 (Alpha=0.5)")
    print("=" * 80)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"查询 {i}: {query}")
        print('=' * 80)

        # 执行检索
        nodes = retriever.retrieve(query)

        # 显示结果
        print(f"\n[检索结果] Top 3:")
        for j, node in enumerate(nodes[:3], 1):
            print(f"\n  结果 {j}:")
            print(f"    Score: {node.score:.4f}")
            print(f"    Text: {node.node.text[:150]}...")

    # 5. 测试不同 alpha 值
    print("\n" + "=" * 80)
    print("  测试不同 Alpha 值")
    print("=" * 80)

    query = "家电以旧换新补贴"

    for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
        retriever.update_alpha(alpha)

        print(f"\n{'=' * 60}")
        print(f"Alpha = {alpha:.1f} ({'纯BM25' if alpha == 0 else '纯向量' if alpha == 1 else '混合'})")
        print('=' * 60)

        nodes = retriever.retrieve(query)

        print(f"Top 3 结果:")
        for j, node in enumerate(nodes[:3], 1):
            print(f"  {j}. [{node.score:.4f}] {node.node.text[:80]}...")

    print("\n" + "=" * 80)
    print("  测试完成")
    print("=" * 80)
