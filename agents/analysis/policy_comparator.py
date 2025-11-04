"""
政策比较Agent - 比较多个政策文件的差异和共同点
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import difflib
from collections import defaultdict
from pydantic import Field
from pydantic_settings import  BaseSettings
from uuid import UUID
from autogen_core import MessageContext

from ..base.base_agent import PolicyAgentBase
from ...models.base import (
    AgentType,
    PolicyDocument,
    PolicyAnalysis,
    QueryIntent,
    BaseModel
)


class PolicyComparison(BaseModel):
    """政策比较结果"""
    query_id: UUID
    documents: List[UUID]  # 比较的文档ID列表
    comparison_type: str  # 比较类型：benefits, eligibility, process, etc.
    similarities: List[str] = BaseSettings(default_factory=list)
    differences: List[Dict[str, Any]] = BaseSettings(default_factory=list)
    summary: Optional[str] = None
    comparison_table: Optional[Dict[str, List[Any]]] = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class PolicyComparatorAgent(PolicyAgentBase):
    """政策比较Agent，负责分析和比较多个政策文件"""

    def __init__(self, model_client=None, **kwargs):
        super().__init__(
            agent_type=AgentType.POLICY_ANALYZER,
            name="PolicyComparator",
            description="比较多个政策文件的差异和共同点",
            **kwargs
        )
        self.model_client = model_client

        # 比较维度定义
        self.comparison_dimensions = {
            "eligibility": {
                "name": "申请资格",
                "keywords": ["申请条件", "资格要求", "申请人", "符合条件", "申请资格"],
                "weight": 0.3
            },
            "benefits": {
                "name": "补贴标准",
                "keywords": ["补贴", "补助", "金额", "标准", "额度", "最高"],
                "weight": 0.25
            },
            "process": {
                "name": "申请流程",
                "keywords": ["流程", "步骤", "程序", "办理", "申请方式"],
                "weight": 0.2
            },
            "documents": {
                "name": "所需材料",
                "keywords": ["材料", "证件", "文件", "资料", "证明"],
                "weight": 0.15
            },
            "deadlines": {
                "name": "时间节点",
                "keywords": ["截止", "时间", "日期", "期限", "有效期"],
                "weight": 0.1
            }
        }

    async def process_request(
        self,
        request: Dict[str, Any],
        context: MessageContext
    ) -> PolicyComparison:
        """处理政策比较请求"""
        documents = request.get("documents", [])
        query_id = request.get("query_id")
        comparison_type = request.get("comparison_type", "all")

        self.logger.info(f"Comparing {len(documents)} policies")

        start_time = asyncio.get_event_loop().time()

        try:
            if len(documents) < 2:
                raise ValueError("需要至少2个文档进行比较")

            # 执行比较分析
            comparison_result = await self._compare_policies(
                documents, query_id, comparison_type
            )

            # 更新指标
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(processing_time)

            self.logger.info(f"Policy comparison completed in {processing_time:.3f}s")

            return comparison_result

        except Exception as e:
            self.logger.error(f"Error comparing policies: {e}", exc_info=True)
            self.metrics["errors"] += 1
            raise

    async def _compare_policies(
        self,
        documents: List[PolicyDocument],
        query_id: UUID,
        comparison_type: str
    ) -> PolicyComparison:
        """执行政策比较"""
        comparison_result = PolicyComparison(
            query_id=query_id,
            documents=[doc.id for doc in documents]
        )

        # 根据比较类型选择维度
        if comparison_type == "all":
            dimensions = self.comparison_dimensions.keys()
        else:
            dimensions = [comparison_type] if comparison_type in self.comparison_dimensions else []

        # 初始化比较结果
        all_similarities = []
        all_differences = []
        comparison_table = defaultdict(list)

        # 对每个维度进行比较
        for dimension in dimensions:
            dim_config = self.comparison_dimensions[dimension]
            similarities, differences, table_data = await self._compare_dimension(
                documents, dimension, dim_config
            )

            all_similarities.extend(similarities)
            all_differences.extend(differences)
            comparison_table[dim_config["name"]] = table_data

        # 生成比较摘要
        summary = await self._generate_comparison_summary(
            documents, all_similarities, all_differences
        )

        # 计算整体置信度
        confidence = self._calculate_comparison_confidence(
            len(documents), len(all_similarities), len(all_differences)
        )

        comparison_result.similarities = all_similarities
        comparison_result.differences = all_differences
        comparison_result.summary = summary
        comparison_result.comparison_table = dict(comparison_table)
        comparison_result.confidence = confidence

        return comparison_result

    async def _compare_dimension(
        self,
        documents: List[PolicyDocument],
        dimension: str,
        dim_config: Dict[str, Any]
    ) -> Tuple[List[str], List[Dict[str, Any]], List[Any]]:
        """比较特定维度"""
        similarities = []
        differences = []
        table_data = []

        # 提取每个文档在该维度的信息
        dimension_info = []
        for doc in documents:
            info = await self._extract_dimension_info(doc, dimension)
            dimension_info.append({
                "doc_id": doc.id,
                "doc_title": doc.title,
                "info": info
            })

        # 找出共同点
        common_elements = self._find_common_elements(dimension_info)
        for element in common_elements:
            similarities.append(f"{dim_config['name']}：{element}")

        # 找出差异点
        unique_elements = self._find_unique_elements(dimension_info)
        for element in unique_elements:
            differences.append({
                "dimension": dim_config["name"],
                "type": "difference",
                "content": element,
                "affected_policies": element["policies"]
            })

        # 构建表格数据
        table_header = [dim_config["name"]]
        table_header.extend([doc["doc_title"][:20] + "..." for doc in dimension_info])
        table_data.append(table_header)

        # 添加比较内容到表格
        all_keys = set()
        for info in dimension_info:
            all_keys.update(info["info"].keys())

        for key in sorted(all_keys):
            row = [key]
            for info in dimension_info:
                value = info["info"].get(key, "无")
                row.append(str(value)[:50] + "..." if len(str(value)) > 50 else str(value))
            table_data.append(row)

        return similarities, differences, table_data

    async def _extract_dimension_info(
        self,
        document: PolicyDocument,
        dimension: str
    ) -> Dict[str, Any]:
        """从文档中提取特定维度的信息"""
        info = {}
        content = document.content.lower()

        if dimension == "eligibility":
            # 提取申请条件
            info = await self._extract_eligibility_info(content)
        elif dimension == "benefits":
            # 提取补贴标准
            info = await self._extract_benefit_info(content)
        elif dimension == "process":
            # 提取申请流程
            info = await self._extract_process_info(content)
        elif dimension == "documents":
            # 提取所需材料
            info = await self._extract_document_info(content)
        elif dimension == "deadlines":
            # 提取时间节点
            info = await self._extract_deadline_info(content)

        return info

    async def _extract_eligibility_info(self, content: str) -> Dict[str, Any]:
        """提取申请条件信息"""
        # 这里应该使用NLP技术提取，简化处理
        eligibility_info = {}

        # 常见条件模式
        patterns = {
            "户籍要求": r"(?:户籍|户口)[：:]\s*([^。\n]+)",
            "年龄要求": r"(?:年龄|年纪)[：:]\s*([^。\n]+)",
            "收入要求": r"(?:收入|收入标准)[：:]\s*([^。\n]+)",
            "社保要求": r"(?:社保|社会保险)[：:]\s*([^。\n]+)",
            "居住要求": r"(?:居住|居住证)[：:]\s*([^。\n]+)"
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                eligibility_info[key] = match.group(1).strip()

        return eligibility_info

    async def _extract_benefit_info(self, content: str) -> Dict[str, Any]:
        """提取补贴标准信息"""
        benefit_info = {}

        # 提取金额信息
        money_patterns = [
            r"最高补贴[：:]?\s*(\d+(?:\.\d+)?[万千百]?元)",
            r"补贴标准[：:]?\s*(\d+(?:\.\d+)?[万千百]?元)",
            r"补助金额[：:]?\s*(\d+(?:\.\d+)?[万千百]?元)",
            r"按比例[：:]?\s*(\d+(?:\.\d+)?%)"
        ]

        for pattern in money_patterns:
            matches = re.findall(pattern, content)
            if matches:
                benefit_info["补贴金额"] = matches[0]
                break

        return benefit_info

    async def _extract_process_info(self, content: str) -> Dict[str, Any]:
        """提取申请流程信息"""
        process_info = {}

        # 查找流程步骤
        step_pattern = r"(?:第[一二三四五六七八九十\d]+步|步骤\d+)[：:]?\s*([^。\n]+)"
        steps = re.findall(step_pattern, content)

        if steps:
            for i, step in enumerate(steps[:5], 1):
                process_info[f"第{i}步"] = step.strip()

        return process_info

    async def _extract_document_info(self, content: str) -> Dict[str, Any]:
        """提取所需材料信息"""
        document_info = {}

        # 常见材料类型
        material_patterns = {
            "身份证": r"身份证[复印件]?|身份证明",
            "户口本": r"户口本[复印件]?|户籍证明",
            "申请表": r"申请表|申请书",
            "收入证明": r"收入证明|工资流水",
            "社保记录": r"社保[记录|证明]|缴费记录"
        }

        for material, pattern in material_patterns.items():
            if re.search(pattern, content):
                document_info[material] = "需要"

        return document_info

    async def _extract_deadline_info(self, content: str) -> Dict[str, Any]:
        """提取时间节点信息"""
        deadline_info = {}

        # 时间模式
        time_patterns = [
            (r"(\d{4}年\d{1,2}月\d{1,2}日)", "截止日期"),
            (r"每年\s*([一二三四]季度)", "申请时间"),
            (r"有效期\s*([^\n。]+)", "有效期")
        ]

        for pattern, label in time_patterns:
            match = re.search(pattern, content)
            if match:
                deadline_info[label] = match.group(1).strip()

        return deadline_info

    def _find_common_elements(self, dimension_info: List[Dict]) -> List[str]:
        """找出所有文档的共同元素"""
        common_elements = []

        # 获取第一个文档的所有键
        if dimension_info:
            first_keys = set(dimension_info[0]["info"].keys())

            # 找出所有文档都有的键
            for info in dimension_info[1:]:
                first_keys &= set(info["info"].keys())

            # 检查这些键的值是否也相同
            for key in first_keys:
                values = [info["info"][key] for info in dimension_info]
                if len(set(str(v) for v in values)) == 1:  # 所有值相同
                    common_elements.append(f"{key}：{values[0]}")

        return common_elements

    def _find_unique_elements(self, dimension_info: List[Dict]) -> List[Dict]:
        """找出每个文档独有的元素"""
        unique_elements = []

        for info in dimension_info:
            doc_title = info["doc_title"]
            doc_info = info["info"]

            # 与其他文档比较，找出独有内容
            for key, value in doc_info.items():
                is_unique = True
                for other_info in dimension_info:
                    if other_info["doc_id"] != info["doc_id"]:
                        if key in other_info["info"]:
                            if str(other_info["info"][key]) == str(value):
                                is_unique = False
                                break

                if is_unique:
                    unique_elements.append({
                        "content": f"{doc_title}在{key}方面：{value}",
                        "policies": [doc_title],
                        "unique_to": doc_title
                    })

        return unique_elements

    async def _generate_comparison_summary(
        self,
        documents: List[PolicyDocument],
        similarities: List[str],
        differences: List[Dict]
    ) -> str:
        """生成比较摘要"""
        doc_count = len(documents)
        similarity_count = len(similarities)
        difference_count = len(differences)

        summary_parts = []

        # 总体概述
        summary_parts.append(
            f"对{doc_count}项政策进行了比较分析，"
            f"发现{similarity_count}个共同点，{difference_count}个差异点。"
        )

        # 主要共同点
        if similarities:
            summary_parts.append("主要共同点包括：")
            for sim in similarities[:3]:
                summary_parts.append(f"- {sim}")

        # 主要差异
        if differences:
            summary_parts.append("主要差异体现在：")
            for diff in differences[:3]:
                summary_parts.append(f"- {diff['content']}")

        return " ".join(summary_parts)

    def _calculate_comparison_confidence(
        self,
        doc_count: int,
        similarity_count: int,
        difference_count: int
    ) -> float:
        """计算比较结果的置信度"""
        base_confidence = 0.7

        # 文档数量越多，置信度略高
        if doc_count >= 3:
            base_confidence += 0.1

        # 有足够多的比较点，置信度增加
        total_points = similarity_count + difference_count
        if total_points >= 5:
            base_confidence += 0.1
        elif total_points >= 10:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def get_metrics(self) -> Dict[str, Any]:
        """获取Agent指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "comparison_dimensions": len(self.comparison_dimensions),
            "memory_size": len(self.memory.memory_contents) if self.memory else 0
        }