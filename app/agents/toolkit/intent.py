"""Lightweight intent-detection tool used by the agent service."""

from __future__ import annotations

from typing import Any, Dict

from app.agents.router.llm_classifier import LLMIntentClassifier


class IntentDetectionTool:
    def __init__(self, classifier: LLMIntentClassifier | None = None) -> None:
        self.classifier = classifier or LLMIntentClassifier()

    async def detect(self, query: str) -> Dict[str, Any]:
        result = await self.classifier.classify(query)
        if result:
            return result
        # Fallback意图
        return {
            "intent": "policy_inquiry",
            "confidence": 0.3,
            "processing_chain": ["knowledge_retriever", "policy_analyzer", "answer_generator"],
        }


__all__ = ["IntentDetectionTool"]
