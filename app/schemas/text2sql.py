"""Pydantic schemas shared by the Text2SQL pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryMessage(BaseModel):
    query: str
    connection_id: Optional[int] = Field(default=None, description="连接ID")


class ResponseMessage(BaseModel):
    source: str
    content: str
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class SchemaContextMessage(QueryMessage):
    schema_context: Dict[str, Any] = Field(default_factory=dict)
    mappings_str: str = ""


class AnalysisMessage(SchemaContextMessage):
    role: str = "assistant"
    analysis: str
    memory_content: List[Dict[str, Any]] = Field(default_factory=list)


class SqlMessage(QueryMessage):
    sql: str


class SqlExplanationMessage(SqlMessage):
    explanation: str


class SqlResultMessage(SqlExplanationMessage):
    results: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class Text2SQLResponse(BaseModel):
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
    "Text2SQLResponse",
]
