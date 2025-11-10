"""
聊天Agent - 处理日常对话和问候
"""

import asyncio
import logging
import random
from typing import Dict, Any
from datetime import datetime

from autogen_core import MessageContext
from autogen_agentchat.messages import TextMessage

from app.agents.framework.base.base_agent import PolicyAgentBase
from app.models.base import UUID, BaseModel, Field


class ChatResponse(BaseModel):
    """聊天响应"""
    response_text: str
    response_type: str  # greeting, farewell, introduction, casual
    emotion: str = "neutral"  # friendly, professional, helpful
    follow_up_suggestions: list = Field(default_factory=list)


class ChatAgent(PolicyAgentBase):
    """聊天Agent - 处理日常对话"""

    def __init__(self, **kwargs):
        super().__init__(
            agent_type="chat_agent",
            name="ChatAgent",
            description="处理日常问候、闲聊和系统介绍",
            **kwargs
        )

        # 响应模板
        self.response_templates = {
            "greeting": [
                "您好！我是Gove政策智能助手，有什么可以帮助您的吗？",
                "您好！很高兴为您服务，请问您想了解哪方面的政策信息？",
                "欢迎！我是您的政策咨询助手，有什么问题请随时提问。",
                "您好！我可以帮您查询各种政策信息，请问有什么需要帮助的吗？"
            ],
            "farewell": [
                "感谢您的使用，祝您生活愉快！",
                "再见！如果您还有其他问题，随时可以咨询我。",
                "谢谢您的信任，期待下次为您服务！",
                "再见！记得有政策问题可以随时找我哦。"
            ],
            "introduction": [
                "我是Gove政策智能问答系统，可以帮您查询各种政府政策信息，包括补贴申请、流程办理、材料准备等。",
                "我专门负责解答政策相关的问题，拥有济南市的最新政策数据库，可以为您提供准确的政策咨询。",
                "作为您的政策助手，我可以帮您：\n1. 查询补贴政策和申请条件\n2. 了解申请流程和所需材料\n3. 计算补贴金额\n4. 比较不同政策\n\n请问有什么可以帮助您的？"
            ],
            "casual": [
                "我主要是政策咨询助手，如果您有政策相关问题，我很乐意为您解答。",
                "虽然我很想和您聊天，但我更擅长帮您解决政策问题哦。",
                "有什么政策想了解的吗？我可是政策专家呢！",
                "让我们聊点政策相关的话题吧，这样我能更好地帮助您。"
            ]
        }

        # 情绪映射
        self.emotion_mapping = {
            "greeting": "friendly",
            "farewell": "professional",
            "introduction": "helpful",
            "casual": "friendly"
        }

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> ChatResponse:
        """处理聊天请求"""
        query_text = request.get("text", "")
        response_type = request.get("response_type", "casual")
        intent = request.get("intent", "casual_chat")

        self.logger.info(f"Chat request: {query_text[:30]}... (type: {response_type})")

        try:
            # 生成响应
            response_text = self._generate_response(query_text, response_type, intent)

            # 获取情绪
            emotion = self.emotion_mapping.get(response_type, "neutral")

            # 生成后续建议
            follow_ups = self._generate_follow_up_suggestions(response_type)

            return ChatResponse(
                response_text=response_text,
                response_type=response_type,
                emotion=emotion,
                follow_up_suggestions=follow_ups
            )

        except Exception as e:
            self.logger.error(f"Error in chat response: {e}")
            return ChatResponse(
                response_text="抱歉，我遇到了一些问题。请尝试重新提问或联系管理员。",
                response_type="error",
                emotion="neutral"
            )

    def _generate_response(self, query_text: str, response_type: str, intent: str) -> str:
        """生成响应文本"""
        # 如果有特定的响应模板
        if response_type in self.response_templates:
            templates = self.response_templates[response_type]
            base_response = random.choice(templates)

            # 添加一些个性化
            if "你好" in query_text or "hello" in query_text.lower():
                base_response += " 今天天气不错，适合咨询政策问题呢！"
            elif "谢谢" in query_text or "感谢" in query_text:
                base_response = "不客气！" + base_response

            return base_response

        # 默认响应
        return "您好！我是政策智能助手，有什么政策问题需要了解吗？"

    def _generate_follow_up_suggestions(self, response_type: str) -> list:
        """生成后续建议"""
        if response_type == "greeting":
            return [
                "查询补贴政策",
                "了解申请流程",
                "咨询申请条件",
                "计算补贴金额"
            ]
        elif response_type == "introduction":
            return [
                "家电以旧换新补贴",
                "汽车消费补贴",
                "消费券使用",
                "创业扶持政策"
            ]
        elif response_type == "casual":
            return [
                "我想申请补贴",
                "申请材料有哪些",
                "补贴标准是多少",
                "去哪里申请"
            ]
        else:
            return []

    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type,
            "name": self.name,
            "response_types": len(self.response_templates)
        }
