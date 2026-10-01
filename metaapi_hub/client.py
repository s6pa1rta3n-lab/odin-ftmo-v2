"""Engine-side hub client. This object never synchronizes."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from metaapi_hub.errors import HubRequestError
from metaapi_hub.locks import LazyLock
from metaapi_hub.protocol import FORBIDDEN_CLIENT_METHODS, dumps, loads

log = logging.getLogger("odin.metaapi_hub.client")


class HubClient:
    """Newline-JSON client for one engine process."""

    def __init__(self, socket_path: str, *, engine_name: str, account_id: str, expects_mode: str) -> None:
        self.socket_path = socket_path
        self.engine_name = engine_name
        self.account_id = account_id
        self.expects_mode = expects_mode
        self.local_synchronize_calls = 0
        self.client_id: str | None = None
        self._reader: Any = None
        self._writer: Any = None
        self._reader_task: asyncio.Task | None = None
        self._write_lock = LazyLock()
        self._pending: dict[str, asyncio.Future] = {}
        self._closed = False

    async def connect(self) -> dict:
        self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
        self._reader_task = asyncio.get_running_loop().create_task(self._read_loop())
        hello = await self.request(
            "hello",
            {
                "engine": self.engine_name,
                "pid": os.getpid(),
                "account_id": self.account_id,
                "expects_mode": self.expects_mode,
            },
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
        if self._writer is None:
            raise HubRequestError("NOT_CONNECTED", "hub client is not connected")
        loop = asyncio.get_running_loop()
        request_id = str(uuid.uuid4())
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future
        payload = dumps({"id": request_id, "method": method, "params": params or {}})
        try:
            async with self._write_lock:
                self._writer.write(payload)
                await self._writer.drain()
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._writer is not None and self.client_id is not None:
                await self.request("unsubscribe", {}, timeout=2.0)
        except Exception:
            pass
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    message = loads(line)
                except Exception as exc:
                    log.error("Bad hub frame: %s", exc)
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
            raise
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(HubRequestError("CLOSED", "hub connection closed"))
