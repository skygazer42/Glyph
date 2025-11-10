"""Knowledge retrieval + synthesis agent built on KnowledgeService."""

from __future__ import annotations

import logging
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from autogen_core.models import UserMessage

from app.agents.service.tools import KnowledgeTool
from app.core.llms import model_client
from app.models.base import FinalAnswer, PolicyDocument


class KnowledgeAgent:
    """Wraps KnowledgeTool and LLM summarization to answer policy inquiries."""

    def __init__(self, knowledge_tool: KnowledgeTool, top_k: int = 5) -> None:
        self.tool = knowledge_tool
        self.top_k = top_k
        self.logger = logging.getLogger(__name__)

    async def answer(
        self,
        query: str,
        *,
        intent: Optional[Dict[str, Any]] = None,
        emphasis: Optional[str] = None,
    ) -> FinalAnswer:
        docs, scores = await self._safe_search(query)
        if not docs:
            return self._build_no_result_answer(query, reason="知识库暂无匹配文档")

        formatted_context = self._format_documents(docs)
        focus = emphasis or (intent or {}).get("sub_intent") or "general"
        summary_prompt = (
            "你是政府政策问答系统的知识库专家，已检索到若干参考资料。"
            "请结合上下文回答用户问题，列出关键信息（条件、金额、流程、时间等），"
            "以条列方式输出，并在结尾用一句话总结答复依据。\n\n"
            f"用户问题：{query}\n"
            f"关注点/意图：{focus}\n\n"
            f"参考资料：\n{formatted_context}\n\n"
            "请直接给出回答，不要重复引用原文。"
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
            },
            total_processing_time=0.0,
        )

    async def _safe_search(
        self, query: str
    ) -> Tuple[List[PolicyDocument], List[float]]:
        try:
            docs, scores = await self.tool.search(query, top_k=self.top_k)
            return docs or [], scores or []
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("知识检索失败: %s", exc)
            return [], []

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
            preview = (doc.content or "")[:400].replace("\n", " ")
            chunks.append(
                f"[资料{idx}] 标题：{doc.title}\n来源：{doc.source}\n内容摘录：{preview}\n"
            )
        return "\n".join(chunks)

    def _estimate_confidence(self, scores: List[float]) -> float:
        if not scores:
            return 0.55
        avg = mean(scores)
        # Milvus score 0-1 (cosine/IP) -> map to 0.5-0.9
        return max(0.45, min(0.9, avg))

    def _build_no_result_answer(self, query: str, reason: str) -> FinalAnswer:
        return FinalAnswer(
            query_id=uuid4(),
            answer=f"暂未在知识库中找到与“{query}”直接相关的政策条目。建议提供更多背景或确认关键词。",
            sources=[],
            confidence=0.2,
            verification_passed=False,
            metadata={"route": "knowledge", "reason": reason},
            total_processing_time=0.0,
        )
