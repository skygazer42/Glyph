"""
LLM-based intent classifier using Autogen AgentChat AssistantAgent.
"""

import json
from typing import Optional, Dict

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from .prompt import intent_system_instruction, intent_user_prompt
from app.core.llms import model_client as GLOBAL_MODEL_CLIENT
from app.core import logging_manager

GLOBAL_MODEL_CTX = None


class LLMIntentClassifier:
    def __init__(self):
        self._client = None
        self._assistant = None

    async def _ensure(self):
        if self._client is None:
            self._client = GLOBAL_MODEL_CLIENT
        if self._assistant is None:
            self._assistant = AssistantAgent(
                name="intent_router",
                system_message=intent_system_instruction(),
                model_client=self._client,
                model_context=GLOBAL_MODEL_CTX,
            )

    async def classify(self, query: str) -> Optional[Dict]:
        await self._ensure()
        user = intent_user_prompt(query)
        messages = [
            {"role": "system", "content": intent_system_instruction()},
            {"role": "user", "content": user},
        ]
        logging_manager.log_llm_stream_start(messages=messages)
        resp = await self._assistant.on_messages(
            [TextMessage(content=user, source="user")],
            CancellationToken(),
        )
        text = resp.chat_message.to_text().strip()
        logging_manager.log_llm_stream_end(
            response={"content": text},
            prompt_tokens=0,
            completion_tokens=0,
        )
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "intent" in data:
                logging_manager.log_llm_call(
                    messages=messages,
                    response={"content": text},
                    prompt_tokens=0,
                    completion_tokens=0,
                    intent=data.get("intent"),
                )
                return data
        except Exception:
            pass
        return None
