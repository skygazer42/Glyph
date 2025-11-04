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
    model = model or os.getenv("MODEL__MODEL_NAME", "gpt-4o")
    base_url = base_url or os.getenv("MODEL__BASE_URL")
    api_key = api_key or os.getenv("MODEL__API_KEY") or os.getenv("OPENAI_API_KEY")
    temperature = (
        float(temperature)
        if temperature is not None
        else float(os.getenv("MODEL__TEMPERATURE", "0"))
    )
    seed = int(seed) if seed is not None else int(os.getenv("MODEL__SEED", "42"))

    kwargs = {"model": model, "seed": seed, "temperature": temperature}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key

    return OpenAIChatCompletionClient(**kwargs)


def create_buffered_context(buffer_size: int = 10) -> BufferedChatCompletionContext:
    size = int(os.getenv("MODEL__CTX_BUFFER_SIZE", str(buffer_size)))
    return BufferedChatCompletionContext(buffer_size=size)

