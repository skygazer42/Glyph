"""
Policy analysis agent for analyzing retrieved policy documents.
"""

import logging
import anyio

from typing import Dict, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agents.framework.common.model_client import create_openai_client
from autogen_core.models import SystemMessage, UserMessage
from app.agents.framework.base.types import MessageTypes
from app.models.base import PolicyDocument


class ReviewRequest(BaseModel):
    """Policy documents and the actual user query being evaluated."""

    model_config = ConfigDict(strict=True, extra="ignore")

    query: str = Field(min_length=1)
    documents: list[PolicyDocument]

    @field_validator("query")
    @classmethod
    def require_nonempty_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Policy review requires a nonempty query")
        return value


class PolicyReviewAnalysis(BaseModel):
    """Policy facts returned by the document-analysis prompt."""

    model_config = ConfigDict(strict=True, extra="ignore")

    relevance_score: float = Field(ge=0, le=1)
    policy_summary: str
    key_points: list[str]
    eligibility_criteria: list[str]
    benefits: str
    application_process: str
    deadlines: str
    contact_info: str | None = None
    answered_questions: list[str]
    missing_information: list[str]
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class PolicyReviewAgent:
    """Agent responsible for analyzing retrieved policy documents."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        *, model_client=None,
    ):
        """Initialize the policy analyzer."""
        self.name = name
        self.llm_config = llm_config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.system_message = self._get_default_system_message()
        self._owns_model_client = model_client is None
        self.model_client = create_openai_client(llm_config=llm_config) if model_client is None else model_client

    def _get_default_system_message(self) -> str:
        """Get the default system message."""
        return """您是政策分析专员，专门分析政府政策文档。

您的任务：
1. 阅读并理解政策文档
2. 提取关键政策信息
3. 识别资格标准
4. 确定补贴金额或支持水平
5. 识别申请流程和截止日期
6. 检查政策冲突或互补性
7. 评估政策与用户查询的相关性

需要提取的关键信息：
- 政策名称和发布机构
- 生效日期和截止日期
- 目标受益人
- 资格要求
- 补贴金额/支持细节
- 申请流程
- 所需材料
- 联系信息
- 相关政策

始终提供结构化分析和置信度评分。"""

    async def process_message(
        self,
        message: str | Dict[str, Any],
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and analyze policy documents."""
        try:
            # Parse the message
            if isinstance(message, str):
                request = ReviewRequest.model_validate_json(message)
            else:
                request = ReviewRequest.model_validate(message)

            if not request.documents:
                return {"success": False, "error": "No documents provided for analysis"}

            # Analyze each document
            analyzed_documents = []
            for document in request.documents:
                analysis = await self._analyze_document(document, request.query)
                analyzed_documents.append({
                    "document": document.model_dump(mode="json"),
                    "analysis": analysis
                })

            # Synthesize overall analysis
            synthesis = await self._synthesize_analysis(request.query, analyzed_documents)

            return {"success": True, "data": {
                    "query": request.query,
                    "document_analyses": analyzed_documents,
                    "synthesis": synthesis
                }, "type": MessageTypes.ANALYSIS_REPORT.value}

        except Exception as e:
            self.logger.exception("Policy request failed")
            return {"success": False, "error": str(e)}

    async def _analyze_document(self, document: PolicyDocument, query: str) -> Dict[str, Any]:
        """Analyze a single policy document."""
        prompt = f"""
Please analyze the following policy document in relation to the user's query:

User Query: {query}

Document:
Title: {document.title}
Source: {document.source}
Content: {document.content[:2000]}...

Provide your analysis in the following JSON format:
{{
    "relevance_score": 0.95,
    "policy_summary": "brief summary of the policy",
    "key_points": [
        "point 1",
        "point 2",
        ...
    ],
    "eligibility_criteria": [
        "criterion 1",
        "criterion 2",
        ...
    ],
    "benefits": "description of benefits or support",
    "application_process": "brief description of application process",
    "deadlines": "important dates or deadlines",
    "contact_info": "contact information if available",
    "answered_questions": [
        "specific question from query that this document answers"
    ],
    "missing_information": [
        "information not found in this document"
    ],
    "confidence": 0.90,
    "reasoning": "explanation of the analysis"
}}

Focus on information directly relevant to answering the user's question.
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
            return PolicyReviewAnalysis.model_validate_json(response).model_dump()
        except ValidationError:
            self.logger.warning("Invalid policy analysis; using keyword analysis", exc_info=True)
            # Fallback: simple keyword-based analysis
            return self._simple_analysis(document, query)

    async def _synthesize_analysis(
        self,
        query: str,
        analyzed_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize analysis from multiple documents."""
        if not analyzed_documents:
            return {"summary": "No relevant policies found"}

        # Collect all key points
        all_key_points = []
        all_eligibility = []
        benefits = []
        deadlines = []

        for doc_analysis in analyzed_documents:
            analysis = doc_analysis["analysis"]
            all_key_points.extend(analysis["key_points"])
            all_eligibility.extend(analysis["eligibility_criteria"])
            if analysis["benefits"]:
                benefits.append(analysis["benefits"])
            if analysis["deadlines"]:
                deadlines.append(analysis["deadlines"])

        # Remove duplicates
        unique_key_points = list(set(all_key_points))
        unique_eligibility = list(set(all_eligibility))

        return {
            "total_documents": len(analyzed_documents),
            "most_relevant": max(
                analyzed_documents,
                key=lambda document_analysis: document_analysis["analysis"]["relevance_score"]
            )["document"]["title"],
            "summary": f"Found {len(analyzed_documents)} relevant policies",
            "key_points": unique_key_points[:10],
            "eligibility_criteria": unique_eligibility[:10],
            "benefits": benefits,
            "deadlines": deadlines,
            "complementary_policies": self._find_complementary_policies(analyzed_documents),
            "conflicting_policies": self._find_conflicting_policies(analyzed_documents)
        }

    def _find_complementary_policies(self, analyzed_documents: List[Dict]) -> List[str]:
        """Find policies that complement each other."""
        # Simple implementation - look for policies targeting different aspects
        complementary = []
        sources = [doc["document"]["source"] for doc in analyzed_documents]
        if len(set(sources)) > 1:
            complementary.append("Multiple policies from different authorities may be combined")
        return complementary

    def _find_conflicting_policies(self, analyzed_documents: List[Dict]) -> List[str]:
        """Find potential policy conflicts."""
        # Simple implementation - look for overlapping benefits
        conflicting = []
        benefits = []
        for doc in analyzed_documents:
            analysis = doc["analysis"]
            if analysis["benefits"]:
                benefits.append(analysis["benefits"])

        if len(benefits) > 3:
            conflicting.append("Multiple benefit programs available - check eligibility restrictions")
        return conflicting

    def _simple_analysis(self, document: PolicyDocument, query: str) -> Dict[str, Any]:
        """Simple keyword-based analysis fallback."""
        content_lower = document.content.lower()
        query_lower = query.lower()

        # Simple relevance check
        relevance = 0.5
        if any(word in content_lower for word in query_lower.split()):
            relevance = 0.7

        return {
            "relevance_score": relevance,
            "policy_summary": f"Policy document from {document.source}",
            "key_points": [document.title],
            "eligibility_criteria": [],
            "benefits": "",
            "application_process": "",
            "deadlines": "",
            "contact_info": "",
            "answered_questions": [],
            "missing_information": ["Detailed analysis not available"],
            "confidence": 0.5,
            "reasoning": "Simple keyword-based analysis"
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
