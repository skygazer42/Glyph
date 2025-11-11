"""
测试API服务的DSL生成
"""
import pytest
import requests
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试文本
test_texts = {
    "消费券": """
2025年济南市"泉城购"零售、餐饮消费券发放活动公告

三、消费券面额设置
1.零售消费券：满100元减20元、满200元减40元、满300元减60元。
2.餐饮消费券：满100元减25元、满200元减50元、满300元减75元。

活动时间：2025年1月1日至2025年3月31日
每人最多可领取3张消费券
""",
    "家电补贴": """
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
"""
}

# API服务地址
API_URL = "http://localhost:8000"


@pytest.mark.requires_network
def test_api_dsl_generation():
    """测试通过API生成DSL"""
    print("=" * 80)
    print("测试API服务DSL生成")
    print("=" * 80)

    # 检查服务健康状态
    try:
        response = requests.get(f"{API_URL}/api/health", timeout=5)
        print(f"\n服务状态: {response.json()}")
    except Exception as e:
        pytest.skip(f"无法连接到API服务: {e}")

    # 测试每个类型
    for policy_type, text in test_texts.items():
        print(f"\n{'=' * 80}")
        print(f"测试: {policy_type}")
        print("=" * 80)

        try:
            # 调用生成API
            response = requests.post(
                f"{API_URL}/api/dsl/generate",
                json={"text": text},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                print(f"\n[OK] 生成成功")
                print(f"  - rule_id: {result['dsl_data'].get('rule_id')}")
                print(f"  - name: {result['dsl_data'].get('name')}")
                print(f"  - YAML长度: {len(result['yaml_content'])} 字符")

                # 保存到本地查看
                rule_id = result['dsl_data'].get('rule_id', 'unknown')
                filename = f"{rule_id}_api_test.yaml"
                with open(f"rules/{filename}", 'w', encoding='utf-8') as f:
                    f.write(result['yaml_content'])
                print(f"  - 已保存: rules/{filename}")

            else:
                print(f"\n[ERROR] 生成失败: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"\n[ERROR] 请求失败: {e}")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


def test_dsl_generation_offline():
    """离线测试DSL生成（不需要API服务）"""
    from app.agents.packs.dsl_generator.node import DSLGeneratorNode

    print("\n" + "=" * 80)
    print("离线测试DSL生成")
    print("=" * 80)

    generator = DSLGeneratorNode()

    for policy_type, text in test_texts.items():
        print(f"\n测试: {policy_type}")
        try:
            # 直接调用生成器
            result = generator.generate(text)
            assert result is not None, "生成结果不应为空"
            assert 'rule_id' in result, "应包含规则ID"
            assert 'name' in result, "应包含规则名称"
            print(f"  ✓ 生成成功: {result.get('name')}")
        except Exception as e:
            print(f"  ✗ 生成失败: {e}")
            raise


if __name__ == "__main__":
    # 如果直接运行脚本，执行离线测试
    test_dsl_generation_offline()
