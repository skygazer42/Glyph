"""
Vector store for document embeddings and similarity search.
"""

import os
import numpy as np
import pickle
import faiss
from typing import List, Dict, Any, Tuple, Optional
from sentence_transformers import SentenceTransformer

from ..agents.base.types import PolicyDocument


class VectorStore:
    """Vector database for storing and retrieving policy documents."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_path: str = "data/vector_store/faiss.index",
        metadata_path: str = "data/vector_store/metadata.pkl"
    ):
        """Initialize the vector store."""
        self.model = SentenceTransformer(model_name)
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

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
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True
        )

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