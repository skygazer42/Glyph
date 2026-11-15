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
from typing import Any, Callable, Dict, List, Optional
from math import isfinite


def _is_missing(value: Any) -> bool:
    """Determine whether a value should be treated as 'missing'."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False


@dataclass
class TemplateProfile:
    """Metadata for a single Jinja template."""

    name: str
    template_name: str
    prepare: Callable[[Dict[str, Any]], Dict[str, Any]]
    keywords: List[str] = field(default_factory=list)
    field_signals: List[str] = field(default_factory=list)
    defaults_factory: Callable[[], Dict[str, Any]] = dict
    min_score: int = 2

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

    def __init__(self):
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
        if profile.name == "appliance":
            rates = merged.get("efficiency_rates", {})
            if not isinstance(rates, dict) or rates.get("base_rate") is None:
                raise ValueError("Missing policy efficiency_rates.base_rate")
            cap = merged.get("per_item_cap")
            if cap is None:
                cap = merged.get("limits", {}).get("per_item_cap")
            if cap is None:
                raise ValueError("Missing policy per_item_cap")
            merged["per_item_cap"] = cap
        defaults = profile.defaults_factory()
        self._deep_fill(merged, defaults)

        return profile.prepare(merged)

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
            "version": "1.0",
            "policy_source": {"doc_id": None, "title": None, "clause": None},
            "valid_period": {"start": None, "end": None},
            "efficiency_rates": {},
            "category_limits": {"per_category": {}, "total_items": None},
            "special_rules": {},
        }

    @staticmethod
    def _auto_defaults() -> Dict[str, Any]:
        return {
            "version": "1.0",
            "policy_source": {"doc_id": None, "title": None},
            "windows": {}, "budget": {}, "eligibility": {},
            "price_basis": None,
            "matching": {"powertrain_defs": {}, "tiers": []},
            "limits": {},
        }

    @staticmethod
    def _coupon_defaults() -> Dict[str, Any]:
        return {
            "version": "1.0",
            "policy_source": {"doc_id": None, "title": None},
            "valid_period": {"start": None, "end": None},
            "tiers": [], "distribution": {}, "usage_limits": {}, "platform": {},
        }

    # ------------------------------------------------------------------ #
    # Prepare helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prepare_appliance_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        category_limits = data.setdefault("category_limits", {})
        per_category = category_limits.setdefault("per_category", {})
        if not isinstance(per_category, dict):
            raise ValueError("category_limits.per_category must be an object")
        category_limits["total_items"] = TemplateRegistry._normalize_number(category_limits.get("total_items"))
        cap = data.get("per_item_cap")
        if cap is None:
            cap = data.get("limits", {}).get("per_item_cap")
        numeric_cap = TemplateRegistry._normalize_number(cap)
        if numeric_cap is None:
            raise ValueError("Missing policy per_item_cap")
        data["per_item_cap"] = numeric_cap
        rates = data["efficiency_rates"]
        for key in ("base_rate", "level_1_bonus", "no_label_rate"):
            if key in rates:
                rates[key] = TemplateRegistry._normalize_number(rates[key])
        if rates.get("base_rate") is None:
            raise ValueError("Missing policy efficiency_rates.base_rate")
        return data

    @staticmethod
    def _prepare_auto_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        valid_period = data.get("valid_period", {})
        windows = data.setdefault("windows", {})
        for key in ("purchase_window", "claim_window", "modify_window"):
            window = windows.setdefault(key, {})
            # An explicitly supplied general validity window also bounds these operations.
            for bound in ("start", "end"):
                if bound not in window and bound in valid_period:
                    window[bound] = valid_period[bound]
        matching = data.setdefault("matching", {})
        if "tiers" not in matching or (not matching["tiers"] and "tiers" in data):
            matching["tiers"] = data.get("tiers", [])
        converted = []
        for tier in matching["tiers"]:
            entry = dict(tier)
            if "powertrain" not in entry:
                entry["powertrain"] = entry["vehicle_type"]
            if entry["powertrain"] not in {"NEV", "ICE"}:
                raise ValueError("Auto tier requires NEV or ICE powertrain")
            tier_range = entry.get("range", entry.get("price_range"))
            if tier_range is not None:
                if not isinstance(tier_range, list) or len(tier_range) != 2:
                    raise ValueError("Auto tier range must contain two bounds")
                entry.setdefault("min_ex_tax", tier_range[0])
                entry.setdefault("max_ex_tax", tier_range[1])
            if "min_ex_tax" not in entry or "max_ex_tax" not in entry:
                raise ValueError("Auto tier requires explicit price bounds")
            entry.setdefault("open_interval", "[)")
            if entry["open_interval"] not in {"[]", "[)", "(]", "()"}:
                raise ValueError("Invalid auto tier interval")
            if "subsidy" not in entry:
                entry["subsidy"] = entry["package"] if "package" in entry else entry["benefit"]
            for key in ("min_ex_tax", "max_ex_tax", "subsidy"):
                entry[key] = TemplateRegistry._normalize_number(entry[key])
            if entry["subsidy"] is None:
                raise ValueError("Auto tier requires subsidy")
            converted.append(entry)
        matching["tiers"] = converted
        matching.setdefault("powertrain_defs", {})
        data.setdefault("limits", {})
        data.setdefault("budget", {})
        data.setdefault("eligibility", {})
        return data

    @staticmethod
    def _prepare_coupon_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = []
        for tier in data.get("tiers", []):
            entry = dict(tier)
            if "type" not in entry:
                entry["type"] = entry["tier_type"]
            if entry["type"] not in {"AMOUNT", "PERCENT"}:
                raise ValueError("Unsupported coupon tier type")
            if "threshold" not in entry:
                entry["threshold"] = entry["range"][0]
            if "discount" not in entry:
                entry["discount"] = entry["amount"] if "amount" in entry else entry["value"]
            for key in ("threshold", "discount"):
                entry[key] = TemplateRegistry._normalize_number(entry[key])
                if entry[key] is None:
                    raise ValueError(f"Coupon tier requires {key}")
            entry["cap"] = TemplateRegistry._normalize_number(entry.get("cap"))
            entry["name"] = TemplateRegistry._normalize_placeholder(entry.get("name"))
            normalized.append(entry)
        data["tiers"] = normalized
        if "coupon_types" not in data:
            data["coupon_types"] = list(dict.fromkeys(tier["type"] for tier in normalized))
        if not isinstance(data["coupon_types"], list):
            raise ValueError("coupon_types must be a list")
        distribution = data.setdefault("distribution", {})
        for key in ("total_quota", "quota_per_person"):
            if key in distribution:
                distribution[key] = TemplateRegistry._normalize_number(distribution[key])
        schedule = distribution.get("release_schedule", [])
        if not isinstance(schedule, list):
            raise ValueError("release_schedule must be a list")
        for batch in schedule:
            batch["amount"] = TemplateRegistry._normalize_number(batch["amount"])
        usage_limits = data.setdefault("usage_limits", {})
        if "valid_days" in usage_limits:
            usage_limits["valid_days"] = TemplateRegistry._normalize_number(usage_limits["valid_days"])
        platform = data.setdefault("platform", {})
        if "payment_methods" in platform and not isinstance(platform["payment_methods"], list):
            raise ValueError("payment_methods must be a list")
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
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(value, dict):
                if not isinstance(target[key], dict):
                    raise ValueError(f"Policy section {key} must be an object")
                TemplateRegistry._deep_fill(target[key], value)
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
        if isinstance(value, bool):
            raise ValueError("Boolean is not a numeric policy value")
        if isinstance(value, (int, float)):
            if not isfinite(value):
                raise ValueError("Policy number must be finite")
            return value
        if isinstance(value, str):
            text = value.strip()
            multiplier = 1
            if text.endswith("万"):
                multiplier = 10000
                text = text[:-1]
            text = text.replace(',', '').replace('元', '').strip()
            try:
                number = float(text) * multiplier
                if not isfinite(number):
                    raise ValueError("Policy number must be finite")
                if number.is_integer():
                    return int(number)
                return number
            except ValueError as exc:
                raise ValueError(f"Invalid numeric policy value: {value!r}") from exc
        raise ValueError(f"Invalid numeric policy value: {value!r}")
