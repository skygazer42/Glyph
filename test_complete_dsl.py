"""
完整测试：DSL生成和执行
"""
import os
import sys
import json
import requests
from pathlib import Path

API_URL = "http://localhost:8000"

print("=" * 80)
print("完整测试：DSL生成和执行")
print("=" * 80)

# 测试用例
test_cases = [
    {
        "name": "消费券政策",
        "text": """
2025年济南市"泉城购"零售、餐饮消费券发放活动公告

三、消费券面额设置
1.零售消费券：满100元减20元、满200元减40元、满300元减60元。
2.餐饮消费券：满100元减25元、满200元减50元、满300元减75元。

活动时间：2025年1月1日至2025年3月31日
每人最多可领取3张消费券
消费券有效期为领取后30天
可在参与活动的商户使用
可叠加商户优惠，但不可叠加其他政府消费券

领取平台：泉城购小程序
支付方式：微信支付、支付宝
""",
        "expected_template": "consumer_coupon"
    },
    {
        "name": "家电补贴政策",
        "text": """
济南市2025年家电消费补贴实施方案
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
2025年1月1日至2025年12月31日
""",
        "expected_template": "appliance_subsidy"
    }
]

results = []

# 测试每个用例
for i, test_case in enumerate(test_cases, 1):
    print(f"\n{'=' * 80}")
    print(f"测试 {i}: {test_case['name']}")
    print("=" * 80)

    try:
        # 1. 生成DSL
        print(f"\n[1] 生成DSL...")
        response = requests.post(
            f"{API_URL}/api/dsl/generate",
            json={"text": test_case['text']},
            timeout=30
        )

        if response.status_code != 200:
            print(f"[ERROR] 生成失败: {response.status_code}")
            results.append({"name": test_case['name'], "status": "生成失败"})
            continue

        result = response.json()
        dsl_data = result['dsl_data']
        yaml_content = result['yaml_content']

        print(f"[OK] 生成成功")
        print(f"  - rule_id: {dsl_data.get('rule_id')}")
        print(f"  - name: {dsl_data.get('name')}")
        print(f"  - YAML长度: {len(yaml_content)} 字符")

        # 2. 验证模板类型
        template_indicators = {
            'consumer_coupon': ['coupon_types', 'distribution', 'usage_limits'],
            'appliance_subsidy': ['efficiency_rates', 'category_limits', 'per_item_cap'],
            'auto_subsidy': ['invoice_no_tax', 'vehicle_type']
        }

        detected_template = None
        for template_name, indicators in template_indicators.items():
            if any(ind in yaml_content for ind in indicators):
                detected_template = template_name
                break

        print(f"\n[2] 验证模板类型...")
        if detected_template == test_case['expected_template']:
            print(f"[OK] 使用了正确的模板: {detected_template}")
        else:
            print(f"[WARNING] 模板不匹配")
            print(f"  期望: {test_case['expected_template']}")
            print(f"  实际: {detected_template}")

        # 3. 保存到文件
        rule_id = dsl_data.get('rule_id')
        filename = f"{rule_id}_final_test.yaml"

        response = requests.post(
            f"{API_URL}/api/dsl/save",
            json={
                "rule_id": rule_id,
                "yaml_content": yaml_content,
                "filename": filename
            },
            timeout=10
        )

        if response.status_code == 200:
            print(f"\n[3] 保存成功: {filename}")
        else:
            print(f"\n[WARNING] 保存失败")

        # 4. 验证关键字段
        print(f"\n[4] 验证关键字段...")

        if test_case['expected_template'] == 'consumer_coupon':
            checks = [
                ('coupon_types' in dsl_data, 'coupon_types'),
                ('tiers' in dsl_data and len(dsl_data['tiers']) > 0, 'tiers'),
                ('distribution' in dsl_data, 'distribution'),
                ('usage_limits' in dsl_data, 'usage_limits'),
                ('inputs' in dsl_data and len(dsl_data['inputs']) >= 4, 'inputs (>=4)')
            ]
        elif test_case['expected_template'] == 'appliance_subsidy':
            checks = [
                ('efficiency_rates' in dsl_data, 'efficiency_rates'),
                ('category_limits' in dsl_data, 'category_limits'),
                ('per_item_cap' in dsl_data, 'per_item_cap'),
                ('inputs' in dsl_data and len(dsl_data['inputs']) == 3, 'inputs (=3)')
            ]
        else:
            checks = []

        all_passed = True
        for passed, field_name in checks:
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {field_name}")
            if not passed:
                all_passed = False

        results.append({
            "name": test_case['name'],
            "status": "成功" if all_passed else "部分失败",
            "rule_id": rule_id,
            "template": detected_template,
            "yaml_size": len(yaml_content)
        })

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append({"name": test_case['name'], "status": f"异常: {e}"})

# 输出总结
print(f"\n{'=' * 80}")
print("测试总结")
print("=" * 80)

for result in results:
    status_icon = "✓" if result['status'] == "成功" else "✗"
    print(f"\n{status_icon} {result['name']}")
    print(f"  状态: {result['status']}")
    if 'rule_id' in result:
        print(f"  Rule ID: {result['rule_id']}")
        print(f"  模板: {result['template']}")
        print(f"  YAML大小: {result['yaml_size']} 字符")

success_count = sum(1 for r in results if r['status'] == "成功")
print(f"\n总计: {len(results)} 个测试, 成功 {success_count} 个")

print("\n" + "=" * 80)
