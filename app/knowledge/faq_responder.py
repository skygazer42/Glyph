"""Lightweight FAQ matcher that short-circuits common queries."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from app.models.base import FinalAnswer


logger = logging.getLogger(__name__)


@dataclass
class FAQEntry:
    question: str
    answer: str
    tags: List[str]
    source: str


class FAQResponder:
    """Simple FAQ matcher that returns canned answers for high-frequency queries."""

    def __init__(
        self,
        data_path: str = "resources/faq/qa_pairs.json",
        *,
        threshold: float = 0.88,
        max_candidates: int = 1,
    ) -> None:
        self.data_path = Path(data_path)
        self.threshold = threshold
        self.max_candidates = max(1, max_candidates)
        self.entries: List[FAQEntry] = []
        self._load_entries()

    def _load_entries(self) -> None:
        if not self.data_path.exists():
            logger.warning("FAQResponder 找不到数据文件：%s", self.data_path)
            return
        try:
            raw = json.loads(self.data_path.read_text(encoding="utf-8"))
            self.entries = [
                FAQEntry(
                    question=item.get("question", "").strip(),
                    answer=item.get("answer", "").strip(),
                    tags=item.get("tags", []),
                    source=item.get("source", ""),
                )
                for item in raw
                if item.get("question") and item.get("answer")
            ]
            logger.info("FAQResponder loaded %s entries from %s", len(self.entries), self.data_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("FAQResponder 载入失败：%s", exc)
            self.entries = []

    def maybe_answer(self, query: str) -> Optional[FinalAnswer]:
        if not query or not self.entries:
            return None

        match = self._best_match(query)
        if not match:
            return None

        entry, score = match
        return FinalAnswer(
            query_id=uuid4(),
            answer=entry.answer,
            sources=[],
            confidence=round(score, 3),
            verification_passed=True,
            metadata={
                "route": "faq_cache",
                "faq_question": entry.question,
                "faq_source": entry.source,
                "similarity": score,
                "tags": entry.tags,
            },
            total_processing_time=0.0,
        )

    def _best_match(self, query: str) -> Optional[Tuple[FAQEntry, float]]:
        """Return the best FAQ entry whose similarity passes the threshold."""
        normalized_query = query.strip().lower()
        best: Tuple[Optional[FAQEntry], float] = (None, 0.0)
        for entry in self.entries:
            candidate = entry.question.lower()
            score = SequenceMatcher(None, normalized_query, candidate).ratio()
            if score > best[1]:
                best = (entry, score)
        if best[0] and best[1] >= self.threshold:
            return best  # type: ignore[return-value]
        return None


__all__ = ["FAQResponder"]
