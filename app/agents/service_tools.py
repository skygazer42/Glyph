"""Helper utilities used by AgentService and pipeline agents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.agents.framework.base.types import PolicyDocument
from app.agents.packs.intent_router.utils import LLMIntentClassifier
from app.knowledge.service import KnowledgeService


class IntentDetectionTool:
    """Lightweight wrapper around the intent router classifier."""

    def __init__(self, classifier: LLMIntentClassifier | None = None) -> None:
        self.classifier = classifier or LLMIntentClassifier()

    async def detect(self, query: str) -> Dict[str, Any]:
        result = await self.classifier.classify(query)
        if result:
            return result
        # 默认兜底意图
        return {
            "intent": "policy_inquiry",
            "confidence": 0.3,
            "processing_chain": [
                "knowledge_retriever",
                "policy_analyzer",
                "answer_generator",
            ],
            "chains": ["kb_chain"],
        }


class KnowledgeTool:
    """Async facade sitting on top of KnowledgeService."""

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
        return await self.service.search(
            query, top_k=top_k, threshold=threshold, filters=filters
        )


__all__ = ["IntentDetectionTool", "KnowledgeTool"]
