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

    def ask(self, original_query: str) -> FinalAnswer:
        checklist = (
            "为了准确判断补贴资格，请补充以下信息：\n"
            "1. 计划购买的具体家电类别（如空调/冰箱/洗衣机等）；\n"
            "2. 产品的能效或水效等级（1级或2级）；\n"
            "3. 含税购买价格（发票金额，单位：元）。"
        )
        answer = f"针对“{original_query}”，我需要更多信息：\n{checklist}"
        return FinalAnswer(
            query_id=uuid4(),
            answer=answer,
            sources=[],
            confidence=0.4,
            verification_passed=False,
            metadata={"route": "clarification"},
            total_processing_time=0.0,
        )
