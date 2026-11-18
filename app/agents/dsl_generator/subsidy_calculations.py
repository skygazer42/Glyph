"""Pure subsidy calculations registered explicitly by the DSL evaluator."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Dict, List, Optional


def _parse_optional_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not a policy number")
    number = float(value)
    if not isfinite(number):
        raise ValueError("Policy number must be finite")
    return number

def _round_policy_value(value: float, digits: int = 2) -> float:
    return round(value + 1e-12, digits)

def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _is_within_window(timestamp: Optional[datetime], window: Optional[Dict[str, Any]]) -> bool:
    if timestamp is None:
        return False
    if not window:
        return True
    start = _parse_iso(window.get("start"))
    end = _parse_iso(window.get("end"))
    ok_start = (start is None) or (timestamp >= start)
    ok_end = (end is None) or (timestamp < end)
    return ok_start and ok_end

def _parse_policy_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    elif isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ValueError(f"Invalid policy boolean: {value!r}")

def _get_policy_callback(
    context: dict[str, Any] | None, name: str,
) -> Callable[..., Any] | None:
    if context is None:
        return None
    callback = context.get(name)
    if callback is not None and not callable(callback):
        raise TypeError(f"Policy callback {name!r} must be callable")
    return callback

# ------------------------------------------------------------------ #
# Appliance subsidy helper
# ------------------------------------------------------------------ #

def appliance_subsidy(
    inputs: Dict[str, Any],
    efficiency_rates: Dict[str, Any],
    per_item_cap: Optional[Any] = None,
    category_limits: Optional[Dict[str, Any]] = None,
    special_rules: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    special_rules = special_rules or {}

    price = _parse_optional_number(inputs.get("price"))
    energy_level = inputs.get("energy_level")

    if price is None or price < 0:
        return {
            "status": "INVALID_INPUT",
            "error": "INVALID_PRICE",
            "price": price,
            "rate": 0,
            "raw_subsidy": 0,
            "final_subsidy": 0,
            "per_item_cap": _parse_optional_number(per_item_cap),
            "energy_level": energy_level,
        }

    base_rate = _parse_optional_number(efficiency_rates["base_rate"])
    if base_rate is None:
        raise ValueError("Missing policy base_rate")
    if energy_level == 1:
        bonus = _parse_optional_number(efficiency_rates["level_1_bonus"])
        if bonus is None:
            raise ValueError("Missing policy level_1_bonus")
        rate = base_rate + bonus
    elif energy_level == 2:
        rate = base_rate
    else:
        no_label_rate = _parse_optional_number(efficiency_rates["no_label_rate"])
        if no_label_rate is None:
            raise ValueError("Missing policy no_label_rate")
        rate = no_label_rate

    rate = max(0.0, min(rate, 1.0))
    raw_subsidy = price * rate

    cap_value = _parse_optional_number(per_item_cap)
    if cap_value is not None and cap_value < 0:
        raise ValueError("Policy per_item_cap must not be negative")
    final_subsidy = raw_subsidy if cap_value is None else min(raw_subsidy, cap_value)

    return {
        "status": "QUALIFIED",
        "price": _round_policy_value(price, 2),
        "energy_level": energy_level,
        "rate": _round_policy_value(rate, 4),
        "raw_subsidy": _round_policy_value(raw_subsidy, 2),
        "final_subsidy": _round_policy_value(final_subsidy, 2),
        "per_item_cap": cap_value,
        "category_limits": category_limits or {},
        "trade_in_required": _parse_policy_bool(special_rules.get("trade_in_required"), False),
        "old_device_criteria": special_rules.get("old_device_criteria"),
        "stacking_allowed": _parse_policy_bool(special_rules.get("stacking_allowed"), True),
    }

# ------------------------------------------------------------------ #
# Auto subsidy helper
# ------------------------------------------------------------------ #

def auto_subsidy(
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

    invoice = _parse_optional_number(inputs.get("invoice_no_tax"))
    result = {
        "invoice_no_tax": _round_policy_value(invoice, 2) if invoice is not None else None,
        "vehicle_type": inputs.get("vehicle_type"),
        "purchase_time": inputs.get("purchase_time"),
        "claim_time": inputs.get("claim_time"),
        "tier": None,
        "subsidy": 0,
        "price_basis": price_basis
    }

    if invoice is None or invoice < 0:
        result.update({"status": "INVALID_INPUT", "reason": "invoice_no_tax"})
        return result

    try:
        purchase_time = _parse_iso(inputs.get("purchase_time"))
        claim_time = _parse_iso(inputs.get("claim_time"))
    except (ValueError, TypeError, AttributeError):
        result.update({"status": "INVALID_INPUT", "reason": "timestamp"})
        return result
    if purchase_time is None or claim_time is None:
        result.update({"status": "INVALID_INPUT", "reason": "timestamp"})
        return result

    result["purchase_time"] = purchase_time.isoformat()
    result["claim_time"] = claim_time.isoformat()

    if not _is_within_window(purchase_time, windows.get("purchase_window")):
        result.update({"status": "OUT_OF_PURCHASE_WINDOW"})
        return result
    if not _is_within_window(claim_time, windows.get("claim_window")):
        result.update({"status": "OUT_OF_CLAIM_WINDOW"})
        return result

    modify_window = windows.get("modify_window")
    if modify_window and (modify_window.get("start") or modify_window.get("end")):
        if not _is_within_window(claim_time, modify_window):
            result.update({"status": "OUT_OF_MODIFY_WINDOW"})
            return result

    dedupe_keys = limits.get("dedupe_keys")
    dedupe_fn = _get_policy_callback(context, "is_duplicate")
    if dedupe_keys and dedupe_fn is not None:
        if dedupe_fn(dedupe_keys, inputs):
            result.update({"status": "DUPLICATE"})
            return result

    per_person_max = limits.get("per_person_max_cars")
    claimed_fn = _get_policy_callback(context, "claimed_count_by_buyer")
    buyer_id = inputs.get("buyer_id")
    if per_person_max is not None and buyer_id and claimed_fn is not None:
        claimed = claimed_fn(buyer_id)
        if claimed >= per_person_max:
            result.update({"status": "PERSON_LIMIT_EXCEEDED"})
            return result

    vehicle_type = inputs.get("vehicle_type")
    if not vehicle_type:
        classify_fn = _get_policy_callback(context, "classify_powertrain")
        if classify_fn is not None:
            vehicle_type = classify_fn(matching.get("powertrain_defs", {}))

    if vehicle_type not in ("NEV", "ICE"):
        result.update({"status": "NOT_IN_SCOPE", "vehicle_type": vehicle_type})
        return result

    result["vehicle_type"] = vehicle_type

    tiers = [t for t in (matching.get("tiers") or []) if t.get("powertrain") == vehicle_type]
    def price_bounds(tier: Dict[str, Any]) -> tuple[float, float]:
        lower = _parse_optional_number(tier.get("min_ex_tax"))
        upper = _parse_optional_number(tier.get("max_ex_tax"))
        return (0.0 if lower is None else lower, float("inf") if upper is None else upper)

    tiers.sort(key=price_bounds)

    matched_tier = None
    for tier in tiers:
        minimum_price = _parse_optional_number(tier.get("min_ex_tax"))
        maximum_price = _parse_optional_number(tier.get("max_ex_tax"))
        interval = tier.get("open_interval", "[)")
        if not isinstance(interval, str) or len(interval) < 2 or interval[0] not in "[(" or interval[-1] not in "])":
            raise ValueError("Invalid auto tier interval")
        left_closed = interval[0] == "["
        right_closed = interval[-1] == "]"

        left_ok = minimum_price is None or (invoice >= minimum_price if left_closed else invoice > minimum_price)
        right_ok = True
        if maximum_price is not None:
            right_ok = invoice <= maximum_price if right_closed else invoice < maximum_price

        if left_ok and right_ok:
            matched_tier = tier
            break

    if matched_tier is None:
        result.update({"status": "NOT_QUALIFIED"})
        return result

    subsidy = _parse_optional_number(matched_tier["subsidy"])
    if subsidy is None:
        raise ValueError("Missing policy tier subsidy")
    if subsidy < 0:
        subsidy = 0
    result["tier"] = matched_tier

    remaining_fn = _get_policy_callback(context, "budget_remaining")
    allocation = budget.get("allocation")
    if remaining_fn is not None and allocation:
        remaining = remaining_fn(allocation)
        if remaining is not None and subsidy > remaining:
            result.update({"status": "BUDGET_EXHAUSTED"})
            return result

    result.update({
        "status": "QUALIFIED",
        "subsidy": _round_policy_value(subsidy, 2),
        "price_basis": price_basis
    })
    return result

# ------------------------------------------------------------------ #
# Consumer coupon helper
# ------------------------------------------------------------------ #

def consumer_coupon(
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

    amount = _parse_optional_number(inputs.get("consumption_amount"))
    coupon_type = inputs.get("coupon_type")
    result = {
        "amount": amount,
        "coupon_type": coupon_type,
        "discount": 0,
        "final_amount": amount if amount is not None else 0,
        "tier": None,
        "expire_at": None
    }

    if amount is None or amount < 0:
        result.update({"status": "INVALID_INPUT", "final_amount": 0})
        return result

    if coupon_type not in coupon_types:
        result.update({"status": "INVALID_COUPON_TYPE"})
        return result

    try:
        claim_time = _parse_iso(inputs.get("claim_time"))
    except (ValueError, TypeError, AttributeError):
        result.update({"status": "INVALID_TIME"})
        return result
    if claim_time is None:
        result.update({"status": "INVALID_TIME"})
        return result

    policy_start = _parse_iso(valid_period.get("start"))
    policy_end = _parse_iso(valid_period.get("end"))
    if (policy_start and claim_time < policy_start) or (policy_end and claim_time >= policy_end):
        result.update({"status": "OUT_OF_POLICY_WINDOW"})
        return result

    valid_days = _parse_optional_number(usage_limits.get("valid_days"))
    expire_at = policy_end
    if valid_days is not None:
        expire_at = claim_time + timedelta(days=valid_days)
        if policy_end is not None and expire_at > policy_end:
            expire_at = policy_end
    result["expire_at"] = expire_at.isoformat() if expire_at is not None else None

    total_quota = distribution.get("total_quota")
    if total_quota is not None:
        avail_fn = _get_policy_callback(context, "available_quota_at")
        used_fn = _get_policy_callback(context, "used_quota_total")
        if avail_fn is not None and used_fn is not None:
            available_total = max(0, avail_fn(claim_time) - used_fn())
            if available_total <= 0:
                result.update({"status": "QUOTA_EXHAUSTED"})
                return result

    quota_per_person = distribution.get("quota_per_person")
    if quota_per_person is not None:
        used_by_user = _get_policy_callback(context, "used_quota_by_user")
        user_id = inputs.get("user_id")
        if used_by_user is not None and user_id:
            already = used_by_user(user_id)
            if already >= quota_per_person:
                result.update({"status": "USER_QUOTA_EXCEEDED"})
                return result

    merchant_allowed_fn = _get_policy_callback(context, "is_merchant_allowed")
    product_allowed_fn = _get_policy_callback(context, "is_product_allowed")
    merchant_scope = usage_limits.get("merchant_scope")
    product_scope = usage_limits.get("product_scope")

    if merchant_allowed_fn is not None:
        if not merchant_allowed_fn(inputs.get("merchant_id"), merchant_scope):
            result.update({"status": "OUT_OF_SCOPE"})
            return result
    if product_allowed_fn is not None:
        if not product_allowed_fn(inputs.get("product_id"), product_scope):
            result.update({"status": "OUT_OF_SCOPE"})
            return result

    time_restrictions = usage_limits.get("time_restrictions")
    if time_restrictions:
        time_allowed_fn = _get_policy_callback(context, "is_time_allowed")
        if time_allowed_fn is not None:
            if not time_allowed_fn(claim_time, time_restrictions):
                result.update({"status": "TIME_RESTRICTED"})
                return result

    stacking = usage_limits.get("stacking", {})
    allow_other_coupons = _parse_policy_bool(stacking.get("with_other_coupons"), True)
    allow_merchant_discount = _parse_policy_bool(stacking.get("with_merchant_discount"), True)

    if not allow_other_coupons and inputs.get("using_other_coupon"):
        result.update({"status": "STACKING_NOT_ALLOWED_COUPON"})
        return result
    if not allow_merchant_discount and inputs.get("has_merchant_discount"):
        result.update({"status": "STACKING_NOT_ALLOWED_MERCHANT"})
        return result

    matched_tier = None
    best_discount = 0.0
    best_threshold = -1.0

    for tier in tiers:
        if tier.get("type") != coupon_type:
            continue
        threshold = _parse_optional_number(tier["threshold"])
        if threshold is None:
            raise ValueError("Missing policy coupon threshold")
        if amount < threshold:
            continue

        if coupon_type == "AMOUNT":
            discount = _parse_optional_number(tier["discount"])
            if discount is None:
                raise ValueError("Missing policy coupon discount")
        else:
            discount_rate = _parse_optional_number(tier["discount"])
            if discount_rate is None:
                raise ValueError("Missing policy coupon discount")
            discount = amount * discount_rate
            cap = _parse_optional_number(tier.get("cap"))
            if cap is not None and discount > cap:
                discount = cap

        if discount > best_discount or (
            abs(discount - best_discount) < 1e-9 and threshold > best_threshold
        ):
            best_discount = discount
            best_threshold = threshold
            matched_tier = dict(tier)
            matched_tier.setdefault("name", None)
            matched_tier["cap"] = _parse_optional_number(tier.get("cap"))

    if matched_tier is None or best_discount <= 0:
        result.update({"status": "NOT_QUALIFIED"})
        return result

    discount_value = _round_policy_value(best_discount, 2)
    final_amount = _round_policy_value(max(0.0, amount - discount_value), 2)
    result.update({
        "status": "QUALIFIED",
        "discount": discount_value,
        "final_amount": final_amount,
        "tier": matched_tier
    })
    return result
