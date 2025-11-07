"""
DSL 生成器快速演示
展示如何一键将政策文档转换为 DSL
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from agents.dsl_generator.main import DSLPipeline


def demo():
    print("=" * 70)
    print(" " * 15 + "DSL 自动生成系统演示")
    print("=" * 70)
    print("\n此系统可以将政策文档（.docx/.txt）自动转换为可执行的规则代码")
    print("-" * 70)

    # 1. 创建示例政策文档
    print("\n[步骤 1] 准备政策文档")
    print("-" * 40)

    test_file = "F:/pythonproject/gov/data/guize/demo_policy.txt"
    test_content = """济南市2025年家电消费补贴实施方案
济商务字〔2025〕88号

一、补贴标准
购买一级能效家电，补贴销售价格的20%；
购买二级能效家电，补贴销售价格的15%；
单件商品补贴最高不超过2000元。

二、补贴范围
空调：每人限购3台
冰箱：每人限购2台
其他家电：每类限购1台

三、活动时间
2025年1月1日至2025年12月31日"""

    Path(test_file).parent.mkdir(exist_ok=True)
    Path(test_file).write_text(test_content, encoding='utf-8')
    print(f"[OK] 创建示例文档: {test_file}")

    # 2. 初始化转换系统
    print("\n[步骤 2] 初始化 DSL 转换系统")
    print("-" * 40)

    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/rules"
    )
    print("[OK] 系统初始化完成")

    # 3. 转换文档为 DSL
    print("\n[步骤 3] 将文档转换为 DSL")
    print("-" * 40)

    result = pipeline.process_document(test_file)

    if result['status'] == 'success':
        print("[OK] 转换成功!")
        print(f"   生成的 DSL 文件: {result['dsl_file']}")

        # 显示部分 DSL 内容
        if 'yaml_content' in result:
            print("\n[DSL 内容（部分）:]")
            print("-" * 40)
            lines = result['yaml_content'].split('\n')[:20]
            for line in lines:
                print(f"   {line}")
            print("   ...")

    else:
        print(f"[ERROR] 转换失败: {result.get('errors', ['未知错误'])}")

    # 4. 测试生成的规则
    print("\n[步骤 4] 测试生成的规则")
    print("-" * 40)

    if result['status'] == 'success' and 'dsl_data' in result:
        rule_id = result['dsl_data'].get('rule_id', 'Rule_Jinan_Policy_2025')

        # 测试用例1：一级能效空调
        test1 = {
            'price': 5000.0,
            'energy_level': 1,
            'category': '空调'
        }

        print(f"\n测试用例 1: 一级能效空调，价格 {test1['price']} 元")
        result1 = pipeline.test_rule(rule_id, test1)
        if result1.get('status') in ['QUALIFIED', 'NOT_QUALIFIED']:
            print(f"   状态: {result1['status']}")
            print(f"   补贴金额: {result1.get('final_result', 0)} 元")

        # 测试用例2：二级能效冰箱
        test2 = {
            'price': 15000.0,
            'energy_level': 2,
            'category': '冰箱'
        }

        print(f"\n测试用例 2: 二级能效冰箱，价格 {test2['price']} 元")
        result2 = pipeline.test_rule(rule_id, test2)
        if result2.get('status') in ['QUALIFIED', 'NOT_QUALIFIED']:
            print(f"   状态: {result2['status']}")
            print(f"   补贴金额: {result2.get('final_result', 0)} 元")

    # 5. 总结
    print("\n" + "=" * 70)
    print(" " * 20 + "演示完成")
    print("=" * 70)
    print("\n系统特性:")
    print("  * 自动解析政策文档（支持 .docx/.txt/.pdf）")
    print("  * 智能提取政策要素（金额、比例、时间、限制）")
    print("  * 生成标准化 DSL 规则（YAML 格式）")
    print("  * 可直接执行计算（无需编程）")
    print("  * 支持批量处理和热更新")
    print("\n提示: 将您的政策文档放入 data/guize 目录，运行程序即可自动转换!")


if __name__ == "__main__":
    try:
        demo()
    except Exception as e:
        print(f"\n[ERROR] 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()