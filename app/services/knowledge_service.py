"""High-level service that wraps vector/graph knowledge operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.knowledge.milvus import MilvusStore
from app.agents.base.types import PolicyDocument


class KnowledgeService:
    """Gateway for ingesting and querying knowledge assets."""

    def __init__(
        self,
        vector_store: Optional[MilvusStore] = None,
    ) -> None:
        self.vector_store = vector_store or MilvusStore()

    async def index_documents(self, documents: List[PolicyDocument]) -> int:
        if not documents:
            return 0
        self.vector_store.add_documents(documents)
        return len(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return self.vector_store.search(
            query=query,
            top_k=top_k,
            threshold=threshold,
            filters=filters,
        )


__all__ = ["KnowledgeService"]
