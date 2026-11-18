"""
LLM-based intent classifier using Autogen AgentChat AssistantAgent.
"""

import asyncio
from typing import Literal

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .prompt import INTENT_SYSTEM_INSTRUCTION, build_intent_user_prompt
from app.core.llms import model_client as GLOBAL_MODEL_CLIENT
from app.core.logging_manager import logging_manager

class IntentPrediction(BaseModel):
    """The exact JSON fields requested from the intent model."""

    model_config = ConfigDict(extra="ignore")

    intent: Literal["greeting", "farewell", "chit_chat", "calculation", "comparison",
                    "summary", "policy_inquiry", "clarification"]
    sub_intent: Literal["eligibility", "benefit", "process", "deadline", "documents",
                        "contact", "region", "limit", "exception"] | None
    confidence: float = Field(ge=0, le=1, strict=True, allow_inf_nan=False)
    chains: list[Literal["chat_chain", "calculation_chain", "comparison_chain",
                         "kb_chain", "graph_chain", "hybrid_chain"]]
    requires_parallel: StrictBool


class LLMIntentClassifier:
    def __init__(self, model_client=None):
        self._client = model_client
        self._assistant = None
        self._lock = asyncio.Lock()

    def _get_assistant(self) -> AssistantAgent:
        if self._client is None:
            self._client = GLOBAL_MODEL_CLIENT
        if self._assistant is None:
            self._assistant = AssistantAgent(
                name="intent_router",
                description="Classifies user intent for routing decisions.",
                system_message=INTENT_SYSTEM_INSTRUCTION,
                model_client=self._client,
            )
        return self._assistant

    async def classify(self, query: str) -> IntentPrediction:
        async with self._lock:
            return await self._classify(query)

    async def _classify(self, query: str) -> IntentPrediction:
        assistant = self._get_assistant()
        user = build_intent_user_prompt(query)
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_INSTRUCTION},
            {"role": "user", "content": user},
        ]
        logging_manager.log_llm_stream_start(messages=messages)
        resp = await assistant.on_messages(
            [TextMessage(content=user, source="user")],
            CancellationToken(),
        )
        text = resp.chat_message.to_text().strip()
        logging_manager.log_llm_stream_end(
            response={"content": text},
            prompt_tokens=0,
            completion_tokens=0,
        )
        prediction = IntentPrediction.model_validate_json(text)
        logging_manager.log_llm_call(
            messages=messages,
            response={"content": text},
            prompt_tokens=0,
            completion_tokens=0,
            intent=prediction.intent,
        )
        return prediction
