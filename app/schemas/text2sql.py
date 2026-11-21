"""Pydantic schemas shared by the Text2SQL pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryMessage(BaseModel):
    """携带自然语言查询和可选连接标识的处理消息。"""

    query: str
    connection_id: Optional[int] = Field(default=None, description="连接ID")


class ResponseMessage(BaseModel):
    """描述流水线响应片段及可选结果和元数据。"""

    source: str
    content: str
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class SchemaContextMessage(QueryMessage):
    """为查询附加已检索的表结构及值映射上下文。"""

    schema_context: Dict[str, Any] = Field(default_factory=dict)
    mappings_str: str = ""


class AnalysisMessage(SchemaContextMessage):
    """携带分析文本与历史记忆的查询处理消息。"""

    role: str = "assistant"
    analysis: str
    memory_content: List[Dict[str, Any]] = Field(default_factory=list)


class SqlMessage(QueryMessage):
    """携带待执行或展示 SQL 的查询消息。"""

    sql: str


class SqlExplanationMessage(SqlMessage):
    """为 SQL 消息补充解释文本。"""

    explanation: str


class SqlResultMessage(SqlExplanationMessage):
    """携带 SQL 解释、结果行及可选执行错误。"""

    results: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class SQLQueryResult(BaseModel):
    """Result of the service query, including an explicit execution error."""

    sql: str = ""
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class Text2SQLResponse(BaseModel):
    """向调用方返回 SQL、解释、结果和可选可视化配置。"""

    sql: str
    explanation: Optional[str] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
    visualization_type: Optional[str] = None
    visualization_config: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "QueryMessage",
    "ResponseMessage",
    "SchemaContextMessage",
    "AnalysisMessage",
    "SqlMessage",
    "SqlExplanationMessage",
    "SqlResultMessage",
    "SQLQueryResult",
    "Text2SQLResponse",
]
