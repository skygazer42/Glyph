"""
Base agent implementation using AutoGen Core.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from uuid import UUID

from autogen_core import (
    BaseAgent,
    Component,
    MessageContext,
    TopicId,
    CancellationToken,
    default_subscription,
    message_handler
)
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_agentchat.messages import TextMessage, ModelClientStreamingChunkEvent

from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    UserQuery,
    QueryAnalysis,
    RetrievalRequest,
    RetrievalResult,
    PolicyAnalysis,
    GeneratedAnswer,
    FactCheck,
    ConsistencyCheck,
    FinalAnswer
)

T = TypeVar('T')


class PolicyAgentBase(BaseAgent, ABC, Generic[T]):
    """Base class for all policy QA agents."""

    def __init__(
        self,
        agent_type: AgentType,
        name: str,
        description: str,
        memory_size: int = 100,
        **kwargs
    ):
        """Initialize the base agent."""
        super().__init__(description=description)
        self.agent_type = agent_type
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # Initialize memory
        self.memory = ListMemory()
        self.memory_size = memory_size

        # State management
        self.state: Dict[str, Any] = {}
        self.processing_queue: asyncio.Queue[T] = asyncio.Queue()
        self._is_running = False

        # Metrics
        self.metrics = {
            "messages_processed": 0,
            "errors": 0,
            "avg_processing_time": 0.0
        }

        self.logger.info(f"Agent {name} ({agent_type}) initialized")

    @abstractmethod
    async def process_request(self, request: T, context: MessageContext) -> Any:
        """Process a request. Must be implemented by subclasses."""
        pass

    @message_handler
    async def handle_message(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle incoming messages."""
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.debug(f"Received {message.type} from {message.sender}")

            # Store in memory
            await self._store_in_memory(message)

            # Process based on message type
            response = await self._route_message(message, ctx)

            # Update metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(processing_time)

            return response

        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
            self.metrics["errors"] += 1

            # Create error response
            return AgentMessage(
                type=MessageType.ERROR,
                sender=self.agent_type,
                recipient=message.sender,
                content={"error": str(e), "original_message_id": str(message.id)},
                correlation_id=message.correlation_id or message.id
            )

    async def _route_message(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Route message to appropriate handler."""
        handlers = {
            MessageType.USER_QUERY: self._handle_user_query,
            MessageType.QUERY_ANALYSIS: self._handle_query_analysis,
            MessageType.RETRIEVAL_REQUEST: self._handle_retrieval_request,
            MessageType.RETRIEVAL_RESULT: self._handle_retrieval_result,
            MessageType.ANALYSIS_REQUEST: self._handle_analysis_request,
            MessageType.ANALYSIS_RESULT: self._handle_analysis_result,
            MessageType.REQUIREMENT_EXTRACTION: self._handle_requirement_extraction,
            MessageType.ANSWER_GENERATION: self._handle_answer_generation,
            MessageType.FACT_CHECK: self._handle_fact_check,
            MessageType.CONSISTENCY_CHECK: self._handle_consistency_check,
            MessageType.FINAL_ANSWER: self._handle_final_answer
        }

        handler = handlers.get(message.type)
        if handler:
            return await handler(message, ctx)
        else:
            self.logger.warning(f"No handler for message type: {message.type}")
            return None

    @abstractmethod
    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages."""
        pass

    @abstractmethod
    async def _handle_query_analysis(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle query analysis messages."""
        pass

    async def _store_in_memory(self, message: AgentMessage):
        """Store message in agent memory."""
        content = MemoryContent(
            content=f"{message.type.value}: {message.content}",
            mime_type=MemoryMimeType.TEXT
        )

        self.memory.add(content)

        # Maintain memory size
        if len(self.memory) > self.memory_size:
            # Remove oldest messages
            while len(self.memory) > self.memory_size:
                self.memory.remove(0)

    def _update_metrics(self, processing_time: float):
        """Update agent metrics."""
        self.metrics["messages_processed"] += 1

        # Update average processing time
        n = self.metrics["messages_processed"]
        current_avg = self.metrics["avg_processing_time"]
        self.metrics["avg_processing_time"] = (current_avg * (n - 1) + processing_time) / n

    async def send_message(
        self,
        recipient: AgentType,
        message_type: MessageType,
        content: Dict[str, Any],
        correlation_id: Optional[UUID] = None
    ) -> None:
        """Send a message to another agent."""
        message = AgentMessage(
            type=message_type,
            sender=self.agent_type,
            recipient=recipient,
            content=content,
            correlation_id=correlation_id,
            requires_response=True
        )

        # Publish to message bus
        # Implementation depends on your message bus setup
        await self._publish_message(message)

    async def _publish_message(self, message: AgentMessage):
        """Publish message to the message bus."""
        # This would integrate with your message broker
        # For now, just log it
        self.logger.info(f"Publishing {message.type} to {message.recipient}")

    async def get_memory_context(self, limit: int = 10) -> str:
        """Get recent context from memory."""
        recent_memories = self.memory[-limit:] if len(self.memory) > limit else self.memory[:]

        context_parts = []
        for memory in recent_memories:
            context_parts.append(memory.content)

        return "\n".join(context_parts)

    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics."""
        return {
            **self.metrics,
            "memory_size": len(self.memory),
            "queue_size": self.processing_queue.qsize(),
            "is_running": self._is_running
        }

    async def start(self):
        """Start the agent."""
        self._is_running = True
        self.logger.info(f"Agent {self.name} started")

    async def stop(self):
        """Stop the agent."""
        self._is_running = False
        self.logger.info(f"Agent {self.name} stopped")


class StatefulAgent(PolicyAgentBase):
    """Base class for agents that maintain state."""

    def __init__(self, agent_type: AgentType, name: str, **kwargs):
        super().__init__(agent_type, name, **kwargs)
        self.persistent_state: Dict[str, Any] = {}
        self.state_version = 0

    async def update_state(self, updates: Dict[str, Any]):
        """Update agent state."""
        self.persistent_state.update(updates)
        self.state_version += 1
        self.logger.debug(f"State updated to version {self.state_version}")

    async def persist_state(self):
        """Persist agent state."""
        # Implementation depends on your persistence layer
        pass

    async def restore_state(self):
        """Restore agent state."""
        # Implementation depends on your persistence layer
        pass


class ReactiveAgent(PolicyAgentBase):
    """Base class for reactive agents that respond to events."""

    def __init__(self, agent_type: AgentType, name: str, **kwargs):
        super().__init__(agent_type, name, **kwargs)
        self.event_handlers: Dict[str, callable] = {}
        self.triggers: List[Dict[str, Any]] = []

    def register_event_handler(self, event_type: str, handler: callable):
        """Register an event handler."""
        self.event_handlers[event_type] = handler
        self.logger.debug(f"Registered handler for {event_type}")

    def add_trigger(self, condition: Dict[str, Any], action: callable):
        """Add a trigger condition and action."""
        self.triggers.append({"condition": condition, "action": action})

    async def check_triggers(self, event: Dict[str, Any]):
        """Check if any triggers are activated by the event."""
        for trigger in self.triggers:
            if self._evaluate_condition(trigger["condition"], event):
                await trigger["action"](event)

    def _evaluate_condition(self, condition: Dict[str, Any], event: Dict[str, Any]) -> bool:
        """Evaluate trigger condition."""
        # Simple implementation - can be enhanced with a rule engine
        for key, value in condition.items():
            if event.get(key) != value:
                return False
        return True


class ProactiveAgent(PolicyAgentBase):
    """Base class for proactive agents that initiate actions."""

    def __init__(self, agent_type: AgentType, name: str, **kwargs):
        super().__init__(agent_type, name, **kwargs)
        self.goals: List[Dict[str, Any]] = []
        self.plans: List[Dict[str, Any]] = []
        self._task_scheduler = asyncio.TaskScheduler()

    def add_goal(self, goal: Dict[str, Any]):
        """Add a goal for the agent to pursue."""
        self.goals.append(goal)
        self.logger.info(f"Added goal: {goal}")

    async def create_plan(self, goal: Dict[str, Any]) -> Dict[str, Any]:
        """Create a plan to achieve a goal."""
        # Must be implemented by subclasses
        raise NotImplementedError

    async def execute_plan(self, plan: Dict[str, Any]):
        """Execute a plan."""
        # Must be implemented by subclasses
        raise NotImplementedError

    async def start_task_scheduler(self):
        """Start the task scheduler."""
        self._task_scheduler.start()

    async def schedule_task(self, coro, delay: float = 0):
        """Schedule a task to run after a delay."""
        if delay > 0:
            await asyncio.sleep(delay)
        await self._task_scheduler.schedule(coro)