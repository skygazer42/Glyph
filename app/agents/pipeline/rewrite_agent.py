"""Query rewriting agent to normalize user inputs before routing."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict

from autogen_core.models import UserMessage

from app.core.llms import model_client
from app.agents.domain import PolicyDomainContextBuilder


@dataclass
class ContextHints:
    topic: str = ""
    product: str = ""
    energy: str = ""
    price: str = ""
    intent: str = ""

    def missing_slots(self) -> list[str]:
        if self.intent not in {"eligibility", "calculation"}:
            return []
        missing: list[str] = []
        if not self.product:
            missing.append("产品类别")
        if not self.energy:
            missing.append("能效/水效等级")
        if not self.price:
            missing.append("价格")
        return missing


class RewriteAgent:
    """Lightweight agent that rewrites user queries into clearer business wording."""

    PRODUCT_KEYWORDS = [
        "空调",
        "冰箱",
        "洗衣机",
        "电视",
        "家电",
        "净水器",
        "洗碗机",
        "电脑",
        "热水器",
        "油烟机",
        "家用灶具",
        "汽车",
        "手机",
        "消费券",
    ]

    def __init__(self, max_length: int = 256) -> None:
        self.logger = logging.getLogger(__name__)
        self.max_length = max_length
        self._domain_builder = PolicyDomainContextBuilder()
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_max = 256

    async def rewrite(self, query: str, context: dict | None = None, domain_hint: dict | None = None) -> str:
        key = query.strip()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        ctx = self._domain_builder.build(query)
        normalized = ctx.normalized_query.strip()
        context_hints = self._build_context_hints(context, query)
        topic_hint = context_hints.topic or self._topic_hint_from_history(context)
        if topic_hint and topic_hint not in normalized:
            normalized = f"{topic_hint} {normalized}".strip()

        has_price = bool(re.search(r"\d", normalized))
        has_grade = any(tag in normalized for tag in ["1级", "一级", "2级", "二级", "能效", "水效"])
        has_policy_kw = bool(ctx.keywords) or bool(topic_hint)
        if len(normalized) <= 64 or (has_policy_kw and (has_price or has_grade)):
            result = self._compose_standalone(normalized, context_hints)[: self.max_length]
            self._remember(key, result)
            return result

        domain_hints = self._build_domain_hint(ctx)
        if topic_hint and topic_hint not in domain_hints:
            domain_hints = (
                domain_hints
                + ("；" if domain_hints and domain_hints != "无" else "")
                + f"主题={topic_hint}"
            )
        summary = self._format_context_summary(context_hints)
        prompt = (
            "请将以下用户问题改写成更清晰、专业、便于政务/政策业务逻辑匹配的‘自包含单句问题’，"
            "保留或补齐关键主体（城市、政策名称、产品类别、金额、时间范围等），"
            "若检测到领域关键词，必须在改写后的句子中以规范词形呈现；"
            "不要臆造事实，无法确认的字段保持原词。禁止输出任何解释，只返回改写后的单句问题。\n\n"
            f"领域提示：{domain_hints}\n"
            f"上下文摘要：\n{summary}\n"
            f"原始问题：{normalized}"
        )

        try:
            response = await model_client.create(
                [UserMessage(content=prompt[: self.max_length * 4], source="user")]
            )
            text = (response.content or "").strip()
            if not text:
                self._remember(key, normalized)
                return self._compose_standalone(normalized, context_hints)[: self.max_length]
            result = self._compose_standalone(text, context_hints)[: self.max_length]
            self._remember(key, result)
            return result
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.warning("Rewrite agent failed: %s", exc)
            result = self._compose_standalone(normalized, context_hints)[: self.max_length]
            self._remember(key, result)
            return result

    def _build_context_hints(self, context: dict | None, query: str) -> ContextHints:
        hints = ContextHints()
        if context:
            topic = self._topic_hint_from_history(context)
            if topic:
                hints.topic = topic[:80]
            history = context.get("history") or []
            for item in history:
                text = (item.get("text") or "").strip()
                if not text or item.get("type") != "query":
                    continue
                slots = self._extract_slots(text)
                hints.product = hints.product or slots.get("product", "")
                hints.energy = hints.energy or slots.get("energy", "")
                hints.price = hints.price or slots.get("price", "")

        current_slots = self._extract_slots(query)
        hints.product = hints.product or current_slots.get("product", "")
        hints.energy = hints.energy or current_slots.get("energy", "")
        hints.price = hints.price or current_slots.get("price", "")
        hints.intent = self._infer_intent(query)
        return hints

    def _extract_slots(self, text: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        if not text:
            return result
        for kw in self.PRODUCT_KEYWORDS:
            if kw in text:
                result["product"] = kw
                break
        energy_match = re.search(r"([12一二]级[^，。；\s]{0,4}(?:能效|水效)|能效[12一二]级)", text)
        if energy_match:
            result["energy"] = energy_match.group(1)
        price_match = re.search(r"(\d+(?:\.\d+)?\s*元)", text)
        if price_match:
            result["price"] = price_match.group(1)
        return result

    def _infer_intent(self, text: str) -> str:
        if not text:
            return "inquiry"
        if any(kw in text for kw in ["补贴多少", "能补贴", "怎么算", "金额", "折算"]):
            return "calculation"
        if any(kw in text for kw in ["是否符合", "有没有资格", "能否享受", "符合条件"]):
            return "eligibility"
        if any(kw in text for kw in ["流程", "怎么办", "如何申请", "需要什么", "哪些材料", "怎么操作"]):
            return "process"
        return "inquiry"

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

    def _format_context_summary(self, hints: ContextHints) -> str:
        lines: list[str] = []
        if hints.topic:
            lines.append(f"- 主题: {hints.topic}")
        if hints.intent:
            lines.append(f"- 问题类型: {hints.intent}")
        if hints.product:
            lines.append(f"- 产品: {hints.product}")
        if hints.energy:
            lines.append(f"- 能效/水效: {hints.energy}")
        if hints.price:
            lines.append(f"- 价格: {hints.price}")
        missing = hints.missing_slots()
        if missing:
            lines.append("- 待补信息: " + "、".join(missing))
        return "\n".join(lines) if lines else "- (无额外上下文)"

    def _compose_standalone(self, question: str, hints: ContextHints) -> str:
        q = question.strip()
        supplements: list[str] = []
        if hints.topic and hints.topic not in q:
            supplements.append(f"主题：{hints.topic}")
        if hints.product and hints.product not in q:
            supplements.append(f"产品：{hints.product}")
        if hints.energy and hints.energy not in q:
            supplements.append(f"能效/水效：{hints.energy}")
        if hints.price and hints.price not in q:
            supplements.append(f"价格：{hints.price}")
        missing = hints.missing_slots()
        if missing:
            supplements.append("待补充：" + "、".join(missing))
        if supplements:
            return f"{q}（{'；'.join(supplements)}）"
        return q

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
        for item in reversed(history):
            if item.get("type") != "query":
                continue
            text = (item.get("text") or "").strip()
            if any(k in text for k in keywords):
                return text[:50]
        for item in reversed(history):
            if item.get("type") != "answer":
                continue
            text = (item.get("text") or "").strip()
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("- ") and ("细则" in line or "消费券" in line or "活动" in line):
                    return line[2:80]
        return ""
