#!/usr/bin/env python3
"""
基于实际政策文档内容的问答测试
测试系统是否能准确回答具体的政策问题
"""

import asyncio
import json
from typing import List, Dict, Any
from pathlib import Path
import sys

# 添加项目根目录
sys.path.append(str(Path(__file__).parent.parent))

from app.agents.service.agent_service import AgentService
from app.models.base import Attachment
from app.core import logging_manager

# 配置日志
logging_manager.configure(
    log_dir="logs",
    filename="policy_qa_test.log",
    max_bytes=10485760,
    backup_count=5
)

class PolicyQATestSuite:
    """基于实际政策文档的问答测试套件"""

    def __init__(self):
        self.service = AgentService()
        self.test_cases = self._prepare_test_cases()
        self.results = []

    def _prepare_test_cases(self) -> List[Dict[str, Any]]:
        """根据实际文档内容准备测试用例"""
        return [
            # ========== 济南市家电以旧换新政策 ==========
            {
                "category": "家电补贴标准",
                "query": "济南市购买一级能效冰箱补贴多少",
                "expected_answer": "20%（15%基础+5%额外），每件最高2000元",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "家电补贴标准",
                "query": "济南市二级能效洗衣机补贴比例是多少",
                "expected_answer": "15%，每件最高2000元",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "补贴范围",
                "query": "济南市家电以旧换新包括哪些产品",
                "expected_answer": "12类：电冰箱、洗衣机、电视机、空调、电脑、热水器、家用灶具、吸油烟机、净水器、洗碗机、微波炉、电饭煲",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "补贴限额",
                "query": "每个人可以享受几件家电补贴",
                "expected_answer": "每类产品1件，空调最多3件",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "补贴资格",
                "query": "家电补贴资格领取后多久内要使用",
                "expected_answer": "2个自然日内",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },

            # ========== 手机平板智能手表补贴政策 ==========
            {
                "category": "数码产品补贴",
                "query": "济南市买手机补贴多少",
                "expected_answer": "15%，每件最高500元",
                "source": "济南市2025年手机、平板、智能手表（手环）购新补贴实施细则"
            },
            {
                "category": "数码产品限制",
                "query": "手机补贴的价格上限是多少",
                "expected_answer": "单件销售价格不超过6000元",
                "source": "济南市2025年手机、平板、智能手表（手环）购新补贴实施细则"
            },
            {
                "category": "数码产品范围",
                "query": "济南市数码产品补贴包括哪些",
                "expected_answer": "手机、平板、智能手表（手环）3类",
                "source": "济南市2025年手机、平板、智能手表（手环）购新补贴实施细则"
            },

            # ========== 补贴计算测试 ==========
            {
                "category": "具体计算",
                "query": "济南市买一台5000元的一级能效冰箱能补贴多少钱",
                "expected_answer": "1000元（5000*20%）",
                "source": "计算：5000*20%=1000元"
            },
            {
                "category": "具体计算",
                "query": "济南市买一个4000元的手机能补贴多少钱",
                "expected_answer": "500元（4000*15%=600，但最高500元）",
                "source": "计算：min(4000*15%, 500)=500元"
            },
            {
                "category": "具体计算",
                "query": "济南市买一台3000元二级能效洗衣机补贴多少",
                "expected_answer": "450元（3000*15%）",
                "source": "计算：3000*15%=450元"
            },

            # ========== 补贴流程相关 ==========
            {
                "category": "申领流程",
                "query": "在哪里领取济南市家电补贴资格",
                "expected_answer": "济南市泉城购服务平台",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "申领流程",
                "query": "家电补贴资格每个品类可以领取几次",
                "expected_answer": "3次领取机会",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },

            # ========== 政策对比问题 ==========
            {
                "category": "政策对比",
                "query": "家电补贴和手机补贴的最高限额分别是多少",
                "expected_answer": "家电每件最高2000元，手机每件最高500元",
                "source": "政策对比"
            },
            {
                "category": "政策对比",
                "query": "一级能效和二级能效家电的补贴差别是什么",
                "expected_answer": "一级能效20%（15%+5%），二级能效15%",
                "source": "政策对比"
            },

            # ========== 特殊条件问题 ==========
            {
                "category": "特殊条件",
                "query": "2024年已经享受过冰箱补贴，2025年还能再申请吗",
                "expected_answer": "可以继续享受补贴",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },
            {
                "category": "特殊条件",
                "query": "没有能效标识的家电怎么补贴",
                "expected_answer": "补贴标准不得高于2级能效产品补贴标准（15%）",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },

            # ========== 废旧家电回收 ==========
            {
                "category": "回收政策",
                "query": "废旧家电在哪里预约回收",
                "expected_answer": "济南市泉城购服务平台或电商平台",
                "source": "济南市2025年家电以旧换新补贴实施细则"
            },

            # ========== 复杂综合问题 ==========
            {
                "category": "综合问题",
                "query": "我想在济南买一台8000元的一级能效空调和一个3000元的手机，总共能补贴多少",
                "expected_answer": "空调1600元（8000*20%），手机450元（3000*15%），总计2050元",
                "source": "综合计算"
            },
            {
                "category": "综合问题",
                "query": "一个家庭三口人在济南最多能买几台空调享受补贴",
                "expected_answer": "每人最多3件，三口人最多9件",
                "source": "政策理解"
            }
        ]

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试用例"""
        try:
            # 调用answer方法
            result = await self.service.answer(
                query=test_case["query"],
                session_id="test_session",
                user_id="test_user"
            )

            # 提取答案和相关信息
            answer = result.answer if result else "无答案"
            metadata = result.metadata if result else {}
            route = metadata.get("route", "unknown")
            confidence = result.confidence if result else 0

            # 简单判断答案是否包含关键信息
            expected = test_case["expected_answer"]
            answer_correct = self._check_answer_correctness(answer, expected)

            return {
                "category": test_case["category"],
                "query": test_case["query"],
                "expected_answer": expected,
                "actual_answer": answer[:200] if answer else "无答案",
                "route": route,
                "confidence": confidence,
                "correct": answer_correct,
                "source": test_case["source"]
            }

        except Exception as e:
            return {
                "category": test_case["category"],
                "query": test_case["query"],
                "expected_answer": test_case["expected_answer"],
                "actual_answer": f"错误: {str(e)}",
                "correct": False,
                "error": str(e)
            }

    def _check_answer_correctness(self, answer: str, expected: str) -> bool:
        """检查答案是否包含关键信息"""
        if not answer:
            return False

        # 提取关键数字和信息
        key_parts = []

        # 提取百分比
        import re
        percentages = re.findall(r'\d+%', expected)
        for p in percentages:
            if p in answer:
                key_parts.append(p)

        # 提取金额
        amounts = re.findall(r'\d+元', expected)
        for a in amounts:
            if a in answer or a.replace('元', '') in answer:
                key_parts.append(a)

        # 提取数字
        numbers = re.findall(r'\d+', expected)
        for n in numbers:
            if n in answer:
                key_parts.append(n)

        # 提取关键词
        keywords = ["空调", "冰箱", "洗衣机", "手机", "平板", "一级能效", "二级能效",
                   "泉城购", "12类", "3类", "2个自然日", "3次"]
        for kw in keywords:
            if kw in expected and kw in answer:
                key_parts.append(kw)

        # 如果找到超过一半的关键信息，认为正确
        if len(key_parts) >= 2:
            return True

        # 特殊处理某些答案格式
        if "15%" in expected and "15" in answer:
            return True
        if "20%" in expected and "20" in answer:
            return True

        return False

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("基于实际政策文档的问答测试")
        print("=" * 80)
        print()

        # 初始化服务
        await self.service.initialize()

        # 按类别分组运行测试
        categories = {}
        for test_case in self.test_cases:
            cat = test_case["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(test_case)

        for category, cases in categories.items():
            print(f"\n【{category}】({len(cases)}个问题)")
            print("-" * 60)

            for i, test_case in enumerate(cases, 1):
                print(f"{i}. 问题: {test_case['query']}")

                result = await self.run_single_test(test_case)
                self.results.append(result)

                status = "✅" if result["correct"] else "❌"
                print(f"   {status} 期望: {test_case['expected_answer']}")
                print(f"   实际: {result['actual_answer'][:100]}...")
                print(f"   路由: {result.get('route', 'unknown')} | 置信度: {result.get('confidence', 0):.2f}")
                print()

        # 生成报告
        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 80)
        print("测试报告汇总")
        print("=" * 80)

        # 统计
        total = len(self.results)
        correct = sum(1 for r in self.results if r.get("correct", False))
        incorrect = total - correct

        print(f"\n📊 总体统计:")
        print(f"  总问题数: {total}")
        print(f"  回答正确: {correct} ({correct/total*100:.1f}%)")
        print(f"  回答错误: {incorrect} ({incorrect/total*100:.1f}%)")

        # 按类别统计
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "correct": 0}
            categories[cat]["total"] += 1
            if result.get("correct", False):
                categories[cat]["correct"] += 1

        print(f"\n📈 分类统计:")
        for cat, stats in categories.items():
            rate = stats["correct"] / stats["total"] * 100
            status = "✅" if rate >= 80 else "⚠️" if rate >= 50 else "❌"
            print(f"  {status} {cat}: {stats['correct']}/{stats['total']} ({rate:.0f}%)")

        # 路由统计
        routes = {}
        for result in self.results:
            route = result.get("route", "unknown")
            if route not in routes:
                routes[route] = 0
            routes[route] += 1

        print(f"\n🔀 路由分布:")
        for route, count in sorted(routes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {route}: {count}次 ({count/total*100:.1f}%)")

        # 错误的问题
        errors = [r for r in self.results if not r.get("correct", False)]
        if errors:
            print(f"\n❌ 回答错误的问题:")
            for e in errors[:10]:  # 只显示前10个
                print(f"  问题: {e['query']}")
                print(f"  期望: {e['expected_answer']}")
                print(f"  实际: {e['actual_answer'][:100]}...")
                print()

        # 保存JSON报告
        report_path = Path("tests/policy_qa_test_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细报告已保存至: {report_path}")


async def main():
    """主函数"""
    suite = PolicyQATestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())