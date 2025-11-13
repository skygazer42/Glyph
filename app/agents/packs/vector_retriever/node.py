"""
Vector-based retrieval agent (no torch dependency).

Supported embedding backends:
- openai (default): OpenAI Embeddings API（轻量）
- ollama: 本地 Ollama 嵌入服务
"""

import os
import numpy as np
from typing import List, Dict, Any, Optional
import time

from autogen_core import MessageContext
import faiss

from app.models.base import (
    AgentType,
   MessageType,
   AgentMessage,
   RetrievalRequest,
   RetrievalResult,
   PolicyDocument,
   RetrievalMethod
)
from app.agents.framework.base.base_agent import StatefulAgent


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
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_dim = embedding_dim or self._infer_embedding_dim(self.embedding_backend, self.model_name)

        # Initialize components
        self.embedding_model = None  # backends无需预加载
        self.vector_index = None
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
        import os
        import pickle

        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # Load existing index
            self.vector_index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.document_metadata = pickle.load(f)
            self.logger.info(f"Loaded index with {len(self.document_metadata)} documents")
        else:
            # Create new index
            if not self.embedding_dim:
                self.embedding_dim = self._infer_embedding_dim(self.embedding_backend, self.model_name)
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
            self.document_metadata = []
            self.logger.info("Created new vector index")

    async def add_documents(self, documents: List[PolicyDocument]):
        """Add documents to the vector store."""
        self.logger.info(f"Adding {len(documents)} documents to vector store")

        # Prepare texts for embedding
        texts = []
        for doc in documents:
            # Combine title, content, and keywords for better retrieval
            text = f"{doc.title} {doc.content} {' '.join(doc.keywords)}"
            texts.append(text)

        # Generate embeddings via backend
        all_embeddings = await self._embed_texts(texts)

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
        import pickle

        faiss.write_index(self.vector_index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.document_metadata, f)

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages."""
        query_data = message.content
        query = query_data.get("text", "")

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
                "query_id": str(query_data.get("id", "")),
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
                "query_id": request_data.get("query_id", ""),
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

        # Convert to numpy array
        query_np = np.array([query_embedding], dtype=np.float32)

        # Search in FAISS index
        scores, indices = self.vector_index.search(query_np, min(top_k, self.vector_index.ntotal))

        # Prepare results
        documents = []
        valid_scores = []

        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.document_metadata) and score >= threshold:
                doc_metadata = self.document_metadata[idx]

                # Apply filters
                if await self._passes_filters(doc_metadata, filters):
                    # Convert back to PolicyDocument
                    doc = PolicyDocument(
                        id=doc_metadata["id"],
                        title=doc_metadata["title"],
                        content=doc_metadata["content"],
                        source=doc_metadata["source"],
                        doc_type=doc_metadata["doc_type"],
                        keywords=doc_metadata.get("keywords", []),
                        regions=doc_metadata.get("regions", []),
                        target_groups=doc_metadata.get("target_groups", [])
                    )

                    documents.append(doc)
                    valid_scores.append(float(score))

        search_time = time.time() - start_time

        return {
            "documents": [doc.dict() for doc in documents],
            "scores": valid_scores,
            "search_time": search_time
        }

    async def _maybe_rerank(self, query_text: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if os.getenv("KB_RERANK_ENABLED", "true").lower() != "true":
                return search_results
            if os.getenv("RERANKER_BACKEND", "").lower() != "dashscope":
                return search_results
            from app.knowledge.reranker.dashscope import reorder_by_rerank
            docs = search_results.get("documents", [])
            if not docs:
                return search_results
            # extract full content or fallback to title
            texts = []
            for d in docs:
                # d is dict from PolicyDocument.dict()
                texts.append(d.get("content") or d.get("title") or "")
            ranking = reorder_by_rerank(query_text, texts, top_n=min(len(texts), int(os.getenv("RERANKER_TOP_N", "5"))))
            # strategy: replace | fuse
            strategy = os.getenv("RERANKER_STRATEGY", "replace").lower()
            idx_map = [idx for idx, score in ranking]
            rerank_scores = {idx: score for idx, score in ranking}
            if strategy == "fuse":
                faiss_scores = search_results.get("scores", [0.0] * len(docs))
                alpha = float(os.getenv("RERANK_WEIGHT", "0.7"))
                beta = float(os.getenv("FAISS_WEIGHT", "0.3"))
                fused = []
                for i in range(len(docs)):
                    rr = rerank_scores.get(i, 0.0)
                    fs = faiss_scores[i] if i < len(faiss_scores) else 0.0
                    fused.append((i, alpha * rr + beta * fs))
                fused.sort(key=lambda x: x[1], reverse=True)
                idx_map = [i for i, _ in fused]
                new_scores = [s for _, s in fused]
            else:
                new_scores = [score for _, score in ranking]
            # reorder
            new_docs = [docs[i] for i in idx_map]
            search_results["documents"] = new_docs
            search_results["scores"] = new_scores
            return search_results
        except Exception as e:
            self.logger.warning(f"Reranker failed: {e}")
            return search_results

    async def _passes_filters(self, doc_metadata: Dict, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if document passes filters."""
        if not filters:
            return True

        # Check doc_type filter
        if "doc_type" in filters:
            if doc_metadata.get("doc_type") != filters["doc_type"]:
                return False

        # Check source filter
        if "source" in filters:
            if filters["source"] not in doc_metadata.get("source", ""):
                return False

        # Check region filter
        if "region" in filters:
            if filters["region"] not in doc_metadata.get("regions", []):
                return False

        # Check date range filter
        if "date_from" in filters or "date_to" in filters:
            if doc_metadata.get("effective_date"):
                from datetime import datetime
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
            "index_size": self.vector_index.ntotal if self.vector_index else 0,
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
        # Fallback zeros
        self.logger.warning(f"Unknown embedding backend '{backend}', using zeros")
        return self._l2_normalize(np.zeros((len(texts), self.embedding_dim), dtype=np.float32))

    async def _embed_openai(self, texts: List[str]) -> np.ndarray:
        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError("openai 包未安装，无法使用 openai 嵌入后端") from e
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        model = self.model_name or "text-embedding-3-small"
        if not api_key:
            raise RuntimeError("未配置 LLM_API_KEY/OPENAI_API_KEY，无法使用 openai 嵌入后端")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        res = client.embeddings.create(model=model, input=texts)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        # ensure index dim
        if self.vector_index is None or self.vector_index.d != vecs.shape[1]:
            self.embedding_dim = vecs.shape[1]
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
        return self._l2_normalize(vecs)

    async def _embed_ollama(self, texts: List[str]) -> np.ndarray:
        try:
            from lightrag.llm.ollama import ollama_embed
        except Exception as e:
            raise RuntimeError("需要安装 lightrag 以使用 ollama 嵌入后端") from e
        host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")
        model = self.model_name or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        vecs = ollama_embed(texts, embed_model=model, host=host)
        if isinstance(vecs, list):
            vecs = np.array(vecs, dtype=np.float32)
        if self.vector_index is None or self.vector_index.d != vecs.shape[1]:
            self.embedding_dim = vecs.shape[1]
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
        return self._l2_normalize(vecs)

    @staticmethod
    def _l2_normalize(embs: np.ndarray) -> np.ndarray:
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
