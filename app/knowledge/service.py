"""High-level service that wraps vector/graph knowledge operations."""

from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Tuple

import anyio
from loguru import logger

from app.config.app_config import settings
from app.knowledge.milvus import MilvusStore
from app.knowledge.llamaindex_integration import LlamaIndexIntegration
from app.models.policy import PolicyDocument


class KnowledgeService:
    """Gateway for ingesting and querying knowledge assets."""

    def __init__(
        self,
        vector_store: Optional[MilvusStore] = None,
        *,
        use_hierarchical: Optional[bool] = None,
        hierarchical_storage: Optional[str] = None,
    ) -> None:
        self._owns_vector_store = vector_store is None
        self.vector_store = MilvusStore() if vector_store is None else vector_store
        resolved_flag = (
            use_hierarchical
            if use_hierarchical is not None
            else settings.system.hybrid_retrieval_enabled
        )
        self.hierarchical_store: Optional[LlamaIndexIntegration] = None
        self._last_timings: ContextVar[Dict[str, Any]] = ContextVar("knowledge_timings")
        if resolved_flag:
            storage_dir = settings.llamaindex.storage_dir if hierarchical_storage is None else hierarchical_storage
            try:
                self.hierarchical_store = LlamaIndexIntegration(storage_dir)
            except BaseException:
                if self._owns_vector_store:
                    self.vector_store.close()
                raise
            logger.info("KnowledgeService: hierarchical index enabled at {}", storage_dir)

    @property
    def last_timings(self) -> Dict[str, Any]:
        """Timings for the most recent search in the current caller's context."""
        return dict(self._last_timings.get({}))

    async def index_documents(self, documents: List[PolicyDocument]) -> int:
        """依次写入向量库及可选分级索引，返回输入文档数；后续失败不会回滚已完成的写入。"""
        if not documents:
            return 0
        await asyncio.to_thread(self.vector_store.add_documents, documents)
        if self.hierarchical_store:
            await self.hierarchical_store.build_index_from_documents(documents)
            logger.info("KnowledgeService: hierarchical index refreshed with {} docs", len(documents))
        return len(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """合并满足阈值的检索结果并按文档 ID 保留最高分，返回等长文档与分数列表；零数量返回两个空列表。"""
        if top_k < 0:
            raise ValueError("top_k must not be negative")
        self._last_timings.set({})
        if top_k == 0:
            return [], []
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
            doc_id = str(doc.id)
            previous = combined.get(doc_id)
            if previous is None or score > previous[1]:
                combined[doc_id] = (doc.model_copy(update={"retrieval_origin": origin}), float(score))

        # 1. 尝试使用分级索引
        has_vector_filters = bool(filters and {"doc_type", "source", "title", "coverage_year", "content"}.intersection(filters))
        # Hierarchical nodes do not retain the fields needed for Milvus filters.
        if self.hierarchical_store and self.hierarchical_store.has_index and not has_vector_filters:
            t_h = time.perf_counter()
            h_docs, h_scores = await self.hierarchical_store.search(
                query, top_k=top_k * 2, threshold=threshold
            )
            if len(h_docs) != len(h_scores):
                raise ValueError("Hierarchical documents and scores have different lengths")
            for index, doc in enumerate(h_docs):
                _upsert(doc, h_scores[index], "hierarchical_index")
            timings["hierarchical_ms"] = round(
                (time.perf_counter() - t_h) * 1000, 2
            )

        # 2. 向量检索兜底
        t_v = time.perf_counter()
        v_docs, v_scores = await asyncio.to_thread(
            self.vector_store.search,
            query=query,
            top_k=top_k * 2,
            threshold=threshold,
            filters=filters,
        )
        if len(v_docs) != len(v_scores):
            raise ValueError("Vector documents and scores have different lengths")
        for index, doc in enumerate(v_docs):
            _upsert(doc, v_scores[index], "knowledge_base")
        timings["vector_ms"] = round((time.perf_counter() - t_v) * 1000, 2)

        if not combined:
            timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            self._last_timings.set(timings)
            return [], []

        t_sort = time.perf_counter()
        sorted_results = sorted(
            combined.values(), key=lambda item: item[1], reverse=True
        )[:top_k]
        docs = [item[0] for item in sorted_results]
        scores = [item[1] for item in sorted_results]
        timings["combine_ms"] = round((time.perf_counter() - t_sort) * 1000, 2)
        timings["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
        self._last_timings.set(timings)
        return docs, scores

    async def close(self) -> None:
        """限时关闭分级检索资源，并在 finally 中关闭自建向量库；借入向量库仍由调用方管理。"""
        try:
            if self.hierarchical_store is not None:
                with anyio.fail_after(5, shield=True):
                    await self.hierarchical_store.close()
        finally:
            if self._owns_vector_store:
                with anyio.fail_after(5, shield=True):
                    await anyio.to_thread.run_sync(self.vector_store.close, abandon_on_cancel=True)


__all__ = ["KnowledgeService"]
