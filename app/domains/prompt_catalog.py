"""Structured loader for domain-specific prompts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, Dict[str, str]]:
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
    return _load_catalog()["domains"].get(name)


def list_domain_prompts() -> Dict[str, str]:
    return dict(_load_catalog()["domains"])


__all__ = ["get_domain_prompt", "list_domain_prompts"]
