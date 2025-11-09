"""
测试 API 端点
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("测试健康检查...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 200
    print("[OK] 健康检查通过")


def test_agent_chat():
    """测试 Agent 非流式聊天"""
    print("=" * 60)
    print("测试 Agent 非流式聊天...")
    data = {"message": "你好，请介绍一下自己"}
    response = requests.post(f"{BASE_URL}/api/agent/chat", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    assert response.status_code == 200
    assert result["success"] == True
    print("[OK] Agent 聊天测试通过")


def test_dsl_list():
    """测试 DSL 规则列表"""
    print("=" * 60)
    print("测试 DSL 规则列表...")
    response = requests.get(f"{BASE_URL}/api/dsl/list")
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"规则数量: {result.get('total', 0)}")
    assert response.status_code == 200
    print("[OK] DSL 列表测试通过")


def test_knowledge_documents():
    """测试知识库文档列表"""
    print("=" * 60)
    print("测试知识库文档列表...")
    response = requests.get(f"{BASE_URL}/api/knowledge/documents")
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"文档数量: {result.get('total', 0)}")
    assert response.status_code == 200
    print("[OK] 知识库列表测试通过")


if __name__ == "__main__":
    print("\n开始 API 端点测试\n")

    try:
        test_health()
        test_agent_chat()
        test_dsl_list()
        test_knowledge_documents()

        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
