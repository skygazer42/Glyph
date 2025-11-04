"""
LLM-based intent classifier using Autogen AgentChat AssistantAgent.
"""

import json
from typing import Optional, Dict

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from .prompt import intent_system_instruction, intent_user_prompt
from ..common.model_client import create_openai_client, create_buffered_context


class LLMIntentClassifier:
    def __init__(self):
        self._client = None
        self._assistant = None

    async def _ensure(self):
        if self._client is None:
            self._client = create_openai_client()
        if self._assistant is None:
            self._assistant = AssistantAgent(
                name="intent_router",
                system_message=intent_system_instruction(),
                model_client=self._client,
                model_context=create_buffered_context(10),
            )

    async def classify(self, query: str) -> Optional[Dict]:
        await self._ensure()
        user = intent_user_prompt(query)
        resp = await self._assistant.on_messages(
            [TextMessage(content=user, source="user")],
            CancellationToken(),
        )
        text = resp.chat_message.to_text().strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "intent" in data:
                return data
        except Exception:
            pass
        return None

