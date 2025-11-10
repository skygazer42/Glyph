"""
Policy analysis agent implementation.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

from autogen_core import MessageContext, CancellationToken
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage

from app.models.base import (
    AgentType,
    MessageType,
    AgentMessage,
    PolicyDocument,
    PolicyAnalysis,
    QueryAnalysis,
    PolicyType,
    QueryIntent
)
from app.agents.framework.base.base_agent import StatefulAgent, ReactiveAgent
from app.agents.framework.common.model_client import create_buffered_context
from .prompt import nlp_extraction_system_prompt, nlp_extraction_user_prompt


class PolicyAnalyzerAgent(ReactiveAgent):
    """Deep policy analysis agent with structured extraction."""

    def __init__(
        self,
        model_client: Any = None,
        **kwargs
    ):
        """Initialize the policy analyzer agent."""
        super().__init__(
            agent_type=AgentType.POLICY_ANALYZER,
            name="PolicyAnalyzer",
            description="深度分析政策文档，提取关键信息",
            **kwargs
        )

        self.model_client = model_client
        self._assistant: Optional[AssistantAgent] = None

        # Analysis patterns and rules
        self.eligibility_patterns = [
            r"(符合条件|申请条件|资格要求|需要满足)",
            r"(具有.*资格|拥有.*条件)",
            r"(户籍要求|居住要求|年龄要求|收入要求)",
            r"(企业资质|注册时间|注册资本|纳税记录)"
        ]

        self.benefit_patterns = [
            r"(补贴标准|补助金额|补贴额度)",
            r"(最高.*元|不超过.*元|按比例.*%)",
            r"(一次性补贴|分期发放|定额补助)",
            r"(税收减免|优惠幅度|减免比例)"
        ]

        self.deadline_patterns = [
            r"(截止日期|申请期限|有效期)",
            r"(截止到.*年.*月.*日|有效期至.*年.*月)",
            r"(.*年.*月.*日前|.*个工作日内)",
            r"(长期有效|每年.*月|季度申报)"
        ]

        # Register event handlers
        self.register_event_handler("policy_received", self._on_policy_received)
        self.register_event_handler("analysis_requested", self._on_analysis_requested)

        # Add triggers
        self.add_trigger(
            condition={"event": "new_policy", "type": "urgent"},
            action=self._urgent_policy_analysis
        )

    async def _handle_retrieval_result(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle retrieval result messages."""
        documents_data = message.content.get("documents", [])
        query_id = message.content.get("query_id", "")

        if not documents_data:
            return AgentMessage(
                type=MessageType.ERROR,
                sender=self.agent_type,
                recipient=message.sender,
                content={"error": "No documents provided for analysis"},
                correlation_id=message.correlation_id
            )

        # Analyze each document
        analyses = []
        for doc_data in documents_data:
            doc = PolicyDocument(**doc_data)
            analysis = await self._analyze_document(doc, query_id)
            analyses.append(analysis.dict())

        # Synthesize analysis
        synthesis = await self._synthesize_analyses(analyses, query_id)

        return AgentMessage(
            type=MessageType.ANALYSIS_RESULT,
            sender=self.agent_type,
            recipient=message.sender,
            content={
                "query_id": query_id,
                "analyses": analyses,
                "synthesis": synthesis,
                "total_analyzed": len(analyses)
            },
            correlation_id=message.correlation_id
        )

    async def _analyze_document(self, document: PolicyDocument, query_id: str) -> PolicyAnalysis:
        """Perform deep analysis of a policy document."""
        self.logger.info(f"Analyzing document: {document.title}")

        # Extract structured information
        eligibility_criteria = await self._extract_eligibility_criteria(document)
        benefit_details = await self._extract_benefit_details(document)
        application_steps = await self._extract_application_steps(document)
        required_documents = await self._extract_required_documents(document)
        deadlines = await self._extract_deadlines(document)
        contact_info = await self._extract_contact_info(document)
        limitations = await self._extract_limitations(document)

        # Calculate relevance score based on query context
        relevance_score = await self._calculate_relevance_score(document, query_id)

        # Find related policies
        related_policies = await self._find_related_policies(document)

        # Calculate analysis confidence
        analysis_confidence = await self._calculate_analysis_confidence(
            eligibility_criteria,
            benefit_details,
            application_steps,
            deadlines
        )

        return PolicyAnalysis(
            document_id=document.id,
            query_id=query_id,
            relevance_score=relevance_score,
            eligibility_criteria=eligibility_criteria,
            benefit_details=benefit_details,
            application_steps=application_steps,
            required_documents=required_documents,
            deadlines=deadlines,
            contact_info=contact_info,
            limitations=limitations,
            related_policies=related_policies,
            analysis_confidence=analysis_confidence
        )

    async def _extract_eligibility_criteria(self, document: PolicyDocument) -> List[str]:
        """Extract eligibility criteria using pattern matching and NLP."""
        criteria = []
        content = document.content

        # Pattern-based extraction
        for pattern in self.eligibility_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Extract surrounding context
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 100)
                context = content[start:end].strip()
                criteria.append(context)

        # If model client available, use NLP extraction
        if self.model_client:
            try:
                nlp_criteria = await self._extract_with_nlp(
                    content,
                    "以 JSON 数组形式返回所有申请条件和资格要求，短句精炼"
                )
                criteria.extend(nlp_criteria)
            except Exception as e:
                self.logger.warning(f"LLM eligibility extraction failed: {e}")

        # Remove duplicates and clean
        criteria = list(set(criteria))
        return [c for c in criteria if len(c) > 10]

    async def _extract_benefit_details(self, document: PolicyDocument) -> Optional[str]:
        """Extract benefit amounts and details."""
        content = document.content
        benefits = []

        # Extract numeric values and contexts
        for pattern in self.benefit_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Extract sentence containing the match
                sentence_start = content.rfind('。', 0, match.start()) + 1
                sentence_end = content.find('。', match.end())
                if sentence_end == -1:
                    sentence_end = len(content)
                sentence = content[sentence_start:sentence_end].strip()
                benefits.append(sentence)

        # Look for monetary amounts
        amount_pattern = r'([0-9,]+(?:\.\d+)?元)'
        amounts = re.findall(amount_pattern, content)
        if amounts:
            benefits.append(f"补贴金额: {', '.join(amounts[:5])}")

        # Look for percentages
        percent_pattern = r'([0-9]+(?:\.\d+)?%)'
        percentages = re.findall(percent_pattern, content)
        if percentages:
            benefits.append(f"优惠比例: {', '.join(percentages[:5])}")

        return "\n".join(benefits[:10]) if benefits else None

    async def _extract_application_steps(self, document: PolicyDocument) -> List[str]:
        """Extract application procedure steps."""
        content = document.content
        steps = []

        # Look for numbered or bulleted lists
        step_patterns = [
            r'第[一二三四五六七八九十\d]+步[:：]',
            r'(\d+)[\.、]',
            r'步骤[\d]+[:：]'
        ]

        for pattern in step_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Extract the step
                step_start = match.start()
                step_end = content.find('\n', match.end())
                if step_end == -1:
                    step_end = len(content)
                step = content[step_start:step_end].strip()
                if len(step) > 5:
                    steps.append(step)

        # Look for process keywords
        process_keywords = ["申请", "提交", "审核", "审批", "公示", "发放", "领取"]
        for keyword in process_keywords:
            pattern = f"{keyword}[:：]([^。;；\n]+)"
            matches = re.findall(pattern, content)
            steps.extend(matches)

        return steps[:10]

    async def _extract_required_documents(self, document: PolicyDocument) -> List[str]:
        """Extract required application documents."""
        content = document.content
        documents = []

        # Common document types
        doc_types = [
            "身份证", "户口本", "营业执照", "税务登记证",
            "组织机构代码证", "银行流水", "收入证明", "房产证",
            "购房合同", "发票", "收据", "申请表", "审批表"
        ]

        for doc_type in doc_types:
            if doc_type in content:
                # Extract the full context
                pattern = f"({doc_type}[^。;；\n]*)"
                matches = re.findall(pattern, content)
                documents.extend(matches)

        return list(set(documents))

    async def _extract_deadlines(self, document: PolicyDocument) -> List[str]:
        """Extract important dates and deadlines."""
        content = document.content
        deadlines = []

        # Date patterns
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'(\d{1,2}月\d{1,2}日)',
            r'(\d{1,2}个工作日)',
            r'(\d{1,2}天)'
        ]

        # Extract dates with context
        for pattern in date_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get surrounding context
                start = max(0, match.start() - 20)
                end = min(len(content), match.end() + 20)
                context = content[start:end].strip()
                if any(keyword in context for keyword in ["截止", "有效期", "申请", "前", "内"]):
                    deadlines.append(context)

        return deadlines[:10]

    async def _extract_contact_info(self, document: PolicyDocument) -> List[str]:
        """Extract contact information."""
        content = document.content
        contacts = []

        # Phone patterns
        phone_pattern = r'(\d{3,4}[-\s]?\d{7,8}|\d{11})'
        phones = re.findall(phone_pattern, content)
        contacts.extend([f"电话: {phone}" for phone in phones])

        # Email patterns
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        emails = re.findall(email_pattern, content)
        contacts.extend([f"邮箱: {email}" for email in emails])

        # Address patterns
        address_keywords = ["地址", "办公地址", "受理地点"]
        for keyword in address_keywords:
            pattern = f"{keyword}[:：]([^。;；\n]+)"
            matches = re.findall(pattern, content)
            contacts.extend(matches)

        return contacts[:10]

    async def _extract_limitations(self, document: PolicyDocument) -> List[str]:
        """Extract policy limitations and restrictions."""
        content = document.content
        limitations = []

        # Limitation keywords
        limit_keywords = [
            "不得", "不能", "不予", "除外", "仅限",
            "限制", "禁止", "不符合", "不享受"
        ]

        for keyword in limit_keywords:
            pattern = f".{keyword}[^。;；\n]+"
            matches = re.findall(pattern, content)
            limitations.extend(matches)

        return limitations[:10]

    async def _calculate_relevance_score(self, document: PolicyDocument, query_id: str) -> float:
        """Calculate relevance score based on document content and query."""
        # Get query context from memory
        memory_context = await self.get_memory_context(limit=5)

        # Simple scoring based on keyword matching
        score = 0.5  # Base score

        # Boost score for recent policies
        if document.effective_date:
            days_since_effective = (datetime.now() - document.effective_date).days
            if days_since_effective < 365:
                score += 0.2

        # Boost score for relevant policy types
        if document.doc_type in [PolicyType.SUBSIDY, PolicyType.VOUCHER]:
            score += 0.1

        # Deduct score for expired policies
        if document.expiry_date and document.expiry_date < datetime.now():
            score -= 0.3

        return min(1.0, max(0.0, score))

    async def _find_related_policies(self, document: PolicyDocument) -> List[str]:
        """Find related policies based on keywords and departments."""
        related = []

        # Simple keyword-based matching
        for keyword in document.keywords:
            # In a real implementation, this would query the vector store
            # For now, return empty list
            pass

        return related

    async def _calculate_analysis_confidence(
        self,
        eligibility: List[str],
        benefits: Optional[str],
        steps: List[str],
        deadlines: List[str]
    ) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.0
        total = 4.0

        # Check for each information type
        if eligibility:
            score += 1.0
        if benefits:
            score += 1.0
        if steps:
            score += 1.0
        if deadlines:
            score += 1.0

        return score / total

    async def _extract_with_nlp(self, content: str, prompt: str) -> List[str]:
        """Use LLM (AssistantAgent) to extract info as a JSON array of strings."""
        if not self.model_client:
            return []
        if self._assistant is None:
            self._assistant = AssistantAgent(
                name="policy_analyzer_llm",
                system_message=nlp_extraction_system_prompt(),
                model_client=self.model_client,
                model_context=create_buffered_context(10),
            )
        user = nlp_extraction_user_prompt(content, prompt)
        resp = await self._assistant.on_messages([TextMessage(content=user, source="user")], CancellationToken())
        text = resp.chat_message.to_text().strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x) for x in data][:20]
        except Exception as e:
            self.logger.debug(f"LLM JSON parse failed: {e}")
        return []

    async def _synthesize_analyses(self, analyses: List[Dict], query_id: str) -> Dict[str, Any]:
        """Synthesize multiple document analyses."""
        if not analyses:
            return {}

        # Find most relevant document
        most_relevant = max(analyses, key=lambda x: x.get("relevance_score", 0))

        # Collect all benefits
        all_benefits = [a.get("benefit_details") for a in analyses if a.get("benefit_details")]
        unique_benefits = list(set(all_benefits))

        # Collect all eligibility criteria
        all_eligibility = []
        for a in analyses:
            all_eligibility.extend(a.get("eligibility_criteria", []))
        unique_eligibility = list(set(all_eligibility))

        return {
            "most_relevant_document": most_relevant.get("document_id"),
            "total_benefits": len(unique_benefits),
            "total_eligibility_criteria": len(unique_eligibility),
            "coverage_score": len([a for a in analyses if a.get("relevance_score", 0) > 0.7]) / len(analyses)
        }

    # Event handlers
    async def _on_policy_received(self, event: Dict[str, Any]):
        """Handle new policy received event."""
        doc = event.get("document")
        if doc:
            await self._analyze_document(doc, event.get("query_id", ""))

    async def _on_analysis_requested(self, event: Dict[str, Any]):
        """Handle analysis requested event."""
        # Trigger analysis
        pass

    async def _urgent_policy_analysis(self, event: Dict[str, Any]):
        """Handle urgent policy analysis trigger."""
        self.logger.info("Performing urgent policy analysis")
        # Implementation for urgent analysis
        pass

    async def _handle_user_query(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle user query messages."""
        return None

    async def _handle_query_analysis(self, message: AgentMessage, ctx: MessageContext) -> Optional[AgentMessage]:
        """Handle query analysis messages."""
        return None

    async def process_request(self, request: Any, context: MessageContext) -> Any:
        """Process an analysis request."""
        return await self._analyze_document(request.document, request.query_id)
