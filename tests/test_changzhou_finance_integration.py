"""Real engine, preview, provenance and offline planner contracts for new finance rules."""

import asyncio
from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import yaml

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.api.endpoints.rule_preview import router
from app.models.policy import FinalAnswer
from test_python_guidelines_knowledge_pipeline import load_subject_definitions


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_IDS = {
    "Rule_National_Appliance_2026",
    "Rule_National_Digital_2026",
    "Rule_National_AutoScrap_2026",
    "Rule_National_AutoReplace_2026",
    "Rule_Changzhou_Renovation_2026",
    "Rule_Changzhou_NewHome_2026",
    "Rule_Changzhou_PropertyFee_2026",
    "Rule_Changzhou_ExistingHome_2026",
}
RULE_PATHS = sorted(
    path
    for path in (ROOT / "rules").glob("Rule_Changzhou_*_2026.yaml")
    if path.stem not in ORIGINAL_IDS
)
STATES = {"CALCULATED", "INELIGIBLE", "MANUAL_REVIEW", "INVALID_INPUT"}


@pytest.fixture(scope="module")
def engine():
    return PolicyEngine(str(ROOT / "rules"))


@pytest.fixture(scope="module")
def preview_client():
    application = FastAPI()
    application.include_router(router, prefix="/api/dsl")
    with TestClient(application) as client:
        yield client


def read_rule(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def preview(client, rule, inputs):
    response = client.post(
        "/api/dsl/preview",
        json={
            "yaml_content": yaml.safe_dump(rule, allow_unicode=True),
            "inputs": inputs,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def agent_class():
    return load_subject_definitions(
        "app/agents/pipeline/rule_agent.py",
        "RuleEngineAgent",
        FinalAnswer=FinalAnswer,
        uuid4=uuid4,
    )["RuleEngineAgent"]


def test_all_initial_eight_finance_contracts_are_discovered():
    expected = {
        "AutoScrap",
        "AutoReplace",
        "VehiclePurchaseTax",
        "ElectricBicycle",
        "ChildcareAnnual",
        "ChildcareTransition",
        "EmploymentJobsearch",
        "TalentSupport",
    }
    assert {f"Rule_Changzhou_{suffix}_2026" for suffix in expected} <= {
        path.stem for path in RULE_PATHS
    }


@pytest.mark.parametrize("path", RULE_PATHS, ids=lambda path: path.stem)
def test_saved_execution_and_http_draft_match_example(engine, preview_client, path):
    rule = read_rule(path)
    expected = rule["example_expected"]
    assert expected["status"] in STATES
    original_registry = deepcopy(engine.rules)
    originals = {
        p: p.read_bytes()
        for p in (ROOT / "rules").glob("*.yaml")
        if p.stem in ORIGINAL_IDS or p == path
    }
    saved = engine.execute(rule["rule_id"], deepcopy(rule["example_inputs"]))
    draft = preview(preview_client, rule, deepcopy(rule["example_inputs"]))
    assert saved["status"] == expected["status"], saved
    assert Decimal(str(saved["final_result"])) == Decimal(str(expected["amount"]))
    assert draft == saved
    assert saved["policy_source"] == rule["policy_source"]
    assert saved["explainability_trace"]
    if expected["status"] != "CALCULATED":
        assert Decimal(str(saved["final_result"])) == 0
    assert engine.rules == original_registry
    assert all(p.read_bytes() == content for p, content in originals.items())


@pytest.mark.parametrize("path", RULE_PATHS, ids=lambda path: path.stem)
def test_chinese_form_and_official_source_contract(path):
    rule = read_rule(path)
    assert rule["rule_id"] == path.stem
    assert re.search("[\u4e00-\u9fff]", rule["name"])
    assert rule["valid_period"]["start"] and rule["valid_period"]["end"]
    for field in rule["inputs"]:
        assert re.search("[\u4e00-\u9fff]", field["label"]), field
        assert re.search("[\u4e00-\u9fff]", field["description"]), field
        assert field.get("default") is not True, field
        for option in field.get("options", []):
            assert re.search("[\u4e00-\u9fff]", option["label"]), option
            assert "value" in option
    source = rule["policy_source"]
    assert re.match(r"https://[^/]+\.(?:gov|chinatax)\.cn/", source["url"])
    assert source["published_date"] is None or source["published_date"] <= "2026-11-21"
    assert (ROOT / source["raw_path"]).is_file()
    body = (ROOT / source["source_path"]).read_text(encoding="utf-8").split(
        "## 正文", 1
    )[1].strip() + "\n"
    assert hashlib.sha256(body.encode()).hexdigest() == source["body_sha256"]


@pytest.mark.parametrize("path", RULE_PATHS, ids=lambda path: path.stem)
def test_missing_fact_is_invalid_through_both_api_paths(engine, preview_client, path):
    rule = read_rule(path)
    inputs = deepcopy(rule["example_inputs"])
    field = next(spec["name"] for spec in rule["inputs"] if spec.get("required", True))
    inputs.pop(field, None)
    saved = engine.execute(rule["rule_id"], inputs)
    assert saved["status"] == "INVALID_INPUT", saved
    assert preview(preview_client, rule, inputs) == saved


@pytest.mark.parametrize("path", RULE_PATHS, ids=lambda path: path.stem)
def test_new_rules_reach_bounded_dialogue_candidates_without_llm(engine, path):
    cls = agent_class()
    agent = object.__new__(cls)
    agent.engine = engine
    agent.max_rules = 5
    rule = read_rule(path)
    planned = []

    async def plan(query, contexts):
        planned.extend(contexts)
        return SimpleNamespace(
            rule_id=None, inputs={}, reasoning="仅检验候选，不调用模型"
        )

    agent._plan_execution = plan
    asyncio.run(agent.compute("请帮我测算" + rule["keywords"][0] + "能有多少元"))
    assert len(planned) <= 5
    assert rule["rule_id"] in {context["rule_id"] for context in planned}


@pytest.mark.parametrize("status", sorted(STATES))
def test_dialogue_distinguishes_zero_pending_from_calculated_amount(status):
    text = agent_class()._format_result(
        {
            "status": status,
            "final_result": "0.0",
            "policy_source": {"title": "金融规则接入合同"},
        },
        {},
    )
    assert "判断您符合补贴条件" not in text
    if status == "MANUAL_REVIEW":
        assert "核验" in text or "人工" in text
        assert not re.search(r"结论[：:].*计算得到.*0(?:\.0)?", text)


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"nev_in_current_catalog": False}, "INELIGIBLE"),
        ({"price_ex_vat": 0}, "INVALID_INPUT"),
        ({"tax_exemption_mark_verified": False}, "MANUAL_REVIEW"),
    ],
)
def test_vehicle_noncalculated_statuses_survive_real_engine_and_preview(
    engine, preview_client, changes, status
):
    rule = read_rule(ROOT / "rules/Rule_Changzhou_VehiclePurchaseTax_2026.yaml")
    inputs = rule["example_inputs"] | changes
    saved = engine.execute(rule["rule_id"], inputs)
    assert saved["status"] == status, saved
    assert Decimal(str(saved["final_result"])) == 0
    assert preview(preview_client, rule, inputs) == saved


@pytest.mark.parametrize("suffix", ["ElectricBicycle", "TalentSupport"])
def test_real_manual_review_dialogue_never_confirms_cash_or_eligibility(engine, suffix):
    rule = read_rule(ROOT / f"rules/Rule_Changzhou_{suffix}_2026.yaml")
    cls = agent_class()
    agent = object.__new__(cls)
    agent.engine = engine
    agent.max_rules = 5

    async def plan(query, contexts):
        return SimpleNamespace(
            rule_id=rule["rule_id"], inputs=deepcopy(rule["example_inputs"])
        )

    agent._plan_execution = plan
    result = asyncio.run(agent.compute(rule["keywords"][0] + "可以领多少元"))
    assert result.metadata["engine_result"]["status"] == "MANUAL_REVIEW"
    assert result.verification_passed is False
    assert "判断您符合补贴条件" not in result.answer
    assert not re.search(r"结论[：:].*计算得到.*0(?:\.0)?", result.answer)
