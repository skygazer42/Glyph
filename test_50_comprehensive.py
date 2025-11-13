"""
完整的50问测试脚本
测试所有路由: faq_cache, dialogue, clarify, workflow, graph, rule_engine, text2sql, knowledge
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.service import AgentService
from app.models.base import Attachment


# 测试用例定义
TEST_CASES = [
    # ==================== FAQ Cache 路由 ====================
    {
        "id": 1,
        "target_route": "faq_cache",
        "query": "家电以旧换新补贴标准是多少？",
        "description": "命中 FAQ 第一条",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 2,
        "target_route": "faq_cache",
        "query": "申请创业补贴需要满足什么条件？",
        "description": "命中 FAQ 第二条",
        "connection_id": None,
        "user_id": None,
    },

    # ==================== Dialogue 路由 ====================
    {
        "id": 3,
        "target_route": "dialogue",
        "query": "你好，在吗？",
        "description": "Intent=greeting",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 4,
        "target_route": "dialogue",
        "query": "辛苦啦，今天先这样，下次聊。",
        "description": "Intent=farewell",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 5,
        "target_route": "dialogue",
        "query": "你都能做什么？",
        "description": "默认 chit_chat",
        "connection_id": None,
        "user_id": None,
    },

    # ==================== Clarify 路由 ====================
    {
        "id": 6,
        "target_route": "clarify",
        "query": "这个政策怎么样？",
        "description": "触发 Clarifier 补问",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 7,
        "target_route": "clarify",
        "query": "能不能说说那个东西？",
        "description": "极度模糊，期望 intent=clarification",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 8,
        "target_route": "clarify",
        "query": "资料对不对？",
        "description": "需澄清'哪份资料'",
        "connection_id": None,
        "user_id": None,
    },

    # ==================== Workflow (User Profile) 路由 ====================
    {
        "id": 9,
        "target_route": "workflow",
        "query": "帮我看看用户 12345 往年政策记录，有没有逾期？",
        "description": "USER_PROFILE 张三",
        "connection_id": None,
        "user_id": "12345",
    },
    {
        "id": 10,
        "target_route": "workflow",
        "query": "查询用户 67890 最近一次活动是什么？",
        "description": "USER_PROFILE 李四",
        "connection_id": None,
        "user_id": "67890",
    },
    {
        "id": 11,
        "target_route": "workflow",
        "query": "UserID=88888 是否申请过补贴？输出详细历史。",
        "description": "USER_PROFILE 王五",
        "connection_id": None,
        "user_id": "88888",
    },
    {
        "id": 12,
        "target_route": "workflow",
        "query": "能依据用户 12345 的历史给出申报建议吗？",
        "description": "user_history intent",
        "connection_id": None,
        "user_id": "12345",
    },

    # ==================== Graph 路由 ====================
    {
        "id": 19,
        "target_route": "graph",
        "query": "济南汽车消费补贴与新车商业保险补贴之间的联动环节有哪些？",
        "description": "多机构关系",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 20,
        "target_route": "graph",
        "query": "家电以旧换新政策里，旧机回收和财政审核的关联节点？",
        "description": "以旧换新 doc",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 21,
        "target_route": "graph",
        "query": "LightRAG 种子里提到的'动力电池企业'与'地方补贴审核'如何配合？",
        "description": "resources/data/lightrag 测试",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 22,
        "target_route": "graph",
        "query": "列出政策执行部门之间的协同职责（济南首保消费券）。",
        "description": "consumption_doc 段落",
        "connection_id": None,
        "user_id": None,
    },

    # ==================== Rule Engine 路由 ====================
    {
        "id": 23,
        "target_route": "rule_engine",
        "query": "购买 12 万元新能源车，按照 2025 济南补贴标准能领多少？请列出计算过程。",
        "description": "consumption_doc.txt 汽车补贴段",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 24,
        "target_route": "rule_engine",
        "query": "燃油车开票 32 万（不含税），对应补贴是多少？",
        "description": "汽车补贴计算",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 25,
        "target_route": "rule_engine",
        "query": "首保商业险 5200 元，根据首保消费券公告补贴多少？",
        "description": "首保补贴计算",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 26,
        "target_route": "rule_engine",
        "query": "保险金额 2500 元，补充公告后的首保补贴是多少？",
        "description": "补充公告段",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 27,
        "target_route": "rule_engine",
        "query": "青岛消费券档位：消费 25 万补贴多少？写出计算逻辑。",
        "description": "青岛消费券",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 28,
        "target_route": "rule_engine",
        "query": "家电消费：二级能效冰箱 1.5 万，补贴金额与限购说明？",
        "description": "demo_policy.txt",
        "connection_id": None,
        "user_id": None,
    },

    # ==================== Text2SQL 路由 ====================
    {
        "id": 29,
        "target_route": "text2sql",
        "query": "写一条 SQL：统计 db.policy_apply 表中 2024 年济南汽车补贴申请数。",
        "description": "含 SQL 关键字",
        "connection_id": 1,
        "user_id": None,
    },
    {
        "id": 30,
        "target_route": "text2sql",
        "query": "给我 SQL 查询 user_apply 中超过 2 次申报的用户 ID。",
        "description": "SQL 请求",
        "connection_id": 2,
        "user_id": None,
    },
    {
        "id": 31,
        "target_route": "text2sql",
        "query": "我要 SQL：按地区统计 subsidy_claim 金额总和，结果按降序。",
        "description": "需 connection_id",
        "connection_id": 1,
        "user_id": None,
    },
    {
        "id": 32,
        "target_route": "text2sql",
        "query": "把最新 50 条申请的 rule_id 和 submit_time 查出来。",
        "description": "SQL route",
        "connection_id": 1,
        "user_id": None,
    },
    {
        "id": 33,
        "target_route": "text2sql",
        "query": "列出 policy_docs 表中 doc_type='coupon' 的标题。",
        "description": "SQL 关键词",
        "connection_id": 1,
        "user_id": None,
    },

    # ==================== Knowledge 路由 ====================
    {
        "id": 34,
        "target_route": "knowledge",
        "query": "泉城购零售券的满减档位有哪些？",
        "description": "consumption_doc.txt 零售券段",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 35,
        "target_route": "knowledge",
        "query": "餐饮消费券 200 元档需要满足的条件？",
        "description": "餐饮券",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 36,
        "target_route": "knowledge",
        "query": "济南汽车补贴的购车、申报、资料修改三个时间窗口分别是什么？",
        "description": "consumption_doc 日期",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 39,
        "target_route": "knowledge",
        "query": "青岛消费券活动持续到哪一天？",
        "description": "青岛消费券文档",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 40,
        "target_route": "knowledge",
        "query": "家电补贴方案里空调单人限购几台？",
        "description": "demo_policy.txt",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 41,
        "target_route": "knowledge",
        "query": "一级与二级能效家电补贴比例分别是多少？",
        "description": "demo_policy",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 42,
        "target_route": "knowledge",
        "query": "家电补贴活动起止日期？",
        "description": "demo_policy",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 43,
        "target_route": "knowledge",
        "query": "说明 2025 年首保消费券的各档补贴额度。",
        "description": "consumption_doc",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 44,
        "target_route": "knowledge",
        "query": "追加的 3000 万汽车补贴公告主要说明了什么？",
        "description": "追加公告段",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 45,
        "target_route": "knowledge",
        "query": "第二轮与第三轮汽车消费礼包标准有区别吗？",
        "description": "检验回答",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 46,
        "target_route": "knowledge",
        "query": "LightRAG 种子里有哪些政策主题？请概述。",
        "description": "resources/data/lightrag 内容",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 47,
        "target_route": "knowledge",
        "query": "user_profiles 中白金用户来自哪个地区？",
        "description": "张三=深圳南山",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 48,
        "target_route": "knowledge",
        "query": "王五有没有提交过补贴？官方描述是什么？",
        "description": "user_profiles 88888",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 49,
        "target_route": "knowledge",
        "query": "FAQ/embedding 数据里与'申报进度'相关的问法有哪些？如何回复？",
        "description": "faq_embeddings",
        "connection_id": None,
        "user_id": None,
    },
    {
        "id": 50,
        "target_route": "knowledge",
        "query": "结合资源文件，概述济南 2025 年汽车补贴额度总量及先到先得规则。",
        "description": "consumption_doc 段落",
        "connection_id": None,
        "user_id": None,
    },
]


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.agent_service = None
        self.results = []
        self.stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "route_match": 0,
            "route_mismatch": 0,
            "errors": 0,
        }

    async def initialize(self):
        """初始化 AgentService"""
        print("正在初始化 AgentService...")
        self.agent_service = AgentService()
        await self.agent_service.initialize()
        print("✅ AgentService 初始化完成\n")

    async def run_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试"""
        test_id = test_case["id"]
        target_route = test_case["target_route"]
        query = test_case["query"]
        description = test_case["description"]
        connection_id = test_case.get("connection_id")
        user_id = test_case.get("user_id")

        print(f"\n{'='*80}")
        print(f"测试 #{test_id}: {target_route} 路由")
        print(f"问题: {query}")
        print(f"说明: {description}")
        print(f"{'='*80}")

        result = {
            "id": test_id,
            "target_route": target_route,
            "query": query,
            "description": description,
            "actual_route": None,
            "answer": None,
            "confidence": None,
            "processing_time": 0,
            "route_match": False,
            "error": None,
            "metadata": {},
        }

        try:
            start_time = time.time()

            # 调用 AgentService
            final = await self.agent_service.process_query(
                query=query,
                session_id=f"test_session_{test_id}",
                user_id=user_id,
                connection_id=connection_id,
                attachments=None,
            )

            elapsed = time.time() - start_time

            # 提取结果
            actual_route = final.metadata.get("route", "unknown")
            result["actual_route"] = actual_route
            result["answer"] = final.answer[:200] + "..." if len(final.answer) > 200 else final.answer
            result["confidence"] = final.confidence
            result["processing_time"] = elapsed
            result["route_match"] = (actual_route == target_route)
            result["metadata"] = final.metadata

            # 统计
            self.stats["total"] += 1
            if result["route_match"]:
                self.stats["route_match"] += 1
                self.stats["passed"] += 1
                status = "✅ PASS"
            else:
                self.stats["route_mismatch"] += 1
                self.stats["failed"] += 1
                status = "❌ FAIL"

            print(f"\n{status} | 路由: {actual_route} (预期: {target_route})")
            print(f"耗时: {elapsed:.2f}s | 置信度: {result['confidence']:.3f}")
            print(f"答案摘要: {result['answer']}")

        except Exception as e:
            result["error"] = str(e)
            self.stats["total"] += 1
            self.stats["errors"] += 1
            self.stats["failed"] += 1
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

        self.results.append(result)
        return result

    async def run_all_tests(self, test_cases: List[Dict[str, Any]]):
        """运行所有测试"""
        print(f"\n{'='*80}")
        print(f"开始测试 {len(test_cases)} 个问题")
        print(f"{'='*80}\n")

        for test_case in test_cases:
            await self.run_test(test_case)
            # 短暂延迟，避免过载
            await asyncio.sleep(0.5)

        self.print_summary()
        self.save_results()

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n\n{'='*80}")
        print("测试总结")
        print(f"{'='*80}")
        print(f"总测试数: {self.stats['total']}")
        print(f"通过: {self.stats['passed']} ({self.stats['passed']/self.stats['total']*100:.1f}%)")
        print(f"失败: {self.stats['failed']} ({self.stats['failed']/self.stats['total']*100:.1f}%)")
        print(f"  - 路由匹配: {self.stats['route_match']}")
        print(f"  - 路由不匹配: {self.stats['route_mismatch']}")
        print(f"  - 错误: {self.stats['errors']}")
        print(f"{'='*80}")

        # 按路由统计
        print("\n按目标路由统计:")
        route_stats = {}
        for result in self.results:
            target = result["target_route"]
            if target not in route_stats:
                route_stats[target] = {"total": 0, "match": 0}
            route_stats[target]["total"] += 1
            if result["route_match"]:
                route_stats[target]["match"] += 1

        for route, stats in sorted(route_stats.items()):
            total = stats["total"]
            match = stats["match"]
            rate = match / total * 100 if total > 0 else 0
            print(f"  {route:15s}: {match:2d}/{total:2d} ({rate:5.1f}%)")

        # 失败案例
        if self.stats["route_mismatch"] > 0:
            print(f"\n路由不匹配的案例:")
            for result in self.results:
                if not result["route_match"] and not result["error"]:
                    print(f"  #{result['id']:2d} | 预期: {result['target_route']:12s} -> 实际: {result['actual_route']:12s} | {result['query'][:50]}")

        if self.stats["errors"] > 0:
            print(f"\n出错的案例:")
            for result in self.results:
                if result["error"]:
                    print(f"  #{result['id']:2d} | {result['query'][:50]} | 错误: {result['error']}")

    def save_results(self):
        """保存测试结果"""
        output_file = "test_results_50_questions.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "stats": self.stats,
                "results": self.results,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 测试结果已保存到: {output_file}")

        # 生成 Markdown 报告
        self.generate_markdown_report()

    def generate_markdown_report(self):
        """生成 Markdown 测试报告"""
        output_file = "test_results_50_questions.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# 50问综合测试报告\n\n")
            f.write(f"**生成时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 统计概览
            f.write("## 测试统计\n\n")
            f.write(f"- **总测试数:** {self.stats['total']}\n")
            f.write(f"- **通过:** {self.stats['passed']} ({self.stats['passed']/self.stats['total']*100:.1f}%)\n")
            f.write(f"- **失败:** {self.stats['failed']} ({self.stats['failed']/self.stats['total']*100:.1f}%)\n")
            f.write(f"  - 路由匹配: {self.stats['route_match']}\n")
            f.write(f"  - 路由不匹配: {self.stats['route_mismatch']}\n")
            f.write(f"  - 错误: {self.stats['errors']}\n\n")

            # 按路由统计
            f.write("## 按路由统计\n\n")
            f.write("| 路由 | 通过 | 总数 | 通过率 |\n")
            f.write("|------|------|------|--------|\n")

            route_stats = {}
            for result in self.results:
                target = result["target_route"]
                if target not in route_stats:
                    route_stats[target] = {"total": 0, "match": 0}
                route_stats[target]["total"] += 1
                if result["route_match"]:
                    route_stats[target]["match"] += 1

            for route, stats in sorted(route_stats.items()):
                total = stats["total"]
                match = stats["match"]
                rate = match / total * 100 if total > 0 else 0
                f.write(f"| {route} | {match} | {total} | {rate:.1f}% |\n")

            # 详细结果
            f.write("\n## 详细测试结果\n\n")
            for result in self.results:
                status = "✅" if result["route_match"] else ("❌" if not result["error"] else "⚠️")
                f.write(f"### {status} 测试 #{result['id']}: {result['target_route']} 路由\n\n")
                f.write(f"**问题:** {result['query']}\n\n")
                f.write(f"**说明:** {result['description']}\n\n")
                f.write(f"**预期路由:** {result['target_route']}\n\n")
                f.write(f"**实际路由:** {result['actual_route']}\n\n")
                f.write(f"**置信度:** {result['confidence']}\n\n")
                f.write(f"**耗时:** {result['processing_time']:.2f}s\n\n")

                if result["error"]:
                    f.write(f"**错误:** ```\n{result['error']}\n```\n\n")
                else:
                    f.write(f"**答案摘要:**\n```\n{result['answer']}\n```\n\n")

                f.write("---\n\n")

        print(f"✅ Markdown 报告已保存到: {output_file}")


async def main():
    """主函数"""
    runner = TestRunner()
    await runner.initialize()
    await runner.run_all_tests(TEST_CASES)


if __name__ == "__main__":
    asyncio.run(main())
