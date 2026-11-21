"""Local execution conditions and 2026 vehicle tax boundaries."""

import importlib
from pathlib import Path

import pytest
import yaml


def calculate(name, inputs, **kwargs):
    module = importlib.import_module(
        "app.agents.dsl_generator.changzhou_vehicle_calculations"
    )
    return getattr(module, name)(inputs, **kwargs)


def car_inputs(mode="replace", **changes):
    suffix = "AutoScrap" if mode == "scrap" else "AutoReplace"
    data = yaml.safe_load(
        Path(f"rules/Rule_National_{suffix}_2026.yaml").read_text(encoding="utf-8")
    )
    inputs = data["example_inputs"] | {
        "invoice_city": "常州市",
        "registration_province": "江苏省",
        "local_new_car_subsidy_claimed": False,
        "quota_status": "available",
    }
    return inputs | changes


def tax_inputs(**changes):
    return {
        "price_ex_vat": 200000,
        "purchase_date": "2026-11-21",
        "new_passenger_car": True,
        "nev_in_current_catalog": True,
        "tax_exemption_mark_verified": True,
        "domestic_purchase_for_own_use": True,
        "battery_invoice_separate": False,
    } | changes


@pytest.mark.parametrize(
    "price,normal,saving,payable",
    [
        (100000, 10000, 5000, 5000),
        (300000, 30000, 15000, 15000),
        (500000, 50000, 15000, 35000),
        ("123456.78", 12345.68, 6172.84, 6172.84),
    ],
)
def test_tax_is_tax_payable_not_cash_subsidy(price, normal, saving, payable):
    result = calculate(
        "changzhou_nev_purchase_tax_2026", tax_inputs(price_ex_vat=price)
    )
    assert result["status"] == "CALCULATED"
    assert result["amount"] == payable
    assert result["normal_tax"] == normal
    assert result["tax_reduction"] == saving
    assert result["amount_kind"] == "tax_payable"


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"purchase_date": "2025-12-31"}, "INELIGIBLE"),
        ({"purchase_date": "2027-01-01"}, "INELIGIBLE"),
        ({"nev_in_current_catalog": False}, "INELIGIBLE"),
        ({"tax_exemption_mark_verified": False}, "MANUAL_REVIEW"),
        ({"domestic_purchase_for_own_use": False}, "MANUAL_REVIEW"),
        ({"new_passenger_car": False}, "MANUAL_REVIEW"),
        ({"price_ex_vat": True}, "INVALID_INPUT"),
        ({"price_ex_vat": "NaN"}, "INVALID_INPUT"),
        ({"price_ex_vat": 0}, "INVALID_INPUT"),
        ({"purchase_date": "2026-02-30"}, "INVALID_INPUT"),
    ],
)
def test_tax_never_assumes_missing_eligibility(changes, status):
    result = calculate("changzhou_nev_purchase_tax_2026", tax_inputs(**changes))
    assert (result["status"], result["amount"]) == (status, 0)


@pytest.mark.parametrize("field", list(tax_inputs()))
def test_tax_requires_each_fact(field):
    data = tax_inputs()
    del data[field]
    assert (
        calculate("changzhou_nev_purchase_tax_2026", data)["status"] == "INVALID_INPUT"
    )


def test_separate_battery_invoice_uses_only_explicit_vehicle_invoice_base():
    result = calculate(
        "changzhou_nev_purchase_tax_2026",
        tax_inputs(price_ex_vat=200000, battery_invoice_separate=True),
    )
    assert result["amount"] == 10000
    assert "电池" in result["reason"]


@pytest.mark.parametrize(
    "mode,price,amount",
    [
        ("scrap", 100000, 12000),
        ("scrap", 200000, 20000),
        ("replace", 100000.01, 8001),
        ("replace", 200000, 15000),
    ],
)
def test_local_trade_in_reuses_national_amount(mode, price, amount):
    result = calculate(
        "changzhou_auto_trade_in_2026", car_inputs(mode, price=price), mode=mode
    )
    assert (result["status"], result["amount"]) == ("CALCULATED", amount)
    assert "全国" in result["reason"] and "常州" in result["reason"]


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"invoice_city": "无锡市"}, "INELIGIBLE"),
        ({"registration_province": "浙江省"}, "INELIGIBLE"),
        ({"local_new_car_subsidy_claimed": True}, "MANUAL_REVIEW"),
        ({"quota_status": "unknown"}, "MANUAL_REVIEW"),
        ({"quota_status": "exhausted"}, "MANUAL_REVIEW"),
        ({"quota_status": "yes"}, "INVALID_INPUT"),
        ({"old_owned_since": "2025-01-09"}, "INELIGIBLE"),
        ({"same_owner": False}, "INELIGIBLE"),
        ({"local_new_car_subsidy_claimed": "false"}, "INVALID_INPUT"),
    ],
)
def test_local_restrictions_and_platform_review(changes, status):
    result = calculate("changzhou_auto_trade_in_2026", car_inputs(**changes))
    assert (result["status"], result["amount"]) == (status, 0)


@pytest.mark.parametrize(
    "field",
    [
        "invoice_city",
        "registration_province",
        "local_new_car_subsidy_claimed",
        "quota_status",
        "price",
        "same_province",
    ],
)
def test_local_required_fields(field):
    data = car_inputs()
    del data[field]
    assert calculate("changzhou_auto_trade_in_2026", data)["status"] == "INVALID_INPUT"


def test_local_checks_do_not_hide_invalid_national_inputs():
    assert (
        calculate(
            "changzhou_auto_trade_in_2026", car_inputs(price=-1, quota_status="unknown")
        )["status"]
        == "INVALID_INPUT"
    )


@pytest.mark.parametrize("price", [1000, 3000, 10000])
def test_no_verified_2026_ebike_amount_is_not_replaced_by_2025_rate(price):
    result = calculate(
        "changzhou_electric_bicycle_2026",
        {"price": price, "purchase_date": "2026-11-21"},
    )
    assert (result["status"], result["amount"]) == ("MANUAL_REVIEW", 0)
    assert "2025" in result["reason"] and "2026" in result["reason"]


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"price": True, "purchase_date": "2026-11-21"},
        {"price": 1000, "purchase_date": "2026-02-30"},
    ],
)
def test_ebike_invalid_inputs(inputs):
    assert (
        calculate("changzhou_electric_bicycle_2026", inputs)["status"]
        == "INVALID_INPUT"
    )


@pytest.mark.parametrize(
    "suffix", ["AutoScrap", "AutoReplace", "VehiclePurchaseTax", "ElectricBicycle"]
)
def test_yaml_examples_and_provenance(suffix):
    import hashlib

    module = importlib.import_module(
        "app.agents.dsl_generator.changzhou_vehicle_calculations"
    )
    rule = yaml.safe_load(
        Path(f"rules/Rule_Changzhou_{suffix}_2026.yaml").read_text(encoding="utf-8")
    )
    result = eval(
        rule["calc"]["result"],
        {"__builtins__": {}},
        {"dsl_helpers": module, "inputs": rule["example_inputs"]},
    )
    assert result["status"] == rule["example_expected"]["status"]
    assert result["amount"] == rule["example_expected"]["amount"]
    for field in rule["inputs"]:
        assert field.get("label") and field.get("description")
        assert not (field["type"] == "bool" and field.get("default") is True)
    source = rule["policy_source"]
    body = (
        Path(source["source_path"])
        .read_text(encoding="utf-8")
        .split("## 正文", 1)[1]
        .strip()
        + "\n"
    )
    assert hashlib.sha256(body.encode()).hexdigest() == source["body_sha256"]


def test_every_vehicle_faq_quote_is_traceable():
    import hashlib
    import json

    catalog = json.loads(
        Path(
            "resources/data/policy_catalog/changzhou_vehicle_finance_20261121.json"
        ).read_text(encoding="utf-8")
    )
    docs = {c["url"]: c for c in catalog}
    faqs = json.loads(
        Path("resources/faq/changzhou_vehicle_finance_20261121.json").read_text(
            encoding="utf-8"
        )
    )
    for faq in faqs:
        source = docs[faq["source"]]
        body = (
            Path(faq["source_markdown_path"])
            .read_text(encoding="utf-8")
            .split("## 正文", 1)[1]
            .strip()
            + "\n"
        )
        assert faq["source_quote"] in body
        assert (
            hashlib.sha256(body.encode()).hexdigest()
            == source["body_sha256"]
            == faq["source_body_sha256"]
        )
        assert Path(source["raw_path"]).is_file()
