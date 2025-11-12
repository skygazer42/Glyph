#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent问答接口测试脚本
测试不同场景下Agent的路由和响应能力
"""

import requests
import json
import time
import sys
from datetime import datetime

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_URL = "http://localhost:8000/api/agent/chat"

def print_separator(title):
    """打印分隔线"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_query(query, session_id, connection_id=None, description=""):
    """测试单个查询"""
    print(f"\n【{description}】")
    print(f"问题: {query}")
    print(f"会话ID: {session_id}")

    payload = {
        "message": query,
        "session_id": session_id
    }

    if connection_id:
        payload["connection_id"] = connection_id

    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload, timeout=120)
        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 响应成功 (耗时: {elapsed_time:.2f}秒)")
            print(f"路由: {result.get('metadata', {}).get('route', 'unknown')}")
            print(f"意图: {result.get('metadata', {}).get('intent', {}).get('intent', 'unknown')}")
            print(f"置信度: {result.get('metadata', {}).get('confidence', 0)}")
            print(f"回答:\n{result.get('message', '')}")

            # 显示来源文档
            doc_origins = result.get('metadata', {}).get('doc_origins', [])
            if doc_origins:
                print(f"\n📄 相关文档数量: {len(doc_origins)}")

            return result
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            print(f"错误: {response.text}")
            return None

    except Exception as e:
        print(f"\n❌ 异常: {str(e)}")
        return None

def main():
    """主测试流程"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ========== 测试1: 知识库查询 ==========
    print_separator("测试1: 知识库查询 (Knowledge Base)")

    # 1.1 政策概述查询
    test_query(
        "家电以旧换新政策的主要内容是什么？",
        f"test-kb-{timestamp}",
        description="查询政策详情"
    )

    time.sleep(2)

    # 1.2 具体条件查询
    test_query(
        "申请消费券需要满足什么条件？",
        f"test-kb-cond-{timestamp}",
        description="查询申请条件"
    )

    time.sleep(2)

    # 1.3 模糊查询
    test_query(
        "有哪些补贴政策？",
        f"test-kb-list-{timestamp}",
        description="查询政策列表"
    )

    # ========== 测试2: Text2SQL数据查询 ==========
    print_separator("测试2: Text2SQL数据查询")

    time.sleep(2)

    # 2.1 统计查询
    test_query(
        "一共有多少个政策文件？",
        f"test-sql-count-{timestamp}",
        description="统计查询"
    )

    time.sleep(2)

    # 2.2 分类查询
    test_query(
        "按类别统计有多少个政策？",
        f"test-sql-group-{timestamp}",
        description="分组统计"
    )

    time.sleep(2)

    # 2.3 条件筛选
    test_query(
        "查询家电以旧换新相关的政策文件名称",
        f"test-sql-filter-{timestamp}",
        description="条件筛选查询"
    )

    # ========== 测试3: 多轮对话上下文 ==========
    print_separator("测试3: 多轮对话上下文")

    time.sleep(2)

    session_id = f"test-multi-{timestamp}"

    # 3.1 第一轮
    test_query(
        "泉城购消费券是什么？",
        session_id,
        description="第1轮 - 询问消费券"
    )

    time.sleep(2)

    # 3.2 第二轮 - 测试上下文
    test_query(
        "如何申请？",
        session_id,
        description="第2轮 - 追问申请方式（需要理解'它'指消费券）"
    )

    time.sleep(2)

    # 3.3 第三轮 - 继续上下文
    test_query(
        "有效期是多久？",
        session_id,
        description="第3轮 - 追问有效期"
    )

    # ========== 测试4: 混合查询 ==========
    print_separator("测试4: 混合查询（需要多个数据源）")

    time.sleep(2)

    test_query(
        "对比一下家电以旧换新和消费券政策的区别",
        f"test-hybrid-{timestamp}",
        description="对比查询"
    )

    # ========== 测试5: 边界情况 ==========
    print_separator("测试5: 边界情况测试")

    time.sleep(2)

    # 5.1 不存在的政策
    test_query(
        "有关于新能源汽车补贴的政策吗？",
        f"test-boundary-notfound-{timestamp}",
        description="查询不存在的政策"
    )

    time.sleep(2)

    # 5.2 模糊问题
    test_query(
        "我想买家电",
        f"test-boundary-vague-{timestamp}",
        description="模糊意图测试"
    )

    time.sleep(2)

    # 5.3 一般性问题
    test_query(
        "今天天气怎么样？",
        f"test-boundary-general-{timestamp}",
        description="超出知识范围的一般性问题"
    )

    print_separator("测试完成")
    print("\n所有测试场景已执行完毕！")

if __name__ == "__main__":
    main()
