"""
Vector-based retrieval agent (no torch dependency).

Supported embedding backends:
- openai (default): OpenAI Embeddings API（轻量）
- ollama: 本地 Ollama 嵌入服务
"""

import os
import pickle
from datetime import datetime
import asyncio
from pathlib import Path
import numpy as np
from typing import List, Dict, Any, Optional
import time
from openai import AsyncOpenAI

from autogen_core import MessageContext
import faiss

from app.models.policy import (
    AgentType,
   MessageType,
   AgentMessage,
   RetrievalRequest,
   RetrievalResult,
   PolicyDocument,
   RetrievalMethod
)
from app.agents.framework.base.base_agent import StatefulAgent
from app.knowledge.rerank import Reranker


class VectorRetrieverAgent(StatefulAgent):
    """Vector-based policy document retrieval agent."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        index_path: str = "resources/data/vector_store/policy_index.faiss",
        metadata_path: str = "resources/data/vector_store/metadata.pkl",
        embedding_dim: Optional[int] = None,
        embedding_backend: Optional[str] = None,
        **kwargs
    ):
        """Initialize the vector retriever agent."""
        super().__init__(
            agent_type=AgentType.POLICY_RETRIEVER,
            name="VectorRetriever",
            description="负责基于向量相似度的政策文档检索",
            **kwargs
        )

        # Embedding backend & model
        self.embedding_backend = (embedding_backend or os.getenv("EMBEDDING_BACKEND") or "openai").lower()
        if model_name is None:
            model_name = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
        if not model_name:
            raise ValueError("Embedding model name must not be empty")
        self.model_name: str = model_name
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_dim = self._infer_embedding_dim(self.embedding_backend, self.model_name) if embedding_dim is None else embedding_dim
        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim must be positive")

        # Initialize components
        self.embedding_model = None  # backends无需预加载
        self.vector_index: Any = None
        self.document_metadata: List[Dict] = []
        self._load_or_create_index()

        # Cache for query embeddings
        self.embedding_cache: Dict[str, List[float]] = {}
        self.cache_size = 1000

    async def initialize(self):
        """No-op for openai/ollama backends (无需预加载)."""
        self.logger.info(f"Embedding backend '{self.embedding_backend}' 无需预加载")

    def _load_or_create_index(self):
        """Load existing index or create new one."""
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.metadata_path).parent.mkdir(parents=True, exist_ok=True)

        index_exists = os.path.exists(self.index_path)
        metadata_exists = os.path.exists(self.metadata_path)
        if index_exists != metadata_exists:
            raise ValueError("Persisted vector index and metadata must exist together as a pair")
        if index_exists:
            # Load existing index
            self.vector_index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.document_metadata = pickle.load(f)
            if len(self.document_metadata) != self.vector_index.ntotal:
                raise ValueError("Vector index and metadata counts differ")
            self.embedding_dim = self.vector_index.d
            self.logger.info(f"Loaded index with {len(self.document_metadata)} documents")
        else:
            # Create new index
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
            self.document_metadata = []
            self.logger.info("Created new vector index")

    async def add_documents(self, documents: List[PolicyDocument]):
        """Add documents to the vector store."""
        self.logger.info(f"Adding {len(documents)} documents to vector store")
        if not documents:
            return

        # Prepare texts for embedding
        texts = []
        for doc in documents:
            # Combine title, content, and keywords for better retrieval
            text = f"{doc.title} {doc.content} {' '.join(doc.keywords)}"
            texts.append(text)

        # Generate embeddings via backend
        all_embeddings = await self._embed_texts(texts)
        if len(all_embeddings) != len(documents):
            raise ValueError("Embedding and document count differ")

        # Add to index
        self.vector_index.add(all_embeddings.astype(np.float32))

        # Store metadata
        for doc in documents:
            self.document_metadata.append({
                "id": str(doc.id),
                "title": doc.title,
                "content": doc.content[:8000],  # Store more content to include detailed standards
                "source": doc.source,
                "doc_type": doc.doc_type,
                "publish_date": doc.publish_date.isoformat() if doc.publish_date else None,
                "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                "keywords": doc.keywords,
                "regions": doc.regions,
                "target_groups": doc.target_groups
            })

        # Save to disk
        await self._save_index()

        self.logger.info(f"Successfully added {len(documents)} documents")

    async def _save_index(self):
        """Save index and metadata to disk."""
        await asyncio.to_thread(self._save_index_sync)

    def _save_index_sync(self):
        """Persist this trusted local index and its matching metadata together."""
        faiss.write_index(self.vector_index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.document_metadata, f)

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages."""
        query_data = message.content
        query = query_data["text"]

        # Generate embedding for the query
        query_embedding = await self._get_query_embedding(query)

        # Perform search
        search_results = await self._search_similar(
            query_embedding,
            top_k=10,
            threshold=0.7
        )

        # Optional rerank via DashScope if enabled and query text available
        search_results = await self._maybe_rerank(query, search_results)

        # Create response
        return AgentMessage(
            type=MessageType.RETRIEVAL_RESULT,
            sender=self.agent_type,
            recipient=message.sender,
            content={
                "query_id": str(query_data["id"]),
                "documents": search_results["documents"],
                "scores": search_results["scores"],
                "method": RetrievalMethod.SEMANTIC_SEARCH,
                "total_searched": len(self.document_metadata)
            },
            correlation_id=message.correlation_id
        )

    async def _handle_retrieval_request(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle retrieval request messages."""
        request_data = message.content
        query_embedding = request_data.get("query_embedding")
        if query_embedding is None:
            raise ValueError("query_embedding is required for vector search")
        filters = request_data.get("filters", {})
        top_k = request_data.get("top_k", 10)
        threshold = request_data.get("threshold", 0.7)

        # Perform search
        search_results = await self._search_similar(
            query_embedding,
            top_k=top_k,
            threshold=threshold,
            filters=filters
        )

        # Optional rerank if query text provided in filters (filters.get('query') or 'query_text')
        qtext = filters.get("query") or filters.get("query_text") if isinstance(filters, dict) else None
        if qtext:
            search_results = await self._maybe_rerank(qtext, search_results)

        return AgentMessage(
            type=MessageType.RETRIEVAL_RESULT,
            sender=self.agent_type,
            recipient=message.sender,
            content={
                "query_id": request_data["query_id"],
                "documents": search_results["documents"],
                "scores": search_results["scores"],
                "method": RetrievalMethod.SEMANTIC_SEARCH,
                "total_searched": len(self.document_metadata),
                "search_time": search_results["search_time"]
            },
            correlation_id=message.correlation_id
        )

    async def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for query, with caching."""
        # Check cache first
        if query in self.embedding_cache:
            return self.embedding_cache[query]

        # Generate embedding
        emb = await self._embed_texts([query])
        embedding_list = emb[0].astype(float).tolist()

        # Update cache
        if len(self.embedding_cache) < self.cache_size:
            self.embedding_cache[query] = embedding_list

        return embedding_list

    async def _search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar documents."""
        start_time = time.time()
        if query_embedding is None:
            raise ValueError("query_embedding is required for vector search")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.vector_index.ntotal == 0:
            return {"documents": [], "scores": [], "search_time": time.time() - start_time}

        # Convert to numpy array
        query_np = np.array([query_embedding], dtype=np.float32)

        # Search in FAISS index
        scores, indices = await asyncio.to_thread(self.vector_index.search, query_np, min(top_k, self.vector_index.ntotal))

        # Prepare results
        documents = []
        valid_scores = []

        for result_index, idx in enumerate(indices[0]):
            score = scores[0][result_index]
            if idx >= 0 and idx < len(self.document_metadata) and score >= threshold:
                doc_metadata = self.document_metadata[idx]

                # Apply filters
                if self._passes_filters(doc_metadata, filters):
                    # Convert back to PolicyDocument
                    doc = PolicyDocument(
                        id=doc_metadata["id"],
                        title=doc_metadata["title"],
                        content=doc_metadata["content"],
                        source=doc_metadata["source"],
                        doc_type=doc_metadata["doc_type"],
                        keywords=doc_metadata["keywords"],
                        regions=doc_metadata["regions"],
                        target_groups=doc_metadata["target_groups"]
                    )

                    documents.append(doc)
                    valid_scores.append(float(score))

        search_time = time.time() - start_time

        return {
            "documents": [doc.model_dump() for doc in documents],
            "scores": valid_scores,
            "search_time": search_time
        }

    async def _maybe_rerank(self, query_text: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """按配置在线程中重排并原地更新检索结果，replace 只留重排子集，fuse 对全部候选加权。

        每次创建的重排器负责关闭；未启用、无候选或重排失败时返回传入结果，不额外复制或保证事务回滚。
        """
        try:
            if os.getenv("KB_RERANK_ENABLED", "true").lower() != "true":
                return search_results
            if os.getenv("RERANKER_BACKEND", "").lower() != "dashscope":
                return search_results
            documents = search_results["documents"]
            if not documents:
                return search_results
            texts = [document["content"] for document in documents]
            def rerank_texts():
                reranker = Reranker()
                try:
                    return [(index, score) for index, score, _ in reranker.rerank(
                        query_text, texts,
                        top_n=min(len(texts), int(os.getenv("RERANKER_TOP_N", "5"))),
                    )]
                finally:
                    reranker.close()

            ranking = await asyncio.to_thread(rerank_texts)
            # strategy: replace | fuse
            strategy = os.getenv("RERANKER_STRATEGY", "replace").lower()
            idx_map = [idx for idx, score in ranking]
            rerank_scores = {idx: score for idx, score in ranking}
            if strategy == "fuse":
                faiss_scores = search_results["scores"]
                alpha = float(os.getenv("RERANK_WEIGHT", "0.7"))
                beta = float(os.getenv("FAISS_WEIGHT", "0.3"))
                fused = []
                for index in range(len(documents)):
                    # Only the selected top_n documents receive a rerank score.
                    rerank_score = rerank_scores.get(index, 0.0)
                    vector_score = faiss_scores[index]
                    fused.append((index, alpha * rerank_score + beta * vector_score))
                fused.sort(key=lambda scored_document: scored_document[1], reverse=True)
                idx_map = [i for i, _ in fused]
                new_scores = [s for _, s in fused]
            else:
                new_scores = [score for _, score in ranking]
            # reorder
            new_docs = [documents[index] for index in idx_map]
            search_results["documents"] = new_docs
            search_results["scores"] = new_scores
            return search_results
        except Exception as e:
            self.logger.warning(f"Reranker failed: {e}", exc_info=True)
            return search_results

    @staticmethod
    def _passes_filters(doc_metadata: Dict, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if document passes filters."""
        if not filters:
            return True

        # Check doc_type filter
        if "doc_type" in filters:
            if doc_metadata["doc_type"] != filters["doc_type"]:
                return False

        # Check source filter
        if "source" in filters:
            if filters["source"] not in doc_metadata["source"]:
                return False

        # Check region filter
        if "region" in filters:
            if filters["region"] not in doc_metadata["regions"]:
                return False

        # Check date range filter
        if "date_from" in filters or "date_to" in filters:
            if doc_metadata.get("effective_date"):
                eff_date = datetime.fromisoformat(doc_metadata["effective_date"])

                if "date_from" in filters:
                    date_from = datetime.fromisoformat(filters["date_from"])
                    if eff_date < date_from:
                        return False

                if "date_to" in filters:
                    date_to = datetime.fromisoformat(filters["date_to"])
                    if eff_date > date_to:
                        return False

        return True

    async def _handle_query_analysis(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle query analysis messages."""
        # Not needed for vector retriever
        return None

    async def process_request(self, request: RetrievalRequest, context: MessageContext) -> RetrievalResult:
        """Process a retrieval request."""
        if request.query_embedding is None:
            raise ValueError("query_embedding is required for vector search")
        search_results = await self._search_similar(
            request.query_embedding,
            request.top_k,
            request.threshold,
            request.filters
        )

        return RetrievalResult(
            query_id=request.query_id,
            documents=[PolicyDocument(**doc) for doc in search_results["documents"]],
            scores=search_results["scores"],
            method=RetrievalMethod.SEMANTIC_SEARCH,
            total_searched=len(self.document_metadata),
            search_time=search_results["search_time"]
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return {
            "total_documents": len(self.document_metadata),
            "index_size": self.vector_index.ntotal,
            "cache_size": len(self.embedding_cache),
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dim,
            "backend": self.embedding_backend,
        }

    async def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts using the configured backend. Returns np.ndarray (n, d), L2-normalized."""
        backend = self.embedding_backend
        if backend == "openai":
            return await self._embed_openai(texts)
        if backend == "ollama":
            return await self._embed_ollama(texts)
        raise ValueError(f"Unsupported embedding backend: {backend}")

    async def _embed_openai(self, texts: List[str]) -> np.ndarray:
        """使用本次请求拥有的异步客户端获取向量并校验维度，退出时关闭客户端。"""
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        model = self.model_name
        if not api_key:
            raise RuntimeError("未配置 LLM_API_KEY/OPENAI_API_KEY，无法使用 openai 嵌入后端")
        async with AsyncOpenAI(api_key=api_key, base_url=base_url) as client:
            res = await client.embeddings.create(model=model, input=texts)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        return self._prepare_embeddings(vecs)

    async def _embed_ollama(self, texts: List[str]) -> np.ndarray:
        # Ollama is an independently selected backend whose SDK is not a runtime requirement.
        """按显式选定的 Ollama 后端加载 SDK、生成向量并交给索引维度校验。"""
        from lightrag.llm.ollama import ollama_embed
        host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")
        model = self.model_name
        vecs = await ollama_embed(texts, embed_model=model, host=host)
        return self._prepare_embeddings(np.asarray(vecs, dtype=np.float32))

    def _prepare_embeddings(self, vecs: np.ndarray) -> np.ndarray:
        """Accept a discovered dimension only while the index is empty."""
        if vecs.ndim != 2:
            raise ValueError("Embedding response must be a two-dimensional array")
        if self.vector_index is None or self.vector_index.d != vecs.shape[1]:
            if self.vector_index is not None and self.vector_index.ntotal:
                raise ValueError("Embedding dimension differs from the populated vector index")
            self.embedding_dim = vecs.shape[1]
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
        return self._l2_normalize(vecs)

    @staticmethod
    def _l2_normalize(embs: np.ndarray) -> np.ndarray:
        """沿每行向量归一化并转为 float32，分母加微量值以允许零向量。"""
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
        return (embs / norms).astype(np.float32)

    @staticmethod
    def _infer_embedding_dim(backend: str, model: Optional[str]) -> int:
        b = (backend or "openai").lower()
        if b == "openai":
            if model and "3-large" in model:
                return 3072
            return 1536  # text-embedding-3-small 默认
        if b == "ollama":
            return int(os.getenv("EMBEDDING_DIM", "768"))
        return 768
