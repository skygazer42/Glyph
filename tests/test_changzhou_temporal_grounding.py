"""Actual annual-source and expired-rate regressions from the alignment audit."""

import asyncio
import json
from calendar import monthrange
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import time

import pytest

from app.models.policy import FinalAnswer, PolicyDocument, PolicyType
from test_python_guidelines_knowledge_pipeline import load_subject_definitions


def source(title, text):
    return PolicyDocument(
        title=title, content=text, source=f"https://example.gov.cn/{uuid4()}",
        doc_type=PolicyType.GUIDELINE,
    )


def agent(tool=None):
    cls = load_subject_definitions(
        "app/agents/pipeline/knowledge_agent.py", "KnowledgeAgent",
        date=date, monthrange=monthrange, time=time, FinalAnswer=FinalAnswer, uuid4=uuid4,
        settings=SimpleNamespace(system=SimpleNamespace(early_stop_conf=.8, knowledge_max_context_per_doc=6000)),
    )["KnowledgeAgent"]
    instance = cls(tool or SimpleNamespace(last_timings={}))
    instance._should_direct_return_dify = lambda docs: False
    instance._estimate_confidence = lambda scores: .8
    instance._collect_images = lambda docs: []
    return instance


def test_previous_annual_rate_cannot_answer_next_year_amount_without_llm():
    previous = source(
        "2026年度居民医保政策访谈",
        "资料名称：2026年度居民医保政策访谈\n保障年度：2026\n\n学生儿童每人270元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([previous], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Wrong-year money must not reach synthesis"))
    result = asyncio.run(subject.answer("2027年常州普通非从业居民医保每人交多少钱，含长期护理险？"))
    assert "不能确认" in result.answer or "未核实" in result.answer
    assert "2027" in result.answer
    assert "270" not in result.answer
    assert result.verification_passed is False


def test_expired_amount_is_not_reused_when_other_sources_only_describe_process():
    expired = source(
        "一次性营养补助计发标准",
        "资料名称：一次性营养补助计发标准\n施行日期：2025-07-01\n到期日期：2026-06-30\n\n2705元。",
    )
    process = source("生育服务提案答复", "资料名称：生育服务提案答复\n\n一次性营养补助直接发放到个人。")
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([expired, process], [.9, .8], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Expired money must not reach synthesis"))
    result = asyncio.run(subject.answer("2026年11月在常州生孩子，一次性营养补助现在是多少？"))
    assert "不能确认" in result.answer or "未核实" in result.answer
    assert "2705" not in result.answer


def test_annual_outline_does_not_certify_all_amounts_for_every_month():
    outline = source(
        "2026年度职工医保政策宣传提纲",
        "资料名称：2026年度职工医保政策宣传提纲\n保障年度：2026\n\n一次性营养补助2705元，仅对应2025-07至2026-06。其他政策仍有效。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([outline], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("An annual outline is not a full-year rate guarantee"))
    result = asyncio.run(subject.answer("2026年11月生孩子，一次性营养补助现在是多少？"))
    assert "不能确认" in result.answer
    assert "2705" not in result.answer


def test_unmatched_calculation_returns_source_based_knowledge_explanation():
    cls = load_subject_definitions("app/agents/service/agent_service.py", "AgentService")["AgentService"]
    subject = object.__new__(cls)
    unmatched = SimpleNamespace(metadata={"route": "rule_engine", "reason": "no_match"})
    explanation = SimpleNamespace(metadata={"route": "knowledge"}, answer="不能直接计算，医保机构须核定剩余年限及适用基数。")
    subject.rule_agent = SimpleNamespace(compute=AsyncMock(return_value=unmatched))
    subject.knowledge_agent = SimpleNamespace(answer=AsyncMock(return_value=explanation))
    result = asyncio.run(subject._compute_with_knowledge_fallback(
        "医保退休一次性补缴能按4533×8%×剩余月数直接算吗？", intent={"intent": "calculation"}, domain_context=None,
    ))
    assert result is explanation
    assert result.metadata["fallback_from"] == "rule_engine"
    subject.knowledge_agent.answer.assert_awaited_once()


def test_selected_calculation_with_missing_facts_does_not_fall_back_to_guessing():
    cls = load_subject_definitions("app/agents/service/agent_service.py", "AgentService")["AgentService"]
    subject = object.__new__(cls)
    review = SimpleNamespace(metadata={"route": "rule_engine", "rule_id": "selected_rule"}, answer="请补充已核实资格。")
    subject.rule_agent = SimpleNamespace(compute=AsyncMock(return_value=review))
    subject.knowledge_agent = SimpleNamespace(answer=AsyncMock(side_effect=AssertionError("Do not guess missing personal facts")))
    assert asyncio.run(subject._compute_with_knowledge_fallback(
        "已匹配事项的个人金额", intent={}, domain_context=None,
    )) is review


def test_expiry_date_is_inclusive_and_publication_date_is_not_an_effective_period():
    item = source("正式标准", "施行日期：2025-07-01\n到期日期：2026-06-30\n\n2705元。")
    subject = agent()
    assert subject._temporal_status(item, (date(2026, 6, 30), date(2026, 6, 30))) == "covered"
    assert subject._temporal_status(item, (date(2026, 7, 1), date(2026, 7, 1))) == "expired"
    published = source("2026政策宣传提纲", "发布日期：2026-02-02\n\n2705元。")
    assert subject._temporal_status(published, (date(2026, 11, 1), date(2026, 11, 30))) == "undated"


def test_annual_source_recall_uses_year_and_observed_product_title():
    old = source(
        "江苏医惠保1号2026年度正式保障计划、保险条款及参保理赔须知",
        "资料名称：江苏医惠保1号2026年度正式保障计划、保险条款及参保理赔须知\n保障年度：2026\n\n正式条款。",
    )
    new = source("江苏医惠保1号2027年度正式保障计划", "保障年度：2027\n\n不设置年龄限制。")
    calls = []

    class Tool:
        async def search(self, query, **kwargs):
            calls.append(kwargs)
            if (kwargs.get("filters") or {}).get("coverage_year") == 2027:
                return [new], [.75]
            return [old], [.85]

    docs, _, _ = asyncio.run(agent(Tool())._domain_aware_search(
        "我60岁还能买2027江苏医惠保1号吗？有既往症怎么办？", None
    ))
    assert docs[0].id == new.id
    assert any((call.get("filters") or {}).get("title") == "江苏医惠保1号" for call in calls)


def test_basic_medical_query_does_not_take_commercial_supplement_premium():
    supplement = source(
        "江苏医惠保1号2027年度正式保障计划",
        "资料名称：江苏医惠保1号2027年度正式保障计划\n保障年度：2027\n说明：商业保险产品平台正式销售文件快照。\n\n158元。",
    )
    poster = source(
        "2027年度居民医保缴费截止日期和线上渠道",
        "资料名称：2027年度居民医保缴费截止日期和线上渠道\n保障年度：2027\n说明：官方公开资料快照。\n\n截止日期及渠道。",
    )
    docs, _ = agent()._prefer_verified_evidence(
        "2027年普通非从业居民医保每人交多少钱？", [supplement, poster], [.8, .7]
    )
    assert supplement not in docs
    assert poster in docs


def test_year_filter_uses_declared_coverage_instead_of_any_body_year():
    cls = load_subject_definitions("app/knowledge/milvus.py", "MilvusStore")["MilvusStore"]
    expression = cls._build_filter({"coverage_year": 2027, "title": "江苏医惠保1号"})
    assert 'content like ' + json.dumps("%保障年度：2027%", ensure_ascii=False) in expression
    assert " && " in expression


def test_unrelated_current_policy_amount_does_not_fill_missing_nutrition_standard():
    unrelated = source(
        "江苏医惠保1号2026年度保障方案",
        "资料名称：江苏医惠保1号2026年度保障方案\n保障年度：2026\n说明：官方公开资料快照。\n\n每人158元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([unrelated], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Do not borrow another business price"))
    result = asyncio.run(subject.answer("2026年11月常州一次性营养补助现在是多少？"))
    assert "158" not in result.answer
    assert "不能确认" in result.answer or "未核实" in result.answer


def test_how_much_can_be_claimed_uses_same_period_guard_as_how_much_money():
    outline = source(
        "2026年度职工医疗保障政策宣传提纲",
        "资料名称：2026年度职工医疗保障政策宣传提纲\n保障年度：2026\n\n营养补助2705元，仅适用至2026-06-30。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([outline], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Ordinary claim wording cannot bypass period guard"))
    result = asyncio.run(subject.answer("2026年11月常州生孩子，一次性营养补助能领多少？"))
    assert "2705" not in result.answer
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_how_much_to_pay_does_not_use_undated_old_interview_as_future_rate():
    interview = source(
        "2026年度居民医保政策在线访谈实录",
        "资料名称：2026年度居民医保政策在线访谈实录\n发布日期：2026-01-01\n\n学生儿童缴费270元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([interview], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Payment wording cannot bypass annual evidence"))
    result = asyncio.run(subject.answer("2027年常州普通非从业居民医保交多少，含长期护理险？"))
    assert "270" not in result.answer
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_undated_amount_question_means_current_not_expired_amount():
    expired = source(
        "一次性营养补助标准",
        "资料名称：一次性营养补助标准\n施行日期：2025-07-01\n到期日期：2026-06-30\n\n2705元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([expired], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Omitting a date cannot make expired money current"))
    result = asyncio.run(subject.answer("常州一次性营养补助多少钱？"))
    assert "2705" not in result.answer
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_explicit_annual_interview_can_support_its_actual_student_rate():
    interview = source(
        "居民医疗保险 守护全民健康——2026年度居民医保政策在线访谈实录",
        "资料名称：居民医疗保险 守护全民健康——2026年度居民医保政策在线访谈实录\n保障年度：2026\n\n"
        "大学生的个人缴费标准为：居民医保240元/人，长期护理险30元/人，合计270元/人。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([interview], [.7], "query"))
    subject._call_llm = AsyncMock(return_value="2026年度大学生合计270元，含居民医保240元和长护险30元。")
    result = asyncio.run(subject.answer("2026年常州大学生居民医保交多少钱，含长期护理险？"))
    subject._call_llm.assert_awaited_once()
    assert "270元" in result.answer


def test_explicit_2026_official_resident_table_supports_new_north_830():
    official = source(
        "2026年度常州市居民医保（含长期护理险）的个人缴费标准是什么？",
        "资料名称：2026年度常州市居民医保（含长期护理险）的个人缴费标准是什么？\n保障年度：2026\n说明：官方公开资料快照。\n\n"
        "非从业居民：武进区、常州经开区、新北区、天宁区、钟楼区：基本医疗保险个人缴费标准为800元/人，长护险个人缴费标准为30元/人，合计830元/人。"
        "溧阳市、金坛区：基本医疗保险个人缴费标准为700元/人，长护险个人缴费标准为30元/人，合计730元/人。",
    )
    official.source = "https://www.changzhou.gov.cn/ns_news/11769565604746"
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([official], [.7], "query"))
    subject._call_llm = AsyncMock(return_value="2026年度新北区非从业居民800元医保加30元长护险，合计830元。")
    result = asyncio.run(subject.answer("2026年常州新北区普通非从业居民医保交多少钱，含长期护理险？"))
    subject._call_llm.assert_awaited_once()
    assert "830元" in result.answer


def test_explicit_annual_document_does_not_extend_a_narrower_amount_period():
    annual = source(
        "2026年度生育一次性营养补助办理指南",
        "资料名称：2026年度生育一次性营养补助办理指南\n保障年度：2026\n\n"
        "营养补助2705元，仅适用至2026-06-30。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([annual], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Annual title cannot extend an individual amount"))
    result = asyncio.run(subject.answer("2026年11月常州一次性营养补助能领多少？"))
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_empty_local_amount_evidence_cannot_bypass_guard_via_web():
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([], [], "query"))
    subject._search_web = AsyncMock(side_effect=AssertionError("Do not use unverified web snippets as current rates"))
    result = asyncio.run(subject.answer("2027年常州普通非从业居民医保交多少？"))
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_unrelated_calculation_candidates_are_not_sent_to_planner():
    cls = load_subject_definitions(
        "app/agents/pipeline/rule_agent.py", "RuleEngineAgent", FinalAnswer=FinalAnswer, uuid4=uuid4,
    )["RuleEngineAgent"]
    subject = object.__new__(cls)
    subject.max_rules = 5
    subject._collect_rules = lambda: [{"rule_id": "childcare", "title": "育儿补贴", "keywords": ["育儿补贴", "新生儿3600元"]}]
    subject._plan_execution = AsyncMock(side_effect=AssertionError("Nutrition is not childcare"))
    result = asyncio.run(subject.compute("2026年11月在常州生孩子，一次性营养补助现在是多少？"))
    assert result.metadata.get("rule_id") is None


def test_amount_without_local_period_evidence_does_not_borrow_unverified_web_rate():
    subject = agent(SimpleNamespace(last_timings={}))
    subject.web_tool = SimpleNamespace(enabled=True)
    subject._domain_aware_search = AsyncMock(return_value=([], [], "query"))
    subject._search_web = AsyncMock(side_effect=AssertionError("Unverified web rates must not bypass the period gate"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Do not invent current amounts"))
    result = asyncio.run(subject.answer("2027年常州普通非从业居民医保交多少？"))
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_observed_revised_basis_url_is_recalled_before_old_same_business_text():
    url = "https://www.mee.gov.cn/zcwj/gwywj/202608/t20260820_1164286.shtml"
    old = source(
        "常州市公积金贷款管理实施细则",
        "资料名称：常州市公积金贷款管理实施细则\n适用说明：新正式依据：" + url
        + "\n说明：官方公开资料快照。\n\n旧审批规定15日。",
    )
    revised = source(
        "住房公积金管理条例（2026修订）",
        "资料名称：住房公积金管理条例（2026修订）\n施行日期：2026-09-20\n说明：官方公开资料快照。\n\n受理申请之日起10日内作出准予或不准予贷款的决定。",
    )
    revised.source = url

    class Tool:
        async def search(self, query, **kwargs):
            if (kwargs.get("filters") or {}).get("source") == url:
                return [revised], [.7]
            return [old], [.85]

    docs, scores, _ = asyncio.run(agent(Tool())._domain_aware_search(
        "现在常州公积金贷款申请几日内决定准予贷款？", None
    ))
    assert docs[0].source == url
    assert scores[0] == .7


def test_non_material_question_does_not_use_blank_form_as_required_material():
    template = source(
        "医保单位补缴申请表",
        "资料名称：医保单位补缴申请表\n资料类型：official_form_template\n说明：官方公开资料快照。\n\n用人单位补缴并盖章。",
    )
    policy = source(
        "退休医保最低缴费年限",
        "资料名称：退休医保最低缴费年限\n说明：官方公开资料快照。\n\n首次参保时间与视同年限须医保核定。",
    )
    docs, _ = agent()._prefer_verified_evidence("医保退休补缴能直接算吗？", [template, policy], [.9, .7])
    assert template not in docs
    assert policy in docs


def test_referenced_document_number_recalls_transition_conditions():
    old = source(
        "退休医保一次性补缴",
        "资料名称：退休医保一次性补缴\n适用说明：需结合常医保待遇〔2023〕71号首次参保分界。\n说明：官方公开资料快照。\n\n2020原版一般年限。",
    )
    updated = source(
        "职工基本医疗保险最低缴费年限处理意见",
        "资料名称：职工基本医疗保险最低缴费年限处理意见\n说明：官方公开资料快照。\n\n常医保待遇〔2023〕71号：2023年6月1日起首次参保与此前人员按规定分别处理。",
    )

    class Tool:
        async def search(self, query, **kwargs):
            if (kwargs.get("filters") or {}).get("content") == "常医保待遇〔2023〕71号":
                return [updated], [.7]
            return [old], [.85]

    docs, _, _ = asyncio.run(agent(Tool())._domain_aware_search(
        "常州医保退休一次性补缴能否直接计算？", None
    ))
    assert docs[0].id == updated.id


def test_current_undated_official_service_guide_keeps_its_public_standard_identity():
    guide = source(
        "城乡居民基本养老保险费一次性补缴核定",
        "资料名称：城乡居民基本养老保险费一次性补缴核定\n资料类型：official_service_guide\n说明：官方公开资料快照。\n\n"
        "最低缴费档次1000元，特殊困难群体按规定处理，具体补缴由经办机构核定。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([guide], [.9], "query"))
    subject._call_llm = AsyncMock(return_value="该指南公开最低档次为1000元，特殊群体除外。")
    answer = asyncio.run(subject.answer("金坛城乡居民养老保险一次性补缴最低多少钱？"))
    assert "1000元" in answer.answer
    assert "指南" in answer.answer and "核定" in answer.answer
    subject._call_llm.assert_awaited_once()


def test_undated_service_snapshot_cannot_prove_a_future_annual_standard():
    guide = source(
        "城乡居民基本养老保险费一次性补缴核定",
        "资料名称：城乡居民基本养老保险费一次性补缴核定\n资料类型：official_service_guide\n说明：官方公开资料快照。\n\n最低缴费档次1000元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([guide], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("A snapshot is not a future effective-period certificate"))
    answer = asyncio.run(subject.answer("2027年金坛城乡居民养老保险补缴最低多少钱？"))
    assert "1000" not in answer.answer
    assert answer.metadata["reason"] == "temporal_evidence_gap"


def test_direct_official_amount_with_covering_dates_can_still_be_answered():
    valid = source(
        "一次性营养补助计发标准",
        "资料名称：一次性营养补助计发标准\n施行日期：2025-07-01\n到期日期：2026-06-30\n\n2705元。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([valid], [.75], "query"))
    subject._call_llm = AsyncMock(return_value="该期间标准为2705元；个人资格另行核定。")
    result = asyncio.run(subject.answer("2026年6月常州一次性营养补助标准是多少？"))
    assert "2705" in result.answer
    subject._call_llm.assert_awaited_once()
    assert result.sources == [valid]


@pytest.mark.parametrize("query", [
    "2027年常州普通居民医保每人交多少钱？",
    "2027年常州普通居民医疗保险每人交多少钱？",
])
def test_commercial_premium_is_never_basic_medical_fee_when_it_is_only_hit(query):
    contract = source(
        "江苏医惠保1号2027年度正式保障计划",
        "资料名称：江苏医惠保1号2027年度正式保障计划\n保障年度：2027\n资料类型：commercial_insurance_formal_sales_documents\n"
        "说明：商业保险产品平台正式销售文件快照。\n\n保险期间内，被保险人住院发生基本医保支付范围内个人自付费用，按照如下办法赔付：\n在扣除年度免赔额1.46万元后，对10万元以内部分按照50%的比例进行赔付。",
    )
    contract.source = "https://cx-hmb.zkydib.com/js27/assets/js/agreement~index~myAccount.9c910c51.js"
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([contract], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Commercial insurance is not basic medical insurance"))
    result = asyncio.run(subject.answer(query))
    assert result.metadata["reason"] == "temporal_evidence_gap"
    assert "158" not in result.answer and "1.46" not in result.answer


@pytest.mark.parametrize("query", [
    "2027年江苏医惠保1号的基本医保范围内自付费用免赔额是多少？",
    "2027年补充商业医疗保险江苏医惠保1号免赔额是多少？",
])
def test_explicit_commercial_product_question_keeps_its_formal_contract(query):
    contract = source(
        "江苏医惠保1号2027年度正式保障计划",
        "资料名称：江苏医惠保1号2027年度正式保障计划\n保障年度：2027\n资料类型：commercial_insurance_formal_sales_documents\n"
        "说明：商业保险产品平台正式销售文件快照。\n\n保险期间内，被保险人住院发生基本医保支付范围内个人自付费用，按照如下办法赔付：\n在扣除年度免赔额1.46万元后，对10万元以内部分按照50%的比例进行赔付。",
    )
    contract.source = "https://cx-hmb.zkydib.com/js27/assets/js/agreement~index~myAccount.9c910c51.js"
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([contract], [.9], "query"))
    subject._call_llm = AsyncMock(return_value="2027年度江苏医惠保1号该责任年度免赔额为1.46万元。")
    result = asyncio.run(subject.answer(query))
    subject._call_llm.assert_awaited_once()
    assert result.sources == [contract]
    assert "1.46万元" in result.answer


def test_government_product_release_does_not_turn_commercial_premium_into_basic_fee():
    release = source(
        "2027年度“江苏医惠保1号”上线",
        "资料名称：2027年度“江苏医惠保1号”上线\n保障年度：2027\n资料类型：official_published_product_information\n说明：官方公开资料快照。\n\n"
        "面向基本医保参保人员的基础版保费158元/人/年。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([release], [.9], "query"))
    subject._call_llm = AsyncMock(side_effect=AssertionError("Government publication does not change insurance type"))
    result = asyncio.run(subject.answer("2027年常州普通居民医保每人交多少钱？"))
    assert result.metadata["reason"] == "temporal_evidence_gap"


def test_preexisting_question_keeps_claim_difference_and_definition_from_same_annual_contract():
    url = "https://cx-hmb.zkydib.com/js27/assets/js/agreement~index~myAccount.9c910c51.js"
    header = (
        "资料名称：江苏医惠保1号2027年度正式保障计划、保险条款及参保理赔须知\n保障年度：2027\n"
        "资料类型：commercial_insurance_formal_sales_documents\n说明：商业保险产品平台正式销售文件快照。\n\n"
    )
    wrong_sections = [source("江苏医惠保1号2027年度正式保障计划", header + f"第{index}份癌症年龄分期表、联系方式和保险金材料。") for index in range(5)]
    claim = source("江苏医惠保1号2027年度正式保障计划", header + "责任一：既往病史参保人员赔付比例在上述赔付比例基础上下降15个百分点。")
    definition = source("江苏医惠保1号2027年度正式保障计划", header + "六、特别约定\n既往病史参保人员待遇约定：首次购买本产品时为非既往病史参保人员，之后连续参保的，按非既往病史参保人员享受赔付待遇。上述约定仅适用于责任一至四，责任五和六按各自约定。")
    for doc in wrong_sections + [claim, definition]:
        doc.source = url
    age = source("2027年度江苏医惠保1号上线", "保障年度：2027\n\n正常参加江苏省基本医疗保险、不设置年龄和健康状况参保限制。")
    calls = []

    class Tool:
        async def search(self, query, **kwargs):
            calls.append(kwargs)
            filters = kwargs.get("filters") or {}
            if filters.get("source") == url and filters.get("content") == "既往病史参保人员赔付比例":
                assert filters["coverage_year"] == 2027
                return [claim], [.65]
            if filters.get("source") == url and filters.get("content") == "既往病史参保人员待遇约定":
                assert filters["coverage_year"] == 2027
                return [definition], [.64]
            return [age] + wrong_sections, [.8] + [.75] * 5

    docs, scores, _ = asyncio.run(agent(Tool())._domain_aware_search(
        "我60岁还能买2027江苏医惠保1号吗？有既往症怎么办？", None
    ))
    ids = {doc.id for doc in docs}
    assert {claim.id, definition.id, age.id} <= ids
    assert len(docs) <= 5
    assert scores[docs.index(next(doc for doc in docs if doc.id == claim.id))] == .65
    facet_calls = [row for row in calls if (row.get("filters") or {}).get("content", "").startswith("既往病史参保人员")]
    assert facet_calls and all(row["filters"]["coverage_year"] == 2027 for row in facet_calls)


@pytest.mark.parametrize("reduction", [15, 9])
def test_actual_preexisting_answer_quotes_complete_conditions_without_inventing_materials(reduction):
    receipt = Path("resources/data/research/20261121/mimirq-changzhou-data-20261121/supplementary_actual_retrieval_after.json")
    actual = json.loads(receipt.read_text(encoding="utf-8"))
    docs = [PolicyDocument(
        id=row["id"], title=row["title"], content=row["content"].replace("下降15个百分点", f"下降{reduction}个百分点"),
        source=row["source"], metadata=row["metadata"], doc_type=PolicyType.GUIDELINE,
    ) for row in actual["docs"]]
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=(docs, [row["score"] for row in actual["docs"]], actual["query"]))
    subject._call_llm = AsyncMock(return_value=(
        "能购买。需要哪些材料：通常需提供有效身份证件。既往病史参保人员赔付比例一概下降15个百分点。"
    ))
    result = asyncio.run(subject.answer(actual["query"]))
    assert "首次购买本产品时为非既往病史参保人员，之后连续参保的，按非既往病史参保人员享受赔付待遇。" in result.answer
    assert "上述约定仅适用于“基础版”及“升级版”的责任一、责任二、责任三和责任四。" in result.answer
    assert "“升级版”的责任五和责任六以本保障计划第四条“保障责任详述”对应约定为准。" in result.answer
    assert "正常参加江苏省基本医疗保险" in result.answer and "不设置年龄" in result.answer
    assert f"下降{reduction}个百分点" in result.answer
    assert "责任一：基本医保支付范围内个人自付保障责任" in result.answer
    assert "需要哪些材料" not in result.answer and "有效身份证件" not in result.answer
    assert "申请与给付" not in result.answer
    subject._call_llm.assert_not_awaited()


@pytest.mark.parametrize("direction", ["以前", "以后"])
def test_model_cannot_invent_applicability_from_publication_year(direction):
    old = source(
        "2020原版最低缴费年限条款摘录",
        "资料名称：2020原版最低缴费年限条款摘录\n发布日期：2020-12-31\n说明：官方公开资料快照。\n\n最低缴费年限原政策。",
    )
    transition = source(
        "常医保待遇〔2023〕71号",
        "资料名称：常医保待遇〔2023〕71号\n发布日期：2023-06-01\n说明：官方公开资料快照。\n\n"
        "2023年6月1日起首次参保人员与此前已参保人员，分别按规定执行。此前已参保人员可选择我市原有最低缴费年限政策或条例相应规定。",
    )
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([transition, old], [.8, .7], "query"))
    subject._call_llm = AsyncMock(return_value=(
        f"不能直接套公式。\n1. 常医保待遇〔2023〕71号（适用年度：2023年及{direction}）："
        "2023年6月1日起首次参保人员与此前人员分别处理。\n"
        f"2. 2020原版最低缴费年限条款摘录（适用年度：2020年及{direction}）：此前人员可选择原有政策。"
    ))
    result = asyncio.run(subject.answer("常州医保退休一次性补缴能直接按4533×8%×剩余月数算吗？"))
    assert f"2020年及{direction}" not in result.answer and f"2023年及{direction}" not in result.answer
    assert "2023年6月1日起首次参保" in result.answer
    assert "2020原版最低缴费年限条款摘录" in result.answer
    assert result.sources == [transition, old]


def test_explicit_source_applicability_range_is_preserved():
    current = source("适用范围", "资料名称：适用范围\n说明：官方公开资料快照。\n\n适用年度：2023年及以后。")
    subject = agent()
    subject._domain_aware_search = AsyncMock(return_value=([current], [.7], "query"))
    subject._call_llm = AsyncMock(return_value="依据原文，适用年度：2023年及以后。")
    result = asyncio.run(subject.answer("这份医保政策适用什么年度？"))
    assert "适用年度：2023年及以后" in result.answer
