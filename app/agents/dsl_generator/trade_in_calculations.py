"""Source-backed national 2026 estimates; supplied facts are not approval records."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from math import isfinite
import re


_YEAR_START = date(2026, 1, 1)
_YEAR_END = date(2026, 12, 31)
_OWNERSHIP_CUTOFF = date(2025, 1, 8)
_APPLIANCES = {
    "refrigerator", "washing_machine", "tv", "air_conditioner", "water_heater", "computer",
}
_DIGITAL_PRODUCTS = {"phone", "tablet", "smart_watch_band", "smart_glasses"}
_PRODUCT_FLAGS = (
    "individual_consumer", "participating_merchant", "new_product",
    "identity_consistent", "real_name_single_item_invoice",
)
_CAR_FLAGS = (
    "individual_consumer", "old_passenger_car", "new_passenger_car", "same_owner",
    "new_owned_during_review", "same_province", "documents_valid",
)


def _result(status: str, reason: str, amount: Decimal = Decimal(0)) -> dict:
    return {"status": status, "amount": float(amount), "reason": reason}


def _required(inputs: Mapping, fields: tuple) -> None:
    missing = [field for field in fields if field not in inputs or inputs[field] is None]
    if missing:
        raise ValueError("缺少必填事实：" + "、".join(missing))


def _number(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{name}须为有限数值")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name}须为有限数值") from exc
    if not number.is_finite():
        raise ValueError(f"{name}须为有限数值")
    # Match the DSL's float input contract before performing Decimal arithmetic.
    approximate = float(number)
    if not isfinite(approximate) or (number != 0 and approximate == 0):
        raise ValueError(f"{name}超出浮点输入可表示范围")
    return number


def _positive(value: object, name: str) -> Decimal:
    number = _number(value, name)
    if number <= 0:
        raise ValueError(f"{name}须大于零")
    return number


def _count(value: object, name: str) -> int:
    number = _number(value, name)
    if number < 0 or number != number.to_integral_value():
        raise ValueError(f"{name}须为非负整数")
    return int(number)


def _flag(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name}须明确填写是或否")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}须为非空文本选项")
    return value


def _date(value: object, name: str) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError(f"{name}须为YYYY-MM-DD日期")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name}不是有效日期") from exc


def _in_2026(day: date) -> bool:
    return _YEAR_START <= day <= _YEAR_END


def _product_subsidy(inputs: Mapping, *, appliance: bool) -> dict:
    if not isinstance(inputs, Mapping):
        return _result("INVALID_INPUT", "输入须为事实字段对象")
    try:
        fields: tuple[str, ...] = ("price", "category", "claim_time", "purchase_date", "invoice_date", "prior_category_claims") + _PRODUCT_FLAGS
        if appliance:
            fields += ("energy_level",)
        _required(inputs, fields)
        price = _positive(inputs["price"], "最终销售价格")
        category = _text(inputs["category"], "产品品类")
        count = _count(inputs["prior_category_claims"], "本年同类已使用补贴次数")
        flags = {field: _flag(inputs[field], field) for field in _PRODUCT_FLAGS}
        claim = _date(inputs["claim_time"], "申领日期")
        purchase = _date(inputs["purchase_date"], "购买日期")
        invoice = _date(inputs["invoice_date"], "发票日期")
        if appliance:
            energy = _count(inputs["energy_level"], "能效或水效等级")
        if not _in_2026(claim) or not _in_2026(purchase) or not _in_2026(invoice):
            return _result("INELIGIBLE", "本规则仅测算2026年度购买、开票并申领的交易；跨年申请需按当地实施细则核验")
        if purchase > claim or invoice > claim:
            return _result("INVALID_INPUT", "购买或发票日期不能晚于申领日期")
        categories = _APPLIANCES if appliance else _DIGITAL_PRODUCTS
        if category not in categories:
            return _result("INELIGIBLE", "产品不在本规则全国统一支持品类内")
        if appliance and energy != 1:
            return _result("INELIGIBLE", "家电须符合1级能效或水效标准")
        if not appliance and price > Decimal("6000"):
            return _result("INELIGIBLE", "数码及智能产品单件最终销售价格须不超过6000元")
        if count != 0:
            return _result("INELIGIBLE", "2026年每人每类仅补贴1件，已有未恢复资格的同类补贴记录")
        if not all(flags.values()):
            return _result("INELIGIBLE", "须为个人购买新产品、参与商家销售、申领付款收货人一致且具备实名单件发票")
        cap = Decimal("1500") if appliance else Decimal("500")
        amount = min(price * Decimal("0.15"), cap).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return _result("CALCULATED", "按扣除商家等各环节优惠后、政府补贴前销售价的15%测算；分位金额四舍五入仅用于展示。资格、产品备案、额度及兑付由当地平台核验，非审批结果", amount)
    except (ValueError, OverflowError, DecimalException) as exc:
        return _result("INVALID_INPUT", str(exc))


def appliance_subsidy_2026(inputs: Mapping) -> dict:
    """Estimate one of six level-one appliances, per person/category, for 2026."""
    return _product_subsidy(inputs, appliance=True)


def digital_subsidy_2026(inputs: Mapping) -> dict:
    """Estimate one of four digital categories priced at most 6,000 yuan."""
    return _product_subsidy(inputs, appliance=False)


def changzhou_smart_goods_2026(inputs: Mapping) -> dict:
    """Estimate a platform-verified local subcategory, separate from national goods."""
    if not isinstance(inputs, Mapping):
        return _result("INVALID_INPUT", "输入须为事实字段对象")
    categories = {
        "smart_door_lock",
        "smart_air_purifier",
        "smart_lighting",
        "smart_range_hood",
        "smart_gas_stove",
        "smart_steam_microwave_oven",
        "smart_food_processor",
        "smart_dishwasher",
        "smart_water_purifier",
        "smart_dryer",
        "smart_toilet",
        "smart_cleaning_robot",
        "digital_camera",
        "smart_speaker",
        "smart_headphones",
        "embodied_robot",
        "smart_printer",
        "smart_massage_chair",
        "smart_monitor",
        "electric_wheelchair",
    }
    flags = (
        "individual_consumer",
        "participating_merchant",
        "platform_category_confirmed",
        "current_round_product_confirmed",
        "claims_history_confirmed",
        "no_duplicate_subsidy_confirmed",
        "has_efficiency_label",
    )
    try:
        _required(
            inputs,
            (
                "price",
                "category",
                "claim_time",
                "purchase_date",
                "product_code",
                "prior_category_claims",
                "budget_status",
            )
            + flags,
        )
        price = _positive(inputs["price"], "优惠后政府补贴前销售价")
        category = _text(inputs["category"], "本期细分品类")
        claim = _date(inputs["claim_time"], "业务申请日期")
        purchase = _date(inputs["purchase_date"], "购买日期")
        code = inputs["product_code"]
        if not isinstance(code, str) or re.fullmatch(r"[0-9]{13}", code) is None:
            raise ValueError(
                "商品码须为13位半角数字文本；格式符合不代表已获平台商品备案"
            )
        count = _count(inputs["prior_category_claims"], "本人本期细分品类已享次数")
        facts = {field: _flag(inputs[field], field) for field in flags}
        budget = _text(inputs["budget_status"], "本次受理预算状态")
        if budget not in {"available", "unknown", "exhausted"}:
            raise ValueError("预算状态须为available、unknown或exhausted")
        if facts["has_efficiency_label"]:
            _required(inputs, ("efficiency_level", "efficiency_registered"))
            level = _count(inputs["efficiency_level"], "能效或水效等级")
            registered = _flag(inputs["efficiency_registered"], "标识网备案已核实")
        if purchase > claim:
            raise ValueError("购买日期不能晚于业务申请日期")
        if not all(date(2026, 8, 29) <= day <= _YEAR_END for day in (purchase, claim)):
            return _result(
                "NOT_IN_PERIOD",
                "本入口仅计算2026-08-29至12-31内购买并办理的交易；资金用完即止，其他时点须另核",
            )
        if category not in categories:
            return _result(
                "INELIGIBLE",
                "不在本入口20个原文明列主要产品项中；括号子产品须先由平台确认映射，不能混入全国六类或电动自行车",
            )
        if count != 0:
            return _result(
                "INELIGIBLE", "每人每细分品类1件；已有尚未恢复资格的记录不能再次计算"
            )
        if facts["has_efficiency_label"] and level != 1:
            return _result(
                "INELIGIBLE", "具有能效或水效标识的商品须为中国能效或水效一级"
            )
        if not all(facts[field] for field in flags if field != "has_efficiency_label"):
            return _result(
                "MANUAL_REVIEW",
                "须明示核实个人资格、参与商户、本期商品及细分品类、跨渠道历史/退货恢复和全国地方重复；套装不得拆分双算，未知事实不推定满足",
            )
        if facts["has_efficiency_label"] and not registered:
            return _result(
                "MANUAL_REVIEW", "须核实一级能效或水效标识已在相应标识网备案"
            )
        if budget != "available":
            return _result(
                "MANUAL_REVIEW",
                "本次受理预算尚未确认可用或已耗尽；限额管理，用完即止，暂不确定金额",
            )
        amount = min(price * Decimal("0.15"), Decimal("1500")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return _result(
            "CALCULATED",
            "常州地方自主品类：优惠后政府补贴前价格×15%，每件最高1500元、每人每细分品类1件；分位四舍五入仅作展示，非官方统一舍入规则。平台须复核商品码、预算和重复，非审批结果",
            amount,
        )
    except (ValueError, OverflowError, DecimalException) as exc:
        return _result("INVALID_INPUT", str(exc))


def auto_trade_in_2026(inputs: Mapping, mode: str = "scrap") -> dict:
    """Check supplied national conditions and ceil the capped car estimate to yuan.

    The official handbook defines January 1 inclusively. This calculator accepts
    only claims within 2026; local cross-year deadlines need separate review.
    Ownership dates refer to the current uninterrupted ownership period.
    """
    if not isinstance(inputs, Mapping) or not isinstance(mode, str) or mode not in {"scrap", "replace"}:
        return _result("INVALID_INPUT", "输入须为事实字段对象，模式须为scrap或replace")
    try:
        date_fields: tuple[str, ...] = ("new_invoice_date", "new_registration_date")
        date_fields += (
            "scrap_certificate_date", "scrap_delivery_date", "deregistration_date",
            "deregistration_certificate_date",
        ) if mode == "scrap" else ("transfer_invoice_date", "transfer_registration_date")
        required: tuple[str, ...] = ("price", "claim_time", "old_owned_since", "new_fuel", "prior_auto_claims") + _CAR_FLAGS + date_fields
        if mode == "scrap":
            required += ("old_fuel", "old_registration_date", "qualified_scrapper")
        _required(inputs, required)
        price = _positive(inputs["price"], "新车含税发票价格")
        count = _count(inputs["prior_auto_claims"], "2026年汽车报废和置换合计已享次数")
        flags = {field: _flag(inputs[field], field) for field in _CAR_FLAGS}
        claim = _date(inputs["claim_time"], "申领日期")
        owned_since = _date(inputs["old_owned_since"], "旧车本次连续登记至本人名下日期")
        document_dates = {field: _date(inputs[field], field) for field in date_fields}
        if mode == "scrap":
            registered = _date(inputs["old_registration_date"], "旧车首次注册日期")
            old_fuel = _text(inputs["old_fuel"], "旧车燃料类型")
            qualified_scrapper = _flag(inputs["qualified_scrapper"], "有资质回收拆解企业")
        new_fuel = _text(inputs["new_fuel"], "新车燃料类型")
        if new_fuel == "nev":
            _required(inputs, ("nev_in_catalog",))
            new_qualifies = _flag(inputs["nev_in_catalog"], "新车纳入减免车辆购置税目录")
        elif new_fuel == "fuel":
            _required(inputs, ("displacement_liters",))
            new_qualifies = _positive(inputs["displacement_liters"], "新车排量") <= Decimal("2.0")
        else:
            return _result("INELIGIBLE", "新车须为目录内新能源乘用车或排量2.0升及以下燃油乘用车")
        if not _in_2026(claim) or any(not _in_2026(day) for day in document_dates.values()):
            return _result("INELIGIBLE", "所需凭证须在2026年取得；本规则仅测算2026年内申请，跨年受理截止日期另按当地细则核验")
        if any(day > claim for day in document_dates.values()):
            return _result("INVALID_INPUT", "凭证日期不能晚于申领日期")
        if document_dates["new_registration_date"] < document_dates["new_invoice_date"]:
            return _result("INVALID_INPUT", "新车登记日期不能早于新车销售发票日期")
        disposal = document_dates["scrap_delivery_date" if mode == "scrap" else "transfer_registration_date"]
        if owned_since > disposal:
            return _result("INVALID_INPUT", "旧车登记至本人日期不能晚于处置日期")
        if mode == "scrap" and (registered > owned_since or document_dates["deregistration_date"] < disposal):
            return _result("INVALID_INPUT", "旧车首次注册、本人登记、回收和注销日期顺序矛盾")
        if mode == "scrap" and (
            document_dates["scrap_certificate_date"] < disposal
            or document_dates["deregistration_certificate_date"] < document_dates["deregistration_date"]
        ):
            return _result("INVALID_INPUT", "回收或注销证明取得日期不能早于其记载的实际处置日期")
        if mode == "replace" and disposal < document_dates["transfer_invoice_date"]:
            return _result("INVALID_INPUT", "旧车转让登记日期不能早于二手车销售发票日期")
        if owned_since > _OWNERSHIP_CUTOFF:
            return _result("INELIGIBLE", "旧车须于2025年1月8日（含）前登记在申请人名下")
        if count != 0:
            return _result("INELIGIBLE", "2026年每人仅能享受一次汽车报废更新或置换更新补贴，两者不可重复")
        if not all(flags.values()) or not new_qualifies:
            return _result("INELIGIBLE", "个人、乘用车、同一车主、审核期间名下、同省发票登记、完整有效凭证及新车车型条件须同时满足")
        if mode == "scrap":
            cutoffs = {"gasoline": date(2013, 6, 30), "diesel": date(2015, 6, 30), "other": date(2015, 6, 30), "nev": date(2019, 12, 31)}
            if old_fuel not in cutoffs or registered > cutoffs[old_fuel]:
                return _result("INELIGIBLE", "旧车燃料类型或首次注册日期不符合2026年报废门槛")
            if not qualified_scrapper:
                return _result("INELIGIBLE", "回收证明须由有资质的报废机动车回收拆解企业开具")
            if old_fuel == "nev" and new_fuel == "fuel":
                return _result("INELIGIBLE", "报废新能源旧车仅支持购买符合条件的新能源新车")
            rate, cap = (Decimal("0.12"), Decimal("20000")) if new_fuel == "nev" else (Decimal("0.10"), Decimal("15000"))
        else:
            rate, cap = (Decimal("0.08"), Decimal("15000")) if new_fuel == "nev" else (Decimal("0.06"), Decimal("13000"))
        amount = min(price * rate, cap).quantize(Decimal("1"), rounding=ROUND_CEILING)
        return _result("CALCULATED", "按新车含税发票金额及全国比例封顶、向上取整至整元试算；仅核对所填事实，不代替平台身份、车辆、年度次数及地方资金审核，非审批结果", amount)
    except (ValueError, OverflowError, DecimalException) as exc:
        return _result("INVALID_INPUT", str(exc))
