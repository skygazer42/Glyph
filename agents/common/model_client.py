"""
Model client utilities for Autogen AgentChat, configured via environment variables.
"""

import os
from typing import Optional

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext


def create_openai_client(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
):
    # Prefer LLM_* keys; optional fallback to OPENAI_*
    model = model or os.getenv("LLM_MODEL_NAME")
    base_url = base_url or os.getenv("LLM_BASE_URL")
    api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    temperature = (
        float(temperature)
        if temperature is not None
        else float(os.getenv("LLM_TEMPERATURE") or 0)
    )
    seed = int(seed) if seed is not None else int(os.getenv("LLM_SEED") or 42)

    kwargs = {"model": model, "seed": seed, "temperature": temperature}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key

    return OpenAIChatCompletionClient(**kwargs)


def create_buffered_context(buffer_size: int = 10) -> BufferedChatCompletionContext:
    size = int(os.getenv("LLM_CTX_BUFFER_SIZE", str(buffer_size)))
    return BufferedChatCompletionContext(buffer_size=size)
