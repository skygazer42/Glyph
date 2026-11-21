"""Source-backed benefit boundaries, including missing qualification facts."""

import pytest
import hashlib
import json
from pathlib import Path

import yaml

from app.agents.dsl_generator.changzhou_benefit_calculations import (
    changzhou_childcare_annual_2026,
    changzhou_childcare_transition_2026,
    changzhou_employment_jobsearch_2026,
    changzhou_talent_support_2026,
)


def annual():
    return dict(
        claim_time="2026-11-21",
        birth_date="2026-10-31",
        first_application_year=2026,
        eligibility_confirmed=True,
        changzhou_household_confirmed=True,
        chinese_nationality_confirmed=True,
        already_received=False,
    )


@pytest.mark.parametrize(
    "birth,first", [("2026-10-31", 2026), ("2025-12-31", 2026), ("2025-01-01", 2025)]
)
def test_newborn_annual_is_not_prorated(birth, first):
    assert (
        changzhou_childcare_annual_2026(
            {**annual(), "birth_date": birth, "first_application_year": first}
        )["amount"]
        == 3600
    )


@pytest.mark.parametrize(
    "birth,amount",
    [
        ("2023-01-01", 300),
        ("2023-06-30", 1800),
        ("2023-12-31", 3600),
        ("2024-01-01", 3600),
        ("2024-12-31", 3600),
        ("2022-12-31", 0),
    ],
)
def test_transition_calendar_month_table(birth, amount):
    facts = {**annual(), "birth_date": birth, "annual_entitlement_confirmed": True}
    assert changzhou_childcare_transition_2026(facts)["amount"] == amount


@pytest.mark.parametrize(
    "function",
    [
        changzhou_childcare_annual_2026,
        changzhou_childcare_transition_2026,
        changzhou_employment_jobsearch_2026,
    ],
)
def test_missing_facts_never_assume_eligibility(function):
    assert function({})["status"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "key",
    [
        "eligibility_confirmed",
        "changzhou_household_confirmed",
        "chinese_nationality_confirmed",
    ],
)
def test_unverified_child_eligibility(key):
    assert changzhou_childcare_annual_2026({**annual(), key: False})["amount"] == 0


@pytest.mark.parametrize(
    "patch",
    [
        {"already_received": True},
        {"birth_date": "2024-12-31"},
        {"first_application_year": 2024},
        {"birth_date": "2026-12-01"},
        {"eligibility_confirmed": "true"},
        {"claim_time": "2027-01-01"},
        {"first_application_year": True},
    ],
)
def test_annual_rejects_duplicates_invalid_dates_and_wrong_cohort(patch):
    assert changzhou_childcare_annual_2026({**annual(), **patch})["amount"] == 0


def job():
    return dict(
        claim_time="2026-09-15",
        graduation_year=2027,
        eligibility_confirmed=True,
        jiangsu_school_confirmed=True,
        fulltime_nondirected_confirmed=True,
        jobseeking_confirmed=True,
        hardship_category="national_student_loan",
        already_received=False,
        financial_card_confirmed=True,
    )


@pytest.mark.parametrize(
    "day", ["2026-09-01", "2026-09-30", "2027-05-01", "2027-05-31"]
)
def test_jobsearch_windows(day):
    assert (
        changzhou_employment_jobsearch_2026({**job(), "claim_time": day})["amount"]
        == 1500
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"claim_time": "2026-11-21"},
        {"claim_time": "2027-04-30"},
        {"graduation_year": 2026},
        {"already_received": True},
        {"hardship_category": "other"},
        {"jiangsu_school_confirmed": False},
        {"eligibility_confirmed": False},
        {"fulltime_nondirected_confirmed": False},
        {"jobseeking_confirmed": False},
        {"financial_card_confirmed": False},
    ],
)
def test_jobsearch_rejects_ineligible_and_duplicates(patch):
    assert changzhou_employment_jobsearch_2026({**job(), **patch})["amount"] == 0


@pytest.mark.parametrize(
    "kind,cap", [("living_rent", 1600), ("housing_voucher", 300000)]
)
def test_talent_maximum_never_becomes_award(kind, cap):
    result = changzhou_talent_support_2026(
        dict(claim_time="2026-11-21", support_kind=kind)
    )
    assert result["status"] == "MANUAL_REVIEW"
    assert result["amount"] == 0
    assert result["maximum_reference"] == cap


def test_catalog_and_faq_evidence_match_frozen_bodies():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads(
        (
            root
            / "resources/data/policy_catalog/changzhou_benefit_finance_20261121.json"
        ).read_text(encoding="utf-8")
    )
    sources = {item["url"]: item for item in catalog}
    for source in catalog:
        body = (root / source["markdown_path"]).read_text(encoding="utf-8").split(
            "\n## 正文\n", 1
        )[1].strip() + "\n"
        assert hashlib.sha256(body.encode()).hexdigest() == source["body_sha256"]
        assert (root / source["raw_path"]).is_file()
    faq = json.loads(
        (root / "resources/faq/changzhou_benefit_finance_20261121.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in faq:
        source = sources[entry["source"]]
        assert entry["source_body_sha256"] == source["body_sha256"]
        assert entry["source_quote"] in (root / source["markdown_path"]).read_text(
            encoding="utf-8"
        )


@pytest.mark.parametrize(
    "name,function",
    [
        ("ChildcareAnnual", changzhou_childcare_annual_2026),
        ("ChildcareTransition", changzhou_childcare_transition_2026),
        ("EmploymentJobsearch", changzhou_employment_jobsearch_2026),
        ("TalentSupport", changzhou_talent_support_2026),
    ],
)
def test_yaml_examples_and_explicit_qualification_inputs(name, function):
    root = Path(__file__).resolve().parents[1]
    rule = yaml.safe_load(
        (root / "rules" / f"Rule_Changzhou_{name}_2026.yaml").read_text(
            encoding="utf-8"
        )
    )
    result = function(rule["example_inputs"])
    assert result["amount"] == rule["example_expected"]["amount"]
    assert result["status"] == rule["example_expected"]["status"]
    assert all("default" not in item for item in rule["inputs"])
    assert all(item["label"] and item["description"] for item in rule["inputs"])
