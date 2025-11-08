"""
测试规则引擎执行
"""
import requests
import json

API_URL = "http://localhost:8000"

print("=" * 80)
print("测试规则引擎执行")
print("=" * 80)

# 测试数据
test_case = {
    "rule_id": "Rule_Test_Consumer_Coupon",
    "inputs": {
        "consumption_amount": 250.0,
        "coupon_type": "AMOUNT",
        "claim_time": "2025-02-01T10:00:00",
        "user_id": "user_123",
        "using_other_coupon": False,
        "has_merchant_discount": True
    }
}

print(f"\n测试用例:")
print(f"  规则: {test_case['rule_id']}")
print(f"  消费金额: {test_case['inputs']['consumption_amount']} 元")
print(f"  券种类型: {test_case['inputs']['coupon_type']}")

try:
    response = requests.post(
        f"{API_URL}/api/dsl/test",
        json=test_case,
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        print(f"\n[OK] 执行成功")

        # 保存结果到文件
        with open("test_exec_result.json", "w", encoding="utf-8") as f:
            json.dump(result['result'], f, ensure_ascii=False, indent=2)

        print(f"\n执行结果已保存到: test_exec_result.json")
        print(f"  status: {result['result'].get('status')}")
        print(f"  final_result: {result['result'].get('final_result')}")
    else:
        print(f"\n[ERROR] 执行失败: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"\n[ERROR] 请求失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
