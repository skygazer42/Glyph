"""Changzhou official 2026 housing policy behavior; no Jinan standards."""

import importlib
import pytest


def calculate(name, values, **kwargs):
    return getattr(
        importlib.import_module("app.agents.dsl_generator.housing_calculations"), name
    )(values, **kwargs)


def renovation(**changes):
    return (
        dict(
            claim_time="2026-11-21",
            certificate_date="2026-05-21",
            invoice_date="2026-10-01",
            invoice_amount=120000,
            available_balance=200000,
            eligibility_confirmed=True,
            unsettled_provident_loan=False,
            prior_renovation_claims=0,
            home_withdrawn_amount=0,
            hard_decoration_invoice=True,
            nonowner_spouse_premarital_home=False,
        )
        | changes
    )


def property_fee(**changes):
    return (
        dict(
            claim_time="2026-11-21",
            eligibility_confirmed=True,
            unsettled_provident_loan=False,
            invoice_year=2026,
            invoice_amount_for_year=4000,
            available_balance=10000,
            personal_claimed_this_year=False,
            home_withdrawn_this_year=0,
        )
        | changes
    )


def purchase(**changes):
    return (
        dict(
            claim_time="2026-11-21",
            completion_date="2026-10-01",
            contract_price=2000000,
            eligibility_confirmed=True,
            household_existing_area=75,
            purchased_area=100,
            voucher_confirmed=True,
            eligible_library_confirmed=True,
            voucher_already_used=False,
            expropriation_voucher_used=False,
            guarantee_agreement_confirmed=True,
            funds_supervision_confirmed=True,
        )
        | changes
    )


def ren(**changes):
    return calculate("changzhou_renovation_2026", renovation(**changes))


def prop(**changes):
    return calculate("changzhou_property_fee_2026", property_fee(**changes))


def buy(kind="new", **changes):
    return calculate("changzhou_home_purchase_2026", purchase(**changes), kind=kind)


def test_renovation_invoice_cap_and_verified_available_balance():
    assert ren()["amount"] == 100000
    assert ren(invoice_amount=80000)["amount"] == 80000
    assert ren(available_balance=1234.56)["amount"] == 1234.56
    assert ren(home_withdrawn_amount=30000)["amount"] == 70000
    assert ren(invoice_amount=80000, home_withdrawn_amount=30000)["amount"] == 50000


@pytest.mark.parametrize(
    "certificate,claim,status",
    [
        ("2026-05-31", "2026-11-29", "INELIGIBLE"),
        ("2026-05-31", "2026-11-30", "CALCULATED"),
        ("2021-11-21", "2026-11-21", "CALCULATED"),
        ("2021-11-20", "2026-11-21", "INELIGIBLE"),
        ("2011-11-21", "2026-11-21", "CALCULATED"),
        ("2011-11-22", "2026-11-21", "INELIGIBLE"),
        ("2008-02-29", "2026-11-21", "CALCULATED"),
        ("9998-01-01", "9999-12-31", "CALCULATED"),
    ],
)
def test_real_calendar_six_month_five_year_fifteen_year_boundaries(
    certificate, claim, status
):
    assert ren(certificate_date=certificate, claim_time=claim)["status"] == status


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"claim_time": "2026-09-19", "invoice_date": "2026-09-18"}, "INELIGIBLE"),
        ({"invoice_date": "2026-09-19"}, "INELIGIBLE"),
        ({"invoice_date": "2026-09-20"}, "MANUAL_REVIEW"),
        ({"unsettled_provident_loan": True}, "INELIGIBLE"),
        ({"prior_renovation_claims": 1}, "INELIGIBLE"),
        ({"hard_decoration_invoice": False}, "INELIGIBLE"),
        ({"nonowner_spouse_premarital_home": True}, "INELIGIBLE"),
        ({"eligibility_confirmed": False}, "MANUAL_REVIEW"),
        ({"home_withdrawn_amount": 100000}, "INELIGIBLE"),
    ],
)
def test_renovation_changzhou_conditions(changes, status):
    assert ren(**changes)["status"] == status


def test_property_uses_actual_current_year_invoice_and_per_home_three_thousand_cap():
    assert prop()["amount"] == 3000
    assert prop(invoice_amount_for_year=2500)["amount"] == 2500
    assert (
        prop(invoice_amount_for_year=2500, home_withdrawn_this_year=1000)["amount"]
        == 1500
    )
    assert prop(available_balance=80.01)["amount"] == 80.01
    assert prop(claim_time="2027-01-01", invoice_year=2027)["status"] == "CALCULATED"


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"personal_claimed_this_year": True}, "INELIGIBLE"),
        ({"unsettled_provident_loan": True}, "INELIGIBLE"),
        ({"invoice_year": 2025}, "INELIGIBLE"),
        ({"home_withdrawn_this_year": 3000}, "INELIGIBLE"),
        ({"claim_time": "2026-09-19"}, "INELIGIBLE"),
        ({"eligibility_confirmed": False}, "MANUAL_REVIEW"),
    ],
)
def test_property_annual_and_loan_conditions(changes, status):
    assert prop(**changes)["status"] == status


@pytest.mark.parametrize("kind,cap", [("new", 200000), ("existing", 180000)])
def test_purchase_fifteen_percent_and_distinct_caps(kind, cap):
    assert buy(kind)["amount"] == cap
    assert buy(kind, contract_price=500000)["amount"] == 75000
    assert buy(kind, contract_price="1000000.10")["amount"] == 150000.01
    assert buy(kind)["calculation_type"] == "purchase_price_deduction"


@pytest.mark.parametrize(
    "kind,area,status",
    [
        ("new", 140, "CALCULATED"),
        ("new", 140.01, "INELIGIBLE"),
        ("existing", 75, "INELIGIBLE"),
        ("existing", 75.01, "CALCULATED"),
    ],
)
def test_housing_library_area_boundaries(kind, area, status):
    assert buy(kind, purchased_area=area)["status"] == status


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"household_existing_area": 75.01}, "INELIGIBLE"),
        ({"eligibility_confirmed": False}, "MANUAL_REVIEW"),
        ({"voucher_confirmed": False}, "MANUAL_REVIEW"),
        ({"eligible_library_confirmed": False}, "MANUAL_REVIEW"),
        ({"guarantee_agreement_confirmed": False}, "MANUAL_REVIEW"),
        ({"voucher_already_used": True}, "INELIGIBLE"),
        ({"expropriation_voucher_used": True}, "INELIGIBLE"),
        ({"completion_date": "2025-12-31"}, "INELIGIBLE"),
        ({"completion_date": "2027-01-01", "claim_time": "2027-01-02"}, "INELIGIBLE"),
        ({"completion_date": "2026-12-01"}, "INVALID_INPUT"),
    ],
)
def test_purchase_confirmed_voucher_and_2026_completion(changes, status):
    assert buy(**changes)["status"] == status


def test_existing_purchase_requires_full_funds_supervision():
    assert (
        buy("existing", funds_supervision_confirmed=False)["status"] == "MANUAL_REVIEW"
    )
    assert (
        buy("new", completion_date="2026-01-01", claim_time="2026-01-01")["status"]
        == "CALCULATED"
    )
    assert (
        buy("existing", completion_date="2026-12-31", claim_time="2026-12-31")["status"]
        == "CALCULATED"
    )


@pytest.mark.parametrize(
    "name,values,field",
    [
        ("changzhou_renovation_2026", renovation(), "invoice_amount"),
        ("changzhou_property_fee_2026", property_fee(), "invoice_amount_for_year"),
        ("changzhou_home_purchase_2026", purchase(), "contract_price"),
    ],
)
@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf"), "1e9999999"])
def test_invalid_amounts_do_not_raise_or_pay(name, values, field, value):
    result = calculate(name, values | {field: value})
    assert result["status"] == "INVALID_INPUT"
    assert result["amount"] == 0


@pytest.mark.parametrize(
    "name,values",
    [
        ("changzhou_renovation_2026", renovation()),
        ("changzhou_property_fee_2026", property_fee()),
        ("changzhou_home_purchase_2026", purchase()),
    ],
)
def test_qualification_missing_is_not_true(name, values):
    values.pop("eligibility_confirmed")
    assert calculate(name, values)["status"] == "INVALID_INPUT"


def test_invalid_dates_counts_and_flags():
    assert ren(certificate_date="2026-02-30")["status"] == "INVALID_INPUT"
    assert ren(prior_renovation_claims=True)["status"] == "INVALID_INPUT"
    assert prop(personal_claimed_this_year="false")["status"] == "INVALID_INPUT"
    assert prop(invoice_year=2026.5)["status"] == "INVALID_INPUT"
    assert buy(kind="other")["status"] == "INVALID_INPUT"
    assert ren(available_balance=0)["amount"] == 0


@pytest.mark.parametrize(
    "name,values,required_fields",
    [
        (
            "changzhou_renovation_2026",
            renovation(),
            [
                "claim_time",
                "certificate_date",
                "invoice_date",
                "invoice_amount",
                "available_balance",
                "eligibility_confirmed",
                "unsettled_provident_loan",
                "prior_renovation_claims",
                "home_withdrawn_amount",
                "hard_decoration_invoice",
                "nonowner_spouse_premarital_home",
            ],
        ),
        (
            "changzhou_property_fee_2026",
            property_fee(),
            [
                "claim_time",
                "eligibility_confirmed",
                "unsettled_provident_loan",
                "invoice_year",
                "invoice_amount_for_year",
                "available_balance",
                "personal_claimed_this_year",
                "home_withdrawn_this_year",
            ],
        ),
        (
            "changzhou_home_purchase_2026",
            purchase(),
            [
                "claim_time",
                "completion_date",
                "contract_price",
                "eligibility_confirmed",
                "household_existing_area",
                "purchased_area",
                "voucher_confirmed",
                "eligible_library_confirmed",
                "voucher_already_used",
                "expropriation_voucher_used",
                "guarantee_agreement_confirmed",
            ],
        ),
    ],
)
def test_required_policy_facts_are_never_implicitly_true(name, values, required_fields):
    for field in required_fields:
        incomplete = values.copy()
        incomplete.pop(field)
        result = calculate(name, incomplete)
        assert result["status"] == "INVALID_INPUT", field
        assert result["amount"] == 0


def test_source_catalog_faq_and_yaml_examples_are_traceable():
    import hashlib
    import json
    from pathlib import Path
    import yaml

    root = Path(__file__).resolve().parents[1]
    catalog = json.loads(
        (
            root / "resources/data/policy_catalog/changzhou_housing_20261121.json"
        ).read_text(encoding="utf8")
    )
    assert len(catalog) == 10
    sources = {row["markdown_path"]: row for row in catalog}
    for row in catalog:
        path = root / row["markdown_path"]
        text = path.read_text(encoding="utf8")
        assert text.startswith("# " + row["title"] + "\n")
        body = text.split("## 正文", 1)[1].strip() + "\n"
        assert hashlib.sha256(body.encode()).hexdigest() == row["body_sha256"]
        assert (root / row["raw_path"]).is_file()
        assert row["region"] == "江苏省常州市"
    faqs = json.loads(
        (root / "resources/faq/changzhou_housing_20261121.json").read_text(
            encoding="utf8"
        )
    )
    assert len(faqs) >= 20
    for faq in faqs:
        source = sources[faq["source_markdown_path"]]
        assert (
            faq["source_quote"]
            in (root / source["markdown_path"])
            .read_text(encoding="utf8")
            .split("## 正文")[1]
        )
        assert faq["source_body_sha256"] == source["body_sha256"]
        assert faq["source"] == source["url"]
        assert faq["source"] in faq["answer"]
    rules = json.loads(
        (root / "resources/data/policy_catalog/rules_2026_housing.json").read_text(
            encoding="utf8"
        )
    )
    assert len(rules) == 4
    for row in rules:
        assert row["rule_id"].startswith("Rule_Changzhou_")
        rule = yaml.safe_load((root / row["rule_path"]).read_text(encoding="utf8"))
        source = sources[rule["policy_source"]["source_path"]]
        assert source["body_sha256"] == rule["policy_source"]["body_sha256"]
        for spec in rule["inputs"]:
            assert spec["label"] and spec["description"]
            assert spec["type"] in {"string", "int", "float", "bool"}
            assert not (spec["type"] == "bool" and spec.get("default") is True)
            for option in spec.get("options", []):
                assert set(option) == {"label", "value"}
        kwargs = {}
        if "NewHome" in row["rule_id"]:
            kwargs["kind"] = "new"
        if "ExistingHome" in row["rule_id"]:
            kwargs["kind"] = "existing"
        result = calculate(row["helper"], row["example_inputs"], **kwargs)
        assert result["status"] == "CALCULATED"
        assert result["amount"] == row["expected_amount"]


def test_removed_legacy_local_functions_are_not_available():
    module = importlib.import_module("app.agents.dsl_generator.housing_calculations")
    assert not any(name.startswith("jinan_") for name in vars(module))
