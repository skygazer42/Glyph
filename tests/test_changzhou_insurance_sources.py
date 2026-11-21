"""Supplementary insurance evidence must reach import without losing provenance."""

import json
from pathlib import Path

from scripts import import_changzhou_policies as importer
from scripts.official_policy_data import load_official_policies


ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENT = ROOT / "resources/data/policy_catalog/changzhou_insurance_supplement_20261121.json"


def test_supplementary_sources_reach_import_with_publisher_and_document_type():
    expected = json.loads(SUPPLEMENT.read_text(encoding="utf-8"))
    accepted = {item["url"]: item for item in load_official_policies(ROOT)}
    assert {item["url"] for item in expected} <= accepted.keys()
    for item in expected:
        loaded = accepted[item["url"]]
        assert loaded["issuer"] == loaded["source_publisher"]
        assert loaded["document_kind"] == item["document_kind"]
        assert loaded["body"].strip()


def test_medical_insurance_coverage_years_keep_distinct_sources_and_enrollment_dates():
    accepted = {item.get("source_id"): item for item in load_official_policies(ROOT)}
    earlier = accepted["medical_supplement_2026"]
    later = accepted["medical_supplement_2027"]
    assert earlier["coverage_year"] == 2026
    assert later["coverage_year"] == 2027
    assert earlier["url"] != later["url"]
    assert "2025年12月31日" in earlier["body"]
    assert "2027年度" in later["body"]
    assert earlier["enrollment_period_has_ended_as_of_retrieval"] is True


def test_department_news_and_individual_reply_remain_distinct_from_policy():
    accepted = {item.get("source_id"): item for item in load_official_policies(ROOT)}
    assert accepted["supplement_2027_changzhou"]["document_kind"] == "official_department_news"
    assert accepted["pension_retirement_2026"]["document_kind"] == "official_individual_consultation_reply"


def test_import_preserves_coverage_year_and_closed_enrollment_context():
    sources = {item["source_id"]: item for item in json.loads(SUPPLEMENT.read_text(encoding="utf-8"))}
    historical = importer.build_source_header(sources["medical_supplement_2026"])
    upcoming = importer.build_source_header(sources["medical_supplement_2027"])
    assert "保障年度：2026" in historical
    assert "投保期已结束" in historical
    assert "保障年度：2027" in upcoming
    assert "未给出投保截止日期" in upcoming


def test_contract_sources_keep_first_party_identity_and_verified_raw_bytes():
    sources = {item.get("source_id"): item for item in load_official_policies(ROOT)}
    item = sources["jiangsu_medical_insurance_2027_formal_documents"]
    assert item["source_type"] == "first_party_insurance_product"
    assert "商业保险" in importer.build_source_header(item)
    assert "官方公开资料快照" not in importer.build_source_header(item)
