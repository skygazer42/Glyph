#!/usr/bin/env python3
"""
测试Agent路由逻辑 - 根据不同类型问题验证路由是否正确
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
    filename="agent_route_test.log",
    max_bytes=10485760,
    backup_count=5
)

class AgentRouteTestSuite:
    """Agent路由测试套件"""

    def __init__(self):
        self.service = AgentService()
        self.test_cases = self._prepare_test_cases()
        self.results = []

    def _prepare_test_cases(self) -> List[Dict[str, Any]]:
        """准备测试用例，覆盖所有路由场景"""
        return [
            # 1. FAQ缓存测试（需要先有QA对）
            {
                "category": "FAQ缓存",
                "query": "如何申请补贴",
                "expected_route": "faq_cache or knowledge",
                "attachments": [],
                "description": "常见问题，应优先查FAQ缓存"
            },

            # 2. 闲聊对话
            {
                "category": "闲聊",
                "query": "你好，今天天气不错",
                "expected_route": "dialogue",
                "attachments": [],
                "description": "闲聊内容，应走DialogueAgent"
            },
            {
                "category": "问候",
                "query": "早上好",
                "expected_route": "dialogue",
                "attachments": [],
                "description": "问候语，应走DialogueAgent"
            },
            {
                "category": "告别",
                "query": "再见，谢谢你的帮助",
                "expected_route": "dialogue",
                "attachments": [],
                "description": "告别语，应走DialogueAgent"
            },

            # 3. 模糊追问
            {
                "category": "模糊追问",
                "query": "我想了解一下",
                "expected_route": "clarify",
                "attachments": [],
                "description": "信息不足，需要ClarifierAgent澄清"
            },
            {
                "category": "模糊追问",
                "query": "这个怎么办",
                "expected_route": "clarify",
                "attachments": [],
                "description": "缺少具体内容，需要澄清"
            },

            # 4. 规则计算
            {
                "category": "补贴计算",
                "query": "济南市买一台3000元的冰箱，一级能效，能拿多少补贴",
                "expected_route": "rule_engine",
                "attachments": [],
                "description": "具体补贴计算，应走RuleEngineAgent"
            },
            {
                "category": "金额计算",
                "query": "新能源汽车补贴怎么计算",
                "expected_route": "rule_engine",
                "attachments": [],
                "description": "计算类问题，应走RuleEngineAgent"
            },

            # 5. 知识检索
            {
                "category": "政策咨询",
                "query": "北京市创业补贴政策有哪些",
                "expected_route": "knowledge",
                "attachments": [],
                "description": "政策查询，应走KnowledgeAgent"
            },
            {
                "category": "条件查询",
                "query": "申请失业保险金需要什么条件",
                "expected_route": "knowledge",
                "attachments": [],
                "description": "条件查询，应走KnowledgeAgent"
            },
            {
                "category": "流程咨询",
                "query": "如何办理营业执照",
                "expected_route": "knowledge",
                "attachments": [],
                "description": "流程查询，应走KnowledgeAgent"
            },

            # 6. 政策比较
            {
                "category": "政策比较",
                "query": "济南和青岛的创业补贴政策有什么区别",
                "expected_route": "knowledge",
                "attachments": [],
                "description": "比较类问题，应走KnowledgeAgent(comparison)"
            },

            # 7. 图谱总结（需要LightRAG）
            {
                "category": "关系总结",
                "query": "总结一下新能源汽车补贴涉及哪些部门和它们的关系",
                "expected_route": "graph",
                "attachments": [],
                "description": "关系图谱问题，应走GraphAgent"
            },
            {
                "category": "政策概括",
                "query": "概括一下所有创业扶持政策的主要内容",
                "expected_route": "graph",
                "attachments": [],
                "description": "概括总结问题，应走GraphAgent"
            },

            # 8. SQL查询（需要connection_id）
            {
                "category": "数据查询",
                "query": "查询数据库中有多少条政策记录",
                "expected_route": "text2sql or knowledge",
                "attachments": [],
                "description": "SQL类问题，有connection_id时走Text2SQLAgent"
            },
            {
                "category": "字段查询",
                "query": "policy表有哪些字段",
                "expected_route": "text2sql or knowledge",
                "attachments": [],
                "description": "数据库结构问题"
            },

            # 9. 多模态工作流（带图片附件）
            {
                "category": "图片识别",
                "query": "这张图片上的表格有哪些补贴政策",
                "expected_route": "workflow",
                "attachments": ["fake_image.jpg"],  # 模拟图片附件
                "description": "带图片的问题，应走WorkflowAgent"
            },

            # 10. 用户历史查询
            {
                "category": "用户历史",
                "query": "我之前查询过什么政策",
                "expected_route": "workflow",
                "attachments": [],
                "description": "用户历史问题，应走WorkflowAgent"
            },
            {
                "category": "个人资料",
                "query": "查看我的个人资料",
                "expected_route": "workflow",
                "attachments": [],
                "description": "用户资料问题，应走WorkflowAgent"
            }
        ]

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试用例"""
        try:
            # 准备附件（如果有）
            attachments = []
            for att_name in test_case.get("attachments", []):
                if "image" in att_name.lower():
                    # 模拟图片附件
                    attachments.append(Attachment(
                        filename=att_name,
                        content_type="image/jpeg",
                        size=1024,
                        data=b"fake_image_data"
                    ))

            # 调用answer方法
            result = await self.service.answer(
                query=test_case["query"],
                session_id="test_session",
                user_id="test_user",
                attachments=attachments,
                connection_id=1 if "sql" in test_case["query"].lower() else None
            )

            # 提取路由信息
            route = result.metadata.get("route", "unknown")
            intent = result.metadata.get("intent", {})
            rewritten = result.metadata.get("rewritten_query", "")

            # 判断是否符合预期
            expected = test_case["expected_route"]
            success = False
            if " or " in expected:
                # 多个可能的路由
                possible_routes = expected.split(" or ")
                success = any(r.strip() in route for r in possible_routes)
            else:
                success = expected == route

            return {
                "category": test_case["category"],
                "query": test_case["query"],
                "expected_route": expected,
                "actual_route": route,
                "intent": intent.get("intent") if isinstance(intent, dict) else intent,
                "confidence": intent.get("confidence", 0) if isinstance(intent, dict) else 0,
                "rewritten_query": rewritten,
                "success": success,
                "description": test_case["description"],
                "answer_preview": result.answer[:100] if result.answer else "无答案"
            }

        except Exception as e:
            return {
                "category": test_case["category"],
                "query": test_case["query"],
                "expected_route": test_case["expected_route"],
                "actual_route": "error",
                "success": False,
                "error": str(e)
            }

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("Agent路由测试开始")
        print("=" * 80)
        print()

        # 初始化服务
        await self.service.initialize()

        for i, test_case in enumerate(self.test_cases, 1):
            print(f"[{i}/{len(self.test_cases)}] 测试类别: {test_case['category']}")
            print(f"  查询: {test_case['query']}")

            result = await self.run_single_test(test_case)
            self.results.append(result)

            status = "✅" if result["success"] else "❌"
            print(f"  {status} 路由: {result['actual_route']} (期望: {result['expected_route']})")

            if "intent" in result:
                print(f"  意图: {result['intent']} (置信度: {result.get('confidence', 0):.2f})")

            if "error" in result:
                print(f"  ⚠️ 错误: {result['error']}")

            print()

        # 生成报告
        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        print("=" * 80)
        print("测试报告")
        print("=" * 80)
        print()

        # 统计
        total = len(self.results)
        success = sum(1 for r in self.results if r["success"])
        failed = total - success

        print(f"总测试数: {total}")
        print(f"成功: {success} ({success/total*100:.1f}%)")
        print(f"失败: {failed} ({failed/total*100:.1f}%)")
        print()

        # 按类别统计
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0}
            categories[cat]["total"] += 1
            if result["success"]:
                categories[cat]["success"] += 1

        print("各类别测试结果:")
        for cat, stats in categories.items():
            rate = stats["success"] / stats["total"] * 100
            status = "✅" if rate == 100 else "⚠️" if rate > 50 else "❌"
            print(f"  {status} {cat}: {stats['success']}/{stats['total']} ({rate:.0f}%)")

        # 失败的测试
        failures = [r for r in self.results if not r["success"]]
        if failures:
            print("\n失败的测试:")
            for f in failures:
                print(f"  ❌ {f['category']}: {f['query']}")
                print(f"     期望: {f['expected_route']}, 实际: {f['actual_route']}")
                if "error" in f:
                    print(f"     错误: {f['error']}")

        # 保存JSON报告
        report_path = Path("tests/agent_route_test_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n详细报告已保存至: {report_path}")


async def main():
    """主函数"""
    suite = AgentRouteTestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())