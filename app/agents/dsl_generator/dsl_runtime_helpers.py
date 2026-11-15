"""
Runtime helper functions that DSL expressions can call during evaluation.
These helpers encapsulate the multi-step logic that previously lived inside
the YAML templates, allowing the DSL to stay declarative (route A).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Dict, Optional, List


class DSLRuntimeHelpers:
    """Utility helpers that can be safely exposed to the PolicyEngine eval sandbox."""

    # ------------------------------------------------------------------ #
    # Common utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_optional_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("Boolean is not a policy number")
        number = float(value)
        if not isfinite(number):
            raise ValueError("Policy number must be finite")
        return number

    @staticmethod
    def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
        return None if value is None else round(value + 1e-12, digits)

    @staticmethod
    def _parse_iso(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @classmethod
    def _in_window(cls, ts: Optional[datetime], window: Optional[Dict[str, Any]]) -> bool:
        if ts is None:
            return False
        if not window:
            return True
        start = cls._parse_iso(window.get("start"))
        end = cls._parse_iso(window.get("end"))
        ok_start = (start is None) or (ts >= start)
        ok_end = (end is None) or (ts < end)
        return ok_start and ok_end

    @staticmethod
    def _bool(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    @staticmethod
    def _get_callable(context: Optional[Dict[str, Any]], name: str):
        if isinstance(context, dict):
            func = context.get(name)
            if callable(func):
                return func
        return None

    # ------------------------------------------------------------------ #
    # Appliance subsidy helper
    # ------------------------------------------------------------------ #

    @classmethod
    def appliance_subsidy(
        cls,
        inputs: Dict[str, Any],
        efficiency_rates: Optional[Dict[str, Any]] = None,
        per_item_cap: Optional[Any] = None,
        category_limits: Optional[Dict[str, Any]] = None,
        special_rules: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        efficiency_rates = efficiency_rates or {}
        special_rules = special_rules or {}

        price = cls._parse_optional_number(inputs.get("price"))
        energy_level = inputs.get("energy_level")

        if price is None or price < 0:
            return {
                "status": "INVALID_INPUT",
                "error": "INVALID_PRICE",
                "price": price,
                "rate": 0,
                "raw_subsidy": 0,
                "final_subsidy": 0,
                "per_item_cap": cls._parse_optional_number(per_item_cap),
                "energy_level": energy_level,
            }

        base_rate = cls._parse_optional_number(efficiency_rates["base_rate"])
        if base_rate is None:
            raise ValueError("Missing policy base_rate")
        if energy_level == 1:
            bonus = cls._parse_optional_number(efficiency_rates["level_1_bonus"])
            if bonus is None:
                raise ValueError("Missing policy level_1_bonus")
            rate = base_rate + bonus
        elif energy_level == 2:
            rate = base_rate
        else:
            no_label_rate = cls._parse_optional_number(efficiency_rates["no_label_rate"])
            if no_label_rate is None:
                raise ValueError("Missing policy no_label_rate")
            rate = no_label_rate

        rate = max(0.0, min(rate, 1.0))
        raw_subsidy = price * rate

        cap_value = cls._parse_optional_number(per_item_cap)
        final_subsidy = raw_subsidy if cap_value is None else min(raw_subsidy, cap_value)

        return {
            "status": "QUALIFIED",
            "price": cls._round(price, 2),
            "energy_level": energy_level,
            "rate": cls._round(rate, 4),
            "raw_subsidy": cls._round(raw_subsidy, 2),
            "final_subsidy": cls._round(final_subsidy, 2),
            "per_item_cap": cap_value,
            "category_limits": category_limits or {},
            "trade_in_required": cls._bool(special_rules.get("trade_in_required"), False),
            "old_device_criteria": special_rules.get("old_device_criteria"),
            "stacking_allowed": cls._bool(special_rules.get("stacking_allowed"), True),
        }

    # ------------------------------------------------------------------ #
    # Auto subsidy helper
    # ------------------------------------------------------------------ #

    @classmethod
    def auto_subsidy(
        cls,
        inputs: Dict[str, Any],
        windows: Optional[Dict[str, Any]] = None,
        limits: Optional[Dict[str, Any]] = None,
        matching: Optional[Dict[str, Any]] = None,
        budget: Optional[Dict[str, Any]] = None,
        eligibility: Optional[Dict[str, Any]] = None,
        price_basis: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        windows = windows or {}
        limits = limits or {}
        matching = matching or {}
        budget = budget or {}
        eligibility = eligibility or {}

        invoice = cls._parse_optional_number(inputs.get("invoice_no_tax"))
        base = {
            "invoice_no_tax": cls._round(invoice, 2) if invoice is not None else None,
            "vehicle_type": inputs.get("vehicle_type"),
            "purchase_time": inputs.get("purchase_time"),
            "claim_time": inputs.get("claim_time"),
            "tier": None,
            "subsidy": 0,
            "price_basis": price_basis
        }

        if invoice is None or invoice < 0:
            base.update({"status": "INVALID_INPUT", "reason": "invoice_no_tax"})
            return base

        try:
            purchase_time = cls._parse_iso(inputs.get("purchase_time"))
            claim_time = cls._parse_iso(inputs.get("claim_time"))
        except (ValueError, TypeError, AttributeError):
            base.update({"status": "INVALID_INPUT", "reason": "timestamp"})
            return base
        if purchase_time is None or claim_time is None:
            base.update({"status": "INVALID_INPUT", "reason": "timestamp"})
            return base

        base["purchase_time"] = purchase_time.isoformat()
        base["claim_time"] = claim_time.isoformat()

        if not cls._in_window(purchase_time, windows.get("purchase_window")):
            base.update({"status": "OUT_OF_PURCHASE_WINDOW"})
            return base
        if not cls._in_window(claim_time, windows.get("claim_window")):
            base.update({"status": "OUT_OF_CLAIM_WINDOW"})
            return base

        modify_window = windows.get("modify_window")
        if modify_window and (modify_window.get("start") or modify_window.get("end")):
            if not cls._in_window(claim_time, modify_window):
                base.update({"status": "OUT_OF_MODIFY_WINDOW"})
                return base

        dedupe_keys = limits.get("dedupe_keys")
        dedupe_fn = cls._get_callable(context, "is_duplicate")
        if dedupe_keys and dedupe_fn:
            if dedupe_fn(dedupe_keys, inputs):
                base.update({"status": "DUPLICATE"})
                return base

        per_person_max = limits.get("per_person_max_cars")
        claimed_fn = cls._get_callable(context, "claimed_count_by_buyer")
        buyer_id = inputs.get("buyer_id")
        if per_person_max is not None and buyer_id and claimed_fn:
            claimed = claimed_fn(buyer_id)
            if claimed >= per_person_max:
                base.update({"status": "PERSON_LIMIT_EXCEEDED"})
                return base

        vehicle_type = inputs.get("vehicle_type")
        if not vehicle_type:
            classify_fn = cls._get_callable(context, "classify_powertrain")
            if classify_fn:
                vehicle_type = classify_fn(matching.get("powertrain_defs", {}))

        if vehicle_type not in ("NEV", "ICE"):
            base.update({"status": "NOT_IN_SCOPE", "vehicle_type": vehicle_type})
            return base

        base["vehicle_type"] = vehicle_type

        tiers = [t for t in (matching.get("tiers") or []) if t.get("powertrain") == vehicle_type]
        tiers.sort(
            key=lambda t: (
                cls._parse_optional_number(t.get("min_ex_tax")) or 0,
                float("inf") if t.get("max_ex_tax") is None else float(t["max_ex_tax"]),
            )
        )

        matched_tier = None
        for tier in tiers:
            min_v = cls._parse_optional_number(tier.get("min_ex_tax")) or 0
            max_v = cls._parse_optional_number(tier.get("max_ex_tax"))
            interval = (tier.get("open_interval") or "[)")
            left_closed = interval[0] == "["
            right_closed = interval[1] == "]"

            left_ok = invoice >= min_v if left_closed else invoice > min_v
            right_ok = True
            if max_v is not None:
                right_ok = invoice <= max_v if right_closed else invoice < max_v

            if left_ok and right_ok:
                matched_tier = tier
                break

        if not matched_tier:
            base.update({"status": "NOT_QUALIFIED"})
            return base

        subsidy = cls._parse_optional_number(matched_tier["subsidy"])
        if subsidy is None:
            raise ValueError("Missing policy tier subsidy")
        if subsidy < 0:
            subsidy = 0
        base["tier"] = matched_tier

        remaining_fn = cls._get_callable(context, "budget_remaining")
        allocation = budget.get("allocation")
        if remaining_fn and allocation:
            remaining = remaining_fn(allocation)
            if remaining is not None and subsidy > remaining:
                base.update({"status": "BUDGET_EXHAUSTED"})
                return base

        base.update({
            "status": "QUALIFIED",
            "subsidy": cls._round(subsidy, 2),
            "price_basis": price_basis
        })
        return base

    # ------------------------------------------------------------------ #
    # Consumer coupon helper
    # ------------------------------------------------------------------ #

    @classmethod
    def consumer_coupon(
        cls,
        inputs: Dict[str, Any],
        valid_period: Optional[Dict[str, Any]] = None,
        tiers: Optional[List[Dict[str, Any]]] = None,
        distribution: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        coupon_types: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        valid_period = valid_period or {}
        tiers = tiers or []
        distribution = distribution or {}
        usage_limits = usage_limits or {}
        coupon_types = coupon_types or []

        amount = cls._parse_optional_number(inputs.get("consumption_amount"))
        coupon_type = inputs.get("coupon_type")
        base = {
            "amount": amount,
            "coupon_type": coupon_type,
            "discount": 0,
            "final_amount": amount if amount is not None else 0,
            "tier": None,
            "expire_at": None
        }

        if amount is None or amount < 0:
            base.update({"status": "INVALID_INPUT", "final_amount": 0})
            return base

        if coupon_type not in coupon_types:
            base.update({"status": "INVALID_COUPON_TYPE"})
            return base

        try:
            claim_time = cls._parse_iso(inputs.get("claim_time"))
        except (ValueError, TypeError, AttributeError):
            base.update({"status": "INVALID_TIME"})
            return base
        if claim_time is None:
            base.update({"status": "INVALID_TIME"})
            return base

        vp_start = cls._parse_iso(valid_period.get("start"))
        vp_end = cls._parse_iso(valid_period.get("end"))
        if (vp_start and claim_time < vp_start) or (vp_end and claim_time >= vp_end):
            base.update({"status": "OUT_OF_POLICY_WINDOW"})
            return base

        valid_days = cls._parse_optional_number(usage_limits.get("valid_days"))
        expire_at = vp_end
        if valid_days is not None:
            expire_at = claim_time + timedelta(days=valid_days)
            if vp_end is not None and expire_at > vp_end:
                expire_at = vp_end
        base["expire_at"] = expire_at.isoformat() if expire_at is not None else None

        total_quota = distribution.get("total_quota")
        if total_quota is not None:
            avail_fn = cls._get_callable(context, "available_quota_at")
            used_fn = cls._get_callable(context, "used_quota_total")
            if avail_fn and used_fn:
                available_total = max(0, avail_fn(claim_time) - used_fn())
                if available_total <= 0:
                    base.update({"status": "QUOTA_EXHAUSTED"})
                    return base

        quota_per_person = distribution.get("quota_per_person")
        if quota_per_person is not None:
            used_by_user = cls._get_callable(context, "used_quota_by_user")
            user_id = inputs.get("user_id")
            if used_by_user and user_id:
                already = used_by_user(user_id)
                if already >= quota_per_person:
                    base.update({"status": "USER_QUOTA_EXCEEDED"})
                    return base

        merchant_allowed_fn = cls._get_callable(context, "is_merchant_allowed")
        product_allowed_fn = cls._get_callable(context, "is_product_allowed")
        merchant_scope = usage_limits.get("merchant_scope")
        product_scope = usage_limits.get("product_scope")

        if merchant_allowed_fn:
            if not merchant_allowed_fn(inputs.get("merchant_id"), merchant_scope):
                base.update({"status": "OUT_OF_SCOPE"})
                return base
        if product_allowed_fn:
            if not product_allowed_fn(inputs.get("product_id"), product_scope):
                base.update({"status": "OUT_OF_SCOPE"})
                return base

        time_restrictions = usage_limits.get("time_restrictions")
        if time_restrictions:
            time_allowed_fn = cls._get_callable(context, "is_time_allowed")
            if time_allowed_fn:
                if not time_allowed_fn(claim_time, time_restrictions):
                    base.update({"status": "TIME_RESTRICTED"})
                    return base

        stacking = usage_limits.get("stacking", {})
        allow_other_coupons = cls._bool(stacking.get("with_other_coupons"), True)
        allow_merchant_discount = cls._bool(stacking.get("with_merchant_discount"), True)

        if not allow_other_coupons and inputs.get("using_other_coupon"):
            base.update({"status": "STACKING_NOT_ALLOWED_COUPON"})
            return base
        if not allow_merchant_discount and inputs.get("has_merchant_discount"):
            base.update({"status": "STACKING_NOT_ALLOWED_MERCHANT"})
            return base

        matched_tier = None
        best_discount = 0.0
        best_threshold = -1.0

        for tier in tiers:
            if tier.get("type") != coupon_type:
                continue
            threshold = cls._parse_optional_number(tier["threshold"])
            if threshold is None:
                raise ValueError("Missing policy coupon threshold")
            if amount < threshold:
                continue

            if coupon_type == "AMOUNT":
                discount = cls._parse_optional_number(tier["discount"])
                if discount is None:
                    raise ValueError("Missing policy coupon discount")
            else:
                pct = cls._parse_optional_number(tier["discount"])
                if pct is None:
                    raise ValueError("Missing policy coupon discount")
                discount = amount * pct
                cap = cls._parse_optional_number(tier.get("cap"))
                if cap is not None and discount > cap:
                    discount = cap

            if discount > best_discount or (
                abs(discount - best_discount) < 1e-9 and threshold > best_threshold
            ):
                best_discount = discount
                best_threshold = threshold
                matched_tier = dict(tier)
                matched_tier.setdefault("name", None)
                matched_tier["cap"] = cls._parse_optional_number(tier.get("cap"))

        if not matched_tier or best_discount <= 0:
            base.update({"status": "NOT_QUALIFIED"})
            return base

        discount_value = cls._round(best_discount, 2) or 0
        final_amount = cls._round(max(0.0, amount - discount_value), 2)
        base.update({
            "status": "QUALIFIED",
            "discount": discount_value,
            "final_amount": final_amount,
            "tier": matched_tier
        })
        return base


# Backwards-compatible alias for templates that may prefer snake_case.
dsl_helpers = DSLRuntimeHelpers
