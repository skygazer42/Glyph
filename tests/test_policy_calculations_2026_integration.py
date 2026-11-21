"""2026 policy rules must be discoverable and executable through both API paths."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import yaml

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.api.endpoints.rule_preview import router
from app.models.policy import FinalAnswer
from test_python_guidelines_knowledge_pipeline import load_subject_definitions

ROOT = Path(__file__).resolve().parents[1]
RULE_IDS = [
    'Rule_National_Appliance_2026',
    'Rule_National_Digital_2026',
    'Rule_National_AutoScrap_2026',
    'Rule_National_AutoReplace_2026',
    'Rule_Changzhou_Renovation_2026',
    'Rule_Changzhou_NewHome_2026',
    'Rule_Changzhou_PropertyFee_2026',
    'Rule_Changzhou_ExistingHome_2026',
]


def rule_agent_class():
    """Load the real agent methods without constructing an external LLM client."""
    return load_subject_definitions(
        'app/agents/pipeline/rule_agent.py', 'RuleEngineAgent',
        FinalAnswer=FinalAnswer, uuid4=__import__('uuid').uuid4,
    )['RuleEngineAgent']


def test_rule_context_collection_does_not_drop_later_registered_rules():
    cls = rule_agent_class()
    agent = object.__new__(cls)
    agent.max_rules = 5
    rules = [{'rule_id': str(index), 'title': f'规则{index}', 'is_active': True} for index in range(8)]
    agent.engine = SimpleNamespace(list_rules=lambda: rules, get_rule_info=lambda identity: {'inputs': [], 'keywords': [f'场景{identity}']})
    contexts = agent._collect_rules()
    assert len(contexts) == 8
    assert contexts[-1]['keywords'] == ['场景7']


def test_query_matching_happens_before_five_candidate_limit():
    cls = rule_agent_class()
    agent = object.__new__(cls)
    agent.max_rules = 5
    agent._collect_rules = lambda: [
        {'rule_id': str(index), 'title': f'规则{index}', 'inputs': [], 'description': '', 'keywords': [f'场景{index}']}
        for index in range(8)
    ]
    planned = []

    async def plan(query, contexts):
        planned.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning=None)

    agent._plan_execution = plan
    asyncio.run(agent.compute('请计算场景7能提取多少元'))
    assert 1 <= len(planned) <= agent.max_rules
    assert planned[0]['rule_id'] == '7'
    assert {item['rule_id'] for item in planned} == {'7'}


def test_calculated_result_is_explained_as_an_estimate_not_approval():
    cls = rule_agent_class()
    text = cls._format_result({
        'status': 'CALCULATED', 'final_result': '750.00',
        'policy_source': {'title': '2026年政策'},
    }, {'price': 5000})
    assert '测算' in text
    assert '审核' in text
    assert '判断您符合' not in text
    assert '750.00' in text


@pytest.mark.parametrize('query,rule_id', [
    ('2026年买冰箱补贴多少', 'Rule_National_Appliance_2026'),
    ('2026年买手机补贴多少', 'Rule_National_Digital_2026'),
    ('2026年汽车报废更新补贴', 'Rule_National_AutoScrap_2026'),
    ('2026年汽车置换更新补贴', 'Rule_National_AutoReplace_2026'),
    ('常州装修住房公积金能提多少', 'Rule_Changzhou_Renovation_2026'),
    ('常州新房工薪购房资助怎么计算', 'Rule_Changzhou_NewHome_2026'),
    ('常州物业费公积金提取额度', 'Rule_Changzhou_PropertyFee_2026'),
    ('常州二手房购房资助怎么计算', 'Rule_Changzhou_ExistingHome_2026'),
])
def test_each_real_2026_rule_can_reach_the_bounded_planner(query, rule_id):
    cls = rule_agent_class()
    agent = object.__new__(cls)
    agent.engine = PolicyEngine(str(ROOT / 'rules'))
    agent.max_rules = 5
    planned = []

    async def plan(query, contexts):
        planned.extend(contexts)
        return SimpleNamespace(rule_id=None, inputs={}, reasoning=None)

    agent._plan_execution = plan
    asyncio.run(agent.compute(query))
    assert 1 <= len(planned) <= agent.max_rules
    assert planned[0]['rule_id'] == rule_id
    assert all(any(keyword.casefold() in query.casefold() for keyword in item['keywords']) for item in planned)


def test_unmatched_query_does_not_call_planner_or_execute_an_unrelated_rule():
    agent = object.__new__(rule_agent_class())
    agent.engine = PolicyEngine(str(ROOT / 'rules'))
    agent.max_rules = 5
    agent._plan_execution = AsyncMock(side_effect=AssertionError('No matching rule can enter the planner'))
    agent.engine.execute = Mock(side_effect=AssertionError('An unrelated rule must not execute'))

    answer = asyncio.run(agent.compute('常州一次性营养补助现在多少钱？'))

    agent._plan_execution.assert_not_awaited()
    agent.engine.execute.assert_not_called()
    assert answer.verification_passed is False
    assert answer.metadata.get('rule_id') is None
    assert 'engine_result' not in answer.metadata
    assert '没有命中本事项的计算规则' in answer.metadata['reason']


def test_saved_list_distinguishes_calculations_from_the_same_policy():
    engine = PolicyEngine(rule_dir=None)
    engine.rules = {
        'appliance': {'rule_id': 'appliance', 'name': '2026年家电补贴测算', 'policy_source': {'title': '同一份官方通知'}},
        'digital': {'rule_id': 'digital', 'name': '2026年数码补贴测算', 'policy_source': {'title': '同一份官方通知'}},
    }
    assert [row['title'] for row in engine.list_rules()] == ['2026年家电补贴测算', '2026年数码补贴测算']


@pytest.mark.parametrize('rule_id', RULE_IDS)
def test_new_saved_rule_and_draft_return_the_same_source_backed_calculation(rule_id):
    path = ROOT / 'rules' / f'{rule_id}.yaml'
    assert path.is_file(), f'Missing 2026 calculator: {rule_id}'
    raw = path.read_text(encoding='utf-8')
    rule = yaml.safe_load(raw)
    assert rule['rule_id'] == rule_id
    assert rule['policy_source']['url'].startswith('https://')
    assert rule['policy_source']['clause']
    assert (ROOT / rule['policy_source']['source_path']).is_file()
    for spec in rule['inputs']:
        assert spec['label'] and spec['description']
        assert spec.get('default') is not True, 'Eligibility cannot be pre-confirmed'
        if 'options' in spec:
            assert all('label' in option and 'value' in option for option in spec['options'])
    inputs = rule['example_inputs']
    engine = PolicyEngine(str(ROOT / 'rules'))
    result = engine.execute(rule_id, inputs)
    assert result['status'] == 'CALCULATED', result
    assert float(result['final_result']) == rule['example_expected']['amount']
    assert result['policy_source'] == rule['policy_source']
    assert result['explainability_trace']
    application = FastAPI()
    application.include_router(router, prefix='/api/dsl')
    with TestClient(application) as client:
        response = client.post('/api/dsl/preview', json={'yaml_content': raw, 'inputs': inputs})
    assert response.status_code == 200
    assert response.json()['result'] == result

@pytest.mark.parametrize('query,expected',[
    ('常州装修公积金政策','常州'),
    ('江苏省有哪些住房政策','江苏'),
    ('常州市新北区住房政策','新北'),
    ('天宁区物业费提取','天宁'),
    ('钟楼区购房资助','钟楼'),
    ('武进区住房政策','武进'),
    ('金坛区住房政策','金坛'),
    ('溧阳市住房政策','溧阳'),
    ('常州经开区住房政策','常州经开区'),
    ('济南市住房政策','济南'),
    ('青岛市补贴政策','青岛'),
])
def test_local_region_context_keeps_cross_region_recognition(query,expected):
    from app.agents.domain.policy_domain import PolicyDomainContextBuilder
    assert PolicyDomainContextBuilder().build(query).region == expected


def test_document_loader_identifies_changzhou_without_losing_other_regions():
    cls=load_subject_definitions('app/knowledge/document_loader.py','DocumentLoader')['DocumentLoader']
    assert '常州' in cls._extract_regions('常州市住房公积金管理中心发布本通知')
    assert '江苏省' in cls._extract_regions('江苏省住房政策')
    assert '山东省' in cls._extract_regions('山东省住房政策')
    assert cls._infer_source(Path('changzhou_20261121/housing/01.md')) == '常州市政府'
    assert cls._infer_source(Path('江苏/政策.md')) == '江苏省政府'


@pytest.mark.parametrize('text,expected',[('常州市装修政策','常州'),('金坛区住房政策','常州'),('溧阳市公积金政策','溧阳'),('济南市政策','济南')])
def test_dsl_city_extraction_preserves_explicit_regions(text,expected):
    cls=load_subject_definitions('app/agents/dsl_generator/dsl_extractor.py','DSLExtractor')['DSLExtractor']
    assert cls._extract_city(text)==expected
