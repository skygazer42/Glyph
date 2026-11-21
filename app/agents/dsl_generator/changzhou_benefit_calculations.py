"""Source-backed Changzhou benefit estimates; never administrative approvals."""

from datetime import date
import re
from typing import Any


def _date(facts: dict[str, Any], key: str) -> date:
    value = facts[key]
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{key}须为YYYY-MM-DD")
    return date.fromisoformat(value)


def _bool(facts: dict[str, Any], key: str) -> bool:
    value = facts[key]
    if type(value) is not bool:
        raise ValueError(f"{key}须明确填写是或否")
    return value


def _year(facts: dict[str, Any], key: str) -> int:
    value = facts[key]
    if type(value) is not int:
        raise ValueError(f"{key}须为整数年份")
    return value


def _result(status: str, reason: str, amount: int = 0) -> dict[str, Any]:
    return dict(
        status=status,
        amount=float(amount),
        reason=reason,
        calculation_type="benefit_estimate",
    )


def _child_facts(inputs: dict[str, Any]) -> tuple[date, date, bool, bool]:
    claim = _date(inputs, "claim_time")
    birth = _date(inputs, "birth_date")
    eligible = all(
        [
            _bool(inputs, "eligibility_confirmed"),
            _bool(inputs, "changzhou_household_confirmed"),
            _bool(inputs, "chinese_nationality_confirmed"),
        ]
    )
    received = _bool(inputs, "already_received")
    if birth > claim:
        raise ValueError("出生日期不能晚于申请日期")
    return claim, birth, eligible, received


def changzhou_childcare_annual_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """One 2026 annual installment for children born from 2025, not monthly cash."""
    try:
        claim, birth, eligible, received = _child_facts(inputs)
        first = _year(inputs, "first_application_year")
        if claim.year != 2026:
            return _result("NOT_IN_PERIOD", "本规则仅计算2026申领年度")
        if birth.year < 2025:
            return _result("NOT_APPLICABLE", "2025年前出生须按过渡期规则折月")
        if (
            first not in (birth.year, birth.year + 1)
            or not first <= claim.year <= first + 2
        ):
            return _result(
                "NOT_ELIGIBLE", "首次申请须出生当年或次年，后续连续两个年度续领"
            )
        if not eligible:
            return _result(
                "MANUAL_REVIEW", "须核实国籍、常州户籍及合法生育/收养、监护和申领资格"
            )
        if received:
            return _result("NOT_ELIGIBLE", "本年度本次补贴已领取，不重复计算")
        return _result(
            "CALCULATED",
            "2025年起出生婴幼儿本次年度标准3600元；不按出生月折减，不代表到账或审批",
            3600,
        )
    except (KeyError, ValueError, TypeError) as error:
        return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")


def changzhou_childcare_transition_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """2026 entitlement in the national 2022–2024 birth-month table."""
    try:
        claim, birth, eligible, received = _child_facts(inputs)
        entitlement = _bool(inputs, "annual_entitlement_confirmed")
        if claim.year != 2026:
            return _result("NOT_IN_PERIOD", "本规则仅计算归属2026年度的补贴")
        if birth.year not in (2023, 2024):
            return _result(
                "NOT_APPLICABLE",
                "2026年度表仅2023/2024年出生有额度；2022年历史首次补领需另行核实，不在此计算",
            )
        if not eligible or not entitlement:
            return _result(
                "MANUAL_REVIEW",
                "须核实2026年度申领/续领资格；延长首次申请不等于自动补发全部历史年度",
            )
        if received:
            return _result("NOT_ELIGIBLE", "归属2026年度补贴已领取，不重复享受")
        months = birth.month if birth.year == 2023 else 12
        return _result(
            "CALCULATED",
            f"国家对照表：2026归属年度{months}个月×300元；按年发放，包含满3周岁的生日月份",
            months * 300,
        )
    except (KeyError, ValueError, TypeError) as error:
        return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")


def changzhou_employment_jobsearch_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """2027 graduating class, with the two officially announced application windows."""
    try:
        claim = _date(inputs, "claim_time")
        graduation = _year(inputs, "graduation_year")
        eligible = all(
            [
                _bool(inputs, "eligibility_confirmed"),
                _bool(inputs, "jiangsu_school_confirmed"),
                _bool(inputs, "fulltime_nondirected_confirmed"),
                _bool(inputs, "jobseeking_confirmed"),
                _bool(inputs, "financial_card_confirmed"),
            ]
        )
        received = _bool(inputs, "already_received")
        category = inputs["hardship_category"]
        categories = (
            "minimum_living",
            "zero_employment",
            "orphan",
            "disabled",
            "national_student_loan",
            "extreme_poverty",
        )
        if not (
            date(2026, 9, 1) <= claim <= date(2026, 9, 30)
            or date(2027, 5, 1) <= claim <= date(2027, 5, 31)
        ):
            return _result(
                "NOT_IN_PERIOD", "申报仅2026年9月或2027年5月，当前日期不在窗口内"
            )
        if graduation != 2027 or received or category not in categories:
            return _result(
                "NOT_ELIGIBLE", "仅2027届六类困难毕业生，一人一次，多重身份不叠加"
            )
        if not eligible:
            return _result(
                "MANUAL_REVIEW",
                "须核实江苏院校、全日制非定向、毕业学年求职意愿、困难资格及金融社保卡",
            )
        return _result(
            "CALCULATED",
            "符合条件的2027届毕业生一次性1500元，不限户籍，不是只要常州户籍即可申请",
            1500,
        )
    except (KeyError, ValueError, TypeError) as error:
        return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")


def changzhou_talent_support_2026(inputs: dict[str, Any]) -> dict[str, Any]:
    """Expose policy maxima without inventing degree bands or an award formula."""
    try:
        claim = _date(inputs, "claim_time")
        kind = inputs["support_kind"]
        caps = {"living_rent": 1600, "housing_voucher": 300000}
        if kind not in caps:
            raise ValueError("支持类型须为living_rent或housing_voucher")
        if not date(2026, 10, 1) <= claim <= date(2030, 12, 31):
            return _result("NOT_IN_PERIOD", "本措施有效期2026-10-01至2030-12-31")
        result = _result(
            "MANUAL_REVIEW",
            "正式措施仅公布最高标准；2026升级调整范围及周期，缺少现行档位细则，不能把最高额或旧政策当应得金额",
        )
        result["maximum_reference"] = caps[kind]
        result["maximum_unit"] = (
            "元/月（生活和租房合计）" if kind == "living_rent" else "元（人才专属房票）"
        )
        return result
    except (KeyError, ValueError, TypeError) as error:
        return _result("INVALID_INPUT", f"输入缺失或格式不合法：{error}")
