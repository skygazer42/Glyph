"""Simple conversational agents for greetings/farewells and clarifications."""

from __future__ import annotations

import random
from typing import List
from uuid import uuid4

from app.models.base import FinalAnswer


class DialogueAgent:
    """Template-driven responses for greeting/ farewell/ chit-chat intents."""

    RESPONSES = {
        "greeting": [
            "您好，我是政策智能助手，很高兴为您服务！",
            "您好，欢迎咨询政策问题，我可以协助查条件、流程和补贴计算。",
        ],
        "farewell": [
            "感谢使用政策智能助手，如需帮助随时再来！",
            "祝您工作顺利，若有新的问题欢迎继续咨询。",
        ],
        "chit_chat": [
            "我主要负责政策问答，有关条件、流程、补贴等都可以问我哦。",
            "您好，我可以帮助您理解政策、计算补贴或查办理方式，需要我做什么？",
        ],
    }

    def respond(self, intent: str) -> FinalAnswer:
        options: List[str] = self.RESPONSES.get(intent, self.RESPONSES["chit_chat"])
        answer = random.choice(options)
        return FinalAnswer(
            query_id=uuid4(),
            answer=answer,
            sources=[],
            confidence=0.9,
            verification_passed=True,
            metadata={"route": "dialogue", "intent": intent},
            total_processing_time=0.0,
        )


class ClarifierAgent:
    """Asks follow-up questions when intent is unclear."""

    QUESTIONS = [
        "请问您更关注申请资格、办理流程还是补贴金额？",
        "为了更准确回答，能否说明所在地区或政策名称？",
        "想确认一下，您是想了解补贴标准、计算方式还是申报要求？",
    ]

    def ask(self, original_query: str) -> FinalAnswer:
        question = random.choice(self.QUESTIONS)
        answer = f"为了更准确地回答“{original_query}”，需要进一步确认：{question}"
        return FinalAnswer(
            query_id=uuid4(),
            answer=answer,
            sources=[],
            confidence=0.4,
            verification_passed=False,
            metadata={"route": "clarification"},
            total_processing_time=0.0,
        )
