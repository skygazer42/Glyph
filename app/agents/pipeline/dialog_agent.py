"""Simple conversational agents for greetings/farewells and clarifications."""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from app.models.base import FinalAnswer


class DialogueAgent:
    """Template-driven responses for greeting/ farewell/ chit-chat intents."""

    RESPONSES = {
        "greeting": [
            "您好，我是政策智能助手，欢迎咨询政策问题，我可以协助查条件、流程和补贴计算。很高兴为您服务！",
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

    def ask(
        self,
        original_query: str,
        domain_meta: Optional[Dict[str, Any]] = None,
    ) -> FinalAnswer:
        """
        版本 A：根据缺失槽位选择固定模板，不调用 LLM。

        - 先用启发式判断领域（家电以旧换新 / 消费券 / 汽车购车补贴 / 新车首保券）。
        - 再根据问题中已出现的信息推断已填槽位，生成缺失槽位集合。
        - 按领域 + 缺失槽位返回对应追问模版，兜底时回退到通用模版。
        """
        domain = self._detect_domain(original_query, domain_meta)
        missing = self._detect_missing_slots(domain, original_query, domain_meta)
        answer = self._build_message(domain, missing)
        return FinalAnswer(
            query_id=uuid4(),
            answer=answer,
            sources=[],
            confidence=0.4,
            verification_passed=False,
            metadata={"route": "clarification"},
            total_processing_time=0.0,
        )

    def _detect_domain(self, query: str, domain_meta: Optional[Dict[str, Any]]) -> str:
        text = (query or "").strip()
        meta_keywords = (domain_meta or {}).get("keywords") or []
        meta_joined = "".join(str(k) for k in meta_keywords)
        haystack = text + meta_joined

        if "家电" in haystack or "以旧换新" in haystack:
            return "appliance_subsidy"
        if "消费券" in haystack or "零售" in haystack or "餐饮" in haystack:
            return "retail_coupon"
        if "首保" in haystack or "商业保险" in haystack:
            return "auto_first_service_coupon"
        if any(kw in haystack for kw in ["汽车", "乘用车", "购车", "新车"]):
            return "auto_purchase_subsidy"
        return "generic"

    def _detect_missing_slots(
        self,
        domain: str,
        query: str,
        domain_meta: Optional[Dict[str, Any]],
    ) -> Set[str]:
        text = (query or "").strip()
        keywords = (domain_meta or {}).get("keywords") or []
        joined = text + "".join(str(k) for k in keywords)

        all_slots: Set[str] = set()
        present: Set[str] = set()

        if domain == "appliance_subsidy":
            all_slots = {"product", "energy", "price"}
            product_kws = [
                "空调",
                "冰箱",
                "洗衣机",
                "电视",
                "净水器",
                "洗碗机",
                "电脑",
                "热水器",
                "油烟机",
                "家用灶具",
            ]
            if any(kw in joined for kw in product_kws):
                present.add("product")
            energy_tags = ["1级", "一级", "2级", "二级", "能效", "水效"]
            if any(tag in joined for tag in energy_tags):
                present.add("energy")
            if re.search(r"\d+(?:\.\d+)?\s*元", joined):
                present.add("price")

        elif domain == "retail_coupon":
            all_slots = {"scene", "order_amount"}
            scene_kws = [
                "零售",
                "商超",
                "超市",
                "便利店",
                "食品零售",
                "餐饮",
                "饭店",
                "餐厅",
                "酒店",
            ]
            if any(kw in joined for kw in scene_kws):
                present.add("scene")
            if re.search(r"\d+(?:\.\d+)?\s*元", joined):
                present.add("order_amount")

        elif domain == "auto_purchase_subsidy":
            all_slots = {"car_type", "invoice_price"}
            car_type_kws = [
                "新能源汽车",
                "新能源车",
                "纯电",
                "电动车",
                "插电式混合动力",
                "混动",
                "燃油车",
                "油车",
            ]
            if any(kw in joined for kw in car_type_kws):
                present.add("car_type")
            if re.search(r"\d+(?:\.\d+)?\s*(万|万元|元)", joined):
                present.add("invoice_price")

        elif domain == "auto_first_service_coupon":
            all_slots = {"insurance_amount"}
            if "保险" in joined or "保单" in joined:
                if re.search(r"\d+(?:\.\d+)?\s*元", joined):
                    present.add("insurance_amount")

        # generic 域不做细分，返回空集合以触发通用提示
        if not all_slots:
            return set()
        return all_slots - present

    def _build_message(self, domain: str, missing: Set[str]) -> str:
        # 家电以旧换新补贴
        if domain == "appliance_subsidy":
            if not missing or missing == {"product", "energy", "price"}:
                return (
                    "为了准确判断家电以旧换新补贴资格，请补充以下信息：\n"
                    "1. 计划购买的具体家电类别（如空调/冰箱/洗衣机等）；\n"
                    "2. 产品的能效或水效等级（1级或2级）；\n"
                    "3. 含税购买价格（发票金额，单位：元）。"
                )
            lines: List[str] = ["为了准确判断家电以旧换新补贴资格，请补充："]
            if "product" in missing:
                lines.append("1. 计划购买的具体家电类别（如空调/冰箱/洗衣机等）；")
            if "energy" in missing:
                lines.append("2. 产品的能效或水效等级（1级或2级）；")
            if "price" in missing:
                lines.append("3. 含税购买价格（发票金额，单位：元）。")
            return "\n".join(lines)

        # 零售 / 餐饮消费券
        if domain == "retail_coupon":
            if not missing or missing == {"scene", "order_amount"}:
                return (
                    "为了判断您是否满足“泉城购”零售/餐饮消费券的使用条件，请补充：\n"
                    "1. 准备在哪一类场景消费（零售商超、便利店，还是餐饮门店/酒店餐厅）；\n"
                    "2. 单笔预计消费金额（元）。"
                )
            lines = ["为了判断您能否使用消费券，请补充："]
            if "scene" in missing:
                lines.append("1. 本次消费属于零售（商超/便利店等）还是餐饮（餐厅/酒店餐厅）；")
            if "order_amount" in missing:
                lines.append("2. 本次单笔预计消费金额（元）。")
            return "\n".join(lines)

        # 汽车购车补贴
        if domain == "auto_purchase_subsidy":
            if not missing or missing == {"car_type", "invoice_price"}:
                return (
                    "为了判断您是否符合汽车消费补贴条件，请补充：\n"
                    "1. 所购车辆类型（新能源汽车还是燃油车）；\n"
                    "2. 机动车销售统一发票上的购车金额（不含装潢、挂牌等费用，单位：元）。"
                )
            lines = ["为了判断您是否符合汽车消费补贴条件，请补充："]
            if "car_type" in missing:
                lines.append("1. 所购车辆类型（新能源汽车还是燃油车）；")
            if "invoice_price" in missing:
                lines.append("2. 机动车销售统一发票上的购车金额（不含装潢、挂牌等费用，单位：元）。")
            return "\n".join(lines)

        # 新车首保消费券
        if domain == "auto_first_service_coupon":
            if not missing or "insurance_amount" in missing:
                return (
                    "为了判断您可领取的新车首保消费券面额，请补充车辆商业保险金额（保单金额，单位：元）。"
                )

        # 通用兜底提示：领域无法判断或槽位无法分类时使用
        return (
            "为了更准确回答您的问题，请补充更具体的信息，例如涉及的具体政策名称、地区、产品/服务类型和金额等。"
        )
