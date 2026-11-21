"""
Chinese gov/policy domain helpers for ChatDB (政务领域适配).

This module centralizes:
- Domain synonyms for tables/columns/values (中英/中性别名 → 规范值)
- Region aliases (e.g., "常州市" → "常州")
- Time window phrase parser (e.g., "近3个月" → [start,end])
- Lightweight intent heuristics (count/list/latest/top)

These hints are consumed by Text2SQL utilities/prompts to improve
recall and correctness on policy-oriented policy databases
regardless of the underlying engine (MySQL/SQLite/Postgres, etc.).
"""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
from pathlib import Path


# ---------------------------
# Region & value synonyms
# ---------------------------

REGION_ALIASES: Dict[str, str] = {
    "常州经济开发区": "常州经开区",
    "常州经开区": "常州经开区",
    "天宁区": "天宁",
    "钟楼区": "钟楼",
    "新北区": "新北",
    "武进区": "武进",
    "金坛区": "金坛",
    "溧阳市": "溧阳",
    "常州市": "常州",
    "江苏省": "江苏",
    "济南市": "济南",
    "青岛市": "青岛",
    "北京市": "北京",
    "上海市": "上海",
}

# Column-oriented normalized value mappings commonly seen in the demo schema
# key = fully-qualified placeholder (table.column) OR generic column name
# value = { nl_term -> db_value }
GENERIC_COLUMN_VALUE_SYNONYMS: Dict[str, Dict[str, str]] = {
    # Generic region/city
    "city": {
        **REGION_ALIASES,
    },
    # Vehicle types in auto_subsidy_tiers
    "vehicle_type": {
        "新能源汽车": "新能源",
        "纯电": "新能源",
        "油车": "燃油",
        "燃油车": "燃油",
    },
    # Benefit type
    "benefit_type": {
        "现金": "cash",
        "礼包": "gift_package",
    },
}

# Fully-qualified override synonyms loaded from JSON overrides
OVERRIDE_COLUMN_VALUE_SYNONYMS: Dict[str, Dict[str, str]] = {}


# ---------------------------
# Table hints from NL keywords
# ---------------------------

TABLE_HINTS: Dict[str, List[str]] = {
    # policies
    "政策": ["policy_documents", "policy_benefit_rules", "policy_timelines", "policy_execution_roles"],
    "公告": ["policy_documents", "policy_timelines"],
    "细则": ["policy_documents", "policy_benefit_rules"],
    "通知": ["policy_documents"],
    # coupons & appliances & auto
    "消费券": ["coupon_rules"],
    "餐饮券": ["coupon_rules"],
    "零售券": ["coupon_rules"],
    "家电": ["appliance_subsidy_rules", "policy_benefit_rules"],
    "以旧换新": ["appliance_subsidy_rules", "policy_benefit_rules"],
    "汽车": ["auto_subsidy_tiers", "auto_subsidy_windows"],
    "首保": ["insurance_subsidy_rules"],
}


# ---------------------------
# Time window parsing
# ---------------------------

@dataclass
class TimeWindow:
    """中文时间短语解析出的日期起止与原短语，供下游构造查询条件。"""

    start: date
    end: date
    phrase: str


def _add_months(base: date, months: int) -> date:
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    day = min(base.day, monthrange(year, month)[1])
    return date(year, month, day)


def parse_time_window(query: str, today: Optional[date] = None) -> Optional[TimeWindow]:
    """Parse Chinese time phrases to a [start, end] window.

    Supports phrases like: 近N天/周/月/季度/年, 本月/本季度/今年, 去年/上个月/上周.
    """
    query = query.strip()
    if not query:
        return None
    now = today or date.today()

    # 近N单位
    match = re.search(r"近\s*(\d+)\s*(天|日|周|星期|月|季度|年)", query)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ("天", "日"):
            start = now - timedelta(days=amount)
        elif unit in ("周", "星期"):
            start = now - timedelta(weeks=amount)
        elif unit == "月":
            start = _add_months(now, -amount)
        elif unit == "季度":
            start = _add_months(now, -3 * amount)
        else:  # 年
            start = _add_months(now, -12 * amount)
        return TimeWindow(start=start, end=now, phrase=match.group(0))

    # 今年/本年、本月、本周
    if re.search(r"(今年|本年)", query):
        return TimeWindow(start=date(now.year, 1, 1), end=now, phrase="今年")
    if re.search(r"本月", query):
        return TimeWindow(start=date(now.year, now.month, 1), end=now, phrase="本月")
    if re.search(r"本季度", query):
        quarter_start_month = (now.month - 1) // 3 * 3 + 1
        return TimeWindow(start=date(now.year, quarter_start_month, 1), end=now, phrase="本季度")
    if re.search(r"本周", query):
        # Monday as start of week
        start = now - timedelta(days=(now.weekday()))
        return TimeWindow(start=start, end=now, phrase="本周")

    # 去年/上个月/上周
    if re.search(r"去年", query):
        return TimeWindow(start=date(now.year - 1, 1, 1), end=date(now.year - 1, 12, 31), phrase="去年")
    if re.search(r"上个月", query):
        previous_month = _add_months(now, -1)
        return TimeWindow(
            start=date(previous_month.year, previous_month.month, 1),
            end=date(previous_month.year, previous_month.month, monthrange(previous_month.year, previous_month.month)[1]),
            phrase="上个月",
        )
    if re.search(r"上周", query):
        last_monday = now - timedelta(days=(now.weekday() + 7))
        last_sunday = last_monday + timedelta(days=6)
        return TimeWindow(start=last_monday, end=last_sunday, phrase="上周")

    return None


# ---------------------------
# Intent & query heuristics
# ---------------------------

def infer_intent(query: str) -> Dict[str, str]:
    """用中文关键词提取聚合、排序和条数提示；未识别时返回空字典。"""
    query = query.strip()
    intent: Dict[str, str] = {}
    if not query:
        return intent

    if re.search(r"(多少|多少条|数量|有几|有多少)", query):
        intent["aggregation"] = "count"
    if re.search(r"(总额|总数|合计|累计|总计|总和)", query):
        intent.setdefault("aggregation", "sum")
    if re.search(r"(平均|均值|平均值)", query):
        intent.setdefault("aggregation", "avg")
    if re.search(r"(最新|最近|按时间|近|本月|今年)", query):
        intent["order_by"] = "desc_time"
    # Top N
    match = re.search(r"(前|TOP|Top|top)\s*(\d+)", query)
    if match:
        intent["limit"] = match.group(2)
    elif re.search(r"(列出|展示|清单|有哪些)", query):
        intent.setdefault("limit", "100")
    return intent


def normalize_terms(query: str) -> Tuple[str, Dict[str, str]]:
    """Normalize common NL synonyms to their canonical values in-place within the NL query.

    Returns the normalized NL string and a dict of replacements applied.
    """
    replaced: Dict[str, str] = {}
    for alias, canonical_name in REGION_ALIASES.items():
        if alias in query:
            query = query.replace(alias, canonical_name)
            replaced[alias] = canonical_name
    return query, replaced


def candidate_tables_from_query(query: str) -> List[str]:
    """Return a flat list of candidate table names hinted by NL keywords."""
    hints: List[str] = []
    for keyword, tables in TABLE_HINTS.items():
        if keyword in query:
            hints.extend(tables)
    # unique preserve order
    seen = set()
    candidates = []
    for table in hints:
        if table not in seen:
            seen.add(table)
            candidates.append(table)
    return candidates


def domain_value_mappings_for_schema(schema_context: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Build additional value-mappings based on generic synonyms and the actual columns in schema_context.

    For any column whose name matches keys in GENERIC_COLUMN_VALUE_SYNONYMS, attach the mapping
    under "{table}.{column}".
    """
    mappings: Dict[str, Dict[str, str]] = {}
    for column in schema_context["columns"]:
        column_name = column["name"].lower()
        qualified_column = f"{column['table_name']}.{column['name']}"
        if column_name in GENERIC_COLUMN_VALUE_SYNONYMS:
            mappings[qualified_column] = GENERIC_COLUMN_VALUE_SYNONYMS[column_name]
        # Merge fully-qualified overrides if available
        if qualified_column in OVERRIDE_COLUMN_VALUE_SYNONYMS:
            mappings[qualified_column] = {
                **mappings.get(qualified_column, {}),
                **OVERRIDE_COLUMN_VALUE_SYNONYMS[qualified_column],
            }
    return mappings


# ---------------------------
# Overrides loader
# ---------------------------

DEFAULT_OVERRIDE_PATHS = [
    Path("resources/data/process/domain_overrides.json"),
    Path("resources/data/domain_overrides.json"),
]


def _apply_overrides(payload: Dict[str, Any]) -> None:
    # regions
    REGION_ALIASES.update(payload.get("region_aliases", {}))
    # table hints
    for keyword, tables in payload.get("table_hints", {}).items():
        current = TABLE_HINTS.setdefault(keyword, [])
        for table in tables:
            if table not in current:
                current.append(table)
    # column synonyms
    for column, mapping in payload.get("column_value_synonyms", {}).items():
        if "." in column:
            # fully-qualified
            OVERRIDE_COLUMN_VALUE_SYNONYMS[column] = {
                **OVERRIDE_COLUMN_VALUE_SYNONYMS.get(column, {}),
                **mapping,
            }
        else:
            GENERIC_COLUMN_VALUE_SYNONYMS[column] = {
                **GENERIC_COLUMN_VALUE_SYNONYMS.get(column, {}),
                **mapping,
            }


def load_overrides(paths: Optional[List[Path]] = None) -> None:
    """按顺序将存在的 JSON 配置合并到模块级领域词表；单文件失败记录警告并继续。"""
    if paths is None:
        paths = DEFAULT_OVERRIDE_PATHS
    for path in paths:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                _apply_overrides(data)
        except Exception as exc:  # best-effort
            logging.getLogger(__name__).warning("Failed to load domain overrides %s: %s", path, exc, exc_info=True)


# Load on import (best-effort)
load_overrides()
