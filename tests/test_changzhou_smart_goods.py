"""Official local smart-goods terms without national-category inference."""

from pathlib import Path

import pytest
import yaml

from app.agents.dsl_generator.trade_in_calculations import changzhou_smart_goods_2026


def facts(**changes):
    return dict(
        price=3999.99,
        category="smart_door_lock",
        claim_time="2026-11-21",
        purchase_date="2026-11-20",
        product_code="1234567890123",
        individual_consumer=True,
        participating_merchant=True,
        platform_category_confirmed=True,
        current_round_product_confirmed=True,
        claims_history_confirmed=True,
        prior_category_claims=0,
        no_duplicate_subsidy_confirmed=True,
        budget_status="available",
        has_efficiency_label=False,
        **changes,
    )


@pytest.mark.parametrize(
    "price,amount", [(1, 0.15), (3999.99, 600), (10000, 1500), (20000, 1500)]
)
def test_rate_cap_and_display_rounding(price, amount):
    inputs = facts()
    inputs["price"] = price
    assert changzhou_smart_goods_2026(inputs)["amount"] == amount


@pytest.mark.parametrize(
    "day,status",
    [
        ("2026-08-28", "NOT_IN_PERIOD"),
        ("2026-08-29", "CALCULATED"),
        ("2026-12-31", "CALCULATED"),
        ("2027-01-01", "NOT_IN_PERIOD"),
    ],
)
def test_purchase_and_claim_boundaries(day, status):
    inputs = facts()
    inputs.update(claim_time=day, purchase_date=day)
    assert changzhou_smart_goods_2026(inputs)["status"] == status


@pytest.mark.parametrize(
    "category",
    [
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
    ],
)
def test_twenty_primary_product_items(category):
    inputs = facts()
    inputs["category"] = category
    assert changzhou_smart_goods_2026(inputs)["amount"] == 600


@pytest.mark.parametrize(
    "category",
    [
        "electric_bicycle",
        "refrigerator",
        "washing_machine",
        "tv",
        "air_conditioner",
        "water_heater",
        "computer",
        "drone",
        "washing_drying_set",
    ],
)
def test_excluded_and_unmapped_subproducts_are_not_inferred(category):
    inputs = facts()
    inputs["category"] = category
    assert changzhou_smart_goods_2026(inputs)["status"] == "INELIGIBLE"


@pytest.mark.parametrize(
    "field",
    [
        "individual_consumer",
        "participating_merchant",
        "platform_category_confirmed",
        "current_round_product_confirmed",
        "claims_history_confirmed",
        "no_duplicate_subsidy_confirmed",
    ],
)
def test_unconfirmed_qualification_needs_review(field):
    inputs = facts()
    inputs[field] = False
    result = changzhou_smart_goods_2026(inputs)
    assert result["status"] == "MANUAL_REVIEW"
    assert result["amount"] == 0


@pytest.mark.parametrize("budget", ["unknown", "exhausted"])
def test_no_amount_when_budget_is_unconfirmed_or_exhausted(budget):
    inputs = facts()
    inputs["budget_status"] = budget
    assert changzhou_smart_goods_2026(inputs)["status"] == "MANUAL_REVIEW"


@pytest.mark.parametrize(
    "patch,status",
    [
        (
            {
                "has_efficiency_label": True,
                "efficiency_level": 1,
                "efficiency_registered": True,
            },
            "CALCULATED",
        ),
        (
            {
                "has_efficiency_label": True,
                "efficiency_level": 2,
                "efficiency_registered": True,
            },
            "INELIGIBLE",
        ),
        (
            {
                "has_efficiency_label": True,
                "efficiency_level": 1,
                "efficiency_registered": False,
            },
            "MANUAL_REVIEW",
        ),
        ({"has_efficiency_label": True}, "INVALID_INPUT"),
        ({"has_efficiency_label": "false"}, "INVALID_INPUT"),
    ],
)
def test_efficiency_requirements_are_conditional(patch, status):
    assert changzhou_smart_goods_2026(facts() | patch)["status"] == status


@pytest.mark.parametrize(
    "patch",
    [
        {"product_code": "123"},
        {"product_code": 1234567890123},
        {"product_code": "１２３４５６７８９０１２３"},
        {"prior_category_claims": True},
        {"prior_category_claims": 0.5},
        {"price": True},
        {"price": "NaN"},
        {"purchase_date": "2026-11-22"},
    ],
)
def test_invalid_facts_do_not_become_awards(patch):
    assert changzhou_smart_goods_2026(facts() | patch)["status"] == "INVALID_INPUT"


def test_used_category_is_not_reset_or_stacked():
    assert (
        changzhou_smart_goods_2026(facts() | {"prior_category_claims": 1})["status"]
        == "INELIGIBLE"
    )


def test_every_unconditional_fact_is_required():
    complete = facts()
    for field in complete:
        inputs = {key: value for key, value in complete.items() if key != field}
        assert changzhou_smart_goods_2026(inputs)["status"] == "INVALID_INPUT", field


def test_yaml_example_and_required_facts():
    root = Path(__file__).resolve().parents[1]
    rule = yaml.safe_load(
        (root / "rules/Rule_Changzhou_SmartGoods_2026.yaml").read_text(encoding="utf-8")
    )
    result = changzhou_smart_goods_2026(rule["example_inputs"])
    assert result["status"] == rule["example_expected"]["status"]
    assert result["amount"] == rule["example_expected"]["amount"]
    assert all(
        "default" not in item and item["label"] and item["description"]
        for item in rule["inputs"]
    )
