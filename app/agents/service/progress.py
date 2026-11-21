"""Request-local execution observations and public source references.

Observers never own the operation, and their failure must not change its result.
The HTTP transport adapts these events to its protocol outside the agent service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import re
from typing import Any, TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

if TYPE_CHECKING:
    from app.models.policy import PolicyDocument


logger = logging.getLogger(__name__)
_observer: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("agent_progress_observer", default=None)
_native_tools: ContextVar[bool] = ContextVar("agent_native_tool_progress", default=False)


@contextmanager
def capture_progress(callback: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    """Bind only this request/task's observations and restore a previous binding."""
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def emit_progress(event_type: str, **data: Any) -> None:
    """Publish factual execution state; response-disconnect errors stay local."""
    callback = _observer.get()
    if callback is None:
        return
    try:
        callback({"type": event_type, **data})
    except Exception:
        logger.debug("Progress observer unavailable")


@contextmanager
def progress_step(name: str, label: str) -> Iterator[None]:
    """Report an actual operation's lifetime, including errors and cancellation."""
    emit_progress("step_started", name=name, label=label)
    try:
        yield
    except BaseException as exc:
        status = "cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "error"
        emit_progress("step_finished", name=name, label=label, status=status)
        raise
    else:
        emit_progress("step_finished", name=name, label=label, status="completed")


@contextmanager
def native_tool_progress() -> Iterator[None]:
    """Let an SDK stream report its real call IDs instead of wrapper duplicates."""
    token = _native_tools.set(True)
    try:
        yield
    finally:
        _native_tools.reset(token)


@contextmanager
def progress_tool(name: str, label: str) -> Iterator[None]:
    """Observe a tool execution without sending its input or private result."""
    call_id = uuid4().hex
    native = _native_tools.get()
    if not native:
        emit_progress("tool_started", tool_call_id=call_id, name=name)
    try:
        with progress_step(name, label):
            yield
    except BaseException as exc:
        if not native:
            status = "cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "error"
            emit_progress("tool_finished", tool_call_id=call_id, name=name, status=status)
        raise
    else:
        if not native:
            emit_progress("tool_finished", tool_call_id=call_id, name=name, status="completed")


def _source_url(value: object) -> str:
    if not isinstance(value, str) or not value or re.search(r"[\x00-\x20\\]", value):
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
        return value
    if value.startswith(("/api/knowledge/documents/", "/api/uploads/", "/resources/")) and ".." not in parsed.path.split("/"):
        return value
    return ""


def source_references(documents: Sequence[PolicyDocument]) -> list[dict[str, Any]]:
    """Keep citation order and fragment identity while adding navigable evidence.

    Grouping is a display concern: equal titles or equal URLs must not collapse
    distinct numbered fragments in the answer's original reference array.
    """
    references = []
    for document in documents[:5]:
        metadata = document.metadata
        url = next((link for value in (
            metadata.get("source_url"), metadata.get("url"), metadata.get("original_url"), document.source,
            metadata.get("path"), metadata.get("origin"),
        ) if (link := _source_url(value))), "")
        title = document.title
        fragment = re.search(r"\s*[（(]第\s*(\d+)\s*/\s*(\d+)\s*段[）)]\s*$", title)
        document_title = title[:fragment.start()] if fragment else title
        reference: dict[str, Any] = {
            "id": str(document.id),
            "document_id": str(metadata.get("source_id") or metadata.get("original_document_id") or url or ""),
            "title": title,
            "document_title": document_title,
            "path": metadata.get("path") or metadata.get("origin") or "",
            "origin": document.source,
            "url": url,
            "excerpt": document.content[:6000],
            "chunk_idx": metadata.get("chunk_idx", metadata.get("chunk_index")),
        }
        if fragment:
            reference["chunk_number"] = int(fragment.group(1))
            reference["chunk_total"] = int(fragment.group(2))
            if reference["chunk_idx"] is None:
                reference["chunk_idx"] = reference["chunk_number"] - 1
        for name in ("page", "page_number", "chunk_total", "article", "article_number", "source_version", "parsed_version"):
            value = metadata.get(name)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                reference[name] = value
        references.append(reference)
    return references
