"""Shared LLM client helpers."""

import os

from app.config import settings
from autogen_ext.models.openai import OpenAIChatCompletionClient


def _setup_model_client():
    """Construct the default model client from Settings."""
    for key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        os.environ.pop(key, None)

    model_cfg = settings.model
    model_config = {
        "model": model_cfg.llm_model_name,
        "api_key": model_cfg.llm_api_key,
        "temperature": model_cfg.llm_temperature,
        "model_info": {
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": True,
            "family": "unknown",
            "multiple_system_messages": True,
        },
    }

    if model_cfg.llm_base_url:
        model_config["base_url"] = model_cfg.llm_base_url

    return OpenAIChatCompletionClient(**model_config)


model_client = _setup_model_client()

__all__ = ["model_client"]
