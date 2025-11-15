"""Lightweight per-session memory helpers for multi-turn QA.

Captures three kinds of information:
- topic: recent policy/topic hint (e.g., "济南市2025年家电以旧换新补贴政策")
- slots: product category / energy_level / price extracted from Q&A
- sources: last policy source titles/links (for better rewrites or display)

Design goals:
- Cheap (regex + simple rules). Optional LLM can be added later.
- Non-invasive: stored under session context path context['memory'].
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


CATEGORY_WORDS = [
    "空调", "冰箱", "洗衣机", "电视", "电脑", "热水器", "家用灶具", "吸油烟机",
    "净水器", "洗碗机", "微波炉", "电饭煲", "家电"
]


def get_memory(context: Dict[str, Any]) -> Dict[str, Any]:
    mem = context.get("memory") or {}
    if not isinstance(mem, dict):
        mem = {}
    mem.setdefault("topic", "")
    mem.setdefault("slots", {"category": "", "energy_level": "", "price": ""})
    mem.setdefault("sources", [])
    return mem


def set_memory(context: Dict[str, Any], mem: Dict[str, Any]) -> None:
    context["memory"] = mem


def extract_slots_from_text(text: str) -> Dict[str, str]:
    text = text or ""
    cat = ""
    for w in CATEGORY_WORDS:
        if w in text:
            cat = w
            break
    # 能效/水效：匹配 1级/一级/2级/二级/能效/水效
    eng = ""
    m = re.search(r"([12]级|[一二]级).{0,4}(能效|水效)|(?:能效|水效)[^\n]{0,6}([12]级|[一二]级)", text)
    if m:
        # 统一输出 1级/2级
        raw = "".join([g or "" for g in m.groups()])
        if "一" in raw:
            eng = "1级"
        elif "二" in raw:
            eng = "2级"
        elif "1" in raw:
            eng = "1级"
        elif "2" in raw:
            eng = "2级"
    # 价格：匹配 8000元/￥8000/8,000元
    price = ""
    m = re.search(r"(?:￥|¥)?\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)(?:\.\d+)?\s*元", text)
    if m:
        price = m.group(1).replace(",", "")
    return {"category": cat, "energy_level": eng, "price": price}


def extract_topic_from_sources(sources: List[Dict[str, Any]] | Any) -> str:
    if not sources:
        return ""
    # Try the first source title
    try:
        s0 = sources[0]
        title = getattr(s0, "title", None) or s0.get("title")
        if title:
            return str(title)[:80]
    except Exception:
        pass
    return ""


def update_memory(context: Dict[str, Any], final: Any, intent: Dict[str, Any] | None = None) -> None:
    mem = get_memory(context)
    # update topic from metadata domain_context or sources
    topic = mem.get("topic") or ""
    dom = (final.metadata or {}).get("domain_context") if hasattr(final, "metadata") else None
    if isinstance(dom, dict):
        # prefer keywords/policy oriented hints if available
        kws = dom.get("keywords") or []
        if not topic and kws:
            topic = "、".join(kws[:3])
    if not topic:
        topic = extract_topic_from_sources(getattr(final, "sources", None)) or topic
    mem["topic"] = topic

    # update slots from answer text or metadata
    text = getattr(final, "answer", "") or ""
    new_slots = extract_slots_from_text(text)
    cur = mem.get("slots", {})
    for k, v in new_slots.items():
        if v and not cur.get(k):
            cur[k] = v
    mem["slots"] = cur

    # update sources titles (at most 3)
    srcs = []
    for s in (getattr(final, "sources", []) or [])[:3]:
        try:
            srcs.append({"title": getattr(s, "title", None) or s.get("title", "")})
        except Exception:
            continue
    if srcs:
        mem["sources"] = srcs

    set_memory(context, mem)


def slot_carry_over(context: Dict[str, Any], query_text: str) -> Dict[str, str]:
    """Provide missing slots using memory for the current query.

    If user asks a follow-up like "我是否符合补贴资格?", we can reuse
    known slots (category/energy/price) captured from prior turns.
    """
    mem = get_memory(context)
    slots = mem.get("slots", {})
    # If current query already contains slot values, don't override
    cur = extract_slots_from_text(query_text or "")
    result = {}
    for k in ("category", "energy_level", "price"):
        if cur.get(k):
            result[k] = cur[k]
        elif slots.get(k):
            result[k] = slots[k]
        else:
            result[k] = ""
    return result

