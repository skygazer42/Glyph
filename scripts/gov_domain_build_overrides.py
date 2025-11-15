#!/usr/bin/env python3
"""
Build domain overrides (region/table/value synonyms) from resources/data/process
for the Chinese gov/policy domain. The output JSON is saved to
resources/data/process/domain_overrides.json and automatically loaded by
ChatDB domain helpers.

Heuristics, not NLP-heavy: scans .md/.txt/.docx text for keywords.
Requires: docx2txt (already in requirements.txt).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

try:
    import docx2txt  # type: ignore
except Exception:
    docx2txt = None


ROOT = Path(__file__).resolve().parents[1]
PROCESS_DIR = ROOT / "resources" / "data" / "process"
OUTPUT_PATH = PROCESS_DIR / "domain_overrides.json"


CITY_ALIAS: Dict[str, str] = {}
TABLE_HINTS: Dict[str, List[str]] = {}
COLUMN_VALUE_SYN: Dict[str, Dict[str, str]] = {}


CITY_PAT = re.compile(r"([\u4e00-\u9fa5]{2,6})市")

KW_TABLES = {
    # kw -> candidate tables
    "消费券": ["coupon_rules"],
    "餐饮": ["coupon_rules"],
    "零售": ["coupon_rules"],
    "家电": ["appliance_subsidy_rules", "policy_benefit_rules"],
    "以旧换新": ["appliance_subsidy_rules", "policy_benefit_rules"],
    "汽车": ["auto_subsidy_tiers", "auto_subsidy_windows"],
    "首保": ["insurance_subsidy_rules"],
    "政策": ["policy_documents", "policy_benefit_rules", "policy_timelines", "policy_execution_roles"],
    "公告": ["policy_documents", "policy_timelines"],
    "细则": ["policy_documents", "policy_benefit_rules"],
}

VALUE_SYNONYMS = {
    # fully-qualified or generic column names
    "coupon_rules.coupon_type": {
        "餐饮券": "dining",
        "餐饮": "dining",
        "零售券": "retail",
        "零售": "retail",
    },
    "appliance_subsidy_rules.category": {
        "空调": "空调",
        "冰箱": "冰箱",
        "手机": "手机",
        "平板": "平板",
        "智能手表": "智能手表",
        "手环": "智能手表",
    },
    "auto_subsidy_tiers.vehicle_type": {
        "新能源": "新能源",
        "纯电": "新能源",
        "燃油": "燃油",
        "燃油车": "燃油",
    },
    "auto_subsidy_tiers.benefit_type": {
        "现金": "cash",
        "礼包": "gift_package",
    },
    # generic
    "city": {},  # will be filled from CITY_ALIAS
}


def read_text(p: Path) -> str:
    if p.suffix.lower() in (".md", ".txt"):
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    if p.suffix.lower() in (".docx",):
        if docx2txt is None:
            return ""
        try:
            return docx2txt.process(str(p)) or ""
        except Exception:
            return ""
    return ""


def scan_process_dir() -> None:
    for f in PROCESS_DIR.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".md", ".txt", ".docx"):
            continue
        text = read_text(f)
        if not text:
            continue

        # city aliases
        for m in CITY_PAT.finditer(text):
            full = m.group(0)
            short = m.group(1)
            CITY_ALIAS[full] = short

        # table hints
        for kw, tables in KW_TABLES.items():
            if kw in text:
                lst = TABLE_HINTS.setdefault(kw, [])
                for t in tables:
                    if t not in lst:
                        lst.append(t)


def main() -> None:
    if not PROCESS_DIR.exists():
        print(f"No process dir: {PROCESS_DIR}")
        return
    scan_process_dir()

    # finalize value synonyms with city aliases
    if CITY_ALIAS:
        VALUE_SYNONYMS["city"].update(CITY_ALIAS)

    payload = {
        "region_aliases": CITY_ALIAS,
        "table_hints": TABLE_HINTS,
        "column_value_synonyms": VALUE_SYNONYMS,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote overrides: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

