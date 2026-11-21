"""Rule agent that leverages the DSL PolicyEngine for subsidy calculations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from autogen_core.models import UserMessage
from pydantic import BaseModel, ConfigDict

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.core.llms import model_client
from app.models.policy import FinalAnswer


class RuleExecutionPlan(BaseModel):
    """模型输出的严格执行计划；rule_id 可为空，输入保留为具名字段字典。"""

    model_config = ConfigDict(strict=True)

    rule_id: str | None
    inputs: dict[str, Any]
    reasoning: str | None = None


class RuleEngineAgent:
    """Selects the best DSL rule and executes it via PolicyEngine."""

    def __init__(self, rule_dir: str = "rules", max_rules: int = 5) -> None:
        self.engine = PolicyEngine(rule_dir=rule_dir)
        self.max_rules = max_rules
        self.logger = logging.getLogger(__name__)

    async def compute(
        self, query: str, intent: Optional[Dict[str, Any]] = None
    ) -> FinalAnswer:
        """匹配候选规则并执行，返回携带引擎结果的 FinalAnswer；无规则或无法匹配时返回未验证答复。"""
        rules_context = self._collect_rules()
        if not rules_context:
            return self._no_rule_answer()

        query_text = query.casefold()
        scored = [
            (sum(
                len(keyword) for keyword in item.get("keywords", [])
                if keyword and keyword.casefold() in query_text
            ), item) for item in rules_context
        ]
        rules_context = [
            item for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True)
            if score > 0
        ][: self.max_rules]
        if not rules_context:
            return self._unable_to_match_answer(query, "没有命中本事项的计算规则，需检索对应政策条款。")
        plan = await self._plan_execution(query, rules_context)
        rule_id = plan.rule_id
        if not rule_id or rule_id not in self.engine.rules:
            return self._unable_to_match_answer(query, plan.reasoning)

        rule_info = self.engine.get_rule_info(rule_id)
        if rule_info is None:
            raise KeyError(rule_id)
        inputs = self._coerce_inputs(rule_info, plan.inputs)
        result = self.engine.execute(rule_id, inputs)
        review = result.get("verification", {"status": "unverified"})
        if review["status"] not in {"verified_for_estimate", "manual_only"}:
            result = {
                "rule_id": rule_id,
                "status": "MANUAL_REVIEW",
                "message": review.get("message", "此规则版本尚未完成官方条款核验，暂不提供金额。"),
                "policy_source": rule_info.get("policy_source", {}),
                "verification": review,
            }
        answer_text = self._format_result(result, inputs, rule_info.get("inputs", []))
        qualified = result["status"] in {"QUALIFIED", "SUCCESS"}
        confidence = 0.85 if qualified else 0.45

        return FinalAnswer(
            query_id=uuid4(),
            answer=answer_text,
            sources=[],
            confidence=confidence,
            verification_passed=qualified,
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
        rules = self.engine.list_rules()
        # 优先活跃规则
        active_rules = [r for r in rules if r["is_active"]]
        sorted_rules = active_rules + [r for r in rules if not r["is_active"]]
        contexts = []
        for rule_meta in sorted_rules:
            info = self.engine.get_rule_info(rule_meta["rule_id"])
            if info is None:
                raise KeyError(rule_meta["rule_id"])
            contexts.append(
                {
                    "rule_id": rule_meta["rule_id"],
                    "title": info.get("name") or rule_meta["title"],
                    "inputs": info.get("inputs", []),
                    "description": info.get("description") or info.get("notes") or "",
                    "keywords": info.get("keywords", []),
                }
            )
        return contexts

    async def _plan_execution(
        self, query: str, contexts: List[Dict[str, Any]]
    ) -> RuleExecutionPlan:
        prompt = self._build_planner_prompt(query, contexts)
        try:
            response = await model_client.create(
                [UserMessage(content=prompt, source="user")]
            )
            return self._parse_execution_plan(response.content)
        except Exception as exc:  # pragma: no cover
            self.logger.error("Rule planner调用失败: %s", exc, exc_info=True)
            raise

    @staticmethod
    def _build_planner_prompt(query: str, contexts: List[Dict[str, Any]]) -> str:
        lines = [
            "你是政策规则匹配助手。以下是系统中可用的 DSL 规则，"
            "请阅读规则及其输入说明，并根据用户问题选择最合适的规则。"
            "输入只能填写用户明确提供的事实，不得推断或补造资格确认、日期、"
            "既往领取次数、资金余额和业务恢复状态；缺失参数应省略并说明需要补充的信息。",
            "业务场景已明确但输入不完整时，仍选择对应规则，只填写已知事实；由引擎用中文字段列出缺项，不要因为缺项否认存在该业务规则。",
            "标题含核验、最高标准或金额待确认的规则也是该事项的核验入口；用户询问金额时仍选择它，由引擎返回人工核实，不得声称没有该规则。",
            "未知日期、商品码等不得填空字符串，未知次数不得填0，未知能效属性不得填false；这些缺项一律省略。",
        ]
        for ctx in contexts:
            inputs_desc = ", ".join(
                f"{spec['name']}({spec['type']}): {spec.get('description', '')}"
                + (f"；可选值：{json.dumps(spec['options'], ensure_ascii=False)}" if "options" in spec else "")
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

    @staticmethod
    def _coerce_inputs(
        rule_info: Dict[str, Any], raw_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """按规则声明尝试转换输入；无法转换、未知字段和 None 保持原值，交给引擎继续校验。"""
        specs_map = {
            spec["name"]: spec for spec in rule_info.get("inputs", [])
        }
        converted: Dict[str, Any] = {}
        for key, value in raw_inputs.items():
            spec = specs_map.get(key)
            if spec is None or value is None:
                converted[key] = value
                continue
            input_type = spec["type"].lower()
            if input_type in {"float", "int", "integer"} and isinstance(value, bool):
                converted[key] = value
                continue
            if input_type in {"int", "integer"} and isinstance(value, float) and not value.is_integer():
                converted[key] = value
                continue
            try:
                if input_type == "float":
                    converted[key] = float(value)
                elif input_type in {"int", "integer"}:
                    converted[key] = int(value)
                elif input_type in {"bool", "boolean"}:
                    if isinstance(value, bool):
                        converted[key] = value
                    else:
                        token = str(value).lower()
                        if token in {"true", "1", "yes", "是"}:
                            converted[key] = True
                        elif token in {"false", "0", "no", "否"}:
                            converted[key] = False
                        else:
                            converted[key] = value
                else:
                    converted[key] = value
            except (ValueError, TypeError):
                converted[key] = value
        return converted

    @staticmethod
    def _format_result(
        result: Dict[str, Any], inputs: Dict[str, Any], input_specs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """保留金额小数和官方出处；缺项用中文字段追问，未核实状态不展示成功金额。"""
        status = result["status"]
        msg = result.get("message", "")
        final_value = result.get("final_result")
        trace_steps = result.get("explainability_trace", [])
        policy_source = result.get("policy_source", {})
        title = policy_source.get("title") or ""

        lines: list[str] = []

        # 开场：根据状态给一句总体验证结论
        if status == "CALCULATED":
            lines.append(
                f"依据《{title}》及您提供的事实完成金额测算。"
                "本结果不代表审批通过，实际资格、材料及额度仍需主管部门审核。"
            )
        elif status in {"QUALIFIED", "SUCCESS"}:
            if title:
                lines.append(f"感谢您提供的信息。根据《{title}》及您提供的参数，系统判断您符合当前规则下的补贴条件，并已完成补贴金额的计算。")
            else:
                lines.append("感谢您提供的信息。根据相关政策规则，系统判断您符合补贴条件，并已完成补贴金额的计算。")
        elif status == "EXPIRED":
            if title:
                lines.append(f"您提供的业务日期不在《{title}》所选规则的适用期内，暂无法按此版本计算金额。")
            else:
                lines.append("您提供的业务日期不在所选规则的适用期内，暂无法按此版本计算金额。")
        elif status == "INVALID_INPUT":
            lines.append("您提供的参数不完整或格式有误，暂时无法进行精确计算，请核对后重新提交。")
        elif status == "MANUAL_REVIEW":
            lines.append("现有事实或现行金额标准需要人工核实，本次没有得出可领取、可提取或应付的金额。")
        elif status in {"NOT_IN_PERIOD", "SUSPENDED", "INELIGIBLE", "NOT_QUALIFIED"}:
            lines.append("本次业务时间或条件不满足所选规则，暂不提供成功金额测算。")
        else:
            lines.append("系统已根据相关政策规则尝试进行计算，结果如下：")

        if status == "INVALID_INPUT" and result.get("errors"):
            errors = list(result["errors"])
            for spec in input_specs if input_specs is not None else []:
                pattern = rf"(?<![A-Za-z0-9_]){re.escape(spec['name'])}(?![A-Za-z0-9_])"
                label = spec.get("label", spec["name"])
                errors = [re.sub(pattern, lambda match: label, error) for error in errors]
            lines.append("请补充或修正：" + "；".join(errors))

        # 关键信息归纳
        if inputs:
            specs = {spec["name"]: spec for spec in (input_specs if input_specs is not None else [])}
            items = []
            for key, value in inputs.items():
                if value is None or value == "":
                    continue
                spec = specs.get(key, {})
                displayed = "是" if value is True else "否" if value is False else str(value)
                for option in spec.get("options", []):
                    if type(value) is type(option["value"]) and value == option["value"]:
                        displayed = option["label"]
                        break
                items.append(f"{spec.get('label', key)}={displayed}")
            pretty_inputs = "，".join(items)
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
        if status in {"CALCULATED", "QUALIFIED", "SUCCESS", "VALID"} and final_value is not None:
            if isinstance(final_value, (int, float)):
                lines.append(f"\n金额试算结果：{final_value:,.2f} 元；具体性质见上述计算依据。")
            else:
                lines.append(f"\n金额试算结果：{final_value} 元；具体性质见上述计算依据。")
        source_url = policy_source.get("url")
        if source_url:
            lines.append(f"\n官方依据：{source_url}")

        review = result.get("verification")
        if review is not None:
            if review["status"] == "verified_for_estimate":
                lines.append(f"条款核验日期：{review['reviewed_on']}；仅核对本版本公式及适用条件，个人资格和实时额度仍需核实。")
            elif review["status"] == "manual_only":
                lines.append("核验范围：仅确认官方入口和已公开条件，个人金额依据尚不完整。")

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

    @staticmethod
    def _parse_execution_plan(text: Any) -> RuleExecutionPlan:
        """解析文本中的 JSON 并校验严格计划模型；非文本、无有效 JSON 或字段不合约时抛错。"""
        if not isinstance(text, str):
            raise ValueError("Rule planner returned non-text content")
        text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(text[start : end + 1])
            else:
                raise ValueError("Rule planner returned invalid JSON") from exc
        return RuleExecutionPlan.model_validate(parsed)
