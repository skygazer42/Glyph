"""Independent policy-edge checks; no reuse of the implementation's formula helpers."""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
from pathlib import Path

import pytest
import yaml

from app.agents.dsl_generator import provident_fund_calculations as subject


ROOT = Path(__file__).resolve().parents[1]


def loan(**changes):
    spec = yaml.safe_load(
        (ROOT / "rules/Rule_Changzhou_ProvidentLoan_2026.yaml").read_text(
            encoding="utf-8"
        )
    )
    return (
        spec["example_inputs"]
        | {
            "first_loan_average_balance": 100000,
            "supplementary_balance": 0,
            "home_price": 10000000,
            "income_monthly": 100000,
        }
        | changes
    )


@pytest.mark.parametrize(
    "support,expected",
    [
        ("none", 800000),
        ("two_children", 1100000),
        ("three_children", 1300000),
        ("local_graduate", 1000000),
        ("veteran", 1000000),
        ("military_spouse", 1200000),
        ("master_under35", 1500000),
        ("doctor_or_recognized_talent", 1800000),
    ],
)
def test_2025_support_supersedes_2023_directory_relisted_amounts(support, expected):
    result = subject.changzhou_provident_loan_2026(loan(support_type=support))
    assert result["amount"] == expected


@pytest.mark.parametrize(
    "support,expected",
    [
        ("none", 2000000),
        ("three_children", 2500000),
        ("doctor_or_recognized_talent", 2600000),
    ],
)
def test_two_borrowers_and_building_support_can_stack_but_identity_cannot(
    support, expected
):
    result = subject.changzhou_provident_loan_2026(
        loan(
            support_type=support,
            qualified_borrowers=2,
            high_quality_home=True,
            green_home=True,
        )
    )
    assert result["amount"] == expected
    invalid = subject.changzhou_provident_loan_2026(
        loan(support_type="three_children+master_under35")
    )
    assert invalid["status"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "day,status", [("2026-07-31", "INELIGIBLE"), ("2026-08-01", "CALCULATED")]
)
def test_green_support_starts_august_first(day, status):
    assert (
        subject.changzhou_provident_loan_2026(loan(claim_time=day, green_home=True))[
            "status"
        ]
        == status
    )


@pytest.mark.parametrize("method", ["annuity", "equal_principal"])
def test_independent_income_ceiling_uses_half_income_and_selected_first_payment(method):
    result = subject.changzhou_provident_loan_2026(
        loan(income_monthly=3000, repayment_method=method)
    )
    with localcontext() as ctx:
        ctx.prec = 40
        monthly = Decimal("0.026") / 12
        months = 240
        if method == "annuity":
            factor = monthly / (1 - (1 + monthly) ** (-months))
        else:
            factor = Decimal(1) / months + monthly
        expected = (Decimal(1500) / factor).quantize(
            Decimal(".01"), rounding=ROUND_DOWN
        )
    assert result["amount"] == float(expected)
    assert result["estimated_first_payment"] <= 1500


def test_all_price_constraints_apply_after_talent_override():
    result = subject.changzhou_provident_loan_2026(
        loan(
            support_type="doctor_or_recognized_talent",
            home_price=1000000,
            purchase_withdrawn=300000,
            housing_aid_voucher=True,
        )
    )
    assert result["amount"] == 700000
    assert result["minimum_downpayment"] == 150000


@pytest.mark.parametrize(
    "changes",
    [
        {"borrower_age": 49, "term_years": 20},
        {"home_type": "existing", "remaining_land_years": 19, "term_years": 20},
        {"home_type": "existing", "green_home": True},
        {"home_type": "existing", "high_quality_home": True},
    ],
)
def test_age_land_and_new_building_limits(changes):
    assert (
        subject.changzhou_provident_loan_2026(loan(**changes))["status"] == "INELIGIBLE"
    )


@pytest.mark.parametrize(
    "years,rate,payment",
    [
        (1, 2.1, 10210),
        (2, 2.1, 425.84),
        (5, 2.1, 175.72),
        (6, 2.6, 150.15),
        (20, 2.6, 53.48),
        (30, 2.6, 40.03),
    ],
)
def test_independent_first_tier_matches_official_per_ten_thousand_table(
    years, rate, payment
):
    result = subject.changzhou_provident_repayment_2026(
        {
            "claim_time": "2026-11-21",
            "principal": 10000,
            "term_years": years,
            "rate_class": "first",
        }
    )
    assert result["annual_rate_percent"] == rate
    assert result["amount"] == payment


@pytest.mark.parametrize(
    "years,rate,payment",
    [(1, 2.525, 10252.5), (5, 2.525, 177.58), (6, 3.075, 152.27), (30, 3.075, 42.57)],
)
def test_second_tier_matches_official_table(years, rate, payment):
    result = subject.changzhou_provident_repayment_2026(
        {
            "claim_time": "2026-11-21",
            "principal": 10000,
            "term_years": years,
            "rate_class": "second",
        }
    )
    assert result["annual_rate_percent"] == rate
    assert result["amount"] == payment


def test_equal_principal_total_interest_independent_closed_form():
    principal = Decimal(120000)
    months = 120
    expected = (principal * Decimal(".026") / 12 * (months + 1) / 2).quantize(
        Decimal(".01"), rounding=ROUND_HALF_UP
    )
    result = subject.changzhou_provident_repayment_2026(
        {
            "claim_time": "2026-11-21",
            "principal": 120000,
            "term_years": 10,
            "rate_class": "first",
        },
        "equal_principal",
    )
    assert result["total_interest"] == float(expected)
    assert result["amount"] == 1260
    assert result["last_payment"] == 1002.17


def test_contribution_rounds_each_party_up_before_summing():
    result = subject.changzhou_provident_contribution_2026(
        {
            "claim_time": "2026-07-01",
            "monthly_salary": 34081,
            "rate_percent": 12,
            "standard_employee_confirmed": True,
        }
    )
    assert result["assessed_base"] == 34080
    assert result["employee_monthly"] == 4090
    assert result["amount"] == 8180


def test_interest_cap_is_settlement_year_remaining_not_principal_times_rate():
    result = subject.changzhou_provident_interest_subsidy_2026(
        {
            "claim_time": "2026-11-21",
            "eligibility_confirmed": True,
            "settled_interest_this_event": 10000,
            "subsidy_paid_this_settlement_year": 4900,
        }
    )
    assert result["amount"] == 100


def test_purchase_withdrawal_aggregates_prior_all_owner_amounts_and_planned_loan():
    result = subject.changzhou_provident_purchase_withdrawal_2026(
        {
            "claim_time": "2026-11-21",
            "eligibility_confirmed": True,
            "available_withdrawable_balance": 200000,
            "home_price": 1000000,
            "home_already_withdrawn": 200000,
            "planned_provident_loan": 750000,
        }
    )
    assert result["amount"] == 50000


def test_rent_is_single_person_annual_remaining_not_family_double_cap():
    result = subject.changzhou_provident_rent_2026(
        {
            "claim_time": "2026-11-21",
            "eligibility_confirmed": True,
            "multi_child_eligible": True,
            "available_withdrawable_balance": 100000,
            "withdrawn_this_year": 17000,
        }
    )
    assert result["amount"] == 1000
