"""Engine-side hub client. This object never synchronizes.

Resilience notes:

* The stream reader is created with ``MAX_MESSAGE_BYTES`` as its limit. The
  asyncio default is 64 KiB, and one historical-candle response is larger
  than that. With the default limit ``readline`` raised, the reader task
  died, and every later request timed out while the engine looked alive.
* If the hub closes the socket (hub restart, crash, oversized frame), the
  client marks itself detached-by-peer and reattaches on the next request.
  Only the engine's own ``close()`` is final. Reattaching re-sends ``hello``;
  it never asks the hub to synchronize.
* Idempotent reads may be resent once after a reattach. Mutating methods are
  never resent: a lost response is surfaced as an error, not a second order.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import uuid
from typing import Any

from metaapi_hub.errors import HubRequestError
from metaapi_hub.locks import LazyLock
from metaapi_hub.protocol import FORBIDDEN_CLIENT_METHODS, MAX_MESSAGE_BYTES, MUTATING_METHODS, dumps, loads

log = logging.getLogger("odin.metaapi_hub.client")


class HubClient:
    """Newline-JSON client for one engine process."""

    def __init__(
        self,
        socket_path: str,
        *,
        engine_name: str,
        account_id: str,
        expects_mode: str,
        reattach_attempts: int = 3,
        reattach_backoff: float = 0.5,
        reattach_backoff_max: float = 5.0,
    ) -> None:
        self.socket_path = socket_path
        self.engine_name = engine_name
        self.account_id = account_id
        self.expects_mode = expects_mode
        self.reattach_attempts = reattach_attempts
        self.reattach_backoff = reattach_backoff
        self.reattach_backoff_max = reattach_backoff_max
        self.local_synchronize_calls = 0
        self.reattaches = 0
        self.connection_losses = 0
        self.client_id: str | None = None
        self._reader: Any = None
        self._writer: Any = None
        self._reader_task: asyncio.Task | None = None
        self._write_lock = LazyLock()
        self._attach_lock = LazyLock()
        self._pending: dict[str, asyncio.Future] = {}
        self._closed = False
        self._peer_closed = False
        self._loss_reason: str | None = None

    @property
    def attached(self) -> bool:
        """True while the socket is open and the reader task is alive."""

        return (
            not self._closed
            and not self._peer_closed
            and self._writer is not None
            and self._reader_task is not None
            and not self._reader_task.done()
        )

    async def connect(self) -> dict:
        self._closed = False
        return await self._attach()

    async def _attach(self) -> dict:
        """Open the socket and register. Does not synchronize."""

        await self._teardown_transport()
        self._peer_closed = False
        self._loss_reason = None
        self._reader, self._writer = await asyncio.open_unix_connection(
            self.socket_path,
            limit=MAX_MESSAGE_BYTES,
        )
        self._reader_task = asyncio.get_running_loop().create_task(self._read_loop())
        hello = await self._send(
            "hello",
            {
                "engine": self.engine_name,
                "pid": os.getpid(),
                "account_id": self.account_id,
                "expects_mode": self.expects_mode,
            },
            timeout=30.0,
        )
        self.client_id = hello["client_id"]
        log.info(
            "Hub client attached engine=%s mode=%s you_do_not_sync=%s",
            self.engine_name,
            hello.get("mode"),
            hello.get("you_do_not_sync"),
        )
        return hello

    async def request(self, method: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        if method in FORBIDDEN_CLIENT_METHODS:
            self.local_synchronize_calls += 1
            raise HubRequestError("FORBIDDEN_SYNC", "this client is not allowed to synchronize")
        if self._closed:
            raise HubRequestError("NOT_CONNECTED", "hub client was closed by the engine")
        if self._writer is None and self.client_id is None:
            raise HubRequestError("NOT_CONNECTED", "hub client is not connected; call connect() first")

        if not self.attached:
            await self._reattach()

        try:
            return await self._send(method, params, timeout=timeout)
        except HubRequestError as exc:
            if exc.code != "CLOSED" or method in MUTATING_METHODS:
                raise
            # The socket dropped while an idempotent read was outstanding.
            # Reattach once and resend. Mutations are never resent.
            log.warning(
                "Hub connection dropped during %s for engine=%s; reattaching and resending the read",
                method,
                self.engine_name,
            )
            await self._reattach()
            return await self._send(method, params, timeout=timeout)

    async def _send(self, method: str, params: dict | None, *, timeout: float) -> Any:
        if self._writer is None:
            raise HubRequestError("NOT_CONNECTED", "hub client is not connected")
        loop = asyncio.get_running_loop()
        request_id = str(uuid.uuid4())
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future
        payload = dumps({"id": request_id, "method": method, "params": params or {}})
        try:
            try:
                async with self._write_lock:
                    self._writer.write(payload)
                    await self._writer.drain()
            except (ConnectionError, OSError) as exc:
                self._note_loss(f"write failed: {type(exc).__name__}")
                raise HubRequestError("CLOSED", f"hub connection closed while sending {method}") from exc
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)

    async def _reattach(self) -> None:
        """Reopen the socket with bounded, jittered backoff. Raises NOT_CONNECTED on failure."""

        async with self._attach_lock:
            if self._closed:
                raise HubRequestError("NOT_CONNECTED", "hub client was closed by the engine")
            if self.attached:
                return
            last: BaseException | None = None
            for attempt in range(1, self.reattach_attempts + 1):
                try:
                    await self._attach()
                    self.reattaches += 1
                    log.warning(
                        "Hub client reattached engine=%s attempt=%s reattaches=%s (previous loss: %s)",
                        self.engine_name,
                        attempt,
                        self.reattaches,
                        self._loss_reason or "unknown",
                    )
                    return
                except Exception as exc:  # socket missing, hub restarting, hello refused
                    last = exc
                    await self._teardown_transport()
                    if attempt >= self.reattach_attempts:
                        break
                    delay = min(self.reattach_backoff * (2 ** (attempt - 1)), self.reattach_backoff_max)
                    delay += delay * 0.25 * random.random()
                    log.warning(
                        "Hub reattach attempt %s/%s failed for engine=%s (%s: %s); retrying in %.2fs",
                        attempt,
                        self.reattach_attempts,
                        self.engine_name,
                        type(exc).__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            raise HubRequestError(
                "NOT_CONNECTED",
                f"hub unreachable at {self.socket_path} after {self.reattach_attempts} reattach attempts: {last}",
            )

    def _note_loss(self, reason: str) -> None:
        if not self._peer_closed:
            self.connection_losses += 1
            self._loss_reason = reason
            log.error(
                "Hub connection lost for engine=%s (%s). Pending requests fail now; "
                "the next request reattaches. This engine did not synchronize and will not.",
                self.engine_name,
                reason,
            )
        self._peer_closed = True

    async def _teardown_transport(self) -> None:
        task = self._reader_task
        self._reader_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        writer = self._writer
        self._writer = None
        self._reader = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.attached and self.client_id is not None:
                await self._send("unsubscribe", {}, timeout=2.0)
        except Exception:
            pass
        await self._teardown_transport()

    async def _read_loop(self) -> None:
        assert self._reader is not None
        reason = "hub closed the socket"
        try:
            while True:
                try:
                    line = await self._reader.readline()
                except (ValueError, asyncio.LimitOverrunError) as exc:
                    # Only reachable if a frame exceeds MAX_MESSAGE_BYTES.
                    reason = f"oversized hub frame (> {MAX_MESSAGE_BYTES} bytes): {exc}"
                    break
                except asyncio.IncompleteReadError:
                    reason = "hub socket ended mid-frame"
                    break
                if not line:
                    break
                try:
                    message = loads(line)
                except Exception as exc:
                    log.error("Bad hub frame (%d bytes): %s", len(line), exc)
                    continue
                future = self._pending.get(message.get("id"))
                if future is None or future.done():
                    continue
                if message.get("ok"):
                    future.set_result(message.get("result"))
                else:
                    error = message.get("error") or {}
                    future.set_exception(
                        HubRequestError(
                            error.get("code") or "BROKER_ERROR",
                            error.get("message") or "hub request failed",
                            receipt=error.get("receipt"),
                        )
                    )
        except asyncio.CancelledError:
            reason = "closed by engine"
            raise
        except (ConnectionError, OSError) as exc:
            reason = f"socket error: {type(exc).__name__}"
        finally:
            if reason != "closed by engine" and not self._closed:
                self._note_loss(reason)
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(HubRequestError("CLOSED", f"hub connection closed ({reason})"))
