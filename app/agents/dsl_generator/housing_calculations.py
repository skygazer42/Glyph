"""Changzhou housing estimates from explicit verified facts, not approvals.

Sources: 常公积金委〔2026〕5号 and the official 2026 home-purchase aid
announcement, with separately preserved official interpretations. The three pure functions cover only the source-backed local scenarios.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal, DecimalException, ROUND_DOWN
from math import isfinite
from typing import Any


_START = date(2026, 9, 20)
_ZERO = Decimal("0")


def _number(inputs: dict[str, Any], key: str, *, positive: bool = False) -> Decimal:
    value = inputs[key]
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{key}必须为有限数值，不能为布尔值")
    number = Decimal(str(value))
    if (
        not number.is_finite()
        or not isfinite(float(number))
        or (number != 0 and float(number) == 0)
    ):
        raise ValueError(f"{key}超出有限数值输入范围")
    if number < 0 or (positive and number == 0):
        raise ValueError(f"{key}必须为非负数，费用或房价须大于零")
    return number


def _integer(inputs: dict[str, Any], key: str) -> int:
    value = _number(inputs, key)
    if value != value.to_integral_value():
        raise ValueError(f"{key}须为非负整数")
    return int(value)


def _boolean(inputs: dict[str, Any], key: str) -> bool:
    value = inputs[key]
    if type(value) is not bool:
        raise ValueError(f"{key}须明确填写是或否")
    return value


def _date(inputs: dict[str, Any], key: str) -> date:
    value = inputs[key]
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{key}须为YYYY-MM-DD日期")
    return date.fromisoformat(value)


def _months_after(value: date, months: int) -> tuple[int, int, int]:
    """Calendar anniversary key; no 30-day approximation or year-9999 overflow."""
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return year, month, min(value.day, calendar.monthrange(year, month)[1])


def _result(
    status: str,
    reason: str,
    amount: Decimal = _ZERO,
    calculation_type: str = "provident_withdrawal",
) -> dict[str, Any]:
    return dict(
        status=status,
        amount=float(amount.quantize(Decimal(".01"), rounding=ROUND_DOWN)),
        reason=reason,
        calculation_type=calculation_type,
    )


def _invalid(error: Exception) -> dict[str, Any]:
    return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")


def changzhou_renovation_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """Estimate verified hard-decoration invoice withdrawals, all owners combined."""
    if not isinstance(inputs, dict):
        return _result("INVALID_INPUT", "inputs须为事实字段对象")
    try:
        claim = _date(inputs, "claim_time")
        certificate = _date(inputs, "certificate_date")
        invoice_date = _date(inputs, "invoice_date")
        invoice = _number(inputs, "invoice_amount", positive=True)
        balance = _number(inputs, "available_balance")
        paid = _number(inputs, "home_withdrawn_amount")
        verified = _boolean(inputs, "eligibility_confirmed")
        loan = _boolean(inputs, "unsettled_provident_loan")
        count = _integer(inputs, "prior_renovation_claims")
        hard_decoration = _boolean(inputs, "hard_decoration_invoice")
        excluded_spouse = _boolean(inputs, "nonowner_spouse_premarital_home")
        if certificate > claim or invoice_date > claim:
            raise ValueError("权证日期或发票日期不能晚于申请日期")
    except (KeyError, ValueError, TypeError, OverflowError, DecimalException) as error:
        return _invalid(error)
    if claim < _START or invoice_date < _START:
        return _result(
            "INELIGIBLE", "常州装修提取自2026-09-20施行，装修发票不能早于新政实施"
        )
    if invoice_date == _START:
        return _result(
            "MANUAL_REVIEW",
            "官方解读要求开票日期在9月20日后；实施当日发票的受理口径请向常州公积金中心核实",
        )
    if not verified:
        return _result(
            "MANUAL_REVIEW",
            "须先核实常州自住住房产权/配偶关系、真实装修合同和发票、缴存及可用余额",
        )
    if loan:
        return _result(
            "INELIGIBLE", "申请时须在本市无未还清的住房公积金贷款，含公转商贷款"
        )
    if count:
        return _result(
            "INELIGIBLE", "常州每人仅可就名下一套自住住房申请装修提取1次，不能重复办理"
        )
    if excluded_spouse:
        return _result(
            "INELIGIBLE", "婚前购买的住房，配偶不是权证载明权利人的，不可办理装修提取"
        )
    if not hard_decoration:
        return _result(
            "INELIGIBLE",
            "仅多空间多工种整体硬装发票计入；家具家电、装饰陈设等软装不计入",
        )
    claim_key = claim.year, claim.month, claim.day
    if not (
        _months_after(certificate, 6) <= claim_key <= _months_after(certificate, 60)
        or claim_key >= _months_after(certificate, 180)
    ):
        return _result("INELIGIBLE", "权证须满6个日历月且不超过5年，或满15个日历年")
    limit = min(invoice, Decimal("100000"))
    if paid >= limit:
        return _result(
            "INELIGIBLE", "同套住房所有提取人累计额度已达装修发票金额或10万元上限"
        )
    return _result(
        "CALCULATED",
        "按真实硬装发票、同套所有提取人10万元上限、既提金额及已核实可用余额试算；不代表审批",
        min(limit - paid, balance),
    )


def changzhou_property_fee_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """Estimate one contributor's annual fee withdrawal within the dwelling cap.

    invoice_amount_for_year is the verified part of property/elevator invoices
    allocated to claim_time's calendar year, not an invoice spanning all years.
    """
    if not isinstance(inputs, dict):
        return _result("INVALID_INPUT", "inputs须为事实字段对象")
    try:
        claim = _date(inputs, "claim_time")
        verified = _boolean(inputs, "eligibility_confirmed")
        loan = _boolean(inputs, "unsettled_provident_loan")
        year = _integer(inputs, "invoice_year")
        invoice = _number(inputs, "invoice_amount_for_year")
        balance = _number(inputs, "available_balance")
        personal_claimed = _boolean(inputs, "personal_claimed_this_year")
        home_paid = _number(inputs, "home_withdrawn_this_year")
    except (KeyError, ValueError, TypeError, OverflowError, DecimalException) as error:
        return _invalid(error)
    if claim < _START:
        return _result("INELIGIBLE", "常州物业费提取自2026-09-20施行")
    if not verified:
        return _result(
            "MANUAL_REVIEW",
            "须核实自住住房产权/配偶关系、当年发票分摊、年度提取记录及可用余额",
        )
    if loan:
        return _result(
            "INELIGIBLE", "本市有未还清的住房公积金或公转商贷款，不符合本类提取条件"
        )
    if personal_claimed:
        return _result("INELIGIBLE", "每人每自然年仅可就名下一套自住住房提取1次")
    if year != claim.year:
        return _result(
            "INELIGIBLE",
            "只按申请自然年度对应的物业/电梯费发票金额测算，不补提其他年度",
        )
    limit = min(invoice, Decimal("3000"))
    if home_paid >= limit and limit:
        return _result(
            "INELIGIBLE", "同套住房所有提取人本年度发票对应额度或3000元额度已用尽"
        )
    return _result(
        "CALCULATED",
        "按当年物业/电梯费发票金额及每套所有提取人3000元上限扣除已提额，再受已核实可用余额约束；不结转，不代表审批",
        min(max(_ZERO, limit - home_paid), balance),
    )


def changzhou_home_purchase_2026(
    inputs: dict[str, Any], kind: str = "new"
) -> dict[str, Any]:
    """Estimate verified 2026 purchase-price aid, not a direct cash payment.

    new means housing library A and contract filing; existing means library B
    and property transfer registration. Existing sellers' subsequent 180-day
    improvement purchases are a distinct scenario and are not estimated here.
    """
    if (
        not isinstance(inputs, dict)
        or not isinstance(kind, str)
        or kind not in ("new", "existing")
    ):
        return _result("INVALID_INPUT", "inputs须为对象，kind仅支持new或existing")
    try:
        claim = _date(inputs, "claim_time")
        completion = _date(inputs, "completion_date")
        price = _number(inputs, "contract_price", positive=True)
        existing_area = _number(inputs, "household_existing_area")
        area = _number(inputs, "purchased_area", positive=True)
        verified = _boolean(inputs, "eligibility_confirmed")
        voucher = _boolean(inputs, "voucher_confirmed")
        library = _boolean(inputs, "eligible_library_confirmed")
        used = _boolean(inputs, "voucher_already_used")
        expropriation = _boolean(inputs, "expropriation_voucher_used")
        guarantee = _boolean(inputs, "guarantee_agreement_confirmed")
        supervised = (
            _boolean(inputs, "funds_supervision_confirmed")
            if kind == "existing"
            else True
        )
        if completion > claim:
            raise ValueError("网签备案/不动产转移登记完成日期不能晚于申请日期")
    except (KeyError, ValueError, TypeError, OverflowError, DecimalException) as error:
        return _invalid(error)
    if not (claim.year == completion.year == 2026):
        return _result(
            "INELIGIBLE",
            "仅测算2026年办理且年内完成新房合同网签备案或存量房不动产转移登记的场景",
        )
    if not verified or not voucher or not library or not guarantee or not supervised:
        return _result(
            "MANUAL_REVIEW",
            "须核实住房困难工薪资格、配偶共同申请、A/B房源库、资格凭证、资助及担保协议；存量房还须全额资金监管",
        )
    if used or expropriation:
        return _result(
            "INELIGIBLE", "资格凭证只能使用一次；凭征收房票购房不享受本项资助"
        )
    if existing_area > 75:
        return _result(
            "INELIGIBLE", "申请人及配偶在常州已有商品住房建筑面积合计须不超过75平方米"
        )
    if (kind == "new" and area > 140) or (kind == "existing" and area <= 75):
        return _result(
            "INELIGIBLE",
            "A库新建商品住房须140平方米及以下；B库成套存量商品住房须75平方米以上",
        )
    cap = Decimal("200000") if kind == "new" else Decimal("180000")
    return _result(
        "CALCULATED",
        "按网签备案合同购房款15%及新房20万元/存量18万元封顶试算；为购房款抵扣资助，不直接付现，后续交易或另购房须全额无息归还；不代表审批",
        min(price * Decimal(".15"), cap),
        "purchase_price_deduction",
    )
