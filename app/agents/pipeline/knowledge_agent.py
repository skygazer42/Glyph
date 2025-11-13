"""Knowledge retrieval + synthesis agent built on KnowledgeService."""

from __future__ import annotations

import asyncio
import logging
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from autogen_core.models import UserMessage

from app.agents.service.tools import KnowledgeTool, WebSearchTool
from app.core.llms import model_client
from app.models.base import FinalAnswer, PolicyDocument, PolicyType


class KnowledgeAgent:
    """Wraps KnowledgeTool and LLM summarization to answer policy inquiries."""

    def __init__(
        self,
        knowledge_tool: KnowledgeTool,
        top_k: int = 5,
        web_search_tool: WebSearchTool | None = None,
    ) -> None:
        self.tool = knowledge_tool
        self.top_k = top_k
        self.web_tool = web_search_tool
        self.logger = logging.getLogger(__name__)

    async def answer(
        self,
        query: str,
        *,
        intent: Optional[Dict[str, Any]] = None,
        emphasis: Optional[str] = None,
    ) -> FinalAnswer:
        docs, scores = await self._safe_search(query)
        focus = emphasis or (intent or {}).get("sub_intent") or "general"

        if docs:
            doc_origins = [
                getattr(doc, "retrieval_origin", "knowledge_base") for doc in docs
            ]
            if doc_origins and all(origin == doc_origins[0] for origin in doc_origins):
                dominant_origin = doc_origins[0]
            elif "hierarchical_index" in doc_origins:
                dominant_origin = "hierarchical_index"
            else:
                dominant_origin = "knowledge_base"

            formatted_context = self._format_documents(docs)
            summary_prompt = self._build_summary_prompt(
                query, focus, formatted_context, context_label="参考资料"
            )
            answer_text = await self._call_llm(summary_prompt)
            confidence = self._estimate_confidence(scores)
            return FinalAnswer(
                query_id=uuid4(),
                answer=answer_text,
                sources=docs,
                confidence=confidence,
                verification_passed=False,
                metadata={
                    "route": "knowledge",
                    "focus": focus,
                    "doc_count": len(docs),
                    "origin": dominant_origin,
                    "doc_origins": doc_origins,
                },
                total_processing_time=0.0,
            )

        web_results = await self._search_web(query)
        tool = self.web_tool
        if web_results and tool:
            formatted_context = tool.format_results(web_results)
            summary_prompt = self._build_summary_prompt(
                query, focus, formatted_context, context_label="网络搜索结果"
            )
            answer_text = await self._call_llm(summary_prompt)
            web_docs = self._web_results_to_documents(web_results)
            return FinalAnswer(
                query_id=uuid4(),
                answer=answer_text,
                sources=web_docs,
                confidence=self._estimate_web_confidence(web_results),
                verification_passed=False,
                metadata={
                    "route": "knowledge",
                    "focus": focus,
                    "doc_count": 0,
                    "origin": "web_search",
                    "doc_origins": ["web_search"],
                    "web_results": [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "score": item.get("score", 0.0),
                        }
                        for item in web_results
                    ],
                },
                total_processing_time=0.0,
            )

        return self._build_no_result_answer(query, reason="知识库暂无匹配文档且网络检索为空")

    async def _safe_search(
        self, query: str
    ) -> Tuple[List[PolicyDocument], List[float]]:
        try:
            docs, scores = await self.tool.search(query, top_k=self.top_k)
            return docs or [], scores or []
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("知识检索失败: %s", exc)
            return [], []

    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        tool = self.web_tool
        if not tool or not tool.enabled:
            return []
        return await asyncio.to_thread(tool.search, query, tool.max_results)

    async def _call_llm(self, prompt: str) -> str:
        try:
            response = await model_client.create(
                [UserMessage(content=prompt, source="user")]
            )
            return (response.content or "").strip() or "抱歉，目前无法根据知识库生成可靠回答。"
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("知识总结 LLM 调用失败: %s", exc)
            return "抱歉，生成答案时出现问题，请稍后再试。"

    def _format_documents(self, docs: List[PolicyDocument]) -> str:
        chunks = []
        for idx, doc in enumerate(docs[: self.top_k], 1):
            preview = (doc.content or "")[:6000].replace("\n", " ")  # Increased from 400 to 6000 to capture detailed subsidy standards
            chunks.append(
                f"[资料{idx}] 标题：{doc.title}\n来源：{doc.source}\n内容摘录：{preview}\n"
            )
        return "\n".join(chunks)

    def _web_results_to_documents(self, results: List[Dict[str, Any]]) -> List[PolicyDocument]:
        docs: List[PolicyDocument] = []
        for idx, item in enumerate(results, 1):
            docs.append(
                PolicyDocument(
                    title=item.get("title") or f"网络检索结果{idx}",
                    content=item.get("content") or "",
                    summary=None,
                    source=item.get("url") or "web_search",
                    doc_type=PolicyType.GUIDELINE,
                    publish_date=None,
                    effective_date=None,
                    expiry_date=None,
                    relevant_departments=[],
                    target_groups=[],
                    regions=[],
                    keywords=[],
                    embedding=None,
                    metadata={
                        "origin": "web_search",
                        "url": item.get("url", ""),
                        "score": item.get("score", 0.0),
                    },
                )
            )
        return docs

    def _estimate_confidence(self, scores: List[float]) -> float:
        if not scores:
            return 0.55
        avg = mean(scores)
        # Milvus score 0-1 (cosine/IP) -> map to 0.5-0.9
        return max(0.45, min(0.9, avg))

    def _estimate_web_confidence(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.3
        scores = [item.get("score", 0.0) for item in results]
        avg = sum(scores) / len(scores)
        # Tavily score roughly 0-3 -> normalize to 0.35-0.65
        normalized = 0.35 + min(max(avg, 0.0), 3.0) / 3.0 * 0.3
        return round(normalized, 3)

    def _build_summary_prompt(
        self, query: str, focus: str, context: str, *, context_label: str
    ) -> str:
        return (
            "你是政府政策问答系统的知识专家。"
            "请结合提供的资料回答用户问题，列出关键信息（条件、金额、流程、时间等），"
            "以条列方式输出，并在结尾用一句话总结答复依据。\n\n"
            f"用户问题：{query}\n"
            f"关注点/意图：{focus}\n\n"
            f"{context_label}：\n{context}\n\n"
            "请直接给出回答，不要重复引用原文。"
        )

    def _build_no_result_answer(self, query: str, reason: str) -> FinalAnswer:
        return FinalAnswer(
            query_id=uuid4(),
            answer=f"暂未在知识库或联网检索中找到与“{query}”直接相关的政策条目。建议提供更多背景或确认关键词。",
            sources=[],
            confidence=0.2,
            verification_passed=False,
            metadata={"route": "knowledge", "reason": reason, "doc_origins": []},
            total_processing_time=0.0,
        )
