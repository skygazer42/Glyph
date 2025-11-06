"""
增强版Policy QA系统编排器 - 集成所有新的agents
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from autogen_core import (
    AgentRuntime,
    SingleThreadedAgentRuntime,
    MessageContext,
    TopicId,
    CancellationToken
)
from autogen_agentchat.messages import TextMessage, AgentMessage

from models.base import (
    AgentType,
    MessageType,
    UserQuery,
    QueryAnalysis,
    RetrievalRequest,
    RetrievalResult,
    PolicyAnalysis,
    GeneratedAnswer,
    FinalAnswer,
    UUID
)
from agents.retrieval.query_analyzer import QueryAnalyzerAgent
from agents.retrieval.vector_retriever import VectorRetrieverAgent
from agents.analysis.policy_analyzer import PolicyAnalyzerAgent
from agents.analysis.policy_comparator import PolicyComparatorAgent
from agents.generation.answer_generator import AnswerGeneratorAgent
from agents.verification.answer_verifier import AnswerVerifierAgent
from agents.common import session_store
try:
    from app.llm import model_client as GLOBAL_MODEL_CLIENT
except Exception:
    GLOBAL_MODEL_CLIENT = None
# DataLoader 已移除，文档加载使用 LlamaIndexIntegration


class EnhancedPolicyQAOrchestrator:
    """增强版政策问答系统编排器"""

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

        self.runtime = SingleThreadedAgentRuntime()
        self.agents: Dict[AgentType, Any] = {}
        self.workflow_state: Dict[str, Any] = {}
        self.active_sessions: Dict[str, Dict] = {}

        # 数据加载已迁移到 LlamaIndexIntegration，不再在编排器中处理
        self.data_loaded = False

        self.logger.info("Enhanced Policy QA Orchestrator initialized")

    def setup_logging(self, config: Optional[Dict[str, Any]]):
        """设置日志配置"""
        logging.basicConfig(
            level=config.get("level", "INFO") if config else "INFO",
            format=config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        self.logger = logging.getLogger(__name__)

    async def initialize(self, load_data: bool = True):
        """初始化所有agents和组件"""
        self.logger.info("Initializing enhanced agents...")

        # 数据加载已迁移到 LlamaIndexIntegration
        # 使用独立的脚本（如 scripts/embed_documents.py）进行文档加载和索引构建
        if load_data:
            self.logger.info("文档加载已迁移到 LlamaIndex，请使用 scripts/embed_documents.py")
            self.data_loaded = True

        # 2. 初始化核心agents
        await self._initialize_core_agents()

        # 3.（可选）使用 runtime 的高级能力时再注册；此处无需注册/启动

        self.logger.info("All enhanced agents initialized successfully")

    async def _initialize_core_agents(self):
        """初始化核心功能agents"""
        # 查询理解Agent
        self.agents[AgentType.QUERY_ANALYZER] = QueryAnalyzerAgent(
            model_client=self._create_model_client()
        )

        # 向量检索Agent
        self.agents[AgentType.POLICY_RETRIEVER] = VectorRetrieverAgent(
            **self.vector_store_config
        )
        await self.agents[AgentType.POLICY_RETRIEVER].initialize()

        # 政策分析Agent
        self.agents[AgentType.POLICY_ANALYZER] = PolicyAnalyzerAgent(
            model_client=self._create_model_client()
        )

        # 答案生成Agent
        self.agents[AgentType.ANSWER_GENERATOR] = AnswerGeneratorAgent(
            model_client=self._create_model_client()
        )

        # 答案验证Agent
        if hasattr(AgentType, 'FACT_CHECKER'):
            self.agents[AgentType.FACT_CHECKER] = AnswerVerifierAgent(
                model_client=self._create_model_client()
            )

    async def _initialize_management_agents(self):
        """初始化管理相关组件（此处仅保留比较器）"""
        # 政策比较Agent
        self.policy_comparator = PolicyComparatorAgent(
            model_client=self._create_model_client()
        )
        self.agents["policy_comparator"] = self.policy_comparator

    def _create_model_client(self):
        """创建模型客户端"""
        return GLOBAL_MODEL_CLIENT

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FinalAnswer:
        """处理用户查询的完整工作流程"""
        # 创建或获取会话（基础设施层）
        session_id, _ = session_store.create_or_update_session(session_id, user_id)

        # 创建用户查询对象
        user_query = UserQuery(
            text=query,
            session_id=session_id,
            user_id=user_id
        )

        # 添加查询到会话
        session_store.add_query(session_id, user_query)

        # 获取会话上下文
        context_result = session_store.get_context(session_id, query)

        # 处理查询
        start_time = datetime.now()
        self.workflow_state[session_id] = {
            "query": user_query,
            "step": 1,
            "total_steps": 6,
            "results": {},
            "errors": [],
            "context": context_result
        }

        try:
            # Step 1: 查询理解
            self.logger.info(f"Step 1: Understanding query - {query[:50]}...")
            query_analysis = await self.agents[AgentType.QUERY_ANALYZER].process_request(
                user_query,
                MessageContext()
            )
            self.workflow_state[session_id]["results"]["query_analysis"] = query_analysis
            self.workflow_state[session_id]["step"] = 2

            # Step 2: 文档检索
            self.logger.info("Step 2: Retrieving relevant policies...")
            retrieval_result = await self._retrieve_documents(
                user_query, query_analysis, context_result
            )
            self.workflow_state[session_id]["results"]["retrieval"] = retrieval_result
            self.workflow_state[session_id]["step"] = 3

            if not retrieval_result.documents:
                self.logger.warning("No documents found for the query")
                return self._create_no_policy_response(user_query)

            # Step 3: 政策分析
            self.logger.info(f"Step 3: Analyzing {len(retrieval_result.documents)} documents...")
            analyses = await self._analyze_policies(
                retrieval_result.documents, user_query, query_analysis
            )
            self.workflow_state[session_id]["results"]["analysis"] = analyses
            self.workflow_state[session_id]["step"] = 4

            # Step 4: 政策比较（如果需要）
            comparison_result = None
            if (query_analysis.intent == "policy_comparison" or
                "比较" in query or "区别" in query):
                self.logger.info("Step 4: Comparing policies...")
                comparison_result = await self.policy_comparator.process_request({
                    "documents": retrieval_result.documents,
                    "query_id": user_query.id,
                    "comparison_type": "all"
                }, MessageContext())
                self.workflow_state[session_id]["results"]["comparison"] = comparison_result

            # Step 5: 答案生成
            self.logger.info("Step 5: Generating answer...")
            generated_answer = await self._generate_answer(
                user_query, query_analysis, retrieval_result, analyses, comparison_result
            )
            self.workflow_state[session_id]["results"]["answer"] = generated_answer
            self.workflow_state[session_id]["step"] = 6

            # Step 6: 答案验证
            self.logger.info("Step 6: Verifying answer...")
            verification_result = await self._verify_answer(
                generated_answer, retrieval_result, analyses
            )

            # Step 7: 编译最终答案
            self.logger.info("Step 7: Compiling final response...")
            final_answer = await self._compile_final_answer(
                user_query,
                query_analysis,
                retrieval_result,
                analyses,
                generated_answer,
                comparison_result,
                verification_result
            )

            # 添加答案到会话
            session_store.add_answer(session_id, final_answer)

            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            final_answer.total_processing_time = processing_time

            # 更新工作流状态
            self.workflow_state[session_id]["step"] = "completed"
            self.workflow_state[session_id]["final_answer"] = final_answer

            self.logger.info(f"Query processed successfully in {processing_time:.2f}s")
            return final_answer

        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            self.workflow_state[session_id]["errors"].append(str(e))
            return self._create_error_response(user_query, str(e))

    async def _retrieve_documents(
        self,
        user_query: UserQuery,
        query_analysis: QueryAnalysis,
        context: Dict[str, Any]
    ) -> RetrievalResult:
        """检索相关文档"""
        # 使用历史上下文优化查询
        enhanced_query = user_query.text
        if context.get("topic_continuity") and context.get("related_entities"):
            # 添加相关实体到查询
            entities = " ".join(context["related_entities"][:3])
            enhanced_query = f"{enhanced_query} {entities}"

        # 创建检索请求
        retrieval_request = RetrievalRequest(
            query_id=user_query.id,
            filters={
                "policy_types": [t.value for t in query_analysis.policy_types],
                "regions": query_analysis.location_constraints or ["济南市"]
            },
            top_k=10,
            threshold=0.7
        )

        # 执行检索
        return await self.agents[AgentType.POLICY_RETRIEVER].process_request(
            retrieval_request,
            MessageContext()
        )

    async def _analyze_policies(
        self,
        documents: List,
        user_query: UserQuery,
        query_analysis: QueryAnalysis
    ) -> List[PolicyAnalysis]:
        """分析政策文档"""
        analyses = []

        # 并行分析多个文档
        tasks = []
        for doc in documents[:5]:  # 最多分析5个文档
            task = self.agents[AgentType.POLICY_ANALYZER].process_request(
                {"document": doc, "query_id": user_query.id, "intent": query_analysis.intent},
                MessageContext()
            )
            tasks.append(task)

        # 等待所有分析完成
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if not isinstance(result, Exception):
                    analyses.append(result)

        return analyses

    async def _generate_answer(
        self,
        user_query: UserQuery,
        query_analysis: QueryAnalysis,
        retrieval_result: RetrievalResult,
        analyses: List[PolicyAnalysis],
        comparison_result: Optional[Any] = None
    ) -> GeneratedAnswer:
        """生成答案"""
        generation_request = {
            "query_context": {
                "query_id": str(user_query.id),
                "text": user_query.text,
                "intent": query_analysis.intent.value,
                "entities": query_analysis.entities
            },
            "sources": [(a.dict(), a.relevance_score) for a in analyses],
            "synthesis": {
                "most_relevant_document": analyses[0].document_id if analyses else None,
                "total_analyzed": len(analyses),
                "coverage_score": len([a for a in analyses if a.relevance_score > 0.7]) / len(analyses) if analyses else 0
            },
            "comparison": comparison_result.dict() if comparison_result else None
        }

        return await self.agents[AgentType.ANSWER_GENERATOR].process_request(
            generation_request,
            MessageContext()
        )

    async def _verify_answer(
        self,
        answer: GeneratedAnswer,
        retrieval_result: RetrievalResult,
        analyses: List[PolicyAnalysis]
    ) -> Dict[str, Any]:
        """验证答案"""
        verification = {
            "passed": True,
            "confidence": answer.confidence,
            "issues": []
        }

        # 如果有验证agent，使用它
        if hasattr(AgentType, 'FACT_CHECKER') and AgentType.FACT_CHECKER in self.agents:
            try:
                verification_result = await self.agents[AgentType.FACT_CHECKER].process_request({
                    "answer": answer,
                    "sources": analyses
                }, MessageContext())
                verification.update(verification_result)
            except Exception as e:
                self.logger.error(f"Error in answer verification: {e}")

        return verification

    async def _compile_final_answer(
        self,
        user_query: UserQuery,
        query_analysis: QueryAnalysis,
        retrieval_result: RetrievalResult,
        analyses: List[PolicyAnalysis],
        generated_answer: GeneratedAnswer,
        comparison_result: Optional[Any] = None,
        verification_result: Optional[Dict[str, Any]] = None
    ) -> FinalAnswer:
        """编译最终答案"""
        # 获取源文档
        source_docs = []
        for doc in retrieval_result.documents:
            if doc.id in generated_answer.sources:
                source_docs.append(doc)

        # 添加比较结果到答案
        answer_text = generated_answer.answer
        if comparison_result and comparison_result.summary:
            answer_text += f"\n\n## 政策比较\n{comparison_result.summary}"

        return FinalAnswer(
            query_id=user_query.id,
            answer=answer_text,
            sources=source_docs,
            confidence=generated_answer.confidence,
            verification_passed=verification_result.get("passed", True) if verification_result else generated_answer.confidence > 0.7,
            fact_check=verification_result.get("fact_check") if verification_result else None,
            consistency_check=verification_result.get("consistency_check") if verification_result else None,
            metadata={
                "retrieved_count": len(retrieval_result.documents),
                "analyzed_count": len(analyses),
                "used_sources": len(source_docs),
                "session_id": user_query.session_id,
                "intent": query_analysis.intent.value,
                "has_comparison": comparison_result is not None
            }
        )

    def _create_no_policy_response(self, query: UserQuery) -> FinalAnswer:
        """创建无政策响应"""
        return FinalAnswer(
            query_id=query.id,
            answer="抱歉，我没有找到与您的问题相关的政策信息。建议您：\n\n1. 尝试使用不同的关键词\n2. 咨询相关部门获取最新政策\n3. 查看政府官方网站",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"reason": "no_documents_found"}
        )

    def _create_error_response(self, query: UserQuery, error: str) -> FinalAnswer:
        """创建错误响应"""
        return FinalAnswer(
            query_id=query.id,
            answer=f"处理您的问题时遇到了错误：{error}\n\n请稍后重试或联系系统管理员。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"error": error}
        )

    async def load_documents(self, document_paths: List[str]):
        """加载文档到知识库"""
        self.logger.info(f"Loading documents from {len(document_paths)} paths...")

        documents = await self.data_loader.load_and_initialize(force_reload=True)

        if documents:
            self.data_loaded = True
            # 更新向量检索器
            if AgentType.POLICY_RETRIEVER in self.agents:
                await self.agents[AgentType.POLICY_RETRIEVER].initialize()

        return documents

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        return self.active_sessions.get(session_id)

    def get_workflow_state(self, session_id: str) -> Optional[Dict]:
        """获取工作流状态"""
        return self.workflow_state.get(session_id)

    def get_agent_metrics(self) -> Dict[str, Any]:
        """获取所有agent的指标"""
        metrics = {}
        for agent_type, agent in self.agents.items():
            if hasattr(agent, 'get_metrics'):
                if hasattr(agent_type, 'value'):
                    metrics[agent_type.value] = agent.get_metrics()
                else:
                    metrics[str(agent_type)] = agent.get_metrics()
        return metrics

    async def shutdown(self):
        """关闭编排器和所有agents"""
        self.logger.info("Shutting down enhanced orchestrator...")

        # 停止所有agents
        for agent in self.agents.values():
            if hasattr(agent, 'stop'):
                await agent.stop()

        # 停止runtime
        self.runtime.stop()

        self.logger.info("Enhanced orchestrator shutdown complete")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.shutdown()
