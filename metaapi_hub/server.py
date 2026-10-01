"""Unix-socket server. Local engines are the only clients.

There is no TCP listener. Authentication is the socket filesystem mode.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from metaapi_hub.errors import HubError
from metaapi_hub.owner import SyncOwner
from metaapi_hub.protocol import FORBIDDEN_CLIENT_METHODS, dumps, loads

log = logging.getLogger("odin.metaapi_hub.server")


class HubServer:
    """One connection per engine, one sync owner for the account."""

    def __init__(self, owner: SyncOwner, socket_path: str) -> None:
        self.owner = owner
        self.socket_path = socket_path
        self._server: Any = None

    async def start(self) -> None:
        import asyncio

        directory = os.path.dirname(self.socket_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = await asyncio.start_unix_server(self._handle, path=self.socket_path)
        os.chmod(self.socket_path, 0o660)
        log.info(
            "Hub listening path=%s mode=%s orders_mode=%s",
            self.socket_path,
            self.owner.mode,
            self.owner.orders_mode,
        )

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError as exc:
                log.warning("Could not unlink hub socket: %s", exc)

    async def _handle(self, reader: Any, writer: Any) -> None:
        client_id: str | None = None
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                request: dict | None = None
                try:
                    request = loads(line)
                    response = await self._dispatch(request, client_id)
                except Exception as exc:
                    request_id = request.get("id") if isinstance(request, dict) else None
                    response = _error_response(request_id, exc)
                if (
                    isinstance(request, dict)
                    and response.get("ok")
                    and request.get("method") == "hello"
                ):
                    client_id = (response.get("result") or {}).get("client_id")
                writer.write(dumps(response))
                await writer.drain()
        finally:
            self.owner.unregister(client_id)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

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
