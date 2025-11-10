"""
批量测试DSL生成 - 测试所有政策文件
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

# 初始化组件
extractor = DSLExtractor(use_project_config=True)
generator = DSLGenerator(output_dir="rules", template_dir="templates")
parser = DocumentParser()

# 测试文件列表
test_files = [
    "consumption_doc.txt",
    "demo_policy.txt",
    "青岛_消费券发放_20251107_002327.txt",
]

print("=" * 80)
print("批量测试DSL生成")
print("=" * 80)

results = []

for filename in test_files:
    print(f"\n{'=' * 80}")
    print(f"测试文件: {filename}")
    print("=" * 80)

    file_path = Path("data/guize") / filename

    if not file_path.exists():
        print(f"[跳过] 文件不存在: {file_path}")
        results.append({"file": filename, "status": "文件不存在"})
        continue

    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        print(f"文本长度: {len(text)} 字符")
        print(f"文本预览: {text[:150]}...")

        # 提取DSL数据
        print("\n[1] 提取DSL数据...")
        dsl_data = extractor.extract(text, {})

        print(f"[OK] 提取完成")
        print(f"  - rule_id: {dsl_data.get('rule_id')}")
        print(f"  - name: {dsl_data.get('name')}")
        print(f"  - coupon_types: {dsl_data.get('coupon_types')}")
        print(f"  - tiers: {len(dsl_data.get('tiers', []))} 个")
        print(f"  - inputs: {len(dsl_data.get('inputs', []))} 个")

        # 生成YAML
        print("\n[2] 生成YAML...")
        yaml_content = generator.generate(dsl_data, auto_detect=True)
        print(f"[OK] 生成成功, 长度: {len(yaml_content)} 字符")

        # 保存文件
        rule_id = dsl_data.get('rule_id', 'unknown')
        save_filename = f"{rule_id}_test.yaml"
        file_path = generator.save(yaml_content, save_filename)
        print(f"[OK] 已保存到: {file_path}")

        # 验证YAML
        print("\n[3] 验证YAML...")
        import yaml
        parsed = yaml.safe_load(yaml_content)
        print(f"[OK] YAML格式有效")

        results.append({
            "file": filename,
            "status": "成功",
            "rule_id": rule_id,
            "yaml_length": len(yaml_content),
            "tiers": len(dsl_data.get('tiers', [])),
            "inputs": len(dsl_data.get('inputs', []))
        })

    except Exception as e:
        print(f"[ERROR] 处理失败: {e}")
        import traceback
        traceback.print_exc()
        results.append({"file": filename, "status": f"失败: {e}"})

# 输出总结
print("\n" + "=" * 80)
print("测试总结")
print("=" * 80)

for result in results:
    status = result.get('status')
    if status == "成功":
        print(f"\n✓ {result['file']}")
        print(f"  Rule ID: {result.get('rule_id')}")
        print(f"  YAML长度: {result.get('yaml_length')} 字符")
        print(f"  档位数: {result.get('tiers')}")
        print(f"  输入参数: {result.get('inputs')}")
    else:
        print(f"\n✗ {result['file']}")
        print(f"  状态: {status}")

success_count = sum(1 for r in results if r.get('status') == "成功")
print(f"\n总计: {len(results)} 个文件, 成功 {success_count} 个, 失败 {len(results) - success_count} 个")
