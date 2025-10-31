"""
Vector-based retrieval agent implementation.
"""

import asyncio
import numpy as np
from typing import List, Dict, Any, Optional
import time

from autogen_core import MessageContext, TopicId
from sentence_transformers import SentenceTransformer
import faiss

from ...models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    UserQuery,
    QueryAnalysis,
    RetrievalRequest,
    RetrievalResult,
    PolicyDocument,
    RetrievalMethod
)
from ..base.base_agent import StatefulAgent


class VectorRetrieverAgent(StatefulAgent):
    """Vector-based policy document retrieval agent."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        index_path: str = "data/vector_store/policy_index.faiss",
        metadata_path: str = "data/vector_store/metadata.pkl",
        embedding_dim: int = 1024,
        **kwargs
    ):
        """Initialize the vector retriever agent."""
        super().__init__(
            agent_type=AgentType.POLICY_RETRIEVER,
            name="VectorRetriever",
            description="负责基于向量相似度的政策文档检索",
            **kwargs
        )

        self.model_name = model_name
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_dim = embedding_dim

        # Initialize components
        self.embedding_model = None
        self.vector_index = None
        self.document_metadata: List[Dict] = []
        self._load_or_create_index()

        # Cache for query embeddings
        self.embedding_cache: Dict[str, List[float]] = {}
        self.cache_size = 1000

    async def initialize(self):
        """Initialize the agent and load models."""
        self.logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer(self.model_name)
        self.logger.info(f"Model loaded: {self.model_name}")

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
            self.vector_index = faiss.IndexFlatIP(self.embedding_dim)
            self.document_metadata = []
            self.logger.info("Created new vector index")

    async def add_documents(self, documents: List[PolicyDocument]):
        """Add documents to the vector store."""
        if not self.embedding_model:
            await self.initialize()

        self.logger.info(f"Adding {len(documents)} documents to vector store")

        # Prepare texts for embedding
        texts = []
        for doc in documents:
            # Combine title, content, and keywords for better retrieval
            text = f"{doc.title} {doc.content} {' '.join(doc.keywords)}"
            texts.append(text)

        # Generate embeddings in batches
        batch_size = 32
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            embeddings = self.embedding_model.encode(
                batch_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True
            )
            all_embeddings.append(embeddings)

        # Concatenate all embeddings
        all_embeddings = np.vstack(all_embeddings)

        # Add to index
        self.vector_index.add(all_embeddings)

        # Store metadata
        for doc in documents:
            self.document_metadata.append({
                "id": str(doc.id),
                "title": doc.title,
                "content": doc.content[:500],  # Store summary
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
        if not self.embedding_model:
            await self.initialize()

        embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        embedding_list = embedding.tolist()

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
            "embedding_dimension": self.embedding_dim
        }