"""Model clients configured from environment or an explicit legacy config list."""

import os
from collections.abc import Mapping
from typing import Any, Optional

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext


def create_openai_client(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    *,
    llm_config: Mapping[str, Any] | None = None,
) -> OpenAIChatCompletionClient:
    """Create a caller-owned client; an explicit config_list selects its first provider.

    Callers may inject an existing client into agents instead. The creator must await
    close() for clients returned here; no process-wide singleton is installed.
    """
    configuration = dict(llm_config) if llm_config is not None else {}
    if "config_list" in configuration:
        providers = configuration.pop("config_list")
        if not isinstance(providers, list) or not providers or not isinstance(providers[0], Mapping):
            raise ValueError("llm_config.config_list must contain at least one provider mapping")
        configuration = {**providers[0], **configuration}

    if model is None:
        model = configuration.get("model", os.getenv("LLM_MODEL_NAME"))
    if not isinstance(model, str) or not model:
        raise ValueError("A model name is required")
    if base_url is None:
        base_url = configuration.get("base_url", os.getenv("LLM_BASE_URL"))
    if api_key is None:
        api_key = configuration.get("api_key", os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")))
    if temperature is None:
        temperature = configuration.get("temperature", os.getenv("LLM_TEMPERATURE", "0"))
    if seed is None:
        seed = configuration.get("seed", os.getenv("LLM_SEED", "42"))

    kwargs: dict[str, Any] = {"model": model, "temperature": float(temperature), "seed": int(seed)}
    if base_url is not None:
        kwargs["base_url"] = base_url
    if api_key is not None:
        kwargs["api_key"] = api_key
    for key in ("timeout", "max_retries", "model_info"):
        if key in configuration:
            kwargs[key] = configuration[key]
    if "model_info" not in kwargs and model.startswith(("deepseek-", "qwen-", "Qwen")):
        # These configured OpenAI-compatible text providers are not in AutoGen's
        # OpenAI model registry. Capabilities can be overridden with model_info.
        kwargs["model_info"] = {
            "vision": False, "function_calling": True, "json_output": True,
            "structured_output": False, "family": "unknown",
        }
    return OpenAIChatCompletionClient(**kwargs)


def create_buffered_context(buffer_size: int = 10) -> BufferedChatCompletionContext:
    """创建模型消息缓冲区，环境变量 LLM_CTX_BUFFER_SIZE 可覆盖调用参数容量。"""
    size = int(os.getenv("LLM_CTX_BUFFER_SIZE", str(buffer_size)))
    return BufferedChatCompletionContext(buffer_size=size)
