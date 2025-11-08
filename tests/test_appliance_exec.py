"""
测试家电补贴规则执行
"""
import requests
import json

API_URL = "http://localhost:8000"

print("=" * 80)
print("测试家电补贴规则执行")
print("=" * 80)

# 测试用例: 购买一台一级能效空调,价格8000元
test_case = {
    "rule_id": "Rule_济南_家电补贴_2025",
    "inputs": {
        "price": 8000.0,
        "energy_level": 1,
        "category": "空调"
    }
}

print(f"\n测试用例:")
print(f"  规则: {test_case['rule_id']}")
print(f"  商品价格: {test_case['inputs']['price']} 元")
print(f"  能效等级: {test_case['inputs']['energy_level']} 级")
print(f"  商品类别: {test_case['inputs']['category']}")

print(f"\n预期计算:")
print(f"  补贴率: 15% (二级基础) + 5% (一级额外) = 20%")
print(f"  原始补贴: 8000 * 0.20 = 1600 元")
print(f"  封顶后补贴: min(1600, 2000) = 1600 元")

try:
    response = requests.post(
        f"{API_URL}/api/dsl/test",
        json=test_case,
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        print(f"\n[OK] 执行成功\n")

        # 保存结果
        with open("test_appliance_result.json", "w", encoding="utf-8") as f:
            json.dump(result['result'], f, ensure_ascii=False, indent=2)

        print(f"执行结果:")
        print(f"  status: {result['result'].get('status')}")
        print(f"  final_result: {result['result'].get('final_result')} 元")

        calc_details = result['result'].get('calculation_details', {})
        if calc_details:
            print(f"\n计算详情:")
            print(json.dumps(calc_details, ensure_ascii=False, indent=2))

        print(f"\n结果已保存到: test_appliance_result.json")

    else:
        print(f"\n[ERROR] 执行失败: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"\n[ERROR] 请求失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
