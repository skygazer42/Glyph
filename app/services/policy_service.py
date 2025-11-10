"""
政策智能问答系统 (Policy QA System)

基于AutoGen框架的政策知识库智能问答系统
"""

from typing import Optional,Dict,Any

from app.agents import AgentFactory, AgentTypes
from app.knowledge import VectorStore, KnowledgeGraph, DocumentProcessor


class PolicyQAService:
    """Main service for policy QA system."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the policy QA service."""
        self.agent_factory = AgentFactory(config_path)
        self.vector_store = None
        self.graph_db = None
        self.document_processor = DocumentProcessor()

    def initialize(self):
        """Initialize all components."""
        # Create agents
        self.agent_factory.create_all_agents()

        # Initialize knowledge base components
        self.vector_store = self.agent_factory.vector_store
        self.graph_db = self.agent_factory.graph_db

    def load_documents(self, directory_path: str):
        """Load and process documents from directory."""
        documents = self.document_processor.process_directory(directory_path)

        # Add to vector store
        self.vector_store.add_documents(documents)

        # Add to knowledge graph
        for doc in documents:
            self.graph_db.add_policy_document(doc)

        return len(documents)

    async def ask(self, question: str) -> Dict[str, Any]:
        """Ask a policy question."""
        return await self.agent_factory.process_query(question)


# Convenience function
async def ask_policy_question(question: str, document_dir: str = None) -> Dict[str, Any]:
    """Convenience function to ask a policy question."""
    service = PolicyQAService()
    service.initialize()

    if document_dir:
        service.load_documents(document_dir)

    return await service.ask(question)
