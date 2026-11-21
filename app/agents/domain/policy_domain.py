"""Policy-domain helpers shared across AgentService pipelines.

This module borrows concepts from ChatDB's domain_zh_gov helper to:
- normalize policy-related queries (地区别名、政策关键词、时间窗口)
- expose structured context consumed by KnowledgeAgent / other agents
- provide search variants to improve recall in policy corpora under
  resources/data/process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.chatdb.domain_zh_gov import (
    REGION_ALIASES,
    normalize_terms,
    parse_time_window,
    TimeWindow,
    load_overrides as load_chatdb_overrides,
)

# Ensure overrides from resources/data/process are loaded once (idempotent)
load_chatdb_overrides()

POLICY_KEYWORDS = [
    "住房",
    "公积金",
    "装修",
    "物业费",
    "购房资助",
    "人才",
    "消费券",
    "家电",
    "以旧换新",
    "首保",
    "汽车",
    "新能源",
    "燃油",
    "活动",
    "公告",
    "细则",
    "政策",
    "补贴",
]


@dataclass
class PolicyDomainContext:
    """保存原问题、规范化结果和检索提示，不代表政策资格或数据库过滤已被验证。"""

    original_query: str
    normalized_query: str
    region: Optional[str] = None
    region_alias_applied: Optional[str] = None
    time_window: Optional[TimeWindow] = None
    keywords: List[str] = field(default_factory=list)
    search_variants: List[str] = field(default_factory=list)
    synonyms_applied: Dict[str, str] = field(default_factory=dict)

    def to_metadata(self) -> Dict[str, Any]:
        """将领域提示转为答案元数据；未识别时间时保留空时间字段。"""
        return {
            "region": self.region,
            "time_window": {
                "start": self.time_window.start.isoformat() if self.time_window else None,
                "end": self.time_window.end.isoformat() if self.time_window else None,
                "phrase": self.time_window.phrase if self.time_window else None,
            },
            "keywords": self.keywords,
            "synonyms": self.synonyms_applied,
        }


class PolicyDomainContextBuilder:
    """Factory building domain context for policy QA."""

    def __init__(self) -> None:
        self.region_aliases = REGION_ALIASES
        self.policy_keywords = POLICY_KEYWORDS

    def build(self, query: str) -> PolicyDomainContext:
        """从问题提取地区、时间与关键词，生成保持顺序的去重检索变体。"""
        normalized, replacements = normalize_terms(query)
        region = self._detect_region(normalized, replacements)
        time_window = parse_time_window(normalized)
        keywords = self._extract_keywords(normalized)

        search_variants = self._compose_search_variants(normalized, region, keywords, time_window)
        return PolicyDomainContext(
            original_query=query,
            normalized_query=normalized,
            region=region,
            region_alias_applied=replacements.get(region, None) if region else None,
            time_window=time_window,
            keywords=keywords,
            search_variants=search_variants,
            synonyms_applied=replacements,
        )

    def _detect_region(self, normalized: str, replacements: Dict[str, str]) -> Optional[str]:
        for original_term, replacement in replacements.items():
            if original_term.endswith(("区", "县")):
                return replacement
        for original_term, replacement in replacements.items():
            if original_term.endswith("市"):
                return replacement
        for alias, region in self.region_aliases.items():
            if alias in normalized or region in normalized:
                return region
        return None

    def _extract_keywords(self, normalized: str) -> List[str]:
        return [keyword for keyword in self.policy_keywords if keyword in normalized]

    def _compose_search_variants(
        self,
        normalized: str,
        region: Optional[str],
        keywords: List[str],
        time_window: Optional[TimeWindow],
    ) -> List[str]:
        variants = [normalized]
        if region and region not in normalized:
            variants.append(f"{normalized} {region}")
        for keyword in keywords[:2]:  # limit expansions
            if keyword not in normalized:
                variants.append(f"{region or ''} {keyword} 政策".strip())
        if time_window and time_window.phrase:
            variants.append(f"{normalized} {time_window.phrase}")
        # Deduplicate while preserving order
        seen = set()
        unique_variants: List[str] = []
        for text in variants:
            key = text.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique_variants.append(key)
        return unique_variants


__all__ = ["PolicyDomainContext", "PolicyDomainContextBuilder"]
