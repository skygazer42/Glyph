"""Money and boundary contracts for source-backed Changzhou provident rules."""

import pytest

from app.agents.dsl_generator import provident_fund_calculations as c


def contribution(**changes):
    return dict(
        claim_time="2026-11-21",
        monthly_salary=8761,
        rate_percent=12,
        standard_employee_confirmed=True,
        **changes,
    )


def loan(**changes):
    values = dict(
        claim_time="2026-11-21",
        eligibility_confirmed=True,
        qualified_borrowers=1,
        first_loan_average_balance=10000,
        repeat_loan_average_balance=0,
        supplementary_balance=10000,
        external_balance=0,
        family_cooperative_quota=0,
        support_type="none",
        high_quality_home=False,
        green_home=False,
        home_price=2000000,
        purchase_withdrawn=0,
        housing_aid_voucher=False,
        income_monthly=20000,
        term_years=20,
        rate_class="first",
        repayment_method="annuity",
        borrower_age=35,
        remaining_land_years=60,
        home_type="new",
    )
    values.update(changes)
    return values


def repayment(**changes):
    values = dict(
        claim_time="2026-11-21", principal=10000, term_years=20, rate_class="first"
    )
    values.update(changes)
    return values


def test_contribution_rounds_both_sides_up_to_whole_yuan():
    result = c.changzhou_provident_contribution_2026(contribution())
    assert result["amount"] == 2104
    assert result["employee_monthly"] == result["employer_monthly"] == 1052


@pytest.mark.parametrize("salary,total", [(0, 266), (100000, 8180)])
def test_contribution_clamps_the_assessment_base(salary, total):
    values = contribution()
    values.update(monthly_salary=salary, rate_percent=5 if salary == 0 else 12)
    assert c.changzhou_provident_contribution_2026(values)["amount"] == total


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1])
def test_invalid_money_never_becomes_a_payment(value):
    assert (
        c.changzhou_provident_repayment_2026(repayment(principal=value))["status"]
        == "INVALID_INPUT"
    )


@pytest.mark.parametrize("claim", ["2026-06-30", "2027-07-01"])
def test_contribution_rejects_dates_outside_the_published_settlement_year(claim):
    values = contribution()
    values["claim_time"] = claim
    assert c.changzhou_provident_contribution_2026(values)["status"] == "NOT_IN_PERIOD"


def test_ordinary_loan_combines_balance_formulas():
    result = c.changzhou_provident_loan_2026(loan())
    assert result["amount"] == 660000
    assert result["account_quota"] == 660000


def test_policy_cap_and_family_cooperation_are_separate():
    result = c.changzhou_provident_loan_2026(loan(family_cooperative_quota=1000000))
    assert result["amount"] == 800000
    assert result["policy_quota"] == 800000


def test_talent_exception_does_not_require_an_invented_balance():
    result = c.changzhou_provident_loan_2026(
        loan(
            first_loan_average_balance=0,
            supplementary_balance=0,
            support_type="doctor_or_recognized_talent",
            high_quality_home=True,
            green_home=True,
            home_price=4000000,
            income_monthly=100000,
        )
    )
    assert result["amount"] == 2600000


def test_two_children_increase_actual_quota_not_only_the_ceiling():
    assert (
        c.changzhou_provident_loan_2026(loan(support_type="two_children"))["amount"]
        == 960000
    )


def test_minimum_downpayment_and_purchase_withdrawals_limit_the_loan():
    result = c.changzhou_provident_loan_2026(
        loan(home_price=500000, purchase_withdrawn=150000)
    )
    assert result["amount"] == 350000
    assert result["minimum_downpayment"] == 100000


def test_verified_housing_aid_uses_fifteen_percent_downpayment():
    result = c.changzhou_provident_loan_2026(
        loan(home_price=500000, housing_aid_voucher=True)
    )
    assert result["amount"] == 425000
    assert result["minimum_downpayment"] == 75000


def test_income_constraint_is_met_after_rounding():
    result = c.changzhou_provident_loan_2026(loan(income_monthly=1000))
    assert result["amount"] < 100000
    assert result["estimated_first_payment"] <= 500


@pytest.mark.parametrize(
    "changes", [dict(eligibility_confirmed=False), dict(term_years=1)]
)
def test_unverified_qualification_or_one_year_affordability_requires_review(changes):
    assert c.changzhou_provident_loan_2026(loan(**changes))["status"] == "MANUAL_REVIEW"


@pytest.mark.parametrize(
    "changes",
    [
        dict(term_years=31),
        dict(borrower_age=60, term_years=9),
        dict(home_type="existing", remaining_land_years=10, term_years=11),
    ],
)
def test_loan_term_limits_are_enforced(changes):
    assert c.changzhou_provident_loan_2026(loan(**changes))["status"] == "INELIGIBLE"


def test_land_remaining_limit_does_not_extend_to_new_housing():
    assert (
        c.changzhou_provident_loan_2026(loan(remaining_land_years=0))["status"]
        == "CALCULATED"
    )


@pytest.mark.parametrize("flag", ["high_quality_home", "green_home"])
def test_new_housing_bonuses_cannot_be_applied_to_existing_housing(flag):
    assert (
        c.changzhou_provident_loan_2026(loan(home_type="existing", **{flag: True}))[
            "status"
        ]
        == "INELIGIBLE"
    )


def test_rounded_payment_never_exceeds_a_half_cent_income_budget():
    result = c.changzhou_provident_loan_2026(loan(income_monthly=1000.01))
    assert result["estimated_first_payment"] <= 500.005


def test_annuity_matches_the_current_official_reference_table():
    result = c.changzhou_provident_repayment_2026(repayment())
    assert result["amount"] == 53.48
    assert result["annual_rate_percent"] == 2.6
    assert result["total_interest"] > 0


def test_one_year_is_bullet_repayment_in_both_selected_modes():
    for method in ["annuity", "equal_principal"]:
        result = c.changzhou_provident_repayment_2026(repayment(term_years=1), method)
        assert result["repayment_mode"] == "bullet"
        assert result["amount"] == result["total_payment"] == 10210
        assert result["total_interest"] == 210


def test_equal_principal_first_and_last_payment_and_interest():
    result = c.changzhou_provident_repayment_2026(
        repayment(principal=120000, term_years=10), "equal_principal"
    )
    assert result["amount"] == 1260
    assert result["last_payment"] == 1002.17
    assert result["total_interest"] == 15730


def test_second_tier_rates_and_five_year_boundary():
    assert (
        c.changzhou_provident_repayment_2026(
            repayment(term_years=5, rate_class="second")
        )["annual_rate_percent"]
        == 2.525
    )
    assert (
        c.changzhou_provident_repayment_2026(
            repayment(term_years=6, rate_class="second")
        )["annual_rate_percent"]
        == 3.075
    )


def test_interest_subsidy_caps_the_years_remaining_budget():
    inputs = dict(
        claim_time="2026-11-21",
        eligibility_confirmed=True,
        settled_interest_this_event=500,
        subsidy_paid_this_settlement_year=4900,
    )
    assert c.changzhou_provident_interest_subsidy_2026(inputs)["amount"] == 100


def test_rent_is_an_individual_remaining_annual_cap():
    inputs = dict(
        claim_time="2026-11-21",
        eligibility_confirmed=True,
        multi_child_eligible=True,
        available_withdrawable_balance=20000,
        withdrawn_this_year=5000,
    )
    assert c.changzhou_provident_rent_2026(inputs)["amount"] == 13000


def test_purchase_withdrawal_cannot_duplicate_the_loan_or_other_owners():
    inputs = dict(
        claim_time="2026-11-21",
        eligibility_confirmed=True,
        available_withdrawable_balance=900000,
        home_price=1000000,
        home_already_withdrawn=100000,
        planned_provident_loan=700000,
    )
    assert c.changzhou_provident_purchase_withdrawal_2026(inputs)["amount"] == 200000


@pytest.mark.parametrize(
    "function",
    [
        c.changzhou_provident_contribution_2026,
        c.changzhou_provident_loan_2026,
        c.changzhou_provident_repayment_2026,
        c.changzhou_provident_interest_subsidy_2026,
        c.changzhou_provident_rent_2026,
        c.changzhou_provident_purchase_withdrawal_2026,
    ],
)
def test_missing_inputs_and_nonobject_payloads_fail_explicitly(function):
    assert function({})["status"] == "INVALID_INPUT"
    assert function(None)["status"] == "INVALID_INPUT"
