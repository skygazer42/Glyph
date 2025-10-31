"""
Policy QA System Orchestrator - Coordinates all agents in the workflow.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from autogen_core import (
    AgentRuntime,
    SingleThreadedAgentRuntime,
    MessageContext,
    TopicId,
    CancellationToken
)
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage, AgentMessage

from models.base import (
    AgentType,
    MessageType,
    UserQuery,
    QueryAnalysis,
    RetrievalRequest,
    RetrievalResult,
    PolicyAnalysis,
    GeneratedAnswer,
    FinalAnswer
)
from agents.retrieval.vector_retriever import VectorRetrieverAgent
from agents.analysis.policy_analyzer import PolicyAnalyzerAgent
from agents.generation.answer_generator import AnswerGeneratorAgent


class PolicyQAOrchestrator:
    """Main orchestrator for the policy QA system."""

    def __init__(
        self,
        model_config: Dict[str, Any],
        vector_store_config: Dict[str, Any],
        logging_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the orchestrator."""
        self.model_config = model_config
        self.vector_store_config = vector_store_config
        self.setup_logging(logging_config)

        self.runtime = SingleThreadedAgentRuntime()
        self.agents: Dict[AgentType, Any] = {}
        self.workflow_state: Dict[str, Any] = {}
        self.active_sessions: Dict[str, Dict] = {}

        self.logger.info("Policy QA Orchestrator initialized")

    def setup_logging(self, config: Optional[Dict[str, Any]]):
        """Setup logging configuration."""
        logging.basicConfig(
            level=config.get("level", "INFO") if config else "INFO",
            format=config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize all agents and components."""
        self.logger.info("Initializing agents...")

        # Initialize vector retriever
        self.agents[AgentType.POLICY_RETRIEVER] = VectorRetrieverAgent(
            **self.vector_store_config
        )
        await self.agents[AgentType.POLICY_RETRIEVER].initialize()

        # Initialize policy analyzer
        self.agents[AgentType.POLICY_ANALYZER] = PolicyAnalyzerAgent(
            model_client=self._create_model_client()
        )

        # Initialize answer generator
        self.agents[AgentType.ANSWER_GENERATOR] = AnswerGeneratorAgent(
            model_client=self._create_model_client()
        )

        # Register agents with runtime
        for agent_type, agent in self.agents.items():
            await self.runtime.register(agent, f"{agent_type.value}")

        # Start the runtime
        self.runtime.start()

        self.logger.info("All agents initialized successfully")

    def _create_model_client(self):
        """Create model client based on configuration."""
        # This would create an actual model client
        # Implementation depends on the model provider
        return None

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FinalAnswer:
        """Process a user query through the complete workflow."""
        # Create session if not exists
        session_id = session_id or f"session_{datetime.now().timestamp()}"
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "created_at": datetime.now(),
                "queries": [],
                "context": {}
            }

        # Create user query object
        user_query = UserQuery(
            text=query,
            session_id=session_id,
            user_id=user_id
        )

        # Store in session
        self.active_sessions[session_id]["queries"].append(user_query)

        # Process through workflow
        start_time = datetime.now()
        self.workflow_state[session_id] = {
            "query": user_query,
            "step": 1,
            "total_steps": 5,
            "results": {},
            "errors": []
        }

        try:
            # Step 1: Query Understanding (using retriever for now)
            self.logger.info(f"Step 1: Understanding query - {query[:50]}...")
            query_embedding = await self.agents[AgentType.POLICY_RETRIEVER]._get_query_embedding(query)
            self.workflow_state[session_id]["results"]["query_embedding"] = query_embedding
            self.workflow_state[session_id]["step"] = 2

            # Step 2: Document Retrieval
            self.logger.info("Step 2: Retrieving relevant policies...")
            retrieval_request = RetrievalRequest(
                query_id=user_query.id,
                query_embedding=query_embedding,
                top_k=10,
                threshold=0.7
            )

            retrieval_result = await self.agents[AgentType.POLICY_RETRIEVER].process_request(
                retrieval_request,
                MessageContext()
            )
            self.workflow_state[session_id]["results"]["retrieval"] = retrieval_result
            self.workflow_state[session_id]["step"] = 3

            if not retrieval_result.documents:
                self.logger.warning("No documents found for the query")
                return self._create_no_policy_response(user_query)

            # Step 3: Policy Analysis
            self.logger.info(f"Step 3: Analyzing {len(retrieval_result.documents)} documents...")
            analyses = []
            for doc in retrieval_result.documents[:5]:  # Analyze top 5
                analysis = await self.agents[AgentType.POLICY_ANALYZER].process_request(
                    {"document": doc, "query_id": user_query.id},
                    MessageContext()
                )
                analyses.append(analysis)

            synthesis = {
                "most_relevant_document": analyses[0].document_id if analyses else None,
                "total_analyzed": len(analyses),
                "coverage_score": len([a for a in analyses if a.relevance_score > 0.7]) / len(analyses) if analyses else 0
            }
            self.workflow_state[session_id]["results"]["analysis"] = {
                "analyses": [a.dict() for a in analyses],
                "synthesis": synthesis
            }
            self.workflow_state[session_id]["step"] = 4

            # Step 4: Answer Generation
            self.logger.info("Step 4: Generating answer...")
            generation_request = {
                "query_context": {
                    "query_id": str(user_query.id),
                    "text": query,
                    "intent": "general_inquiry"  # Would be determined by query analyzer
                },
                "sources": [(a.dict(), a.relevance_score) for a in analyses],
                "synthesis": synthesis,
                "intent": "general_inquiry"
            }

            generated_answer = await self.agents[AgentType.ANSWER_GENERATOR].process_request(
                generation_request,
                MessageContext()
            )
            self.workflow_state[session_id]["results"]["answer"] = generated_answer
            self.workflow_state[session_id]["step"] = 5

            # Step 5: Final Response Compilation
            self.logger.info("Step 5: Compiling final response...")
            final_answer = await self._compile_final_answer(
                user_query,
                retrieval_result,
                analyses,
                generated_answer
            )

            # Calculate total processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            final_answer.total_processing_time = processing_time

            # Update workflow state
            self.workflow_state[session_id]["step"] = "completed"
            self.workflow_state[session_id]["final_answer"] = final_answer

            # Store in session
            self.active_sessions[session_id]["context"]["last_answer"] = final_answer

            self.logger.info(f"Query processed successfully in {processing_time:.2f}s")
            return final_answer

        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            self.workflow_state[session_id]["errors"].append(str(e))
            return self._create_error_response(user_query, str(e))

    async def _compile_final_answer(
        self,
        query: UserQuery,
        retrieval_result: RetrievalResult,
        analyses: List[PolicyAnalysis],
        generated_answer: GeneratedAnswer
    ) -> FinalAnswer:
        """Compile the final answer from all workflow results."""
        # Get source documents
        source_docs = []
        for doc in retrieval_result.documents:
            if doc.id in generated_answer.sources:
                source_docs.append(doc)

        return FinalAnswer(
            query_id=query.id,
            answer=generated_answer.answer,
            sources=source_docs,
            confidence=generated_answer.confidence,
            verification_passed=generated_answer.confidence > 0.7,
            fact_check=None,  # Would be added by fact checker
            consistency_check=None,  # Would be added by consistency checker
            metadata={
                "retrieved_count": len(retrieval_result.documents),
                "analyzed_count": len(analyses),
                "used_sources": len(source_docs),
                "session_id": query.session_id
            }
        )

    def _create_no_policy_response(self, query: UserQuery) -> FinalAnswer:
        """Create response when no policies are found."""
        return FinalAnswer(
            query_id=query.id,
            answer="抱歉，我没有找到与您的问题相关的政策信息。建议您：\n\n1. 尝试使用不同的关键词\n2. 咨询相关部门获取最新政策\n3. 查看政府官方网站",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"reason": "no_documents_found"}
        )

    def _create_error_response(self, query: UserQuery, error: str) -> FinalAnswer:
        """Create error response."""
        return FinalAnswer(
            query_id=query.id,
            answer=f"处理您的问题时遇到了错误：{error}\n\n请稍后重试或联系系统管理员。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"error": error}
        )

    async def load_documents(self, document_paths: List[str]):
        """Load documents into the vector store."""
        self.logger.info(f"Loading documents from {len(document_paths)} paths...")

        # This would load and process documents
        # For now, just log
        for path in document_paths:
            self.logger.info(f"Loading documents from: {path}")

        # Initialize vector retriever if not already done
        if AgentType.POLICY_RETRIEVER not in self.agents:
            self.agents[AgentType.POLICY_RETRIEVER] = VectorRetrieverAgent(
                **self.vector_store_config
            )
            await self.agents[AgentType.POLICY_RETRIEVER].initialize()

        # Get statistics
        stats = self.agents[AgentType.POLICY_RETRIEVER].get_stats()
        self.logger.info(f"Loaded documents. Stats: {stats}")

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information."""
        return self.active_sessions.get(session_id)

    def get_workflow_state(self, session_id: str) -> Optional[Dict]:
        """Get workflow state for a session."""
        return self.workflow_state.get(session_id)

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get metrics from all agents."""
        metrics = {}
        for agent_type, agent in self.agents.items():
            if hasattr(agent, 'get_metrics'):
                metrics[agent_type.value] = agent.get_metrics()
        return metrics

    async def shutdown(self):
        """Shutdown the orchestrator and all agents."""
        self.logger.info("Shutting down...")

        # Stop all agents
        for agent in self.agents.values():
            if hasattr(agent, 'stop'):
                await agent.stop()

        # Stop runtime
        self.runtime.stop()

        self.logger.info("Shutdown complete")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()