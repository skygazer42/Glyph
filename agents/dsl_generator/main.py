"""
DSL 转换系统主程序（优化版）
使用项目配置的 LLM 将政策文档转换为 DSL
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.dsl_generator.document_parser import DocumentParser
from agents.dsl_generator.dsl_extractor import DSLExtractor  # 使用优化版
from agents.dsl_generator.dsl_generator import DSLGenerator
from agents.dsl_generator.rule_engine import PolicyEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DSLPipeline:
    """DSL 转换管道（优化版）"""

    def __init__(self,
                 data_dir: str = "data/guize",
                 output_dir: str = "rules",
                 use_project_config: bool = True):
        """
        初始化 DSL 转换管道

        Args:
            data_dir: 输入文档目录
            output_dir: DSL 输出目录
            use_project_config: 是否使用项目配置的 LLM
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.use_project_config = use_project_config

        # 初始化各模块
        self.parser = DocumentParser()
        self.extractor = DSLExtractor(use_project_config=use_project_config)
        self.generator = DSLGenerator(output_dir=str(output_dir))
        self.engine = PolicyEngine(rule_dir=str(output_dir))

        # 如果使用项目配置，显示配置信息
        if use_project_config:
            try:
                from config.settings import settings
                logger.info(f"使用项目 LLM 配置:")
                logger.info(f"  模型: {settings.model.llm_model_name}")
                logger.info(f"  API: {settings.model.llm_base_url}")
            except ImportError:
                logger.warning("无法导入项目配置，将使用内置规则提取")

    def process_document(self, file_path: str, save: bool = True) -> Dict[str, Any]:
        """
        处理单个文档

        Args:
            file_path: 文档路径
            save: 是否保存生成的 DSL

        Returns:
            处理结果
        """
        result = {
            'file': file_path,
            'status': 'processing',
            'dsl_file': None,
            'errors': []
        }

        try:
            logger.info(f"开始��理文档: {file_path}")

            # 1. 解析文档
            logger.info("步骤 1: 解析文档")
            text = self.parser.parse(file_path)
            processed = self.parser.preprocess_text(text)
            logger.info(f"  提取到文本长度: {len(text)} 字符")

            if processed['metadata'].get('title'):
                logger.info(f"  识别到标题: {processed['metadata']['title']}")

            # 2. 提取规则
            logger.info("步骤 2: 提取结构化规则")
            if self.use_project_config:
                logger.info("  使用项目 LLM 进行智能提取...")
            else:
                logger.info("  使用规则引擎进行提取...")

            dsl_data = self.extractor.extract(text, processed['metadata'])

            if dsl_data.get('rule_id'):
                logger.info(f"  生成规则 ID: {dsl_data['rule_id']}")

            # 3. 验证提取的数据
            logger.info("步骤 3: 验证提取的数据")
            validation_errors = self.extractor.validate_dsl(dsl_data)
            if validation_errors:
                logger.warning(f"  验证警告: {validation_errors}")
                result['errors'].extend(validation_errors)
            else:
                logger.info("  数据验证通过")

            # 4. 生成 DSL YAML
            logger.info("步骤 4: 生成 DSL YAML")
            yaml_content = self.generator.generate(
                dsl_data,
                auto_detect=True,
                context=processed.get('metadata', {})
            )
            logger.info(f"  生成 YAML 长度: {len(yaml_content)} 字符")

            # 5. 保存文件
            if save:
                logger.info("步骤 5: 保存 DSL 文件")
                dsl_file = self.generator.save(yaml_content)
                result['dsl_file'] = str(dsl_file)
                logger.info(f"  文件保存至: {dsl_file}")

            result['status'] = 'success'
            result['dsl_data'] = dsl_data
            result['yaml_content'] = yaml_content

            logger.info(f"文档处理成功: {file_path}")

        except Exception as e:
            logger.error(f"处理文档失败: {e}")
            result['status'] = 'error'
            result['errors'].append(str(e))

        return result

    def process_directory(self, directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        处理目录下的所有文档

        Args:
            directory: 目录路径，默认使用 data_dir

        Returns:
            处理结果列表
        """
        dir_path = Path(directory) if directory else self.data_dir
        results = []

        logger.info(f"批量处理目录: {dir_path}")

        # 支持的文件格式
        patterns = ['*.docx', '*.txt', '*.doc', '*.pdf']

        file_count = 0
        for pattern in patterns:
            for file_path in dir_path.glob(pattern):
                file_count += 1
                logger.info(f"处理文件 [{file_count}]: {file_path.name}")
                result = self.process_document(str(file_path))
                results.append(result)

        logger.info(f"批量处理完成: 共处理 {file_count} 个文件")
        success_count = sum(1 for r in results if r['status'] == 'success')
        logger.info(f"成功: {success_count}/{file_count}")

        return results

    def test_rule(self, rule_id: str, test_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        测试生成的规则

        Args:
            rule_id: 规则ID
            test_inputs: 测试输入

        Returns:
            执行结果
        """
        logger.info(f"测试规则: {rule_id}")
        logger.info(f"测试输入: {test_inputs}")

        # 重新加载规则
        self.engine.reload_rules()

        # 执行规则
        result = self.engine.execute(rule_id, test_inputs)

        if result.get('status') == 'QUALIFIED':
            logger.info(f"测试通过，结果: {result.get('final_result')}")
        else:
            logger.info(f"测试状态: {result.get('status')}")

        return result

    def generate_test_cases(self, rule_id: str) -> List[Dict[str, Any]]:
        """
        为规则生成测试用例

        Args:
            rule_id: 规则ID

        Returns:
            测试用例列表
        """
        rule = self.engine.get_rule_info(rule_id)
        if not rule:
            logger.warning(f"规则不存在: {rule_id}")
            return []

        test_cases = []

        # 基于输入参数生成测试用例
        inputs = rule.get('inputs', [])

        # 测试用例1: 最小值测试
        case1 = {}
        for input_spec in inputs:
            name = input_spec['name']
            input_type = input_spec['type']
            if input_type == 'float':
                case1[name] = 1000.0
            elif input_type == 'int':
                case1[name] = 1
            elif input_type == 'string':
                case1[name] = 'test'
        test_cases.append({'name': '最小值测试', 'inputs': case1})

        # 测试用例2: 中间值测试
        case2 = {}
        for input_spec in inputs:
            name = input_spec['name']
            input_type = input_spec['type']
            if input_type == 'float':
                case2[name] = 50000.0
            elif input_type == 'int':
                case2[name] = 2
            elif input_type == 'string':
                if name == 'category':
                    case2[name] = '空调'
                elif name == 'vehicle_type':
                    case2[name] = 'NEV'
                else:
                    case2[name] = 'test'
        test_cases.append({'name': '中间值测试', 'inputs': case2})

        # 测试用例3: 最大值测试
        case3 = {}
        for input_spec in inputs:
            name = input_spec['name']
            input_type = input_spec['type']
            if input_type == 'float':
                case3[name] = 500000.0
            elif input_type == 'int':
                case3[name] = 3
            elif input_type == 'string':
                case3[name] = 'premium'
        test_cases.append({'name': '最大值测试', 'inputs': case3})

        # 如果有分档，为每个档位生成测试用例
        tiers = rule.get('tiers', [])
        for i, tier in enumerate(tiers):
            tier_case = {}
            for input_spec in inputs:
                name = input_spec['name']
                input_type = input_spec['type']
                if name in ['invoice_no_tax', 'price', 'amount']:
                    # 使用档位的中间值
                    low = tier['range'][0] if tier['range'][0] else 0
                    high = tier['range'][1] if tier['range'][1] else low * 2
                    tier_case[name] = (low + high) / 2 if high else low + 10000
                elif input_type == 'string':
                    tier_case[name] = 'test'
                else:
                    tier_case[name] = 1
            test_cases.append({'name': f'档位{i+1}测试', 'inputs': tier_case})

        logger.info(f"生成了 {len(test_cases)} 个测试用例")
        return test_cases

    def run_full_test(self, rule_id: str) -> Dict[str, Any]:
        """
        运行完整测试

        Args:
            rule_id: 规则ID

        Returns:
            测试报告
        """
        logger.info(f"运行完整测试: {rule_id}")

        report = {
            'rule_id': rule_id,
            'test_cases': [],
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0
            }
        }

        # 生成测试用例
        test_cases = self.generate_test_cases(rule_id)

        # 执行每个测试用例
        for test_case in test_cases:
            logger.info(f"执行测试用例: {test_case['name']}")
            result = self.test_rule(rule_id, test_case['inputs'])

            test_result = {
                'name': test_case['name'],
                'inputs': test_case['inputs'],
                'result': result,
                'status': 'pass' if result['status'] in ['QUALIFIED', 'NOT_QUALIFIED'] else 'fail'
            }

            report['test_cases'].append(test_result)
            report['summary']['total'] += 1

            if test_result['status'] == 'pass':
                report['summary']['passed'] += 1
            else:
                report['summary']['failed'] += 1

        logger.info(f"测试完成: {report['summary']['passed']}/{report['summary']['total']} 通过")
        return report


def main():
    """主程序入口"""
    # 创建管道（使用项目配置）
    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/rules",
        use_project_config=True  # 使用项目配置的 LLM
    )

    # 处理所有文档
    print("=" * 50)
    print("DSL 自动生成系统（使用项目配置）")
    print("=" * 50)

    results = pipeline.process_directory()

    # 显示处理结果
    print("\n处理结果:")
    print("-" * 50)

    for result in results:
        status_mark = "[OK]" if result['status'] == 'success' else "[ERROR]"
        print(f"{status_mark} {result['file']}")

        if result['dsl_file']:
            print(f"   生成: {result['dsl_file']}")

        if result['errors']:
            print(f"   错误: {', '.join(result['errors'])}")

    # 测试生成的规则
    print("\n" + "=" * 50)
    print("测试生成的规则")
    print("=" * 50)

    # 重新加载规则
    pipeline.engine.reload_rules()

    # 列出所有规则
    rules = pipeline.engine.list_rules()
    print(f"\n找到 {len(rules)} 个规则:")
    for rule in rules:
        active = "[ACTIVE]" if rule['is_active'] else "[INACTIVE]"
        print(f"{active} {rule['rule_id']} - {rule['title']}")

    # 运行测试
    if rules:
        rule_id = rules[0]['rule_id']
        print(f"\n测试规则: {rule_id}")
        print("-" * 50)

        test_report = pipeline.run_full_test(rule_id)

        print(f"测试结果: {test_report['summary']['passed']}/{test_report['summary']['total']} 通过")

        for test_case in test_report['test_cases'][:3]:  # 显示前3个测试用例
            print(f"\n测试用例: {test_case['name']}")
            print(f"输入: {test_case['inputs']}")
            print(f"状态: {test_case['result']['status']}")
            print(f"结果: {test_case['result'].get('final_result', 'N/A')}")


if __name__ == "__main__":
    main()
