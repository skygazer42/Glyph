"""Application-level schemas."""

from .db_connection import DBConnectionCreate, DBConnectionUpdate
from .schema_table import SchemaTableCreate, SchemaTableUpdate
from .schema_column import SchemaColumnCreate, SchemaColumnUpdate
from .schema_relationship import SchemaRelationshipCreate, SchemaRelationshipUpdate
from .value_mapping import ValueMappingCreate, ValueMappingUpdate
from .chat_history import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatHistorySnapshotCreate,
)
from .text2sql import (
    QueryMessage,
    ResponseMessage,
    SchemaContextMessage,
    AnalysisMessage,
    SqlMessage,
    SqlExplanationMessage,
    SqlResultMessage,
    Text2SQLResponse,
)
from .query import QueryRequest, QueryResponse

__all__ = [
    "DBConnectionCreate",
    "DBConnectionUpdate",
    "SchemaTableCreate",
    "SchemaTableUpdate",
    "SchemaColumnCreate",
    "SchemaColumnUpdate",
    "SchemaRelationshipCreate",
    "SchemaRelationshipUpdate",
    "ValueMappingCreate",
    "ValueMappingUpdate",
    "ChatSessionCreate",
    "ChatSessionUpdate",
    "ChatMessageCreate",
    "ChatMessageUpdate",
    "ChatHistorySnapshotCreate",
    "QueryMessage",
    "ResponseMessage",
    "SchemaContextMessage",
    "AnalysisMessage",
    "SqlMessage",
    "SqlExplanationMessage",
    "SqlResultMessage",
    "Text2SQLResponse",
    "QueryRequest",
    "QueryResponse",
]
