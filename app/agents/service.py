"""High-level service that wires together the agent toolkit."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agents.base.types import PolicyDocument
from app.agents.orchestrators.smart import SmartOrchestrator
from app.agents.toolkit import IntentDetectionTool, KnowledgeTool, Text2SQLTool
from app.models.db_connection import DBConnection
from app.services.knowledge_service import KnowledgeService
from app.utils.config import Config
from app.utils.document_loader import DocumentLoader
from app.core import logging_manager

logging_manager.configure()


class AgentService:
    """Single entrypoint that orchestrates the multi-agent pipeline."""

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        orchestrator: Optional[SmartOrchestrator] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> None:
        self.config = config or Config.from_env()
        self.orchestrator = orchestrator or SmartOrchestrator(
            model_config=self.config.model,
            vector_store_config=self.config.vector_store,
            logging_config=self.config.logging,
        )
        self.intent_tool = IntentDetectionTool()
        self.text2sql_tool = Text2SQLTool()
        self.knowledge_tool = KnowledgeTool(knowledge_service)
        self._initialized = False
        self._loader = DocumentLoader()

    async def initialize(self) -> None:
        if not self._initialized:
            logging_manager.info("Initializing SmartOrchestrator for AgentService")
            await self.orchestrator.initialize()
            self._initialized = True

    async def process_query(
        self,
        query: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Any:
        await self.initialize()
        return await self.orchestrator.process_query(query, session_id=session_id, user_id=user_id)

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
        logging_manager.info(
            "Ingested %s documents into vector store", indexed
        )
        return {"loaded_docs": len(documents), "kb_indexed": indexed, "rag_indexed": 0}

    async def detect_intent(self, query: str) -> Dict[str, Any]:
        return await self.intent_tool.detect(query)

    def run_text2sql(self, db: Session, connection: DBConnection, query: str):
        return self.text2sql_tool.run(db, connection, query)

    async def search_knowledge(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return await self.knowledge_tool.search(query, top_k=top_k, threshold=threshold, filters=filters)


__all__ = ["AgentService"]
