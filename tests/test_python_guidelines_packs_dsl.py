"""Offline contracts for DSL execution and policy agent boundaries."""

import asyncio
import json
import logging
import importlib
import sys
import threading
from typing import Any
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from app.agents.dsl_generator.dsl_extractor import DSLExtractor
from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.dsl_generator_domain import DomainDrivenDSLGenerator
import app.agents.dsl_generator.subsidy_calculations as subsidy_calculations
from app.agents.dsl_generator.pipeline import DSLPipeline
from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.agents.dsl_generator.template_registry import TemplateRegistry
from app.models.policy import GeneratedAnswer
from test_python_guidelines_tooling import load_definitions


def test_pipeline_validation_failure_does_not_save_or_report_success(monkeypatch):
    pipeline = object.__new__(DSLPipeline)
    monkeypatch.setattr(pipeline, 'parser', SimpleNamespace(parse=lambda path: 'text', preprocess_text=lambda text: {'metadata': {}}), raising=False)
    monkeypatch.setattr(pipeline, 'extractor', SimpleNamespace(extract=lambda *args: {}, validate_dsl=lambda data: ['missing output']), raising=False)
    pipeline.use_project_config = False
    monkeypatch.setattr(pipeline, 'generator', SimpleNamespace(generate=lambda *args, **kwargs: 'invalid',
                                         save=lambda *args: pytest.fail('invalid DSL saved')), raising=False)
    result = pipeline.process_document('policy.txt')
    assert result['status'] == 'error'
    assert result['dsl_file'] is None


@pytest.mark.parametrize('filename', ['../outside.yaml', 'nested/outside.yaml'])
def test_dsl_save_rejects_paths_outside_output_directory(tmp_path, filename):
    generator = DSLGenerator(str(tmp_path))
    with pytest.raises(ValueError):
        generator.save('rule_id: r\ninputs: []\noutput: {}', filename)


def test_generic_dsl_preserves_quoted_values_expressions_and_empty_inputs(tmp_path):
    generator = DSLGenerator(str(tmp_path))
    data = {
        "rule_id": "Rule: 'quoted'", "policy_source": {"title": "居民的'旧车': #补贴"},
        "inputs": [], "calc": {"value": '"double: #" if True else \'single\''},
        "output": {"status": "QUALIFIED", "final_result": "{{ calc.value }}"},
    }
    rule = yaml.safe_load(generator.generate(data))
    assert rule["rule_id"] == data["rule_id"]
    assert rule["policy_source"]["title"] == data["policy_source"]["title"]
    assert rule["inputs"] == []
    assert rule["calc"] == data["calc"]
    assert rule["output"] == data["output"]


def test_external_template_roundtrip_preserves_quotes_newlines_and_optional_limits(tmp_path):
    from test_python_guidelines_tooling import ROOT

    marker = 'Policy: "quoted"\nsecond line'
    data = {
        "rule_id": marker, "name": "Policy: 'quoted'", "version": marker,
        "policy_source": {"title": "Title: 'quoted'", "clause": 'Clause: "quoted"'},
        "efficiency_rates": {"base_rate": 0.15}, "per_item_cap": 2000,
        "category_limits": {"per_category": {marker: 1}},
    }
    generator = DSLGenerator(str(tmp_path), str(ROOT / "templates"))
    rule = yaml.safe_load(generator.generate(data, template_name="appliance_subsidy.yaml.j2"))
    assert rule["rule_id"] == rule["version"] == marker
    assert rule["name"] == data["name"]
    assert rule["policy_source"]["clause"] == data["policy_source"]["clause"]
    assert rule["category_limits"] == {"per_category": {marker: 1}, "total_items": None}


@pytest.mark.parametrize("discount_type,discount", [("AMOUNT", 10), ("PERCENT", 0.1)])
def test_coupon_schema_accepts_executor_discount_types(discount_type, discount):
    from app.domains.schemas import ConsumerCouponSchema, CouponDiscountType

    model = ConsumerCouponSchema.model_validate({
        "rule_id": "Rule_Jinan_Coupon_2030", "name": "Coupon", "policy_source": {}, "valid_period": {},
        "coupon_types": [discount_type],
        "tiers": [{"type": discount_type, "threshold": 100, "discount": discount}],
        "distribution": {}, "usage_limits": {"merchant_types": ["retail", "dining"]}, "output": {},
    })
    assert model.coupon_types == [CouponDiscountType(discount_type)]
    assert model.tiers[0].type == CouponDiscountType(discount_type)
    assert model.usage_limits["merchant_types"] == ["retail", "dining"]


def test_dsl_save_accepts_the_minimal_executable_engine_contract(tmp_path):
    rule = {"rule_id": "minimal", "output": {"status": "QUALIFIED", "final_result": "0"}}
    path = DSLGenerator(str(tmp_path)).save(yaml.safe_dump(rule))
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == rule
    assert PolicyEngine(str(tmp_path)).execute("minimal", {})["final_result"] == "0"


@pytest.mark.parametrize("output", [{}, {"status": "QUALIFIED"}, {"status": "QUALIFIED", "final_result": 0}])
def test_dsl_save_rejects_invalid_outputs_before_writing(tmp_path, output):
    generator = DSLGenerator(str(tmp_path))
    with pytest.raises(ValueError, match="output"):
        generator.save(yaml.safe_dump({"rule_id": "invalid", "output": output}))
    assert list(tmp_path.iterdir()) == []


def test_dsl_atomic_write_preserves_existing_file_when_replace_fails(tmp_path, monkeypatch):
    from unittest.mock import Mock

    module = importlib.import_module("app.agents.dsl_generator.dsl_generator")
    path = tmp_path / "rule.yaml"
    path.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(module.os, "replace", Mock(side_effect=OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        module.atomic_write_text(path, "replacement")
    assert path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [path]


def test_dsl_atomic_write_rejects_symlinks_without_changing_their_target(tmp_path):
    from app.agents.dsl_generator.dsl_generator import atomic_write_text

    target = tmp_path / "target.yaml"
    target.write_text("previous", encoding="utf-8")
    link = tmp_path / "link.yaml"
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) != 1314:
            raise
        pytest.skip("Windows symbolic links require developer mode or elevated privilege")
    with pytest.raises(ValueError, match="symbolic link"):
        atomic_write_text(link, "replacement")
    assert target.read_text(encoding="utf-8") == "previous"
    assert link.is_symlink()


def test_invalid_generated_yaml_is_a_visible_failure(tmp_path, monkeypatch):
    generator = DSLGenerator(str(tmp_path))
    monkeypatch.setattr(generator, '_render_template', lambda template, data: 'not: [valid')
    with pytest.raises(ValueError, match='YAML'):
        generator.generate({'rule_id': 'r'})


def test_rule_load_failure_is_not_silently_ignored(tmp_path):
    (tmp_path / 'broken.yaml').write_text('not: [valid', encoding='utf-8')
    with pytest.raises(yaml.YAMLError):
        PolicyEngine(str(tmp_path))


def test_offline_extraction_uses_policy_text_instead_of_prompt_instructions(monkeypatch):
    extractor = DSLExtractor(use_project_config=False)
    seen = []
    def extract(text):
        seen.append(text)
        return '{"rule_id":"r"}'

    monkeypatch.setattr(extractor, '_extract_with_rules', extract)
    extractor.extract('plain policy')
    assert seen == ['plain policy']


def test_graph_document_failure_is_visible():
    async def fail(text):
        raise OSError('insert failed')

    ns = load_definitions('app/agents/packs/graph_retriever/node.py', {'GraphRetrieverAgent'},
                          StatefulAgent=object, asyncio=asyncio)
    agent = object.__new__(ns['GraphRetrieverAgent'])
    agent._initialized = True
    agent._rag = SimpleNamespace(ainsert=fail)
    agent.logger = logging.getLogger('test')
    with pytest.raises(OSError, match='insert failed'):
        asyncio.run(agent.add_documents([SimpleNamespace(title='t', content='body')]))


def test_vector_embedding_count_mismatch_cannot_mutate_index():
    import numpy as np
    ns = load_definitions('app/agents/packs/vector_retriever/node.py', {'VectorRetrieverAgent'},
                          StatefulAgent=object, asyncio=asyncio, np=np)
    agent = object.__new__(ns['VectorRetrieverAgent'])
    agent.logger = logging.getLogger('test')

    async def embed(texts):
        return np.array([[1, 0]], dtype=np.float32)

    agent._embed_texts = embed
    agent.vector_index = SimpleNamespace(add=lambda vectors: pytest.fail('mismatch mutated index'))
    docs = [SimpleNamespace(title='t', content='b', keywords=[]) for _ in range(2)]
    with pytest.raises(ValueError, match='count'):
        asyncio.run(agent.add_documents(docs))


@pytest.mark.parametrize("template,data,inputs,expected", [
    ("appliance_subsidy.yaml.j2", {"efficiency_rates": {"base_rate": 0.15}, "per_item_cap": 2000}, {"price": 1000, "energy_level": 2, "category": "空调"}, 150),
    ("auto_subsidy.yaml.j2", {"matching": {"tiers": [{"powertrain": "NEV", "min_ex_tax": 0, "max_ex_tax": 10000, "subsidy": 200}]}}, {"invoice_no_tax": 1000, "vehicle_type": "NEV", "purchase_time": "2030-01-01", "claim_time": "2030-01-01", "buyer_id": "u", "vin": "v", "invoice_no": "i"}, 200),
    ("consumer_coupon.yaml.j2", {"tiers": [{"type": "AMOUNT", "threshold": 100, "discount": 20}]}, {"consumption_amount": 150, "coupon_type": "AMOUNT", "claim_time": "2030-01-01", "user_id": "u"}, 20),
])
def test_real_templates_render_and_execute_offline(tmp_path, template, data, inputs, expected):
    from test_python_guidelines_tooling import ROOT

    generator = DSLGenerator(str(tmp_path), str(ROOT / "templates"))
    period = {"start": "2025-01-01", "end": "2035-01-01"}
    data.update({"rule_id": "integration", "valid_period": period,
                 "windows": {name: dict(period) for name in ("purchase_window", "claim_window", "modify_window")}})
    rule = yaml.safe_load(generator.generate(data, template_name=template))
    engine = PolicyEngine(str(tmp_path))
    engine.rules["integration"] = rule
    result = engine.execute("integration", inputs)
    assert result["status"] == "QUALIFIED", result
    assert float(result["final_result"]) == expected


@pytest.mark.parametrize("module_name,class_name", [
    ("question_builder", "QuestionUnderstander"),
    ("policy_review", "PolicyReviewAgent"),
    ("policy_retriever", "PolicyRetriever"),
])
def test_legacy_pack_uses_injected_async_client_without_owning_it(module_name, class_name):
    class Client:
        async def create(self, messages):
            assert messages[0].type == "SystemMessage"
            assert messages[1].type == "UserMessage"
            await asyncio.sleep(0)
            return SimpleNamespace(content='{"intent":"policy","entities":[],"keywords":[],"policy_types":[]}')

        async def close(self):
            raise AssertionError("injected client belongs to its caller")

    module = importlib.import_module(f"app.agents.packs.{module_name}.node")
    agent = getattr(module, class_name)("test", {}, model_client=Client())

    async def run():
        response = await agent._request_completion([{"role": "system", "content": "system"}, {"role": "user", "content": "question"}])
        assert json.loads(response)["intent"] == "policy"
        await agent.close()

    asyncio.run(run())


def test_legacy_retrieval_uses_store_text_search_once_and_reports_missing_store():
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    calls = []

    class Store:
        def search(self, query, **kwargs):
            calls.append(query)
            assert query == "补贴政策"
            return [], []

    agent = PolicyRetriever("test", {}, vector_store=Store(), model_client=object())
    result = asyncio.run(agent.process_message(json.dumps({"query": "补贴政策"})))
    assert result["success"] is True
    assert calls == ["补贴政策"]
    agent.vector_store = None
    result = asyncio.run(agent.process_message(json.dumps({"query": "补贴政策"})))
    assert result["success"] is False
    assert "vector_store" in result["error"]


def test_zero_values_survive_template_normalization(tmp_path):
    registry = TemplateRegistry()
    appliance = registry._prepare_appliance_payload({"per_item_cap": 0, "efficiency_rates": {"base_rate": 0}})
    auto = registry._prepare_auto_payload({"tiers": [{"powertrain": "NEV", "range": [0, None], "subsidy": 0, "package": 100}]})
    coupon = registry._prepare_coupon_payload({"tiers": [{"type": "AMOUNT", "threshold": 0, "amount": 0, "value": 10}], "usage_limits": {"valid_days": 0}})
    assert appliance["per_item_cap"] == 0
    assert auto["matching"]["tiers"][0]["subsidy"] == 0
    assert coupon["tiers"][0]["discount"] == 0
    assert coupon["usage_limits"]["valid_days"] == 0
    assert DSLPipeline._value_for_tier("threshold_value", "float", {"threshold": 0}) == 0


def test_zero_no_label_rate_does_not_receive_base_subsidy():
    result = subsidy_calculations.appliance_subsidy({"price": 1000}, {"base_rate": 0.15, "no_label_rate": 0})
    assert result["rate"] == 0
    assert result["final_subsidy"] == 0


@pytest.mark.parametrize("callback", ["is_merchant_allowed", "is_product_allowed", "is_time_allowed", "used_quota_by_user", "available_quota_at", "used_quota_total"])
def test_coupon_check_failure_cannot_qualify(callback):
    def fail(*args):
        raise RuntimeError("eligibility store unavailable")

    context = {"available_quota_at": lambda *args: 100, "used_quota_total": lambda: 0, callback: fail}
    with pytest.raises(RuntimeError, match="store unavailable"):
        subsidy_calculations.consumer_coupon(
            {"consumption_amount": 100, "coupon_type": "AMOUNT", "claim_time": "2025-01-01", "user_id": "u"},
            tiers=[{"type": "AMOUNT", "threshold": 0, "discount": 10}],
            distribution={"total_quota": 100, "quota_per_person": 1},
            usage_limits={"time_restrictions": ["morning"]}, coupon_types=["AMOUNT"], context=context,
        )


@pytest.mark.parametrize("callback", ["is_duplicate", "claimed_count_by_buyer", "classify_powertrain", "budget_remaining"])
def test_auto_check_failure_cannot_qualify(callback):
    def fail(*args):
        raise RuntimeError("eligibility store unavailable")

    with pytest.raises(RuntimeError, match="store unavailable"):
        subsidy_calculations.auto_subsidy(
            {"invoice_no_tax": 100, "vehicle_type": None if callback == "classify_powertrain" else "NEV", "purchase_time": "2025-01-01", "claim_time": "2025-01-01", "buyer_id": "u"},
            limits={"dedupe_keys": ["buyer_id"], "per_person_max_cars": 1},
            matching={"tiers": [{"powertrain": "NEV", "min_ex_tax": 0, "max_ex_tax": None, "subsidy": 10}]},
            budget={"allocation": "global"}, context={callback: fail},
        )


@pytest.mark.parametrize("expression", ["1 / 0", "inputs['missing']", "__import__('os').getcwd()", "inputs.__class__", "(lambda: 1)()"])
def test_rule_failure_returns_error_instead_of_qualified(tmp_path, expression):
    engine = PolicyEngine(str(tmp_path))
    engine.rules["test"] = {"rule_id": "test", "calc": {"value": expression}, "output": {"status": "QUALIFIED", "final_result": "{{ calc.value }}"}}
    assert engine.execute("test", {})["status"] == "ERROR"


def test_rule_keeps_arithmetic_boolean_and_helper_contracts(tmp_path):
    engine = PolicyEngine(str(tmp_path))
    assert engine._eval_expression("min(inputs['price'] * 0.2, 50) if inputs.get('enabled', False) and inputs['price'] >= 0 else 0", {"inputs": {"price": 100, "enabled": True}}) == 20
    engine.rules["test"] = {"rule_id": "test", "inputs": [{"name": "price", "type": "float", "required": True}], "calc": {"result": "dsl_helpers.appliance_subsidy(inputs, efficiency_rates, per_item_cap, category_limits, rule.get('special_rules', {}), user_state)"}, "efficiency_rates": {"base_rate": 0.15}, "output": {"status": "{{ calc.result.status }}", "final_result": "{{ calc.result.final_subsidy }}"}}
    assert engine.execute("test", {"price": 100, "energy_level": 2})["final_result"] == "15.0"
    assert engine.execute("test", {"price": None})["status"] == "INVALID_INPUT"
    engine.rules["test"]["valid_period"] = {"start": "invalid"}
    assert engine.execute("test", {"price": 1})["status"] == "ERROR"


def test_template_failure_is_not_a_successful_literal(tmp_path):
    engine = PolicyEngine(str(tmp_path))
    engine.rules["test"] = {"rule_id": "test", "output": {"status": "QUALIFIED", "final_result": "{{ missing.amount }}"}}
    assert engine.execute("test", {})["status"] == "ERROR"


def test_extractors_reject_non_object_or_invalid_json():
    extractor = DSLExtractor(use_project_config=False)
    with pytest.raises(ValueError):
        extractor._parse_response("not json", "家电")
    domain = object.__new__(DomainDrivenDSLGenerator)
    with pytest.raises(ValueError):
        domain._parse_json_response("[]")


@pytest.mark.parametrize("response", ["{'name': 'policy'}", '{"name": "policy",}'])
def test_domain_json_parser_rejects_repaired_quotes_or_trailing_commas(response):
    with pytest.raises(ValueError):
        DomainDrivenDSLGenerator._parse_json_response(response)


@pytest.mark.parametrize("fenced", [False, True])
def test_domain_json_parser_preserves_apostrophes_in_valid_values(fenced):
    value = {"name": "O'Brien's policy"}
    response = json.dumps(value)
    if fenced:
        response = f"```json\n{response}\n```"
    assert DomainDrivenDSLGenerator._parse_json_response(response) == value


@pytest.mark.parametrize("text,expected", [
    ("济南市汽车消费补贴", "auto"), ("购车消费券", "auto"),
    ("家电消费补贴", "appliance"), ("商场消费券", "coupon"),
])
def test_policy_type_detection_keeps_specific_vehicle_signals(text, expected):
    assert DSLExtractor._detect_policy_type(text) == expected


def test_domain_time_repair_preserves_city_and_only_normalizes_exact_midnight():
    data = {"rule_id": "Rule_Jinan_Auto_2030", "time_windows": [{
        "start": "2030-01-01T24:00:00+08:00", "end": "2030-01-01T24:00:30+08:00",
    }]}
    fixed = DomainDrivenDSLGenerator._fix_common_issues(data, "汽车补贴")
    assert fixed["rule_id"] == "Rule_Jinan_Car_2030"
    assert fixed["time_windows"][0]["start"] == "2030-01-02 00:00:00+08:00"
    assert fixed["time_windows"][0]["end"] == data["time_windows"][0]["end"]
    assert data["time_windows"][0]["start"] == "2030-01-01T24:00:00+08:00"


def test_document_table_extraction_preserves_an_empty_middle_column():
    from app.agents.dsl_generator.document_parser import DocumentParser

    tables = DocumentParser.extract_tables("| 类别 | 条件 | 金额 |\n| 汽车 | | 100 |")
    assert tables == [[["类别", "条件", "金额"], ["汽车", "", "100"]]]


@pytest.mark.parametrize("invoice,interval,expected", [
    (0, "[min, max]", "QUALIFIED"), (100, "[min, max]", "QUALIFIED"),
    (100, "[min, max)", "NOT_QUALIFIED"),
])
def test_vehicle_tiers_preserve_described_interval_boundaries(invoice, interval, expected):
    tier = {"powertrain": "NEV", "min_ex_tax": None, "max_ex_tax": 100,
            "subsidy": 10, "open_interval": interval}
    prepared = TemplateRegistry._prepare_auto_payload({"tiers": [tier]})
    for matching in ({"tiers": [tier]}, prepared["matching"]):
        result = subsidy_calculations.auto_subsidy({
            "invoice_no_tax": invoice, "vehicle_type": "NEV",
            "purchase_time": "2030-01-01", "claim_time": "2030-01-01",
        }, matching=matching)
        assert result["status"] == expected


@pytest.mark.parametrize("value", ["unknown", "", 2, float("nan")])
def test_policy_boolean_parser_rejects_unknown_values(value):
    with pytest.raises(ValueError):
        subsidy_calculations._parse_policy_bool(value)


@pytest.mark.parametrize("value", [False, 0, "false", "0"])
def test_policy_boolean_parser_preserves_explicit_false(value):
    assert subsidy_calculations._parse_policy_bool(value) is False


@pytest.mark.parametrize("kind,value,expected", [
    ("float", True, "INVALID_INPUT"), ("float", float("nan"), "INVALID_INPUT"),
    ("float", float("inf"), "INVALID_INPUT"), ("integer", True, "INVALID_INPUT"),
    ("integer", 1.5, "INVALID_INPUT"), ("integer", float("inf"), "INVALID_INPUT"),
    ("float", 0, "QUALIFIED"), ("integer", "0", "QUALIFIED"),
])
def test_rule_numeric_inputs_preserve_zero_and_reject_invalid_values(tmp_path, kind, value, expected):
    engine = PolicyEngine(str(tmp_path))
    engine.rules["numbers"] = {"rule_id": "numbers", "inputs": [{"name": "value", "type": kind}],
                               "output": {"status": "QUALIFIED", "final_result": "{{ inputs.value }}"}}
    result = engine.execute("numbers", {"value": value})
    assert result["status"] == expected
    if expected == "QUALIFIED":
        assert float(result["final_result"]) == 0


def test_generator_preserves_input_and_zero_upper_bound(tmp_path):
    generator = DSLGenerator(str(tmp_path))
    data: dict[str, Any] = {"rule_id": "zero", "policy_source": {"title": "  Original  "}, "inputs": [{"name": "price"}], "tiers": [{"range": [-1, 0]}], "output": {"status": "QUALIFIED", "final_result": "0"}}
    rendered = generator.generate(data)
    assert "range: [-1, 0]" in rendered
    assert data["policy_source"]["title"] == "  Original  "
    assert data["inputs"] == [{"name": "price"}]


def test_comparator_includes_required_comparison_type():
    from app.agents.packs.policy_comparator.node import PolicyComparison

    namespace = load_definitions("app/agents/packs/policy_comparator/node.py", {"PolicyComparatorAgent"}, PolicyAgentBase=object, PolicyComparison=PolicyComparison, defaultdict=__import__("collections").defaultdict)
    agent = object.__new__(namespace["PolicyComparatorAgent"])
    agent.comparison_dimensions = {}
    docs = [SimpleNamespace(id=uuid4(), title="one"), SimpleNamespace(id=uuid4(), title="two")]
    result = agent._compare_policies(docs, uuid4(), "all")
    assert result.comparison_type == "all"


def test_answer_quality_uses_declared_weights_and_memory_protocol():
    namespace = load_definitions("app/agents/packs/answer_generator/node.py", {"AnswerGeneratorAgent"}, StatefulAgent=object, QueryIntent=SimpleNamespace(GENERAL_INQUIRY="general"), json=json)
    agent = object.__new__(namespace["AnswerGeneratorAgent"])
    agent.quality_criteria = {"completeness": 0.3, "accuracy": 0.3, "clarity": 0.2, "practicality": 0.2}
    answer = GeneratedAnswer(query_id=uuid4(), answer="## 建议" + "a" * 500, sources=[], confidence=1, evidence=["one", "two", "three"], assumptions=[], limitations=[], followup_questions=[])
    assert agent._validate_answer_quality(answer) == 1


def test_unsupported_embedding_backend_is_visible():
    import numpy as np
    namespace = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object, np=np)
    agent = object.__new__(namespace["VectorRetrieverAgent"])
    agent.embedding_backend = "typo"
    agent.embedding_dim = 2
    agent.logger = logging.getLogger(__name__)
    with pytest.raises(ValueError, match="backend"):
        asyncio.run(agent._embed_texts(["text"]))


def test_vector_dimension_change_preserves_existing_index():
    import numpy as np
    import faiss

    namespace = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object, np=np, faiss=faiss)
    agent = object.__new__(namespace["VectorRetrieverAgent"])
    agent.vector_index = faiss.IndexFlatIP(2)
    agent.vector_index.add(np.array([[1, 0]], dtype=np.float32))
    with pytest.raises(ValueError, match="dimension"):
        agent._prepare_embeddings(np.array([[1, 0, 0]], dtype=np.float32))
    assert agent.vector_index.ntotal == 1


def test_vector_embedding_awaits_request_and_closes_client_on_dimension_failure(monkeypatch):
    import numpy as np
    import faiss
    import openai

    closed = []

    class Client:
        def __init__(self, **kwargs):
            self.embeddings = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def create(self, **kwargs):
            await asyncio.sleep(0)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1, 0, 0])])

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    namespace = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object, np=np, faiss=faiss, os=__import__("os"), AsyncOpenAI=Client)
    agent = object.__new__(namespace["VectorRetrieverAgent"])
    agent.model_name = "test"
    agent.vector_index = faiss.IndexFlatIP(2)
    agent.vector_index.add(np.array([[1, 0]], dtype=np.float32))
    with pytest.raises(ValueError, match="dimension"):
        asyncio.run(agent._embed_openai(["text"]))
    assert closed == [True]
    assert agent.vector_index.ntotal == 1


def test_empty_vector_search_does_not_call_faiss_with_zero_k():
    import numpy as np
    namespace = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"}, StatefulAgent=object, time=__import__("time"), np=np)
    agent = object.__new__(namespace["VectorRetrieverAgent"])
    agent.vector_index = SimpleNamespace(ntotal=0)
    result = asyncio.run(agent._search_similar([0, 1]))
    assert result["documents"] == []
    assert result["scores"] == []


@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("first_content", ["first", ""])
def test_vector_reranker_uses_real_service_contract_and_always_closes(monkeypatch, failed, first_content):
    calls = []

    class Reranker:
        def __init__(self):
            calls.append(("create", threading.get_ident()))

        def rerank(self, query, texts, top_n):
            assert query == "query" and texts == [first_content, "second"] and top_n == 2
            if failed:
                raise OSError("rerank unavailable")
            return [(1, .9, "second"), (0, .2, "first")]

        def close(self):
            calls.append(("close", threading.get_ident()))

    monkeypatch.setitem(sys.modules, "app.knowledge.rerank", SimpleNamespace(Reranker=Reranker))
    monkeypatch.setenv("KB_RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANKER_BACKEND", "dashscope")
    monkeypatch.setenv("RERANKER_STRATEGY", "replace")
    monkeypatch.setenv("RERANKER_TOP_N", "2")
    namespace = load_definitions("app/agents/packs/vector_retriever/node.py", {"VectorRetrieverAgent"},
                                 StatefulAgent=object, asyncio=asyncio, os=__import__("os"), Reranker=Reranker)
    agent = object.__new__(namespace["VectorRetrieverAgent"])
    agent.logger = logging.getLogger(__name__)
    results = {"documents": [{"content": first_content, "title": "first title"}, {"content": "second", "title": "second title"}], "scores": [.8, .4]}
    result = asyncio.run(agent._maybe_rerank("query", results))
    assert result["documents"][0]["content"] == (first_content if failed else "second")
    assert result["scores"] == ([.8, .4] if failed else [.9, .2])
    assert [name for name, _ in calls] == ["create", "close"]
    assert all(thread_id != threading.get_ident() for _, thread_id in calls)


def test_graph_storage_close_failure_still_releases_owned_reranker():
    closed = []

    async def fail_close():
        raise OSError("storage close failed")

    namespace = load_definitions("app/agents/packs/graph_retriever/node.py", {"GraphRetrieverAgent"},
                                 StatefulAgent=object, asyncio=asyncio)
    agent = object.__new__(namespace["GraphRetrieverAgent"])
    agent._rag = SimpleNamespace(finalize_storages=fail_close)
    agent._initialized = True
    agent._reranker = SimpleNamespace(close=lambda: closed.append(True))
    with pytest.raises(OSError, match="storage close failed"):
        asyncio.run(agent.close())
    asyncio.run(agent.close())
    assert closed == [True]
    assert agent._rag is None and agent._reranker is None
    assert agent._initialized is False


@pytest.mark.parametrize("query,value", [("申请材料", "document_requirement"), ("联系电话", "contact_info"), ("查询进度", "status_inquiry")])
def test_query_analyzer_declared_intents_match_keyword_mapping(query, value):
    from app.models.policy import AgentType, PolicyType, QueryIntent

    class Base:
        def __init__(self, **kwargs):
            pass

    namespace = load_definitions("app/agents/packs/query_analyzer/node.py", {"QueryAnalyzerAgent"},
                                 PolicyAgentBase=Base, AgentType=AgentType, QueryIntent=QueryIntent,
                                 PolicyType=PolicyType)
    agent = namespace["QueryAnalyzerAgent"]()
    assert agent._identify_intent(query).value == value


def test_extractor_does_not_invent_financial_terms():
    extractor = DSLExtractor(use_project_config=False)
    with pytest.raises(ValueError, match='efficiency_rates|per_item_cap'):
        extractor._parse_response('{}', '家电补贴政策')


def test_template_merge_requires_policy_rate_and_cap():
    registry = TemplateRegistry()
    profile = registry.get_profile_by_template('appliance_subsidy.yaml.j2')
    for payload in [{}, {'efficiency_rates': {'base_rate': .15}}]:
        with pytest.raises(ValueError, match='efficiency_rates|per_item_cap'):
            registry.apply_defaults(payload, profile)


def test_boolean_rule_input_does_not_treat_unknown_text_as_false(tmp_path):
    engine = PolicyEngine(str(tmp_path))
    rule = {'rule_id': 'bool', 'inputs': [{'name': 'enabled', 'type': 'boolean'}],
            'output': {'status': 'QUALIFIED', 'final_result': '{{ inputs.enabled }}'}}
    engine.rules['bool'] = rule
    assert engine.execute('bool', {'enabled': 'maybe'})['status'] == 'INVALID_INPUT'
    assert engine.execute('bool', {'enabled': False})['status'] == 'QUALIFIED'


def test_cli_json_inputs_require_an_object():
    from app.agents.dsl_generator.main import _load_inputs
    with pytest.raises(ValueError, match='object'):
        _load_inputs('[]')


def test_question_analysis_missing_fields_uses_explicit_rule_fallback():
    ns = load_definitions('app/agents/packs/question_builder/node.py', {'QuestionUnderstander'}, json=json, re=__import__('re'))
    agent = object.__new__(ns['QuestionUnderstander'])
    agent.system_message = 'test'
    agent.logger = logging.getLogger('test')

    async def respond(messages):
        return '{}'

    agent._request_completion = respond
    result = asyncio.run(agent._analyze_question('家电补贴条件'))
    assert result['keywords'] and result['intent']


def test_policy_analysis_shared_assistant_serializes_requests():
    ns = load_definitions('app/agents/packs/policy_analysis/node.py', {'PolicyAnalyzerAgent'},
                          ReactiveAgent=object, asyncio=asyncio, json=json,
                          TextMessage=lambda **kwargs: kwargs, CancellationToken=lambda: None,
                          build_nlp_extraction_user_prompt=lambda *args: 'test')
    agent = object.__new__(ns['PolicyAnalyzerAgent'])
    agent.model_client = object()
    agent._assistant_lock = asyncio.Lock()
    active = 0
    peak = 0

    async def respond(*args):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(.01)
        active -= 1
        return SimpleNamespace(chat_message=SimpleNamespace(to_text=lambda: '["fact"]'))

    agent._assistant = SimpleNamespace(on_messages=respond)

    async def check():
        return await asyncio.gather(agent._extract_with_nlp('a', 'p'), agent._extract_with_nlp('b', 'p'))

    assert asyncio.run(check()) == [['fact'], ['fact']]
    assert peak == 1


@pytest.mark.parametrize('confidence', [None, 'bad', -1, 2])
def test_invalid_model_confidence_uses_rule_routing(confidence):
    ns = load_definitions('app/agents/packs/intent_router/node.py', {'IntentRouterAgent'},
                          PolicyAgentBase=object)
    agent = object.__new__(ns['IntentRouterAgent'])
    agent.logger = logging.getLogger('test')

    async def classify(text):
        return {'intent': 'policy_inquiry', 'confidence': confidence}

    async def rules(text):
        return {'intent_type': 'rule', 'confidence': .2}

    agent._llm_classifier = SimpleNamespace(classify=classify)
    agent._classify_intent = rules
    assert asyncio.run(agent._classify_intent_llm_first('q'))['intent_type'] == 'rule'


def test_router_model_failure_uses_explicit_rule_strategy():
    ns = load_definitions('app/agents/packs/intent_router/node.py', {'IntentRouterAgent'},
                          PolicyAgentBase=object)
    agent = object.__new__(ns['IntentRouterAgent'])
    agent.logger = logging.getLogger('test')

    async def classify(text):
        raise OSError('intent model unavailable')

    async def rules(text):
        return {'intent_type': 'rule', 'confidence': .2}

    agent._llm_classifier = SimpleNamespace(classify=classify)
    agent._classify_intent = rules
    assert asyncio.run(agent._classify_intent_llm_first('q'))['intent_type'] == 'rule'


@pytest.mark.parametrize('response', ['not json', '[]', '{}', '{"intent":null}', '{"intent":""}'])
def test_intent_classifier_rejects_malformed_model_result(response):
    from app.agents.packs.intent_router.utils import IntentPrediction

    ns = load_definitions('app/agents/packs/intent_router/utils.py', {'LLMIntentClassifier'},
                          asyncio=asyncio, IntentPrediction=IntentPrediction, AssistantAgent=object,
                          TextMessage=lambda **kwargs: kwargs, CancellationToken=object,
                          build_intent_user_prompt=lambda query: query, INTENT_SYSTEM_INSTRUCTION='classify',
                          logging_manager=SimpleNamespace(log_llm_stream_start=lambda **kwargs: None,
                                                          log_llm_stream_end=lambda **kwargs: None,
                                                          log_llm_call=lambda **kwargs: None))
    classifier = ns['LLMIntentClassifier'](model_client=object())

    async def respond(*args):
        return SimpleNamespace(chat_message=SimpleNamespace(to_text=lambda: response))

    classifier._assistant = SimpleNamespace(on_messages=respond)
    with pytest.raises(ValueError):
        asyncio.run(classifier.classify('query'))


def test_selected_document_parser_failure_is_visible(tmp_path, monkeypatch):
    from app.agents.dsl_generator.document_parser import DocumentParser

    document = tmp_path / 'policy.txt'
    document.write_text('built-in parser would succeed', encoding='utf-8')
    parser = DocumentParser(use_llama_index=True)

    def fail(path):
        raise OSError('selected parser failed')

    monkeypatch.setattr(parser, '_parse_with_llama_reader', fail)
    with pytest.raises(OSError, match='selected parser failed'):
        parser.parse(str(document))


def test_graph_reranker_configuration_failure_is_visible():
    def fail():
        raise ValueError('invalid reranker configuration')

    ns = load_definitions('app/agents/packs/graph_retriever/node.py', {'GraphRetrieverAgent'},
                          StatefulAgent=object, asyncio=asyncio, Reranker=fail)
    agent = object.__new__(ns['GraphRetrieverAgent'])
    agent.logger = logging.getLogger('test')
    with pytest.raises(ValueError, match='invalid reranker configuration'):
        agent._create_rerank_callback()


def test_answer_request_requires_sources_and_keeps_selected_model_failure_visible():
    ns = load_definitions('app/agents/packs/answer_generator/node.py', {'AnswerGeneratorAgent'},
                          StatefulAgent=object)
    agent = object.__new__(ns['AnswerGeneratorAgent'])
    agent.model_client = object()

    async def fail(*args):
        raise OSError('answer model failed')

    agent._generate_with_llm = fail
    with pytest.raises(KeyError, match='sources'):
        asyncio.run(agent.process_request({'query_context': {'intent': 'unknown'}}, object()))
    with pytest.raises(OSError, match='answer model failed'):
        asyncio.run(agent.process_request({'query_context': {'intent': 'unknown'}, 'sources': [], 'synthesis': {}}, object()))


@pytest.mark.parametrize(('model', 'configured_dimension', 'expected'), [
    ('text-embedding-3-large', 768, 3072),
    ('text-embedding-3-small', 768, 1536),
    ('custom-model', 768, 768),
])
def test_graph_embedding_dimension_uses_selected_model_contract(model, configured_dimension, expected):
    ns = load_definitions('app/agents/packs/graph_retriever/node.py', {'GraphRetrieverAgent'},
                          StatefulAgent=object,
                          settings=SimpleNamespace(embedding=SimpleNamespace(dimension=configured_dimension)))
    agent = object.__new__(ns['GraphRetrieverAgent'])
    agent.embedding_backend = 'openai'
    agent.embedding_model = model
    assert agent._infer_embedding_dim() == expected


@pytest.mark.parametrize('dimension', [0, -1])
def test_graph_custom_model_rejects_nonpositive_configured_dimension(dimension):
    ns = load_definitions('app/agents/packs/graph_retriever/node.py', {'GraphRetrieverAgent'},
                          StatefulAgent=object,
                          settings=SimpleNamespace(embedding=SimpleNamespace(dimension=dimension)))
    agent = object.__new__(ns['GraphRetrieverAgent'])
    agent.embedding_backend = 'openai'
    agent.embedding_model = 'custom-model'
    with pytest.raises(ValueError, match='dimension'):
        agent._infer_embedding_dim()



def test_vector_fusion_uses_real_zero_scores_and_unranked_documents(monkeypatch):
    class Reranker:
        def rerank(self, query, texts, top_n):
            assert texts == ['first', 'second'] and top_n == 1
            return [(1, .9, 'second')]

        def close(self):
            pass

    monkeypatch.setenv('KB_RERANK_ENABLED', 'true')
    monkeypatch.setenv('RERANKER_BACKEND', 'dashscope')
    monkeypatch.setenv('RERANKER_STRATEGY', 'fuse')
    monkeypatch.setenv('RERANKER_TOP_N', '1')
    monkeypatch.setenv('RERANK_WEIGHT', '0.7')
    monkeypatch.setenv('FAISS_WEIGHT', '0.3')
    ns = load_definitions('app/agents/packs/vector_retriever/node.py', {'VectorRetrieverAgent'},
                          StatefulAgent=object, asyncio=asyncio, os=__import__('os'), Reranker=Reranker)
    agent = object.__new__(ns['VectorRetrieverAgent'])
    agent.logger = logging.getLogger('test')
    results = {'documents': [{'content': 'first'}, {'content': 'second'}], 'scores': [0.0, .4]}
    result = asyncio.run(agent._maybe_rerank('query', results))
    assert [document['content'] for document in result['documents']] == ['second', 'first']
    assert result['scores'] == pytest.approx([.75, 0.0])


@pytest.mark.parametrize('change', [
    {'confidence': 2}, {'chains': 'kb_chain'},
    {'requires_parallel': 'false'}, {'intent': 'invented_intent'},
    {'sub_intent': ['benefit']},
])
def test_pack_intent_json_rejects_invalid_contract(monkeypatch, change):
    from app.agents.packs.intent_router import utils
    from unittest.mock import AsyncMock, Mock

    payload = {'intent': 'policy_inquiry', 'sub_intent': 'benefit',
               'confidence': 0.8, 'chains': ['kb_chain'], 'requires_parallel': False}
    payload.update(change)
    classifier = utils.LLMIntentClassifier(model_client=object())
    classifier._assistant = SimpleNamespace(on_messages=AsyncMock(return_value=SimpleNamespace(
        chat_message=SimpleNamespace(to_text=lambda: json.dumps(payload)))))
    monkeypatch.setattr(utils, 'logging_manager', Mock())
    with pytest.raises(ValueError):
        asyncio.run(classifier.classify('补贴'))


def test_pack_intent_json_preserves_zero_and_false(monkeypatch):
    from app.agents.packs.intent_router import utils
    from unittest.mock import AsyncMock, Mock

    payload: dict[str, object] = {'intent': 'policy_inquiry', 'sub_intent': None,
                                  'confidence': 0, 'chains': [], 'requires_parallel': False}
    classifier = utils.LLMIntentClassifier(model_client=object())
    classifier._assistant = SimpleNamespace(on_messages=AsyncMock(return_value=SimpleNamespace(
        chat_message=SimpleNamespace(to_text=lambda: json.dumps(payload)))))
    monkeypatch.setattr(utils, 'logging_manager', Mock())
    result = asyncio.run(classifier.classify('补贴'))
    assert result.confidence == 0 and result.requires_parallel is False
    assert result.chains == [] and result.sub_intent is None


@pytest.mark.parametrize('pack,class_name', [
    ('intent_router', 'IntentRouterAgent'), ('query_analyzer', 'QueryAnalyzerAgent'),
])
def test_pack_processing_failure_does_not_fabricate_success(pack, class_name):
    module = importlib.import_module(f'app.agents.packs.{pack}.node')
    agent = object.__new__(getattr(module, class_name))
    agent.logger = logging.getLogger('pack-failure')
    agent.metrics = {'errors': 0}

    def fail(text):
        raise OSError('tokenization failed')

    agent._preprocess_text = fail
    with pytest.raises(OSError, match='tokenization failed'):
        asyncio.run(agent.process_request(SimpleNamespace(id=uuid4(), text='补贴'), object()))
    assert agent.metrics['errors'] == 1


@pytest.mark.parametrize('text', ['', ' \n\t'])
def test_pack_empty_llm_answer_is_failure(text, monkeypatch):
    from app.agents.packs.answer_generator.node import AnswerGeneratorAgent
    from autogen_agentchat.agents import AssistantAgent
    from unittest.mock import Mock, create_autospec

    agent = object.__new__(AnswerGeneratorAgent)
    agent._assistant_lock = asyncio.Lock()
    assistant = create_autospec(AssistantAgent, instance=True)
    assistant.on_messages.return_value = SimpleNamespace(
        chat_message=SimpleNamespace(to_text=lambda: text))
    agent._assistant = assistant
    monkeypatch.setattr(agent, '_calculate_answer_confidence', Mock(return_value=.8))
    with pytest.raises(ValueError, match='empty'):
        asyncio.run(agent._generate_with_llm({'query_id': uuid4(), 'intent': 'general'}, [], {}))


def test_pack_larger_evidence_reaches_existing_confidence_weights():
    from app.agents.packs.query_analyzer.node import QueryAnalyzerAgent
    from app.models.policy import QueryIntent

    agent = object.__new__(QueryAnalyzerAgent)
    assert agent._calculate_confidence(QueryIntent.GENERAL_INQUIRY, ['e'] * 3, [], []) == pytest.approx(.6)
    assert agent._calculate_confidence(QueryIntent.GENERAL_INQUIRY, ['e'] * 5, [], []) == pytest.approx(.7)
    assert agent._calculate_confidence(QueryIntent.GENERAL_INQUIRY, [], ['k'] * 2, []) == pytest.approx(.6)
    assert agent._calculate_confidence(QueryIntent.GENERAL_INQUIRY, [], ['k'] * 4, []) == pytest.approx(.7)


def test_pack_validated_prediction_reaches_both_consumers():
    from app.agents.packs.intent_router.node import IntentRouterAgent
    from app.agents.packs.intent_router.utils import IntentPrediction, LLMIntentClassifier
    from app.agents.service.tools import IntentDetectionTool
    from unittest.mock import create_autospec

    prediction = IntentPrediction(intent='policy_inquiry', sub_intent=None, confidence=0,
                                  chains=[], requires_parallel=False)
    classifier = create_autospec(LLMIntentClassifier, instance=True)
    classifier.classify.return_value = prediction
    router = object.__new__(IntentRouterAgent)
    router._llm_classifier = classifier
    result = asyncio.run(router._classify_intent_llm_first('补贴'))
    assert result['confidence'] == 0 and result['llm_parallel'] is False
    assert result['llm_chains'] == []
    tool = IntentDetectionTool(classifier=classifier)
    data = asyncio.run(tool.detect('补贴'))
    assert data['intent'] == 'policy_inquiry' and data['confidence'] == 0
    assert data['sub_intent'] is None and data['requires_parallel'] is False


@pytest.mark.parametrize('text,expected_intent,expected_confidence,expected_sub_intent', [
    ('你好补贴', 'greeting', .5, None),
    ('政策补贴申请条件流程', 'policy_inquiry', 1, 'eligibility'),
])
def test_pack_rule_sub_intent_belongs_to_its_candidate(
    text, expected_intent, expected_confidence, expected_sub_intent
):
    from app.agents.packs.intent_router.node import IntentRouterAgent

    router = object.__new__(IntentRouterAgent)
    router.intent_classifiers = {
        'greeting': {'keywords': ['你好'], 'patterns': ['你好']},
        'policy_inquiry': {'keywords': ['政策', '补贴', '申请', '条件', '流程'],
                           'sub_intents': {'eligibility': ['条件'], 'benefit': ['补贴']}},
    }
    classification = asyncio.run(router._classify_intent(text))
    assert classification['intent_type'] == expected_intent
    assert classification['confidence'] == pytest.approx(expected_confidence)
    assert classification.get('sub_intent') == expected_sub_intent


@pytest.fixture
def review_payload():
    return {
        'relevance_score': 0.8, 'policy_summary': 'Existing subsidy',
        'key_points': ['Applications are open'], 'eligibility_criteria': ['Residents'],
        'benefits': '100 yuan', 'application_process': 'Apply online',
        'deadlines': '2030-12-31', 'contact_info': None,
        'answered_questions': ['Who can apply?'], 'missing_information': [],
        'confidence': 0.9, 'reasoning': 'Supported by the policy text',
    }


@pytest.mark.parametrize('change', [
    {'key_points': [{'invented': 'fact'}]}, {'eligibility_criteria': [7]},
    {'benefits': {'amount': 100}}, {'relevance_score': 2},
    {'confidence': False}, {'deadlines': None},
])
def test_json_policy_review_invalid_data_uses_explicit_fallback(
    monkeypatch, caplog, review_payload, change
):
    from app.agents.packs.policy_review.node import PolicyReviewAgent
    from app.models.policy import PolicyDocument, PolicyType
    from unittest.mock import AsyncMock

    payload = {**review_payload, **change}
    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(payload)))
    document = PolicyDocument(title='Subsidy', source='Local government', content='Subsidy policy',
                              doc_type=PolicyType.SUBSIDY)
    result = asyncio.run(agent._analyze_document(document, 'subsidy'))
    assert result['reasoning'] == 'Simple keyword-based analysis'
    assert result['missing_information'] == ['Detailed analysis not available']
    assert any(record.exc_info for record in caplog.records)


def test_json_policy_review_preserves_zero_empty_and_optional_contact(
    monkeypatch, review_payload
):
    from app.agents.packs.policy_review.node import PolicyReviewAgent
    from app.models.policy import PolicyDocument, PolicyType
    from unittest.mock import AsyncMock

    payload = {**review_payload, 'relevance_score': 0, 'confidence': 0,
               'key_points': [], 'eligibility_criteria': [], 'benefits': '', 'deadlines': ''}
    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(payload)))
    document = PolicyDocument(title='Policy', source='Local government', content='Policy text',
                              doc_type=PolicyType.SUBSIDY)
    result = asyncio.run(agent._analyze_document(document, 'query'))
    assert result == payload


def test_json_policy_synthesis_rejects_broken_internal_analysis():
    from app.agents.packs.policy_review.node import PolicyReviewAgent

    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    documents = [{'document': {'title': 'Policy', 'source': 'Government'},
                  'analysis': {'key_points': [], 'eligibility_criteria': [],
                               'benefits': '', 'deadlines': ''}}]
    with pytest.raises(KeyError, match='relevance_score'):
        agent._synthesize_analysis(documents)


@pytest.fixture
def question_payload():
    return {
        'intent': 'Find subsidy eligibility', 'entities': ['Residents'],
        'keywords': ['subsidy'], 'policy_types': ['subsidy'],
        'time_constraints': None, 'location_constraints': None,
        'target_groups': [], 'question_type': 'eligibility',
        'confidence': 0.8, 'reasoning': 'User asks about requirements',
    }


@pytest.mark.parametrize('change', [
    {'entities': [{'person': 'resident'}]}, {'keywords': [17]},
    {'policy_types': [False]}, {'confidence': True},
    {'time_constraints': ['tomorrow']}, {'location_constraints': 123},
])
def test_json_question_invalid_fields_use_rule_fallback(
    monkeypatch, question_payload, change
):
    from app.agents.packs.question_builder.node import QuestionUnderstander
    from unittest.mock import AsyncMock

    agent = QuestionUnderstander('question-json', {}, model_client=object())
    payload = {**question_payload, **change}
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(payload)))
    result = asyncio.run(agent._analyze_question('家电补贴条件'))
    assert result['reasoning'] == 'Rule-based analysis (fallback)'
    assert '补贴' in result['keywords']


def test_json_question_preserves_zero_and_missing_optional_constraints(
    monkeypatch, question_payload
):
    from app.agents.packs.question_builder.node import QuestionUnderstander
    from unittest.mock import AsyncMock

    payload = {**question_payload, 'confidence': 0, 'entities': [],
               'keywords': [], 'policy_types': []}
    del payload['time_constraints'], payload['location_constraints']
    agent = QuestionUnderstander('question-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(payload)))
    result = asyncio.run(agent.process_message('查询政策'))
    assert result['success'] is True
    assert result['data']['confidence'] == 0 and result['data']['keywords'] == []
    assert result['data']['time_constraints'] is None
    assert result['data']['location_constraints'] is None


@pytest.mark.parametrize('payload', [[{'invented': 'fact'}], [2], [False], [None]])
def test_json_nlp_rejects_nonstring_facts_without_losing_regex_evidence(payload, caplog):
    from app.agents.packs.policy_analysis.node import PolicyAnalyzerAgent
    from unittest.mock import AsyncMock

    agent: Any = object.__new__(PolicyAnalyzerAgent)
    agent.model_client = object()
    agent._assistant_lock = asyncio.Lock()
    agent.logger = logging.getLogger('json-policy-analysis')
    agent.eligibility_patterns = ['申请条件']
    agent._assistant = SimpleNamespace(on_messages=AsyncMock(return_value=SimpleNamespace(
        chat_message=SimpleNamespace(to_text=lambda: json.dumps(payload)))))
    content = '申请条件：申请人需在本市连续居住五年以上。'
    result = asyncio.run(agent._extract_eligibility_criteria(SimpleNamespace(content=content)))
    assert result == [content]
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize('facts', [[], ['fact'], [f'fact-{index}' for index in range(22)]])
def test_json_nlp_keeps_valid_strings_and_existing_twenty_fact_limit(facts):
    from app.agents.packs.policy_analysis.node import PolicyAnalyzerAgent
    from unittest.mock import AsyncMock

    agent: Any = object.__new__(PolicyAnalyzerAgent)
    agent.model_client = object()
    agent._assistant_lock = asyncio.Lock()
    agent._assistant = SimpleNamespace(on_messages=AsyncMock(return_value=SimpleNamespace(
        chat_message=SimpleNamespace(to_text=lambda: json.dumps(facts)))))
    assert asyncio.run(agent._extract_with_nlp('policy', 'extract facts')) == facts[:20]


@pytest.mark.parametrize('payload', [[{'invented': 'entity'}], [8], [False], {'entities': ['Policy']}])
def test_json_retriever_invalid_entities_use_existing_keyword_strategy(monkeypatch, payload):
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    from unittest.mock import AsyncMock

    agent = PolicyRetriever('retrieval-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(payload)))
    assert asyncio.run(agent._extract_entities('automotive subsidy')) == ['automotive', 'subsidy']


@pytest.mark.parametrize('entities', [[], ['汽车', '']])
def test_json_retriever_preserves_valid_empty_entity_results(monkeypatch, entities):
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    from unittest.mock import AsyncMock

    agent = PolicyRetriever('retrieval-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_request_completion', AsyncMock(return_value=json.dumps(entities)))
    assert asyncio.run(agent._extract_entities('automotive subsidy')) == entities


@pytest.mark.parametrize('payload', [{}, {'query': ''}, {'query': ' \t'},
                                     {'query': 42}, {'query': 'policy', 'filters': None}])
@pytest.mark.parametrize('as_json', [False, True])
def test_json_retrieval_rejects_invalid_request_before_search(monkeypatch, payload, as_json):
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    from unittest.mock import AsyncMock

    agent = PolicyRetriever('retrieval-json', {}, model_client=object())
    search = AsyncMock(return_value='would report success')
    monkeypatch.setattr(agent, '_hybrid_search', search)
    result = asyncio.run(agent.process_message(json.dumps(payload) if as_json else payload))
    assert result['success'] is False
    search.assert_not_awaited()


@pytest.mark.parametrize('as_json', [False, True])
def test_json_retrieval_default_hybrid_keeps_vector_only_configuration(as_json):
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    from unittest.mock import Mock

    search = Mock(return_value=([], []))
    agent = PolicyRetriever('retrieval-json', {}, vector_store=SimpleNamespace(search=search),
                            model_client=object())
    payload = {'query': 'policy', 'method': 'hybrid'}
    result = asyncio.run(agent.process_message(json.dumps(payload) if as_json else payload))
    assert result['success'] is True and result['data'].documents == []
    search.assert_called_once_with('policy', top_k=5, threshold=0.7, filters={})


def test_json_explicit_graph_search_requires_configured_graph(monkeypatch):
    from app.agents.packs.policy_retriever.node import PolicyRetriever
    from unittest.mock import AsyncMock

    agent = PolicyRetriever('retrieval-json', {}, model_client=object())
    vector_search = AsyncMock(return_value='unrequested vector result')
    monkeypatch.setattr(agent, '_vector_search', vector_search)
    with pytest.raises(RuntimeError, match='graph_db'):
        asyncio.run(agent._graph_search('policy', {}))
    vector_search.assert_not_awaited()


@pytest.mark.parametrize('query_fields', [{}, {'query': ''}, {'query': ' \t'}])
@pytest.mark.parametrize('as_json', [False, True])
def test_json_policy_review_requires_query_before_analyzing(
    monkeypatch, review_payload, query_fields, as_json
):
    from app.agents.packs.policy_review.node import PolicyReviewAgent
    from app.models.policy import PolicyDocument, PolicyType
    from unittest.mock import AsyncMock

    document = PolicyDocument(title='Policy', source='Government', content='Policy text',
                              doc_type=PolicyType.SUBSIDY)
    payload = {'documents': [document.model_dump(mode='json')], **query_fields}
    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    analyze = AsyncMock(return_value=review_payload)
    monkeypatch.setattr(agent, '_analyze_document', analyze)
    result = asyncio.run(agent.process_message(json.dumps(payload) if as_json else payload))
    assert result['success'] is False
    analyze.assert_not_awaited()


def test_json_policy_review_preserves_explicit_no_documents_error(monkeypatch):
    from app.agents.packs.policy_review.node import PolicyReviewAgent
    from unittest.mock import AsyncMock

    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    analyze = AsyncMock()
    monkeypatch.setattr(agent, '_analyze_document', analyze)
    result = asyncio.run(agent.process_message(json.dumps({'query': 'policy', 'documents': []})))
    assert result == {'success': False, 'error': 'No documents provided for analysis'}
    analyze.assert_not_awaited()


@pytest.mark.parametrize('as_json', [False, True])
def test_json_policy_review_valid_request_reaches_synthesis(
    monkeypatch, review_payload, as_json
):
    from app.agents.packs.policy_review.node import PolicyReviewAgent
    from app.models.policy import PolicyDocument, PolicyType
    from unittest.mock import AsyncMock

    document = PolicyDocument(title='Policy', source='Government', content='Policy text',
                              doc_type=PolicyType.SUBSIDY)
    payload = {'query': 'policy', 'documents': [document.model_dump(mode='json')]}
    agent = PolicyReviewAgent('review-json', {}, model_client=object())
    monkeypatch.setattr(agent, '_analyze_document', AsyncMock(return_value=review_payload))
    result = asyncio.run(agent.process_message(json.dumps(payload) if as_json else payload))
    assert result['success'] is True
    assert result['data']['document_analyses'][0]['document']['title'] == 'Policy'
    assert result['data']['synthesis']['most_relevant'] == 'Policy'
