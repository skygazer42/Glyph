"""
Advanced answer generation agent with multi-source synthesis.
"""

import asyncio
import re

from typing import List, Dict, Any, Optional, Tuple

from autogen_core import MessageContext, CancellationToken
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage

from app.models.policy import (
    AgentType,
    MessageType,
    AgentMessage,
    GeneratedAnswer,
    QueryIntent
)
from app.agents.framework.base.base_agent import StatefulAgent
from app.agents.framework.common.model_client import create_buffered_context
from .prompt import GENERATION_SYSTEM_PROMPT, build_generation_user_prompt


class AnswerGeneratorAgent(StatefulAgent):
    """Advanced answer generation agent with structured output."""

    def __init__(
        self,
        model_client: Any = None,
        max_sources: int = 5,
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
        self._assistant: Optional[AssistantAgent] = None
        self._assistant_lock = asyncio.Lock()
        self.max_sources = max_sources

        # Answer templates for different query intents
        self.templates = {
            QueryIntent.ELIGIBILITY_CHECK: self._render_eligibility_answer,
            QueryIntent.BENEFIT_CALCULATION: self._render_benefit_answer,
            QueryIntent.APPLICATION_PROCESS: self._render_process_answer,
            QueryIntent.DEADLINE_QUERY: self._render_deadline_answer,
            QueryIntent.POLICY_COMPARISON: self._render_comparison_answer,
            QueryIntent.GENERAL_INQUIRY: self._render_general_answer
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
        analyses = message.content["analyses"]
        query_id = message.content["query_id"]

        # Get query context
        query_context = {"query_id": query_id, "intent": QueryIntent.GENERAL_INQUIRY}
        query_intent = query_context["intent"]

        # Select best sources
        selected_sources = self._select_best_sources(analyses)

        # Generate answer
        answer = self._generate_comprehensive_answer(
            query_context,
            selected_sources,
            query_intent
        )

        # Validate answer quality
        quality_score = self._validate_answer_quality(answer)

        # Adjust confidence based on quality
        adjusted_confidence = answer.confidence * quality_score

        return AgentMessage(
            type=MessageType.ANSWER_GENERATION,
            sender=self.agent_type,
            recipient=message.sender,
            content={
                "query_id": query_id,
                "answer": answer.model_dump(),
                "quality_score": quality_score,
                "adjusted_confidence": adjusted_confidence
            },
            correlation_id=message.correlation_id
        )

    def _select_best_sources(self, analyses: List[Dict[str, Any]]) -> List[Tuple[Dict, float]]:
        """Select the best sources for answer generation."""
        # Sort by relevance score
        sorted_analyses = sorted(
            analyses,
            key=lambda analysis: analysis["relevance_score"],
            reverse=True
        )

        # Select top sources
        selected = []
        for analysis in sorted_analyses[:self.max_sources]:
            selected.append((analysis, analysis["relevance_score"]))

        return selected

    def _generate_comprehensive_answer(
        self,
        query_context: Dict[str, Any],
        sources: List[Tuple[Dict, float]],
        intent: QueryIntent
    ) -> GeneratedAnswer:
        """Generate a comprehensive answer based on multiple sources."""
        query_id = query_context["query_id"]

        # Use template based on intent
        render_answer = self.templates.get(intent, self._render_general_answer)

        # Extract information from sources
        extracted_info = self._extract_information_from_sources(sources)

        # Generate answer using template
        answer_content = render_answer(extracted_info)

        # Generate evidence list
        evidence = self._generate_evidence_list(sources)

        # Generate follow-up questions
        followup_questions = self._generate_followup_questions(extracted_info)

        # Calculate confidence
        confidence = self._calculate_answer_confidence(
            sources,
            extracted_info
        )

        return GeneratedAnswer(
            query_id=query_id,
            answer=answer_content,
            sources=[source[0]["document_id"] for source in sources],
            confidence=confidence,
            evidence=evidence,
            assumptions=extracted_info["assumptions"],
            limitations=extracted_info["limitations"],
            followup_questions=followup_questions,
            generation_time=0.0  # Would be measured
        )

    def _extract_information_from_sources(self, sources: List[Tuple[Dict, float]]) -> Dict[str, Any]:
        """Extract and consolidate information from multiple sources."""
        consolidated: Dict[str, Any] = {
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
            criteria = analysis["eligibility_criteria"]
            consolidated["eligibility_criteria"].extend(criteria)

            # Add benefits
            if analysis.get("benefit_details"):
                consolidated["benefits"].append({
                    "content": analysis["benefit_details"],
                    "source_id": analysis["document_id"],
                    "confidence": score
                })

            # Add application steps
            steps = analysis["application_steps"]
            consolidated["application_steps"].extend(steps)

            # Add deadlines
            deadlines = analysis["deadlines"]
            consolidated["deadlines"].extend(deadlines)

            # Add contact info
            contacts = analysis["contact_info"]
            consolidated["contact_info"].extend(contacts)

            # Add limitations
            limitations = analysis["limitations"]
            consolidated["limitations"].extend(limitations)

        # Remove duplicates
        for key in ["eligibility_criteria", "application_steps", "deadlines", "contact_info", "limitations"]:
            consolidated[key] = list(set(consolidated[key]))

        # Detect conflicts
        consolidated["conflicts"] = self._detect_conflicts(consolidated)

        return consolidated

    @staticmethod
    def _detect_conflicts(info: Dict[str, Any]) -> List[str]:
        """Detect conflicting information between sources."""
        conflicts = []

        # Check for conflicting benefit amounts
        if len(info["benefits"]) > 1:
            amounts = []
            for benefit in info["benefits"]:
                # Extract numeric values
                numbers = re.findall(r'([0-9,]+(?:\.\d+)?元)', benefit["content"])
                amounts.extend(numbers)

            if len(set(amounts)) > 1:
                conflicts.append(f"发现不同的补贴金额: {', '.join(set(amounts))}")

        # Check for conflicting deadlines
        if len(info["deadlines"]) > 1:
            dates = []
            for deadline in info["deadlines"]:
                date_matches = re.findall(r'(\d{4}年\d{1,2}月\d{1,2}日)', deadline)
                dates.extend(date_matches)

            if len(set(dates)) > 1:
                conflicts.append(f"发现不同的截止日期: {', '.join(set(dates))}")

        return conflicts

    @staticmethod
    def _render_eligibility_answer(info: Dict[str, Any]) -> str:
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

    @staticmethod
    def _render_benefit_answer(info: Dict[str, Any]) -> str:
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

    @staticmethod
    def _render_process_answer(info: Dict[str, Any]) -> str:
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

    @staticmethod
    def _render_deadline_answer(info: Dict[str, Any]) -> str:
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

    @staticmethod
    def _render_comparison_answer(info: Dict[str, Any]) -> str:
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
            criteria_by_source: Dict[str, List[str]] = {}
            for criterion in info["eligibility_criteria"]:
                # In real implementation, would track source
                criteria_by_source.setdefault("来源1", []).append(criterion)

            for source, criteria in criteria_by_source.items():
                answer_parts.append(f"**{source}**：\n")
                for criterion in criteria[:3]:
                    answer_parts.append(f"- {criterion}\n")
                answer_parts.append("\n")

        return "".join(answer_parts)

    @staticmethod
    def _render_general_answer(info: Dict[str, Any]) -> str:
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

    @staticmethod
    def _generate_evidence_list(sources: List[Tuple[Dict, float]]) -> List[str]:
        """Generate list of evidence sources."""
        evidence = []
        for analysis, score in sources:
            evidence.append(f"政策文档: {analysis['document_id']} (置信度: {score:.2%})")
        return evidence

    @staticmethod
    def _generate_followup_questions(info: Dict[str, Any]) -> List[str]:
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

    @staticmethod
    def _calculate_answer_confidence(
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

    def _validate_answer_quality(self, answer: GeneratedAnswer) -> float:
        """Validate the quality of the generated answer."""
        scores = {}

        # Check completeness
        scores["completeness"] = min(1.0, len(answer.answer) / 500)

        # Check clarity (simple heuristic)
        scores["clarity"] = 1.0 if "##" in answer.answer or "###" in answer.answer else 0.7

        # Check practicality
        scores["practicality"] = 1.0 if "建议" in answer.answer or "步骤" in answer.answer else 0.6

        # Check evidence support
        scores["accuracy"] = min(1.0, len(answer.evidence) / 3)

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

    async def process_request(self, request: Dict[str, Any], context: MessageContext) -> GeneratedAnswer:
        """Generate an answer from the request's query context, ranked sources, and synthesis."""
        query_context = request["query_context"]
        sources = request["sources"]
        synthesis = request["synthesis"]
        intent = query_context["intent"]
        if self.model_client is not None:
            return await self._generate_with_llm(query_context, sources, synthesis)
        return self._generate_comprehensive_answer(
            query_context,
            sources,
            intent
        )

    async def _generate_with_llm(self, query_context: Dict[str, Any], sources: List, synthesis: Dict[str, Any]) -> GeneratedAnswer:
        if self._assistant is None:
            self._assistant = AssistantAgent(
                name="answer_gen_llm",
                description="LLM-backed policy answer composer.",
                system_message=GENERATION_SYSTEM_PROMPT,
                model_client=self.model_client,
                model_context=create_buffered_context(10),
            )

        # Simplify structured info for the prompt
        info = self._extract_information_from_sources(sources)
        user_prompt = build_generation_user_prompt(query_context, info, synthesis)
        async with self._assistant_lock:
            resp = await self._assistant.on_messages([TextMessage(content=user_prompt, source="user")], CancellationToken())
        answer_text = resp.chat_message.to_text().strip()
        if not answer_text:
            raise ValueError("Answer model returned empty text")

        # Calculate confidence via heuristic
        confidence = self._calculate_answer_confidence(sources, info)
        query_id = query_context["query_id"]
        return GeneratedAnswer(
            query_id=query_id,
            answer=answer_text,
            sources=[source[0]["document_id"] for source in sources],
            confidence=confidence,
            evidence=self._generate_evidence_list(sources),
            assumptions=info["assumptions"],
            limitations=info["limitations"],
            followup_questions=self._generate_followup_questions(info),
            generation_time=0.0,
        )
