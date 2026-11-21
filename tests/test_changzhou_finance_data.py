"""Financial source aliases and calculation routing must preserve facts."""

import hashlib
import json

import pytest

from scripts.official_policy_data import load_curated_faq
from test_python_guidelines_knowledge_pipeline import load_subject_definitions


def test_identical_official_source_paths_are_verified_without_losing_existing_faq(tmp_path):
    body = '同一来源的真实官方正文。\n'
    digest = hashlib.sha256(body.encode()).hexdigest()
    first = tmp_path / 'original.md'
    duplicate = tmp_path / 'same-source.md'
    first.write_text('# 原文\n\n## 正文\n\n' + body, encoding='utf-8')
    duplicate.write_bytes(first.read_bytes())
    entry = dict(question='问法', answer='原文', source='https://www.changzhou.gov.cn/example',
                 source_body_sha256=digest, source_quote=body.strip(),
                 source_markdown_path=duplicate.name)
    faq = tmp_path / 'resources/faq/changzhou_provident_finance_20261121.json'
    faq.parent.mkdir(parents=True)
    faq.write_text(json.dumps([entry]), encoding='utf-8')
    sources = [dict(url=entry['source'], markdown_path=first.name, body=body, body_sha256=digest)]
    assert load_curated_faq(tmp_path, sources) == [entry]
    duplicate.write_text('# 原文\n\n## 正文\n\n未经核验的金额。\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Unverified FAQ'):
        load_curated_faq(tmp_path, sources)


@pytest.mark.parametrize('query', ['常州公积金月供怎么计算', '公积金能贷多少，计算贷款额度',
                                  '帮我算应缴税', '公积金缴存额试算', '育儿补贴金额怎么算'])
def test_money_rule_tool_accepts_financial_requests_without_appliance_energy_grades(query):
    cls = load_subject_definitions('app/agents/service/agent_service.py', 'AgentService')['AgentService']
    assert object.__new__(cls)._looks_like_calculation(query)


def test_cents_are_not_silently_rounded_to_whole_yuan_in_chat():
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    text = cls._format_result(dict(status='CALCULATED', final_result=5347.88,
        policy_source={'title': '常州公积金', 'url': 'https://www.changzhou.gov.cn/example'}), {})
    assert '5,347.88' in text
    assert 'https://www.changzhou.gov.cn/example' in text


def test_missing_money_facts_are_requested_with_chinese_labels():
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    text = cls._format_result(dict(status='INVALID_INPUT', errors=['缺少必填参数: monthly_salary']), {},
                              [{'name': 'monthly_salary', 'label': '核定月平均工资'}])
    assert '核定月平均工资' in text
    assert 'monthly_salary' not in text


def test_rule_planner_receives_explicit_wire_choices_for_financial_tiers():
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    contexts = [dict(rule_id='loan', title='公积金贷款', inputs=[dict(name='rate_class', type='string',
                    description='官方核定档次', options=[{'label': '第一档', 'value': 'first'},
                                                     {'label': '第二档', 'value': 'second'}])])]
    prompt = cls._build_planner_prompt('计算月供', contexts)
    assert 'first' in prompt and 'second' in prompt and '第一档' in prompt


def test_provident_calculation_is_not_rewritten_as_missing_appliance_energy_grade():
    from app.agents.pipeline.rewrite_agent import ContextHints, RewriteAgent

    hints = ContextHints(topic='常州公积金', intent='calculation')
    question = '请按100万元、20年、第一档公积金利率计算等额本息月供'
    rewritten = RewriteAgent._compose_standalone(question, hints)
    assert '能效' not in rewritten and '产品类别' not in rewritten


def test_appliance_calculations_still_ask_for_relevant_missing_grades():
    from app.agents.pipeline.rewrite_agent import ContextHints

    assert '能效/水效等级' in ContextHints(product='冰箱', intent='calculation').missing_slots()


def test_financial_input_facts_use_chinese_names_and_typed_choices_in_chat():
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    text = cls._format_result(dict(status='CALCULATED', final_result='10.00'),
        {'rate_class': 'first', 'confirmed': True},
        [{'name': 'rate_class', 'label': '利率档次', 'options': [{'label': '第一档', 'value': 'first'}]},
         {'name': 'confirmed', 'label': '资格已核实'}])
    assert '利率档次=第一档' in text and '资格已核实=是' in text
    assert 'rate_class=' not in text


def test_natural_monthly_contribution_request_reaches_the_bounded_planner():
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4
    from app.agents.dsl_generator.rule_engine import PolicyEngine
    from app.models.policy import FinalAnswer

    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent',
                                   FinalAnswer=FinalAnswer, uuid4=uuid4)['RuleEngineAgent']
    agent = object.__new__(cls)
    agent.engine = PolicyEngine()
    agent.max_rules = 5
    selected = []

    async def plan(query, contexts):
        selected.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning='missing facts')

    agent._plan_execution = plan
    asyncio.run(agent.compute('请按常州公积金月缴存规则计算，工资8000元，缴存比例尚未确认'))
    assert selected[0]['rule_id'] == 'Rule_Changzhou_ProvidentContribution_2026'
