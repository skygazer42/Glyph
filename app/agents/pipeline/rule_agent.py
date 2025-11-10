"""Rule agent that leverages the DSL PolicyEngine for subsidy calculations."""

from __future__ import annotations

import json
import logging
from statistics import mean
from typing import Any, Dict, List, Optional
from uuid import uuid4

from autogen_core.models import UserMessage

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.core.llms import model_client
from app.models.base import FinalAnswer


class RuleEngineAgent:
    """Selects the best DSL rule and executes it via PolicyEngine."""

    def __init__(self, rule_dir: str = "rules", max_rules: int = 5) -> None:
        self.engine = PolicyEngine(rule_dir=rule_dir)
        self.max_rules = max_rules
        self.logger = logging.getLogger(__name__)

    async def compute(
        self, query: str, intent: Optional[Dict[str, Any]] = None
    ) -> FinalAnswer:
        rules_context = self._collect_rules()
        if not rules_context:
            return self._no_rule_answer()

        plan = await self._plan_execution(query, rules_context)
        rule_id = plan.get("rule_id")
        if not rule_id or rule_id not in self.engine.rules:
            return self._unable_to_match_answer(query, plan.get("reasoning"))

        rule_info = self.engine.get_rule_info(rule_id) or {}
        inputs = self._coerce_inputs(rule_info, plan.get("inputs", {}))
        result = self.engine.execute(rule_id, inputs)
        answer_text = self._format_result(rule_id, result, inputs)
        confidence = 0.85 if result.get("status") == "SUCCESS" else 0.45

        return FinalAnswer(
            query_id=uuid4(),
            answer=answer_text,
            sources=[],
            confidence=confidence,
            verification_passed=result.get("status") == "SUCCESS",
            metadata={
                "route": "rule_engine",
                "rule_id": rule_id,
                "inputs": inputs,
                "engine_result": result,
                "intent": intent,
            },
            total_processing_time=0.0,
        )

    def _collect_rules(self) -> List[Dict[str, Any]]:
        rules = self.engine.list_rules() or []
        # 优先活跃规则
        active_rules = [r for r in rules if r.get("is_active")]
        sorted_rules = active_rules + [r for r in rules if not r.get("is_active")]
        contexts = []
        for rule_meta in sorted_rules[: self.max_rules]:
            info = self.engine.get_rule_info(rule_meta["rule_id"]) or {}
            contexts.append(
                {
                    "rule_id": rule_meta["rule_id"],
                    "title": rule_meta.get("title") or info.get("title") or "",
                    "inputs": info.get("inputs", []),
                    "description": info.get("description") or info.get("notes") or "",
                }
            )
        return contexts

    async def _plan_execution(
        self, query: str, contexts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        prompt = self._build_planner_prompt(query, contexts)
        try:
            response = await model_client.create(
                [UserMessage(content=prompt, source="user")]
            )
            return self._safe_parse_json(response.content) or {}
        except Exception as exc:  # pragma: no cover
            self.logger.error("Rule planner调用失败: %s", exc)
            return {}

    def _build_planner_prompt(self, query: str, contexts: List[Dict[str, Any]]) -> str:
        lines = [
            "你是政策规则匹配助手。以下是系统中可用的 DSL 规则，"
            "请阅读规则及其输入说明，并根据用户问题选择最合适的规则，同时推理输入参数。",
        ]
        for ctx in contexts:
            inputs_desc = ", ".join(
                f"{spec.get('name')}({spec.get('type','string')}): {spec.get('description','')}"
                for spec in ctx["inputs"]
            )
            lines.append(
                f"- rule_id: {ctx['rule_id']}，标题: {ctx['title']}，输入: {inputs_desc or '无说明'}"
            )
        lines.append(
            "如果无法确定规则，请将 rule_id 设为 null。务必输出严格 JSON："
            '{"rule_id": "Rule_xxx 或 null", "inputs": {参数: 值}, "reasoning": "简述选择原因"}。'
        )
        lines.append(f"\n用户问题：{query}")
        return "\n".join(lines)

    def _coerce_inputs(
        self, rule_info: Dict[str, Any], raw_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        specs_map = {
            spec.get("name"): spec for spec in rule_info.get("inputs", []) if spec.get("name")
        }
        converted: Dict[str, Any] = {}
        for key, value in raw_inputs.items():
            spec = specs_map.get(key)
            if spec is None or value is None:
                converted[key] = value
                continue
            input_type = (spec.get("type") or "string").lower()
            try:
                if input_type == "float":
                    converted[key] = float(value)
                elif input_type == "int":
                    converted[key] = int(value)
                elif input_type == "boolean":
                    if isinstance(value, bool):
                        converted[key] = value
                    else:
                        converted[key] = str(value).lower() in {"true", "1", "yes", "是"}
                else:
                    converted[key] = value
            except (ValueError, TypeError):
                converted[key] = value
        return converted

    def _format_result(
        self, rule_id: str, result: Dict[str, Any], inputs: Dict[str, Any]
    ) -> str:
        status = result.get("status", "UNKNOWN")
        msg = result.get("message", "")
        final_value = result.get("final_result")
        trace = result.get("trace")

        parts = [f"匹配规则：{rule_id}", f"执行状态：{status}"]
        if inputs:
            pretty_inputs = ", ".join(f"{k}={v}" for k, v in inputs.items())
            parts.append(f"输入参数：{pretty_inputs}")
        if final_value:
            if isinstance(final_value, dict):
                entries = ", ".join(f"{k}={v}" for k, v in final_value.items())
                parts.append(f"计算结果：{entries}")
            else:
                parts.append(f"计算结果：{final_value}")
        if msg:
            parts.append(f"说明：{msg}")
        if trace:
            parts.append(f"计算过程：\n{trace}")
        return "\n".join(parts)

    def _unable_to_match_answer(
        self, query: str, reasoning: Optional[str]
    ) -> FinalAnswer:
        detail = reasoning or "缺少关键信息，无法匹配现有 DSL 规则。"
        return FinalAnswer(
            query_id=uuid4(),
            answer=f"无法根据现有 DSL 规则处理“{query}”。请补充具体的政策名称、城市或参数。原因：{detail}",
            sources=[],
            confidence=0.2,
            verification_passed=False,
            metadata={"route": "rule_engine", "reason": detail},
            total_processing_time=0.0,
        )

    def _no_rule_answer(self) -> FinalAnswer:
        return FinalAnswer(
            query_id=uuid4(),
            answer="系统中尚未配置任何 DSL 规则，请先生成并保存规则再执行计算。",
            sources=[],
            confidence=0.1,
            verification_passed=False,
            metadata={"route": "rule_engine"},
            total_processing_time=0.0,
        )

    def _safe_parse_json(self, text: Optional[str]) -> Dict[str, Any]:
        if not text:
            return {}
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    return {}
        except Exception:
            return {}
        return {}
