"""
Text2SQL服务 - 重构后的版本
提供向后兼容的接口，内部使用新的工具模块
"""
import asyncio
from typing import Dict, Any
from sqlalchemy.orm import Session

from autogen_core.models import UserMessage

from app.models.db_connection import DBConnection
from app.schemas.query import QueryResponse
from app.agents.chatdb.db_service import execute_query
from app.agents.chatdb.text2sql_utils import (
    retrieve_relevant_schema, get_value_mappings, format_schema_for_prompt,
    process_sql_with_value_mappings, validate_sql, extract_sql_from_llm_response
)
from app.core.llms import model_client
from .domain_zh_gov import parse_time_window, infer_intent, normalize_terms


def construct_prompt(schema_context: Dict[str, Any], query: str, value_mappings: Dict[str, Dict[str, str]], *, hints: Dict[str, Any] | None = None) -> str:
    """
    为LLM构建增强上下文和指令的提示
    """
    # 格式化表结构信息
    schema_str = format_schema_for_prompt(schema_context)

    # 如果有值映射，添加到提示中
    mappings_str = ""
    if value_mappings:
        mappings_str = "-- 值映射:\n"
        for column, mappings in value_mappings.items():
            mappings_str += f"-- 对于 {column}:\n"
            for nl_term, db_value in mappings.items():
                mappings_str += f"--   自然语言中的'{nl_term}'指数据库中的'{db_value}'\n"
        mappings_str += "\n"

    # 领域/时间/意图提示
    hints = hints or {}
    intent_lines = []
    if agg := hints.get("aggregation"):
        intent_lines.append(f"- 建议聚合: {agg}")
    if order := hints.get("order_by"):
        intent_lines.append("- 时间排序: 倒序(最近优先)" if order == "desc_time" else f"- 排序: {order}")
    if lim := hints.get("limit"):
        intent_lines.append(f"- 默认限制返回行数: {lim}")

    time_hint = ""
    if (tw := hints.get("time_window")) and tw.get("start"):
        # 告诉LLM优先使用与时间相关的列进行过滤
        time_hint = (
            "-- 时间范围建议: {start} 至 {end} (若表含有 publish_date/start_date/start_time 等日期列, 请据此过滤)\n"
        ).format(start=tw["start"], end=tw.get("end") or "当前")

    extra_block = "\n" + ("\n".join(intent_lines) if intent_lines else "- 无特别意图推断") + "\n"

    prompt = f"""
你是一名专业的SQL开发专家，专门将自然语言问题转换为精确的SQL查询。

### 数据库结构:
```sql
{schema_str}
{mappings_str}
{time_hint}
```

### 自然语言问题:
"{query}"

### 指令:
1. 分析问题并识别相关的表和列。
2. 考虑表之间的关系以确定必要的连接。
3. 如果问题提到的术语可能与实际数据库值不同（例如，"中石化" vs "中国石化"），使用提供的值映射或考虑使用LIKE操作符。
4. 生成回答问题的有效SQL查询。
5. 只使用结构中提供的表和列。
6. 如果需要，使用适当的聚合函数（COUNT、SUM、AVG等）。
7. 根据需要包含适当的GROUP BY、ORDER BY和LIMIT子句。
8. 如果查询与时间相关，适当处理日期/时间比较。
9. 简要解释你的推理。

### 解析出的意图与约束:
{extra_block}

### SQL查询:
"""

    return prompt


async def call_llm_api(prompt: str) -> str:
    """
    调用LLM API 使用 model_client 生成 SQL。

    为了与项目中其他模块保持一致，这里使用 `model_client.create(...)`
    并传入单条 UserMessage。
    """
    try:
        system_message = """
你是一名专业的SQL开发专家，专门将自然语言问题转换为精确的SQL查询。
你的专长包括:
1. 理解复杂的数据库结构和关系
2. 将自然语言意图转换为正确的SQL语法
3. 处理连接、聚合和复杂的过滤条件
4. 确保查询优化并遵循最佳实践

始终生成遵循标准SQL语法的有效SQL。专注于准确性和精确性。
"""
        # 将系统提示拼接到用户提示中，简化消息结构
        full_prompt = f"{system_message}\n\n{prompt}"

        response = await model_client.create(
            [UserMessage(content=full_prompt, source="user")]
        )

        # Autogen 的 OpenAIChatCompletionClient 返回对象带有 content 属性
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        raise Exception(f"调用LLM API时出错: {str(e)}")


async def _process_text2sql_query_async(
    db: Session,
    connection: DBConnection,
    natural_language_query: str
) -> QueryResponse:
    """
    处理自然语言查询并转换为SQL
    """
    try:
        # 0. 领域预处理（规范地区/常见词，并推断时间窗/意图）
        normalized_query, replacements = normalize_terms(natural_language_query)
        time_window = parse_time_window(normalized_query)
        inferred = infer_intent(normalized_query)
        hints = {**inferred}
        if time_window:
            hints["time_window"] = {
                "start": time_window.start.isoformat() if time_window.start else None,
                "end": time_window.end.isoformat() if time_window.end else None,
                "phrase": time_window.phrase,
            }

        # 1. 检索相关表结构（使用规范化后的查询以提升召回）
        schema_context = await retrieve_relevant_schema(db, connection.id, normalized_query)

        # 如果没有找到相关表结构，返回错误
        if not schema_context["tables"]:
            return QueryResponse(
                sql="",
                results=None,
                error="无法为此查询识别相关表。",
                context={"schema_context": schema_context}
            )

        # 2. 获取值映射（合并领域映射，如 city/vehicle_type 等）
        value_mappings = get_value_mappings(db, schema_context)

        # 3. 构建提示（附带时间/意图提示）
        prompt = construct_prompt(schema_context, normalized_query, value_mappings, hints=hints)

        # 4. 调用LLM API
        llm_response = await call_llm_api(prompt)

        # 5. 从响应中提取SQL
        sql = extract_sql_from_llm_response(llm_response)

        # 6. 使用值映射处理SQL
        processed_sql = process_sql_with_value_mappings(sql, value_mappings)

        # 6.1 缺省行数保护：无聚合/无显式LIMIT时默认限制返回数量
        if "limit" not in (processed_sql.lower()) and inferred.get("aggregation") not in ("count",):
            processed_sql = processed_sql.rstrip("; ") + " LIMIT 100"

        # 7. 验证SQL
        if not validate_sql(processed_sql):
            return QueryResponse(
                sql=processed_sql,
                results=None,
                error="生成的SQL验证失败。它可能不是有效的SELECT语句。",
                context={
                    "schema_context": schema_context,
                    "prompt": prompt,
                    "llm_response": llm_response
                }
            )

        # 8. 执行SQL
        try:
            results = execute_query(connection, processed_sql)

            return QueryResponse(
                sql=processed_sql,
                results=results,
                error=None,
                context={
                    "schema_context": schema_context,
                    "prompt": prompt,
                    "llm_response": llm_response
                }
            )
        except Exception as e:
            return QueryResponse(
                sql=processed_sql,
                results=None,
                error=f"SQL执行失败: {str(e)}",
                context={
                    "schema_context": schema_context,
                    "prompt": prompt,
                    "llm_response": llm_response
                }
            )
    except Exception as e:
        return QueryResponse(
            sql="",
            results=None,
            error=f"处理查询时出错: {str(e)}",
            context=None
        )


class Text2SQLService:
    """Object-oriented facade for the Text2SQL helpers."""

    async def run_async(self, db: Session, connection: DBConnection, query: str) -> QueryResponse:
        return await _process_text2sql_query_async(db, connection, query)

    def run(self, db: Session, connection: DBConnection, query: str) -> QueryResponse:
        # 为向后兼容保留同步接口，在独立线程内可安全调用
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.run_async(db, connection, query))
        finally:
            loop.close()


def process_text2sql_query(db: Session, connection: DBConnection, natural_language_query: str) -> QueryResponse:
    """同步包装，保持对 legacy 调用的兼容。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_process_text2sql_query_async(db, connection, natural_language_query))
    finally:
        loop.close()


async def process_text2sql_query_async(
    db: Session, connection: DBConnection, natural_language_query: str
) -> QueryResponse:
    """异步接口，允许在现有事件循环内调用。"""
    return await _process_text2sql_query_async(db, connection, natural_language_query)
