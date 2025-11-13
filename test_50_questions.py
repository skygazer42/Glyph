#!/usr/bin/env python3
"""
测试50个问题的路由系统
"""

import requests
import json
import time
from typing import Dict, List, Any
from datetime import datetime

# API端点
API_URL = "http://localhost:8000/api/agent/chat"

# 50个测试用例
TEST_CASES = [
    # FAQ缓存路由 (1-2)
    {"id": 1, "route": "faq_cache", "question": "家电以旧换新补贴标准是多少？", "note": "命中FAQ第一条"},
    {"id": 2, "route": "faq_cache", "question": "申请创业补贴需要满足什么条件？", "note": "命中FAQ第二条"},

    # 对话路由 (3-5)
    {"id": 3, "route": "dialogue", "question": "你好，在吗？", "note": "Intent=greeting"},
    {"id": 4, "route": "dialogue", "question": "辛苦啦，今天先这样，下次聊。", "note": "Intent=farewell"},
    {"id": 5, "route": "dialogue", "question": "你都能做什么？", "note": "默认chit_chat"},

    # 澄清路由 (6-8)
    {"id": 6, "route": "clarify", "question": "这个政策怎么样？", "note": "触发Clarifier补问"},
    {"id": 7, "route": "clarify", "question": "能不能说说那个东西？", "note": "极度模糊"},
    {"id": 8, "route": "clarify", "question": "资料对不对？", "note": "需澄清哪份资料"},

    # 用户画像工作流 (9-12)
    {"id": 9, "route": "workflow_user", "question": "帮我看看用户12345往年政策记录，有没有逾期？", "note": "张三"},
    {"id": 10, "route": "workflow_user", "question": "查询用户67890最近一次活动是什么？", "note": "李四"},
    {"id": 11, "route": "workflow_user", "question": "UserID=88888是否申请过补贴？输出详细历史。", "note": "王五"},
    {"id": 12, "route": "workflow_user", "question": "能依据用户12345的历史给出申报建议吗？", "note": "user_history intent"},

    # 知识图谱路由 (19-22)
    {"id": 19, "route": "graph", "question": "济南汽车消费补贴与新车商业保险补贴之间的联动环节有哪些？", "note": "多机构关系"},
    {"id": 20, "route": "graph", "question": "家电以旧换新政策里，旧机回收和财政审核的关联节点？", "note": "以旧换新doc"},
    {"id": 21, "route": "graph", "question": "LightRAG种子里提到的'动力电池企业'与'地方补贴审核'如何配合？", "note": "graph测试"},
    {"id": 22, "route": "graph", "question": "列出政策执行部门之间的协同职责（济南首保消费券）。", "note": "consumption_doc段落"},

    # 规则引擎路由 (23-28)
    {"id": 23, "route": "rule_engine", "question": "购买12万元新能源车，按照2025济南补贴标准能领多少？请列出计算过程。", "note": "汽车补贴"},
    {"id": 24, "route": "rule_engine", "question": "燃油车开票32万（不含税），对应补贴是多少？", "note": "燃油车补贴"},
    {"id": 25, "route": "rule_engine", "question": "首保商业险5200元，根据首保消费券公告补贴多少？", "note": "首保补贴"},
    {"id": 26, "route": "rule_engine", "question": "保险金额2500元，补充公告后的首保补贴是多少？", "note": "补充公告"},
    {"id": 27, "route": "rule_engine", "question": "青岛消费券档位：消费25万补贴多少？写出计算逻辑。", "note": "青岛消费券"},
    {"id": 28, "route": "rule_engine", "question": "家电消费：二级能效冰箱1.5万，补贴金额与限购说明？", "note": "家电补贴"},

    # Text2SQL路由 (29-33)
    {"id": 29, "route": "text2sql", "question": "（connection_id=1）写一条SQL：统计db.policy_apply表中2024年济南汽车补贴申请数。", "note": "含SQL关键字"},
    {"id": 30, "route": "text2sql", "question": "（连接ID=2）给我SQL查询user_apply中超过2次申报的用户ID。", "note": "SQL请求"},
    {"id": 31, "route": "text2sql", "question": "我要SQL：按地区统计subsidy_claim金额总和，结果按降序。", "note": "需connection_id"},
    {"id": 32, "route": "text2sql", "question": "把最新50条申请的rule_id和submit_time查出来。", "note": "SQL route"},
    {"id": 33, "route": "text2sql", "question": "列出policy_docs表中doc_type='coupon'的标题。", "note": "SQL关键词"},

    # 知识库路由 (34-50)
    {"id": 34, "route": "knowledge", "question": "泉城购零售券的满减档位有哪些？", "note": "零售券段"},
    {"id": 35, "route": "knowledge", "question": "餐饮消费券200元档需要满足的条件？", "note": "餐饮券"},
    {"id": 36, "route": "knowledge", "question": "济南汽车补贴的购车、申报、资料修改三个时间窗口分别是什么？", "note": "时间窗口"},
    {"id": 39, "route": "knowledge", "question": "青岛消费券活动持续到哪一天？", "note": "青岛活动"},
    {"id": 40, "route": "knowledge", "question": "家电补贴方案里空调单人限购几台？", "note": "限购政策"},
    {"id": 41, "route": "knowledge", "question": "一级与二级能效家电补贴比例分别是多少？", "note": "能效补贴"},
    {"id": 42, "route": "knowledge", "question": "家电补贴活动起止日期？", "note": "活动日期"},
    {"id": 43, "route": "knowledge", "question": "说明2025年首保消费券的各档补贴额度。", "note": "首保额度"},
    {"id": 44, "route": "knowledge", "question": "追加的3000万汽车补贴公告主要说明了什么？", "note": "追加公告"},
    {"id": 45, "route": "knowledge", "question": "第二轮与第三轮汽车消费礼包标准有区别吗？", "note": "礼包对比"},
    {"id": 46, "route": "knowledge", "question": "LightRAG种子里有哪些政策主题？请概述。", "note": "政策主题"},
    {"id": 47, "route": "knowledge", "question": "user_profiles中白金用户来自哪个地区？", "note": "用户地区"},
    {"id": 48, "route": "knowledge", "question": "王五有没有提交过补贴？官方描述是什么？", "note": "王五信息"},
    {"id": 49, "route": "knowledge", "question": "FAQ/embedding数据里与'申报进度'相关的问法有哪些？如何回复？", "note": "FAQ embedding"},
    {"id": 50, "route": "knowledge", "question": "结合资源文件，概述济南2025年汽车补贴额度总量及先到先得规则。", "note": "补贴总量"},
]


def test_single_question(question_data: Dict) -> Dict[str, Any]:
    """测试单个问题"""
    start_time = time.time()

    try:
        # 发送请求
        response = requests.post(
            API_URL,
            json={
                "message": question_data["question"],
                "session_id": f"test_{question_data['id']}",
                "user_id": "test_user"
            },
            timeout=30
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            return {
                "id": question_data["id"],
                "expected_route": question_data["route"],
                "actual_route": result.get("route", "unknown"),
                "question": question_data["question"],
                "response": result.get("response", "")[:200],  # 截取前200字符
                "success": True,
                "elapsed": elapsed,
                "note": question_data["note"]
            }
        else:
            return {
                "id": question_data["id"],
                "expected_route": question_data["route"],
                "actual_route": "error",
                "question": question_data["question"],
                "response": f"HTTP {response.status_code}",
                "success": False,
                "elapsed": elapsed,
                "note": question_data["note"]
            }

    except Exception as e:
        return {
            "id": question_data["id"],
            "expected_route": question_data["route"],
            "actual_route": "exception",
            "question": question_data["question"],
            "response": str(e),
            "success": False,
            "elapsed": time.time() - start_time,
            "note": question_data["note"]
        }


def run_all_tests():
    """运行所有测试"""
    print("="*80)
    print(f"开始测试50个问题 - {datetime.now()}")
    print("="*80)

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] 测试问题 ID={test_case['id']}: {test_case['question'][:50]}...")
        result = test_single_question(test_case)
        results.append(result)

        # 打印简要结果
        if result["success"]:
            route_match = "✅" if result["expected_route"] == result["actual_route"] else "❌"
            print(f"  {route_match} 期望路由: {result['expected_route']}, 实际路由: {result['actual_route']}")
            print(f"  ⏱️ 耗时: {result['elapsed']:.2f}秒")
        else:
            print(f"  ❌ 请求失败: {result['response']}")

        # 避免过快请求
        time.sleep(0.5)

    # 生成报告
    print("\n" + "="*80)
    print("测试完成 - 统计报告")
    print("="*80)

    # 统计
    total = len(results)
    success_count = sum(1 for r in results if r["success"])
    route_match_count = sum(1 for r in results if r["success"] and r["expected_route"] == r["actual_route"])

    print(f"\n📊 总体统计:")
    print(f"  - 总测试数: {total}")
    print(f"  - 成功请求: {success_count}/{total} ({success_count/total*100:.1f}%)")
    print(f"  - 路由匹配: {route_match_count}/{success_count} ({route_match_count/success_count*100:.1f}%)")

    # 按路由分组统计
    print(f"\n📋 路由分组统计:")
    route_groups = {}
    for r in results:
        exp_route = r["expected_route"]
        if exp_route not in route_groups:
            route_groups[exp_route] = {"total": 0, "success": 0, "match": 0}
        route_groups[exp_route]["total"] += 1
        if r["success"]:
            route_groups[exp_route]["success"] += 1
            if r["expected_route"] == r["actual_route"]:
                route_groups[exp_route]["match"] += 1

    for route, stats in sorted(route_groups.items()):
        print(f"  {route}: {stats['match']}/{stats['total']} 匹配 ({stats['match']/stats['total']*100:.0f}%)")

    # 保存详细结果
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 详细结果已保存到 test_results.json")

    # 列出失败的测试
    failures = [r for r in results if not r["success"] or r["expected_route"] != r["actual_route"]]
    if failures:
        print(f"\n⚠️ 需要关注的测试 ({len(failures)}个):")
        for f in failures[:10]:  # 只显示前10个
            print(f"  - ID {f['id']}: {f['expected_route']} → {f['actual_route']}")
            print(f"    问题: {f['question'][:60]}...")

    return results


if __name__ == "__main__":
    results = run_all_tests()