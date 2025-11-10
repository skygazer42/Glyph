"""
测试生成的DSL规则是否有效
使用PolicyEngine加载并执行规则
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import yaml

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.agents.dsl_generator.rule_engine import PolicyEngine


def test_rule_execution():
    """测试规则执行"""

    print("=" * 60)
    print("DSL规则验证测试")
    print("=" * 60)

    # 初始化规则引擎
    print("\n[步骤 1] 初始化规则引擎")
    try:
        engine = PolicyEngine(rule_dir="rules")
        print("[OK] 规则引擎初始化成功")
    except Exception as e:
        print(f"[FAIL] 规则引擎初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 列出所有规则
    print("\n[步骤 2] 列出所有规则")
    try:
        rules = engine.list_rules()
        print(f"[OK] 找到 {len(rules)} 个规则:")
        for rule in rules:
            print(f"  - {rule['rule_id']}: {rule.get('title', 'N/A')}")
    except Exception as e:
        print(f"[FAIL] 列出规则失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试规则1: 消费券
    print("\n" + "=" * 60)
    print("[步骤 3] 测试规则: Rule_Jinan_消费券_2025")
    print("=" * 60)

    rule_id = "Rule_Jinan_消费券_2025"

    # 获取规则详情
    print(f"\n[3.1] 获取规则详情...")
    try:
        rule_info = engine.get_rule_info(rule_id)
        if rule_info:
            print(f"[OK] 规则详情:")
            print(f"  - rule_id: {rule_info.get('rule_id')}")
            print(f"  - title: {rule_info.get('title')}")
            print(f"  - valid_period: {rule_info.get('valid_period')}")
            print(f"  - tiers: {len(rule_info.get('tiers', []))} 个档位")
        else:
            print(f"[FAIL] 规则不存在: {rule_id}")
    except Exception as e:
        print(f"[FAIL] 获取规则详情失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试不同的输入
    test_cases = [
        {"消费金额": 150, "expected": "满100减20或其他档位"},
        {"消费金额": 250, "expected": "满200减40或其他档位"},
        {"消费金额": 350, "expected": "满300减60或其他档位"},
        {"消费金额": 50, "expected": "不满足任何档位"},
    ]

    print(f"\n[3.2] 测试规则执行...")
    for i, test_case in enumerate(test_cases, 1):
        inputs = {k: v for k, v in test_case.items() if k != "expected"}
        expected = test_case["expected"]

        print(f"\n  测试用例 {i}: {inputs}")
        print(f"  期望结果: {expected}")

        try:
            result = engine.execute(rule_id, inputs)
            print(f"  [OK] 执行结果:")
            print(f"    - status: {result.get('status')}")
            print(f"    - final_result: {result.get('final_result')}")
            if 'trace' in result:
                print(f"    - trace: {result.get('trace')[:200]}...")
        except Exception as e:
            print(f"  [FAIL] 执行失败: {e}")

    # 测试规则2: 家电补贴
    print("\n" + "=" * 60)
    print("[步骤 4] 测试规则: Rule_JiNan_补贴_2025")
    print("=" * 60)

    rule_id = "Rule_JiNan_补贴_2025"

    # 获取规则详情
    print(f"\n[4.1] 获取规则详情...")
    try:
        rule_info = engine.get_rule_info(rule_id)
        if rule_info:
            print(f"[OK] 规则详情:")
            print(f"  - rule_id: {rule_info.get('rule_id')}")
            print(f"  - title: {rule_info.get('title')}")
            print(f"  - valid_period: {rule_info.get('valid_period')}")
            print(f"  - tiers: {len(rule_info.get('tiers', []))} 个档位")
            print(f"  - limits: {rule_info.get('limits')}")
        else:
            print(f"[FAIL] 规则不存在: {rule_id}")
    except Exception as e:
        print(f"[FAIL] 获取规则详情失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试不同的输入
    test_cases = [
        {"能效等级": "一级能效", "商品价格": 5000, "expected": "5000 * 20% = 1000元"},
        {"能效等级": "二级能效", "商品价格": 10000, "expected": "10000 * 15% = 1500元"},
        {"能效等级": "一级能效", "商品价格": 20000, "expected": "最高3000元"},
    ]

    print(f"\n[4.2] 测试规则执行...")
    for i, test_case in enumerate(test_cases, 1):
        inputs = {k: v for k, v in test_case.items() if k != "expected"}
        expected = test_case["expected"]

        print(f"\n  测试用例 {i}: {inputs}")
        print(f"  期望结果: {expected}")

        try:
            result = engine.execute(rule_id, inputs)
            print(f"  [OK] 执行结果:")
            print(f"    - status: {result.get('status')}")
            print(f"    - final_result: {result.get('final_result')}")
            if 'trace' in result:
                print(f"    - trace: {result.get('trace')[:200]}...")
        except Exception as e:
            print(f"  [FAIL] 执行失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_rule_execution()
