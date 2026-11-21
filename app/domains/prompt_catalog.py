"""Structured loader for domain-specific prompts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, Dict[str, str]]:
    """缓存领域提示词目录；文件缺失或内容为空时返回空目录，结构错误则抛出异常。"""
    if not CATALOG_PATH.exists():
        return {"domains": {}}
    with open(CATALOG_PATH, "r", encoding="utf-8") as catalog_file:
        data = yaml.safe_load(catalog_file)
    if data is None:
        return {"domains": {}}
    if not isinstance(data, dict):
        raise ValueError("Prompt catalog must be a mapping")
    domains = data.get("domains", {})
    if not isinstance(domains, dict):
        raise ValueError("Prompt catalog domains must be a mapping")
    return {"domains": domains}


def get_domain_prompt(name: str) -> Optional[str]:
    """按领域键读取提示词，未登记的键返回 None。"""
    return _load_catalog()["domains"].get(name)


def list_domain_prompts() -> Dict[str, str]:
    """返回提示词映射的浅副本，避免调用方直接修改缓存映射。"""
    return dict(_load_catalog()["domains"])


__all__ = ["get_domain_prompt", "list_domain_prompts"]
