"""
生成Agent模块 - 负责生成最终答案
"""

from typing import Dict, Any, List
from datetime import datetime
from .base_module import BaseAgentModule

class GenerationAgent(BaseAgentModule):
    """答案生成Agent"""

    def __init__(self):
        super().__init__("generation_agent", "1.0.0")
        self.description = "根据检索结果生成清晰、有用的答案"

        # 答案模板
        self.templates = {
            "补贴查询": self._subsidy_template,
            "资格条件": self._eligibility_template,
            "申请流程": self._application_template,
            "材料准备": self._document_template,
            "一般咨询": self._general_template
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终答案"""
        query = data.get("original_query", "")
        intent = data.get("intent", "")
        results = data.get("retrieval_results", [])

        # 生成答案
        if results:
            # 使用对应的模板生成答案
            template_func = self.templates.get(intent, self._general_template)
            answer = template_func(query, results)
        else:
            # 没有找到结果时生成建议
            answer = self._no_result_template(query)

        # 生成后续建议
        suggestions = self._generate_suggestions(intent, results)

        # 更新数据
        result = {
            "answer": answer,
            "suggestions": suggestions,
            "source_count": len(results),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        data.update(result)
        return data

    def _subsidy_template(self, query: str, results: List[Dict[str, Any]]) -> str:
        """补贴查询答案模板"""
        answer = f"关于您的问题：{query}\n\n"
        answer += "为您找到以下补贴政策：\n\n"

        for i, policy in enumerate(results[:3], 1):
            answer += f"{i}. {policy['title']}\n"
            answer += f"   补贴金额：{policy['amount']}\n"
            answer += f"   主要内容：{policy['content']}\n"
            answer += f"   负责部门：{policy['department']}\n"
            answer += f"   咨询电话：{policy['phone']}\n\n"

        return answer.strip()

    def _eligibility_template(self, query: str, results: List[Dict[str, Any]]) -> str:
        """资格条件答案模板"""
        answer = f"关于申请资格：{query}\n\n"
        answer += "相关政策要求如下：\n\n"

        for i, policy in enumerate(results[:3], 1):
            answer += f"{i}. {policy['title']}\n"
            answer += "   申请条件：\n"
            for j, condition in enumerate(policy['conditions'], 1):
                answer += f"   ({j}) {condition}\n"
            answer += f"\n   咨询电话：{policy['phone']}\n\n"

        return answer.strip()

    def _application_template(self, query: str, results: List[Dict[str, Any]]) -> str:
        """申请流程答案模板"""
        answer = f"关于申请流程：{query}\n\n"
        answer += "根据相关政策，申请流程如下：\n\n"

        for i, policy in enumerate(results[:2], 1):
            answer += f"{i}. {policy['title']}\n"
            answer += f"   {policy['content']}\n"
            answer += f"   请联系{policy['department']}（电话：{policy['phone']}）\n\n"

        answer += "一般申请步骤：\n"
        answer += "1. 准备相关材料\n"
        answer += "2. 到指定部门或线上平台提交申请\n"
        answer += "3. 等待审核\n"
        answer += "4. 审核通过后领取补贴或享受政策\n"

        return answer.strip()

    def _document_template(self, query: str, results: List[Dict[str, Any]]) -> str:
        """材料准备答案模板"""
        answer = f"关于申请材料：{query}\n\n"

        # 根据申请条件推断需要的材料
        common_materials = {
            "企业": "营业执照、法人身份证、公司章程、银行开户许可证",
            "个人": "身份证、户口本、学历证明、技能证书",
            "创业": "创业计划书、场地租赁合同、员工花名册"
        }

        answer += "通常需要准备以下材料：\n\n"
        for category, materials in common_materials.items():
            if category in query:
                answer += f"• {materials}\n"

        if results:
            answer += "\n根据具体政策，可能还需要：\n"
            for policy in results[:2]:
                answer += f"• {policy['title']}所需材料请咨询{policy['department']}\n"

        return answer.strip()

    def _general_template(self, query: str, results: List[Dict[str, Any]]) -> str:
        """通用答案模板"""
        answer = f"关于您的咨询：{query}\n\n"

        if results:
            answer += "为您找到相关信息：\n\n"
            for i, policy in enumerate(results[:3], 1):
                answer += f"{i}. {policy['title']}\n"
                answer += f"   {policy['content']}\n"
                answer += f"   详情咨询：{policy['department']}（{policy['phone']}）\n\n"
        else:
            answer += "抱歉，暂时没有找到相关信息。\n\n"

        return answer.strip()

    def _no_result_template(self, query: str) -> str:
        """无结果时的答案模板"""
        answer = f"关于您的问题：{query}\n\n"
        answer += "抱歉，暂时没有找到完全匹配的政策信息。\n\n"
        answer += "建议您：\n"
        answer += "1. 尝试使用不同的关键词重新查询\n"
        answer += "2. 直接拨打政务服务热线：12345\n"
        answer += "3. 前往当地政务服务中心咨询\n"
        answer += "4. 访问政府官方网站查询最新政策\n\n"
        answer += "如果您能提供更多具体信息（如您所在的城市、企业类型等），\n"
        answer += "我可以为您提供更精准的帮助。"

        return answer

    def _generate_suggestions(
        self,
        intent: str,
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """生成后续建议"""
        suggestions = []

        # 根据意图生成相关建议
        if intent == "补贴查询":
            suggestions = [
                "了解申请资格条件",
                "查看申请流程",
                "准备申请材料"
            ]
        elif intent == "资格条件":
            suggestions = [
                "查看申请流程",
                "了解补贴金额",
                "咨询具体要求"
            ]
        elif intent == "申请流程":
            suggestions = [
                "查看申请材料",
                "了解办理时间",
                "查询办理地点"
            ]
        else:
            suggestions = [
                "查看相关补贴政策",
                "了解申请条件",
                "咨询办理部门"
            ]

        # 限制建议数量
        return suggestions[:3]