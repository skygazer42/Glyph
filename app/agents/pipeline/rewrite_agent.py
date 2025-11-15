"""Query rewriting agent to normalize user inputs before routing."""

from __future__ import annotations

import logging
from autogen_core.models import UserMessage

from app.core.llms import model_client
from app.agents.domain import PolicyDomainContextBuilder
from collections import OrderedDict


class RewriteAgent:
    """Lightweight agent that rewrites user queries into clearer business wording."""

    def __init__(self, max_length: int = 256) -> None:
        self.logger = logging.getLogger(__name__)
        self.max_length = max_length
        self._domain_builder = PolicyDomainContextBuilder()
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_max = 256

    async def rewrite(self, query: str, context: dict | None = None, domain_hint: dict | None = None) -> str:
        # cache
        key = query.strip()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        # fast-path: normalize only, avoid LLM for short/structured queries
        ctx = self._domain_builder.build(query)
        normalized = ctx.normalized_query.strip()
        topic_hint = self._topic_hint_from_history(context)
        # If query already contains product/price/grade or is short, skip LLM
        has_price = any(tok in normalized for tok in ["元", "￥"]) or any(ch.isdigit() for ch in normalized)
        has_grade = any(tag in normalized for tag in ["1级", "一级", "2级", "二级", "能效", "水效"])
        has_policy_kw = bool(ctx.keywords)
        if len(normalized) <= 64 or (has_policy_kw and (has_price or has_grade)):
            result = self._compose_standalone(normalized, topic_hint)[: self.max_length]
            self._remember(key, result)
            return result

        domain_hints = self._build_domain_hint(ctx)
        if topic_hint:
            domain_hints = (domain_hints + ("；" if domain_hints and domain_hints != "无" else "") + f"主题={topic_hint}")
        prompt = (
            "请将以下用户问题改写成更清晰、专业、便于政务/政策业务逻辑匹配的‘自包含单句问题’，"
            "保留或补齐关键主体（城市、政策名称、产品类别、金额、时间范围等），"
            "若检测到领域关键词，必须在改写后的句子中以规范词形呈现；"
            "不要臆造事实，无法确认的字段保持原词。禁止输出任何解释，只返回改写后的单句问题。\n\n"
            f"领域提示：{domain_hints}\n"
            f"原始问题：{normalized}"
        )

        try:
            response = await model_client.create(
                [UserMessage(content=prompt[: self.max_length * 4], source="user")]
            )
            text = (response.content or "").strip()
            if not text:
                self._remember(key, normalized)
                return self._compose_standalone(normalized, topic_hint)[: self.max_length]
            result = self._compose_standalone(text, topic_hint)[: self.max_length]
            self._remember(key, result)
            return result
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.warning("Rewrite agent failed: %s", exc)
            result = self._compose_standalone(normalized, topic_hint)[: self.max_length]
            self._remember(key, result)
            return result

    def _build_domain_hint(self, ctx) -> str:
        if not ctx:
            return "无"
        req_tokens = []
        if ctx.region:
            req_tokens.append(f"地区={ctx.region}")
        if ctx.keywords:
            req_tokens.append("关键词=" + "、".join(ctx.keywords))
        if ctx.time_window and ctx.time_window.phrase:
            req_tokens.append(f"时间={ctx.time_window.phrase}")
        if not req_tokens and ctx.search_variants:
            req_tokens.append("参考表达=" + ctx.search_variants[0])
        return "；".join(req_tokens) if req_tokens else "无"

    def _remember(self, key: str, value: str) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def _topic_hint_from_history(self, context: dict | None) -> str:
        if not context:
            return ""
        history = context.get("history") or []
        keywords = ["政策", "细则", "消费券", "以旧换新", "首保", "汽车消费", "泉城购"]
        # 先看最近的用户问题里是否包含主题
        for item in reversed(history):
            if item.get("type") != "query":
                continue
            text = (item.get("text") or "").strip()
            if any(k in text for k in keywords):
                return text[:50]
        # 再从助手答案的来源行里提取
        for item in reversed(history):
            if item.get("type") != "answer":
                continue
            text = (item.get("text") or "").strip()
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("- ") and ("细则" in line or "消费券" in line or "活动" in line):
                    return line[2:80]
        return ""

    def _compose_standalone(self, question: str, topic_hint: str) -> str:
        q = question.strip()
        if not topic_hint:
            return q
        vague_cues = ["是否", "怎么", "如何", "哪些", "多少", "怎么办", "要什么", "需要什么"]
        if any(c in q for c in vague_cues) and topic_hint not in q:
            return f"{q}（关于：{topic_hint}）"
        return q
