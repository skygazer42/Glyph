"""Exercise the public built-in DSL templates without external template files."""

import yaml
import pytest

from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.rule_engine import PolicyEngine


def execute_builtin(tmp_path, template_type, inputs, **parameters):
    generator = DSLGenerator(str(tmp_path), str(tmp_path / "missing-templates"))
    rule = yaml.safe_load(generator.generate_from_template(template_type, **parameters))
    engine = PolicyEngine(str(tmp_path))
    engine.rules[rule["rule_id"]] = rule
    return engine.execute(rule["rule_id"], inputs)


@pytest.mark.parametrize("template_type,inputs,expected", [
    ("appliance", {"price": 1000, "energy_level": 1, "category": "空调"}, 200),
    ("car", {"invoice_no_tax": 100000, "vehicle_type": "任意原有车型"}, 3200),
    ("consumption", {"amount": 1000, "merchant_type": "商场"}, 100),
])
def test_builtin_templates_generate_executable_rules(tmp_path, template_type, inputs, expected):
    result = execute_builtin(tmp_path, template_type, inputs)
    assert result["status"] == "QUALIFIED"
    assert float(result["final_result"]) == expected
    assert result["explainability_trace"]


@pytest.mark.parametrize("template_type,inputs,parameters", [
    ("appliance", {"price": 1000, "category": "空调"}, {"cap": 0}),
    ("appliance", {"price": 1000, "energy_level": None, "category": "空调"}, {"base_rate": 0}),
    ("consumption", {"amount": 1000, "merchant_type": "商场"}, {"per_user_limit": 0}),
    ("car", {"invoice_no_tax": 0, "vehicle_type": "任意原有车型"}, {"tiers": [{"range": [None, 1], "package": 0}]}),
])
def test_builtin_templates_preserve_zero_and_optional_values(tmp_path, template_type, inputs, parameters):
    result = execute_builtin(tmp_path, template_type, inputs, **parameters)
    assert result["status"] == "QUALIFIED"
    assert float(result["final_result"]) == 0


def test_builtin_car_keeps_first_matching_tier_and_handles_no_match(tmp_path):
    tiers = [{"range": [10, 20], "package": 7}, {"range": [0, None], "package": 9}]
    result = execute_builtin(tmp_path, "car", {"invoice_no_tax": 10, "vehicle_type": "car"}, tiers=tiers)
    assert float(result["final_result"]) == 7
    result = execute_builtin(tmp_path, "car", {"invoice_no_tax": 20, "vehicle_type": "car"}, tiers=tiers[:1])
    assert result["status"] == "NOT_QUALIFIED"
    assert float(result["final_result"]) == 0
