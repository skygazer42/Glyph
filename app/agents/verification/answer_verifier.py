"""
Answer verification agent for validating generated answers.
"""

import json
import asyncio
from typing import Dict, Any, List

from ..base.base_agent import BaseAgent
from ..base.types import MessageTypes, VerificationReport, GeneratedAnswer


class AnswerVerifier(BaseAgent):
    """Agent responsible for verifying the accuracy and completeness of generated answers."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any]
    ):
        """Initialize the answer verifier."""
        super().__init__(name, "answer_verifier", llm_config)

    def _get_default_system_message(self) -> str:
        """Get the default system message."""
        return """您是答案验证专员，负责确保政策答案的准确性、完整性和可靠性。

您的任务：
1. 根据源政策文档验证事实
2. 检查答案的完整性
3. 识别任何缺失的关键信息
4. 检测潜在的误解或错误解释
5. 确保所有主张都有证据支持
6. 验证数字、日期和具体要求
7. 检查过时信息或政策变更

验证标准：
- 准确性：所有事实必须与源文档匹配
- 完整性：答案应涵盖问题的所有方面
- 可靠性：信息应是最新的且来自权威来源
- 清晰性：答案应易于理解
- 实用性：建议应是可操作的

始终提供具体的反馈和改进建议。"""

    async def process_message(
        self,
        message: str,
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and verify the generated answer."""
        try:
            # Parse the message
            data = json.loads(message) if isinstance(message, str) else message
            query = data.get("query", "")
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            document_analyses = data.get("document_analyses", [])

            if not answer:
                return self.format_error_response("No answer provided for verification")

            # Perform comprehensive verification
            verification = await self._verify_answer(
                query, answer, sources, document_analyses
            )

            return self.format_success_response(
                verification.__dict__,
                MessageTypes.VERIFICATION_REPORT
            )

        except Exception as e:
            return self.format_error_response(str(e))

    async def _verify_answer(
        self,
        query: str,
        answer: str,
        sources: List[str],
        document_analyses: List[Dict[str, Any]]
    ) -> VerificationReport:
        """Perform comprehensive answer verification."""
        # Prepare verification context
        context = self._prepare_verification_context(
            query, answer, sources, document_analyses
        )

        prompt = f"""
Please verify the following policy answer for accuracy and completeness:

User Question: {query}

Generated Answer:
{answer}

Sources: {', '.join(sources)}

Source Documents Analysis:
{context}

Please provide your verification in the following JSON format:
{{
    "is_accurate": true,
    "is_complete": true,
    "confidence": 0.95,
    "issues": [
        {{
            "type": "accuracy|completeness|clarity|currency",
            "description": "Description of the issue",
            "severity": "high|medium|low"
        }}
    ],
    "suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2"
    ],
    "missing_information": [
        "Critical information that should be included"
    ],
    "fact_checks": [
        {{
            "claim": "Claim from the answer",
            "verification": "Verified|Unverified|Partially verified",
            "source": "Source document or section"
        }}
    ],
    "final_score": 0.90,
    "reasoning": "Detailed explanation of the verification process"
}}

Focus on:
- Checking that all facts match the source documents
- Ensuring important details (amounts, dates, requirements) are correct
- Verifying that the answer fully addresses the user's question
- Identifying any outdated or incorrect information
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
            verification_data = json.loads(response.content)

            # Extract issues and suggestions
            issues = [
                issue.get("description", "")
                for issue in verification_data.get("issues", [])
            ]

            suggestions = verification_data.get("suggestions", [])

            return VerificationReport(
                is_accurate=verification_data.get("is_accurate", False),
                is_complete=verification_data.get("is_complete", False),
                confidence=verification_data.get("confidence", 0.0),
                issues=issues,
                suggestions=suggestions,
                final_score=verification_data.get("final_score", 0.0)
            )

        except json.JSONDecodeError:
            # Fallback: simple verification
            return self._simple_verification(answer, sources)

    def _prepare_verification_context(
        self,
        query: str,
        answer: str,
        sources: List[str],
        document_analyses: List[Dict[str, Any]]
    ) -> str:
        """Prepare context for verification."""
        context_parts = []

        if document_analyses:
            context_parts.append("Source Document Details:")
            for doc_analysis in document_analyses[:3]:
                doc = doc_analysis.get("document", {})
                analysis = doc_analysis.get("analysis", {})

                context_parts.append(f"\nDocument: {doc.get('title', 'Untitled')}")
                context_parts.append(f"Source: {doc.get('source', 'N/A')}")

                if analysis.get("key_points"):
                    context_parts.append("Key Points:")
                    for point in analysis["key_points"]:
                        context_parts.append(f"- {point}")

                if analysis.get("benefits"):
                    context_parts.append(f"Benefits: {analysis['benefits'][:300]}")

                if analysis.get("eligibility_criteria"):
                    context_parts.append("Eligibility Criteria:")
                    for criteria in analysis["eligibility_criteria"]:
                        context_parts.append(f"- {criteria}")

        return "\n".join(context_parts)

    def _simple_verification(
        self,
        answer: str,
        sources: List[str]
    ) -> VerificationReport:
        """Simple verification fallback."""
        issues = []
        suggestions = []

        # Basic checks
        if not sources:
            issues.append("No sources provided for verification")
            suggestions.append("Always cite policy sources")

        if len(answer) < 100:
            issues.append("Answer seems too brief")
            suggestions.append("Provide more detailed information")

        # Check for specific policy elements
        if "补贴" in answer and "元" not in answer:
            issues.append("Mentioned subsidy but no specific amount")
            suggestions.append("Include specific subsidy amounts when available")

        confidence = 0.5 if issues else 0.7
        final_score = max(0.0, confidence - len(issues) * 0.1)

        return VerificationReport(
            is_accurate=len(issues) == 0,
            is_complete=len(issues) < 2,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
            final_score=final_score
        )

    async def a_create(self, messages: List[Dict[str, str]]) -> Any:
        """Async wrapper for creating messages."""
        return self.generate_reply(
            messages=[msg["content"] for msg in messages],
            sender=None
        )