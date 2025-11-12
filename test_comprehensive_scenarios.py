#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全面的 Agent 系统测试 - 12个场景
测试不同的路由、Agent和功能组合
"""

import requests
import json
import sys
import io
import time
from datetime import datetime

# 设置UTF-8编码输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_URL = "http://localhost:8000/api/agent/chat"

class TestScenario:
    def __init__(self, name, query, expected_route, description):
        self.name = name
        self.query = query
        self.expected_route = expected_route
        self.description = description
        self.result = None
        self.elapsed_time = 0
        self.success = False

def print_header(title):
    """打印测试标题"""
    print(f"\n{'='*80}")
    print(f"{title:^80}")
    print(f"{'='*80}\n")

def test_query(scenario: TestScenario, session_id: str, connection_id=None, attachments=None):
    """执行单个测试查询"""
    print(f"\n{'─'*80}")
    print(f"【{scenario.name}】")
    print(f"描述: {scenario.description}")
    print(f"预期路由: {scenario.expected_route}")
    print(f"{'─'*80}")
    print(f"问题: {scenario.query}")
    print()

    payload = {
        "message": scenario.query,
        "session_id": session_id
    }

    if connection_id:
        payload["connection_id"] = connection_id

    if attachments:
        payload["attachments"] = attachments

    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload, timeout=120)
        scenario.elapsed_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            scenario.result = result

            # 提取路由和意图信息
            metadata = result.get('metadata', {})
            actual_route = metadata.get('route', 'unknown')
            intent_info = metadata.get('intent', {})
            intent = intent_info.get('intent') if isinstance(intent_info, dict) else intent_info
            confidence = metadata.get('confidence', 0)

            # 判断是否成功
            scenario.success = True

            print(f"✓ 响应成功 (耗时: {scenario.elapsed_time:.2f}秒)")
            print(f"实际路由: {actual_route} {'✅' if actual_route == scenario.expected_route else '⚠️ (不符合预期)'}")
            print(f"意图: {intent}")
            print(f"置信度: {confidence}")

            # 显示回答
            answer = result.get('message', '')
            print(f"\n【回答】")
            if len(answer) > 600:
                print(f"{answer[:600]}...")
                print(f"... (共 {len(answer)} 字符)")
            else:
                print(answer)

            # 显示来源文档
            doc_origins = metadata.get('doc_origins', [])
            if doc_origins:
                print(f"\n📄 相关文档: {len(doc_origins)} 篇")

            return True
        else:
            print(f"✗ 请求失败: {response.status_code}")
            print(f"错误: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ 异常: {str(e)}")
        return False

def generate_report(scenarios, output_file="TEST_RESULTS.md"):
    """生成测试报告"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Agent系统全面测试报告\n\n")
        f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        # 测试概览
        f.write("## 📊 测试概览\n\n")
        total = len(scenarios)
        successful = sum(1 for s in scenarios if s.success)
        f.write(f"- 总测试数: {total}\n")
        f.write(f"- 成功数: {successful}\n")
        f.write(f"- 失败数: {total - successful}\n")
        f.write(f"- 成功率: {successful/total*100:.1f}%\n\n")

        # 路由统计
        f.write("## 🔀 路由统计\n\n")
        route_counts = {}
        for s in scenarios:
            if s.result:
                route = s.result.get('metadata', {}).get('route', 'unknown')
                route_counts[route] = route_counts.get(route, 0) + 1

        f.write("| 路由 | 次数 |\n")
        f.write("|------|------|\n")
        for route, count in sorted(route_counts.items(), key=lambda x: x[1], reverse=True):
            f.write(f"| {route} | {count} |\n")
        f.write("\n")

        # 性能统计
        f.write("## ⚡ 性能统计\n\n")
        times = [s.elapsed_time for s in scenarios if s.success]
        if times:
            f.write(f"- 平均响应时间: {sum(times)/len(times):.2f}秒\n")
            f.write(f"- 最快响应: {min(times):.2f}秒\n")
            f.write(f"- 最慢响应: {max(times):.2f}秒\n\n")

        # 详细结果
        f.write("## 📝 详细测试结果\n\n")
        for i, s in enumerate(scenarios, 1):
            f.write(f"### {i}. {s.name}\n\n")
            f.write(f"**描述**: {s.description}\n\n")
            f.write(f"**问题**: {s.query}\n\n")
            f.write(f"**预期路由**: `{s.expected_route}`\n\n")

            if s.result:
                metadata = s.result.get('metadata', {})
                actual_route = metadata.get('route', 'unknown')
                f.write(f"**实际路由**: `{actual_route}` ")
                f.write("✅\n\n" if actual_route == s.expected_route else "⚠️ 不符合预期\n\n")
                f.write(f"**响应时间**: {s.elapsed_time:.2f}秒\n\n")

                answer = s.result.get('message', '')
                f.write(f"**回答** (前300字):\n```\n{answer[:300]}...\n```\n\n")
            else:
                f.write("**状态**: ❌ 失败\n\n")

            f.write("---\n\n")

    print(f"\n✅ 测试报告已生成: {output_file}")

def main():
    """主测试流程"""
    print_header("Agent系统全面测试 - 12个场景")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 定义测试场景
    scenarios = [
        TestScenario(
            "测试1: 政策概览",
            "请概述《md2025年家电和数码以旧换新政策文件》中关于补贴目的、适用产品范围和执行时间的要点，每一项单独成段说明，并注明出处段落标题。",
            "knowledge",
            "knowledge + 分级索引 - 政策概述"
        ),

        TestScenario(
            "测试2: 申请条件与材料",
            "泉城购消费券活动里，个人申请需要满足的资格和需提交的材料分别有哪些？请按条件/材料两列对照输出，并标注职责部门。",
            "knowledge",
            "knowledge/graph - 结构化信息提取"
        ),

        TestScenario(
            "测试3: 金额计算",
            "我准备在活动期内更换 3 台 9000 元的节能空调，旧机都可回收，根据当前以旧换新政策说明我最多能获多少补贴，并解释计算过程。",
            "rule_engine",
            "rule_engine - DSL规则计算"
        ),

        TestScenario(
            "测试4: 流程与部门关系",
            "请梳理最新家电以旧换新补贴的办理流程，强调每个节点由哪个部门或平台负责，以及审核/公示/拨付之间的衔接关系。",
            "graph",
            "graph优先 - 流程与关系梳理"
        ),

        TestScenario(
            "测试5: 日期与时效性",
            "泉城购消费券的领取窗口、使用截止日期分别是什么？如果过期了怎么办？",
            "knowledge",
            "knowledge - 时间信息查询"
        ),

        TestScenario(
            "测试6: 政策对比",
            "对比家电以旧换新和泉城购消费券两个政策的适用对象、补贴标准、申请流程的异同点。",
            "knowledge",
            "knowledge/comparison - 多政策对比"
        ),

        TestScenario(
            "测试7: 数据库统计查询",
            "一共有多少个家电类的政策文件？",
            "text2sql",
            "text2sql - SQL数据查询"
        ),

        TestScenario(
            "测试8: 规则引擎验证",
            "如果我是济南市历下区居民，想购买一台5000元的新冰箱，旧冰箱已使用8年，能获得多少补贴？",
            "rule_engine",
            "rule_engine - 资格验证+计算"
        ),

        TestScenario(
            "测试9: 图谱总结",
            "请总结家电以旧换新政策的主要参与方及其职责。",
            "graph",
            "graph/knowledge - 主体关系总结"
        ),

        TestScenario(
            "测试10: LightRAG关系总结",
            "请用关系图式描述家电以旧换新政策中'商务局、财政局、街道办、第三方核验机构'之间在补贴审核与发放环节的职责关系。",
            "graph",
            "graph - 实体关系抽取"
        ),

        TestScenario(
            "测试11: 闲聊对话",
            "你好，今天天气怎么样？",
            "dialogue",
            "dialogue - 闲聊识别"
        ),

        TestScenario(
            "测试12: 混合意图",
            "我想了解家电补贴，但不知道从哪里开始？",
            "knowledge",
            "clarify/knowledge - 模糊意图处理"
        ),
    ]

    # 执行测试
    results = []
    for i, scenario in enumerate(scenarios, 1):
        session_id = f"test-comprehensive-{timestamp}-{i}"

        # 对于Text2SQL测试，提供connection_id
        connection_id = 1 if scenario.expected_route == "text2sql" else None

        success = test_query(scenario, session_id, connection_id)
        results.append(success)

        # 测试之间稍作等待
        if i < len(scenarios):
            time.sleep(2)

    # 生成报告
    print_header("生成测试报告")
    generate_report(scenarios)

    # 打印总结
    print_header("测试总结")
    total = len(scenarios)
    successful = sum(1 for s in scenarios if s.success)

    print(f"总测试数: {total}")
    print(f"成功数: {successful}")
    print(f"失败数: {total - successful}")
    print(f"成功率: {successful/total*100:.1f}%")

    print("\n路由符合预期统计:")
    route_match = sum(1 for s in scenarios if s.result and
                     s.result.get('metadata', {}).get('route') == s.expected_route)
    print(f"路由匹配: {route_match}/{successful} ({route_match/successful*100:.1f}%)" if successful > 0 else "路由匹配: 0/0")

    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    main()
