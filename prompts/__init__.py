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

__all__ = [
    "PromptManager",
    "IntentPrompts",
    "ChatPrompts",
    "PolicyPrompts",
    "CalculationPrompts",
    "ComparisonPrompts",
    "AnalysisPrompts",
    "GenerationPrompts"
]