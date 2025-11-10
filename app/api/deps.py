"""
API 依赖注入
提供可复用的依赖项
"""

from typing import Optional
from fastapi import HTTPException

from app.agents.dsl_generator.dsl_extractor import DSLExtractor
from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.document_parser import DocumentParser
from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.agents.service import AgentService
from app.knowledge.milvus import MilvusStore
from app.models.llms import model_client


# ==================== 模块实例（全局单例） ====================

# DSL 相关
_dsl_generator: Optional[DSLGenerator] = None
_dsl_extractor: Optional[DSLExtractor] = None
_doc_parser: Optional[DocumentParser] = None
_policy_engine: Optional[PolicyEngine] = None

# 知识库
_milvus_store: Optional[MilvusStore] = None

# Agent Service
_agent_service: Optional[AgentService] = None


# ==================== DSL 相关依赖 ====================

def get_dsl_generator() -> DSLGenerator:
    """获取 DSL 生成器实例"""
    global _dsl_generator
    if _dsl_generator is None:
        _dsl_generator = DSLGenerator(output_dir="rules", template_dir="templates")
    return _dsl_generator


def get_dsl_extractor() -> DSLExtractor:
    """获取 DSL 提取器实例"""
    global _dsl_extractor
    if _dsl_extractor is None:
        _dsl_extractor = DSLExtractor(use_project_config=True)
    return _dsl_extractor


def get_document_parser() -> DocumentParser:
    """获取文档解析器实例"""
    global _doc_parser
    if _doc_parser is None:
        _doc_parser = DocumentParser()
    return _doc_parser


def get_policy_engine() -> PolicyEngine:
    """获取规则引擎实例"""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine(rule_dir="rules")
    return _policy_engine


# ==================== 知识库相关依赖 ====================

def get_milvus_store() -> MilvusStore:
    """获取 Milvus 存储实例"""
    global _milvus_store
    if _milvus_store is None:
        try:
            _milvus_store = MilvusStore()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到Milvus: {str(e)}"
            )
    return _milvus_store


# ==================== Agent 相关依赖 ====================

def get_model_client():
    """获取模型客户端实例"""
    return model_client


async def get_agent_service() -> AgentService:
    """获取统一 AgentService 实例"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
        await _agent_service.initialize()
    return _agent_service


# ==================== 会话管理依赖 ====================

from app.agents.framework.common.session_manager import SessionManager
from app.agents.service.chat_history_store import ChatHistoryStore

_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        history_store = ChatHistoryStore()
        _session_manager = SessionManager(history_store=history_store)
    return _session_manager
