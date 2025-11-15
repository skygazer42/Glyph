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
        status = (result or {}).get("status", "UNKNOWN")
        msg = (result or {}).get("message", "")
        final_value = (result or {}).get("final_result")
        trace_steps = (result or {}).get("explainability_trace") or []
        policy_source = (result or {}).get("policy_source") or {}
        title = policy_source.get("title") or ""

        lines: list[str] = []

        # 开场：根据状态给一句总体验证结论
        if status in {"QUALIFIED", "SUCCESS"}:
            if title:
                lines.append(f"感谢您提供的信息。根据《{title}》及您提供的参数，系统判断您符合当前规则下的补贴条件，并已完成补贴金额的计算。")
            else:
                lines.append("感谢您提供的信息。根据相关政策规则，系统判断您符合补贴条件，并已完成补贴金额的计算。")
        elif status == "EXPIRED":
            if title:
                lines.append(f"根据《{title}》，该政策当前已不在有效期内，因此无法为您计算补贴金额。")
            else:
                lines.append("经核对，该政策当前已不在有效期内，暂无法为您计算补贴金额。")
        elif status == "INVALID_INPUT":
            lines.append("您提供的参数不完整或格式有误，暂时无法进行精确计算，请核对后重新提交。")
        else:
            lines.append("系统已根据相关政策规则尝试进行计算，结果如下：")

        # 关键信息归纳
        if inputs:
            pretty_inputs = "，".join(f"{k}={v}" for k, v in inputs.items())
            lines.append(f"\n本次计算使用的关键信息包括：{pretty_inputs}。")

        # 计算过程：优先使用 DSL trace_template 生成的 explainability_trace
        if trace_steps:
            lines.append("\n计算过程如下：")
            for step in trace_steps:
                desc = step.get("description") if isinstance(step, dict) else str(step)
                desc = str(desc).strip()
                if not desc:
                    continue
                # 统一用条目形式呈现
                lines.append(f"· {desc}")

        # 计算结论
        if isinstance(final_value, (int, float)):
            lines.append(f"\n结论：本次计算得到的关键结果为 {final_value:.0f}。")
        elif final_value is not None:
            lines.append(f"\n结论：本次计算得到的关键结果为：{final_value}。")

        if msg:
            lines.append(f"\n补充说明：{msg}")

        return "\n".join(lines)

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
