"""asyncio locks that bind on first use.

Python 3.9's ``asyncio.Lock()`` calls ``get_event_loop()`` immediately. After
``asyncio.run()`` the main thread has no current loop, so constructing a
broker or owner outside a running loop raises ``RuntimeError``. Creating the
lock on first ``async with`` binds it to the loop that actually runs the hub.
"""

from __future__ import annotations

import asyncio


class LazyLock:
    """Drop-in ``async with`` lock. Safe to construct before the loop exists."""

    def __init__(self) -> None:
        self._lock: asyncio.Lock | None = None

    def _ensure(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def __aenter__(self) -> None:
        await self._ensure().acquire()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._ensure().release()


class LazySemaphore:
    """``async with`` semaphore that binds to the running loop on first use."""

    def __init__(self, value: int) -> None:
        if value < 1:
            raise ValueError("semaphore value must be at least 1")
        self.value = value
        self._sem: asyncio.Semaphore | None = None

    def _ensure(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.value)
        return self._sem

    async def __aenter__(self) -> None:
        await self._ensure().acquire()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._ensure().release()
