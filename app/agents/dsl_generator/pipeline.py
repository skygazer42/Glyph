"""
Core pipeline logic for converting policy documents into executable DSL rules.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.dsl_generator.document_parser import DocumentParser
from app.agents.dsl_generator.dsl_extractor import DSLExtractor
from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.rule_engine import PolicyEngine

logger = logging.getLogger(__name__)


class DSLPipeline:
    """High-level orchestration for parsing documents and producing DSL rules."""

    def __init__(
        self,
        data_dir: str = "data/guize",
        output_dir: str = "rules",
        use_project_config: bool = True,
        use_llama_index_parser: bool = False,
        llama_reader_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_project_config = use_project_config

        self.parser = DocumentParser(
            use_llama_index=use_llama_index_parser,
            llama_reader_kwargs=llama_reader_kwargs,
        )
        self.extractor = DSLExtractor(use_project_config=use_project_config)
        self.generator = DSLGenerator(output_dir=str(self.output_dir))
        self.engine = PolicyEngine(rule_dir=str(self.output_dir))

        if use_project_config:
            try:
                from app.config import settings  # type: ignore

                logger.info("使用项目 LLM 配置:")
                logger.info("  模型: %s", settings.model.llm_model_name)
                logger.info("  API: %s", settings.model.llm_base_url)
            except ImportError:
                logger.warning("无法导入项目配置，将使用内置规则提取")

    def process_document(self, file_path: str, save: bool = True) -> Dict[str, Any]:
        """Process an individual document."""
        result: Dict[str, Any] = {
            "file": file_path,
            "status": "processing",
            "dsl_file": None,
            "errors": [],
        }

        try:
            logger.info("开始处理文档: %s", file_path)

            logger.info("步骤 1: 解析文档")
            text = self.parser.parse(file_path)
            processed = self.parser.preprocess_text(text)
            logger.info("  提取到文本长度 %s 字符", len(text))

            if processed["metadata"].get("title"):
                logger.info("  识别到标题: %s", processed["metadata"]["title"])

            logger.info("步骤 2: 提取结构化规则")
            logger.info(
                "  %s",
                "使用项目 LLM 进行智能提取..." if self.use_project_config else "使用规则引擎进行提取...",
            )
            dsl_data = self.extractor.extract(text, processed["metadata"])

            if dsl_data.get("rule_id"):
                logger.info("  生成规则 ID: %s", dsl_data["rule_id"])

            logger.info("步骤 3: 验证提取的数据")
            validation_errors = self.extractor.validate_dsl(dsl_data)
            if validation_errors:
                logger.warning("  验证警告: %s", validation_errors)
                result["errors"].extend(validation_errors)
            else:
                logger.info("  数据验证通过")

            logger.info("步骤 4: 生成 DSL YAML")
            yaml_content = self.generator.generate(
                dsl_data,
                auto_detect=True,
                context=processed.get("metadata", {}),
            )
            logger.info("  生成 YAML 长度: %s 字符", len(yaml_content))

            if save:
                logger.info("步骤 5: 保存 DSL 文件")
                dsl_file = self.generator.save(yaml_content)
                result["dsl_file"] = str(dsl_file)
                logger.info("  文件保存至 %s", dsl_file)

            result["status"] = "success"
            result["dsl_data"] = dsl_data
            result["yaml_content"] = yaml_content
            logger.info("文档处理成功: %s", file_path)

        except Exception as exc:  # pragma: no cover
            logger.exception("处理文档失败: %s", exc)
            result["status"] = "error"
            result["errors"].append(str(exc))

        return result

    def process_directory(self, directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """Process all supported files in a directory."""
        dir_path = Path(directory) if directory else self.data_dir
        results: List[Dict[str, Any]] = []

        logger.info("批量处理目录: %s", dir_path)

        patterns = ["*.docx", "*.txt", "*.doc", "*.pdf"]

        file_count = 0
        for pattern in patterns:
            for file_path in dir_path.glob(pattern):
                file_count += 1
                logger.info("处理文件 [%s]: %s", file_count, file_path.name)
                result = self.process_document(str(file_path))
                results.append(result)

        logger.info("批量处理完成: 共处理 %s 个文件", file_count)
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info("成功: %s/%s", success_count, file_count)

        return results

    def test_rule(self, rule_id: str, test_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a rule with custom inputs."""
        logger.info("测试规则: %s", rule_id)
        logger.info("测试输入: %s", test_inputs)

        self.engine.reload_rules()
        result = self.engine.execute(rule_id, test_inputs)

        if result.get("status") == "QUALIFIED":
            logger.info("测试通过，结果: %s", result.get("final_result"))
        else:
            logger.info("测试状态: %s", result.get("status"))

        return result

    def generate_test_cases(self, rule_id: str) -> List[Dict[str, Any]]:
        """Generate rudimentary test cases for a rule."""
        logger.info("生成测试用例: %s", rule_id)

        self.engine.reload_rules()
        rule = self.engine.get_rule_info(rule_id)

        if not rule:
            raise ValueError(f"规则不存在: {rule_id}")

        inputs = rule.get("inputs", [])
        test_cases = [
            {
                "name": "基础测试",
                "inputs": {inp["name"]: self._default_input_value(inp) for inp in inputs},
            }
        ]

        tiers = rule.get("tiers", [])
        for i, tier in enumerate(tiers):
            tier_case: Dict[str, Any] = {}
            for spec in inputs:
                name = spec["name"]
                input_type = spec.get("type", "string")
                tier_case[name] = self._value_for_tier(name, input_type, tier)
            test_cases.append({"name": f"档位{i + 1}测试", "inputs": tier_case})

        logger.info("生成 %s 个测试用例", len(test_cases))
        return test_cases

    def run_full_test(self, rule_id: str) -> Dict[str, Any]:
        """Execute generated test cases for a rule."""
        logger.info("运行完整测试: %s", rule_id)

        report = {
            "rule_id": rule_id,
            "test_cases": [],
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }

        for test_case in self.generate_test_cases(rule_id):
            logger.info("执行测试用例: %s", test_case["name"])
            result = self.test_rule(rule_id, test_case["inputs"])
            status = "pass" if result["status"] in {"QUALIFIED", "NOT_QUALIFIED"} else "fail"

            report["test_cases"].append(
                {"name": test_case["name"], "inputs": test_case["inputs"], "result": result, "status": status}
            )
            report["summary"]["total"] += 1
            report["summary"]["passed" if status == "pass" else "failed"] += 1

        logger.info(
            "测试完成: %s/%s 通过",
            report["summary"]["passed"],
            report["summary"]["total"],
        )
        return report

    @staticmethod
    def _default_input_value(spec: Dict[str, Any]) -> Any:
        name = spec["name"]
        input_type = spec.get("type", "string")

        if input_type == "float":
            return 10000.0 if "price" in name else 100.0
        if input_type == "int":
            return 1
        if input_type == "boolean":
            return False
        return "test"

    @staticmethod
    def _value_for_tier(name: str, input_type: str, tier: Dict[str, Any]) -> Any:
        if name in {"invoice_no_tax", "price", "amount", "consumption_amount"}:
            low, high = tier.get("range", [0, None])
            if high is None:
                high = low + 10000 if isinstance(low, (int, float)) else 20000
            return (low + high) / 2 if isinstance(low, (int, float)) else high

        if input_type == "string":
            return "test"
        if input_type == "float":
            return tier.get("threshold", 0) or 100.0
        if input_type == "int":
            return 1
        return DSLPipeline._default_input_value({"name": name, "type": input_type})
