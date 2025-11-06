"""
智能体编排服务 - 统一管理所有智能体
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from enum import Enum

from autogen_core import AgentRuntime, SingleThreadedAgentRuntime, MessageContext

from ..models.base import UserQuery, FinalAnswer, UUID
from ..agents.chatdb.factory import AgentFactory, get_agent_factory
from ..agents.enhanced.query_analyzer import EnhancedQueryAnalyzerAgent, QueryAnalysis
from ..agents.specialized.chat_agent import ChatAgent
from ..agents.specialized.calculation_agent import CalculationAgent
from ..agents.analysis.policy_analyzer import PolicyAnalyzerAgent
from ..agents.analysis.policy_comparator import PolicyComparatorAgent
from ..agents.generation.answer_generator import AnswerGeneratorAgent
from ..agents.coordination.session_manager import SessionManagerAgent


class ProcessingMode(Enum):
    """处理模式"""
    SINGLE = "single"  # 单个智能体
    SEQUENTIAL = "sequential"  # 串行处理
    PARALLEL = "parallel"  # 并行处理
    ADAPTIVE = "adaptive"  # 自适应模式


class AgentOrchestratorService:
    """智能体编排服务 - 统一管理所有智能体"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化编排服务"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化工厂
        self.agent_factory = get_agent_factory()
        self.agent_factory.register_default_agents()
        self.agent_factory.set_config("orchestrator", self.config)

        # 初始化核心组件
        self.runtime = SingleThreadedAgentRuntime()
        self.session_manager = SessionManagerAgent()
        self.query_analyzer = EnhancedQueryAnalyzerAgent()

        # 注册所有智能体
        self.agents: Dict[str, Any] = {
            "session_manager": self.session_manager,
            "query_analyzer": self.query_analyzer,
            "chat_agent": ChatAgent(),
            "calculation_agent": CalculationAgent(),
            "policy_analyzer": PolicyAnalyzerAgent(),
            "policy_comparator": PolicyComparatorAgent(),
            "answer_generator": AnswerGeneratorAgent()
        }

        # 处理链配置
        self.processing_chains = {
            "chat": {
                "mode": ProcessingMode.SINGLE,
                "agents": ["chat_agent"],
                "parallel": False
            },
            "simple_query": {
                "mode": ProcessingMode.SEQUENTIAL,
                "agents": ["policy_retriever", "policy_analyzer", "answer_generator"],
                "parallel": False
            },
            "complex_query": {
                "mode": ProcessingMode.ADAPTIVE,
                "agents": ["policy_retriever", "policy_analyzer", "policy_comparator", "calculation_agent"],
                "parallel": True
            },
            "calculation": {
                "mode": ProcessingMode.SEQUENTIAL,
                "agents": ["policy_retriever", "policy_analyzer", "calculation_agent", "answer_generator"],
                "parallel": False
            },
            "comparison": {
                "mode": ProcessingMode.SEQUENTIAL,
                "agents": ["policy_retriever", "policy_comparator", "answer_generator"],
                "parallel": False
            }
        }

        # 智能体注册推迟到 initialize()
        self.logger.info("Agent Orchestrator Service constructed (deferred init)")

    async def initialize(self):
        """异步初始化（注册所有智能体并启动 runtime）"""
        self.runtime.start()
        for name, agent in self.agents.items():
            await self.runtime.register(agent, name)
        self.logger.info("Agent Orchestrator Service initialized")

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        mode: Optional[ProcessingMode] = None
    ) -> FinalAnswer:
        """处理查询的主入口"""
        # 创建用户查询对象
        user_query = UserQuery(
            text=query,
            session_id=session_id,
            user_id=user_id
        )

        # 获取或创建会话
        session_result = await self.session_manager.process_request({
            "action": "create_or_update",
            "session_id": session_id,
            "user_id": user_id
        }, MessageContext())

        session_id = session_result["session_id"]

        # 添加查询到会话
        await self.session_manager.process_request({
            "action": "add_query",
            "session_id": session_id,
            "query": user_query
        }, MessageContext())

        try:
            # Step 1: 查询分析和路由
            analysis = await self.query_analyzer.process_request({
                "user_query": user_query
            }, MessageContext())

            self.logger.info(
                f"Query analysis: {analysis.intent_classification.intent_type} "
                f"-> {analysis.processing_chain}"
            )

            # Step 2: 根据分析结果执行处理
            result = await self._execute_processing_chain(
                user_query,
                analysis,
                mode or ProcessingMode.ADAPTIVE
            )

            # Step 3: 添加结果到会话
            if result:
                await self.session_manager.process_request({
                    "action": "add_answer",
                    "session_id": session_id,
                    "answer": result
                }, MessageContext())

            return result or self._create_fallback_response(user_query)

        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return self._create_error_response(user_query, str(e))

    async def _execute_processing_chain(
        self,
        user_query: UserQuery,
        analysis: QueryAnalysis,
        mode: ProcessingMode
    ) -> Optional[FinalAnswer]:
        """执行处理链"""
        processing_chain = analysis.processing_chain
        intent_type = analysis.intent_classification.intent_type

        # 根据意图类型和模式选择执行方式
        if intent_type in ["greeting", "farewell", "casual_chat"]:
            return await self._execute_chat_chain(user_query, analysis)

        elif intent_type == "calculation":
            return await self._execute_calculation_chain(user_query, analysis)

        elif intent_type == "comparison":
            return await self._execute_comparison_chain(user_query, analysis)

        else:
            # 政策查询
            return await self._execute_policy_chain(user_query, analysis, mode)

    async def _execute_chat_chain(
        self,
        user_query: UserQuery,
        analysis: QueryAnalysis
    ) -> FinalAnswer:
        """执行聊天链"""
        agent = self.agents["chat_agent"]
        response = await agent.process_request({
            "text": user_query.text,
            "response_type": analysis.intent_classification.intent_type
        }, MessageContext())

        return FinalAnswer(
            query_id=user_query.id,
            answer=response.response_text,
            sources=[],
            confidence=0.95,
            verification_passed=True,
            metadata={
                "response_type": response.response_type,
                "chain": "chat"
            }
        )

    async def _execute_calculation_chain(
        self,
        user_query: UserQuery,
        analysis: QueryAnalysis
    ) -> FinalAnswer:
        """执行计算链"""
        # 检索相关政策（如果可用）
        policies = await self._retrieve_policies(user_query, top_k=3)

        # 执行计算
        calc_agent = self.agents["calculation_agent"]
        result = await calc_agent.process_request({
            "query": user_query.text,
            "policy_documents": policies
        }, MessageContext())

        # 格式化答案
        answer = self._format_calculation_result(result)

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer,
            sources=policies,
            confidence=result.confidence,
            verification_passed=result.confidence > 0.7,
            metadata={
                "calculated_amount": result.calculated_amount,
                "chain": "calculation"
            }
        )

    async def _execute_comparison_chain(
        self,
        user_query: UserQuery,
        analysis: QueryAnalysis
    ) -> FinalAnswer:
        """执行比较链"""
        # 检索多个政策
        policies = await self._retrieve_policies(user_query, top_k=5)

        if len(policies) < 2:
            return FinalAnswer(
                query_id=user_query.id,
                answer="需要至少2个相关政策才能进行比较。",
                sources=policies,
                confidence=0.3,
                verification_passed=False
            )

        # 执行比较
        comparator = self.agents["policy_comparator"]
        comparison = await comparator.process_request({
            "documents": policies[:5],
            "query_id": user_query.id,
            "comparison_type": "all"
        }, MessageContext())

        # 格式化比较结果
        answer = self._format_comparison_result(comparison)

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer,
            sources=policies,
            confidence=comparison.confidence,
            verification_passed=comparison.confidence > 0.7,
            metadata={
                "compared_count": len(policies),
                "chain": "comparison"
            }
        )

    async def _execute_policy_chain(
        self,
        user_query: UserQuery,
        analysis: QueryAnalysis,
        mode: ProcessingMode
    ) -> FinalAnswer:
        """执行政策查询链"""
        # 检索政策
        policies = await self._retrieve_policies(user_query, top_k=5)

        if not policies:
            return self._create_no_policy_response(user_query)

        # 分析政策
        analyses = []
        for policy in policies[:3]:
            analyzer = self.agents["policy_analyzer"]
            result = await analyzer.process_request({
                "document": policy,
                "query_id": user_query.id,
                "intent": analysis.intent_classification.sub_intent
            }, MessageContext())
            analyses.append(result)

        # 生成答案
        generator = self.agents["answer_generator"]
        answer = await generator.process_request({
            "query": user_query.text,
            "sources": analyses,
            "analysis": analysis.dict()
        }, MessageContext())

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer.answer,
            sources=policies,
            confidence=answer.confidence,
            verification_passed=answer.confidence > 0.7,
            metadata={
                "retrieved_count": len(policies),
                "analyzed_count": len(analyses),
                "chain": "policy"
            }
        )

    async def _retrieve_policies(self, user_query: UserQuery, top_k: int = 5) -> List:
        """检索政策文档"""
        # 这里应该调用实际的政策检索器
        # 暂时返回空列表
        return []

    def _format_calculation_result(self, result) -> str:
        """格式化计算结果"""
        if not result:
            return "无法完成计算"

        answer = f"## 计算结果\n\n补贴金额：{result.calculated_amount:.2f}元\n\n"

        if result.calculation_breakdown:
            answer += "### 计算明细\n"
            for item in result.calculation_breakdown:
                for key, value in item.items():
                    answer += f"- {key}: {value}\n"

        if result.notes:
            answer += "\n### 注意事项\n"
            for note in result.notes:
                answer += f"- {note}\n"

        return answer

    def _format_comparison_result(self, comparison) -> str:
        """格式化比较结果"""
        if not comparison or not comparison.summary:
            return "无法完成比较"

        answer = f"## 政策比较\n\n{comparison.summary}\n\n"

        if comparison.comparison_table:
            answer += "### 详细对比\n\n"
            for category, data in comparison.comparison_table.items():
                answer += f"**{category}**\n"
                for row in data[:3]:  # 只显示前3行
                    answer += f"- {row}\n"
                answer += "\n"

        return answer

    def _create_no_policy_response(self, user_query: UserQuery) -> FinalAnswer:
        """创建无政策响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer="抱歉，没有找到相关的政策信息。建议您：\n\n1. 尝试不同的关键词\n2. 咨询相关部门\n3. 查看政府官网",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"reason": "no_policies_found"}
        )

    def _create_error_response(self, user_query: UserQuery, error: str) -> FinalAnswer:
        """创建错误响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer=f"处理出错：{error}\n\n请稍后重试。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"error": error}
        )

    def _create_fallback_response(self, user_query: UserQuery) -> FinalAnswer:
        """创建回退响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer="抱歉，暂时无法处理您的请求。",
            sources=[],
            confidence=0.3,
            verification_passed=False,
            metadata={"fallback": True}
        )

    async def shutdown(self):
        """关闭编排服务"""
        self.logger.info("Shutting down Agent Orchestrator Service...")
        self.runtime.stop()

    def get_metrics(self) -> Dict[str, Any]:
        """获取编排服务指标"""
        metrics = {
            "total_agents": len(self.agents),
            "processing_chains": len(self.processing_chains),
            "agent_metrics": {}
        }

        # 收集各个智能体的指标
        for name, agent in self.agents.items():
            if hasattr(agent, 'get_metrics'):
                metrics["agent_metrics"][name] = agent.get_metrics()

        return metrics
