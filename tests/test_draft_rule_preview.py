"""Draft previews share execution semantics without changing saved rules."""

from copy import deepcopy
import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
import yaml

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.api.endpoints.rule_preview import router
from app.api.schemas import GenerateDSLRequest, GenerateDSLResponse
from test_python_guidelines_tooling import load_definitions


@pytest.fixture
def client():
    application = FastAPI()
    application.include_router(router, prefix="/api/dsl")
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def draft():
    return {
        "rule_id": "same-rule-id",
        "inputs": [{"name": "price", "type": "float", "required": True}],
        "calc": {"total": "inputs['price'] * 0.2"},
        "output": {
            "status": "QUALIFIED",
            "final_result": "{{ calc.total }}",
            "trace_template": "按输入价格计算：{{ calc.total }}",
        },
    }


def preview(client, rule, inputs):
    return client.post("/api/dsl/preview", json={"yaml_content": yaml.safe_dump(rule), "inputs": inputs})


def test_generate_returns_the_input_contract_of_the_rendered_yaml(draft):
    extracted = {"rule_id": "before-template", "inputs": []}
    namespace = load_definitions(
        "app/api/endpoints/dsl.py", {"generate_dsl"},
        router=SimpleNamespace(post=lambda *args, **kwargs: lambda function: function),
        Depends=lambda dependency: None,
        get_dsl_generator=lambda: None,
        get_dsl_extractor=lambda: None,
        get_document_parser=lambda: None,
        GenerateDSLResponse=GenerateDSLResponse,
        HTTPException=HTTPException,
        logger=logging.getLogger(__name__),
        yaml=yaml,
    )
    result = namespace["generate_dsl"](
        GenerateDSLRequest(text="政策原文"),
        SimpleNamespace(generate=lambda *args, **kwargs: yaml.safe_dump(draft)),
        SimpleNamespace(extract=lambda *args: extracted),
        SimpleNamespace(preprocess_text=lambda text: {"metadata": {}}),
    )

    assert result.dsl_data == yaml.safe_load(result.yaml_content) == draft
    assert result.dsl_data["rule_id"] != extracted["rule_id"]
    assert result.dsl_data["inputs"] == draft["inputs"]


@pytest.mark.parametrize("input_type", ["float", "number"])
def test_preview_calculates_the_supplied_draft_without_disk_access(client, draft, monkeypatch, input_type):
    def unexpected_disk_access(*args, **kwargs):
        pytest.fail("Draft evaluation must not access the rule directory")

    monkeypatch.setattr(Path, "mkdir", unexpected_disk_access)
    monkeypatch.setattr(Path, "glob", unexpected_disk_access)
    draft["inputs"][0]["type"] = input_type
    first = preview(client, draft, {"price": 100})
    second = preview(client, draft, {"price": 250})

    assert first.status_code == second.status_code == 200
    assert first.json()["success"] is True
    assert first.json()["result"]["final_result"] == "20.0"
    assert second.json()["result"]["final_result"] == "50.0"
    assert second.json()["result"]["explainability_trace"][0]["description"] == "按输入价格计算：50.0"


def test_execute_rule_preserves_saved_version_and_registry(tmp_path, draft):
    saved = deepcopy(draft)
    saved["calc"]["total"] = "inputs['price'] * 0.1"
    file_path = tmp_path / "saved.yaml"
    file_path.write_text(yaml.safe_dump(saved), encoding="utf-8")
    original_content = file_path.read_bytes()
    engine = PolicyEngine(str(tmp_path))
    original_rules = deepcopy(engine.rules)

    assert engine.execute_rule(draft, {"price": 100})["final_result"] == "20.0"
    assert engine.execute("same-rule-id", {"price": 100})["final_result"] == "10.0"
    assert engine.rules == original_rules
    assert file_path.read_bytes() == original_content
    assert list(tmp_path.iterdir()) == [file_path]


@pytest.mark.parametrize("content", [
    "rule_id: [broken",
    "[]",
    "rule_id: 12\noutput: {}",
    "rule_id: r\ninputs: {}\noutput: {status: VALID, final_result: '0'}",
    "rule_id: r\ninputs: [{name: price, required: 'true'}]\noutput: {status: VALID, final_result: '0'}",
    "rule_id: r\ninputs: [{name: price}, {name: price}]\noutput: {status: VALID, final_result: '0'}",
    "rule_id: r\ncalc: []\noutput: {status: VALID, final_result: '0'}",
    "rule_id: r\noutput: {status: VALID, final_result: 0}",
])
def test_preview_rejects_malformed_rule_content(client, content):
    response = client.post("/api/dsl/preview", json={"yaml_content": content, "inputs": {}})
    assert response.status_code == 400
    assert "规则格式无效" in response.json()["detail"]


@pytest.mark.parametrize("payload", [
    {"yaml_content": "", "inputs": {}},
    {"yaml_content": "x" * 64001, "inputs": {}},
    {"yaml_content": 123, "inputs": {}},
    {"yaml_content": "rule_id: r", "inputs": []},
])
def test_preview_bounds_and_types_the_request(client, payload):
    assert client.post("/api/dsl/preview", json=payload).status_code == 422


def test_preview_keeps_engine_validation_and_execution_failures(client, draft):
    missing = preview(client, draft, {})
    assert missing.status_code == 200
    assert missing.json()["result"]["status"] == "INVALID_INPUT"
    assert missing.json()["result"]["errors"] == ["缺少必填参数: price"]

    draft["calc"]["total"] = "__import__('os').getcwd()"
    unsafe = preview(client, draft, {"price": 100})
    assert unsafe.status_code == 200
    assert unsafe.json()["result"]["status"] == "ERROR"
    assert "Unsupported DSL" in unsafe.json()["result"]["message"]


def test_preview_preserves_boolean_input_and_validity_semantics(client, draft):
    draft["inputs"] = [{"name": "enabled", "type": "boolean"}]
    draft["calc"]["total"] = "1 if inputs['enabled'] else 0"
    assert preview(client, draft, {"enabled": False}).json()["result"]["final_result"] == "0"
    assert preview(client, draft, {"enabled": "false"}).json()["result"]["status"] == "INVALID_INPUT"

    draft["valid_period"] = {"end": "2000-01-01"}
    expired = preview(client, draft, {"enabled": False, "claim_time": "2026-01-01"})
    assert expired.json()["result"]["status"] == "EXPIRED"
