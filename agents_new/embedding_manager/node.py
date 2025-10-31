"""
Embedding manager for vector storage and retrieval.
"""

import numpy as np
import pickle
import os
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import faiss


class EmbeddingManager:
    """Manages embeddings for policy documents."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        index_path: Optional[str] = None
    ):
        """Initialize the embedding manager."""
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = embedding_dim
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
        return self.model.encode(
            documents,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True
        )

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
        query_embedding = self.model.encode([query])
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