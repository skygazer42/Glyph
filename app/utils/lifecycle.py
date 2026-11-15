"""Bounded cleanup for application-owned asynchronous resources."""

from collections.abc import Awaitable, Callable
from math import isfinite
from typing import TypeVar

import anyio

T = TypeVar("T")


async def close_with_timeout(
    close: Callable[[], Awaitable[T]], *, cleanup_timeout: float = 5
) -> T:
    """Finish cooperative cleanup after cancellation, exposing timeout/failure."""
    if not isfinite(cleanup_timeout) or cleanup_timeout <= 0:
        raise ValueError("Cleanup timeout must be finite and greater than zero")
    with anyio.fail_after(cleanup_timeout, shield=True):
        return await close()
