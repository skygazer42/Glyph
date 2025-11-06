"""
快速测试 DSL 生成器
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from agents.dsl_generator.main_v2 import DSLPipeline


def quick_test():
    """快速测试（使用规则提取）"""
    print("=" * 50)
    print("快速测试 DSL 生成器")
    print("=" * 50)

    # 创建简单的测试文档
    test_file = "F:/pythonproject/gov/data/guize/quick_test.txt"
    test_content = """济南市家电补贴政策
补贴标准：
一级能效补贴20%
二级能效补贴15%
最高2000元"""

    Path(test_file).parent.mkdir(exist_ok=True)
    Path(test_file).write_text(test_content, encoding='utf-8')
    print(f"\n创建测试文档: {test_file}")

    # 使用规则提取（不用 LLM）
    pipeline = DSLPipeline(
        data_dir="F:/pythonproject/gov/data/guize",
        output_dir="F:/pythonproject/gov/rules",
        use_project_config=False  # 不使用 LLM
    )

    # 处理文档
    print("\n处理文档...")
    result = pipeline.process_document(test_file)

    if result['status'] == 'success':
        print("[成功] 文档处理完成")
        print(f"生成的文件: {result['dsl_file']}")

        # 显示 DSL 数据
        if 'dsl_data' in result:
            import json
            print("\nDSL 数据:")
            print(json.dumps(result['dsl_data'], ensure_ascii=False, indent=2))

        # 测试规则执行
        if 'dsl_data' in result:
            rule_id = result['dsl_data']['rule_id']
            print(f"\n测试规则: {rule_id}")

            test_input = {
                'price': 10000.0,
                'energy_level': 1,
                'category': '空调'
            }

            test_result = pipeline.test_rule(rule_id, test_input)
            print(f"输入: {test_input}")
            print(f"结果: {test_result.get('final_result', 'N/A')}")
            print(f"状态: {test_result.get('status', 'N/A')}")
    else:
        print(f"[失败] {result.get('errors', ['未知错误'])}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    quick_test()