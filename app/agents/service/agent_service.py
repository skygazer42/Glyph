"""High-level service that wires together the agent pipeline."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from app.agents.framework.base.types import PolicyDocument
from app.agents.pipeline import (
    ClarifierAgent,
    DialogueAgent,
    GraphAgent,
    KnowledgeAgent,
    RewriteAgent,
    RuleEngineAgent,
    Text2SQLAgent,
    WorkflowAgent,
)
from .tools import (
    IntentDetectionTool,
    KnowledgeTool,
    VisionTool,
    WebSearchTool,
    UserProfileTool,
)
from app.core import logging_manager
from app.knowledge.service import KnowledgeService
from app.utils.config import Config
from app.utils.document_loader import DocumentLoader
from app.models.base import Attachment

logging_manager.configure()


class AgentService:
    """Single entrypoint that orchestrates the streamlined agent pipeline."""

    SQL_KEYWORDS = ["sql", "数据库", "数据表", "字段", "列名", "select", "查询语句"]

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> None:
        self.config = config or Config.from_env()
        self.intent_tool = IntentDetectionTool()
        self.knowledge_tool = KnowledgeTool(knowledge_service)
        search_cfg = self.config.web_search
        self.web_search_tool = WebSearchTool(
            api_key=(search_cfg.tavily_api_key or None),
            max_results=search_cfg.max_results,
            search_depth=search_cfg.search_depth,
            enabled=search_cfg.enabled,
            site_filter=search_cfg.site_filter,
        )
        vision_cfg = self.config.vision
        self.vision_tool = VisionTool(
            enabled=vision_cfg.enabled,
            model=vision_cfg.model,
            api_key=(vision_cfg.api_key or None),
            base_url=vision_cfg.base_url or None,
            prompt_template=vision_cfg.prompt_template,
            max_images=vision_cfg.max_images,
            max_output_tokens=vision_cfg.max_output_tokens,
        )
        profile_db_path = self.config.user_profile_db_path
        self.user_profile_tool = UserProfileTool(db_path=profile_db_path)
        self._loader = DocumentLoader()

        # Pipeline agents
        self.rewrite_agent = RewriteAgent()
        self.knowledge_agent = KnowledgeAgent(
            self.knowledge_tool, web_search_tool=self.web_search_tool
        )
        self.graph_agent = GraphAgent(self.knowledge_agent)
        self.rule_agent = RuleEngineAgent()
        self.text2sql_agent = Text2SQLAgent()
        self.dialogue_agent = DialogueAgent()
        self.clarifier_agent = ClarifierAgent()
        self.workflow_agent = WorkflowAgent(
            vision_tool=self.vision_tool,
            knowledge_agent=self.knowledge_agent,
            rule_agent=self.rule_agent,
            user_profile_tool=self.user_profile_tool,
        )
        self._initialized = True  # no heavy bootstrap step anymore

    async def initialize(self) -> None:
        # 保留兼容接口，未来如需预热可在此实现
        self._initialized = True

    async def process_query(
        self,
        query: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> Any:
        start = time.perf_counter()
        await self.initialize()
        attachments = attachments or []

        rewritten_query = await self.rewrite_agent.rewrite(query)
        intent_result = await self.intent_tool.detect(rewritten_query)
        route = self._resolve_route(intent_result, rewritten_query, connection_id, attachments)

        if route == "dialogue":
            final = self.dialogue_agent.respond(intent_result.get("intent", "chit_chat"))
        elif route == "clarify":
            final = self.clarifier_agent.ask(rewritten_query)
        elif route == "rule_engine":
            final = await self.rule_agent.compute(rewritten_query, intent=intent_result)
        elif route == "text2sql":
            final = await self.text2sql_agent.answer(
                rewritten_query, connection_id=connection_id
            )
        elif route == "graph":
            final = await self.graph_agent.answer(rewritten_query, intent=intent_result)
        elif route == "workflow":
            final = await self.workflow_agent.answer(
                rewritten_query,
                attachments=attachments,
                intent=intent_result,
            )
        else:  # knowledge 默认
            final = await self.knowledge_agent.answer(rewritten_query, intent=intent_result)

        metadata = final.metadata or {}
        metadata.update(
            {
                "route": route,
                "intent": intent_result,
                "rewritten_query": rewritten_query,
                "session_id": session_id,
                "user_id": user_id,
            }
        )
        if attachments:
            metadata.setdefault("attachments", [att.model_dump() for att in attachments])
        final.metadata = metadata
        final.total_processing_time = time.perf_counter() - start
        return final

    async def ingest_paths(self, paths: List[str]) -> Dict[str, int]:
        documents = []
        for path in paths:
            try:
                documents.extend(self._loader.load_from_directory(path))
            except Exception:
                doc = self._loader.load_single_file(path)
                if doc:
                    documents.append(doc)
        if not documents:
            return {"loaded_docs": 0, "kb_indexed": 0, "rag_indexed": 0}
        indexed = await self.knowledge_tool.ingest(documents)
        await self.graph_agent.ingest(documents)
        logging_manager.info("Ingested %s documents into vector store", indexed)
        return {"loaded_docs": len(documents), "kb_indexed": indexed, "rag_indexed": 0}

    async def detect_intent(self, query: str) -> Dict[str, Any]:
        return await self.intent_tool.detect(query)

    async def search_knowledge(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return await self.knowledge_tool.search(
            query, top_k=top_k, threshold=threshold, filters=filters
        )

    def _resolve_route(
        self,
        intent_result: Dict[str, Any],
        rewritten_query: str,
        connection_id: Optional[int],
        attachments: List[Attachment],
    ) -> str:
        intent = (intent_result or {}).get("intent", "policy_inquiry")
        if attachments and any(att.is_image() for att in attachments):
            if self.vision_tool.enabled:
                return "workflow"
        if intent in {"user_history", "user_profile"}:
            return "workflow"
        if intent in {"greeting", "farewell", "chit_chat"}:
            return "dialogue"
        if intent == "clarification":
            return "clarify"
        if intent == "calculation":
            return "rule_engine"
        if intent == "summary":
            return "graph"
        if intent == "comparison":
            return "knowledge"

        if self._looks_like_sql_question(rewritten_query) and connection_id:
            return "text2sql"

        chains = (intent_result or {}).get("chains") or []
        if "vision_chain" in chains and self.vision_tool.enabled:
            return "workflow"
        if "user_history_chain" in chains:
            return "workflow"
        if "graph_chain" in chains and connection_id is None:
            return "graph"
        if "calculation_chain" in chains:
            return "rule_engine"

        if self._looks_like_user_history(rewritten_query):
            return "workflow"

        return "knowledge"

    def _looks_like_sql_question(self, query: str) -> bool:
        q = query.lower()
        return any(keyword in q for keyword in self.SQL_KEYWORDS)

    def _looks_like_user_history(self, query: str) -> bool:
        keywords = [
            "历史查询",
            "用户历史",
            "个人历史",
            "个人资料",
            "用户信息",
            "user history",
            "user profile",
        ]
        q_lower = query.lower()
        return any(kw in query or kw in q_lower for kw in keywords)


__all__ = ["AgentService"]
