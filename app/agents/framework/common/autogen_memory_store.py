"""Lightweight bridge to AutoGen memory for per-session chat history.

Supports in-memory ListMemory by default, optional RedisMemory when configured:
- set AGENTCHAT_REDIS_URL or REDIS_URL to enable.
- optional AGENTCHAT_REDIS_NAMESPACE, AGENTCHAT_REDIS_TTL_SECONDS.
- MEMORY_MAX_ITEMS, MEMORY_TRUNCATE_CHARS 控制长度。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_core.model_context import BufferedChatCompletionContext

try:
    from autogen_ext.memory.redis import RedisMemory
except Exception:  # pragma: no cover - optional dependency
    RedisMemory = None

_MEMORIES: Dict[str, ListMemory] = {}
_REDIS_ENABLED = False
_REDIS_CFG = {}


def _configure_redis():
    global _REDIS_ENABLED, _REDIS_CFG
    url = os.getenv("AGENTCHAT_REDIS_URL") or os.getenv("REDIS_URL")
    if not url or RedisMemory is None:
        _REDIS_ENABLED = False
        return
    namespace = os.getenv("AGENTCHAT_REDIS_NAMESPACE", "agentchat_memory")
    ttl = int(os.getenv("AGENTCHAT_REDIS_TTL_SECONDS", "0") or "0")
    _REDIS_CFG = {"redis_url": url, "namespace": namespace, "ttl_seconds": ttl if ttl > 0 else None}
    _REDIS_ENABLED = True


_configure_redis()


def redis_health() -> Dict[str, Any]:
    """
    Return health info for Redis memory (if enabled).
    """
    info = {"enabled": _REDIS_ENABLED}
    if not _REDIS_ENABLED:
        info["reason"] = "redis not configured or driver missing"
        return info
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(_REDIS_CFG["redis_url"])
        client.ping()
        info["status"] = "ok"
    except Exception as exc:  # pragma: no cover - optional
        info["status"] = "error"
        info["error"] = str(exc)
    return info


def get_memory(session_id: str) -> ListMemory:
    """Get or create a ListMemory for the given session."""
    mem = _MEMORIES.get(session_id)
    if mem is not None:
        return mem

    max_items = int(os.getenv("MEMORY_MAX_ITEMS", "50") or "50")
    truncate_chars = int(os.getenv("MEMORY_TRUNCATE_CHARS", "800") or "800")

    if _REDIS_ENABLED:
        try:
            mem = RedisMemory(
                name=f"session:{session_id}",
                redis_url=_REDIS_CFG["redis_url"],
                namespace=_REDIS_CFG["namespace"],
                ttl_seconds=_REDIS_CFG["ttl_seconds"],
                max_messages=max_items,
                truncate_message_length=truncate_chars,
            )
            _MEMORIES[session_id] = mem
            return mem
        except Exception:
            # 回退到内存
            pass

    mem = ListMemory(name=f"session:{session_id}", max_messages=max_items, truncate_message_length=truncate_chars)
    _MEMORIES[session_id] = mem
    return mem


async def add_user_message(session_id: str, text: str) -> None:
    """Append a user turn to AutoGen memory."""
    if not text:
        return
    mem = get_memory(session_id)
    await mem.add(
        MemoryContent(
            content=f"用户:{text}",
            mime_type=MemoryMimeType.TEXT,
        )
    )


async def add_assistant_message(session_id: str, text: str, max_len: int = 800) -> None:
    """Append an assistant turn to AutoGen memory."""
    if not text:
        return
    mem = get_memory(session_id)
    snippet = text.strip()
    if max_len and len(snippet) > max_len:
        snippet = snippet[:max_len] + "…"
    await mem.add(
        MemoryContent(
            content=f"助手:{snippet}",
            mime_type=MemoryMimeType.TEXT,
        )
    )


def get_recent_messages(session_id: str, limit: int = 10) -> List[str]:
    """Return recent memory items for prompt context (latest first)."""
    mem = _MEMORIES.get(session_id)
    if not mem or not mem.content:
        return []
    recent = mem.content[-limit:]
    return [item.content for item in recent if getattr(item, "content", None)]


async def build_buffered_context(session_id: str, buffer_size: int = 10) -> BufferedChatCompletionContext:
    """
    Populate a BufferedChatCompletionContext with session memory.

    Can be passed directly to AutoGen model clients that support buffered contexts.
    """
    ctx = BufferedChatCompletionContext(buffer_size=buffer_size)
    mem = get_memory(session_id)
    await mem.update_context(ctx)
    return ctx


__all__ = [
    "get_memory",
    "add_user_message",
    "add_assistant_message",
    "get_recent_messages",
    "build_buffered_context",
]
