"""Independent amount boundaries checked against official 2026 published terms."""

from pathlib import Path

import pytest
import yaml

from app.agents.dsl_generator import changzhou_benefit_calculations as benefit
from app.agents.dsl_generator import changzhou_vehicle_calculations as vehicle
from app.agents.dsl_generator import trade_in_calculations as national


ROOT = Path(__file__).resolve().parents[1]


def facts(rule: str) -> dict:
    """Use complete declared facts; monetary expectations below are independent."""
    return yaml.safe_load(
        (ROOT / "rules" / f"Rule_{rule}_2026.yaml").read_text(encoding="utf-8")
    )["example_inputs"]


@pytest.mark.parametrize(
    "mode,fuel,price,expected",
    [
        ("scrap", "nev", 100000.01, 12001),
        ("scrap", "nev", 200000, 20000),
        ("scrap", "fuel", 100000.01, 10001),
        ("scrap", "fuel", 200000, 15000),
        ("replace", "nev", 100000.01, 8001),
        ("replace", "nev", 200000, 15000),
        ("replace", "fuel", 100000.01, 6001),
        ("replace", "fuel", 300000, 13000),
    ],
)
def test_car_rates_caps_and_yuan_ceiling(mode, fuel, price, expected):
    suffix = "AutoScrap" if mode == "scrap" else "AutoReplace"
    inputs = facts(f"Changzhou_{suffix}") | {
        "price": price,
        "new_fuel": fuel,
        "displacement_liters": 2,
    }
    if mode == "scrap":
        inputs.update(old_fuel="gasoline", old_registration_date="2013-06-30")
    assert vehicle.changzhou_auto_trade_in_2026(inputs, mode)["amount"] == expected
    assert national.auto_trade_in_2026(inputs, mode)["amount"] == expected


@pytest.mark.parametrize("mode", ["scrap", "replace"])
@pytest.mark.parametrize(
    "patch",
    [
        {"prior_auto_claims": 1},
        {"same_owner": False},
        {"old_owned_since": "2025-01-09"},
        {"quota_status": "unknown"},
        {"local_new_car_subsidy_claimed": True},
        {"invoice_city": "苏州市"},
        {"registration_province": "浙江省"},
    ],
)
def test_local_cars_never_award_duplicate_or_unknown_facts(mode, patch):
    suffix = "AutoScrap" if mode == "scrap" else "AutoReplace"
    result = vehicle.changzhou_auto_trade_in_2026(
        facts(f"Changzhou_{suffix}") | patch, mode
    )
    assert result["status"] != "CALCULATED"
    assert result["amount"] == 0


@pytest.mark.parametrize("price,expected", [(10000, 1500), (20000, 1500)])
def test_appliance_fifteen_percent_with_single_item_cap(price, expected):
    assert (
        national.appliance_subsidy_2026(facts("National_Appliance") | {"price": price})[
            "amount"
        ]
        == expected
    )


@pytest.mark.parametrize("price,expected", [(1000, 150), (6000, 500), (6000.01, 0)])
def test_digital_final_price_limit_and_cap(price, expected):
    assert (
        national.digital_subsidy_2026(facts("National_Digital") | {"price": price})[
            "amount"
        ]
        == expected
    )


@pytest.mark.parametrize(
    "name,function",
    [
        ("Appliance", national.appliance_subsidy_2026),
        ("Digital", national.digital_subsidy_2026),
    ],
)
@pytest.mark.parametrize(
    "patch",
    [
        {"prior_category_claims": 1},
        {"participating_merchant": False},
        {"identity_consistent": False},
        {"purchase_date": "2025-12-31"},
    ],
)
def test_products_reject_wrong_year_repeated_category_and_identity(
    name, function, patch
):
    assert function(facts(f"National_{name}") | patch)["amount"] == 0


@pytest.mark.parametrize(
    "price,payable,reduction",
    [
        (299999, 14999.95, 14999.95),
        (300000, 15000, 15000),
        (300001, 15000.1, 15000),
        (500000, 35000, 15000),
    ],
)
def test_tax_cap_is_reduction_cap_not_payable_cap(price, payable, reduction):
    result = vehicle.changzhou_nev_purchase_tax_2026(
        facts("Changzhou_VehiclePurchaseTax") | {"price_ex_vat": price}
    )
    assert result["amount_kind"] == "tax_payable"
    assert result["amount"] == payable
    assert result["tax_reduction"] == reduction


@pytest.mark.parametrize("month", range(1, 13))
def test_2023_birth_month_table_includes_birthday_month(month):
    inputs = facts("Changzhou_ChildcareTransition") | {
        "birth_date": f"2023-{month:02d}-01"
    }
    assert benefit.changzhou_childcare_transition_2026(inputs)["amount"] == month * 300


def test_late_2026_birth_gets_annual_installment_not_remaining_months():
    inputs = facts("Changzhou_ChildcareAnnual") | {
        "claim_time": "2026-12-31",
        "birth_date": "2026-12-31",
    }
    assert benefit.changzhou_childcare_annual_2026(inputs)["amount"] == 3600


@pytest.mark.parametrize(
    "day,expected",
    [
        ("2026-08-31", 0),
        ("2026-09-01", 1500),
        ("2026-09-30", 1500),
        ("2026-10-01", 0),
        ("2027-04-30", 0),
        ("2027-05-01", 1500),
        ("2027-05-31", 1500),
        ("2027-06-01", 0),
    ],
)
def test_jobsearch_announced_windows(day, expected):
    assert (
        benefit.changzhou_employment_jobsearch_2026(
            facts("Changzhou_EmploymentJobsearch") | {"claim_time": day}
        )["amount"]
        == expected
    )


def test_unpublished_talent_and_bicycle_amounts_remain_unawarded():
    talent = benefit.changzhou_talent_support_2026(facts("Changzhou_TalentSupport"))
    bicycle = vehicle.changzhou_electric_bicycle_2026(
        facts("Changzhou_ElectricBicycle")
    )
    assert talent["status"] == bicycle["status"] == "MANUAL_REVIEW"
    assert talent["amount"] == bicycle["amount"] == 0
    assert talent["maximum_reference"] == 300000


@pytest.mark.parametrize(
    "name,function",
    [
        ("Changzhou_ChildcareAnnual", benefit.changzhou_childcare_annual_2026),
        ("Changzhou_ChildcareTransition", benefit.changzhou_childcare_transition_2026),
        ("Changzhou_EmploymentJobsearch", benefit.changzhou_employment_jobsearch_2026),
        ("Changzhou_VehiclePurchaseTax", vehicle.changzhou_nev_purchase_tax_2026),
        ("National_Appliance", national.appliance_subsidy_2026),
        ("National_Digital", national.digital_subsidy_2026),
    ],
)
def test_every_declared_example_fact_is_required_without_eligibility_defaults(
    name, function
):
    complete = facts(name)
    for field in complete:
        incomplete = {key: value for key, value in complete.items() if key != field}
        assert function(incomplete)["status"] == "INVALID_INPUT", field
