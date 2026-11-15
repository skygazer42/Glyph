"""
Coordinator agent for managing the policy QA workflow.
"""

import json
import logging
from pydantic import TypeAdapter
from typing import Dict, Any

from ..base.types import (
    AgentTypes
)


class Coordinator:
    """Coordinator agent that manages the entire policy QA workflow."""

    def __init__(
        self,
        name: str,
        llm_config: Dict[str, Any],
        agents: Dict[str, Any]
    ):
        """Initialize the coordinator."""
        self.name = name
        self.llm_config = llm_config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.agents = agents

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query through the complete workflow."""
        workflow_state: Dict[str, Any] = {
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
            if not analysis_result["success"]:
                raise ValueError(f"Question understanding failed: {analysis_result.get('error')}")

            analysis = TypeAdapter(Any).dump_python(analysis_result["data"], mode="json")
            workflow_state["results"]["analysis"] = analysis
            workflow_state["step"] = 2

            # Step 2: Policy Retrieval
            self.logger.info("Step 2: Retrieving relevant policies...")
            policy_retriever = self.agents.get(AgentTypes.POLICY_RETRIEVER.value)
            if not policy_retriever:
                raise ValueError("PolicyRetriever not available")

            retrieval_request = {
                "query": query,
                "analysis": analysis,
                "method": "hybrid"
            }

            retrieval_result = await policy_retriever.process_message(
                json.dumps(retrieval_request)
            )
            if not retrieval_result["success"]:
                raise ValueError(f"Policy retrieval failed: {retrieval_result.get('error')}")

            retrieval = TypeAdapter(Any).dump_python(retrieval_result["data"], mode="json")
            workflow_state["results"]["retrieval"] = retrieval
            workflow_state["step"] = 3

            # Step 3: Policy Analysis
            self.logger.info("Step 3: Analyzing retrieved policies...")
            policy_analyzer = self.agents.get(AgentTypes.POLICY_ANALYZER.value)
            if not policy_analyzer:
                raise ValueError("PolicyAnalyzer not available")

            analysis_request = {
                "query": query,
                "documents": retrieval["documents"]
            }

            analysis_report = await policy_analyzer.process_message(
                json.dumps(analysis_request)
            )
            if not analysis_report["success"]:
                raise ValueError(f"Policy analysis failed: {analysis_report.get('error')}")

            report = TypeAdapter(Any).dump_python(analysis_report["data"], mode="json")
            workflow_state["results"]["analysis_report"] = report
            workflow_state["step"] = 4

            # Step 4: Answer Generation
            self.logger.info("Step 4: Generating answer...")
            answer_generator = self.agents.get(AgentTypes.ANSWER_GENERATOR.value)
            if not answer_generator:
                raise ValueError("AnswerGenerator not available")

            generation_request = {
                "query": query,
                "analysis": analysis,
                "document_analyses": report["document_analyses"]
            }

            answer_result = await answer_generator.process_message(
                json.dumps(generation_request)
            )
            if not answer_result["success"]:
                raise ValueError(f"Answer generation failed: {answer_result.get('error')}")

            answer_data = TypeAdapter(Any).dump_python(answer_result["data"], mode="json")
            workflow_state["results"]["answer"] = answer_data
            workflow_state["step"] = 5

            # Step 5: Answer Verification
            self.logger.info("Step 5: Verifying answer...")
            answer_verifier = self.agents.get(AgentTypes.ANSWER_VERIFIER.value)
            if answer_verifier:
                verification_request = {
                    "query": query,
                    "answer": answer_data["answer"],
                    "sources": answer_data["sources"],
                    "document_analyses": report["document_analyses"]
                }

                verification_result = await answer_verifier.process_message(
                    json.dumps(verification_request)
                )
                if not verification_result["success"]:
                    # Continue even if verification fails
                    self.logger.warning(f"Verification failed: {verification_result.get('error')}")
                    verification_result["data"] = {
                        "is_accurate": False,
                        "issues": ["Verification process failed"],
                        "confidence": 0.5
                    }
            else:
                self.logger.info("AnswerVerifier not available, skipping verification stage.")
                verification_result = {
                    "data": {
                        "is_accurate": False,
                        "issues": ["verification module disabled"],
                        "confidence": 0.0
                    }
                }

            workflow_state["results"]["verification"] = verification_result["data"]

            # Compile final response
            final_response = self._compile_final_response(workflow_state)
            workflow_state["step"] = "completed"

            return {
                "success": True,
                "query": query,
                "answer": final_response,
                "workflow_state": workflow_state
            }

        except Exception as e:
            self.logger.exception("Workflow failed")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "workflow_state": workflow_state
            }

    def _compile_final_response(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compile the final response from all workflow results."""
        results = workflow_state["results"]

        # Get the generated answer
        answer_data = results["answer"]
        verification_data = results["verification"]

        # Format the final response
        final_response = {
            "answer": answer_data["answer"],
            "sources": answer_data["sources"],
            "confidence": answer_data["confidence"],
            "verification": {
                "is_verified": verification_data["is_accurate"],
                "issues": verification_data["issues"],
                "suggestions": verification_data.get("suggestions", [])
            },
            "metadata": {
                "retrieved_documents": len(results["retrieval"]["documents"]),
                "processing_steps": workflow_state["step"],
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
    ) -> Dict[str, Any]:
        """Process incoming message - delegate to process_query."""
        return await self.process_query(message)
