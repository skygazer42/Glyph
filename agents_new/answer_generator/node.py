"""
Advanced answer generation agent with multi-source synthesis.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from autogen_core import MessageContext, CancellationToken
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

from ...models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    PolicyDocument,
    PolicyAnalysis,
    QueryAnalysis,
    GeneratedAnswer,
    QueryIntent,
    PolicyType
)
from ..base.base_agent import StatefulAgent


class AnswerGeneratorAgent(StatefulAgent):
    """Advanced answer generation agent with structured output."""

    def __init__(
        self,
        model_client: Any = None,
        max_sources: int = 5,
        confidence_threshold: float = 0.7,
        **kwargs
    ):
        """Initialize the answer generator agent."""
        super().__init__(
            agent_type=AgentType.ANSWER_GENERATOR,
            name="AnswerGenerator",
            description="智能生成准确、完整的政策问答答案",
            **kwargs
        )

        self.model_client = model_client
        self.max_sources = max_sources
        self.confidence_threshold = confidence_threshold

        # Answer templates for different query intents
        self.templates = {
            QueryIntent.ELIGIBILITY_CHECK: self._eligibility_template,
            QueryIntent.BENEFIT_CALCULATION: self._benefit_template,
            QueryIntent.APPLICATION_PROCESS: self._process_template,
            QueryIntent.DEADLINE_QUERY: self._deadline_template,
            QueryIntent.POLICY_COMPARISON: self._comparison_template,
            QueryIntent.GENERAL_INQUIRY: self._general_template
        }

        # Quality criteria
        self.quality_criteria = {
            "completeness": 0.3,
            "accuracy": 0.3,
            "clarity": 0.2,
            "practicality": 0.2
        }

    async def _handle_analysis_result(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle analysis result messages and generate answers."""
        analyses = message.content.get("analyses", [])
        synthesis = message.content.get("synthesis", {})
        query_id = message.content.get("query_id", "")

        # Get query context
        query_context = await self._get_query_context(query_id)
        query_intent = query_context.get("intent", QueryIntent.GENERAL_INQUIRY)

        # Select best sources
        selected_sources = await self._select_best_sources(analyses)

        # Generate answer
        answer = await self._generate_comprehensive_answer(
            query_context,
            selected_sources,
            synthesis,
            query_intent
        )

        # Validate answer quality
        quality_score = await self._validate_answer_quality(answer)

        # Adjust confidence based on quality
        adjusted_confidence = answer.confidence * quality_score

        return AgentMessage(
            type=MessageType.ANSWER_GENERATION,
            sender=self.agent_type,
            recipient=message.sender,
            content={
                "query_id": query_id,
                "answer": answer.dict(),
                "quality_score": quality_score,
                "adjusted_confidence": adjusted_confidence
            },
            correlation_id=message.correlation_id
        )

    async def _get_query_context(self, query_id: str) -> Dict[str, Any]:
        """Get query context from memory."""
        # Search memory for query analysis
        for i in range(len(self.memory) - 1, -1, -1):
            memory_content = self.memory[i]
            if f"query_id: {query_id}" in memory_content.content:
                # Extract context
                return {"intent": QueryIntent.GENERAL_INQUIRY}  # Simplified

        return {"intent": QueryIntent.GENERAL_INQUIRY}

    async def _select_best_sources(self, analyses: List[Dict[str, Any]]) -> List[Tuple[Dict, float]]:
        """Select the best sources for answer generation."""
        # Sort by relevance score
        sorted_analyses = sorted(
            analyses,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )

        # Select top sources
        selected = []
        for analysis in sorted_analyses[:self.max_sources]:
            selected.append((analysis, analysis.get("relevance_score", 0)))

        return selected

    async def _generate_comprehensive_answer(
        self,
        query_context: Dict[str, Any],
        sources: List[Tuple[Dict, float]],
        synthesis: Dict[str, Any],
        intent: QueryIntent
    ) -> GeneratedAnswer:
        """Generate a comprehensive answer based on multiple sources."""
        query_id = query_context.get("query_id", "")

        # Use template based on intent
        template_func = self.templates.get(intent, self._general_template)

        # Extract information from sources
        extracted_info = await self._extract_information_from_sources(sources)

        # Generate answer using template
        answer_content = await template_func(
            query_context,
            extracted_info,
            synthesis
        )

        # Generate evidence list
        evidence = await self._generate_evidence_list(sources)

        # Generate follow-up questions
        followup_questions = await self._generate_followup_questions(
            query_context,
            extracted_info
        )

        # Calculate confidence
        confidence = await self._calculate_answer_confidence(
            sources,
            extracted_info
        )

        return GeneratedAnswer(
            query_id=query_id,
            answer=answer_content,
            sources=[source[0]["document_id"] for source in sources],
            confidence=confidence,
            evidence=evidence,
            assumptions=extracted_info.get("assumptions", []),
            limitations=extracted_info.get("limitations", []),
            followup_questions=followup_questions,
            generation_time=0.0  # Would be measured
        )

    async def _extract_information_from_sources(self, sources: List[Tuple[Dict, float]]) -> Dict[str, Any]:
        """Extract and consolidate information from multiple sources."""
        consolidated = {
            "eligibility_criteria": [],
            "benefits": [],
            "application_steps": [],
            "deadlines": [],
            "contact_info": [],
            "limitations": [],
            "assumptions": [],
            "conflicts": []
        }

        for analysis, score in sources:
            # Add eligibility criteria
            criteria = analysis.get("eligibility_criteria", [])
            consolidated["eligibility_criteria"].extend(criteria)

            # Add benefits
            if analysis.get("benefit_details"):
                consolidated["benefits"].append({
                    "content": analysis["benefit_details"],
                    "source_id": analysis["document_id"],
                    "confidence": score
                })

            # Add application steps
            steps = analysis.get("application_steps", [])
            consolidated["application_steps"].extend(steps)

            # Add deadlines
            deadlines = analysis.get("deadlines", [])
            consolidated["deadlines"].extend(deadlines)

            # Add contact info
            contacts = analysis.get("contact_info", [])
            consolidated["contact_info"].extend(contacts)

            # Add limitations
            limitations = analysis.get("limitations", [])
            consolidated["limitations"].extend(limitations)

        # Remove duplicates
        for key in ["eligibility_criteria", "application_steps", "deadlines", "contact_info", "limitations"]:
            consolidated[key] = list(set(consolidated[key]))

        # Detect conflicts
        consolidated["conflicts"] = await self._detect_conflicts(consolidated)

        return consolidated

    async def _detect_conflicts(self, info: Dict[str, Any]) -> List[str]:
        """Detect conflicting information between sources."""
        conflicts = []

        # Check for conflicting benefit amounts
        if len(info["benefits"]) > 1:
            amounts = []
            for benefit in info["benefits"]:
                # Extract numeric values
                import re
                numbers = re.findall(r'([0-9,]+(?:\.\d+)?元)', benefit["content"])
                amounts.extend(numbers)

            if len(set(amounts)) > 1:
                conflicts.append(f"发现不同的补贴金额: {', '.join(set(amounts))}")

        # Check for conflicting deadlines
        if len(info["deadlines"]) > 1:
            dates = []
            import re
            for deadline in info["deadlines"]:
                date_matches = re.findall(r'(\d{4}年\d{1,2}月\d{1,2}日)', deadline)
                dates.extend(date_matches)

            if len(set(dates)) > 1:
                conflicts.append(f"发现不同的截止日期: {', '.join(set(dates))}")

        return conflicts

    async def _eligibility_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for eligibility queries."""
        answer_parts = [
            "## 申请资格条件\n\n",
            "根据相关政策文件，您需要满足以下条件：\n\n"
        ]

        # Add eligibility criteria
        if info["eligibility_criteria"]:
            answer_parts.append("### 必要条件：\n")
            for i, criterion in enumerate(info["eligibility_criteria"], 1):
                answer_parts.append(f"{i}. {criterion}\n")

        # Add any assumptions
        if info["assumptions"]:
            answer_parts.append("\n### 说明：\n")
            for assumption in info["assumptions"]:
                answer_parts.append(f"- {assumption}\n")

        # Add conflicts if any
        if info["conflicts"]:
            answer_parts.append("\n### 注意事项：\n")
            for conflict in info["conflicts"]:
                answer_parts.append(f"⚠️ {conflict}\n")

        # Add practical advice
        answer_parts.append("\n### 建议行动：\n")
        answer_parts.append("1. 请根据上述条件核对自身情况\n")
        answer_parts.append("2. 准备相关证明材料\n")
        answer_parts.append("3. 如有疑问，请联系相关部门咨询\n")

        return "".join(answer_parts)

    async def _benefit_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for benefit calculation queries."""
        answer_parts = [
            "## 补贴标准与金额\n\n",
            "根据相关政策，补贴标准如下：\n\n"
        ]

        # Add benefit details
        if info["benefits"]:
            for benefit in info["benefits"]:
                answer_parts.append(f"### 补贴说明：\n{benefit['content']}\n")
                answer_parts.append(f"*来源置信度: {benefit['confidence']:.2%}\n\n")

        # Add limitations
        if info["limitations"]:
            answer_parts.append("### 限制条件：\n")
            for limitation in info["limitations"]:
                answer_parts.append(f"- {limitation}\n")

        # Add calculation examples
        answer_parts.append("\n### 计算示例：\n")
        answer_parts.append("具体补贴金额将根据您的实际情况和相关政策规定计算。\n")

        return "".join(answer_parts)

    async def _process_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for application process queries."""
        answer_parts = [
            "## 申请流程\n\n"
        ]

        # Add application steps
        if info["application_steps"]:
            answer_parts.append("### 申请步骤：\n")
            for i, step in enumerate(info["application_steps"], 1):
                answer_parts.append(f"**步骤 {i}**: {step}\n\n")

        # Add required documents
        if info["eligibility_criteria"]:  # Using as proxy for required docs
            answer_parts.append("### 所需材料：\n")
            answer_parts.append("请准备以下材料：\n")
            for criteria in info["eligibility_criteria"][:5]:
                if any(word in criteria for word in ["证明", "证件", "材料", "文件"]):
                    answer_parts.append(f"- {criteria}\n")

        # Add contact info
        if info["contact_info"]:
            answer_parts.append("\n### 联系方式：\n")
            for contact in info["contact_info"][:3]:
                answer_parts.append(f"- {contact}\n")

        # Add deadlines
        if info["deadlines"]:
            answer_parts.append("\n### 重要日期：\n")
            for deadline in info["deadlines"][:3]:
                answer_parts.append(f"- {deadline}\n")

        return "".join(answer_parts)

    async def _deadline_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for deadline queries."""
        answer_parts = [
            "## 重要时间节点\n\n"
        ]

        # Add deadlines
        if info["deadlines"]:
            answer_parts.append("### 时间安排：\n")
            for deadline in info["deadlines"]:
                answer_parts.append(f"- {deadline}\n")
        else:
            answer_parts.append("暂无明确的截止日期信息，请咨询相关部门获取最新信息。\n")

        # Add advice
        answer_parts.append("\n### 建议：\n")
        answer_parts.append("1. 请尽早准备申请材料\n")
        answer_parts.append("2. 关注官方发布的最新时间安排\n")
        answer_parts.append("3. 如遇特殊情况，及时与受理部门联系\n")

        return "".join(answer_parts)

    async def _comparison_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for policy comparison queries."""
        answer_parts = [
            "## 政策对比分析\n\n"
        ]

        # Add benefits comparison
        if info["benefits"]:
            answer_parts.append("### 补贴标准对比：\n")
            for i, benefit in enumerate(info["benefits"], 1):
                answer_parts.append(f"政策 {i}：{benefit['content']}\n\n")

        # Add eligibility comparison
        if info["eligibility_criteria"]:
            answer_parts.append("### 申请条件差异：\n")
            criteria_by_source = {}
            for criterion in info["eligibility_criteria"]:
                # In real implementation, would track source
                criteria_by_source.setdefault("来源1", []).append(criterion)

            for source, criteria in criteria_by_source.items():
                answer_parts.append(f"**{source}**：\n")
                for criterion in criteria[:3]:
                    answer_parts.append(f"- {criterion}\n")
                answer_parts.append("\n")

        return "".join(answer_parts)

    async def _general_template(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any],
        synthesis: Dict[str, Any]
    ) -> str:
        """Generate answer for general queries."""
        answer_parts = [
            "## 政策说明\n\n",
            "根据相关政策文件，为您提供以下信息：\n\n"
        ]

        # Add all relevant information
        if info["eligibility_criteria"]:
            answer_parts.append("### 申请条件：\n")
            for criterion in info["eligibility_criteria"][:3]:
                answer_parts.append(f"- {criterion}\n")
            answer_parts.append("\n")

        if info["benefits"]:
            answer_parts.append("### 主要优惠：\n")
            for benefit in info["benefits"][:2]:
                answer_parts.append(f"- {benefit['content'][:100]}...\n")
            answer_parts.append("\n")

        # Add next steps
        answer_parts.append("### 下一步建议：\n")
        answer_parts.append("1. 详细了解政策细则\n")
        answer_parts.append("2. 评估自身是否符合条件\n")
        answer_parts.append("3. 准备相关申请材料\n")

        return "".join(answer_parts)

    async def _generate_evidence_list(self, sources: List[Tuple[Dict, float]]) -> List[str]:
        """Generate list of evidence sources."""
        evidence = []
        for analysis, score in sources:
            evidence.append(f"政策文档: {analysis.get('document_title', '未知')} (置信度: {score:.2%})")
        return evidence

    async def _generate_followup_questions(
        self,
        query_context: Dict[str, Any],
        info: Dict[str, Any]
    ) -> List[str]:
        """Generate relevant follow-up questions."""
        questions = [
            "您是否需要了解具体的申请流程？",
            "您是否符合申请条件中的特殊要求？",
            "是否需要咨询具体的联系方式？"
        ]

        # Customize based on available info
        if not info["deadlines"]:
            questions.insert(0, "您是否关心申请的截止日期？")

        if info["conflicts"]:
            questions.insert(0, "是否需要澄清政策中的矛盾之处？")

        return questions[:3]

    async def _calculate_answer_confidence(
        self,
        sources: List[Tuple[Dict, float]],
        info: Dict[str, Any]
    ) -> float:
        """Calculate overall answer confidence."""
        if not sources:
            return 0.0

        # Base confidence from source scores
        source_confidence = sum(score for _, score in sources) / len(sources)

        # Adjust based on information completeness
        completeness_factor = 0.0
        if info["eligibility_criteria"]:
            completeness_factor += 0.25
        if info["benefits"]:
            completeness_factor += 0.25
        if info["application_steps"]:
            completeness_factor += 0.25
        if info["deadlines"]:
            completeness_factor += 0.25

        # Adjust for conflicts
        conflict_penalty = 0.1 * len(info["conflicts"])

        # Calculate final confidence
        final_confidence = (source_confidence * 0.6) + (completeness_factor * 0.4) - conflict_penalty

        return max(0.0, min(1.0, final_confidence))

    async def _validate_answer_quality(self, answer: GeneratedAnswer) -> float:
        """Validate the quality of the generated answer."""
        scores = {}

        # Check completeness
        scores["completeness"] = min(1.0, len(answer.answer) / 500)

        # Check clarity (simple heuristic)
        scores["clarity"] = 1.0 if "##" in answer.answer or "###" in answer.answer else 0.7

        # Check practicality
        scores["practicality"] = 1.0 if "建议" in answer.answer or "步骤" in answer.answer else 0.6

        # Check evidence support
        scores["evidence"] = min(1.0, len(answer.evidence) / 3)

        # Calculate weighted average
        quality_score = sum(
            score * self.quality_criteria[criterion]
            for criterion, score in scores.items()
        )

        return quality_score

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages."""
        return None

    async def _handle_query_analysis(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle query analysis messages."""
        return None

    async def process_request(self, request: Any, context: MessageContext) -> Any:
        """Process an answer generation request."""
        return await self._generate_comprehensive_answer(
            request.query_context,
            request.sources,
            request.synthesis,
            request.intent
        )