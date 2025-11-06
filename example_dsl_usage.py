"""
DSL 生成器使用示例
演示如何将政策文档转换为 DSL
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from agents.dsl_generator.main import DSLPipeline


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例1: 基本使用 - 处理单个文档")
    print("=" * 60)

    # 创建 DSL 转换管道
    pipeline = DSLPipeline(
        data_dir="data/guize",
        output_dir="rules"
    )

    # 处理单个文档
    result = pipeline.process_document("data/guize/消费活动.docx")

    if result['status'] == 'success':
        print(f"✅ 转换成功!")
        print(f"   输入文件: {result['file']}")
        print(f"   输出文件: {result['dsl_file']}")

        # 显示生成的 YAML 内容（前500字符）
        print("\n生成的 DSL (部分):")
        print("-" * 40)
        print(result['yaml_content'][:500] + "...")
    else:
        print(f"❌ 转换失败: {result['errors']}")


def example_batch_processing():
    """批量处理示例"""
    print("\n" + "=" * 60)
    print("示例2: 批量处理 - 处理整个目录")
    print("=" * 60)

    pipeline = DSLPipeline(
        data_dir="data/guize",
        output_dir="rules"
    )

    # 批量处理目录下所有文档
    results = pipeline.process_directory()

    # 统计结果
    total = len(results)
    success = sum(1 for r in results if r['status'] == 'success')

    print(f"\n处理完成: {success}/{total} 成功")

    for result in results:
        status = "✅" if result['status'] == 'success' else "❌"
        file_name = Path(result['file']).name
        print(f"{status} {file_name}")


def example_rule_testing():
    """规则测试示例"""
    print("\n" + "=" * 60)
    print("示例3: 规则测试 - 验证生成的规则")
    print("=" * 60)

    pipeline = DSLPipeline(output_dir="rules")

    # 列出所有规则
    rules = pipeline.engine.list_rules()
    print(f"找到 {len(rules)} 个规则:")
    for rule in rules:
        print(f"  - {rule['rule_id']}: {rule['title']}")

    if rules:
        # 测试第一个规则
        rule_id = rules[0]['rule_id']
        print(f"\n测试规则: {rule_id}")

        # 创建测试输入
        test_inputs = {
            'price': 15000.0,
            'energy_level': 1,
            'category': '空调'
        }

        # 执行规则
        result = pipeline.test_rule(rule_id, test_inputs)

        print(f"\n测试输入: {test_inputs}")
        print(f"执行状态: {result['status']}")
        print(f"计算结果: {result.get('final_result', 'N/A')}")

        # 显示计算轨迹
        if 'explainability_trace' in result:
            print("\n计算轨迹:")
            for step in result['explainability_trace']:
                print(f"  {step['step']}. {step['description']}")


def example_template_generation():
    """模板生成示例"""
    print("\n" + "=" * 60)
    print("示例4: 使用模板 - 快速生成标准规则")
    print("=" * 60)

    from agents.dsl_generator import DSLGenerator

    generator = DSLGenerator(output_dir="rules")

    # 生成家电补贴规则
    yaml_content = generator.generate_from_template(
        'appliance',
        rule_id='Rule_Custom_Appliance_2025',
        doc_id='自定义文号〔2025〕1号',
        title='自定义家电补贴政策',
        base_rate=0.2,  # 20% 基础补贴
        extra_rate=0.1,  # 10% 额外补贴
        cap=3000  # 最高补贴3000元
    )

    print("生成的家电补贴规则:")
    print("-" * 40)
    print(yaml_content[:600] + "...")

    # 保存规则
    file_path = generator.save(yaml_content, 'custom_appliance_rule.yaml')
    print(f"\n规则已保存到: {file_path}")


def example_custom_processing():
    """自定义处理示例"""
    print("\n" + "=" * 60)
    print("示例5: 自定义处理 - 完整控制流程")
    print("=" * 60)

    from agents.dsl_generator import (
        DocumentParser,
        DSLExtractor,
        DSLGenerator,
        PolicyEngine
    )

    # 1. 解析文档
    parser = DocumentParser()
    text = """
    济南市新能源汽车购置补贴政策

    补贴标准：
    - 10万元以下：补贴5000元
    - 10-20万元：补贴8000元
    - 20-30万元：补贴10000元
    - 30万元以上：补贴15000元

    活动时间：2025年1月1日至2025年6月30日
    每人限购1辆
    """

    # 2. 预处理文本
    processed = parser.preprocess_text(text)
    print(f"提取到 {len(processed['sections'])} 个章节")
    print(f"提取到金额: {processed['metadata'].get('amounts', [])}")

    # 3. 提取结构化数据
    extractor = DSLExtractor()
    dsl_data = extractor._extract_with_rules(text)

    import json
    data = json.loads(dsl_data)
    print(f"\n提取的规则ID: {data.get('rule_id')}")

    # 4. 生成 DSL
    generator = DSLGenerator(output_dir="rules")
    yaml_content = generator.generate(data)

    # 5. 保存并执行
    rule_file = generator.save(yaml_content)
    print(f"\n规则文件: {rule_file}")

    # 6. 测试执行
    engine = PolicyEngine(rule_dir="rules")
    engine.reload_rules()

    test_result = engine.execute(
        data['rule_id'],
        {'invoice_no_tax': 150000, 'vehicle_type': 'NEV'}
    )

    print(f"测试结果: {test_result.get('final_result', 'N/A')}")


def example_auto_test():
    """自动测试示例"""
    print("\n" + "=" * 60)
    print("示例6: 自动测试 - 生成并运行测试用例")
    print("=" * 60)

    pipeline = DSLPipeline(output_dir="rules")

    # 获取第一个规则
    rules = pipeline.engine.list_rules()
    if not rules:
        print("没有找到规则")
        return

    rule_id = rules[0]['rule_id']
    print(f"测试规则: {rule_id}")

    # 生成测试用例
    test_cases = pipeline.generate_test_cases(rule_id)
    print(f"\n生成了 {len(test_cases)} 个测试用例:")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test_case['name']}")
        print(f"  输入: {test_case['inputs']}")

        # 执行测试
        result = pipeline.test_rule(rule_id, test_case['inputs'])
        print(f"  状态: {result['status']}")
        print(f"  结果: {result.get('final_result', 'N/A')}")

    # 运行完整测试报告
    print("\n" + "-" * 40)
    print("生成完整测试报告:")
    test_report = pipeline.run_full_test(rule_id)

    print(f"总测试用例: {test_report['summary']['total']}")
    print(f"通过: {test_report['summary']['passed']}")
    print(f"失败: {test_report['summary']['failed']}")


def main():
    """运行所有示例"""
    examples = [
        ("基本使用", example_basic_usage),
        ("批量处理", example_batch_processing),
        ("规则测试", example_rule_testing),
        ("模板生成", example_template_generation),
        ("自定义处理", example_custom_processing),
        ("自动测试", example_auto_test)
    ]

    print("🚀 DSL 生成器使用示例")
    print("=" * 60)
    print("选择示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print(f"  0. 运行所有示例")
    print("=" * 60)

    try:
        choice = input("请选择 (0-6): ").strip()

        if choice == '0':
            for name, func in examples:
                print(f"\n\n{'='*20} {name} {'='*20}")
                try:
                    func()
                except Exception as e:
                    print(f"示例执行失败: {e}")
        elif choice.isdigit() and 1 <= int(choice) <= len(examples):
            examples[int(choice)-1][1]()
        else:
            print("无效选择")
    except KeyboardInterrupt:
        print("\n\n已取消")


if __name__ == "__main__":
    main()