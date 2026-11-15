"""Graph reasoning agent using LightRAG results and knowledge search on an empty result."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from autogen_core import MessageContext, AgentId, TopicId, CancellationToken
from autogen_core.models import UserMessage

from app.core.llms import model_client
from app.models.base import FinalAnswer, PolicyDocument
from .knowledge_agent import KnowledgeAgent

from app.agents.packs.graph_retriever.node import GraphRetrieverAgent


class GraphAgent:
    """Answer relation questions with LightRAG; search knowledge when no graph evidence exists."""

    def __init__(self, knowledge_agent: KnowledgeAgent):
        self.knowledge_agent = knowledge_agent
        self.logger = logging.getLogger(__name__)
        self._graph_agent = GraphRetrieverAgent()
        self._inline_summary_threshold = 800

    async def answer(self, query: str, *, intent: Optional[Dict[str, Any]] = None) -> FinalAnswer:
        result = await self._graph_agent.process_request(
            {"query_text": query, "mode": "hybrid", "top_k": 3},
            self._build_message_context(),
        )
        if not result.documents:
            return await self.knowledge_agent.answer(
                query, intent=intent, emphasis="relation_summary"
            )
        doc = result.documents[0]
        if len(doc.content) <= self._inline_summary_threshold:
            relation_summary = self._format_graph_snippet(doc.content, query)
        else:
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

    async def ingest(self, documents: List[PolicyDocument]) -> int:
        """Push documents into LightRAG. Returns count of indexed documents."""
        if not documents:
            return 0
        return await self._graph_agent.add_documents(documents)

    async def _summarize_graph(self, graph_text: str, query: str) -> str:
        prompt = (
            "下面是来自 LightRAG 的关系/知识图谱查询结果，请据此回答用户问题，"
            "重点描述主体之间的联系或主题脉络，如无相关信息请说明。"
            "请使用自然段或列表描述，禁止输出以 # 开头的 Markdown 标题。\n\n"
            f"用户问题：{query}\n\n"
            f"图谱返回：\n{graph_text[:2000]}\n"
        )
        response = await model_client.create([UserMessage(content=prompt, source="user")])
        if not isinstance(response.content, str):
            raise ValueError("Graph summary model returned non-text content")
        sanitized = self._strip_markdown_headings(response.content)
        summary = sanitized.strip()
        if not summary:
            raise ValueError("Graph summary model returned empty text")
        return summary

    def _format_graph_snippet(self, graph_text: str, query: str) -> str:
        snippet = graph_text.strip()
        if len(snippet) > self._inline_summary_threshold:
            snippet = snippet[: self._inline_summary_threshold] + "..."
        snippet = self._strip_markdown_headings(snippet)
        return f"根据知识库关系返回的内容，以下是与“{query}”相关的关系概要：\n{snippet}"

    async def close(self) -> None:
        await self._graph_agent.close()

    def _build_message_context(self) -> MessageContext:
        """Create a minimal MessageContext for AutoGen graph agents."""
        return MessageContext(
            sender=AgentId("graph_agent", "router"),
            topic_id=TopicId("graph", "graph_agent"),
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id=str(uuid4()),
        )

    def _strip_markdown_headings(self, text: str) -> str:
        """Remove markdown heading markers (#, ##, ###) to keep responses clean."""
        if not text:
            return ""
        cleaned = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
        return cleaned
