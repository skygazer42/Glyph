"""Changzhou provident money estimates from preserved official terms.

Policy ceilings, account support and affordability remain separate limits.
Repayment schedules use cent-rounded monthly interest for an explicit estimate;
actual bank schedules and later rate adjustments take precedence.
"""

from __future__ import annotations

from datetime import date
from decimal import (
    Decimal,
    DecimalException,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_HALF_UP,
    localcontext,
)
from math import isfinite
from typing import Any

_ZERO = Decimal(0)
_CENT = Decimal(".01")
_ERRORS = (KeyError, TypeError, ValueError, OverflowError, DecimalException)


def _number(
    inputs: dict, key: str, *, integer: bool = False, positive: bool = False
) -> Decimal:
    """Accept finite numeric facts, preserving zero and rejecting booleans."""
    value = inputs[key]
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{key}须为有限数值")
    number = Decimal(str(value))
    if not number.is_finite() or not isfinite(float(number)) or number < 0:
        raise ValueError(f"{key}须为有限非负数")
    if positive and number == 0 or integer and number != number.to_integral_value():
        raise ValueError(f"{key}须为有效正数/整数")
    return number


def _flag(inputs: dict, key: str) -> bool:
    """Require an explicit boolean qualification fact."""
    value = inputs[key]
    if type(value) is not bool:
        raise ValueError(f"{key}须明确填写是或否")
    return value


def _claim(inputs: dict) -> date:
    """Read an explicit ISO business date, without inferring it from the clock."""
    if not isinstance(inputs, dict):
        raise ValueError("inputs须为对象")
    text = inputs["claim_time"]
    if not isinstance(text, str):
        raise ValueError("claim_time须为YYYY-MM-DD")
    value = date.fromisoformat(text)
    if value.isoformat() != text:
        raise ValueError("claim_time须为YYYY-MM-DD")
    return value


def _result(status: str, reason: str, amount: Decimal = _ZERO, **details: Any) -> dict:
    """Return a currency amount and explain the limit or unresolved condition."""
    return dict(
        status=status,
        amount=float(amount.quantize(_CENT, rounding=ROUND_DOWN)),
        reason=reason,
        **details,
    )


def _invalid(error: Exception) -> dict:
    return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")


def _rate(inputs: dict, years: int) -> Decimal:
    """Use the published tier, never infer it from account history or house count."""
    tier = inputs["rate_class"]
    if tier not in ("first", "second"):
        raise ValueError("rate_class须为官方核定的first或second档")
    return (
        Decimal("2.1" if years <= 5 else "2.6")
        if tier == "first"
        else Decimal("2.525" if years <= 5 else "3.075")
    )


def _payment_factor(rate: Decimal, months: int, method: str) -> Decimal:
    """First monthly payment per unit principal for the selected repayment method."""
    monthly = rate / Decimal(1200)
    if method == "equal_principal":
        return Decimal(1) / months + monthly
    if method != "annuity":
        raise ValueError("repayment_method仅支持annuity或equal_principal")
    growth = (1 + monthly) ** months
    return monthly * growth / (growth - 1)


def changzhou_provident_hardship_subsidy_2026(inputs: dict) -> dict:
    """Estimate prior-year loan-interest aid under 常公积金委〔2026〕3号.

    The confirmed highest household category determines one annual entitlement.
    The interest basis excludes overdue compound/penalty interest; this is not
    the separate 50% deposit-interest subsidy with a 5000-yuan settlement cap.
    """
    try:
        claim = _claim(inputs)
        if not date(2026, 7, 1) <= claim <= date(2031, 6, 30):
            return _result("NOT_IN_PERIOD", "本办法适用期为2026-07-01至2031-06-30")
        year = int(_number(inputs, "interest_year", integer=True))
        recognized = int(_number(inputs, "recognition_year", integer=True))
        if year != claim.year - 1 or recognized != year:
            raise ValueError("须使用办理上年度的困难认定和实际支付贷款利息")
        interest = _number(inputs, "eligible_interest_paid_previous_year")
        confirmed = _flag(inputs, "eligibility_confirmed")
        highest = _flag(inputs, "highest_class_confirmed")
        basis = _flag(inputs, "interest_basis_confirmed")
        local_loan = _flag(inputs, "loan_issued_in_changzhou")
        overdue = _flag(inputs, "loan_currently_overdue")
        received = _flag(inputs, "subsidy_already_received_for_year")
        category = inputs["difficulty_class"]
        rates = {
            "extreme": Decimal(1), "minimum": Decimal(1),
            "minimum_edge": Decimal(".8"), "general": Decimal(".8"),
            "rigid_expense": Decimal(".8"), "none": _ZERO,
        }
        if category not in rates:
            raise ValueError("困难类型须为已核定的五类标准或不符合")
        if not confirmed or not highest or not basis:
            return _result(
                "MANUAL_REVIEW",
                "须核实上年度本市民政/总工会困难认定，按就高类型且排除逾期复利和罚息；不能用月供或剩余本金代替利息",
            )
        if not local_loan or overdue or received or category == "none":
            return _result(
                "INELIGIBLE",
                "仅本市发放的公积金贷款且贴息时未逾期、符合困难认定；同一自然年度不重复享受",
            )
        rate = rates[category]
        return _result(
            "CALCULATED",
            "按上年度实际支付的合规贷款利息×核定困难类型100%或80%，同年度就高不重复；不再适用旧6000元上限。非申即享，通常二季度审核、三季度发放到还贷账户；试算不代表审核或到账",
            interest * rate,
            amount_type="annual_provident_loan_interest_subsidy",
            subsidy_rate_percent=float(rate * 100),
            interest_year=year,
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_contribution_2026(inputs: dict) -> dict:
    """Estimate standard employee/employer contributions for July 2026–June 2027."""
    try:
        claim = _claim(inputs)
        salary = _number(inputs, "monthly_salary")
        percent = _number(inputs, "rate_percent", integer=True)
        confirmed = _flag(inputs, "standard_employee_confirmed")
        if not 5 <= percent <= 12:
            raise ValueError("普通单位及职工缴存比例须为5%至12%的整数百分比")
        if not date(2026, 7, 1) <= claim <= date(2027, 6, 30):
            return _result(
                "NOT_IN_PERIOD", "本规则仅适用2026年7月至2027年6月的公布缴存标准"
            )
        if not confirmed:
            return _result(
                "MANUAL_REVIEW",
                "须核实工资基数口径、正常单位职工身份及同一缴存比例；困难企业/灵活就业另核",
            )
        base = min(max(salary, Decimal(2660)), Decimal(34080))
        part = (base * percent / 100).to_integral_value(rounding=ROUND_CEILING)
        return _result(
            "CALCULATED",
            "单位与个人分别见分进元、比例一致；个人部分从工资代扣，单位部分非个人现金补贴",
            part * 2,
            assessed_base=float(base),
            employee_monthly=float(part),
            employer_monthly=float(part),
            annual_projection=float(part * 24),
            amount_type="monthly_provident_contribution",
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_loan_2026(inputs: dict) -> dict:
    """Combine account support, nonstacking personal support and financing limits."""
    try:
        claim = _claim(inputs)
        verified = _flag(inputs, "eligibility_confirmed")
        people = int(
            _number(inputs, "qualified_borrowers", integer=True, positive=True)
        )
        first = _number(inputs, "first_loan_average_balance")
        repeat = _number(inputs, "repeat_loan_average_balance")
        supplement = _number(inputs, "supplementary_balance")
        external = _number(inputs, "external_balance")
        cooperative = _number(inputs, "family_cooperative_quota")
        price = _number(inputs, "home_price", positive=True)
        withdrawn = _number(inputs, "purchase_withdrawn")
        income = _number(inputs, "income_monthly", positive=True)
        years = int(_number(inputs, "term_years", integer=True, positive=True))
        age = int(_number(inputs, "borrower_age", integer=True, positive=True))
        land = int(_number(inputs, "remaining_land_years", integer=True))
        home_type = inputs["home_type"]
        if home_type not in ("new", "existing"):
            raise ValueError("home_type须为new或existing")
        quality = _flag(inputs, "high_quality_home")
        green = _flag(inputs, "green_home")
        voucher = _flag(inputs, "housing_aid_voucher")
        support = inputs["support_type"]
        additions = {
            "none": 0,
            "two_children": 300000,
            "three_children": 500000,
            "local_graduate": 200000,
            "veteran": 200000,
        }
        fixed = {
            "military_spouse": 1200000,
            "master_under35": 1500000,
            "doctor_or_recognized_talent": 1800000,
        }
        if support not in additions and support not in fixed:
            raise ValueError("support_type须选择一类已核实支持对象，不得叠加多个身份")
        if people not in (1, 2):
            raise ValueError("qualified_borrowers按1人或2人及以上选择，填1或2")
        if not date(2026, 4, 1) <= claim <= date(2026, 12, 31):
            return _result(
                "NOT_IN_PERIOD", "本规则按已核实的2026年4月起政策试算，其他时段另核"
            )
        if (
            age < 18
            or years > 30
            or age + years > 68
            or home_type == "existing"
            and years > land
        ):
            return _result(
                "INELIGIBLE",
                "须成年、最长30年、到期不超过68周岁且不超过已核实土地剩余年限",
            )
        if not verified or years == 1:
            return _result(
                "MANUAL_REVIEW",
                "须核实资格、60月月均余额/租房还原、共济锁定、支持身份及利率档；一年期到期还本付息的偿付能力由中心审核",
            )
        if home_type == "existing" and (quality or green):
            return _result(
                "INELIGIBLE",
                "高品质50万元及绿色建筑30万元额度支持均限定符合官方认定的新建住房，存量房不可套用",
            )
        if green and claim < date(2026, 8, 1):
            return _result("INELIGIBLE", "绿色建筑额外30万元支持自2026-08-01施行")
        account = first * 60 + repeat * 30 + supplement * 6 + external * 6 + cooperative
        base_cap = Decimal(800000 if people == 1 else 1200000)
        policy = (
            Decimal(fixed[support])
            if support in fixed
            else min(account, base_cap) + additions[support]
        )
        policy += Decimal(500000 if quality else 0) + Decimal(300000 if green else 0)
        downpayment = price * Decimal(".15" if voucher else ".20")
        available_price = max(_ZERO, min(price - downpayment, price - withdrawn))
        rate = _rate(inputs, years)
        with localcontext() as context:
            context.prec = 40
            factor = _payment_factor(rate, years * 12, inputs["repayment_method"])
            monthly_budget = (income / 2).quantize(_CENT, rounding=ROUND_DOWN)
            affordable = monthly_budget / factor
            amount = min(policy, available_price, affordable).quantize(
                _CENT, rounding=ROUND_DOWN
            )
            first_payment = (amount * factor).quantize(_CENT, rounding=ROUND_HALF_UP)
        return _result(
            "CALCULATED",
            "取政策支持额度、房价扣最低首付、房价扣同房已提额和月供不超家庭月收入50%的最小值；非贷款审批，按分向下展示非官方统一取整标准",
            amount,
            account_quota=float(account),
            policy_quota=float(policy),
            minimum_downpayment=float(downpayment),
            income_quota=float(affordable),
            estimated_first_payment=float(first_payment),
            annual_rate_percent=float(rate),
            amount_type="provident_loan_principal",
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_repayment_2026(inputs: dict, method: str = "annuity") -> dict:
    """Estimate monthly payments, total interest and the cent-adjusted last payment."""
    try:
        claim = _claim(inputs)
        principal = _number(inputs, "principal", positive=True)
        years = int(_number(inputs, "term_years", integer=True, positive=True))
        if not 1 <= years <= 30 or method not in ("annuity", "equal_principal"):
            raise ValueError(
                "贷款年限须为1至30的整数，方式须为annuity或equal_principal"
            )
        if claim.year != 2026:
            return _result(
                "NOT_IN_PERIOD",
                "仅按截至2026年公布利率估算，其他年度及合同特别约定须另核",
            )
        rate = _rate(inputs, years)
        if principal != principal.quantize(_CENT):
            raise ValueError("本金最多保留两位小数")
        if years == 1:
            interest = (principal * rate / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
            return _result(
                "CALCULATED",
                "一年期按原文到期一次还本付息；结果为到期本息，不是月供",
                principal + interest,
                total_payment=float(principal + interest),
                total_interest=float(interest),
                annual_rate_percent=float(rate),
                repayment_mode="bullet",
                amount_type="maturity_payment",
            )
        months = years * 12
        monthly_rate = rate / 1200
        with localcontext() as context:
            context.prec = 40
            fixed_payment = (
                principal * _payment_factor(rate, months, method)
            ).quantize(_CENT, rounding=ROUND_HALF_UP)
            fixed_principal = (principal / months).quantize(_CENT, rounding=ROUND_DOWN)
            balance, total_interest = principal, _ZERO
            first_payment, last_payment = _ZERO, _ZERO
            for index in range(months):
                interest = (balance * monthly_rate).quantize(
                    _CENT, rounding=ROUND_HALF_UP
                )
                repaid = (
                    (fixed_payment - interest)
                    if method == "annuity"
                    else fixed_principal
                )
                repaid = balance if index == months - 1 else min(repaid, balance)
                payment = repaid + interest
                if index == 0:
                    first_payment = payment
                last_payment = payment
                total_interest += interest
                balance -= repaid
        return _result(
            "CALCULATED",
            "按所选方式及公布利率保持不变估算，每期利息按分四舍五入、末期清偿余本；银行逐期舍入与后续调息可能不同，以合同为准，非贷款资格认定",
            first_payment,
            last_payment=float(last_payment),
            total_interest=float(total_interest),
            total_payment=float(principal + total_interest),
            annual_rate_percent=float(rate),
            repayment_mode=method,
            months=months,
            amount_type="first_monthly_repayment",
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_interest_subsidy_2026(inputs: dict) -> dict:
    """Subsidize eligible settled interest, respecting the settlement year's remaining cap."""
    try:
        claim = _claim(inputs)
        verified = _flag(inputs, "eligibility_confirmed")
        interest = _number(inputs, "settled_interest_this_event")
        prior = _number(inputs, "subsidy_paid_this_settlement_year")
        if claim.year != 2026:
            return _result("NOT_IN_PERIOD", "此版本核验2026年适用口径，其他年份另核")
        if not verified:
            return _result(
                "MANUAL_REVIEW",
                "须核实为个人补充公积金或灵活就业按月缴存资金的真实结息额及同结算年度已获补贴",
            )
        return _result(
            "CALCULATED",
            "本次符合条件的实际结息额×50%，受同一公积金结算年度剩余5000元额度约束；非直接按本金计补贴",
            min(interest / 2, max(_ZERO, Decimal(5000) - prior)),
            remaining_year_cap=float(max(_ZERO, Decimal(5000) - prior)),
            amount_type="provident_interest_subsidy",
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_rent_2026(inputs: dict) -> dict:
    """Estimate one eligible person's remaining annual rental withdrawal."""
    try:
        claim = _claim(inputs)
        verified = _flag(inputs, "eligibility_confirmed")
        multi = _flag(inputs, "multi_child_eligible")
        available = _number(inputs, "available_withdrawable_balance")
        prior = _number(inputs, "withdrawn_this_year")
        if claim.year != 2026:
            return _result("NOT_IN_PERIOD", "本规则仅对照核验的2026租房提取口径")
        if not verified:
            return _result(
                "MANUAL_REVIEW",
                "须核实租房、职工及配偶无房范围、可提净余额和多孩资格；公租房实际租金口径另核",
            )
        cap = Decimal(18000 if multi else 15000)
        return _result(
            "CALCULATED",
            "单个缴存人每自然年限额扣除本年已提额，再受已扣应留余额的可提净余额限制；配偶须单独按个人余额计算",
            min(available, max(_ZERO, cap - prior)),
            annual_cap=float(cap),
            amount_type="rental_provident_withdrawal",
        )
    except _ERRORS as error:
        return _invalid(error)


def changzhou_provident_purchase_withdrawal_2026(inputs: dict) -> dict:
    """Limit the current claimant's home-purchase withdrawal against all owners and loan."""
    try:
        claim = _claim(inputs)
        verified = _flag(inputs, "eligibility_confirmed")
        available = _number(inputs, "available_withdrawable_balance")
        price = _number(inputs, "home_price", positive=True)
        prior = _number(inputs, "home_already_withdrawn")
        loan = _number(inputs, "planned_provident_loan")
        if not date(2026, 4, 1) <= claim <= date(2026, 12, 31):
            return _result("NOT_IN_PERIOD", "本版本核验2026-04-01起的购房提取细则")
        if not verified:
            return _result(
                "MANUAL_REVIEW",
                "须核实产权关系、提取次数、有效材料时点余额、同房所有人已提额及拟贷额；不代查产权或审批",
            )
        return _result(
            "CALCULATED",
            "同一住房所有人购房提取额加公积金贷款额不得超过房屋总价；可提净余额已扣应留款及材料时点限制",
            min(available, max(_ZERO, price - prior - loan)),
            remaining_price_limit=float(max(_ZERO, price - prior - loan)),
            amount_type="purchase_provident_withdrawal",
        )
    except _ERRORS as error:
        return _invalid(error)
