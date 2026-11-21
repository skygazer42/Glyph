"""Lightweight AutoGen memory bridge using local, non-persistent ListMemory."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_core.model_context import BufferedChatCompletionContext
import redis

logger = logging.getLogger(__name__)

_MEMORIES: Dict[str, ListMemory] = {}
_REDIS_CFG: Dict[str, Any] = {}


def _configure_redis() -> None:
    global _REDIS_CFG
    url = os.getenv("AGENTCHAT_REDIS_URL") or os.getenv("REDIS_URL")
    _REDIS_CFG = {"redis_url": url} if url else {}
    # AutoGen 0.7.5 RedisMemory has no synchronous .content or TTL/limit
    # protocol. This bridge deliberately exposes its actual local backend.
    if os.getenv("AGENTCHAT_REDIS_URL"):
        logger.warning("AgentChat memory uses local ListMemory; Redis persistence is unsupported by this bridge")


_configure_redis()


def redis_health() -> Dict[str, Any]:
    """返回本地记忆后端状态；配置 Redis 时只探测连通性，不表示启用了 Redis 持久化。"""
    info: Dict[str, Any] = {
        "enabled": False, "backend": "local", "persistent": False,
        "redis_requested": bool(_REDIS_CFG),
        "reason": "Redis persistence is unsupported by the local memory bridge",
    }
    if not _REDIS_CFG:
        return info
    try:
        client = redis.Redis.from_url(_REDIS_CFG["redis_url"], socket_connect_timeout=2, socket_timeout=2)
        try:
            client.ping()
        finally:
            client.close()
        info["connectivity"] = "ok"
    except Exception as exc:
        info["connectivity"] = "error"
        info["error"] = str(exc)
    return info


def get_memory(session_id: str) -> ListMemory:
    """获取或创建进程内会话记忆，返回缓存中的同一 ListMemory 实例。"""
    mem = _MEMORIES.get(session_id)
    if mem is None:
        mem = ListMemory(name=f"session:{session_id}")
        _MEMORIES[session_id] = mem
    return mem


async def add_user_message(session_id: str, text: str) -> None:
    """将非空用户文本加入会话记忆，应用公共长度与条数限制。"""
    if not text:
        return
    mem = get_memory(session_id)
    await _add_with_limit(mem, MemoryContent(content=f"用户:{text}", mime_type=MemoryMimeType.TEXT))


async def add_assistant_message(session_id: str, text: str, max_len: int = 800) -> None:
    """截短非空助手文本后加入会话记忆，仍受公共记忆限制约束。"""
    if not text:
        return
    mem = get_memory(session_id)
    snippet = text.strip()
    if max_len and len(snippet) > max_len:
        snippet = snippet[:max_len] + "…"
    await _add_with_limit(mem, MemoryContent(content=f"助手:{snippet}", mime_type=MemoryMimeType.TEXT))


def get_recent_messages(session_id: str, limit: int = 10) -> List[str]:
    """返回最近 limit 条记忆中的非空文本；负数报错，零或不存在时返回空列表。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    mem = _MEMORIES.get(session_id)
    if mem is None or not mem.content:
        return []
    recent = mem.content[-limit:] if limit else []
    return [item.content for item in recent if isinstance(item.content, str) and item.content]


async def build_buffered_context(session_id: str, buffer_size: int = 10) -> BufferedChatCompletionContext:
    """新建指定容量的模型上下文并注入当前本地会话记忆。"""
    ctx = BufferedChatCompletionContext(buffer_size=buffer_size)
    mem = get_memory(session_id)
    await mem.update_context(ctx)
    return ctx


async def _add_with_limit(mem: ListMemory, content: MemoryContent) -> None:
    """Append content with manual truncation/length enforcement."""
    truncate_len = int(os.getenv("MEMORY_TRUNCATE_CHARS", "800"))
    if truncate_len > 0 and isinstance(content.content, str) and len(content.content) > truncate_len:
        content = MemoryContent(
            content=content.content[:truncate_len] + "…",
            mime_type=content.mime_type,
            metadata=content.metadata,
        )
    await mem.add(content)
    max_msgs = int(os.getenv("MEMORY_MAX_ITEMS", "50"))
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
