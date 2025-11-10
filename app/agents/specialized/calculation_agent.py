"""
计算Agent - 处理补贴金额计算
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

from autogen_core import MessageContext

from ..base.base_agent import PolicyAgentBase
from ...models.base import (
    UUID,
    BaseModel,
    Field,
    PolicyDocument,
    RetrievalResult
)


class CalculationRequest(BaseModel):
    """计算请求"""
    query: str
    policy_type: Optional[str] = None
    amount: Optional[float] = None
    percentage: Optional[float] = None
    base_amount: Optional[float] = None
    calculation_type: str  # fixed, percentage, tiered
    parameters: Dict[str, Any] = Field(default_factory=dict)


class CalculationResult(BaseModel):
    """计算结果"""
    calculated_amount: float
    calculation_breakdown: List[Dict[str, Any]]
    applicable_policies: List[str]
    assumptions: List[str]
    notes: List[str]
    confidence: float = Field(ge=0, le=1)


class CalculationAgent(PolicyAgentBase):
    """计算Agent - 处理补贴金额计算"""

    def __init__(self, model_client=None, **kwargs):
        super().__init__(
            agent_type="calculation_agent",
            name="CalculationAgent",
            description="处理各类补贴金额的计算和估算",
            **kwargs
        )
        self.model_client = model_client

        # 计算规则
        self.calculation_rules = {
            "appliance_subsidy": {
                "name": "家电以旧换新补贴",
                "rules": {
                    "tv": {"max_amount": 500, "percentage": 0.2, "min_amount": 100},
                    "fridge": {"max_amount": 600, "percentage": 0.2, "min_amount": 100},
                    "washing_machine": {"max_amount": 500, "percentage": 0.2, "min_amount": 100},
                    "air_conditioner": {"max_amount": 800, "percentage": 0.2, "min_amount": 100},
                    "computer": {"max_amount": 500, "percentage": 0.2, "min_amount": 100}
                }
            },
            "car_subsidy": {
                "name": "汽车消费补贴",
                "rules": {
                    "new_energy": {"max_amount": 10000, "percentage": 0.1, "min_amount": 3000},
                    "fuel_car": {"max_amount": 5000, "percentage": 0.05, "min_amount": 2000}
                }
            },
            "consumption_voucher": {
                "name": "消费券",
                "rules": {
                    "general": {"fixed_amount": 100, "max_per_person": 500},
                    "restaurant": {"fixed_amount": 50, "max_per_person": 200},
                    "retail": {"fixed_amount": 200, "max_per_person": 1000}
                }
            }
        }

    async def process_request(
        self,
        request: Dict[str, Any],
        context: MessageContext
    ) -> CalculationResult:
        """处理计算请求"""
        query = request.get("query", "")
        policy_documents = request.get("policy_documents", [])

        self.logger.info(f"Calculating for query: {query[:50]}...")

        try:
            # 1. 解析计算请求
            calc_request = self._parse_calculation_request(query)

            # 2. 从政策文档中提取计算规则
            if policy_documents:
                self._update_rules_from_policies(policy_documents)

            # 3. 执行计算
            result = await self._perform_calculation(calc_request)

            return result

        except Exception as e:
            self.logger.error(f"Error in calculation: {e}", exc_info=True)
            self.metrics["errors"] += 1

            return CalculationResult(
                calculated_amount=0,
                calculation_breakdown=[],
                applicable_policies=[],
                assumptions=["计算出错"],
                notes=[f"错误: {str(e)}"],
                confidence=0.0
            )

    def _parse_calculation_request(self, query: str) -> CalculationRequest:
        """解析计算请求"""
        # 提取金额
        amounts = self._extract_amounts(query)
        base_amount = amounts[0] if amounts else None

        # 提取百分比
        percentages = self._extract_percentages(query)
        percentage = percentages[0] if percentages else None

        # 识别计算类型
        calc_type = "fixed"
        if "%" in query or "比例" in query or "百分之" in query:
            calc_type = "percentage"
        elif "阶梯" in query or "分级" in query:
            calc_type = "tiered"

        # 识别政策类型
        policy_type = self._identify_policy_type(query)

        return CalculationRequest(
            query=query,
            policy_type=policy_type,
            amount=base_amount,
            percentage=percentage,
            base_amount=base_amount,
            calculation_type=calc_type,
            parameters=self._extract_parameters(query)
        )

    def _extract_amounts(self, text: str) -> List[float]:
        """提取金额"""
        patterns = [
            r"(\d+(?:\.\d+)?)\s*万?\s*元",
            r"(\d+(?:\.\d+)?)\s*千?\s*元",
            r"(\d+(?:\.\d+)?)\s*百?\s*元"
        ]

        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                amount = float(match)
                if "万" in text:
                    amount *= 10000
                elif "千" in text:
                    amount *= 1000
                elif "百" in text:
                    amount *= 100
                amounts.append(amount)

        return amounts

    def _extract_percentages(self, text: str) -> List[float]:
        """提取百分比"""
        patterns = [
            r"(\d+(?:\.\d+)?)\s*%",
            r"百分之\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*成"
        ]

        percentages = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                percentage = float(match)
                if "成" in text:
                    percentage *= 10
                percentages.append(percentage / 100)

        return percentages

    def _identify_policy_type(self, query: str) -> Optional[str]:
        """识别政策类型"""
        policy_keywords = {
            "appliance_subsidy": ["家电", "电视", "冰箱", "洗衣机", "空调", "电脑"],
            "car_subsidy": ["汽车", "车", "新能源", "燃油车"],
            "consumption_voucher": ["消费券", "购物券", "代金券"],
            "housing_subsidy": ["租房", "购房", "住房"],
            "employment_subsidy": ["创业", "就业", "失业"]
        }

        query_lower = query.lower()
        for policy_type, keywords in policy_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return policy_type

        return None

    def _extract_parameters(self, query: str) -> Dict[str, Any]:
        """提取计算参数"""
        parameters = {}

        # 提取商品类型
        if "电视" in query:
            parameters["product_type"] = "tv"
        elif "冰箱" in query:
            parameters["product_type"] = "fridge"
        elif "洗衣机" in query:
            parameters["product_type"] = "washing_machine"
        elif "空调" in query:
            parameters["product_type"] = "air_conditioner"
        elif "电脑" in query:
            parameters["product_type"] = "computer"

        # 提取能源类型
        if "新能源" in query or "电动" in query:
            parameters["energy_type"] = "new_energy"
        elif "燃油" in query or "汽油" in query:
            parameters["energy_type"] = "fuel"

        return parameters

    def _update_rules_from_policies(self, policy_documents: List[PolicyDocument]):
        """从政策文档更新计算规则"""
        # 这里应该解析政策文档中的具体规则
        # 简化处理，实际应该使用NLP提取
        for doc in policy_documents:
            if "补贴标准" in doc.content:
                # 提取具体金额和比例
                self._extract_subsidy_rules(doc.content)

    def _extract_subsidy_rules(self, content: str):
        """从内容中提取补贴规则"""
        # 简化的规则提取
        patterns = [
            (r"最高补贴\s*(\d+(?:\.\d+)?)\s*元", "max_amount"),
            (r"补贴比例\s*(\d+(?:\.\d+)?)\s*%", "percentage"),
            (r"最低补贴\s*(\d+(?:\.\d+)?)\s*元", "min_amount")
        ]

        for pattern, rule_type in patterns:
            matches = re.findall(pattern, content)
            if matches:
                # 更新规则
                pass  # 实际实现需要根据具体政策更新

    async def _perform_calculation(self, request: CalculationRequest) -> CalculationResult:
        """执行计算"""
        breakdown = []
        applicable_policies = []
        assumptions = []
        notes = []
        total_amount = 0

        if request.policy_type and request.policy_type in self.calculation_rules:
            policy_rule = self.calculation_rules[request.policy_type]
            applicable_policies.append(policy_rule["name"])

            if request.policy_type == "appliance_subsidy":
                total_amount, breakdown = self._calculate_appliance_subsidy(request)
            elif request.policy_type == "car_subsidy":
                total_amount, breakdown = self._calculate_car_subsidy(request)
            elif request.policy_type == "consumption_voucher":
                total_amount, breakdown = self._calculate_consumption_voucher(request)
            else:
                # 通用计算
                total_amount, breakdown = self._calculate_generic(request)

            # 添加假设和说明
            assumptions.append("计算基于当前政策的最新标准")
            if request.base_amount:
                assumptions.append(f"基于输入金额：{request.base_amount}元")

            notes.append("实际补贴金额可能因具体情况而异")
            notes.append("请以相关部门的最终审核结果为准")

        else:
            # 通用估算
            assumptions.append("未识别具体政策类型，使用通用估算")
            notes.append("请提供更多具体信息以获得准确计算")
            total_amount = request.base_amount * 0.1 if request.base_amount else 0
            breakdown.append({
                "项目": "估算补贴",
                "计算": "基础金额 × 10%",
                "金额": total_amount
            })

        # 计算置信度
        confidence = self._calculate_confidence(request, breakdown)

        return CalculationResult(
            calculated_amount=total_amount,
            calculation_breakdown=breakdown,
            applicable_policies=applicable_policies,
            assumptions=assumptions,
            notes=notes,
            confidence=confidence
        )

    def _calculate_appliance_subsidy(self, request: CalculationRequest) -> Tuple[float, List[Dict]]:
        """计算家电补贴"""
        product_type = request.parameters.get("product_type")
        rules = self.calculation_rules["appliance_subsidy"]["rules"]

        if not product_type or product_type not in rules:
            return 0, [{"错误": "未指定家电类型或该类型不在补贴范围内"}]

        rule = rules[product_type]
        amount = request.base_amount or 0

        # 计算补贴
        if request.calculation_type == "percentage":
            subsidy = amount * rule.get("percentage", 0.2)
        else:
            subsidy = rule.get("max_amount", 0)

        # 应用限制
        subsidy = min(subsidy, rule.get("max_amount", float('inf')))
        subsidy = max(subsidy, rule.get("min_amount", 0))

        breakdown = [
            {"项目": "商品原价", "金额": amount},
            {"项目": "补贴比例", "值": f"{rule.get('percentage', 0.2)*100}%"},
            {"项目": "最高限额", "值": f"{rule.get('max_amount', 0)}元"},
            {"项目": "计算补贴", "金额": subsidy}
        ]

        return subsidy, breakdown

    def _calculate_car_subsidy(self, request: CalculationRequest) -> Tuple[float, List[Dict]]:
        """计算汽车补贴"""
        energy_type = request.parameters.get("energy_type", "new_energy")
        rules = self.calculation_rules["car_subsidy"]["rules"]

        rule = rules.get(energy_type, rules["fuel_car"])
        amount = request.base_amount or 0

        # 计算补贴
        if request.calculation_type == "percentage":
            subsidy = amount * rule.get("percentage", 0.1)
        else:
            subsidy = rule.get("max_amount", 0)

        # 应用限制
        subsidy = min(subsidy, rule.get("max_amount", float('inf')))
        subsidy = max(subsidy, rule.get("min_amount", 0))

        breakdown = [
            {"项目": "车辆价格", "金额": amount},
            {"项目": "能源类型", "值": "新能源" if energy_type == "new_energy" else "燃油"},
            {"项目": "补贴比例", "值": f"{rule.get('percentage', 0.1)*100}%"},
            {"项目": "最高限额", "值": f"{rule.get('max_amount', 0)}元"},
            {"项目": "计算补贴", "金额": subsidy}
        ]

        return subsidy, breakdown

    def _calculate_consumption_voucher(self, request: CalculationRequest) -> Tuple[float, List[Dict]]:
        """计算消费券"""
        rules = self.calculation_rules["consumption_voucher"]["rules"]
        voucher_type = request.parameters.get("voucher_type", "general")

        rule = rules.get(voucher_type, rules["general"])
        amount = rule.get("fixed_amount", 100)

        breakdown = [
            {"项目": "消费券类型", "值": voucher_type},
            {"项目": "固定金额", "金额": amount},
            {"项目": "每人限领", "值": f"{rule.get('max_per_person', 0)}元"}
        ]

        return amount, breakdown

    def _calculate_generic(self, request: CalculationRequest) -> Tuple[float, List[Dict]]:
        """通用计算"""
        amount = request.base_amount or 0
        percentage = request.percentage or 0.1

        subsidy = amount * percentage

        breakdown = [
            {"项目": "基础金额", "金额": amount},
            {"项目": "补贴比例", "值": f"{percentage*100}%"},
            {"项目": "计算补贴", "金额": subsidy}
        ]

        return subsidy, breakdown

    def _calculate_confidence(self, request: CalculationRequest, breakdown: List[Dict]) -> float:
        """计算置信度"""
        confidence = 0.5

        # 有明确的政策类型
        if request.policy_type:
            confidence += 0.2

        # 有基础金额
        if request.base_amount and request.base_amount > 0:
            confidence += 0.1

        # 有具体的参数
        if request.parameters:
            confidence += 0.1

        # 计算成功
        if breakdown and not any("错误" in str(item) for item in breakdown):
            confidence += 0.1

        return min(confidence, 1.0)

    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type,
            "name": self.name,
            "calculation_rules": len(self.calculation_rules)
        }