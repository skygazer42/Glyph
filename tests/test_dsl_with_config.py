"""
DSL 生成器测试（使用项目配置）
展示如何使用项目配置的 LLM 生成 DSL
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from agents.dsl_generator.main_v2 import DSLPipeline


def test_with_project_config():
    """测试使用项目配置"""
    print("=" * 70)
    print("测试 DSL 生成器（使用项目配置）")
    print("=" * 70)

    # 检查项目配置
    try:
        from config import settings
        print("\n[项目配置信息]")
        print(f"  LLM 模型: {settings.model.llm_model_name}")
        print(f"  API 地址: {settings.model.llm_base_url}")
        print(f"  温度参数: {settings.model.llm_temperature}")
        print("")
    except ImportError:
        print("\n[警告] 无法加载项目配置，将使用规则提取")

    # 创建测试文档
    test_file = "F:/pythonproject/gov/data/guize/test_with_llm.txt"
    test_content = """济南市2025年新能源汽车购置补贴政策
济南市商务局 济商发〔2025〕15号

第一条 补贴对象
在济南市购买新能源汽车的个人消费者。

第二条 补贴标���
按照车辆购置价格分档补贴：
- 10万元以下（含）：补贴5000元
- 10-20万元（含）：补贴8000元
- 20-30万元（含）：补贴12000元
- 30万元以上：补贴15000元

第三条 申请条件
1. 购车人须为济南市户籍或在济南缴纳社保满一年
2. 车辆须在济南市内上牌
3. 每人限申请一次补贴

第四条 活动时间
2025年3月1日至2025年9月30日"""

    Path(test_file).parent.mkdir(exist_ok=True)
    Path(test_file).write_text(test_content, encoding='utf-8')

    # 创建管道（使用项目配置）
    print("\n[步骤 1] 初始化 DSL 转换系统")
    print("-" * 40)
    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/rules",
        use_project_config=True  # 使用项目配置
    )
    print("[OK] 系统初始化完成（使用项目 LLM）")

    # 处理文档
    print("\n[步骤 2] 处理政策文档")
    print("-" * 40)
    result = pipeline.process_document(test_file)

    if result['status'] == 'success':
        print("[OK] 文档处理成功!")
        print(f"  生成的 DSL 文件: {result['dsl_file']}")

        # 显示部分 DSL 内容
        if 'yaml_content' in result:
            print("\n[DSL 内容预览]")
            print("-" * 40)
            lines = result['yaml_content'].split('\n')[:25]
            for line in lines:
                print(f"  {line}")
            if len(result['yaml_content'].split('\n')) > 25:
                print("  ...")

        # 测试规则
        if 'dsl_data' in result:
            rule_id = result['dsl_data'].get('rule_id')
            print(f"\n[步骤 3] 测试规则: {rule_id}")
            print("-" * 40)

            # 测试案例
            test_cases = [
                {
                    'name': '低价车（8万）',
                    'inputs': {'invoice_no_tax': 80000, 'vehicle_type': 'NEV'}
                },
                {
                    'name': '中价车（15万）',
                    'inputs': {'invoice_no_tax': 150000, 'vehicle_type': 'NEV'}
                },
                {
                    'name': '高价车（25万）',
                    'inputs': {'invoice_no_tax': 250000, 'vehicle_type': 'NEV'}
                }
            ]

            for test in test_cases:
                print(f"\n测试: {test['name']}")
                result = pipeline.test_rule(rule_id, test['inputs'])
                print(f"  输入: {test['inputs']}")
                print(f"  状态: {result.get('status', 'N/A')}")
                print(f"  补贴: {result.get('final_result', 'N/A')}元")

    else:
        print(f"[ERROR] 处理失败: {result.get('errors', ['未知错误'])}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


def test_without_project_config():
    """测试不使用项目配置（纯规则提取）"""
    print("\n" + "=" * 70)
    print("测试 DSL 生成器（不使用项目配置）")
    print("=" * 70)

    # 创建管道（不使用项目配置）
    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/rules",
        use_project_config=False  # 不使用项目配置
    )
    print("[INFO] 使用内置规则提取（不调用 LLM）")

    # 创建简单测试文档
    test_file = "F:/pythonproject/gov/data/guize/test_rule_only.txt"
    test_content = """家电补贴政策
补贴标准：补贴销售价格的15%，最高不超过2000元
活动时间：2025年1月1日至2025年12月31日"""

    Path(test_file).write_text(test_content, encoding='utf-8')

    # 处理文档
    result = pipeline.process_document(test_file)

    if result['status'] == 'success':
        print("[OK] 规则提取成功")
        if 'dsl_data' in result:
            print(f"  规则ID: {result['dsl_data'].get('rule_id')}")
            print(f"  补贴比例: {result['dsl_data'].get('calc', {}).get('base_rate')}")
    else:
        print(f"[ERROR] 提取失败: {result.get('errors')}")


def compare_modes():
    """比较两种模式"""
    print("\n" + "=" * 70)
    print("模式对比")
    print("=" * 70)

    print("\n[使用项目配置的优势]")
    print("  * 智能提取：使用 LLM 理解复杂政策文本")
    print("  * 高准确度：能识别更多政策要素")
    print("  * 灵活处理：适应各种文档格式")

    print("\n[纯规则提取的优势]")
    print("  * 无需 API：不依赖外部服务")
    print("  * 快速处理：基于规则的快速匹配")
    print("  * 成本节省：不消耗 API 调用")

    print("\n[建议]")
    print("  * 标准化文档：使用规则提取")
    print("  * 复杂文档：使用项目配置（LLM）")
    print("  * 混合模式：优先 LLM，失败时降级到规则")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DSL 生成器测试')
    parser.add_argument('--mode', choices=['all', 'llm', 'rule', 'compare'],
                        default='all', help='测试模式')

    args = parser.parse_args()

    if args.mode == 'all':
        test_with_project_config()
        test_without_project_config()
        compare_modes()
    elif args.mode == 'llm':
        test_with_project_config()
    elif args.mode == 'rule':
        test_without_project_config()
    elif args.mode == 'compare':
        compare_modes()