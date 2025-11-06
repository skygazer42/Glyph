"""
Agent factory for creating and managing policy QA agents.
"""

import os
from typing import Dict, Any, Optional
from autogen import config_list_from_json

from .types import AgentTypes
from ..retrieval.policy_retriever import PolicyRetriever
from ..generation.question import QuestionUnderstander
from ..generation.policy_analyzer import PolicyAnalyzer
from ..generation.answer_generator import AnswerGenerator
from ..verification.answer_verifier import AnswerVerifier
from ..coordination.coordinator import Coordinator


class AgentFactory:
    """Factory class for creating and managing agents."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the agent factory."""
        self.agents: Dict[str, Any] = {}
        self.config_path = config_path or os.path.expanduser("~/.autogen/OAI_CONFIG_LIST")
        self.llm_config = self._get_llm_config()
        self.model_client = None
        self.vector_store = None
        self.graph_db = None

    def _get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        try:
            config_list = config_list_from_json(
                env_or_file="OAI_CONFIG_LIST",
                filter_dict={
                    "model": {
                        "gpt-4",
                        "gpt-4-turbo",
                        "gpt-3.5-turbo",
                        "deepseek-chat",
                        "qwen-max"
                    }
                }
            )
            return {
                "config_list": config_list,
                "temperature": 0.1,
                "timeout": 120,
            }
        except Exception as e:
            # Fallback to environment variables
            return {
                "config_list": [
                    {
                        "model": os.getenv("MODEL_NAME", "gpt-3.5-turbo"),
                        "api_key": os.getenv("OPENAI_API_KEY"),
                        "base_url": os.getenv("OPENAI_BASE_URL"),
                    }
                ],
                "temperature": 0.1,
                "timeout": 120,
            }

    def register_agent(self, agent_type: AgentTypes, agent: Any):
        """Register an agent instance."""
        self.agents[agent_type.value] = agent

    def get_agent(self, agent_type: AgentTypes) -> Optional[Any]:
        """Get an agent instance by type."""
        return self.agents.get(agent_type.value)

    def create_all_agents(self):
        """Create all necessary agents for the policy QA system."""
        # Create knowledge base components
        from ...knowledge_base.milvus import MilvusStore

        self.vector_store = MilvusStore()
        self.graph_db = None  # 已移除图数据库，使用 LlamaIndex 替代

        # Create agents
        question_understander = QuestionUnderstander(
            name="QuestionUnderstander",
            llm_config=self.llm_config,
            vector_store=self.vector_store
        )
        self.register_agent(AgentTypes.QUESTION_UNDERSTANDER, question_understander)

        policy_retriever = PolicyRetriever(
            name="PolicyRetriever",
            llm_config=self.llm_config,
            vector_store=self.vector_store,
            graph_db=self.graph_db
        )
        self.register_agent(AgentTypes.POLICY_RETRIEVER, policy_retriever)

        policy_analyzer = PolicyAnalyzer(
            name="PolicyAnalyzer",
            llm_config=self.llm_config
        )
        self.register_agent(AgentTypes.POLICY_ANALYZER, policy_analyzer)

        answer_generator = AnswerGenerator(
            name="AnswerGenerator",
            llm_config=self.llm_config
        )
        self.register_agent(AgentTypes.ANSWER_GENERATOR, answer_generator)

        answer_verifier = AnswerVerifier(
            name="AnswerVerifier",
            llm_config=self.llm_config
        )
        self.register_agent(AgentTypes.ANSWER_VERIFIER, answer_verifier)

        coordinator = Coordinator(
            name="Coordinator",
            llm_config=self.llm_config,
            agents=self.agents
        )
        self.register_agent(AgentTypes.COORDINATOR, coordinator)

    def create_agent_group(self) -> 'GroupChat':
        """Create a group chat with all agents."""
        from autogen import GroupChat, GroupChatManager

        agents = list(self.agents.values())

        group_chat = GroupChat(
            agents=agents,
            messages=[],
            max_round=20,
            speaker_selection_method="auto"
        )

        return GroupChatManager(
            groupchat=group_chat,
            llm_config=self.llm_config
        )

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query through the agent pipeline."""
        coordinator = self.get_agent(AgentTypes.COORDINATOR)
        if not coordinator:
            raise ValueError("Coordinator agent not initialized")

        return await coordinator.process_query(query)