"""
Question understanding agent for analyzing user queries.
"""

import logging
import anyio

from typing import Dict, Any, List
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agents.framework.common.model_client import create_openai_client
from autogen_core.models import SystemMessage, UserMessage
from app.agents.framework.base.types import MessageTypes, AnalysisReport


QUESTION_SYSTEM_MESSAGE = """您是问题理解专员，专门分析用户关于政府政策的查询。

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


class QuestionAnalysis(BaseModel):
    """Structured question interpretation returned by the analysis prompt."""

    model_config = ConfigDict(strict=True, extra="ignore")

    intent: str = Field(min_length=1)
    entities: list[str]
    keywords: list[str]
    policy_types: list[str]
    time_constraints: str | None = None
    location_constraints: str | None = None
    target_groups: list[str]
    question_type: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str

    @field_validator("intent")
    @classmethod
    def require_nonempty_intent(cls, value: str) -> str:
        """拒绝仅空白的意图字段，保留原值交给问题分析。"""
        if not value.strip():
            raise ValueError("Question analysis requires a nonempty intent")
        return value


class QuestionUnderstander:
    """Agent responsible for understanding and analyzing user questions."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        *, model_client=None,
    ):
        """Initialize the question understander."""
        self.name = name
        self.llm_config = llm_config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.system_message = QUESTION_SYSTEM_MESSAGE
        self._owns_model_client = model_client is None
        self.model_client = create_openai_client(llm_config=llm_config) if model_client is None else model_client

    async def process_message(
        self,
        message: str,
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
                intent=analysis["intent"],
                entities=analysis["entities"],
                keywords=analysis["keywords"],
                policy_types=analysis["policy_types"],
                time_constraints=analysis["time_constraints"],
                location_constraints=analysis["location_constraints"],
                confidence=analysis["confidence"]
            )

            return {"success": True, "data": report.__dict__, "type": MessageTypes.ANALYSIS_RESULT.value}

        except Exception as e:
            self.logger.exception("Policy request failed")
            return {"success": False, "error": str(e)}

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

        response = await self._request_completion(messages)

        try:
            return QuestionAnalysis.model_validate_json(response).model_dump()
        except ValidationError as exc:
            self.logger.warning("Invalid question analysis; using rule analysis: %s", exc, exc_info=True)
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


    async def _request_completion(self, messages: List[Dict[str, str]]) -> str:
        """Send complete role-tagged messages through the current async SDK."""
        sdk_messages = [SystemMessage(content=message["content"])
                        if message["role"] == "system"
                        else UserMessage(content=message["content"], source="user")
                        for message in messages]
        response = await self.model_client.create(sdk_messages)
        if not isinstance(response.content, str):
            raise ValueError("Policy model must return text")
        return response.content

    async def close(self):
        """Release only the model client created by this business object."""
        if self._owns_model_client:
            self._owns_model_client = False
            with anyio.fail_after(5, shield=True):
                await self.model_client.close()
