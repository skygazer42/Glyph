#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 LightRAG 检索功能
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

def test_lightrag_query(query, session_id):
    """测试LightRAG查询"""
    print(f"\n{'='*80}")
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
            print(f"路由: {result.get('metadata', {}).get('route', 'unknown')}")
            print(f"意图: {result.get('metadata', {}).get('intent', {}).get('intent', 'unknown')}")
            print(f"置信度: {result.get('metadata', {}).get('confidence', 0)}")

            # 显示回答
            answer = result.get('message', '')
            print(f"\n回答:")
            print(f"{answer[:500]}..." if len(answer) > 500 else answer)

            # 显示来源
            doc_origins = result.get('metadata', {}).get('doc_origins', [])
            if doc_origins:
                print(f"\n相关文档数量: {len(doc_origins)}")
                for i, doc in enumerate(doc_origins[:3], 1):
                    print(f"  {i}. {doc.get('title', 'Unknown')}")

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
    print("LightRAG 检索功能测试")
    print("="*80)

    # 测试1: 家电以旧换新政策查询
    test_lightrag_query(
        "家电以旧换新政策的主要内容是什么？",
        "test-lightrag-001"
    )

    # 测试2: 补贴金额查询
    test_lightrag_query(
        "家电以旧换新能补贴多少钱？",
        "test-lightrag-002"
    )

    # 测试3: 申请流程查询
    test_lightrag_query(
        "如何申请家电以旧换新补贴？",
        "test-lightrag-003"
    )

    print("\n" + "="*80)
    print("测试完成")
    print("="*80)

if __name__ == "__main__":
    main()
