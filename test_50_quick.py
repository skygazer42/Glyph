"""
快速并行测试50问 - 优化版
支持并行测试、进度显示、实时统计
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.agents.service import AgentService


# 简化的测试用例 - 只包含关键信息
QUICK_TEST_CASES = [
    # FAQ Cache (2个)
    (1, "faq_cache", "家电以旧换新补贴标准是多少？", None, None),
    (2, "faq_cache", "申请创业补贴需要满足什么条件？", None, None),

    # Dialogue (3个)
    (3, "dialogue", "你好，在吗？", None, None),
    (4, "dialogue", "辛苦啦，今天先这样，下次聊。", None, None),
    (5, "dialogue", "你都能做什么？", None, None),

    # Clarify (3个)
    (6, "clarify", "这个政策怎么样？", None, None),
    (7, "clarify", "能不能说说那个东西？", None, None),
    (8, "clarify", "资料对不对？", None, None),

    # Workflow (4个)
    (9, "workflow", "帮我看看用户 12345 往年政策记录，有没有逾期？", None, "12345"),
    (10, "workflow", "查询用户 67890 最近一次活动是什么？", None, "67890"),
    (11, "workflow", "UserID=88888 是否申请过补贴？输出详细历史。", None, "88888"),
    (12, "workflow", "能依据用户 12345 的历史给出申报建议吗？", None, "12345"),

    # Graph (4个)
    (19, "graph", "济南汽车消费补贴与新车商业保险补贴之间的联动环节有哪些？", None, None),
    (20, "graph", "家电以旧换新政策里，旧机回收和财政审核的关联节点？", None, None),
    (21, "graph", "LightRAG 种子里提到的'动力电池企业'与'地方补贴审核'如何配合？", None, None),
    (22, "graph", "列出政策执行部门之间的协同职责（济南首保消费券）。", None, None),

    # Rule Engine (6个)
    (23, "rule_engine", "购买 12 万元新能源车，按照 2025 济南补贴标准能领多少？请列出计算过程。", None, None),
    (24, "rule_engine", "燃油车开票 32 万（不含税），对应补贴是多少？", None, None),
    (25, "rule_engine", "首保商业险 5200 元，根据首保消费券公告补贴多少？", None, None),
    (26, "rule_engine", "保险金额 2500 元，补充公告后的首保补贴是多少？", None, None),
    (27, "rule_engine", "青岛消费券档位：消费 25 万补贴多少？写出计算逻辑。", None, None),
    (28, "rule_engine", "家电消费：二级能效冰箱 1.5 万，补贴金额与限购说明？", None, None),

    # Text2SQL (5个)
    (29, "text2sql", "写一条 SQL：统计 db.policy_apply 表中 2024 年济南汽车补贴申请数。", 1, None),
    (30, "text2sql", "给我 SQL 查询 user_apply 中超过 2 次申报的用户 ID。", 2, None),
    (31, "text2sql", "我要 SQL：按地区统计 subsidy_claim 金额总和，结果按降序。", 1, None),
    (32, "text2sql", "把最新 50 条申请的 rule_id 和 submit_time 查出来。", 1, None),
    (33, "text2sql", "列出 policy_docs 表中 doc_type='coupon' 的标题。", 1, None),

    # Knowledge (17个)
    (34, "knowledge", "泉城购零售券的满减档位有哪些？", None, None),
    (35, "knowledge", "餐饮消费券 200 元档需要满足的条件？", None, None),
    (36, "knowledge", "济南汽车补贴的购车、申报、资料修改三个时间窗口分别是什么？", None, None),
    (39, "knowledge", "青岛消费券活动持续到哪一天？", None, None),
    (40, "knowledge", "家电补贴方案里空调单人限购几台？", None, None),
    (41, "knowledge", "一级与二级能效家电补贴比例分别是多少？", None, None),
    (42, "knowledge", "家电补贴活动起止日期？", None, None),
    (43, "knowledge", "说明 2025 年首保消费券的各档补贴额度。", None, None),
    (44, "knowledge", "追加的 3000 万汽车补贴公告主要说明了什么？", None, None),
    (45, "knowledge", "第二轮与第三轮汽车消费礼包标准有区别吗？", None, None),
    (46, "knowledge", "LightRAG 种子里有哪些政策主题？请概述。", None, None),
    (47, "knowledge", "user_profiles 中白金用户来自哪个地区？", None, None),
    (48, "knowledge", "王五有没有提交过补贴？官方描述是什么？", None, None),
    (49, "knowledge", "FAQ/embedding 数据里与'申报进度'相关的问法有哪些？如何回复？", None, None),
    (50, "knowledge", "结合资源文件，概述济南 2025 年汽车补贴额度总量及先到先得规则。", None, None),
]


class QuickTestRunner:
    """快速测试运行器"""

    def __init__(self, max_concurrent=3):
        self.agent_service = None
        self.max_concurrent = max_concurrent
        self.results = []
        self.lock = asyncio.Lock()
        self.progress = 0
        self.total = len(QUICK_TEST_CASES)

    async def initialize(self):
        """初始化"""
        print("\n🚀 正在初始化 AgentService...")
        self.agent_service = AgentService()
        await self.agent_service.initialize()
        print("✅ 初始化完成")

    async def test_one(self, test_id, target_route, query, conn_id, user_id):
        """测试单个问题"""
        start = time.time()
        result = {
            "id": test_id,
            "target": target_route,
            "actual": None,
            "match": False,
            "time": 0,
            "conf": 0,
            "error": None,
        }

        try:
            final = await self.agent_service.process_query(
                query=query,
                session_id=f"test_{test_id}",
                user_id=user_id,
                connection_id=conn_id,
            )

            result["actual"] = final.metadata.get("route", "unknown")
            result["match"] = (result["actual"] == target_route)
            result["time"] = time.time() - start
            result["conf"] = final.confidence

            # 快速输出 - 中文显示
            status = "✅ 通过" if result["match"] else "❌ 失败"
            route_text = f"预期: {target_route:12s} → 实际: {result['actual']:12s}"
            print(f"{status} | 测试#{test_id:2d} | {route_text} | 耗时: {result['time']:4.1f}s | {query[:35]}")

        except Exception as e:
            result["error"] = str(e)[:100]
            print(f"⚠️  错误 | 测试#{test_id:2d} | {str(e)[:60]}")

        async with self.lock:
            self.results.append(result)
            self.progress += 1

        return result

    async def run_batch(self, batch):
        """运行一批测试"""
        tasks = [
            self.test_one(tid, route, query, conn, uid)
            for tid, route, query, conn, uid in batch
        ]
        await asyncio.gather(*tasks)

    async def run_all(self):
        """运行所有测试"""
        print(f"\n{'='*100}")
        print(f"  📝 开始测试 | 共 {self.total} 个问题 | 并发数: {self.max_concurrent}")
        print(f"{'='*100}\n")

        # 分批并行执行
        for i in range(0, len(QUICK_TEST_CASES), self.max_concurrent):
            batch = QUICK_TEST_CASES[i:i+self.max_concurrent]
            await self.run_batch(batch)

            # 显示进度
            progress_pct = self.progress/self.total*100
            bar_len = 40
            filled = int(bar_len * self.progress / self.total)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\n  📊 进度: [{bar}] {self.progress}/{self.total} ({progress_pct:.1f}%)\n")

        self.print_summary()
        self.save_results()

    def print_summary(self):
        """打印摘要"""
        print(f"\n{'='*100}")
        print("📊 测试总结")
        print(f"{'='*100}\n")

        passed = sum(1 for r in self.results if r["match"] and not r["error"])
        failed = sum(1 for r in self.results if not r["match"] and not r["error"])
        errors = sum(1 for r in self.results if r["error"])

        total_time = sum(r["time"] for r in self.results if not r["error"])
        avg_time = total_time / len(self.results) if self.results else 0

        print(f"【统计信息】")
        print(f"  总测试数: {self.total} 个")
        print(f"  ✅ 通过: {passed} 个 ({passed/self.total*100:.1f}%)")
        print(f"  ❌ 失败: {failed} 个 ({failed/self.total*100:.1f}%)")
        print(f"  ⚠️  错误: {errors} 个 ({errors/self.total*100:.1f}%)")
        print(f"  ⏱️  总耗时: {total_time:.1f}秒 | 平均: {avg_time:.1f}秒/个")

        # 按路由统计
        print(f"\n{'='*100}")
        print("【按路由统计】")
        print(f"{'='*100}")

        route_stats = {}
        for r in self.results:
            target = r["target"]
            if target not in route_stats:
                route_stats[target] = {"total": 0, "pass": 0}
            route_stats[target]["total"] += 1
            if r["match"]:
                route_stats[target]["pass"] += 1

        # 表头
        print(f"\n  {'路由名称':<15s} │ {'通过/总数':^12s} │ {'通过率':>8s}")
        print(f"  {'-'*15}─┼─{'-'*12}─┼─{'-'*8}")

        # 数据行
        for route in sorted(route_stats.keys()):
            stats = route_stats[route]
            rate = stats["pass"] / stats["total"] * 100 if stats["total"] > 0 else 0
            ratio = f"{stats['pass']}/{stats['total']}"
            status_icon = "✅" if rate == 100 else "⚠️" if rate >= 80 else "❌"
            print(f"  {route:<15s} │ {ratio:^12s} │ {status_icon} {rate:>5.1f}%")

        # 失败案例
        failures = [r for r in self.results if not r["match"] and not r["error"]]
        if failures:
            print(f"\n{'='*100}")
            print("【❌ 路由不匹配的测试】")
            print(f"{'='*100}\n")
            for r in failures:
                print(f"  测试 #{r['id']:2d} │ 预期: {r['target']:<12s} → 实际: {r['actual']:<12s}")

        # 错误案例
        error_cases = [r for r in self.results if r["error"]]
        if error_cases:
            print(f"\n{'='*100}")
            print("【⚠️  发生错误的测试】")
            print(f"{'='*100}\n")
            for r in error_cases:
                print(f"  测试 #{r['id']:2d} │ 错误: {r['error']}")

    def save_results(self):
        """保存结果"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "total": self.total,
            "passed": sum(1 for r in self.results if r["match"]),
            "failed": sum(1 for r in self.results if not r["match"] and not r["error"]),
            "errors": sum(1 for r in self.results if r["error"]),
            "results": self.results,
        }

        filename = "test_results_quick.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*100}")
        print(f"  💾 测试结果已保存")
        print(f"{'='*100}")
        print(f"  文件: {filename}")
        print(f"  格式: JSON")
        print(f"  编码: UTF-8")


async def main():
    """主函数"""
    runner = QuickTestRunner(max_concurrent=3)  # 并发数3，避免过载
    await runner.initialize()
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())
