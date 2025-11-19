"""
Text2SQL工具模块
提供查询分析、表结构检索、SQL处理等工具函数
"""
import json
import os
import re
import sqlparse
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session

from autogen_core.models import UserMessage
from app.core.config import settings
from app.core.llms import model_client
from app.persistence import crud
from .domain_zh_gov import (
    candidate_tables_from_query,
    domain_value_mappings_for_schema,
)


class _LRUCache(OrderedDict):
    """简单的LRU缓存，避免查询分析缓存无限增长。"""

    def __init__(self, maxsize: int):
        super().__init__()
        self.maxsize = max(1, maxsize)

    def get(self, key, default=None):
        if key in self:
            self.move_to_end(key)
            return super().get(key)
        return default

    def put(self, key, value) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        if len(self) > self.maxsize:
            self.popitem(last=False)


QUERY_ANALYSIS_CACHE_SIZE = int(os.getenv("TEXT2SQL_QUERY_CACHE_SIZE", settings.performance.cache_ttl if settings.performance.cache_ttl else 256))
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

        # 提取并解析JSON响应
        json_match = re.search(r'\{[\s\S]*}', response_text)
        if json_match:
            json_str = json_match.group(0)
            analysis = json.loads(json_str)

            # 验证必需字段
            if not all(k in analysis for k in ["entities", "relationships", "query_intent"]):
                analysis = _create_fallback_analysis(query)
        else:
            analysis = _create_fallback_analysis(query)

        query_analysis_cache.put(query, analysis)
        return analysis
    except Exception as e:
        # 如果发生任何错误，回退到关键词提取
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
    return [k for k in keywords if len(k) > 2 and k not in {
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
            f"表ID: {t['id']} - 名称: {t['name']} - 描述: {t['description'] or '无描述'}"
            for t in all_tables
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

        # 提取并解析JSON响应
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
            ranked_tables = json.loads(json_str)

            # 确保每个表都有所需字段且table_id是整数
            valid_tables: List[Tuple[int, float]] = []
            for t in ranked_tables:
                if "table_id" in t and "relevance_score" in t:
                    if t["relevance_score"] > 3:
                        table_id = t["table_id"]
                        if not isinstance(table_id, int):
                            try:
                                table_id = int(table_id)
                            except (ValueError, TypeError):
                                continue
                        valid_tables.append((table_id, t["relevance_score"]))

            # 领域提示加权：若中文关键词提示某些表，直接提升其分数
            try:
                domain_candidates = set(candidate_tables_from_query(query))
                name_to_id = {t["name"]: int(t["id"]) for t in all_tables if isinstance(t.get("id"), (int,)) or str(t.get("id", "")).isdigit()}
                boost_ids = {name_to_id.get(n) for n in domain_candidates if name_to_id.get(n) is not None}
                if boost_ids:
                    existing = {tid for tid, _ in valid_tables}
                    # boost up existing; add new with base score 8
                    boosted = []
                    for tid, sc in valid_tables:
                        if tid in boost_ids:
                            sc = max(sc, 8.5)
                        boosted.append((tid, sc))
                    for bid in boost_ids:
                        if bid not in existing:
                            boosted.append((bid, 8.5))
                    valid_tables = boosted
            except Exception:
                pass

            return valid_tables
        else:
            return basic_table_matching(query, all_tables)
    except Exception as e:
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
        table_desc = (table["description"] or "").lower()

        # 强力加权：领域候选命中
        if table["name"] in domain_candidates:
            score += 10

        for keyword in keywords:
            if keyword in table_name:
                score += 5  # 名称匹配更高分
            elif keyword in table_desc:
                score += 3  # 描述匹配较低分

        if score > 0:
            relevant_tables.append((table["id"], min(score, 10)))  # 最高10分

    return sorted(relevant_tables, key=lambda x: x[1], reverse=True)


async def filter_expanded_tables_with_llm(query: str, query_analysis: Dict[str, Any],
                                        expanded_tables: List[Tuple[int, str, str]],
                                        relevance_scores: Dict[int, float]) -> Set[Tuple[int, str, str]]:
    """
    使用LLM根据实际相关性过滤扩展表
    """
    try:
        # 准备扩展表信息
        tables_info = "\n".join([
            f"表ID: {t[0]}, 名称: {t[1]}, 描述: {t[2] or '无描述'}, 分数: {relevance_scores.get(t[0], 0)}"
            for t in expanded_tables
        ])

        # 准备提示
        prompt = f"""
        你是一名数据库专家，帮助确定相关表是否真正与查询相关。

        查询: "{query}"

        查询分析: {json.dumps(query_analysis, ensure_ascii=False)}

        以下表是通过关系连接找到的，但我们需要确定它们是否真正相关：
        {tables_info}

        请返回实际与回答查询相关的表ID的JSON数组。
        只包含回答查询所需的表。格式：
        [
            {{
                "table_id": table_id,
                "include": true/false,
                "reasoning": "为什么应该包含或排除此表的简要解释"
            }},
            ...
        ]
        """

        # 调用LLM
        response = await model_client.create([UserMessage(content=prompt, source="user")])
        response_text = response.content

        # 提取并解析JSON响应
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
            filtered_tables = json.loads(json_str)

            # 获取应包含的表的ID
            include_ids = [t["table_id"] for t in filtered_tables if t.get("include", False)]

            # 返回应包含的原始表元组
            return set(t for t in expanded_tables if t[0] in include_ids)
        else:
            # 如果解析失败，包含所有扩展表
            return set(expanded_tables)
    except Exception as e:
        # 如果发生任何错误，包含所有扩展表
        return set(expanded_tables)


def format_schema_for_prompt(schema_context: Dict[str, Any]) -> str:
    """
    将表结构上下文格式化为LLM提示的字符串
    """
    tables = schema_context["tables"]
    columns = schema_context["columns"]
    relationships = schema_context["relationships"]

    # 按表分组列
    columns_by_table = {}
    for column in columns:
        table_name = column["table_name"]
        if table_name not in columns_by_table:
            columns_by_table[table_name] = []
        columns_by_table[table_name].append(column)

    # 格式化表结构
    schema_str = ""

    for table in tables:
        table_name = table["name"]
        table_desc = f" ({table['description']})" if table["description"] else ""

        schema_str += f"-- 表: {table_name}{table_desc}\n"
        schema_str += "-- 列:\n"

        if table_name in columns_by_table:
            for column in columns_by_table[table_name]:
                col_name = column["name"]
                col_type = column["type"]
                col_desc = f" ({column['description']})" if column["description"] else ""
                pk_flag = " PK" if column["is_primary_key"] else ""
                fk_flag = " FK" if column["is_foreign_key"] else ""

                schema_str += f"--   {col_name} {col_type}{pk_flag}{fk_flag}{col_desc}\n"

        schema_str += "\n"

    if relationships:
        schema_str += "-- 关系:\n"
        for rel in relationships:
            rel_type = f" ({rel['relationship_type']})" if rel["relationship_type"] else ""
            schema_str += f"-- {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}{rel_type}\n"

    return schema_str


def get_value_mappings(db: Session, schema_context: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    获取表结构上下文中列的值映射
    """
    mappings: Dict[str, Dict[str, str]] = {}

    for column in schema_context["columns"]:
        column_id = column["id"]
        column_mappings = crud.value_mapping.get_by_column(db=db, column_id=column_id)

        if column_mappings:
            table_col = f"{column['table_name']}.{column['name']}"
            mappings[table_col] = {m.nl_term: m.db_value for m in column_mappings}

    # 合并领域通用映射（如 city/vehicle_type/benefit_type 等中文→规范值）
    try:
        domain_maps = domain_value_mappings_for_schema(schema_context)
        for key, value in domain_maps.items():
            if key in mappings:
                # 显式配置优先，领域映射补充
                merged = dict(value)
                merged.update(mappings[key])
                mappings[key] = merged
            else:
                mappings[key] = value
    except Exception:
        pass

    return mappings


def process_sql_with_value_mappings(sql: str, value_mappings: Dict[str, Dict[str, str]]) -> str:
    """
    处理SQL查询，将自然语言术语替换为数据库值
    """
    if not value_mappings:
        return sql

    # 这是一个简化的方法 - 更健壮的实现会使用适当的SQL解析器
    for column, mappings in value_mappings.items():
        table, col = column.split('.')

        # 查找类似"table.column = 'value'"或"column = 'value'"的模式
        for nl_term, db_value in mappings.items():
            # 尝试匹配带表名的模式
            pattern1 = rf"({table}\.{col}\s*=\s*['\"])({nl_term})(['\"])"
            sql = re.sub(pattern1, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 尝试匹配不带表名的模式
            pattern2 = rf"({col}\s*=\s*['\"])({nl_term})(['\"])"
            sql = re.sub(pattern2, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 也处理LIKE模式
            pattern3 = rf"({table}\.{col}\s+LIKE\s+['\"])%?({nl_term})%?(['\"])"
            sql = re.sub(pattern3, f"\\1%{db_value}%\\3", sql, flags=re.IGNORECASE)

            pattern4 = rf"({col}\s+LIKE\s+['\"])%?({nl_term})%?(['\"])"
            sql = re.sub(pattern4, f"\\1%{db_value}%\\3", sql, flags=re.IGNORECASE)

    # 额外一步：修正 LLM 生成的 PostgreSQL 风格 JSON/类型转换语法为 MySQL 兼容形式
    # 1) 将 "alias.metadata::text" 或 "metadata::text" 替换为 CAST(... AS CHAR)
    def _replace_metadata_cast(match: re.Match) -> str:
        col_ref = match.group(1)
        return f"CAST({col_ref} AS CHAR)"

    # 匹配类似 "pd.metadata::text" 或 "metadata::text"
    sql = re.sub(r"\b([\w]+\.[Mm][Ee][Tt][Aa][Dd][Aa][Tt][Aa])::text\b", _replace_metadata_cast, sql)
    sql = re.sub(r"\b([Mm][Ee][Tt][Aa][Dd][Aa][Tt][Aa])::text\b", _replace_metadata_cast, sql)

    # 2) 通用的 "::text" 类型转换，退化为直接使用原列
    # 例如 "some_column::text" -> "CAST(some_column AS CHAR)"
    sql = re.sub(r"\b([\w]+\.[\w]+)::text\b", _replace_metadata_cast, sql)

    return sql


def validate_sql(sql: str) -> bool:
    """
    验证SQL语法
    """
    try:
        # 从环境变量读取安全开关（默认禁止 UNION）
        allow_union = os.getenv("TEXT2SQL__ALLOW_UNION", "false").lower() == "true"

        parsed = sqlparse.parse(sql)
        if not parsed:
            return False

        # 检查是否是SELECT语句（为了安全）
        stmt = parsed[0]
        if stmt.get_type().upper() != 'SELECT':
            return False

        # 额外安全检查：禁止危险关键字/多语句/UNION
        if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|ATTACH|DETACH|VACUUM|REINDEX|PRAGMA|REPLACE)\b",
                     sql, flags=re.IGNORECASE):
            return False

        # 禁止多语句（末尾允许一个分号）
        body = sql.strip()
        if ';' in body[:-1]:
            return False

        if not allow_union and re.search(r"\bUNION\b", sql, flags=re.IGNORECASE):
            return False

        return True
    except Exception:
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


async def retrieve_relevant_schema(db: Session, connection_id: int, query: str) -> Dict[str, Any]:
    """
    基于自然语言查询检索相关的表结构信息。

    企业化实现说明：
    - 不再依赖 Neo4j，全部基于 ORM 管理的 SchemaTable/SchemaColumn/SchemaRelationship 元数据；
    - 使用 LLM + 关键词匹配对所有表做排序，选出 Top-K 相关表；
    - 保留原有返回结构: {"tables": [...], "columns": [...], "relationships": [...]}
    """
    try:
        # 1. 使用 LLM 分析查询并提取关键实体和意图
        query_analysis = await analyze_query_with_llm(query)

        # 2. 从元数据表中获取所有表信息
        all_tables_from_db = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
        if not all_tables_from_db:
            return {"tables": [], "columns": [], "relationships": []}

        all_tables_for_llm = [
            {
                "id": table.id,
                "name": table.table_name,
                "description": table.description or "",
            }
            for table in all_tables_from_db
        ]

        # 3. 使用语义匹配 + 领域提示找到相关表
        ranked = await find_relevant_tables_semantic(query, query_analysis, all_tables_for_llm)
        # ranked: List[Tuple[table_id, score]]
        relevance_scores: Dict[int, float] = {tid: sc for tid, sc in ranked}

        if ranked:
            table_ids = [tid for tid, _ in ranked]
        else:
            # 回退：没有语义结果时，使用全部表（默认让 LLM 在Prompt里做过滤）
            table_ids = [t["id"] for t in all_tables_for_llm]

        # 限制最多表数，避免提示过长（可按需调整）
        max_tables = int(os.getenv("TEXT2SQL_MAX_TABLES", "8"))
        if len(table_ids) > max_tables:
            table_ids = table_ids[:max_tables]

        # 4. 构造 tables_list
        tables_list = [
            {
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
            }
            for t in all_tables_for_llm
            if t["id"] in table_ids
        ]

        # 5. 加载列信息
        table_name_lookup = {t["id"]: t["name"] for t in tables_list}
        columns_records = crud.schema_column.get_by_table_ids(db=db, table_ids=table_ids)
        columns_list = []
        for column in columns_records:
            columns_list.append(
                {
                    "id": column.id,
                    "name": column.column_name,
                    "type": column.data_type,
                    "description": column.description,
                    "is_primary_key": column.is_primary_key,
                    "is_foreign_key": column.is_foreign_key,
                    "table_id": column.table_id,
                    "table_name": table_name_lookup.get(column.table_id, ""),
                }
            )

        column_lookup = {col["id"]: col for col in columns_list}

        # 6. 加载表间关系（外键等）
        all_tables_count = len(all_tables_from_db)
        if len(tables_list) == all_tables_count:
            rel_records = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)
        else:
            rel_records = crud.schema_relationship.get_by_table_ids(db=db, table_ids=table_ids)

        relationships_list: List[Dict[str, Any]] = []
        for rel in rel_records:
            if rel.source_table_id not in table_ids or rel.target_table_id not in table_ids:
                if len(tables_list) != all_tables_count:
                    # 当只选择部分表时，仅保留完全落在子集内的关系
                    continue

            source_table_name = table_name_lookup.get(rel.source_table_id)
            target_table_name = table_name_lookup.get(rel.target_table_id)
            source_column = column_lookup.get(rel.source_column_id)
            target_column = column_lookup.get(rel.target_column_id)

            if source_table_name and target_table_name and source_column and target_column:
                relationships_list.append(
                    {
                        "id": rel.id,
                        "source_table": source_table_name,
                        "source_column": source_column["name"],
                        "target_table": target_table_name,
                        "target_column": target_column["name"],
                        "relationship_type": rel.relationship_type,
                    }
                )

        return {"tables": tables_list, "columns": columns_list, "relationships": relationships_list}
    except Exception as e:
        raise Exception(f"检索表结构上下文时出错: {str(e)}")
