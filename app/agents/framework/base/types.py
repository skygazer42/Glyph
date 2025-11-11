"""
Type definitions for the policy QA system.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class AgentTypes(Enum):
    """Agent type enumeration."""
    QUESTION_UNDERSTANDER = "question_understander"
    POLICY_RETRIEVER = "policy_retriever"
    POLICY_ANALYZER = "policy_analyzer"
    ANSWER_GENERATOR = "answer_generator"
    ANSWER_VERIFIER = "answer_verifier"
    COORDINATOR = "coordinator"


class TopicTypes(Enum):
    """Communication topic types."""
    QUESTION_ANALYSIS = "question_analysis"
    POLICY_RETRIEVAL = "policy_retrieval"
    POLICY_ANALYSIS = "policy_analysis"
    ANSWER_GENERATION = "answer_generation"
    ANSWER_VERIFICATION = "answer_verification"
    COORDINATION = "coordination"
    ERROR = "error"


class MessageTypes(Enum):
    """Message type enumeration."""
    USER_QUESTION = "user_question"
    ANALYSIS_RESULT = "analysis_result"
    RETRIEVAL_RESULT = "retrieval_result"
    ANALYSIS_REPORT = "analysis_report"
    GENERATED_ANSWER = "generated_answer"
    VERIFICATION_REPORT = "verification_report"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    DATA = "data"  # 用于框架内部的通用数据传递


class RetrievalMethod(Enum):
    """Retrieval method types."""
    VECTOR_SEARCH = "vector_search"
    GRAPH_SEARCH = "graph_search"
    HYBRID = "hybrid"


@dataclass
class PolicyDocument:
    """Policy document data structure."""
    id: str
    title: str
    content: str
    source: str
    doc_type: str
    publish_date: Optional[str] = None
    relevant_departments: List[str] = None
    policy_type: str = ""
    embedding: Optional[List[float]] = None


@dataclass
class QueryResult:
    """Query result data structure."""
    query: str
    documents: List[PolicyDocument]
    scores: List[float]
    method: RetrievalMethod
    metadata: Dict[str, Any] = None


@dataclass
class AnalysisReport:
    """Analysis report data structure."""
    original_query: str
    intent: str
    entities: List[str]
    keywords: List[str]
    policy_types: List[str]
    time_constraints: Optional[str] = None
    location_constraints: Optional[str] = None
    confidence: float = 0.0


@dataclass
class GeneratedAnswer:
    """Generated answer data structure."""
    answer: str
    sources: List[str]
    confidence: float
    reasoning: str
    additional_info: List[str] = None


@dataclass
class VerificationReport:
    """Verification report data structure."""
    is_accurate: bool
    is_complete: bool
    confidence: float
    issues: List[str]
    suggestions: List[str]
    final_score: float
