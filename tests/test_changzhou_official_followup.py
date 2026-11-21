"""Keep newly checked local standards separate from individual entitlements."""

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.models.policy import FinalAnswer
from scripts.official_policy_data import load_curated_faq, load_official_policies
from test_python_guidelines_knowledge_pipeline import load_subject_definitions

ROOT = Path(__file__).resolve().parents[1]
BATCH = "changzhou_official_followup_20261121"


def test_eight_official_bodies_and_eighteen_faq_reach_accepted_sources():
    batch = json.loads(
        (ROOT / f"resources/data/policy_catalog/{BATCH}.json").read_text(
            encoding="utf-8"
        )
    )
    sources = {row["url"]: row for row in load_official_policies(ROOT)}
    faq = load_curated_faq(ROOT, list(sources.values()))
    questions = json.loads(
        (ROOT / f"resources/faq/{BATCH}.json").read_text(encoding="utf-8")
    )
    assert len(batch) == 8 and len(questions) == 18
    assert {row["question"] for row in questions} <= {row["question"] for row in faq}
    for row in batch:
        assert sources[row["url"]]["body_sha256"] == row["body_sha256"]
        assert (
            hashlib.sha256((ROOT / row["raw_path"]).read_bytes()).hexdigest()
            == row["raw_sha256"]
        )


def test_minimum_standards_are_not_promised_as_every_persons_payment():
    faq = json.loads((ROOT / f"resources/faq/{BATCH}.json").read_text(encoding="utf-8"))
    answers = {row["question"]: row["answer"] for row in faq}
    living = answers["常州2026年低保标准现在是多少？"]
    unemployment = answers["常州2026年失业保险金最低标准是多少？"]
    assert "1110" in living and "2026年7月1日" in living and "实际可领" in living
    assert "1665" in unemployment and "下限" in unemployment and "不是" in unemployment


def test_missing_attachments_and_dated_execution_reports_keep_their_boundaries():
    batch = json.loads(
        (ROOT / f"resources/data/policy_catalog/{BATCH}.json").read_text(
            encoding="utf-8"
        )
    )
    sources = {row["source_id"]: row for row in batch}
    expanded = sources["expanded_employment_notice"]
    assert expanded["attachments_status"] == "not_retrieved"
    assert "未" in expanded["retrieval_note"] and "金额" in expanded["retrieval_note"]
    publicity = sources["tianning_grants_publicity"]
    assert publicity["published_date"] == "2026-09-14"
    assert publicity["scope"] == "江苏省常州市天宁区"


@pytest.mark.parametrize(
    "query",
    [
        "常州买智能洗碗机4000元能补贴多少？",
        "请算常州电动轮椅价格20000元的补贴",
        "常州智能门锁3999.99元补贴怎么算？",
        "常州咖啡机补贴金额怎么算？",
    ],
)
def test_local_products_enter_the_correct_candidate_without_national_category_inference(
    query,
):
    cls = load_subject_definitions(
        "app/agents/pipeline/rule_agent.py",
        "RuleEngineAgent",
        FinalAnswer=FinalAnswer,
        uuid4=uuid4,
    )["RuleEngineAgent"]
    agent = object.__new__(cls)
    agent.engine = PolicyEngine(str(ROOT / "rules"))
    agent.max_rules = 5
    selected = []

    async def plan(message, contexts):
        selected.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning="candidate audit")

    agent._plan_execution = plan
    asyncio.run(agent.compute(query))
    assert selected[0]["rule_id"] == "Rule_Changzhou_SmartGoods_2026"


def test_smart_goods_rule_executes_against_the_frozen_official_clause():
    path = ROOT / "rules/Rule_Changzhou_SmartGoods_2026.yaml"
    rule = yaml.safe_load(path.read_text(encoding="utf-8"))
    body = (ROOT / rule["policy_source"]["source_path"]).read_text(
        encoding="utf-8"
    ).split("\n## 正文\n", 1)[1].strip() + "\n"
    assert (
        hashlib.sha256(body.encode()).hexdigest()
        == rule["policy_source"]["body_sha256"]
    )
    result = PolicyEngine(str(ROOT / "rules")).execute(
        rule["rule_id"], rule["example_inputs"]
    )
    assert result["status"] == "CALCULATED" and float(result["final_result"]) == 600
    assert "未确定/不适用" not in str(result["explainability_trace"])


def test_missing_overlapping_field_names_keep_whole_chinese_labels():
    cls = load_subject_definitions(
        "app/agents/pipeline/rule_agent.py", "RuleEngineAgent"
    )["RuleEngineAgent"]
    message = cls._format_result(
        {
            "status": "INVALID_INPUT",
            "errors": [
                "缺少必填参数: platform_category_confirmed",
                "缺少必填参数: prior_category_claims",
            ],
        },
        {"category": None, "price": 0, "confirmed": False},
        [
            {"name": "category", "label": "平台确认细分品类"},
            {"name": "platform_category_confirmed", "label": "细分归类已核实"},
            {"name": "prior_category_claims", "label": "本期细分类已享次数"},
            {"name": "price", "label": "销售价"},
            {"name": "confirmed", "label": "资格已核实"},
        ],
    )
    assert "缺少必填参数: 细分归类已核实" in message
    assert "缺少必填参数: 本期细分类已享次数" in message
    assert (
        "platform_" not in message and "prior_" not in message and "None" not in message
    )
    assert "销售价=0" in message and "资格已核实=否" in message


@pytest.mark.parametrize("claim", ["", "not-a-date", False])
def test_invalid_model_reference_date_is_an_input_error_not_server_error(claim):
    rule = yaml.safe_load(
        (ROOT / "rules/Rule_Changzhou_SmartGoods_2026.yaml").read_text(encoding="utf-8")
    )
    inputs = dict(rule["example_inputs"], claim_time=claim)
    result = PolicyEngine(str(ROOT / "rules")).execute(rule["rule_id"], inputs)
    assert result["status"] == "INVALID_INPUT"
    assert "claim_time" in str(result["errors"])
