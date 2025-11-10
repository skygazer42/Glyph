"""
统一提示词管理系统
"""

from .prompt_manager import PromptManager
from .templates import (
    IntentPrompts,
    ChatPrompts,
    PolicyPrompts,
    CalculationPrompts,
    ComparisonPrompts,
    AnalysisPrompts,
    GenerationPrompts
)
from .domain_catalog import get_domain_prompt, list_domain_prompts

__all__ = [
    "PromptManager",
    "IntentPrompts",
    "ChatPrompts",
    "PolicyPrompts",
    "CalculationPrompts",
    "ComparisonPrompts",
    "AnalysisPrompts",
    "GenerationPrompts",
    "get_domain_prompt",
    "list_domain_prompts",
]
