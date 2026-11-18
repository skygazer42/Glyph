"""Execute Text2SQL queries and present their structured results."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from app.agents.chatdb.text2sql_service import process_text2sql_query_for_connection_async
from app.models.policy import FinalAnswer
from app.schemas.text2sql import SQLQueryResult

logger = logging.getLogger(__name__)


async def answer_text2sql_query(query: str, *, connection_id: Optional[int]) -> FinalAnswer:
    if connection_id is None or connection_id <= 0:
        return FinalAnswer(
            query_id=uuid4(),
            answer="执行数据库查询需要提供 connection_id。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"route": "text2sql", "error": "missing_connection_id"},
            total_processing_time=0.0,
        )

    try:
        response: SQLQueryResult = await process_text2sql_query_for_connection_async(connection_id, query)
        return _build_text2sql_answer(response, connection_id)
    except Exception as exc:  # pragma: no cover
        logger.error("Text2SQL 执行失败: %s", exc, exc_info=True)
        return FinalAnswer(
            query_id=uuid4(),
            answer="执行 SQL 失败，请确认数据库连接与问题格式。",
            sources=[],
            confidence=0.0,
            verification_passed=False,
            metadata={"route": "text2sql", "error": str(exc)},
            total_processing_time=0.0,
        )

def _build_text2sql_answer(response: SQLQueryResult, connection_id: int) -> FinalAnswer:
    rows = [] if response.results is None else response.results
    metadata = {
        "route": "text2sql",
        "sql": response.sql,
        "connection_id": connection_id,
        "error": response.error,
        "rows": rows,
    }

    # 构造人类可读的回答文案
    if response.error:
        answer_text = f"SQL 执行失败：{response.error}"
        confidence = 0.3
    else:
        total = len(rows)
        answer_text = "SQL 执行成功，结果如下："
        answer_text += f"\n返回 {total} 条记录。"

        # 预览前若干条记录，避免一次性输出过多数据
        if rows:
            max_preview = 10
            preview = rows[:max_preview]
            answer_text += f"\n预览前 {len(preview)} 条："
            # 推导列名
            cols = list(preview[0].keys())
            for idx, row in enumerate(preview, start=1):
                # 简单的 k=v 列表，前端会按文本渲染
                kv = ", ".join(f"{k}={row[k]!r}" for k in cols)
                answer_text += f"\n{idx}) {kv}"
            if total > max_preview:
                answer_text += f"\n... 其余 {total - max_preview} 条已省略。"

            # 生成表格和简易 ECharts 数据（假设首列为类别，次列为数值）
            if len(cols) >= 2:
                cat_col = cols[0]
                val_col = cols[1]
                table_preview = {"columns": cols, "rows": preview}
                chart_meta = {
                    "type": "bar",
                    "xField": cat_col,
                    "yField": val_col,
                    "data": [{cat_col: row[cat_col], val_col: row[val_col]} for row in preview],
                    "title": "政策类别统计",
                }
                metadata["chart"] = chart_meta
                metadata["table_preview"] = table_preview

        confidence = 0.75 if rows else 0.5

    return FinalAnswer(
        query_id=uuid4(),
        answer=answer_text,
        sources=[],
        confidence=confidence,
        verification_passed=False,
        metadata=metadata,
        total_processing_time=0.0,
    )
