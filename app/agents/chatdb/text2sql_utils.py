"""
Text2SQL工具模块
提供查询分析、表结构检索、SQL处理等工具函数
"""
import json
import logging
import os
import re
import sqlparse
from collections import OrderedDict
from typing import Dict, Any, List, Tuple
from sqlparse.exceptions import SQLParseError
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field, RootModel

from autogen_core.models import UserMessage
from app.core.llms import model_client
from app.persistence.crud.schema_metadata import (
    schema_column,
    schema_relationship,
    schema_table,
    value_mapping,
)
from .domain_zh_gov import (
    candidate_tables_from_query,
    domain_value_mappings_for_schema,
)
from .types import DEFAULT_DB_TYPE

logger = logging.getLogger(__name__)


class QueryAnalysis(BaseModel):
    """The stable JSON fields requested from the query-analysis model."""

    model_config = ConfigDict(strict=True, extra="ignore")

    entities: list[str]
    relationships: list[str]
    query_intent: str
    likely_aggregations: list[str]
    time_related: bool
    comparison_related: bool


class RankedTable(BaseModel):
    """One table ID and its score in the model's schema-ranking response."""

    model_config = ConfigDict(strict=True, extra="ignore")

    table_id: int
    relevance_score: float = Field(ge=0, le=10)
    reasoning: str


class TableRanking(RootModel[list[RankedTable]]):
    model_config = ConfigDict(strict=True)


class _LRUCache(OrderedDict):
    """简单的LRU缓存，避免查询分析缓存无限增长。"""

    def __init__(self, maxsize: int):
        super().__init__()
        if maxsize < 0:
            raise ValueError("Query cache size must be nonnegative")
        self.maxsize = maxsize

    def get(self, key, default=None):
        if key in self:
            self.move_to_end(key)
            return super().get(key)
        return default

    def put(self, key, value) -> None:
        if self.maxsize == 0:
            return
        super().__setitem__(key, value)
        self.move_to_end(key)
        if len(self) > self.maxsize:
            self.popitem(last=False)


QUERY_ANALYSIS_CACHE_SIZE = int(os.getenv("TEXT2SQL_QUERY_CACHE_SIZE", "256"))
query_analysis_cache = _LRUCache(QUERY_ANALYSIS_CACHE_SIZE)


async def analyze_query_with_llm(query: str) -> Dict[str, Any]:
    """
    使用LLM分析自然语言查询，提取关键实体和意图
    返回包含实体、关系和查询意图的结构化分析
    """
    cached = query_analysis_cache.get(query)
    if cached is not None:
        return cached

    try:
        # 为LLM准备提示
        prompt = f"""
        你是一名数据库专家，帮助分析自然语言查询以找到相关的数据库表和列。
        请分析以下查询并提取关键信息：

        查询: "{query}"

        请以以下JSON格式提供分析：
        {{
            "entities": [查询中提到或暗示的实体名称列表],
            "relationships": [查询中暗示的实体间关系列表],
            "query_intent": "查询试图找到什么的简要描述",
            "likely_aggregations": [可能需要的聚合操作列表，如count、sum、avg],
            "time_related": 布尔值，表示查询是否涉及时间/日期过滤或分组,
            "comparison_related": 布尔值，表示查询是否涉及值比较
        }}
        """

        # 调用LLM
        response = await model_client.create([UserMessage(content=prompt, source="user")])
        response_text = response.content
        if not isinstance(response_text, str):
            raise TypeError("Query analysis requires a text model response")

        # 提取并解析JSON响应
        json_match = re.search(r'\{[\s\S]*}', response_text)
        if json_match:
            json_str = json_match.group(0)
            analysis = QueryAnalysis.model_validate_json(json_str).model_dump()
        else:
            raise ValueError("Query analysis response did not contain JSON")

        query_analysis_cache.put(query, analysis)
        return analysis
    except Exception as exc:
        # 如果发生任何错误，回退到关键词提取
        logger.warning("Query analysis failed; using keyword analysis: %s", exc, exc_info=True)
        analysis = _create_fallback_analysis(query)
        query_analysis_cache.put(query, analysis)
        return analysis


def _create_fallback_analysis(query: str) -> Dict[str, Any]:
    """创建回退分析结果"""
    return {
        "entities": extract_keywords(query),
        "relationships": [],
        "query_intent": query,
        "likely_aggregations": [],
        "time_related": False,
        "comparison_related": False
    }


def extract_keywords(query: str) -> List[str]:
    """
    使用正则表达式从查询中提取关键词（回退方法）
    """
    keywords = re.findall(r'\b\w+\b', query.lower())
    return [keyword for keyword in keywords if len(keyword) > 2 and keyword not in {
        'the', 'and', 'for', 'from', 'where', 'what', 'which', 'when', 'who',
        'how', 'many', 'much', 'with', 'that', 'this', 'these', 'those',
        '什么', '哪个', '哪些', '什么时候', '谁', '怎么', '多少', '和', '的', '是'
    }]


async def find_relevant_tables_semantic(query: str, query_analysis: Dict[str, Any],
                                       all_tables: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    """
    使用LLM进行语义匹配找到相关表
    返回(table_id, relevance_score)元组列表
    """
    try:
        # 为LLM准备表信息
        tables_info = "\n".join([
            f"表ID: {table['id']} - 名称: {table['name']} - 描述: {table['description'] or '无描述'}"
            for table in all_tables
        ])

        # 准备提示
        prompt = f"""
        你是一名数据库专家，帮助为自然语言查询找到相关表。

        查询: "{query}"

        查询分析: {json.dumps(query_analysis, ensure_ascii=False)}

        可用表:
        {tables_info}

        请按相关性对表进行排序，返回包含table_id和relevance_score(0-10)的JSON数组。
        table_id必须是每个表描述开头显示的整数ID（例如"表ID: 123"）。
        只包含实际相关的表（分数>3）。格式：
        [
            {{
                "table_id": 123, // 表的整数ID，不是名称
                "relevance_score": 8.5, // 0-10之间的浮点数
                "reasoning": "为什么这个表相关的简要解释"
            }},
            ...
        ]
        """

        # 调用LLM
        response = await model_client.create([UserMessage(content=prompt, source="user")])
        response_text = response.content
        if not isinstance(response_text, str):
            raise TypeError("Schema ranking requires a text model response")

        # 提取并解析JSON响应
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
            ranking = TableRanking.model_validate_json(json_str)
            available_ids = {table["id"] for table in all_tables}
            if any(table.table_id not in available_ids for table in ranking.root):
                raise ValueError("Schema ranking referenced a table outside the available schema")
            valid_tables = [
                (table.table_id, table.relevance_score)
                for table in ranking.root if table.relevance_score > 3
            ]

            domain_candidates = set(candidate_tables_from_query(query))
            boost_ids = {int(table["id"]) for table in all_tables if table["name"] in domain_candidates}
            existing = {table_id for table_id, _ in valid_tables}
            valid_tables = [(table_id, max(score, 8.5) if table_id in boost_ids else score)
                            for table_id, score in valid_tables]
            valid_tables.extend((table_id, 8.5) for table_id in boost_ids if table_id not in existing)

            return sorted(valid_tables, key=lambda table_score: table_score[1], reverse=True)
        else:
            raise ValueError("Schema ranking response did not contain a JSON array")
    except Exception as exc:
        logger.warning("Semantic schema ranking failed; using keyword matching: %s", exc, exc_info=True)
        return basic_table_matching(query, all_tables)


def basic_table_matching(query: str, all_tables: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    """
    基本关键词匹配回退方法
    """
    keywords = extract_keywords(query)
    # 领域候选表（基于中文关键词）
    domain_candidates = set(candidate_tables_from_query(query))
    relevant_tables = []

    for table in all_tables:
        score = 0
        table_name = table["name"].lower()
        table_description = table["description"]

        # 强力加权：领域候选命中
        if table["name"] in domain_candidates:
            score += 10

        for keyword in keywords:
            if keyword in table_name:
                score += 5  # 名称匹配更高分
            elif table_description and keyword in table_description.lower():
                score += 3  # 描述匹配较低分

        if score > 0:
            relevant_tables.append((table["id"], min(score, 10)))  # 最高10分

    return sorted(relevant_tables, key=lambda table_score: table_score[1], reverse=True)


def format_schema_for_prompt(schema_context: Dict[str, Any]) -> str:
    """
    将表结构上下文格式化为LLM提示的字符串
    """
    tables = schema_context["tables"]
    columns = schema_context["columns"]
    relationships = schema_context["relationships"]

    # 按表分组列
    columns_by_table: Dict[str, List[Dict[str, Any]]] = {}
    for column in columns:
        table_name = column["table_name"]
        if table_name not in columns_by_table:
            columns_by_table[table_name] = []
        columns_by_table[table_name].append(column)

    # 格式化表结构
    schema_str = ""

    for table in tables:
        table_name = table["name"]
        table_description = f" ({table['description']})" if table["description"] else ""

        schema_str += f"-- 表: {table_name}{table_description}\n"
        schema_str += "-- 列:\n"

        if table_name in columns_by_table:
            for column in columns_by_table[table_name]:
                column_name = column["name"]
                column_type = column["type"]
                column_description = f" ({column['description']})" if column["description"] else ""
                primary_key_flag = " PK" if column["is_primary_key"] else ""
                foreign_key_flag = " FK" if column["is_foreign_key"] else ""

                schema_str += f"--   {column_name} {column_type}{primary_key_flag}{foreign_key_flag}{column_description}\n"

        schema_str += "\n"

    if relationships:
        schema_str += "-- 关系:\n"
        for relationship in relationships:
            relationship_type = f" ({relationship['relationship_type']})" if relationship["relationship_type"] else ""
            schema_str += f"-- {relationship['source_table']}.{relationship['source_column']} -> {relationship['target_table']}.{relationship['target_column']}{relationship_type}\n"

    return schema_str


def get_value_mappings(db: Session, schema_context: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    获取表结构上下文中列的值映射
    """
    mappings: Dict[str, Dict[str, str]] = {}

    for column in schema_context["columns"]:
        column_id = column["id"]
        column_mappings = value_mapping.get_by_column(db=db, column_id=column_id)

        if column_mappings:
            qualified_column = f"{column['table_name']}.{column['name']}"
            mappings[qualified_column] = {mapping.nl_term: mapping.db_value for mapping in column_mappings}

    # Explicit persisted mappings take precedence over domain synonyms.
    for key, values in domain_value_mappings_for_schema(schema_context).items():
        mappings[key] = {**values, **mappings.get(key, {})}

    return mappings


def process_sql_with_value_mappings(
    sql: str,
    value_mappings: Dict[str, Dict[str, str]],
    *,
    db_type: str = DEFAULT_DB_TYPE,
) -> str:
    """
    替换自然语言术语，并只为 MySQL 修正支持的 text 类型转换。
    """
    if not value_mappings:
        return sql

    # Match literal schema identifiers/terms and build replacement text without
    # regex backreferences (a numeric DB value must not become group 10).
    for column, mappings in value_mappings.items():
        table_name, column_name = column.rsplit(".", 1)
        identifier = rf"(?<![\w.])(?:{re.escape(table_name)}\.)?{re.escape(column_name)}"
        for nl_term, db_value in mappings.items():
            pattern = rf"({identifier}\s*(=|LIKE)\s*)(['\"])(%?{re.escape(nl_term)}%?)\3"

            def replace_value(match: re.Match[str], replacement: str = db_value) -> str:
                quote = match.group(3)
                escaped_value = replacement.replace(quote, quote * 2)
                if match.group(2).upper() == "LIKE":
                    escaped_value = f"%{escaped_value}%"
                return f"{match.group(1)}{quote}{escaped_value}{quote}"

            sql = re.sub(pattern, replace_value, sql, flags=re.IGNORECASE)

    if db_type.lower() != "mysql":
        return sql

    # 仅为 MySQL 修正 LLM 生成的 PostgreSQL 风格类型转换语法。
    # 1) 将 "alias.metadata::text" 或 "metadata::text" 替换为 CAST(... AS CHAR)
    def replace_text_cast(match: re.Match) -> str:
        column_reference = match.group(1)
        return f"CAST({column_reference} AS CHAR)"

    # 匹配类似 "pd.metadata::text" 或 "metadata::text"
    sql = re.sub(r"\b([\w]+\.[Mm][Ee][Tt][Aa][Dd][Aa][Tt][Aa])::text\b", replace_text_cast, sql)
    sql = re.sub(r"\b([Mm][Ee][Tt][Aa][Dd][Aa][Tt][Aa])::text\b", replace_text_cast, sql)

    # 2) 其他带表名或别名的列，如 "t.name::text" -> "CAST(t.name AS CHAR)"。
    sql = re.sub(r"\b([\w]+\.[\w]+)::text\b", replace_text_cast, sql)

    return sql


def validate_sql(sql: str) -> bool:
    """
    检查单条 SELECT 查询边界；具体语法由数据库验证。
    """
    try:
        # 从环境变量读取安全开关（默认禁止 UNION）
        allow_union = os.getenv("TEXT2SQL__ALLOW_UNION", "false").lower() == "true"

        parsed = sqlparse.parse(sql)
        if len(parsed) != 1:
            return False

        # 检查是否是SELECT语句（为了安全）
        statement = parsed[0]
        if statement.get_type().upper() != 'SELECT':
            return False

        # 额外安全检查：禁止危险关键字/多语句/UNION
        if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|ATTACH|DETACH|VACUUM|REINDEX|PRAGMA|REPLACE|INTO)\b",
                     sql, flags=re.IGNORECASE):
            return False

        # 禁止多语句（末尾允许一个分号）
        body = sql.strip()
        if ';' in body[:-1]:
            return False

        if not allow_union and re.search(r"\bUNION\b", sql, flags=re.IGNORECASE):
            return False

        return True
    except SQLParseError:
        return False


def extract_sql_from_llm_response(response: str) -> str:
    """
    从LLM响应中提取SQL查询
    """
    # 查找SQL代码块
    sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if sql_match:
        return sql_match.group(1).strip()

    # 查找任何代码块
    code_match = re.search(r'```(.*?)```', response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # 如果没有代码块，尝试找到类似SQL的内容
    lines = response.split('\n')
    sql_lines = []
    in_sql = False

    for line in lines:
        if line.strip().upper().startswith('SELECT'):
            in_sql = True

        if in_sql:
            sql_lines.append(line)

            if ';' in line:
                break

    if sql_lines:
        return '\n'.join(sql_lines)

    # 如果都失败了，返回整个响应
    return response


def snapshot_schema(db: Session, connection_id: int) -> Dict[str, Any]:
    """Read metadata into plain values while the caller owns the Session."""
    tables = schema_table.get_by_connection(db=db, connection_id=connection_id)
    table_names = {table.id: table.table_name for table in tables}
    columns = schema_column.get_by_table_ids(db=db, table_ids=list(table_names)) if tables else []
    column_names = {column.id: column.column_name for column in columns}
    relationships = schema_relationship.get_by_connection(db=db, connection_id=connection_id) if tables else []
    return {
        "tables": [{"id": table.id, "name": table.table_name, "description": table.description} for table in tables],
        "columns": [{"id": column.id, "name": column.column_name, "type": column.data_type,
                     "description": column.description, "is_primary_key": column.is_primary_key,
                     "is_foreign_key": column.is_foreign_key, "table_id": column.table_id,
                     "table_name": table_names[column.table_id]} for column in columns],
        "relationships": [{"id": rel.id, "source_table": table_names[rel.source_table_id],
                           "source_column": column_names[rel.source_column_id],
                           "target_table": table_names[rel.target_table_id],
                           "target_column": column_names[rel.target_column_id],
                           "relationship_type": rel.relationship_type}
                          for rel in relationships
                          if rel.source_table_id in table_names and rel.target_table_id in table_names
                          and rel.source_column_id in column_names and rel.target_column_id in column_names],
    }


async def select_relevant_schema(snapshot: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Rank an already detached metadata snapshot on the model client's loop."""
    tables = snapshot["tables"]
    if not tables:
        return snapshot
    analysis = await analyze_query_with_llm(query)
    ranked = await find_relevant_tables_semantic(query, analysis, tables)
    table_ids = [table_id for table_id, _ in ranked] if ranked else [table["id"] for table in tables]
    max_tables = int(os.getenv("TEXT2SQL_MAX_TABLES", "8"))
    if max_tables <= 0:
        raise ValueError("TEXT2SQL_MAX_TABLES must be greater than zero")
    selected_ids = set(table_ids[:max_tables])
    selected_tables = [table for table in tables if table["id"] in selected_ids]
    names = {table["name"] for table in selected_tables}
    return {
        "tables": selected_tables,
        "columns": [column for column in snapshot["columns"] if column["table_id"] in selected_ids],
        "relationships": [rel for rel in snapshot["relationships"]
                          if rel["source_table"] in names and rel["target_table"] in names],
    }
