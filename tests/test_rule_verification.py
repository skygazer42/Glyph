"""Only reviewed rule versions may supply amounts in public conversations."""

import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.models.policy import FinalAnswer
from test_python_guidelines_knowledge_pipeline import load_subject_definitions

ROOT = Path(__file__).resolve().parents[1]
MANUAL_IDS = {
    "Rule_Changzhou_TalentSupport_2026",
    "Rule_Changzhou_ElectricBicycle_2026",
}


def test_every_installed_rule_has_a_scoped_review_in_list_detail_and_result():
    engine = PolicyEngine(str(ROOT / "rules"))
    rows = engine.list_rules()
    assert len(rows) == 25
    for row in rows:
        review = row["verification"]
        expected = "manual_only" if row["rule_id"] in MANUAL_IDS else "verified_for_estimate"
        assert review["status"] == expected, (row["rule_id"], review)
        assert review["reviewed_on"] == "2026-11-21"
        assert review["checked_claims"] and review["limitations"]
        assert review["evidence_files"] and review["implementation_files"]
        rule = engine.rules[row["rule_id"]]
        assert engine.get_rule_info(row["rule_id"])["verification"] == review
        result = engine.execute(row["rule_id"], rule["example_inputs"])
        assert result["verification"] == review
        assert result["status"] == rule["example_expected"]["status"]
        assert float(result["final_result"]) == rule["example_expected"]["amount"]


def test_changed_official_rule_loses_review_but_draft_can_still_be_exercised():
    engine = PolicyEngine(str(ROOT / "rules"))
    identity = "Rule_National_Digital_2026"
    changed = deepcopy(engine.rules[identity])
    changed["output"]["final_result"] = "99999"
    changed["verification"] = {"status": "verified_for_estimate"}
    engine.rules[identity] = changed
    saved = engine.execute(identity, changed["example_inputs"])
    assert saved["status"] == "MANUAL_REVIEW"
    assert "final_result" not in saved
    assert saved["verification"]["status"] == "needs_review"
    draft = engine.execute_rule(changed, changed["example_inputs"])
    assert draft["final_result"] == "99999"
    assert draft["verification"]["status"] == "needs_review"


def test_new_draft_cannot_self_declare_an_official_review():
    draft = {
        "rule_id": "new-custom-draft",
        "verification": {"status": "verified_for_estimate"},
        "calc": {},
        "output": {"status": "CALCULATED", "final_result": "123"},
    }
    result = PolicyEngine(None).execute_rule(draft, {})
    assert result["final_result"] == "123"
    assert result["verification"]["status"] == "unverified"


@pytest.mark.parametrize("review", [None, {"status": "unverified"}, {"status": "needs_review"}])
def test_public_conversation_suppresses_unreviewed_amounts(review):
    cls = load_subject_definitions(
        "app/agents/pipeline/rule_agent.py", "RuleEngineAgent",
        FinalAnswer=FinalAnswer, uuid4=uuid4,
    )["RuleEngineAgent"]
    agent = object.__new__(cls)
    agent.max_rules = 5
    result = {"status": "QUALIFIED", "final_result": 987654}
    if review is not None:
        result["verification"] = review
    agent.engine = SimpleNamespace(
        rules={"custom": {}}, get_rule_info=lambda key: {},
        execute=lambda *args: result,
    )
    agent._collect_rules = lambda: [{"rule_id": "custom", "keywords": ["自定义规则"]}]

    async def plan(*args):
        return SimpleNamespace(rule_id="custom", inputs={})

    agent._plan_execution = plan
    answer = asyncio.run(agent.compute("自定义规则给我算钱"))
    assert answer.metadata["engine_result"]["status"] == "MANUAL_REVIEW"
    assert answer.verification_passed is False
    assert "987654" not in answer.answer
    assert "金额试算结果" not in answer.answer


@pytest.fixture
def reviewed_fixture(tmp_path):
    """A local reviewed calculator with separately stored evidence and audit ledger."""
    from app.agents.dsl_generator.rule_verification import RuleVerificationRegistry, rule_fingerprint

    rule = {"rule_id": "fixture", "calc": {}, "output": {"status": "CALCULATED", "final_result": "1"}}
    for filename in ["official.md", "calculator.py"]:
        (tmp_path / filename).write_text("reviewed version", encoding="utf-8")
    review = {
        "status": "verified_for_estimate", "reviewed_on": "2026-11-21",
        "checked_claims": ["fixture"], "limitations": ["fixture"],
        "evidence_files": [{"path": "official.md", "sha256": hashlib.sha256((tmp_path / "official.md").read_bytes()).hexdigest()}],
        "implementation_files": [{"path": "calculator.py", "sha256": hashlib.sha256((tmp_path / "calculator.py").read_bytes()).hexdigest()}],
    }
    catalog = tmp_path / "resources/data/policy_catalog"
    catalog.mkdir(parents=True)
    (catalog / "rules_2026_manifest.json").write_text(json.dumps({"rules": [{
        "rule_id": "fixture", "semantic_sha256": rule_fingerprint(rule), "verification": review,
    }]}), encoding="utf-8")
    registry = RuleVerificationRegistry(tmp_path, loaded_implementations={"calculator.py": review["implementation_files"][0]["sha256"]})
    assert registry.review(rule)["status"] == "verified_for_estimate"
    return registry, rule, catalog / "rules_2026_manifest.json"


@pytest.mark.parametrize("artifact", ["official.md", "calculator.py"])
@pytest.mark.parametrize("operation", ["change", "delete"])
def test_changed_or_missing_source_and_implementation_require_review(reviewed_fixture, artifact, operation):
    registry, rule, _ = reviewed_fixture
    tmp_path = registry.root
    if operation == "change":
        (tmp_path / artifact).write_text("different version", encoding="utf-8")
    else:
        (tmp_path / artifact).unlink()
    result = registry.review(rule)
    assert result["status"] == "needs_review"
    assert "重新核验" in result["message"]


@pytest.mark.parametrize("action,expected", [("delete", "unverified"), ("remove", "unverified"), ("downgrade", "manual_only")])
def test_existing_registry_observes_ledger_revocations(reviewed_fixture, action, expected):
    registry, rule, ledger = reviewed_fixture
    if action == "delete":
        ledger.unlink()
    else:
        data = json.loads(ledger.read_text(encoding="utf-8"))
        if action == "remove":
            data["rules"] = []
        else:
            data["rules"][0]["verification"]["status"] = "manual_only"
        ledger.write_text(json.dumps(data), encoding="utf-8")
    assert registry.review(rule)["status"] == expected


def test_hot_reapproved_disk_code_does_not_certify_old_loaded_code(reviewed_fixture):
    from app.agents.dsl_generator.rule_verification import RuleVerificationRegistry

    registry, rule, ledger = reviewed_fixture
    implementation = registry.root / "calculator.py"
    implementation.write_text("new reapproved code", encoding="utf-8")
    data = json.loads(ledger.read_text(encoding="utf-8"))
    data["rules"][0]["verification"]["implementation_files"][0]["sha256"] = hashlib.sha256(implementation.read_bytes()).hexdigest()
    ledger.write_text(json.dumps(data), encoding="utf-8")
    # Rebuilding the registry during a YAML reload does not reload Python modules.
    reloaded = RuleVerificationRegistry(registry.root, loaded_implementations=registry.loaded_implementations)
    assert reloaded.review(rule)["status"] == "needs_review"


def test_manual_only_ledger_does_not_allow_an_old_amount_calculation():
    engine = PolicyEngine(str(ROOT / "rules"))
    identity = "Rule_National_Digital_2026"
    rule = engine.rules[identity]
    review = engine.review_registry.review(rule)
    engine.review_registry = SimpleNamespace(review=lambda rule: review | {"status": "manual_only"})
    result = engine.execute(identity, rule["example_inputs"])
    assert result["status"] == "MANUAL_REVIEW"
    assert "final_result" not in result


def test_electric_bicycle_manual_trace_does_not_present_a_zero_amount():
    engine = PolicyEngine(str(ROOT / "rules"))
    rule = engine.rules["Rule_Changzhou_ElectricBicycle_2026"]
    result = engine.execute(rule["rule_id"], rule["example_inputs"])
    trace = str(result["explainability_trace"])
    assert "金额（元）：0" not in trace
    assert "金额尚未确定" in trace


@pytest.mark.parametrize("query,identity", [
    ("常州2026人才专属房票，申请日期2026-11-21，请计算个人金额", "Rule_Changzhou_TalentSupport_2026"),
    ("常州人才租房补贴每月多少", "Rule_Changzhou_TalentSupport_2026"),
    ("常州人才生活补贴帮我算一下", "Rule_Changzhou_TalentSupport_2026"),
    ("常州2026电动自行车以旧换新，2026-11-21买车3000元", "Rule_Changzhou_ElectricBicycle_2026"),
])
def test_manual_rule_natural_names_reach_the_first_candidate(query, identity):
    cls = load_subject_definitions("app/agents/pipeline/rule_agent.py", "RuleEngineAgent", FinalAnswer=FinalAnswer, uuid4=uuid4)["RuleEngineAgent"]
    agent = object.__new__(cls)
    agent.engine = PolicyEngine(str(ROOT / "rules"))
    agent.max_rules = 5
    selected = []

    async def plan(message, contexts):
        selected.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning="candidate verification")

    agent._plan_execution = plan
    asyncio.run(agent.compute(query))
    assert selected[0]["rule_id"] == identity
