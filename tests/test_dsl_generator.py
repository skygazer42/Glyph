"""
DSL 生成器测试程序
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.dsl_generator import (
    DocumentParser,
    DSLExtractor,
    DSLGenerator,
    PolicyEngine
)
from agents.dsl_generator.main import DSLPipeline


def test_document_parser():
    """测试文档解析器"""
    print("\n测试文档解析器")
    print("-" * 40)

    parser = DocumentParser()

    # 创建测试文档
    test_file = "F:/pythonproject/gov/data/guize/test_policy.txt"
    test_content = """
济南市2025年家电以旧换新补贴实施细则
济商务字〔2025〕1号

第一条 为促进消费升级，支持绿色家电消费，制定本细则。

第二条 补贴标准：
1. 一级能效家电：补贴销售价格的20%
2. 二级能效家电：补贴销售价格的15%
3. 其他家电：补贴销售价格的10%
4. 单件商品最高补贴2000元

第三条 补贴范围：
- 空调：每人限购3台
- 冰箱：每人限购2台
- 其他家电：每类限购1台

第四条 活动时间：2025年1月1日至2025年12月31日

第五条 申请材料：
1. 购买发票
2. 身份证明
3. 旧家电回收证明
"""

    # 保存测试文件
    Path(test_file).write_text(test_content, encoding='utf-8')

    try:
        # 解析文档
        text = parser.parse(test_file)
        print("✅ 文档解析成功")
        print(f"   文本长度: {len(text)} 字符")

        # 预处理文本
        processed = parser.preprocess_text(text)
        print("✅ 文本预处理成功")
        print(f"   提取到标题: {processed['metadata'].get('title', '无')}")
        print(f"   提取到文号: {processed['metadata'].get('doc_id', '无')}")
        print(f"   提取到章节: {len(processed['sections'])} 个")

        # 提取规则
        rules = parser.extract_rules(text)
        print(f"✅ 提取到规则: {len(rules)} 个")

        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_dsl_extractor():
    """测试 DSL 提取器"""
    print("\n测试 DSL 提取器")
    print("-" * 40)

    extractor = DSLExtractor()

    test_text = """
济南市家电以旧换新补贴政策
补贴标准：一级能效补贴20%，二级能效补贴15%，最高不超过2000元
活动时间：2025年1月1日至2025年12月31日
"""

    try:
        # 基于规则提取（不依赖 LLM）
        result = extractor._extract_with_rules(test_text)
        print("✅ 规则提取成功")

        import json
        data = json.loads(result)
        print(f"   规则ID: {data.get('rule_id', '无')}")
        print(f"   标题: {data.get('title', '无')}")
        print(f"   补贴比例: {data.get('calc', {}).get('base_rate', '无')}")

        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_dsl_generator():
    """测试 DSL 生成器"""
    print("\n测试 DSL 生成器")
    print("-" * 40)

    generator = DSLGenerator(output_dir="F:/pythonproject/gov/test_rules")

    # 测试数据
    test_data = {
        'rule_id': 'Rule_Test_Appliance_2025',
        'doc_id': '测试文号〔2025〕1号',
        'title': '测试家电补贴政策',
        'valid_start': '2025-01-01',
        'valid_end': '2025-12-31',
        'inputs': [
            {'name': 'price', 'type': 'float', 'required': True},
            {'name': 'energy_level', 'type': 'int', 'required': False}
        ],
        'limits': {
            'per_item_cap': 2000
        },
        'calc': {
            'base_rate': 0.15,
            'subsidy': 'min(price * base_rate, per_item_cap)'
        },
        'output': {
            'status': 'QUALIFIED',
            'final_result': '{{ calc.subsidy }}',
            'trace_template': '- 补贴计算: {{ price }} × {{ calc.base_rate }} = {{ calc.subsidy }}'
        }
    }

    try:
        # 生成 YAML
        yaml_content = generator.generate(test_data)
        print("✅ YAML 生成成功")

        # 保存文件
        file_path = generator.save(yaml_content)
        print(f"✅ 文件保存成功: {file_path}")

        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_policy_engine():
    """测试规则引擎"""
    print("\n测试规则引擎")
    print("-" * 40)

    engine = PolicyEngine(rule_dir="F:/pythonproject/gov/test_rules")

    # 测试输入
    test_inputs = {
        'price': 10000.0,
        'energy_level': 1
    }

    try:
        # 列出规则
        rules = engine.list_rules()
        print(f"✅ 找到 {len(rules)} 个规则")

        if rules:
            # 执行第一个规则
            rule_id = rules[0]['rule_id']
            result = engine.execute(rule_id, test_inputs)

            print(f"✅ 规则执行成功")
            print(f"   状态: {result['status']}")
            print(f"   结果: {result.get('final_result', 'N/A')}")

            if 'explainability_trace' in result:
                print("   执行轨迹:")
                for trace in result['explainability_trace']:
                    print(f"     {trace['step']}. {trace['description']}")

        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_full_pipeline():
    """测试完整管道"""
    print("\n测试完整管道")
    print("-" * 40)

    # 创建测试文档
    test_file = "F:/pythonproject/gov/data/guize/test_complete.txt"
    test_content = """
济南市2025年消费促进补贴实施方案
济商发〔2025〕10号

一、补贴标准
满100元减10元，满200元减25元，满500元减70元，满1000元减150元
单笔最高补贴500元，每人每月限享受3次

二、活动时间
2025年3月1日至2025年5月31日

三、适用范围
全市参与活动的商场、超市、餐饮店
"""

    Path(test_file).write_text(test_content, encoding='utf-8')

    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/test_rules"
    )

    try:
        # 处理文档
        result = pipeline.process_document(test_file)

        if result['status'] == 'success':
            print("✅ 文档处理成功")
            print(f"   生成文件: {result['dsl_file']}")

            # 测试生成的规则
            if 'dsl_data' in result and 'rule_id' in result['dsl_data']:
                rule_id = result['dsl_data']['rule_id']
                test_result = pipeline.test_rule(rule_id, {'amount': 500.0, 'merchant_type': 'mall'})
                print(f"✅ 规则测试成功")
                print(f"   测试结果: {test_result.get('status', 'N/A')}")
        else:
            print(f"❌ 文档处理失败: {result.get('errors', [])}")

        return result['status'] == 'success'
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("DSL 生成系统测试")
    print("=" * 50)

    tests = [
        ("文档解析器", test_document_parser),
        ("DSL 提取器", test_dsl_extractor),
        ("DSL 生成器", test_dsl_generator),
        ("规则引擎", test_policy_engine),
        ("完整管道", test_full_pipeline)
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"测试 {name} 出现异常: {e}")
            results.append((name, False))

    # 显示测试总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)

    total = len(results)
    passed = sum(1 for _, success in results if success)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)