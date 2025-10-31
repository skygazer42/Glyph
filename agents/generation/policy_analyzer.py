"""
Policy analysis agent for analyzing retrieved policy documents.
"""

import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from ..base.base_agent import BaseAgent
from ..base.types import MessageTypes, PolicyDocument


class PolicyAnalyzer(BaseAgent):
    """Agent responsible for analyzing retrieved policy documents."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any]
    ):
        """Initialize the policy analyzer."""
        super().__init__(name, "policy_analyzer", llm_config)

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
        message: str,
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and analyze policy documents."""
        try:
            # Parse the message
            data = json.loads(message) if isinstance(message, str) else message
            query = data.get("query", "")
            documents = data.get("documents", [])

            if not documents:
                return self.format_error_response("No documents provided for analysis")

            # Analyze each document
            analyzed_documents = []
            for doc_data in documents:
                if isinstance(doc_data, dict):
                    doc = PolicyDocument(**doc_data)
                else:
                    doc = doc_data

                analysis = await self._analyze_document(doc, query)
                analyzed_documents.append({
                    "document": doc.__dict__,
                    "analysis": analysis
                })

            # Synthesize overall analysis
            synthesis = await self._synthesize_analysis(query, analyzed_documents)

            return self.format_success_response(
                {
                    "query": query,
                    "document_analyses": analyzed_documents,
                    "synthesis": synthesis
                },
                MessageTypes.ANALYSIS_REPORT
            )

        except Exception as e:
            return self.format_error_response(str(e))

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

        response = await self.a_create(messages)

        try:
            analysis = json.loads(response.content)
            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis format")
            return analysis
        except:
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
            analysis = doc_analysis.get("analysis", {})
            all_key_points.extend(analysis.get("key_points", []))
            all_eligibility.extend(analysis.get("eligibility_criteria", []))
            if analysis.get("benefits"):
                benefits.append(analysis["benefits"])
            if analysis.get("deadlines"):
                deadlines.append(analysis["deadlines"])

        # Remove duplicates
        unique_key_points = list(set(all_key_points))
        unique_eligibility = list(set(all_eligibility))

        return {
            "total_documents": len(analyzed_documents),
            "most_relevant": max(
                analyzed_documents,
                key=lambda x: x.get("analysis", {}).get("relevance_score", 0)
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
            analysis = doc.get("analysis", {})
            if analysis.get("benefits"):
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

    async def a_create(self, messages: List[Dict[str, str]]) -> Any:
        """Async wrapper for creating messages."""
        return self.generate_reply(
            messages=[msg["content"] for msg in messages],
            sender=None
        )