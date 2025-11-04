"""
智能路由编排器 - 基于意图路由的多智能体系统
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json

from autogen_core import (
    AgentRuntime,
    SingleThreadedAgentRuntime,
    MessageContext
)
try:
    from app.llm import model_client as GLOBAL_MODEL_CLIENT
except Exception:
    GLOBAL_MODEL_CLIENT = None

from models.base import (
    AgentType,
    UserQuery,
    FinalAnswer,
    UUID
)
from agents.router.intent_router import IntentRouterAgent, IntentClassification
from agents.specialized.chat_agent import ChatAgent
from agents.specialized.calculation_agent import CalculationAgent
from agents.specialized.clarifier import ClarifierAgent
from agents.retrieval.vector_retriever import VectorRetrieverAgent
from agents.retrieval.graph_retriever import GraphRetrieverAgent
from agents.analysis.policy_analyzer import PolicyAnalyzerAgent
from agents.analysis.policy_comparator import PolicyComparatorAgent
from agents.generation.answer_generator import AnswerGeneratorAgent
from agents.common import session_store


class SmartOrchestrator:
    """智能路由编排器 - 根据意图智能路由到不同的处理链"""

    def __init__(
        self,
        model_config: Dict[str, Any],
        vector_store_config: Dict[str, Any],
        logging_config: Optional[Dict[str, Any]] = None
    ):
        """初始化编排器"""
        self.model_config = model_config
        self.vector_store_config = vector_store_config
        self.setup_logging(logging_config)

        self.logger = logging.getLogger(__name__)

        # 初始化agents
        self.intent_router = IntentRouterAgent(model_client=self._create_model_client())
        # 使用基础设施级会话存储（非智能体）

        # 专门agents
        self.specialized_agents = {
            "chat_agent": ChatAgent(),
            "calculation_agent": CalculationAgent(),
            "comparison_agent": PolicyComparatorAgent(model_client=self._create_model_client()),
            "clarifier": ClarifierAgent(),
        }

        # 知识库agents
        self.kb_agents = {
            "knowledge_retriever": None,  # 延迟初始化
            "policy_analyzer": PolicyAnalyzerAgent(model_client=self._create_model_client()),
            "answer_generator": AnswerGeneratorAgent(model_client=self._create_model_client())
        }

        # 图谱agents
        self.graph_agents = {
            "graph_retriever": None,  # 延迟初始化
            "policy_analyzer": PolicyAnalyzerAgent(model_client=self._create_model_client()),
            "answer_generator": AnswerGeneratorAgent(model_client=self._create_model_client())
        }

        # 处理链配置
        self.processing_chains = {
            "chat_agent": {
                "agents": ["chat_agent"],
                "parallel": False
            },
            "calculation_chain": {
                "agents": ["knowledge_retriever", "policy_analyzer", "calculation_agent", "answer_generator"],
                "parallel": False
            },
            "comparison_chain": {
                "agents": ["knowledge_retriever", "comparison_agent", "answer_generator"],
                "parallel": False
            },
            "kb_chain": {
                "agents": ["knowledge_retriever", "policy_analyzer", "answer_generator"],
                "parallel": False
            },
            "graph_chain": {
                "agents": ["graph_retriever", "policy_analyzer", "answer_generator"],
                "parallel": False
            },
            "hybrid_chain": {
                "agents": ["knowledge_retriever", "graph_retriever", "policy_analyzer", "answer_generator"],
                "parallel": True
            }
        }

        self.logger.info("Smart Orchestrator initialized with intelligent routing")

    def setup_logging(self, config: Optional[Dict[str, Any]]):
        """设置日志"""
        logging.basicConfig(
            level=config.get("level", "INFO") if config else "INFO",
            format=config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    def _create_model_client(self):
        """创建模型客户端"""
        # 优先使用全局统一的 LLM 客户端
        return GLOBAL_MODEL_CLIENT

    async def initialize(self):
        """初始化系统"""
        self.logger.info("Initializing smart orchestrator...")

        # 初始化检索agents
        self.kb_agents["knowledge_retriever"] = VectorRetrieverAgent(**self.vector_store_config)
        await self.kb_agents["knowledge_retriever"].initialize()

        # 初始化图谱检索器（LightRAG）
        self.graph_agents["graph_retriever"] = GraphRetrieverAgent()
        await self.graph_agents["graph_retriever"].initialize()

        self.logger.info("Smart orchestrator initialized successfully")

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FinalAnswer:
        """处理查询的主入口"""
        # 创建用户查询对象
        user_query = UserQuery(
            text=query,
            session_id=session_id,
            user_id=user_id
        )

        # 获取或创建会话（基础设施层，非路由）
        session_id, _ = session_store.create_or_update_session(session_id, user_id)
        session_store.add_query(session_id, user_query)

        try:
            # Step 1: 意图识别和路由
            self.logger.info(f"Step 1: Routing query - {query[:50]}...")
            routing = await self.intent_router.process_request(user_query, MessageContext())

            self.logger.info(
                f"Routed to: {routing.intent_type} -> {routing.processing_chain} "
                f"(confidence: {routing.confidence:.2f})"
            )

            # Step 2: 根据路由执行处理链
            result = await self._execute_processing_chain(
                user_query,
                routing,
                session_id
            )

            # Step 3: 添加答案到会话
            if result:
                session_store.add_answer(session_id, result)

            return result or self._create_fallback_response(user_query)

        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return self._create_error_response(user_query, str(e))

    async def _execute_processing_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification,
        session_id: str
    ) -> Optional[FinalAnswer]:
        """执行处理链（支持并行与早停）"""
        chains = routing.processing_chain or ["kb_chain"]
        # 单链快捷路径
        if not routing.requires_parallel and len(chains) == 1 and chains[0] != "hybrid_chain":
            name = chains[0]
            if name == "chat_agent":
                return await self._handle_chat_chain(user_query, routing)
            if name == "calculation_chain":
                return await self._handle_calculation_chain(user_query, routing)
            if name == "comparison_chain":
                return await self._handle_comparison_chain(user_query, routing)
            if name == "clarification_chain":
                return await self._handle_clarification_chain(user_query, routing)
            if name == "kb_chain":
                return await self._handle_kb_chain(user_query, routing)
            if name == "graph_chain":
                return await self._handle_graph_chain(user_query, routing)
            if name == "hybrid_chain":
                return await self._handle_hybrid_chain(user_query, routing)
            # 未识别则回退 KB
            return await self._handle_kb_chain(user_query, routing)

        # 并行：当指定多个链或需要并行/混合
        tasks = []
        def spawn(chain_name: str):
            if chain_name == "kb_chain":
                return self._handle_kb_chain(user_query, routing)
            if chain_name == "graph_chain":
                return self._handle_graph_chain(user_query, routing)
            if chain_name == "comparison_chain":
                return self._handle_comparison_chain(user_query, routing)
            if chain_name == "calculation_chain":
                return self._handle_calculation_chain(user_query, routing)
            if chain_name == "chat_agent":
                return self._handle_chat_chain(user_query, routing)
            if chain_name == "clarification_chain":
                return self._handle_clarification_chain(user_query, routing)
            if chain_name == "hybrid_chain":
                return self._handle_hybrid_chain(user_query, routing)
            return self._handle_kb_chain(user_query, routing)

        for name in chains:
            tasks.append(asyncio.create_task(spawn(name)))

        try:
            EARLY_STOP_CONF = float(os.getenv("EARLY_STOP_CONF", "0.80"))
        except Exception:
            EARLY_STOP_CONF = 0.80
        results: list[FinalAnswer] = []
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                try:
                    res = d.result()
                    if res:
                        if res.confidence >= EARLY_STOP_CONF:
                            for p in pending:
                                p.cancel()
                            return res
                        results.append(res)
                except Exception as e:
                    self.logger.warning(f"Parallel chain error: {e}")
            tasks = list(pending)

        # 择优（最大置信度）
        if results:
            best = max(results, key=lambda r: getattr(r, 'confidence', 0.0))
            return best

        # 全部失败回退 KB
        return await self._handle_kb_chain(user_query, routing)

    async def _handle_chat_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理聊天链"""
        agent = self.specialized_agents["chat_agent"]
        response = await agent.process_request({
            "text": user_query.text,
            "response_type": routing.intent_type,
            "intent": routing.sub_intent or routing.intent_type
        }, MessageContext())

        return FinalAnswer(
            query_id=user_query.id,
            answer=response.response_text,
            sources=[],
            confidence=0.95,  # 聊天响应置信度高
            verification_passed=True,
            metadata={
                "response_type": response.response_type,
                "emotion": response.emotion,
                "chain": "chat_agent"
            }
        )

    async def _handle_calculation_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理计算链"""
        # 先检索相关政策
        documents = await self._retrieve_documents(user_query, top_k=5)

        # 执行计算
        calc_agent = self.specialized_agents["calculation_agent"]
        result = await calc_agent.process_request({
            "query": user_query.text,
            "policy_documents": documents
        }, MessageContext())

        # 生成答案
        answer = self._format_calculation_result(result, user_query.text)

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer,
            sources=documents[:3],
            confidence=result.confidence,
            verification_passed=result.confidence > 0.7,
            metadata={
                "calculated_amount": result.calculated_amount,
                "applicable_policies": result.applicable_policies,
                "chain": "calculation_chain"
            }
        )

    async def _handle_comparison_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理比较链"""
        # 检索多个相关政策
        documents = await self._retrieve_documents(user_query, top_k=10)

        if len(documents) < 2:
            return FinalAnswer(
                query_id=user_query.id,
                answer="抱歉，需要至少2个相关政策才能进行比较。请提供更具体的查询。",
                sources=documents,
                confidence=0.3,
                verification_passed=False
            )

        # 执行比较
        comparison_agent = self.specialized_agents["comparison_agent"]
        comparison_result = await comparison_agent.process_request({
            "documents": documents[:5],  # 最多比较5个
            "query_id": user_query.id,
            "comparison_type": "all"
        }, MessageContext())

        # 格式化比较结果
        answer = self._format_comparison_result(comparison_result)

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer,
            sources=documents,
            confidence=comparison_result.confidence,
            verification_passed=comparison_result.confidence > 0.7,
            metadata={
                "compared_documents": len(documents),
                "chain": "comparison_chain"
            }
        )

    async def _handle_clarification_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        clarifier = self.specialized_agents.get("clarifier")
        result = await clarifier.process_request({"query": user_query.text}, MessageContext())
        question = result.get("question", "请问您具体想了解申请条件、办理流程还是截止时间？")
        return FinalAnswer(
            query_id=user_query.id,
            answer=f"为更好地解答您的问题，请澄清：{question}",
            sources=[],
            confidence=0.4,
            verification_passed=False,
            metadata={"clarification": True}
        )

    async def _handle_kb_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理知识库链"""
        # 检索文档
        documents = await self._retrieve_documents(user_query, top_k=5)

        if not documents:
            return self._create_no_policy_response(user_query)

        # 分析文档
        # 并发分析文档（限流）
        semaphore = asyncio.Semaphore(5)
        async def analyze_doc(d):
            async with semaphore:
                return await self.kb_agents["policy_analyzer"].process_request({
                    "document": d,
                    "query_id": user_query.id,
                    "intent": routing.sub_intent or routing.intent_type
                }, MessageContext())
        tasks = [asyncio.create_task(analyze_doc(d)) for d in documents[:5]]
        analyses = [res for res in await asyncio.gather(*tasks, return_exceptions=False)]

        # 生成答案
        generation_request = {
            "query_context": {
                "query_id": str(user_query.id),
                "text": user_query.text,
                "intent": routing.intent_type,
                "entities": routing.entities
            },
            "sources": [(a.dict(), a.relevance_score) for a in analyses],
            "synthesis": {
                "most_relevant": analyses[0].document_id if analyses else None,
                "total_analyzed": len(analyses)
            }
        }

        generated_answer = await self.kb_agents["answer_generator"].process_request(
            generation_request,
            MessageContext()
        )

        return FinalAnswer(
            query_id=user_query.id,
            answer=generated_answer.answer,
            sources=documents,
            confidence=generated_answer.confidence,
            verification_passed=generated_answer.confidence > 0.7,
            metadata={
                "chain": "kb_chain",
                "retrieved_count": len(documents)
            }
        )

    async def _handle_graph_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理图谱链（LightRAG）"""
        documents = []
        if self.graph_agents.get("graph_retriever"):
            try:
                result = await self.graph_agents["graph_retriever"].process_request(
                    {"query_text": user_query.text, "mode": "hybrid", "top_k": 5},
                    MessageContext(),
                )
                documents = result.documents
            except Exception as e:
                self.logger.warning(f"Graph retrieval failed, fallback to KB: {e}")
                documents = await self._retrieve_documents(user_query, top_k=5)
        else:
            documents = await self._retrieve_documents(user_query, top_k=5)

        if not documents:
            return self._create_no_policy_response(user_query)

        # 分析文档
        # 并发分析文档（限流）
        semaphore = asyncio.Semaphore(5)
        async def analyze_doc2(d):
            async with semaphore:
                return await self.kb_agents["policy_analyzer"].process_request({
                    "document": d,
                    "query_id": user_query.id,
                    "intent": routing.sub_intent or routing.intent_type
                }, MessageContext())
        tasks2 = [asyncio.create_task(analyze_doc2(d)) for d in documents[:5]]
        analyses = [res for res in await asyncio.gather(*tasks2, return_exceptions=False)]

        # 生成答案
        generation_request = {
            "query_context": {
                "query_id": str(user_query.id),
                "text": user_query.text,
                "intent": routing.intent_type,
                "entities": routing.entities
            },
            "sources": [(a.dict(), a.relevance_score) for a in analyses],
            "synthesis": {
                "most_relevant": analyses[0].document_id if analyses else None,
                "total_analyzed": len(analyses)
            }
        }

        generated_answer = await self.kb_agents["answer_generator"].process_request(
            generation_request,
            MessageContext()
        )

        return FinalAnswer(
            query_id=user_query.id,
            answer=generated_answer.answer,
            sources=documents,
            confidence=generated_answer.confidence,
            verification_passed=generated_answer.confidence > 0.7,
            metadata={
                "chain": "graph_chain",
                "retrieved_count": len(documents)
            }
        )

    async def _handle_hybrid_chain(
        self,
        user_query: UserQuery,
        routing: IntentClassification
    ) -> FinalAnswer:
        """处理混合链（并行执行）"""
        # 并行执行知识库检索和图谱检索
        tasks = [
            self._handle_kb_chain(user_query, routing),
            self._handle_graph_chain(user_query, routing),
        ]

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 选择最好的结果
        best_result = None
        best_confidence = 0

        for result in results:
            if not isinstance(result, Exception) and hasattr(result, 'confidence'):
                if result.confidence > best_confidence:
                    best_result = result
                    best_confidence = result.confidence

        if best_result:
            best_result.metadata["chain"] = "hybrid_chain"
            return best_result

        # 回退到知识库链
        return await self._handle_kb_chain(user_query, routing)

    async def _retrieve_documents(self, user_query: UserQuery, top_k: int = 5) -> List:
        """检索文档"""
        if self.kb_agents["knowledge_retriever"]:
            from models.base import RetrievalRequest
            request = RetrievalRequest(
                query_id=user_query.id,
                top_k=top_k,
                threshold=0.7
            )
            result = await self.kb_agents["knowledge_retriever"].process_request(
                request,
                MessageContext()
            )
            docs = result.documents if result else []
            # 若KB检索为空，尝试图谱检索作为回退
            if not docs and self.graph_agents.get("graph_retriever"):
                try:
                    graph_result = await self.graph_agents["graph_retriever"].process_request(
                        {"query_text": user_query.text, "mode": "hybrid", "top_k": top_k},
                        MessageContext(),
                    )
                    docs = graph_result.documents or []
                except Exception as e:
                    self.logger.warning(f"Graph fallback retrieval failed: {e}")
            return docs
        return []

    def _format_calculation_result(self, result, query: str) -> str:
        """格式化计算结果"""
        answer = f"根据您的问题'{query}'，计算结果如下：\n\n"
        answer += f"## 补贴金额\n{result.calculated_amount:.2f}元\n\n"

        if result.calculation_breakdown:
            answer += "## 计算明细\n"
            for item in result.calculation_breakdown:
                if "金额" in item:
                    answer += f"- {item.get('项目', '')}: {item['金额']}元\n"
                elif "值" in item:
                    answer += f"- {item.get('项目', '')}: {item['值']}\n"

        if result.applicable_policies:
            answer += f"\n## 适用政策\n"
            for policy in result.applicable_policies:
                answer += f"- {policy}\n"

        if result.assumptions:
            answer += f"\n## 计算假设\n"
            for assumption in result.assumptions:
                answer += f"- {assumption}\n"

        if result.notes:
            answer += f"\n## 注意事项\n"
            for note in result.notes:
                answer += f"- {note}\n"

        return answer

    def _format_comparison_result(self, comparison_result) -> str:
        """格式化比较结果"""
        answer = f"## 政策比较结果\n\n"
        answer += f"{comparison_result.summary}\n\n"

        if comparison_result.comparison_table:
            answer += "## 详细对比\n\n"
            for category, data in comparison_result.comparison_table.items():
                answer += f"### {category}\n"
                if data:
                    # 简化表格显示
                    for i, row in enumerate(data[:5]):  # 只显示前5行
                        if i == 0:
                            # 表头
                            answer += "| " + " | ".join(row) + " |\n"
                            answer += "| " + " | ".join(["---"] * len(row)) + " |\n"
                        else:
                            answer += "| " + " | ".join(str(cell)[:20] for cell in row) + " |\n"
                answer += "\n"

        return answer

    def _create_no_policy_response(self, user_query: UserQuery) -> FinalAnswer:
        """创建无政策响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer="抱歉，我没有找到与您的问题相关的政策信息。建议您：\n\n1. 尝试使用不同的关键词\n2. 咨询相关部门获取最新政策\n3. 查看政府官方网站",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"reason": "no_documents_found"}
        )

    def _create_error_response(self, user_query: UserQuery, error: str) -> FinalAnswer:
        """创建错误响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer=f"处理您的问题时遇到了错误：{error}\n\n请稍后重试或联系系统管理员。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"error": error}
        )

    def _create_fallback_response(self, user_query: UserQuery) -> FinalAnswer:
        """创建回退响应"""
        return FinalAnswer(
            query_id=user_query.id,
            answer="抱歉，我暂时无法处理您的请求。请尝试重新表述您的问题或联系人工客服。",
            sources=[],
            confidence=0.3,
            verification_passed=False,
            metadata={"fallback": True}
        )

    def get_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        metrics = {
            "intent_router": self.intent_router.get_metrics(),
            "session_manager": self.session_manager.get_metrics(),
            "specialized_agents": {
                name: agent.get_metrics()
                for name, agent in self.specialized_agents.items()
            }
        }
        return metrics
