"""Shared request/response schemas for API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class QueryResponse(BaseModel):
    sql: str = ""
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


__all__ = ["QueryRequest", "QueryResponse"]
