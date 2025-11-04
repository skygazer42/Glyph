"""
Clarifier agent: ask a clarifying question when the intent is ambiguous or low confidence.
"""

from typing import Dict, Any

from autogen_core import MessageContext

from ..base.base_agent import PolicyAgentBase
from ...models.base import AgentType


class ClarifierAgent(PolicyAgentBase):
    def __init__(self, **kwargs):
        super().__init__(
            agent_type=AgentType.COORDINATOR,
            name="Clarifier",
            description="当意图不明确时提出澄清问题",
            **kwargs,
        )

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> Dict[str, Any]:
        query = request.get("query", "")
        # 简单启发式澄清（可替换为 LLM 提示）
        candidates = [
            "您更关心申请条件、办理流程还是截止时间？",
            "请问需要我计算补贴金额，还是帮您比较不同政策？",
            "您想了解哪些地区/部门的政策？",
        ]
        return {
            "question": candidates[0],
            "original_query": query,
        }

