"""
Coordinator agent for managing the policy QA workflow.
"""

import json
import asyncio
from typing import Dict, Any, List
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

from ..base.base_agent import BaseAgent
from ..base.types import (
    MessageTypes,
    AgentTypes,
    TopicTypes
)


class Coordinator(BaseAgent):
    """Coordinator agent that manages the entire policy QA workflow."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        agents: Dict[str, Any]
    ):
        """Initialize the coordinator."""
        super().__init__(name, "coordinator", llm_config)
        self.agents = agents
        self.workflow_state = {}

    def _get_default_system_message(self) -> str:
        """Get the default system message."""
        return """您是政策问答协调员，负责协调整个问答工作流程。

您的职责：
1. 协调不同专业Agent之间的工作
2. 管理从问题理解到最终答案的整个流程
3. 确保所有Agent有效协作
4. 处理错误并在必要时重试
5. 编译最终的综合响应

工作流程：
1. 将问题发送给问题理解专员进行分析
2. 将分析结果发送给政策检索专员进行文档检索
3. 将结果发送给政策分析专员进行详细分析
4. 将分析发送给答案生成专员创建答案
5. 将答案发送给答案验证专员进行验证
6. 编译并返回最终验证的答案

始终维护上下文并确保Agent之间的顺畅转换。"""

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query through the complete workflow."""
        self.workflow_state = {
            "query": query,
            "step": 1,
            "total_steps": 5,
            "results": {}
        }

        try:
            # Step 1: Question Understanding
            self.logger.info("Step 1: Understanding question...")
            question_understander = self.agents.get(AgentTypes.QUESTION_UNDERSTANDER.value)
            if not question_understander:
                raise ValueError("QuestionUnderstander not available")

            analysis_result = await question_understander.process_message(query)
            if not analysis_result.get("success"):
                raise ValueError(f"Question understanding failed: {analysis_result.get('error')}")

            self.workflow_state["results"]["analysis"] = analysis_result["data"]
            self.workflow_state["step"] = 2

            # Step 2: Policy Retrieval
            self.logger.info("Step 2: Retrieving relevant policies...")
            policy_retriever = self.agents.get(AgentTypes.POLICY_RETRIEVER.value)
            if not policy_retriever:
                raise ValueError("PolicyRetriever not available")

            retrieval_request = {
                "query": query,
                "analysis": analysis_result["data"],
                "method": "hybrid"
            }

            retrieval_result = await policy_retriever.process_message(
                json.dumps(retrieval_request)
            )
            if not retrieval_result.get("success"):
                raise ValueError(f"Policy retrieval failed: {retrieval_result.get('error')}")

            self.workflow_state["results"]["retrieval"] = retrieval_result["data"]
            self.workflow_state["step"] = 3

            # Step 3: Policy Analysis
            self.logger.info("Step 3: Analyzing retrieved policies...")
            policy_analyzer = self.agents.get(AgentTypes.POLICY_ANALYZER.value)
            if not policy_analyzer:
                raise ValueError("PolicyAnalyzer not available")

            analysis_request = {
                "query": query,
                "documents": [doc.__dict__ if hasattr(doc, '__dict__') else doc
                             for doc in retrieval_result["data"].documents]
            }

            analysis_report = await policy_analyzer.process_message(
                json.dumps(analysis_request)
            )
            if not analysis_report.get("success"):
                raise ValueError(f"Policy analysis failed: {analysis_report.get('error')}")

            self.workflow_state["results"]["analysis_report"] = analysis_report["data"]
            self.workflow_state["step"] = 4

            # Step 4: Answer Generation
            self.logger.info("Step 4: Generating answer...")
            answer_generator = self.agents.get(AgentTypes.ANSWER_GENERATOR.value)
            if not answer_generator:
                raise ValueError("AnswerGenerator not available")

            generation_request = {
                "query": query,
                "analysis": analysis_result["data"],
                "document_analyses": analysis_report["data"]["document_analyses"]
            }

            answer_result = await answer_generator.process_message(
                json.dumps(generation_request)
            )
            if not answer_result.get("success"):
                raise ValueError(f"Answer generation failed: {answer_result.get('error')}")

            self.workflow_state["results"]["answer"] = answer_result["data"]
            self.workflow_state["step"] = 5

            # Step 5: Answer Verification
            self.logger.info("Step 5: Verifying answer...")
            answer_verifier = self.agents.get(AgentTypes.ANSWER_VERIFIER.value)
            if not answer_verifier:
                raise ValueError("AnswerVerifier not available")

            verification_request = {
                "query": query,
                "answer": answer_result["data"].get("answer", ""),
                "sources": answer_result["data"].get("sources", []),
                "document_analyses": analysis_report["data"]["document_analyses"]
            }

            verification_result = await answer_verifier.process_message(
                json.dumps(verification_request)
            )
            if not verification_result.get("success"):
                # Continue even if verification fails
                self.logger.warning(f"Verification failed: {verification_result.get('error')}")
                verification_result["data"] = {
                    "is_accurate": False,
                    "issues": ["Verification process failed"],
                    "confidence": 0.5
                }

            self.workflow_state["results"]["verification"] = verification_result["data"]

            # Compile final response
            final_response = self._compile_final_response()
            self.workflow_state["step"] = "completed"

            return {
                "success": True,
                "query": query,
                "answer": final_response,
                "workflow_state": self.workflow_state
            }

        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "workflow_state": self.workflow_state
            }

    def _compile_final_response(self) -> Dict[str, Any]:
        """Compile the final response from all workflow results."""
        results = self.workflow_state["results"]

        # Get the generated answer
        answer_data = results.get("answer", {})
        verification_data = results.get("verification", {})

        # Format the final response
        final_response = {
            "answer": answer_data.get("answer", ""),
            "sources": answer_data.get("sources", []),
            "confidence": answer_data.get("confidence", 0.0),
            "verification": {
                "is_verified": verification_data.get("is_accurate", False),
                "issues": verification_data.get("issues", []),
                "suggestions": verification_data.get("suggestions", [])
            },
            "metadata": {
                "retrieved_documents": len(results.get("retrieval", {}).get("documents", [])),
                "processing_steps": self.workflow_state.get("step", 0),
                "total_processing_time": "N/A"
            }
        }

        # Add warning if verification found issues
        if verification_data.get("issues"):
            final_response["warning"] = "Please review the answer carefully as some issues were identified during verification."

        return final_response

    async def process_message(
        self,
        message: str,
        sender: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process incoming message - delegate to process_query."""
        return await self.process_query(message)