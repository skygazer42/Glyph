"""
Vector store for document embeddings and similarity search (no torch dependency).

Supports backends:
- openai (default): OpenAI Embeddings API
- ollama: local embedding via lightrag.ollama
"""

import os
import numpy as np
import pickle
import faiss
from typing import List, Dict, Any, Tuple, Optional

from ..agents.base.types import PolicyDocument


class VectorStore:
    """Vector database for storing and retrieving policy documents."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        index_path: str = "data/vector_store/faiss.index",
        metadata_path: str = "data/vector_store/metadata.pkl",
        backend: Optional[str] = None
    ):
        """Initialize the vector store."""
        from config.settings import settings

        # 使用 settings.embedding 配置
        self.backend = (backend or settings.embedding.backend).lower()
        self.model_name = model_name or self._get_model_name_from_backend(settings)
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_dim = self._infer_dim()

        # Create directories if they don't exist
        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        # Initialize or load index
        self.index = None
        self.metadata = []
        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load existing index or create a new one."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            # Create a new index
            self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
            self.metadata = []

    def add_documents(self, documents: List[PolicyDocument]):
        """Add documents to the vector store."""
        if not documents:
            return

        # Prepare texts for embedding
        texts = []
        for doc in documents:
            # Combine title and content for better search
            text = f"{doc.title} {doc.content}"
            texts.append(text)

        # Generate embeddings
        embeddings = self._embed_texts(texts)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)

        # Store metadata
        self.metadata.extend([doc.__dict__ for doc in documents])

        # Save to disk
        self._save()

    async def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """Search for similar documents."""
        if self.index.ntotal == 0:
            return [], []

        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))

        # Prepare results
        documents = []
        valid_scores = []

        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata):
                doc_data = self.metadata[idx]
                doc = PolicyDocument(**doc_data)

                # Apply filters if provided
                if self._passes_filters(doc, filters):
                    documents.append(doc)
                    valid_scores.append(float(score))

        return documents, valid_scores

    def _passes_filters(self, doc: PolicyDocument, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if document passes the provided filters."""
        if not filters:
            return True

        # Check document type filter
        if "doc_type" in filters and doc.doc_type != filters["doc_type"]:
            return False

        # Check source filter
        if "source" in filters and filters["source"] not in doc.source:
            return False

        # Check policy type filter
        if "policy_type" in filters and doc.policy_type != filters["policy_type"]:
            return False

        return True

    def _save(self):
        """Save index and metadata to disk."""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)

    def clear(self):
        """Clear all documents from the store."""
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.metadata = []
        self._save()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        return {
            "total_documents": len(self.metadata),
            "index_size": self.index.ntotal,
            "embedding_dimension": self.embedding_dim,
            "index_path": self.index_path
        }

    def _get_model_name_from_backend(self, settings) -> str:
        """根据后端获取模型名称"""
        if self.backend == "openai":
            return settings.embedding.openai_model
        elif self.backend == "dashscope":
            return settings.embedding.dashscope_model
        return "text-embedding-3-small"

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        from config.settings import settings

        if self.backend == "openai":
            from openai import OpenAI
            # 使用 settings.embedding 配置
            api_key = settings.embedding.openai_api_key or os.getenv("LLM_API_KEY")
            base_url = settings.embedding.openai_base_url
            if not api_key:
                raise RuntimeError("OPENAI API Key 未配置，无法使用 openai 嵌入后端")
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            res = client.embeddings.create(model=self.model_name, input=texts)
            vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
            # ensure index dim
            if self.index is None or self.index.d != vecs.shape[1]:
                self.embedding_dim = vecs.shape[1]
                self.index = faiss.IndexFlatIP(self.embedding_dim)
            faiss.normalize_L2(vecs)
            return vecs
        elif self.backend == "dashscope":
            import requests
            api_key = settings.embedding.dashscope_api_key
            if not api_key:
                raise RuntimeError("DashScope API Key 未配置")

            url = settings.embedding.dashscope_base_url
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            all_vecs = []
            for text in texts:
                data = {
                    "model": self.model_name,
                    "input": {"texts": [text]}
                }
                # 添加可选参数
                parameters = {}
                if settings.embedding.dashscope_dimension:
                    parameters["dimension"] = settings.embedding.dashscope_dimension
                if settings.embedding.dashscope_output_type:
                    parameters["output_type"] = settings.embedding.dashscope_output_type
                if parameters:
                    data["parameters"] = parameters

                response = requests.post(url, headers=headers, json=data, timeout=settings.embedding.timeout)
                response.raise_for_status()
                result = response.json()
                embedding = result["output"]["embeddings"][0]["embedding"]
                all_vecs.append(embedding)

            vecs = np.array(all_vecs, dtype=np.float32)
            if self.index is None or self.index.d != vecs.shape[1]:
                self.embedding_dim = vecs.shape[1]
                self.index = faiss.IndexFlatIP(self.embedding_dim)
            faiss.normalize_L2(vecs)
            return vecs
        else:
            raise ValueError(f"Unsupported backend: {self.backend}. Supported: openai, dashscope")

    def _infer_dim(self) -> int:
        from config.settings import settings

        if self.backend == "openai":
            if "3-large" in (self.model_name or ""):
                return 3072
            return 1536
        if self.backend == "ollama":
            return settings.embedding.dimension
        return settings.embedding.dimension
