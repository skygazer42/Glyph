"""
增强查询分析智能体 - 融合ChatDB和Gove的功能
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from autogen_core import MessageContext
from autogen_agentchat.messages import TextMessage

from ..chatdb.base_agent import BaseAgent
from ..router.intent_router import IntentRouterAgent, IntentClassification
from ..specialized.chat_agent import ChatAgent
from ..specialized.calculation_agent import CalculationAgent
from ..retrieval.policy_retriever import PolicyRetrieverAgent
from ..analysis.policy_analyzer import PolicyAnalyzerAgent
from ..analysis.policy_comparator import PolicyComparatorAgent
from ..generation.answer_generator import AnswerGeneratorAgent
from ...models.base import (
    UserQuery,
    UUID,
    BaseModel,
    Field
)


class QueryAnalysis(BaseModel):
    """查询分析结果"""
    intent_classification: IntentClassification
    policy_analysis: Optional[Dict[str, Any]] = None
    retrieved_policies: Optional[List[Any]] = None
    calculation_result: Optional[Dict[str, Any]] = None
    comparison_result: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0, le=1)
    processing_chain: List[str]
    execution_plan: List[Dict[str, Any]]


class EnhancedQueryAnalyzerAgent(BaseAgent):
    """增强查询分析智能体 - 集成意图识别和智能路由"""

    def __init__(self, **kwargs):
        super().__init__(
            agent_id="enhanced_query_analyzer",
            agent_name="EnhancedQueryAnalyzer",
            description="智能分析用户查询并生成执行计划",
            **kwargs
        )

        # 初始化子智能体
        self.intent_router = IntentRouterAgent()
        self.chat_agent = ChatAgent()
        self.calculation_agent = CalculationAgent()
        self.policy_retriever = None  # 延迟初始化
        self.policy_analyzer = PolicyAnalyzerAgent()
        self.policy_comparator = PolicyComparatorAgent()
        self.answer_generator = AnswerGeneratorAgent()

        # 分析策略
        self.analysis_strategies = {
            "chat": {
                "agents": ["chat_agent"],
                "parallel": False,
                "response_type": "casual"
            },
            "calculation": {
                "agents": ["policy_retriever", "calculation_agent"],
                "parallel": False,
                "response_type": "numerical"
            },
            "policy_inquiry": {
                "agents": ["policy_retriever", "policy_analyzer"],
                "parallel": False,
                "response_type": "structured"
            },
            "comparison": {
                "agents": ["policy_retriever", "policy_comparator"],
                "parallel": False,
                "response_type": "comparison"
            },
            "complex": {
                "agents": ["policy_retriever", "policy_analyzer", "policy_comparator", "calculation_agent"],
                "parallel": True,
                "response_type": "comprehensive"
            }
        }

    async def process_request(
        self,
        request: Dict[str, Any],
        context: MessageContext
    ) -> QueryAnalysis:
        """处理查询分析请求"""
        user_query = request.get("user_query")
        if not user_query:
            raise ValueError("user_query is required")

        self.logger.info(f"Analyzing query: {user_query.text[:50]}...")

        try:
            # Step 1: 意图识别
            intent_result = await self.intent_router.process_request(
                user_query,
                MessageContext()
            )

            self.logger.info(
                f"Intent: {intent_result.intent_type} "
                f"(confidence: {intent_result.confidence:.2f})"
            )

            # Step 2: 根据意图选择分析策略
            strategy = self._select_analysis_strategy(intent_result)

            # Step 3: 并行执行相关分析
            analysis_results = await self._execute_analysis(
                user_query,
                intent_result,
                strategy
            )

            # Step 4: 生成执行计划
            execution_plan = self._generate_execution_plan(
                intent_result,
                strategy,
                analysis_results
            )

            # Step 5: 计算综合置信度
            confidence = self._calculate_confidence(
                intent_result,
                analysis_results
            )

            # 构建分析结果
            result = QueryAnalysis(
                intent_classification=intent_result,
                policy_analysis=analysis_results.get("policy_analysis"),
                retrieved_policies=analysis_results.get("retrieved_policies"),
                calculation_result=analysis_results.get("calculation_result"),
                comparison_result=analysis_results.get("comparison_result"),
                confidence=confidence,
                processing_chain=strategy["agents"],
                execution_plan=execution_plan
            )

            # 发送分析摘要
            await self._send_analysis_summary(result)

            return result

        except Exception as e:
            self.logger.error(f"Error in query analysis: {e}", exc_info=True)
            await self.handle_exception("process_request", e)

            # 返回默认分析
            return QueryAnalysis(
                intent_classification=IntentClassification(
                    intent_type="policy_inquiry",
                    confidence=0.5,
                    processing_chain=["policy_retriever", "policy_analyzer"]
                ),
                confidence=0.3,
                processing_chain=["policy_retriever", "policy_analyzer"],
                execution_plan=[{"step": "fallback_analysis", "agent": "fallback"}]
            )

    def _select_analysis_strategy(self, intent_result: IntentClassification) -> Dict[str, Any]:
        """选择分析策略"""
        intent_type = intent_result.intent_type

        # 基本策略选择
        if intent_type in ["greeting", "farewell", "casual_chat"]:
            return self.analysis_strategies["chat"]
        elif intent_type == "calculation":
            return self.analysis_strategies["calculation"]
        elif intent_type == "comparison":
            return self.analysis_strategies["comparison"]
        elif intent_type == "policy_inquiry":
            # 判断是否需要复杂分析
            if self._is_complex_query(intent_result):
                return self.analysis_strategies["complex"]
            else:
                return self.analysis_strategies["policy_inquiry"]
        else:
            # 默认使用策略查询
            return self.analysis_strategies["policy_inquiry"]

    def _is_complex_query(self, intent_result: IntentClassification) -> bool:
        """判断是否为复杂查询"""
        # 基于实体数量判断
        entity_count = sum(len(v) for v in intent_result.entities.values())
        if entity_count > 3:
            return True

        # 基于子意图判断
        if intent_result.sub_intent == "comparison":
            return True

        # 基于置信度判断
        if intent_result.confidence < 0.7:
            return True

        return False

    async def _execute_analysis(
        self,
        user_query: UserQuery,
        intent_result: IntentClassification,
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行分析任务"""
        results = {}
        agents = strategy["agents"]
        parallel = strategy["parallel"]

        # 准备通用上下文
        context = {
            "query": user_query.text,
            "intent": intent_result.intent_type,
            "sub_intent": intent_result.sub_intent,
            "entities": intent_result.entities
        }

        if parallel:
            # 并行执行
            tasks = []
            for agent_name in agents:
                task = self._execute_agent_analysis(agent_name, user_query, context)
                tasks.append(task)

            # 等待所有任务完成
            if tasks:
                agent_results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(agent_results):
                    if not isinstance(result, Exception):
                        agent_name = agents[i]
                        results[f"{agent_name}_result"] = result

        else:
            # 串行执行
            for agent_name in agents:
                try:
                    result = await self._execute_agent_analysis(
                        agent_name,
                        user_query,
                        context
                    )
                    if result:
                        results[f"{agent_name}_result"] = result
                except Exception as e:
                    self.logger.error(f"Error executing {agent_name}: {e}")

        return results

    async def _execute_agent_analysis(
        self,
        agent_name: str,
        user_query: UserQuery,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """执行特定智能体的分析"""
        try:
            if agent_name == "chat_agent":
                response = await self.chat_agent.process_request({
                    "text": user_query.text,
                    "response_type": context["intent"],
                    "intent": context["sub_intent"] or context["intent"]
                }, MessageContext())
                return {"response": response}

            elif agent_name == "calculation_agent":
                result = await self.calculation_agent.process_request({
                    "query": user_query.text
                }, MessageContext())
                return result

            elif agent_name == "policy_retriever":
                if self.policy_retriever is None:
                    # 延迟初始化
                    from ..knowledge_base.vector_store import VectorStore
                    # 这里需要实际的vector_store配置
                    pass
                # 实现政策检索
                return None

            elif agent_name == "policy_analyzer":
                # 实现政策分析
                return None

            elif agent_name == "policy_comparator":
                # 实现政策比较
                return None

            elif agent_name == "answer_generator":
                # 实现答案生成
                return None

            return None

        except Exception as e:
            self.logger.error(f"Error in {agent_name}: {e}")
            return None

    def _generate_execution_plan(
        self,
        intent_result: IntentClassification,
        strategy: Dict[str, Any],
        analysis_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成执行计划"""
        plan = []

        # 基本执行步骤
        plan.append({
            "step": 1,
            "action": "intent_recognition",
            "agent": "intent_router",
            "status": "completed",
            "result": {
                "intent": intent_result.intent_type,
                "confidence": intent_result.confidence
            }
        })

        # 添加后续步骤
        for i, agent_name in enumerate(strategy["agents"], 2):
            status = "completed" if f"{agent_name}_result" in analysis_results else "pending"
            plan.append({
                "step": i,
                "action": agent_name.replace("_agent", "_analysis"),
                "agent": agent_name,
                "status": status,
                "result": analysis_results.get(f"{agent_name}_result")
            })

        # 添加最终步骤
        plan.append({
            "step": len(plan) + 1,
            "action": "response_generation",
            "agent": "response_formatter",
            "status": "pending",
            "dependencies": [step["step"] for step in plan if step["status"] == "pending"]
        })

        return plan

    def _calculate_confidence(
        self,
        intent_result: IntentClassification,
        analysis_results: Dict[str, Any]
    ) -> float:
        """计算综合置信度"""
        base_confidence = intent_result.confidence

        # 基于分析结果调整
        if analysis_results:
            successful_analyses = sum(
                1 for key, value in analysis_results.items()
                if value is not None
            )
            total_analyses = len(analysis_results)

            if total_analyses > 0:
                success_rate = successful_analyses / total_analyses
                base_confidence = base_confidence * 0.7 + success_rate * 0.3

        return min(base_confidence, 1.0)

    async def _send_analysis_summary(self, result: QueryAnalysis):
        """发送分析摘要"""
        summary_parts = [
            f"查询类型: {result.intent_classification.intent_type}",
            f"置信度: {result.confidence:.1%}",
            f"处理链: {' → '.join(result.processing_chain)}"
        ]

        if result.execution_plan:
            summary_parts.append(f"执行步骤: {len(result.execution_plan)}")

        summary = " | ".join(summary_parts)
        await self.send_response(f"[分析完成] {summary}")

    def get_metrics(self) -> Dict[str, Any]:
        """获取分析指标"""
        return {
            **self.metrics,
            "agent_type": self.agent_type,
            "name": self.name,
            "strategies": len(self.analysis_strategies),
            "sub_agents": len([
                self.intent_router,
                self.chat_agent,
                self.calculation_agent
            ])
        }