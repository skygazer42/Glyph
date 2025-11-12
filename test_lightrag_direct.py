#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试 LightRAG 检索功能 - 使用摘要类查询
"""

import requests
import json
import sys
import io

# 设置UTF-8编码输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_URL = "http://localhost:8000/api/agent/chat"

def test_query(query, session_id, description=""):
    """测试查询"""
    print(f"\n{'='*80}")
    print(f"【{description}】")
    print(f"问题: {query}")
    print(f"{'='*80}")

    payload = {
        "message": query,
        "session_id": session_id
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            print(f"\n✓ 响应成功")

            route = result.get('metadata', {}).get('route', 'unknown')
            intent = result.get('metadata', {}).get('intent', {})
            intent_name = intent.get('intent') if isinstance(intent, dict) else intent
            confidence = result.get('metadata', {}).get('confidence', 0)

            print(f"路由: {route}")
            print(f"意图: {intent_name}")
            print(f"置信度: {confidence}")

            # 显示回答
            answer = result.get('message', '')
            print(f"\n回答:")
            if len(answer) > 800:
                print(f"{answer[:800]}...")
            else:
                print(answer)

            # 检查是否使用了 LightRAG
            if route == "graph":
                print(f"\n✅ 成功路由到 LightRAG (graph)")
            else:
                print(f"\n⚠️  路由到了 {route} 而不是 graph")

            return True
        else:
            print(f"\n✗ 请求失败: {response.status_code}")
            print(f"错误: {response.text}")
            return False

    except Exception as e:
        print(f"\n✗ 异常: {str(e)}")
        return False

def main():
    """运行测试"""
    print("\n" + "="*80)
    print("LightRAG (Graph) 路由测试")
    print("="*80)

    # 测试1: 明确要求总结/摘要
    test_query(
        "请总结一下家电以旧换新政策的主要内容",
        "test-graph-001",
        "测试1 - 总结类查询"
    )

    # 测试2: 概括政策
    test_query(
        "概括家电以旧换新政策",
        "test-graph-002",
        "测试2 - 概括类查询"
    )

    # 测试3: 政策整体介绍
    test_query(
        "介绍一下家电以旧换新政策的整体框架",
        "test-graph-003",
        "测试3 - 整体介绍查询"
    )

    print("\n" + "="*80)
    print("测试完成")
    print("="*80)

if __name__ == "__main__":
    main()
