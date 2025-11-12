#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试路由逻辑"""

import sys
import io

# 设置UTF-8编码输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def _looks_like_graph_question(query: str, sub_intent=None) -> bool:
    """检测图谱相关问题"""
    graph_keywords = [
        "关系", "关联", "联系", "执行部门", "监管机制", "责任链",
        "流程图", "梳理", "脉络", "负责", "对接", "协同", "联动",
    ]
    process_keywords = ["流程", "环节", "节点", "使用场景", "链路"]
    q_lower = query.lower()

    print(f"查询: {query}")
    print(f"sub_intent: {sub_intent}")

    # 检查 graph_keywords
    matched_graph = [kw for kw in graph_keywords if kw in query or kw in q_lower]
    if matched_graph:
        print(f"✓ 匹配到 graph_keywords: {matched_graph}")
        return True

    # 检查 process_keywords
    matched_process = [kw for kw in process_keywords if kw in query or kw in q_lower]
    if sub_intent in {"process", "documents"} and matched_process:
        print(f"✓ 匹配到 process_keywords (sub_intent={sub_intent}): {matched_process}")
        return True
    elif matched_process:
        print(f"⚠ 找到 process_keywords 但 sub_intent 不匹配: {matched_process}")

    print(f"✗ 未匹配到任何关键词")
    return False


# 测试用例
test_queries = [
    ("请梳理最新家电以旧换新补贴的办理流程，强调每个节点由哪个部门或平台负责，以及审核/公示/拨付之间的衔接关系。", None),
    ("请总结家电以旧换新政策的主要参与方及其职责。", None),
    ("请用关系图式描述家电以旧换新政策中'商务局、财政局、街道办、第三方核验机构'之间在补贴审核与发放环节的职责关系。", None),
]

print("=" * 80)
print("路由关键词匹配测试")
print("=" * 80)

for i, (query, sub_intent) in enumerate(test_queries, 1):
    print(f"\n【测试 {i}】")
    result = _looks_like_graph_question(query, sub_intent)
    print(f"结果: {'✅ 应路由到 graph' if result else '❌ 不会路由到 graph'}")
    print("-" * 80)
