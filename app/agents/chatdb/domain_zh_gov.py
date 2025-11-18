"""
Chinese gov/policy domain helpers for ChatDB (政务领域适配).

This module centralizes:
- Domain synonyms for tables/columns/values (中英/中性别名 → 规范值)
- Region aliases (e.g., "济南市" → "济南")
- Time window phrase parser (e.g., "近三个月" → [start,end])
- Lightweight intent heuristics (count/list/latest/top)

These hints are consumed by Text2SQL utilities/prompts to improve
recall and correctness on policy-oriented policy databases
regardless of the underlying engine (MySQL/SQLite/Postgres, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging
from pathlib import Path


# ---------------------------
# Region & value synonyms
# ---------------------------

REGION_ALIASES: Dict[str, str] = {
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

_TIME_UNITS = {
    "天": "days",
    "日": "days",
    "周": "weeks",
    "星期": "weeks",
    "月": "months",
    "季度": "quarters",
    "年": "years",
}


@dataclass
class TimeWindow:
    start: Optional[date]
    end: Optional[date]
    phrase: str


def _add_months(base: date, months: int) -> date:
    # naive month arithmetic sufficient for coarse filters
    y = base.year + (base.month - 1 + months) // 12
    m = (base.month - 1 + months) % 12 + 1
    d = min(base.day, 28)  # keep simple to avoid month-end complexity
    return date(y, m, d)


def parse_time_window(query: str, today: Optional[date] = None) -> Optional[TimeWindow]:
    """Parse Chinese time phrases to a [start, end] window.

    Supports phrases like: 近N天/周/月/季度/年, 本月/本季度/今年, 去年/上个月/上周.
    """
    q = query.strip()
    if not q:
        return None
    now = today or date.today()

    # 近N单位
    m = re.search(r"近\s*(\d+)\s*(天|日|周|星期|月|季度|年)", q)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit in ("天", "日"):
            start = now - timedelta(days=n)
        elif unit in ("周", "星期"):
            start = now - timedelta(weeks=n)
        elif unit == "月":
            start = _add_months(now, -n)
        elif unit == "季度":
            start = _add_months(now, -3 * n)
        else:  # 年
            start = date(now.year - n, now.month, min(now.day, 28))
        return TimeWindow(start=start, end=now, phrase=m.group(0))

    # 今年/本年、本月、本周
    if re.search(r"(今年|本年)", q):
        return TimeWindow(start=date(now.year, 1, 1), end=now, phrase="今年")
    if re.search(r"本月", q):
        return TimeWindow(start=date(now.year, now.month, 1), end=now, phrase="本月")
    if re.search(r"本周", q):
        # Monday as start of week
        start = now - timedelta(days=(now.weekday()))
        return TimeWindow(start=start, end=now, phrase="本周")

    # 去年/上个月/上周
    if re.search(r"去年", q):
        return TimeWindow(start=date(now.year - 1, 1, 1), end=date(now.year - 1, 12, 31), phrase="去年")
    if re.search(r"上个月", q):
        prev = _add_months(now, -1)
        return TimeWindow(start=date(prev.year, prev.month, 1), end=date(prev.year, prev.month, 28), phrase="上个月")
    if re.search(r"上周", q):
        last_monday = now - timedelta(days=(now.weekday() + 7))
        last_sunday = last_monday + timedelta(days=6)
        return TimeWindow(start=last_monday, end=last_sunday, phrase="上周")

    return None


# ---------------------------
# Intent & query heuristics
# ---------------------------

def infer_intent(query: str) -> Dict[str, str]:
    q = query.strip()
    intent = {}
    if not q:
        return intent

    if re.search(r"(多少|多少条|数量|有几|有多少)", q):
        intent["aggregation"] = "count"
    if re.search(r"(总额|总数|合计|累计|总计|总和)", q):
        intent["aggregation"] = intent.get("aggregation") or "sum"
    if re.search(r"(平均|均值|平均值)", q):
        intent["aggregation"] = intent.get("aggregation") or "avg"
    if re.search(r"(最新|最近|按时间|近|本月|今年)", q):
        intent["order_by"] = "desc_time"
    # Top N
    m = re.search(r"(前|TOP|Top|top)\s*(\d+)", q)
    if m:
        intent["limit"] = m.group(2)
    elif re.search(r"(列出|展示|清单|有哪些)", q):
        intent.setdefault("limit", "100")
    return intent


def normalize_terms(query: str) -> Tuple[str, Dict[str, str]]:
    """Normalize common NL synonyms to their canonical values in-place within the NL query.

    Returns the normalized NL string and a dict of replacements applied.
    """
    replaced: Dict[str, str] = {}
    q = query
    for k, v in REGION_ALIASES.items():
        if k in q:
            q = q.replace(k, v)
            replaced[k] = v
    return q, replaced


def candidate_tables_from_query(query: str) -> List[str]:
    """Return a flat list of candidate table names hinted by NL keywords."""
    hints: List[str] = []
    for kw, tables in TABLE_HINTS.items():
        if kw in query:
            hints.extend(tables)
    # unique preserve order
    seen = set()
    uniq = []
    for t in hints:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def domain_value_mappings_for_schema(schema_context: Dict[str, any]) -> Dict[str, Dict[str, str]]:
    """Build additional value-mappings based on generic synonyms and the actual columns in schema_context.

    For any column whose name matches keys in GENERIC_COLUMN_VALUE_SYNONYMS, attach the mapping
    under "{table}.{column}".
    """
    mappings: Dict[str, Dict[str, str]] = {}
    if not schema_context or not schema_context.get("columns"):
        return mappings
    for col in schema_context["columns"]:
        col_name = col.get("name", "").lower()
        table = col.get("table_name", "")
        if col_name in GENERIC_COLUMN_VALUE_SYNONYMS:
            fq = f"{table}.{col['name']}"
            mappings[fq] = GENERIC_COLUMN_VALUE_SYNONYMS[col_name]
        # Merge fully-qualified overrides if available
        fq_col = f"{table}.{col['name']}"
        if fq_col in OVERRIDE_COLUMN_VALUE_SYNONYMS:
            base = mappings.get(fq_col, {})
            merged = dict(GENERIC_COLUMN_VALUE_SYNONYMS.get(col_name, {}))
            merged.update(base)
            merged.update(OVERRIDE_COLUMN_VALUE_SYNONYMS[fq_col])
            mappings[fq_col] = merged
    return mappings


# ---------------------------
# Overrides loader
# ---------------------------

DEFAULT_OVERRIDE_PATHS = [
    Path("resources/data/process/domain_overrides.json"),
    Path("resources/data/domain_overrides.json"),
]


def _apply_overrides(payload: Dict[str, any]) -> None:
    if not payload:
        return
    # regions
    for k, v in payload.get("region_aliases", {}).items():
        REGION_ALIASES[k] = v
    # table hints
    for kw, tables in payload.get("table_hints", {}).items():
        current = TABLE_HINTS.get(kw, [])
        for t in tables:
            if t not in current:
                current.append(t)
        TABLE_HINTS[kw] = current
    # column synonyms
    for col, mapping in payload.get("column_value_synonyms", {}).items():
        if "." in col:
            # fully-qualified
            OVERRIDE_COLUMN_VALUE_SYNONYMS[col] = {
                **OVERRIDE_COLUMN_VALUE_SYNONYMS.get(col, {}),
                **mapping,
            }
        else:
            GENERIC_COLUMN_VALUE_SYNONYMS[col] = {
                **GENERIC_COLUMN_VALUE_SYNONYMS.get(col, {}),
                **mapping,
            }


def load_overrides(paths: Optional[List[Path]] = None) -> None:
    paths = paths or DEFAULT_OVERRIDE_PATHS
    for p in paths:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                _apply_overrides(data)
        except Exception as exc:  # best-effort
            logging.getLogger(__name__).warning("Failed to load domain overrides %s: %s", p, exc)


# Load on import (best-effort)
load_overrides()
