"""Shared LLM client helpers."""

from typing import Any

import httpx
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.config.app_config import settings


def _create_model_client() -> OpenAIChatCompletionClient:
    """Construct the default model client from Settings."""
    model_settings = settings.model
    if not model_settings.llm_api_key:
        raise ValueError("LLM_API_KEY is required to construct the model client")
    # AutoGen forwards this supported OpenAI transport option at runtime; its
    # configuration TypedDict omits the extension key in the installed version.
    client_options: dict[str, Any] = {"http_client": httpx.AsyncClient(trust_env=False)}
    if model_settings.llm_max_tokens is not None:
        client_options["max_tokens"] = model_settings.llm_max_tokens
    if model_settings.llm_timeout is not None:
        client_options["timeout"] = model_settings.llm_timeout
    return OpenAIChatCompletionClient(
        **client_options,
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


model_client = _create_model_client()

__all__ = ["model_client"]
