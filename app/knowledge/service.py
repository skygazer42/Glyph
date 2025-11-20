"""High-level service that wraps vector/graph knowledge operations."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.config import settings
from app.knowledge.milvus import MilvusStore
from app.knowledge.llamaindex_integration import LlamaIndexIntegration
from app.agents.framework.base.types import PolicyDocument


class KnowledgeService:
    """Gateway for ingesting and querying knowledge assets."""

    def __init__(
        self,
        vector_store: Optional[MilvusStore] = None,
        *,
        use_hierarchical: Optional[bool] = None,
        hierarchical_storage: Optional[str] = None,
    ) -> None:
        self.vector_store = vector_store or MilvusStore()
        resolved_flag = (
            use_hierarchical
            if use_hierarchical is not None
            else settings.system.hybrid_retrieval_enabled
        )
        self.hierarchical_store: Optional[LlamaIndexIntegration] = None
        self.last_timings: Dict[str, Any] = {}
        if resolved_flag:
            storage_dir = hierarchical_storage or settings.llamaindex.storage_dir
            try:
                self.hierarchical_store = LlamaIndexIntegration(storage_dir)
                logger.info(
                    "KnowledgeService: hierarchical index enabled at %s",
                    storage_dir,
                )
            except Exception as exc:
                logger.warning(
                    "KnowledgeService: failed to initialize hierarchical index (%s). "
                    "Fallback to vector-only retrieval.",
                    exc,
                )
                self.hierarchical_store = None

    async def index_documents(self, documents: List[PolicyDocument]) -> int:
        if not documents:
            return 0
        self.vector_store.add_documents(documents)
        if self.hierarchical_store:
            try:
                await self.hierarchical_store.build_index_from_documents(documents)
                logger.info("KnowledgeService: hierarchical index refreshed with %s docs", len(documents))
            except Exception as exc:
                logger.warning("KnowledgeService: hierarchical index rebuild failed: %s", exc)
        return len(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        timings: Dict[str, Optional[float]] = {
            "hierarchical_ms": None,
            "vector_ms": None,
            "combine_ms": None,
            "total_ms": None,
        }
        t_total = time.perf_counter()
        combined: Dict[str, Tuple[PolicyDocument, float]] = {}

        def _upsert(doc: PolicyDocument, score: float, origin: str) -> None:
            if score < threshold:
                return
            doc_id = getattr(doc, "id", None) or doc.title or str(hash(doc))
            setattr(doc, "retrieval_origin", origin)
            previous = combined.get(doc_id)
            if previous is None or score > previous[1]:
                combined[doc_id] = (doc, float(score))

        # 1. 尝试使用分级索引
        if self.hierarchical_store and self.hierarchical_store.has_index:
            t_h = time.perf_counter()
            try:
                h_docs, h_scores = await self.hierarchical_store.search(
                    query, top_k=top_k * 2, threshold=threshold
                )
                for doc, score in zip(h_docs, h_scores):
                    _upsert(doc, score, "hierarchical_index")
            except Exception as exc:
                logger.warning("Hierarchical search failed: %s", exc)
            timings["hierarchical_ms"] = round(
                (time.perf_counter() - t_h) * 1000, 2
            )

        # 2. 向量检索兜底
        t_v = time.perf_counter()
        v_docs, v_scores = self.vector_store.search(
            query=query,
            top_k=top_k * 2,
            threshold=threshold,
            filters=filters,
        )
        for doc, score in zip(v_docs, v_scores):
            _upsert(doc, score, "knowledge_base")
        timings["vector_ms"] = round((time.perf_counter() - t_v) * 1000, 2)

        if not combined:
            timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            self.last_timings = timings
            return [], []

        t_sort = time.perf_counter()
        sorted_results = sorted(
            combined.values(), key=lambda item: item[1], reverse=True
        )[:top_k]
        docs = [item[0] for item in sorted_results]
        scores = [item[1] for item in sorted_results]
        timings["combine_ms"] = round((time.perf_counter() - t_sort) * 1000, 2)
        timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
        self.last_timings = timings
        return docs, scores


__all__ = ["KnowledgeService"]
