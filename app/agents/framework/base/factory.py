"""
Agent factory for creating and managing policy QA agents.
"""

import os
import asyncio
from typing import Dict, Any, Optional, Protocol, TYPE_CHECKING
import json
from pathlib import Path
from contextlib import AsyncExitStack
from functools import partial

from app.utils.lifecycle import close_with_timeout

from .types import AgentTypes
from app.agents.packs.policy_retriever.node import PolicyRetriever
from app.agents.packs.question_builder.node import QuestionUnderstander
from app.agents.packs.policy_review.node import PolicyReviewAgent
from ..coordination.coordinator import Coordinator

if TYPE_CHECKING:
    from app.knowledge.milvus import MilvusStore


class PolicyAnswerGenerator(Protocol):
    """工厂所需的回答生成协议：异步接收消息文本并返回结果字典。"""

    async def process_message(self, message: str) -> Dict[str, Any]: ...


class AgentFactory:
    """Factory class for creating and managing agents."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the agent factory."""
        self.agents: Dict[str, Any] = {}
        self.config_path = os.path.expanduser("~/.autogen/OAI_CONFIG_LIST") if config_path is None else config_path
        self.llm_config = self._load_llm_config()
        self.vector_store: Optional["MilvusStore"] = None
        self._owned_agents: list[Any] = []

    def _load_llm_config(self) -> Dict[str, Any]:
        """Load provider configuration from the configured JSON or environment."""
        configured = os.getenv("OAI_CONFIG_LIST")
        if configured is not None:
            if configured.lstrip().startswith("["):
                providers = json.loads(configured)
            else:
                providers = json.loads(Path(configured).read_text(encoding="utf-8"))
        elif Path(self.config_path).is_file():
            providers = json.loads(Path(self.config_path).read_text(encoding="utf-8"))
        else:
            providers = [{"model": os.getenv("MODEL_NAME", "gpt-3.5-turbo"),
                          "api_key": os.getenv("OPENAI_API_KEY"),
                          "base_url": os.getenv("OPENAI_BASE_URL")}]
        if not isinstance(providers, list) or not providers or not all(isinstance(item, dict) for item in providers):
            raise ValueError("OAI_CONFIG_LIST must be a non-empty list of provider objects")
        return {"config_list": providers, "temperature": 0.1, "timeout": 120}

    def register_agent(self, agent_type: AgentTypes, agent: Any):
        """Register an agent instance."""
        self.agents[agent_type.value] = agent

    def get_agent(self, agent_type: AgentTypes) -> Optional[Any]:
        """Get an agent instance by type."""
        return self.agents.get(agent_type.value)

    def create_all_agents(self, *, answer_generator: PolicyAnswerGenerator) -> None:
        """Create all necessary agents for the policy QA system."""
        if self.vector_store is not None or self._owned_agents:
            raise RuntimeError("Close the existing factory resources before creating agents again")
        # Create knowledge base components
        from app.knowledge.milvus import MilvusStore

        self.vector_store = MilvusStore()

        # Create agents
        question_understander = QuestionUnderstander(
            name="QuestionUnderstander",
            llm_config=self.llm_config,
        )
        self._owned_agents.append(question_understander)
        self.register_agent(AgentTypes.QUESTION_UNDERSTANDER, question_understander)

        policy_retriever = PolicyRetriever(
            name="PolicyRetriever",
            llm_config=self.llm_config,
            vector_store=self.vector_store,
        )
        self._owned_agents.append(policy_retriever)
        self.register_agent(AgentTypes.POLICY_RETRIEVER, policy_retriever)

        policy_analyzer = PolicyReviewAgent(
            name="PolicyAnalyzer",
            llm_config=self.llm_config
        )
        self._owned_agents.append(policy_analyzer)
        self.register_agent(AgentTypes.POLICY_ANALYZER, policy_analyzer)

        self.register_agent(AgentTypes.ANSWER_GENERATOR, answer_generator)

        coordinator = Coordinator(
            name="Coordinator",
            llm_config=self.llm_config,
            agents=self.agents
        )
        self.register_agent(AgentTypes.COORDINATOR, coordinator)

    async def aclose(self) -> None:
        """Close successfully constructed resources, including after a partial build."""
        agents, self._owned_agents = self._owned_agents, []
        vector_store, self.vector_store = self.vector_store, None
        self.agents.clear()
        async with AsyncExitStack() as stack:
            if vector_store is not None:
                stack.push_async_callback(close_with_timeout, partial(asyncio.to_thread, vector_store.close))
            for agent in agents:
                stack.push_async_callback(close_with_timeout, agent.close)

    def create_agent_group(self) -> Any:
        """Old autogen.GroupChat cannot consume the project's Core/business agents."""
        raise NotImplementedError("Use app.agents.service.AgentChatTeam with AutoGen AgentChat 0.7.5")

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query through the agent pipeline."""
        coordinator = self.get_agent(AgentTypes.COORDINATOR)
        if not coordinator:
            raise ValueError("Coordinator agent not initialized")

        return await coordinator.process_query(query)
