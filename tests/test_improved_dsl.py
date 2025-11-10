"""
测试改进后的DSL生成 - 使用外部模板和详细提取
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).parent))

from app.agents.dsl_generator.dsl_extractor import DSLExtractor
from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.document_parser import DocumentParser

# 测试文本
test_text = """
2025年济南市"泉城购"零售、餐饮消费券发放活动公告

三、消费券面额设置
1.零售消费券：满100元减20元、满200元减40元、满300元减60元。
2.餐饮消费券：满100元减25元、满200元减50元、满300元减75元。

活动时间：2025年1月1日至2025年3月31日

发放规则：
- 每人最多可领取3张消费券
- 消费券有效期为领取后30天
- 可在参与活动的商户使用
- 可叠加商户优惠，但不可叠加其他政府消费券

领取平台：泉城购小程序
支付方式：微信支付、支付宝
"""

print("=" * 60)
print("测试改进后的DSL生成")
print("=" * 60)

# 初始化组件
print("\n[1] 初始化组件")
extractor = DSLExtractor(use_project_config=True)
generator = DSLGenerator(output_dir="rules", template_dir="templates")
parser = DocumentParser()
print("[OK] 组件初始化成功")

# 提取DSL数据
print("\n[2] 提取DSL数据")
print(f"文本预览: {test_text[:100]}...")
dsl_data = extractor.extract(test_text, {})
print("[OK] 提取完成")
print(f"\n提取的数据:")
import json
print(json.dumps(dsl_data, ensure_ascii=False, indent=2))

# 生成YAML - 自动检测模板
print("\n[3] 生成YAML (自动检测模板)")
yaml_content = generator.generate(dsl_data, auto_detect=True)
print(f"[OK] 生成成功, 长度: {len(yaml_content)} 字符")

# 保存 (先保存，避免编码错误导致没保存)
rule_id = dsl_data.get('rule_id', 'test_improved')
filename = f"{rule_id}_improved.yaml"
file_path = generator.save(yaml_content, filename)
print(f"\n[OK] 已保存到: {file_path}")

print(f"\n生成的YAML:")
print("=" * 60)
try:
    print(yaml_content)
except UnicodeEncodeError:
    print("[跳过打印YAML内容，存在编码问题，但文件已成功保存]")
print("=" * 60)

# 验证YAML
print("\n[4] 验证YAML")
import yaml
parsed = yaml.safe_load(yaml_content)
print(f"[OK] YAML格式有效")
print(f"\n关键字段:")
print(f"  - rule_id: {parsed.get('rule_id')}")
print(f"  - name: {parsed.get('name')}")
print(f"  - coupon_types: {parsed.get('coupon_types')}")
print(f"  - tiers: {len(parsed.get('tiers', []))} 个")
print(f"  - distribution: {parsed.get('distribution')}")
print(f"  - usage_limits: {parsed.get('usage_limits')}")
print(f"  - platform: {parsed.get('platform')}")
print(f"  - inputs: {len(parsed.get('inputs', []))} 个")
print(f"  - calc: {parsed.get('calc', {}).get('result', 'N/A')[:50]}...")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
