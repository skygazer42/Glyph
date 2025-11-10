"""Central model client registry."""

from __future__ import annotations

from typing import Dict, Optional

from autogen_core.models import ChatCompletionClient

from app.core.llms import model_client as _default_client

_client_registry: Dict[str, ChatCompletionClient] = {}


def register_model_client(name: str, client: ChatCompletionClient) -> None:
    """Register or override a named model client."""
    _client_registry[name] = client


def get_model_client(model_name: Optional[str] = None) -> ChatCompletionClient:
    """Return a client for ``model_name`` or fall back to the default client."""
    if model_name:
        return _client_registry.get(model_name, _default_client)
    return _default_client


def get_default_model_client() -> ChatCompletionClient:
    """Expose the default chat completion client."""
    return _default_client


__all__ = [
    "get_model_client",
    "get_default_model_client",
    "register_model_client",
]
