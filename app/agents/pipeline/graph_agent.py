"""Graph reasoning agent that leverages LightRAG when available."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from autogen_core import MessageContext
from autogen_core.models import UserMessage

from app.core.llms import model_client
from app.models.base import FinalAnswer, PolicyDocument, PolicyType
from .knowledge_agent import KnowledgeAgent

try:  # pragma: no cover - LightRAG is optional
    from app.agents.packs.graph_retriever.node import GraphRetrieverAgent
except Exception:  # pragma: no cover
    GraphRetrieverAgent = None  # type: ignore


class GraphAgent:
    """Uses LightRAG to answer relation/summary questions, fallback to knowledge agent."""

    def __init__(self, knowledge_agent: KnowledgeAgent):
        self.knowledge_agent = knowledge_agent
        self.logger = logging.getLogger(__name__)
        self._graph_agent = None
        if GraphRetrieverAgent:
            try:
                self._graph_agent = GraphRetrieverAgent()
            except Exception as exc:  # pragma: no cover
                self.logger.warning("GraphRetriever 初始化失败，将退回知识库：%s", exc)
                self._graph_agent = None

    async def answer(self, query: str, *, intent: Optional[Dict[str, Any]] = None) -> FinalAnswer:
        if not self._graph_agent:
            return await self.knowledge_agent.answer(
                query, intent=intent, emphasis="relation_summary"
            )

        try:
            result = await self._graph_agent.process_request(
                {"query_text": query, "mode": "hybrid", "top_k": 3},
                MessageContext(),
            )
            doc = result.documents[0] if result.documents else self._wrap_raw_text("")
            relation_summary = await self._summarize_graph(doc.content, query)
            return FinalAnswer(
                query_id=uuid4(),
                answer=relation_summary,
                sources=[doc],
                confidence=0.7,
                verification_passed=False,
                metadata={"route": "graph", "method": result.method.value if result.method else "graph"},
                total_processing_time=0.0,
            )
        except Exception as exc:  # pragma: no cover
            self.logger.warning("GraphAgent 调用失败，改用知识库：%s", exc)
            return await self.knowledge_agent.answer(
                query, intent=intent, emphasis="relation_summary"
            )

    async def ingest(self, documents: List[PolicyDocument]) -> int:
        """Push documents into LightRAG when available. Returns count of indexed documents."""
        if not self._graph_agent or not documents:
            return 0
        try:
            return await self._graph_agent.add_documents(documents)
        except Exception as exc:  # pragma: no cover
            self.logger.warning("GraphAgent 文档入库失败：%s", exc)
            return 0

    async def _summarize_graph(self, graph_text: str, query: str) -> str:
        prompt = (
            "下面是来自 LightRAG 的关系/知识图谱查询结果，请据此回答用户问题，"
            "重点描述主体之间的联系或主题脉络，如无相关信息请说明。\n\n"
            f"用户问题：{query}\n\n"
            f"图谱返回：\n{graph_text[:2000]}\n"
        )
        response = await model_client.create([UserMessage(content=prompt, source="user")])
        return (response.content or "").strip() or "暂未从知识图谱中解析出明确的关系。"

    def _wrap_raw_text(self, text: str) -> PolicyDocument:
        return PolicyDocument(
            title="LightRAG 结果",
            content=text,
            source="LightRAG",
            doc_type=PolicyType.GUIDELINE,
        )
