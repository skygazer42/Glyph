"""
测试使用外部模板的DSL生成
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).parent))

from agents.dsl_generator.dsl_generator import DSLGenerator

# 测试数据 - 消费券
test_data_coupon = {
    "rule_id": "Rule_Test_Consumer_Coupon",
    "name": "测试消费券",
    "version": "1.0",
    "policy_source": {
        "doc_id": "test_doc_001",
        "title": "2025年济南市零售餐饮消费券发放活动"
    },
    "valid_period": {
        "start": "2025-01-01",
        "end": "2025-12-31"
    },
    "coupon_types": ["AMOUNT"],
    "tiers": [
        {"type": "AMOUNT", "threshold": 100, "discount": 20, "name": "满100减20"},
        {"type": "AMOUNT", "threshold": 200, "discount": 40, "name": "满200减40"},
        {"type": "AMOUNT", "threshold": 300, "discount": 60, "name": "满300减60"}
    ],
    "distribution": {
        "method": "auto_claim",
        "total_quota": 10000000,
        "quota_per_person": 3
    },
    "usage_limits": {
        "valid_days": 30,
        "merchant_scope": "参与活动商户",
        "product_scope": "全品类",
        "stacking": {
            "with_merchant_discount": True,
            "with_other_coupons": False
        }
    },
    "platform": {
        "claim_platform": "泉城购小程序",
        "payment_methods": ["微信支付", "支付宝"]
    }
}

print("=" * 60)
print("测试外部模板DSL生成")
print("=" * 60)

# 初始化生成器
print("\n[1] 初始化DSL生成器")
generator = DSLGenerator(output_dir="rules", template_dir="templates")
print("[OK] 初始化完成")

# 测试1: 手动指定模板
print("\n[2] 测试手动指定consumer_coupon模板")
try:
    yaml_content = generator.generate(test_data_coupon, template_name="consumer_coupon.yaml.j2")
    print(f"[OK] 生成成功, 长度: {len(yaml_content)} 字符")
    print(f"\n生成的YAML (前50行):")
    for i, line in enumerate(yaml_content.split('\n')[:50], 1):
        print(f"{i:3d}: {line}")

    # 保存
    file_path = generator.save(yaml_content, "test_consumer_coupon.yaml")
    print(f"\n[OK] 已保存到: {file_path}")
except Exception as e:
    print(f"[FAIL] 生成失败: {e}")
    import traceback
    traceback.print_exc()

# 测试2: 自动检测模板
print("\n[3] 测试自动检测模板类型")
try:
    yaml_content = generator.generate(test_data_coupon, auto_detect=True)
    print(f"[OK] 生成成功, 长度: {len(yaml_content)} 字符")

    # 验证YAML
    import yaml
    parsed = yaml.safe_load(yaml_content)
    print(f"\n[OK] YAML格式验证通过")
    print(f"  - rule_id: {parsed.get('rule_id')}")
    print(f"  - name: {parsed.get('name')}")
    print(f"  - coupon_types: {parsed.get('coupon_types')}")
    print(f"  - tiers: {len(parsed.get('tiers', []))} 个")
except Exception as e:
    print(f"[FAIL] 自动检测失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
