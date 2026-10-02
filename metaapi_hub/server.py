"""Unix-socket server. Local engines are the only clients.

There is no TCP listener. Authentication is the socket filesystem mode.

Requests on one connection are served concurrently. Before this, a slow
candle fetch that the engine had already given up on (its ``wait_for``
expired) still blocked the engine's next account or position request behind
it, so every follow-up request also timed out. Responses are written under a
per-connection lock so frames never interleave.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from metaapi_hub.errors import HubError
from metaapi_hub.locks import LazyLock
from metaapi_hub.owner import SyncOwner
from metaapi_hub.protocol import FORBIDDEN_CLIENT_METHODS, MAX_MESSAGE_BYTES, dumps, loads

log = logging.getLogger("odin.metaapi_hub.server")


class _Connection:
    """Per-socket state: registration id, write lock, in-flight request tasks."""

    def __init__(self, writer: Any) -> None:
        self.writer = writer
        self.client_id: str | None = None
        self.write_lock = LazyLock()
        self.tasks: set[asyncio.Task] = set()
        self.closed = False


class HubServer:
    """One connection per engine, one sync owner for the account."""

    def __init__(self, owner: SyncOwner, socket_path: str) -> None:
        self.owner = owner
        self.socket_path = socket_path
        self._server: Any = None
        self._writers: set[Any] = set()
        self.max_inflight_per_connection = 0
        self.oversized_frames = 0

    async def start(self) -> None:
        directory = os.path.dirname(self.socket_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = await asyncio.start_unix_server(
            self._handle,
            path=self.socket_path,
            limit=MAX_MESSAGE_BYTES,
        )
        os.chmod(self.socket_path, 0o660)
        log.info(
            "Hub listening path=%s mode=%s orders_mode=%s",
            self.socket_path,
            self.owner.mode,
            self.owner.orders_mode,
        )

    async def close(self) -> None:
        """Stop accepting clients and drop idle sockets.

        ``wait_closed`` would otherwise block until every engine disconnects.
        Shutdown must not depend on the engines exiting first.
        """

        if self._server is not None:
            self._server.close()
        for writer in list(self._writers):
            try:
                writer.close()
            except Exception as exc:
                log.warning("Error closing hub client: %s", exc)
        if self._server is not None:
            await self._server.wait_closed()
            self._server = None
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError as exc:
                log.warning("Could not unlink hub socket: %s", exc)

    async def _handle(self, reader: Any, writer: Any) -> None:
        conn = _Connection(writer)
        self._writers.add(writer)
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ValueError, asyncio.LimitOverrunError) as exc:
                    self.oversized_frames += 1
                    log.error(
                        "Dropping engine connection client=%s: request frame exceeded %d bytes (%s)",
                        conn.client_id,
                        MAX_MESSAGE_BYTES,
                        exc,
                    )
                    break
                except asyncio.IncompleteReadError:
                    break
                if not line:
                    break
                task = loop.create_task(self._serve_one(line, conn))
                conn.tasks.add(task)
                task.add_done_callback(conn.tasks.discard)
                if len(conn.tasks) > self.max_inflight_per_connection:
                    self.max_inflight_per_connection = len(conn.tasks)
        except (ConnectionError, OSError) as exc:
            log.warning("Engine socket error client=%s: %s", conn.client_id, type(exc).__name__)
        finally:
            conn.closed = True
            self._writers.discard(writer)
            self.owner.unregister(conn.client_id)
            # In-flight work is left to finish: a mutation that already reached
            # the broker must not be cancelled half-way, and a shared candle
            # flight is still useful to the other engines. Replies to this
            # closed socket are discarded in _serve_one.
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _serve_one(self, line: bytes, conn: _Connection) -> None:
        request: dict | None = None
        try:
            request = loads(line)
            response = await self._dispatch(request, conn.client_id)
        except Exception as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            response = _error_response(request_id, exc)
        if (
            isinstance(request, dict)
            and response.get("ok")
            and request.get("method") == "hello"
        ):
            conn.client_id = (response.get("result") or {}).get("client_id")
        if conn.closed or conn.writer.is_closing():
            method = request.get("method") if isinstance(request, dict) else "?"
            log.info("Engine client=%s left before %s finished; reply discarded", conn.client_id, method)
            return
        try:
            async with conn.write_lock:
                conn.writer.write(dumps(response))
                await conn.writer.drain()
        except (ConnectionError, OSError) as exc:
            log.warning("Could not write reply to client=%s: %s", conn.client_id, type(exc).__name__)

    async def _dispatch(self, request: dict, client_id: str | None) -> dict:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(params, dict):
            return _fail(request_id, HubError("BAD_REQUEST", "params must be an object"))
        if method in FORBIDDEN_CLIENT_METHODS:
            return _fail(
                request_id,
                HubError("FORBIDDEN_SYNC", "engines cannot synchronize; the hub is the only sync owner"),
            )
        try:
            if method == "health":
                result = self.owner.snapshot()
                result["server_max_inflight_per_connection"] = self.max_inflight_per_connection
                result["server_oversized_frames"] = self.oversized_frames
                result["max_message_bytes"] = MAX_MESSAGE_BYTES
            elif method == "hello":
                result = self.owner.register(
                    engine=str(params.get("engine") or "engine"),
                    pid=int(params.get("pid") or 0),
                    account_id=str(params.get("account_id") or ""),
                    expects_mode=str(params.get("expects_mode") or "on"),
                )
            elif method == "unsubscribe":
                self.owner.unregister(client_id)
                result = {"unsubscribed": True}
            else:
                if client_id is None or client_id not in self.owner.clients:
                    raise HubError("NOT_REGISTERED", "call hello before other methods")
                engine = self.owner.clients[client_id]["engine"]
                result = await self._call(method, params, engine)
        except Exception as exc:
            return _fail(request_id, exc)
        return {"id": request_id, "ok": True, "result": result}

    async def _call(self, method: str, params: dict, engine: str) -> Any:
        if method == "account_information":
            return await self.owner.read("get_account_information")
        if method == "positions":
            return await self.owner.read("get_positions")
        if method == "orders":
            return await self.owner.read("get_orders")
        if method == "symbol_price":
            return await self.owner.read("get_symbol_price", params["symbol"])
        if method == "symbol_specification":
            return await self.owner.read("get_symbol_specification", params["symbol"])
        if method == "historical_candles":
            return await self.owner.historical_candles(
                params["symbol"],
                params.get("timeframe") or "1h",
                params.get("limit"),
            )
        if method == "calculate_margin":
            return await self.owner.read("calculate_margin", params.get("order") or {})
        if method in {
            "create_market_order",
            "create_stop_order",
            "create_limit_order",
            "cancel_order",
            "close_position",
            "close_position_partially",
            "modify_position",
        }:
            return await self.owner.mutate(method, params, engine=engine)
        raise HubError("UNKNOWN_METHOD", f"unknown method {method}")


def _fail(request_id: Any, exc: BaseException) -> dict:
    if isinstance(exc, HubError):
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.receipt is not None:
            error["receipt"] = exc.receipt
        return {"id": request_id, "ok": False, "error": error}
    log.exception("Unhandled hub error")
    return {
        "id": request_id,
        "ok": False,
        "error": {"code": "INTERNAL", "message": type(exc).__name__},
    }


def _error_response(request_id: Any, exc: BaseException) -> dict:
    return _fail(request_id, exc)
