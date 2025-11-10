"""
Embedding manager for vector storage and retrieval (no torch dependency).

Supports backends:
- openai (default): OpenAI Embeddings API
- ollama: local embedding via lightrag.ollama
"""

import numpy as np
import pickle
import os
from typing import List, Dict, Any, Optional
import faiss
from openai import OpenAI


class EmbeddingManager:
    """Manages embeddings for policy documents."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        index_path: Optional[str] = None,
        backend: Optional[str] = None,
    ):
        """Initialize the embedding manager."""
        self.backend = (backend or os.getenv("EMBEDDING_BACKEND") or "openai").lower()
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dim = embedding_dim or self._infer_dim()
        self.index_path = index_path or "data/embeddings/faiss_index.bin"
        self.metadata_path = index_path or "data/embeddings/metadata.pkl"

        self.index = None
        self.documents_metadata = []
        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load existing index or create a new one."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.documents_metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.embedding_dim)

    def encode_documents(self, documents: List[str]) -> np.ndarray:
        """Encode documents to embeddings."""
        if self.backend == "openai":
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            if not api_key:
                raise RuntimeError("OPENAI API Key 未配置，无法使用 openai 嵌入后端")
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            res = client.embeddings.create(model=self.model_name, input=documents)
            vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
            return vecs
        if self.backend == "ollama":
            try:
                from lightrag.llm.ollama import ollama_embed
            except Exception as e:
                raise RuntimeError("需要安装 lightrag 以使用 ollama 嵌入后端") from e
            host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")
            model = self.model_name
            vecs = ollama_embed(documents, embed_model=model, host=host)
            return np.array(vecs, dtype=np.float32)
        # fallback zeros
        return np.zeros((len(documents), self.embedding_dim), dtype=np.float32)

    def add_documents(
        self,
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ):
        """Add documents to the index."""
        embeddings = self.encode_documents(documents)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)

        # Store metadata
        self.documents_metadata.extend(metadata)

        # Save to disk
        self._save_index()

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.7
    ) -> tuple[List[Dict], List[float]]:
        """Search for similar documents."""
        # Encode query
        query_embedding = self.encode_documents([query])
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.index.search(query_embedding, top_k)

        # Filter by threshold
        results = []
        valid_scores = []

        for score, idx in zip(scores[0], indices[0]):
            if score >= threshold and idx < len(self.documents_metadata):
                results.append(self.documents_metadata[idx])
                valid_scores.append(float(score))

        return results, valid_scores

    def _save_index(self):
        """Save index and metadata to disk."""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.documents_metadata, f)

    def rebuild_index(self, documents: List[str], metadata: List[Dict[str, Any]]):
        """Rebuild the entire index."""
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.documents_metadata = []
        self.add_documents(documents, metadata)

    def _infer_dim(self) -> int:
        b = self.backend
        if b == "openai":
            # text-embedding-3-small 默认 1536
            if "3-large" in (self.model_name or ""):
                return 3072
            return 1536
        if b == "ollama":
            return int(os.getenv("EMBEDDING_DIM", "768"))
        return 768
