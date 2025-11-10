"""
Template registry utilities for the DSL generator.

This module knows how to:
1. Score structured policy data against available Jinja templates.
2. Backfill template-specific defaults so the rendered YAML stays consistent.
3. Normalize incoming data into the schema expected by each template.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import re


def _today_iso() -> str:
    """Return today's date in ISO format."""
    return datetime.now().strftime("%Y-%m-%d")


def _is_missing(value: Any) -> bool:
    """Determine whether a value should be treated as 'missing'."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        text = str(value).strip().replace("%", "")
        num = float(text)
        if "%" in str(value) or num > 1 and num <= 100:
            # interpret percentage strings as decimals
            return round(num / 100, 4)
        return num
    except (TypeError, ValueError):
        return None


@dataclass
class TemplateProfile:
    """Metadata for a single Jinja template."""

    name: str
    template_name: str
    keywords: List[str] = field(default_factory=list)
    field_signals: List[str] = field(default_factory=list)
    defaults_factory: Callable[[], Dict[str, Any]] = dict
    min_score: int = 2
    prepare: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    def score(self, data: Dict[str, Any], haystack: str) -> int:
        """Compute a heuristic score for how well the data matches this template."""
        score = 0

        lower_haystack = haystack.lower()
        for kw in self.keywords:
            kw_lower = kw.lower()
            if kw_lower and kw_lower in lower_haystack:
                score += 2

        for signal in self.field_signals:
            if TemplateRegistry.has_field(data, signal):
                score += 1

        return score


class TemplateRegistry:
    """Central place to reason about available templates."""

    def __init__(self, template_dir):
        self.template_dir = template_dir
        self.profiles: List[TemplateProfile] = self._build_profiles()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[TemplateProfile]:
        """Return the best matching template profile."""
        if not data:
            return None

        haystack = self._build_haystack(data, context)
        best_profile: Optional[TemplateProfile] = None
        best_score = 0

        for profile in self.profiles:
            score = profile.score(data, haystack)
            if score >= profile.min_score and score > best_score:
                best_profile = profile
                best_score = score

        return best_profile

    def get_profile_by_template(self, template_name: Optional[str]) -> Optional[TemplateProfile]:
        if not template_name:
            return None
        for profile in self.profiles:
            if profile.template_name == template_name:
                return profile
        return None

    def apply_defaults(self, data: Dict[str, Any], profile: Optional[TemplateProfile]) -> Dict[str, Any]:
        """Backfill defaults + normalize structure for the given template."""
        if not profile:
            return data

        merged = copy.deepcopy(data)
        defaults = profile.defaults_factory() if profile.defaults_factory else {}
        self._deep_fill(merged, defaults)

        if profile.prepare:
            merged = profile.prepare(merged)

        return merged

    # ------------------------------------------------------------------ #
    # Template metadata
    # ------------------------------------------------------------------ #

    def _build_profiles(self) -> List[TemplateProfile]:
        return [
            TemplateProfile(
                name="appliance",
                template_name="appliance_subsidy.yaml.j2",
                keywords=["家电", "以旧换新", "能效", "冰箱", "空调"],
                field_signals=["efficiency_rates", "category_limits", "per_item_cap"],
                defaults_factory=self._appliance_defaults,
                min_score=3,
                prepare=self._prepare_appliance_payload,
            ),
            TemplateProfile(
                name="auto",
                template_name="auto_subsidy.yaml.j2",
                keywords=["汽车", "购车", "车辆", "新车", "燃油", "新能源"],
                field_signals=["tiers", "vehicle_type", "matching.tiers"],
                defaults_factory=self._auto_defaults,
                min_score=3,
                prepare=self._prepare_auto_payload,
            ),
            TemplateProfile(
                name="consumer_coupon",
                template_name="consumer_coupon.yaml.j2",
                keywords=["消费券", "消费", "零售", "餐饮", "代金"],
                field_signals=["coupon_types", "distribution", "usage_limits"],
                defaults_factory=self._coupon_defaults,
                min_score=3,
                prepare=self._prepare_coupon_payload,
            ),
        ]

    # ------------------------------------------------------------------ #
    # Default factories
    # ------------------------------------------------------------------ #

    @staticmethod
    def _appliance_defaults() -> Dict[str, Any]:
        return {
            "name": "家电以旧换新补贴",
            "version": "1.0",
            "policy_source": {
                "doc_id": None,
                "title": "家电补贴政策",
                "clause": None,
            },
            "valid_period": {
                "start": _today_iso(),
                "end": None,
            },
            "efficiency_rates": {
                "base_rate": 0.15,
                "level_1_bonus": 0.05,
                "no_label_rate": 0.1,
            },
            "category_limits": {
                "per_category": {},
                "total_items": None,
            },
            "per_item_cap": 2000,
            "special_rules": {
                "trade_in_required": False,
                "stacking_allowed": True,
            },
        }

    @staticmethod
    def _auto_defaults() -> Dict[str, Any]:
        return {
            "name": "汽车消费补贴",
            "version": "1.0",
            "policy_source": {
                "doc_id": None,
                "title": "汽车消费补贴政策",
            },
            "windows": {
                "time_basis": "purchase_time",
                "purchase_window": {"start": _today_iso(), "end": None},
                "claim_window": {"start": _today_iso(), "end": None},
                "modify_window": {"start": _today_iso(), "end": None},
            },
            "budget": {
                "total": 0,
                "currency": "CNY",
                "allocation": "global",
            },
            "price_basis": "ex_tax",
            "eligibility": {
                "buyer_type": "person",
                "vehicle_scope": "all",
                "combinable_with_upper_policies": True,
            },
            "matching": {
                "powertrain_defs": {
                    "NEV": ["新能源", "纯电", "插混"],
                    "ICE": ["燃油", "混动"],
                },
                "tiers": [],
            },
            "limits": {
                "per_person_max_cars": 1,
                "dedupe_keys": ["buyer_id", "vin", "invoice_no"],
            },
        }

    @staticmethod
    def _coupon_defaults() -> Dict[str, Any]:
        return {
            "name": "消费券补贴活动",
            "version": "1.0",
            "policy_source": {
                "doc_id": None,
                "title": "消费券政策",
            },
            "valid_period": {
                "start": _today_iso(),
                "end": None,
            },
            "coupon_types": ["AMOUNT"],
            "tiers": [],
            "distribution": {
                "method": "auto_claim",
                "total_quota": None,
                "quota_per_person": None,
                "release_schedule": [],
            },
            "usage_limits": {
                "valid_days": 30,
                "merchant_scope": "参与活动商户",
                "product_scope": "全部商品",
                "stacking": {
                    "with_merchant_discount": True,
                    "with_other_coupons": True,
                },
            },
            "platform": {
                "claim_platform": None,
                "payment_methods": [],
            },
        }

    # ------------------------------------------------------------------ #
    # Prepare helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prepare_appliance_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        category_limits = data.setdefault("category_limits", {})
        per_category = category_limits.get("per_category")
        if not isinstance(per_category, dict):
            category_limits["per_category"] = {}
        category_limits["total_items"] = TemplateRegistry._normalize_number(
            category_limits.get("total_items")
        )

        cap = data.get("per_item_cap") or data.get("limits", {}).get("per_item_cap")
        numeric_cap = TemplateRegistry._normalize_number(cap)
        if numeric_cap is not None:
            data["per_item_cap"] = numeric_cap
        else:
            data["per_item_cap"] = 2000

        efficiency_rates = data.get("efficiency_rates", {})
        for key in ["base_rate", "level_1_bonus", "no_label_rate"]:
            if key in efficiency_rates:
                rate = TemplateRegistry._normalize_number(efficiency_rates[key])
                if rate is not None:
                    efficiency_rates[key] = rate

        return data

    @staticmethod
    def _prepare_auto_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        valid_period = data.get("valid_period") or {}
        windows = data.setdefault("windows", {})
        windows.setdefault("time_basis", windows.get("time_basis", "purchase_time"))

        for win_key in ["purchase_window", "claim_window", "modify_window"]:
            window = windows.setdefault(win_key, {})
            window.setdefault("start", valid_period.get("start") or _today_iso())
            window.setdefault("end", valid_period.get("end"))

        matching = data.setdefault("matching", {})
        powertrain_defs = matching.setdefault(
            "powertrain_defs",
            {
                "NEV": ["新能源", "纯电", "插混"],
                "ICE": ["燃油", "混动"],
            },
        )
        matching["powertrain_defs"] = powertrain_defs

        tiers = matching.setdefault("tiers", [])
        if not tiers:
            raw_tiers = data.get("tiers") or []
            converted: List[Dict[str, Any]] = []
            for tier in raw_tiers:
                entry = {}
                tier_range = tier.get("range") or tier.get("price_range")
                if isinstance(tier_range, list):
                    if len(tier_range) >= 1:
                        entry["min_ex_tax"] = tier_range[0]
                    if len(tier_range) >= 2:
                        entry["max_ex_tax"] = tier_range[1]
                entry["powertrain"] = tier.get("powertrain") or tier.get("vehicle_type") or "NEV"
                entry["open_interval"] = tier.get("open_interval") or "[)"
                entry["subsidy"] = tier.get("subsidy") or tier.get("package") or tier.get("benefit")
                converted.append(entry)
            if converted:
                matching["tiers"] = converted

        limits = data.setdefault("limits", {})
        limits.setdefault("per_person_max_cars", limits.get("per_person_max_cars", 1))
        dedupe_keys = limits.get("dedupe_keys")
        if not isinstance(dedupe_keys, list) or not dedupe_keys:
            limits["dedupe_keys"] = ["buyer_id", "vin", "invoice_no"]

        budget = data.setdefault("budget", {})
        budget.setdefault("currency", "CNY")
        budget.setdefault("allocation", budget.get("allocation", "global"))
        budget.setdefault("total", budget.get("total", 0))

        eligibility = data.setdefault("eligibility", {})
        eligibility.setdefault("buyer_type", "person")
        eligibility.setdefault("vehicle_scope", eligibility.get("vehicle_scope", "all"))
        eligibility.setdefault("combinable_with_upper_policies", True)

        return data

    @staticmethod
    def _prepare_coupon_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        coupon_types = data.get("coupon_types")
        if not isinstance(coupon_types, list) or not coupon_types:
            data["coupon_types"] = ["AMOUNT"]

        tiers = data.get("tiers") or []
        normalized: List[Dict[str, Any]] = []
        for tier in tiers:
            entry = dict(tier)
            entry.setdefault("type", entry.get("tier_type", "AMOUNT"))
            if "threshold" not in entry:
                rng = entry.get("range")
                if isinstance(rng, list) and rng:
                    entry["threshold"] = rng[0]
            if "discount" not in entry:
                entry["discount"] = entry.get("amount") or entry.get("value")
            entry["threshold"] = TemplateRegistry._normalize_number(entry.get("threshold")) or 0
            entry["discount"] = TemplateRegistry._normalize_number(entry.get("discount")) or 0
            entry["cap"] = TemplateRegistry._normalize_number(entry.get("cap"))
            if entry.get("name"):
                entry["name"] = TemplateRegistry._normalize_placeholder(entry["name"])
            normalized.append(entry)
        data["tiers"] = normalized

        distribution = data.setdefault("distribution", {})
        distribution.setdefault("method", distribution.get("method", "auto_claim"))
        distribution["total_quota"] = TemplateRegistry._normalize_number(
            distribution.get("total_quota")
        )
        distribution["quota_per_person"] = TemplateRegistry._normalize_number(
            distribution.get("quota_per_person")
        )

        release_schedule = distribution.get("release_schedule")
        if release_schedule and isinstance(release_schedule, list):
            cleaned = []
            for idx, batch in enumerate(release_schedule, start=1):
                if not isinstance(batch, dict):
                    continue
                cleaned.append(
                    {
                        "batch": batch.get("batch", idx),
                        "time": batch.get("time"),
                        "amount": TemplateRegistry._normalize_number(batch.get("amount")),
                    }
                )
            distribution["release_schedule"] = cleaned

        usage_limits = data.setdefault("usage_limits", {})
        usage_limits["valid_days"] = TemplateRegistry._normalize_number(
            usage_limits.get("valid_days", 30)
        ) or 30
        usage_limits.setdefault("merchant_scope", usage_limits.get("merchant_scope", "参与活动商户"))
        usage_limits.setdefault("product_scope", usage_limits.get("product_scope", "全部商品"))

        stacking = usage_limits.setdefault("stacking", {})
        stacking.setdefault("with_merchant_discount", True)
        stacking.setdefault("with_other_coupons", True)

        platform = data.setdefault("platform", {})
        platform["claim_platform"] = TemplateRegistry._normalize_placeholder(
            platform.get("claim_platform")
        ) or ""
        payment_methods = platform.get("payment_methods")
        if not isinstance(payment_methods, list):
            platform["payment_methods"] = []

        return data


    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def has_field(data: Dict[str, Any], dotted_path: str) -> bool:
        """Check whether a dotted path exists and is non-empty."""
        current: Any = data
        for part in dotted_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return not _is_missing(current)

    @staticmethod
    def _deep_fill(target: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in defaults.items():
            if isinstance(value, dict):
                existing = target.get(key)
                if not isinstance(existing, dict):
                    existing = {}
                target[key] = TemplateRegistry._deep_fill(existing, value)
            elif isinstance(value, list):
                if key not in target or _is_missing(target[key]):
                    target[key] = copy.deepcopy(value)
            else:
                if key not in target or _is_missing(target[key]):
                    target[key] = value
        return target

    @staticmethod
    def _build_haystack(data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        parts: List[str] = []

        def push(value: Any):
            if value is None:
                return
            text = str(value).strip()
            if text:
                parts.append(text)

        for key in ("rule_id", "name", "version", "policy_type", "template_hint"):
            push(data.get(key))

        policy_source = data.get("policy_source") or {}
        for key in ("title", "doc_id", "clause"):
            push(policy_source.get(key))

        if context and isinstance(context, dict):
            for ctx_key in ("title", "doc_id", "category", "domain", "summary"):
                push(context.get(ctx_key))

        return " ".join(parts)

    @staticmethod
    def _normalize_placeholder(value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if not text or text.lower() in {"none", "null", "无", "暂无", "na"}:
                return None
            return text
        return value

    @staticmethod
    def _normalize_number(value: Any) -> Optional[float]:
        value = TemplateRegistry._normalize_placeholder(value)
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            multiplier = 1
            if text.endswith("万"):
                multiplier = 10000
                text = text[:-1]
            text = re.sub(r"[^\d\.]", "", text)
            if not text:
                return None
            try:
                number = float(text) * multiplier
                if number.is_integer():
                    return int(number)
                return number
            except ValueError:
                return None
        return None





