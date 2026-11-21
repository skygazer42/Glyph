"""
Clarifier agent: ask a clarifying question when the intent is ambiguous or low confidence. 需要追问
"""

from typing import Dict, Any

from autogen_core import MessageContext

from app.agents.framework.base.base_agent import PolicyAgentBase
from app.models.policy import AgentType


class ClarifierAgent(PolicyAgentBase):
    """在意图需澄清时返回固定追问，保留用户原问题供后续轮次使用。"""

    def __init__(self, **kwargs):
        super().__init__(
            agent_type=AgentType.COORDINATOR,
            name="Clarifier",
            description="当意图不明确时提出澄清问题",
            **kwargs,
        )

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> Dict[str, Any]:
        """读取必需 query 字段，返回追问和 original_query，不执行知识检索。"""
        query = request["query"]
        return {
            "question": "您更关心申请条件、办理流程还是截止时间？",
            "original_query": query,
        }
