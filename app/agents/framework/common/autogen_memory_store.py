"""Lightweight AutoGen memory bridge with optional Redis persistence."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_core.model_context import BufferedChatCompletionContext

try:
    from autogen_ext.memory.redis import RedisMemory  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    RedisMemory = None

_MEMORIES: Dict[str, ListMemory] = {}
_REDIS_ENABLED = False
_REDIS_CFG: Dict[str, Any] = {}


def _configure_redis() -> None:
    global _REDIS_ENABLED, _REDIS_CFG
    url = os.getenv("AGENTCHAT_REDIS_URL") or os.getenv("REDIS_URL")
    if not url or RedisMemory is None:
        _REDIS_ENABLED = False
        return
    namespace = os.getenv("AGENTCHAT_REDIS_NAMESPACE", "agentchat_memory")
    ttl = int(os.getenv("AGENTCHAT_REDIS_TTL_SECONDS", "0") or "0")
    _REDIS_CFG = {
        "redis_url": url,
        "namespace": namespace,
        "ttl_seconds": ttl if ttl > 0 else None,
    }
    _REDIS_ENABLED = True


_configure_redis()


def redis_health() -> Dict[str, Any]:
    info: Dict[str, Any] = {"enabled": _REDIS_ENABLED}
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
            pass

    # 注意：autogen_core.memory.ListMemory 当前不支持 max_messages/truncate 参数，手动截断
    mem = ListMemory(name=f"session:{session_id}")
    mem._max_messages = max_items
    mem._truncate_length = truncate_chars
    _MEMORIES[session_id] = mem
    return mem


async def add_user_message(session_id: str, text: str) -> None:
    if not text:
        return
    mem = get_memory(session_id)
    await _add_with_limit(mem, MemoryContent(content=f"用户:{text}", mime_type=MemoryMimeType.TEXT))


async def add_assistant_message(session_id: str, text: str, max_len: int = 800) -> None:
    if not text:
        return
    mem = get_memory(session_id)
    snippet = text.strip()
    if max_len and len(snippet) > max_len:
        snippet = snippet[:max_len] + "…"
    await _add_with_limit(mem, MemoryContent(content=f"助手:{snippet}", mime_type=MemoryMimeType.TEXT))


def get_recent_messages(session_id: str, limit: int = 10) -> List[str]:
    mem = _MEMORIES.get(session_id)
    if not mem or not mem.content:
        return []
    recent = mem.content[-limit:]
    return [item.content for item in recent if getattr(item, "content", None)]


async def build_buffered_context(session_id: str, buffer_size: int = 10) -> BufferedChatCompletionContext:
    ctx = BufferedChatCompletionContext(buffer_size=buffer_size)
    mem = get_memory(session_id)
    await mem.update_context(ctx)
    return ctx


async def _add_with_limit(mem: ListMemory, content: MemoryContent) -> None:
    """Append content with manual truncation/length enforcement."""
    truncate_len = getattr(mem, "_truncate_length", 0) or 0
    if truncate_len > 0 and content.content and len(content.content) > truncate_len:
        content = MemoryContent(
            content=content.content[:truncate_len] + "…",
            mime_type=content.mime_type,
            metadata=content.metadata,
        )
    await mem.add(content)
    max_msgs = getattr(mem, "_max_messages", 0) or 0
    if max_msgs > 0 and len(mem.content) > max_msgs:
        # 保留最新 max_msgs 条
        mem.content = mem.content[-max_msgs:]


__all__ = [
    "get_memory",
    "add_user_message",
    "add_assistant_message",
    "get_recent_messages",
    "build_buffered_context",
    "redis_health",
]
