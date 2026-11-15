"""
Embedding manager for vector storage and retrieval (no torch dependency).

Supports backends:
- openai (default): OpenAI Embeddings API
- ollama: local embedding via lightrag.ollama
"""

import numpy as np
import pickle
import os
import asyncio
from pathlib import Path
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
        self.backend = (os.getenv("EMBEDDING_BACKEND", "openai") if backend is None else backend).lower()
        self.model_name: str = model_name if model_name is not None else os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        if self.backend not in {"openai", "ollama"}:
            raise ValueError(f"Unsupported embedding backend: {self.backend}")
        self.embedding_dim = self._infer_dim() if embedding_dim is None else embedding_dim
        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim must be positive")
        self.index_path = "data/embeddings/faiss_index.bin" if index_path is None else index_path
        self.metadata_path = str(Path(index_path).with_suffix(".metadata.pkl")) if index_path is not None else "data/embeddings/metadata.pkl"

        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.documents_metadata: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        """Load a persisted index when present; otherwise keep the empty index."""
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as metadata_file:
                self.documents_metadata = pickle.load(metadata_file)

    def encode_documents(self, documents: List[str]) -> np.ndarray:
        """Encode documents to embeddings."""
        if self.backend == "openai":
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            if not api_key:
                raise RuntimeError("OPENAI API Key 未配置，无法使用 openai 嵌入后端")
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            with client:
                response = client.embeddings.create(model=self.model_name, input=documents)
                return np.array([item.embedding for item in response.data], dtype=np.float32)
        if self.backend == "ollama":
            from lightrag.llm.ollama import ollama_embed
            host = os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434")
            model = self.model_name
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                embeddings = asyncio.run(ollama_embed(documents, embed_model=model, host=host))
            else:
                raise RuntimeError("Synchronous Ollama encoding must run in a worker thread")
            return np.array(embeddings, dtype=np.float32)
        raise ValueError(f"Unsupported embedding backend: {self.backend}")

    def add_documents(
        self,
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ):
        """Add documents to the index."""
        if len(documents) != len(metadata):
            raise ValueError("documents and metadata must have equal length")
        if not documents:
            return
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
        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        if top_k == 0:
            return [], []
        # Encode query
        query_embedding = self.encode_documents([query])
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.index.search(query_embedding, top_k)

        # Filter by threshold
        results = []
        valid_scores = []

        for score, idx in zip(scores[0], indices[0], strict=True):
            if score >= threshold and 0 <= idx < len(self.documents_metadata):
                results.append(self.documents_metadata[idx])
                valid_scores.append(float(score))

        return results, valid_scores

    def _save_index(self):
        """Save index and metadata to disk."""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as metadata_file:
            pickle.dump(self.documents_metadata, metadata_file)

    def rebuild_index(self, documents: List[str], metadata: List[Dict[str, Any]]):
        """Rebuild the entire index."""
        if len(documents) != len(metadata):
            raise ValueError("documents and metadata must have the same length")
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.documents_metadata = []
        self.add_documents(documents, metadata)

    def _infer_dim(self) -> int:
        if self.backend == "openai":
            # text-embedding-3-small 默认 1536
            if "3-large" in self.model_name:
                return 3072
            return 1536
        return int(os.getenv("EMBEDDING_DIM", "768"))
