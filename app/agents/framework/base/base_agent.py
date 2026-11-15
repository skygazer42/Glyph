"""
Base agent implementation using AutoGen Core.
"""

import asyncio
from anyio import fail_after
import logging
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from uuid import UUID

from autogen_core import (
    RoutedAgent,
    MessageContext,
    TopicId,
    default_subscription,
    message_handler
)
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage
)

T = TypeVar('T')


@default_subscription
class PolicyAgentBase(RoutedAgent, ABC, Generic[T]):
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
        if memory_size <= 0:
            raise ValueError("memory_size must be positive")
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
        if message.recipient is not None and message.recipient != self.agent_type:
            return None
        start_time = asyncio.get_running_loop().time()

        try:
            self.logger.debug(f"Received {message.type} from {message.sender}")

            # Store in memory
            await self._store_in_memory(message)

            # Process based on message type
            response = await self._route_message(message, ctx)

            # Update metrics
            processing_time = asyncio.get_running_loop().time() - start_time
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
            MessageType.USER_QUERY: "_handle_user_query",
            MessageType.QUERY_ANALYSIS: "_handle_query_analysis",
            MessageType.RETRIEVAL_REQUEST: "_handle_retrieval_request",
            MessageType.RETRIEVAL_RESULT: "_handle_retrieval_result",
            MessageType.ANALYSIS_REQUEST: "_handle_analysis_request",
            MessageType.ANALYSIS_RESULT: "_handle_analysis_result",
            MessageType.REQUIREMENT_EXTRACTION: "_handle_requirement_extraction",
            MessageType.ANSWER_GENERATION: "_handle_answer_generation",
            MessageType.FACT_CHECK: "_handle_fact_check",
            MessageType.CONSISTENCY_CHECK: "_handle_consistency_check",
            MessageType.FINAL_ANSWER: "_handle_final_answer",
        }
        name = handlers.get(message.type)
        # Message handlers are optional capabilities provided by concrete agents.
        handler = getattr(self, name, None) if name is not None else None
        if handler is None:
            self.logger.warning("No handler for message type: %s", message.type)
            return None
        return await handler(message, ctx)

    async def _store_in_memory(self, message: AgentMessage):
        """Store message in agent memory."""
        content = MemoryContent(
            content=f"{message.type.value}: {message.content}",
            mime_type=MemoryMimeType.TEXT
        )

        await self.memory.add(content)
        self.memory.content = self.memory.content[-self.memory_size:]

    def _update_metrics(self, processing_time: float):
        """Update agent metrics."""
        self.metrics["messages_processed"] += 1

        # Update average processing time
        n = self.metrics["messages_processed"]
        current_avg = self.metrics["avg_processing_time"]
        self.metrics["avg_processing_time"] = (current_avg * (n - 1) + processing_time) / n

    async def send_policy_message(
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

        await self.publish_message(message, TopicId("default", self.id.key))

    async def get_memory_context(self, limit: int = 10) -> str:
        """Get recent context from memory."""
        if limit < 0:
            raise ValueError("limit must be non-negative")
        recent_memories = self.memory.content[-limit:] if limit else []

        context_parts = []
        for memory in recent_memories:
            if isinstance(memory.content, str):
                context_parts.append(memory.content)

        return "\n".join(context_parts)

    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics."""
        return {
            **self.metrics,
            "memory_size": len(self.memory.content),
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
        raise NotImplementedError("Persistent state storage is not configured")

    async def restore_state(self):
        """Restore agent state."""
        raise NotImplementedError("Persistent state storage is not configured")


class ReactiveAgent(PolicyAgentBase):
    """Base class for reactive agents that respond to events."""

    def __init__(self, agent_type: AgentType, name: str, **kwargs):
        super().__init__(agent_type, name, **kwargs)
        self.event_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self.triggers: List[Dict[str, Any]] = []

    def register_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Register an event handler."""
        self.event_handlers[event_type] = handler
        self.logger.debug(f"Registered handler for {event_type}")

    def add_trigger(self, condition: Dict[str, Any], action: Callable[[Dict[str, Any]], Awaitable[None]]):
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
        self._scheduled_tasks: set[asyncio.Task[None]] = set()

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
        """Mark this agent ready to own scheduled work."""
        await self.start()

    async def schedule_task(self, coro: Coroutine[Any, Any, None], delay: float = 0):
        """Schedule work whose completion and cancellation belong to this agent."""
        started = False
        async def run():
            nonlocal started
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                started = True
                await coro
            finally:
                if not started:
                    coro.close()
        task = asyncio.create_task(run())
        self._scheduled_tasks.add(task)
        def completed(task: asyncio.Task[None]) -> None:
            if not started:
                coro.close()
            self._scheduled_tasks.discard(task)
            if not task.cancelled():
                error = task.exception()
                if error is not None:
                    self.logger.error(
                        "Scheduled task failed: %s", error,
                        exc_info=(type(error), error, error.__traceback__),
                    )
        task.add_done_callback(completed)

    async def stop(self):
        tasks, self._scheduled_tasks = self._scheduled_tasks, set()
        for task in tasks:
            task.cancel()
        if tasks:
            with fail_after(5, shield=True):
                results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(
                        "Scheduled task failed: %s", result,
                        exc_info=(type(result), result, result.__traceback__),
                    )
        await super().stop()
