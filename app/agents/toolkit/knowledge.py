"""Knowledge-base helper built on top of the Milvus store service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.agents.base.types import PolicyDocument
from app.services.knowledge_service import KnowledgeService


class KnowledgeTool:
    def __init__(self, service: KnowledgeService | None = None) -> None:
        self._service = service

    @property
    def service(self) -> KnowledgeService:
        if self._service is None:
            self._service = KnowledgeService()
        return self._service

    async def ingest(self, documents: List[PolicyDocument]) -> int:
        return await self.service.index_documents(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return await self.service.search(query, top_k=top_k, threshold=threshold, filters=filters)


__all__ = ["KnowledgeTool"]
