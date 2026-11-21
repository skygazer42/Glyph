"""Changzhou execution of national vehicle aid, with distinct tax semantics."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from math import isfinite
import re

from app.agents.dsl_generator.trade_in_calculations import auto_trade_in_2026


def _result(status: str, reason: str, amount: Decimal = Decimal(0)) -> dict:
    return {"status": status, "amount": float(amount), "reason": reason}


def _required(inputs: Mapping, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if inputs.get(field) is None]
    if missing:
        raise ValueError("缺少必填事实：" + "、".join(missing))


def _flag(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label}须明确填写是或否")
    return value


def _price(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("价格须为大于零的有限数值")
    amount = Decimal(str(value))
    if (
        not amount.is_finite()
        or amount <= 0
        or not isfinite(float(amount))
        or float(amount) == 0
    ):
        raise ValueError("价格须为大于零且可表示的有限数值")
    return amount


def _date(value: object) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError("日期须为YYYY-MM-DD格式")
    return date.fromisoformat(value)


def changzhou_auto_trade_in_2026(inputs: Mapping, mode: str = "replace") -> dict:
    """Apply local invoice/registration gates; do not invent a local top-up."""
    if not isinstance(inputs, Mapping):
        return _result("INVALID_INPUT", "输入须为事实字段对象")
    national = auto_trade_in_2026(inputs, mode=mode)
    if national["status"] == "INVALID_INPUT":
        return national
    try:
        _required(
            inputs,
            (
                "invoice_city",
                "registration_province",
                "local_new_car_subsidy_claimed",
                "quota_status",
            ),
        )
        city = inputs["invoice_city"]
        province = inputs["registration_province"]
        if (
            not isinstance(city, str)
            or not city.strip()
            or not isinstance(province, str)
            or not province.strip()
        ):
            raise ValueError("开票城市和登记省份须为非空文本")
        conflict = _flag(
            inputs["local_new_car_subsidy_claimed"], "是否已申报地方纯购新车补贴"
        )
        quota = inputs["quota_status"]
        if not isinstance(quota, str) or quota not in {
            "available",
            "unknown",
            "exhausted",
        }:
            raise ValueError("平台受理额度状态须选择available、unknown或exhausted")
        if city.strip() not in {"常州", "常州市"} or province.strip() not in {
            "江苏",
            "江苏省",
        }:
            return _result(
                "INELIGIBLE", "常州受理要求新车发票在常州市开具、新车在江苏省注册登记"
            )
        if national["status"] != "CALCULATED":
            return national
        if conflict:
            return _result(
                "MANUAL_REVIEW",
                "已申报地方纯购新车补贴，需由平台核验重复申领、核减或撤回情况，不自动叠加金额",
            )
        if quota != "available":
            return _result(
                "MANUAL_REVIEW",
                "常州补贴资金限额管理；平台受理额度不明或已耗尽，须核验本次申请可否受理，金额暂不确定",
            )
        national["reason"] += (
            "；常州执行全国标准，无额外地方加成。已核对所填常州开票、江苏登记及受理额度状态；额度与身份仍由平台实时复核"
        )
        national["amount_kind"] = "cash_subsidy"
        return national
    except (ValueError, DecimalException, OverflowError) as exc:
        return _result("INVALID_INPUT", str(exc))


def changzhou_nev_purchase_tax_2026(inputs: Mapping) -> dict:
    """Return tax payable for a domestic self-use NEV passenger car in 2026.

    The input is the explicit VAT-exclusive vehicle invoice base. A separately
    invoiced battery is not part of that base; imported/self-produced cars and
    unresolved electronic tax marks need the tax authority's assessment.
    """
    if not isinstance(inputs, Mapping):
        return _result("INVALID_INPUT", "输入须为事实字段对象")
    try:
        flags = (
            "new_passenger_car",
            "nev_in_current_catalog",
            "tax_exemption_mark_verified",
            "domestic_purchase_for_own_use",
            "battery_invoice_separate",
        )
        _required(inputs, ("price_ex_vat", "purchase_date") + flags)
        price = _price(inputs["price_ex_vat"])
        purchased = _date(inputs["purchase_date"])
        facts = {field: _flag(inputs[field], field) for field in flags}
        if purchased.year != 2026:
            return _result(
                "INELIGIBLE",
                "本规则仅测算2026年购置；2024—2025年3万元免税额口径不适用。2027年请核验对应年度规则",
            )
        if not facts["nev_in_current_catalog"]:
            return _result(
                "INELIGIBLE",
                "未列入购置时有效减免税车型目录，不能按本优惠估算；金额0不代表无需缴税",
            )
        if not all(
            facts[field]
            for field in (
                "new_passenger_car",
                "tax_exemption_mark_verified",
                "domestic_purchase_for_own_use",
            )
        ):
            return _result(
                "MANUAL_REVIEW",
                "仅支持境内购买自用的新能源乘用新车且已核验有效减免税标识；其他情形交税务机关核定，金额0不代表免税",
            )
        normal = price * Decimal("0.10")
        reduction = min(normal / 2, Decimal("15000"))
        payable = normal - reduction
        cent = Decimal("0.01")
        result = _result(
            "CALCULATED",
            "全国税收政策在常州适用：不含增值税计税价格×10%，减半但减税额最高15000元；amount为应缴购置税，不是现金补贴。分位四舍五入仅作展示，实际依税务机关核定",
            payable.quantize(cent, rounding=ROUND_HALF_UP),
        )
        if facts["battery_invoice_separate"]:
            result["reason"] += (
                "；换电车电池分别核算并单独开票时，仅输入不含电池车身发票的不含税价，且须符合换电模式标准及标识要求"
            )
        result.update(
            normal_tax=float(normal.quantize(cent, rounding=ROUND_HALF_UP)),
            tax_reduction=float(reduction.quantize(cent, rounding=ROUND_HALF_UP)),
            amount_kind="tax_payable",
        )
        return result
    except (ValueError, DecimalException, OverflowError) as exc:
        return _result("INVALID_INPUT", str(exc))


def changzhou_electric_bicycle_2026(inputs: Mapping) -> dict:
    """Avoid assigning the old 30%/1000 policy to an unverified 2026 scheme."""
    if not isinstance(inputs, Mapping):
        return _result("INVALID_INPUT", "输入须为事实字段对象")
    try:
        _required(inputs, ("price", "purchase_date"))
        _price(inputs["price"])
        purchased = _date(inputs["purchase_date"])
        if purchased.year != 2026:
            return _result("INELIGIBLE", "本入口仅核查2026年常州电动自行车补贴")
        return _result(
            "MANUAL_REVIEW",
            "截至2026-11-21，已核验的常州官方页面只列交旧、合规新车、常州上牌和同一车主等要求，未明确2026有效补贴金额及活动期；不能套用2025年30%最高1000元。请向商务部门核验本期细则，金额暂不确定",
        )
    except (ValueError, DecimalException, OverflowError) as exc:
        return _result("INVALID_INPUT", str(exc))
