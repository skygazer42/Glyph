"""Source examples and boundary cases from 常公积金委〔2026〕3号."""

import pytest

from app.agents.dsl_generator import provident_fund_calculations as calculations


def calculate(**changes):
    """Use the official 2025-interest / 2026-subsidy example as the baseline."""
    inputs = {
        "claim_time": "2026-11-21",
        "eligibility_confirmed": True,
        "recognition_year": 2025,
        "interest_year": 2025,
        "difficulty_class": "minimum_edge",
        "highest_class_confirmed": True,
        "eligible_interest_paid_previous_year": 12000,
        "interest_basis_confirmed": True,
        "loan_issued_in_changzhou": True,
        "loan_currently_overdue": False,
        "subsidy_already_received_for_year": False,
    }
    return calculations.changzhou_provident_hardship_subsidy_2026(inputs | changes)


@pytest.mark.parametrize(
    "category,amount",
    [
        ("extreme", 12000),
        ("minimum", 12000),
        ("minimum_edge", 9600),
        ("general", 9600),
        ("rigid_expense", 9600),
    ],
)
def test_five_recognized_categories_without_retired_6000_yuan_cap(category, amount):
    result = calculate(difficulty_class=category)
    assert result["status"] == "CALCULATED"
    assert result["amount"] == amount
    assert "6000" in result["reason"]
    assert "非申即享" in result["reason"]


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"eligibility_confirmed": False}, "MANUAL_REVIEW"),
        ({"highest_class_confirmed": False}, "MANUAL_REVIEW"),
        ({"interest_basis_confirmed": False}, "MANUAL_REVIEW"),
        ({"loan_issued_in_changzhou": False}, "INELIGIBLE"),
        ({"loan_currently_overdue": True}, "INELIGIBLE"),
        ({"subsidy_already_received_for_year": True}, "INELIGIBLE"),
        ({"difficulty_class": "none"}, "INELIGIBLE"),
        ({"difficulty_class": "unknown"}, "INVALID_INPUT"),
        ({"interest_year": 2026}, "INVALID_INPUT"),
        ({"recognition_year": 2024}, "INVALID_INPUT"),
        ({"eligible_interest_paid_previous_year": True}, "INVALID_INPUT"),
        ({"eligible_interest_paid_previous_year": -1}, "INVALID_INPUT"),
        ({"eligible_interest_paid_previous_year": "NaN"}, "INVALID_INPUT"),
        ({"eligible_interest_paid_previous_year": "Infinity"}, "INVALID_INPUT"),
        ({"recognition_year": 2025.5}, "INVALID_INPUT"),
        ({"claim_time": "2026-06-30"}, "NOT_IN_PERIOD"),
        ({"claim_time": "2031-07-01"}, "NOT_IN_PERIOD"),
    ],
)
def test_no_success_amount_for_wrong_period_basis_qualification_or_duplicate(
    changes, status
):
    result = calculate(**changes)
    assert result["status"] == status
    assert result["amount"] == 0


def test_effective_day_and_expiry_day_are_inclusive():
    assert calculate(claim_time="2026-07-01")["amount"] == 9600
    assert (
        calculate(claim_time="2031-06-30", recognition_year=2030, interest_year=2030)[
            "amount"
        ]
        == 9600
    )


def test_confirmed_zero_paid_interest_is_zero_not_missing():
    result = calculate(eligible_interest_paid_previous_year=0)
    assert result["status"] == "CALCULATED"
    assert result["amount"] == 0


def test_future_period_message_does_not_claim_policy_has_expired():
    from app.agents.dsl_generator.rule_engine import PolicyEngine

    engine = PolicyEngine()
    rule_id = "Rule_Changzhou_ProvidentContribution_2026"
    result = engine.execute(rule_id, {"claim_time": "2026-06-30"})
    assert "政策已过期" not in result["message"]
    assert "不在" in result["message"]


@pytest.mark.parametrize(
    "query",
    [
        "请按常州困难家庭公积金贷款年度贴息规则计算，低保边缘家庭去年利息12000元",
        "我在常州有公积金贷款，去年利息12000元，能领多少困难家庭贷款贴息？",
        "常州公积金低保贷款的利息补贴怎么计算？",
    ],
)
def test_hardship_natural_requests_reach_the_correct_bounded_planner(query):
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    from app.agents.dsl_generator.rule_engine import PolicyEngine
    from app.models.policy import FinalAnswer
    from test_python_guidelines_knowledge_pipeline import load_subject_definitions

    cls = load_subject_definitions(
        "app/agents/pipeline/rule_agent.py",
        "RuleEngineAgent",
        FinalAnswer=FinalAnswer,
        uuid4=uuid4,
    )["RuleEngineAgent"]
    agent = object.__new__(cls)
    agent.engine = PolicyEngine()
    agent.max_rules = 5
    selected = []

    async def plan(message, contexts):
        selected.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning="candidate audit")

    agent._plan_execution = plan
    asyncio.run(agent.compute(query))
    assert selected[0]["rule_id"] == "Rule_Changzhou_ProvidentHardshipSubsidy_2026"


@pytest.mark.parametrize(
    "query,expected",
    [
        (
            "常州公积金贷款去年利息12000元，能领多少困难家庭贷款贴息？身份还没核实",
            "rule_engine",
        ),
        ("常州困难家庭贷款贴息需要哪些材料？", "knowledge"),
        ("2026年常州公积金政策有哪些？", "knowledge"),
    ],
)
def test_personal_amount_request_does_not_depend_on_model_calculation_intent(
    query, expected
):
    from contextvars import ContextVar
    from types import SimpleNamespace

    from test_python_guidelines_knowledge_pipeline import load_subject_definitions

    cls = load_subject_definitions(
        "app/agents/service/agent_service.py", "AgentService"
    )["AgentService"]
    agent = object.__new__(cls)
    agent._request_state = ContextVar("financial_accuracy_request")
    agent._request_state.set(SimpleNamespace(routing_debug=[]))
    agent._looks_like_sql_question = lambda message: False
    agent._needs_clarification = lambda *args: False
    agent._looks_like_graph_question = lambda *args: False
    agent._looks_like_user_history = lambda message: False
    intent = {
        "intent": "policy_inquiry",
        "sub_intent": "benefit",
        "raw_query": query,
        "domain_context": {},
        "chains": ["kb_chain"],
    }
    assert agent._resolve_route(intent, query, None, []) == expected


@pytest.mark.parametrize(
    "raw,rewritten,expected",
    [
        (
            "公积金贷款贴息能领多少？",
            "常州困难家庭公积金贷款贴息政策咨询",
            "rule_engine",
        ),
        ("需要哪些材料？", "常州公积金贷款贴息能领多少，现追问申请材料", "knowledge"),
    ],
)
def test_amount_routing_uses_current_question_not_historical_rewrite(
    raw, rewritten, expected
):
    from contextvars import ContextVar
    from types import SimpleNamespace
    from test_python_guidelines_knowledge_pipeline import load_subject_definitions

    cls = load_subject_definitions(
        "app/agents/service/agent_service.py", "AgentService"
    )["AgentService"]
    agent = object.__new__(cls)
    agent._request_state = ContextVar("financial_accuracy_rewrite")
    agent._request_state.set(SimpleNamespace(routing_debug=[]))
    agent._looks_like_sql_question = lambda message: False
    agent._needs_clarification = lambda *args: False
    agent._looks_like_graph_question = lambda *args: False
    agent._looks_like_user_history = lambda message: False
    intent = {
        "intent": "policy_inquiry",
        "sub_intent": "benefit",
        "raw_query": raw,
        "domain_context": {},
        "chains": ["kb_chain"],
    }
    assert agent._resolve_route(intent, rewritten, None, []) == expected


@pytest.mark.parametrize(
    "query,expected",
    [
        ("常州困难家庭公积金贷款贴息需要哪些材料、要自己申请吗？", False),
        ("常州公积金贷款贴息怎么办理？", False),
        ("常州困难家庭贴息跨部门审核的分工和衔接关系是什么？", True),
    ],
)
def test_single_policy_materials_do_not_go_to_partial_relationship_graph(
    query, expected
):
    from test_python_guidelines_knowledge_pipeline import load_subject_definitions

    cls = load_subject_definitions(
        "app/agents/service/agent_service.py", "AgentService"
    )["AgentService"]
    assert object.__new__(cls)._looks_like_graph_question(query) is expected


def test_high_similarity_financial_source_does_not_bypass_question_based_answer():
    import asyncio
    import time
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4
    from app.models.policy import FinalAnswer, PolicyDocument, PolicyType
    from test_python_guidelines_knowledge_pipeline import load_subject_definitions

    cls = load_subject_definitions(
        "app/agents/pipeline/knowledge_agent.py",
        "KnowledgeAgent",
        time=time,
        FinalAnswer=FinalAnswer,
        uuid4=uuid4,
        settings=SimpleNamespace(system=SimpleNamespace(early_stop_conf=0.8)),
    )["KnowledgeAgent"]
    agent = cls(SimpleNamespace(last_timings={}))
    source = PolicyDocument(
        content="补贴标准：15%；材料：电梯使用登记证书。",
        title="其他提取业务",
        source="https://www.changzhou.gov.cn/example",
        doc_type=PolicyType.GUIDELINE,
    )
    agent._domain_aware_search = AsyncMock(
        return_value=([source], [0.99], "贷款贴息材料")
    )
    agent._should_direct_return_dify = lambda docs: False
    agent._estimate_confidence = lambda scores: 0.99
    agent._format_documents = lambda docs: "已分业务标注来源"
    agent._collect_images = lambda docs: []
    agent._call_llm = AsyncMock(return_value="本次贴息非申即享，不套其他提取材料。")
    result = asyncio.run(agent.answer("常州困难家庭公积金贷款贴息如何办理？"))
    agent._call_llm.assert_awaited_once()
    assert result.metadata["early_stopped"] is False
    assert "电梯使用登记" not in result.answer
