"""Query rewriting agent to normalize user inputs before routing."""

from __future__ import annotations

import logging
from autogen_core.models import UserMessage

from app.core.llms import model_client


class RewriteAgent:
    """Lightweight agent that rewrites user queries into clearer business wording."""

    def __init__(self, max_length: int = 256) -> None:
        self.logger = logging.getLogger(__name__)
        self.max_length = max_length

    async def rewrite(self, query: str) -> str:
        prompt = (
            "请将以下用户问题改写成更清晰、专业、便于业务理解的表述，"
            "保持原意不变，补齐缺失的主体/对象信息，如不确定请保留原词。"
            "禁止输出解释或多余文字，只返回改写后的句子。\n\n"
            f"原始问题：{query.strip()}"
        )

        try:
            response = await model_client.create(
                [UserMessage(content=prompt[: self.max_length * 4], source="user")]
            )
            text = (response.content or "").strip()
            if not text:
                return query
            return text[: self.max_length]
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.warning("Rewrite agent failed: %s", exc)
            return query
