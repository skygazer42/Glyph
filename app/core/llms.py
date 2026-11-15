"""Shared LLM client helpers."""

from typing import Any

import httpx

from app.config.app_config import settings
from autogen_ext.models.openai import OpenAIChatCompletionClient


def _setup_model_client():
    """Construct the default model client from Settings."""
    model_settings = settings.model
    if model_settings.llm_api_key is None:
        raise ValueError("LLM_API_KEY is required to construct the model client")
    # AutoGen forwards this supported OpenAI transport option at runtime; its
    # configuration TypedDict omits the extension key in the installed version.
    transport_options: dict[str, Any] = {"http_client": httpx.AsyncClient(trust_env=False)}
    return OpenAIChatCompletionClient(
        **transport_options,
        model=model_settings.llm_model_name,
        api_key=model_settings.llm_api_key,
        temperature=model_settings.llm_temperature,
        base_url=model_settings.llm_base_url,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": True,
            "family": "unknown",
            "multiple_system_messages": True,
        },
    )


model_client = _setup_model_client()

__all__ = ["model_client"]
