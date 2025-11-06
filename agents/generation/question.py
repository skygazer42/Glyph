"""
Question understanding agent for analyzing user queries.
"""

import json
import asyncio
from typing import Dict, Any, List
import re

from ..base.base_agent import BaseAgent
from ..base.types import MessageTypes, AnalysisReport


class QuestionUnderstander(BaseAgent):
    """Agent responsible for understanding and analyzing user questions."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        vector_store: Optional[Any] = None
    ):
        """Initialize the question understander."""
        super().__init__(name, "question_understander", llm_config)
        self.vector_store = vector_store

    def _get_default_system_message(self) -> str:
        """Get the default system message."""
        return """您是问题理解专员，专门分析用户关于政府政策的查询。

您的任务：
1. 理解用户意图和问题类型
2. 提取关键实体、关键词和概念
3. 识别提及或暗示的政策类型
4. 识别时间和地点限制
5. 识别目标群体或资格标准
6. 生成结构化的分析报告

需要处理的问题类型：
- 政策资格问题
- 补贴金额计算
- 申请流程
- 政策比较
- 政策效果
- 实施细节
- 截止日期和时间问题

始终为您的分析提供置信度评分并解释您的推理过程。"""

    async def process_message(
        self,
        message: str,
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and analyze the user's question."""
        try:
            # Clean and preprocess the question
            cleaned_question = self._preprocess_question(message)

            # Extract key information
            analysis = await self._analyze_question(cleaned_question)

            # Create analysis report
            report = AnalysisReport(
                original_query=message,
                intent=analysis.get("intent", ""),
                entities=analysis.get("entities", []),
                keywords=analysis.get("keywords", []),
                policy_types=analysis.get("policy_types", []),
                time_constraints=analysis.get("time_constraints"),
                location_constraints=analysis.get("location_constraints"),
                confidence=analysis.get("confidence", 0.0)
            )

            return self.format_success_response(
                report.__dict__,
                MessageTypes.ANALYSIS_RESULT
            )

        except Exception as e:
            return self.format_error_response(str(e))

    def _preprocess_question(self, question: str) -> str:
        """Preprocess the user's question."""
        # Remove extra whitespace
        question = re.sub(r'\s+', ' ', question.strip())

        # Normalize punctuation
        question = question.replace('？', '?').replace('！', '!')

        return question

    async def _analyze_question(self, question: str) -> Dict[str, Any]:
        """Analyze the question using LLM."""
        prompt = f"""
Please analyze the following policy-related question and extract key information:

Question: {question}

Provide your analysis in the following JSON format:
{{
    "intent": "brief description of user's intent",
    "entities": ["entity1", "entity2", ...],
    "keywords": ["keyword1", "keyword2", ...],
    "policy_types": ["subsidy", "tax_break", "regulation", ...],
    "time_constraints": "any time-related constraints or null",
    "location_constraints": "any location constraints or null",
    "target_groups": ["individuals", "businesses", "seniors", ...],
    "question_type": "eligibility|calculation|procedure|comparison|other",
    "confidence": 0.95,
    "reasoning": "brief explanation of the analysis"
}}

Focus on extracting information that would be useful for searching policy documents.
"""

        messages = [
            {
                "role": "system",
                "content": self.system_message
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        response = await self.a_create(messages)

        try:
            # Try to parse JSON response
            analysis = json.loads(response.content)

            # Validate and clean the analysis
            if not isinstance(analysis, dict):
                raise ValueError("Response is not a dictionary")

            # Ensure required fields exist
            required_fields = ["intent", "entities", "keywords", "policy_types"]
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = []

            return analysis

        except json.JSONDecodeError:
            # Fallback: simple rule-based analysis
            return self._rule_based_analysis(question)

    def _rule_based_analysis(self, question: str) -> Dict[str, Any]:
        """Fallback rule-based analysis."""
        # Simple keyword extraction
        keywords = []
        entities = []
        policy_types = []

        # Common policy keywords
        policy_keywords = {
            "补贴": "subsidy",
            "补贴标准": "subsidy",
            "申请": "application",
            "条件": "eligibility",
            "资格": "eligibility",
            "金额": "calculation",
            "流程": "procedure",
            "时间": "time",
            "截止": "deadline",
            "以旧换新": "replacement",
            "消费券": "voucher",
            "汽车": "automotive",
            "家电": "appliance"
        }

        # Extract keywords and entities
        for chinese, english in policy_keywords.items():
            if chinese in question:
                keywords.append(chinese)
                if english == "subsidy" or english == "replacement" or english == "voucher":
                    policy_types.append("subsidy")

        # Extract entities (simple noun extraction)
        entities = re.findall(r'[\u4e00-\u9fff]{2,}', question)[:10]

        return {
            "intent": "General policy inquiry",
            "entities": entities,
            "keywords": keywords,
            "policy_types": policy_types,
            "time_constraints": None,
            "location_constraints": None,
            "target_groups": [],
            "question_type": "other",
            "confidence": 0.5,
            "reasoning": "Rule-based analysis (fallback)"
        }

    async def a_create(self, messages: List[Dict[str, str]]) -> Any:
        """Async wrapper for creating messages."""
        # This is a simplified version - in real implementation,
        # you would use async API calls
        return self.generate_reply(
            messages=[msg["content"] for msg in messages],
            sender=None
        )