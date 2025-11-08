"""
测试DSL生成功能
从 data/guize 目录读取政策文本,生成DSL规则
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from agents.dsl_generator.dsl_extractor import DSLExtractor
from agents.dsl_generator.dsl_generator import DSLGenerator
from agents.dsl_generator.document_parser import DocumentParser


def test_dsl_generation():
    """测试DSL生成功能"""

    print("=" * 60)
    print("DSL生成测试")
    print("=" * 60)

    # 初始化组件
    print("\n[步骤 1] 初始化组件")
    try:
        extractor = DSLExtractor(use_project_config=True)
        generator = DSLGenerator(output_dir="rules")
        parser = DocumentParser()
        print("[OK] 组件初始化成功")
    except Exception as e:
        print(f"[FAIL] 组件初始化失败: {e}")
        return False

    # 读取测试文件
    guize_dir = Path("data/guize")
    test_files = [
        "consumption_doc.txt",
        "test_policy.txt",
    ]

    results = []

    for test_file in test_files:
        file_path = guize_dir / test_file

        if not file_path.exists():
            print(f"\n[SKIP] 文件不存在: {test_file}")
            continue

        print(f"\n{'=' * 60}")
        print(f"[步骤 2] 测试文件: {test_file}")
        print("=" * 60)

        try:
            # 读取文件
            print(f"\n[2.1] 读取文件...")
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            print(f"[OK] 文件大小: {len(text)} 字符")
            print(f"[OK] 文本预览:\n{text[:300]}...")

            # 预处理
            print(f"\n[2.2] 预处理文本...")
            processed = parser.preprocess_text(text)
            print(f"[OK] 预处理完成")

            # 提取DSL结构
            print(f"\n[2.3] 提取DSL结构...")
            dsl_data = extractor.extract(text, processed.get('metadata', {}))
            print(f"[OK] DSL数据提取完成")
            print(f"[INFO] DSL数据预览:")
            import json
            print(json.dumps(dsl_data, ensure_ascii=False, indent=2)[:500] + "...")

            # 生成YAML
            print(f"\n[2.4] 生成YAML...")
            yaml_content = generator.generate(dsl_data)
            print(f"[OK] YAML生成成功")
            print(f"[INFO] YAML预览 (前40行):")
            yaml_lines = yaml_content.split('\n')
            for i, line in enumerate(yaml_lines[:40], 1):
                print(f"  {i:2d}: {line}")
            if len(yaml_lines) > 40:
                print(f"  ... (共{len(yaml_lines)}行)")

            # 保存规则
            print(f"\n[2.5] 保存规则...")
            rule_id = dsl_data.get('rule_id', 'test_rule')
            filename = f"{rule_id}.yaml"
            file_path = generator.save(yaml_content, filename)
            print(f"[OK] 规则已保存: {file_path}")

            # 验证生成的YAML
            print(f"\n[2.6] 验证YAML格式...")
            try:
                import yaml
                parsed_yaml = yaml.safe_load(yaml_content)
                print(f"[OK] YAML格式有效")
                print(f"[INFO] YAML结构:")
                print(f"  - rule_id: {parsed_yaml.get('rule_id')}")
                print(f"  - policy_source: {parsed_yaml.get('policy_source', {}).get('title')}")
                if 'valid_period' in parsed_yaml:
                    print(f"  - valid_period: {parsed_yaml.get('valid_period')}")
                if 'inputs' in parsed_yaml:
                    print(f"  - inputs: {len(parsed_yaml.get('inputs', []))} 个")
                if 'tiers' in parsed_yaml:
                    print(f"  - tiers: {len(parsed_yaml.get('tiers', []))} 个档位")

                results.append({
                    "file": test_file,
                    "status": "success",
                    "rule_id": rule_id,
                    "file_path": str(file_path),
                    "yaml_valid": True
                })

            except yaml.YAMLError as e:
                print(f"[FAIL] YAML格式错误: {e}")
                results.append({
                    "file": test_file,
                    "status": "yaml_error",
                    "error": str(e)
                })

        except Exception as e:
            print(f"[FAIL] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "file": test_file,
                "status": "error",
                "error": str(e)
            })

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    success_count = sum(1 for r in results if r.get('status') == 'success')
    total_count = len(results)

    print(f"\n总测试文件: {total_count}")
    print(f"成功生成: {success_count}")
    print(f"失败: {total_count - success_count}")

    if success_count > 0:
        print(f"\n成功生成的规则:")
        for r in results:
            if r.get('status') == 'success':
                print(f"  - {r['rule_id']}: {r['file_path']}")

    if success_count < total_count:
        print(f"\n失败的文件:")
        for r in results:
            if r.get('status') != 'success':
                print(f"  - {r['file']}: {r.get('error', r.get('status'))}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

    return success_count == total_count


if __name__ == "__main__":
    test_dsl_generation()
