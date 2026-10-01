"""Single synchronization owner.

Engines never call ``synchronize``. This object does, at most one at a time,
and serializes RPC on that connection. Read calls may be retried once after a
disconnect. Order calls are never retried.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
import uuid
from typing import Any, Awaitable, Callable

from metaapi_hub.errors import (
    DryRunOrderError,
    GatewayTimeoutError,
    HubError,
    NotConnectedError,
    OrdersDisabledError,
)
from metaapi_hub.protocol import MUTATING_METHODS, normalize_candles

log = logging.getLogger("odin.metaapi_hub.owner")


class SyncOwner:
    """Owns the account synchronization slot and serves engine RPCs."""

    def __init__(
        self,
        broker: Any,
        *,
        mode: str,
        orders_mode: str = "deny",
        account_id: str = "shadow",
        cache_ttl: float = 5.0,
        max_sync_attempts: int = 5,
        backoff_base: float = 0.05,
        candle_attempts: int = 4,
        duplicate_window: float = 3.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if mode not in {"shadow", "live"}:
            raise HubError("CONFIG", f"unsupported hub mode {mode}")
        if orders_mode not in {"deny", "dry_run", "live"}:
            raise HubError("CONFIG", f"unsupported orders mode {orders_mode}")
        if mode == "shadow" and orders_mode == "live":
            log.warning("Shadow mode cannot place live orders; forcing orders_mode=dry_run")
            orders_mode = "dry_run"
        self.broker = broker
        self.mode = mode
        self.orders_mode = orders_mode
        self.account_id = account_id
        self.cache_ttl = cache_ttl
        self.max_sync_attempts = max_sync_attempts
        self.backoff_base = backoff_base
        self.candle_attempts = candle_attempts
        self.duplicate_window = duplicate_window
        self._sleep = sleep or asyncio.sleep
        self._clock = clock or time.monotonic
        self.connected = False
        self.synchronize_calls = 0
        self.sync_attempts = 0
        self.reconnects = 0
        self.candle_fetches = 0
        self.candle_timeouts = 0
        self.single_flight_joins = 0
        self.cache_hits = 0
        self.duplicate_suppressions = 0
        self._epoch = 0
        self._sync_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()
        self._flight_lock = asyncio.Lock()
        self._inflight: dict[tuple, asyncio.Task] = {}
        self._cache: dict[tuple, tuple[float, list]] = {}
        self._recent_mutations: dict[tuple, tuple[float, dict]] = {}
        self.clients: dict[str, dict] = {}

    def orders_are_live(self) -> bool:
        """Live orders require the process flag and the environment interlock.

        Both must be set on the hub process. An engine cannot turn this on.
        """

        if self.orders_mode != "live":
            return False
        return os.environ.get("ODIN_METAAPI_HUB_ORDERS", "") == "live"

    def register(self, engine: str, pid: int, account_id: str, expects_mode: str) -> dict:
        """Register an engine client. This does not synchronize."""

        if self.mode == "live" and expects_mode == "shadow":
            raise HubError(
                "MODE_MISMATCH",
                "shadow engine refused: this hub is live. Start a shadow hub or set ODIN_METAAPI_HUB=on only after cutover approval.",
            )
        if self.mode == "live" and account_id and self.account_id and account_id != self.account_id:
            raise HubError(
                "ACCOUNT_MISMATCH",
                "engine account id does not match the hub account",
            )
        client_id = str(uuid.uuid4())
        self.clients[client_id] = {
            "engine": engine,
            "pid": pid,
            "account_id": account_id,
            "expects_mode": expects_mode,
        }
        log.info(
            "Engine subscribed engine=%s pid=%s clients=%s syncs=%s",
            engine,
            pid,
            len(self.clients),
            self.synchronize_calls,
        )
        return {
            "client_id": client_id,
            "mode": self.mode,
            "orders_mode": self.orders_mode,
            "orders_live": self.orders_are_live(),
            "you_do_not_sync": True,
            "synchronize_calls": self.synchronize_calls,
        }

    def unregister(self, client_id: str | None) -> None:
        if client_id and client_id in self.clients:
            engine = self.clients.pop(client_id)["engine"]
            log.info("Engine unsubscribed engine=%s clients=%s", engine, len(self.clients))

    def snapshot(self) -> dict:
        """Health view. Contains no credentials."""

        return {
            "mode": self.mode,
            "orders_mode": self.orders_mode,
            "orders_live": self.orders_are_live(),
            "account_id": self.account_id,
            "connected": self.connected,
            "synchronize_calls": self.synchronize_calls,
            "sync_attempts": self.sync_attempts,
            "reconnects": self.reconnects,
            "clients": sorted(item["engine"] for item in self.clients.values()),
            "client_count": len(self.clients),
            "candle_fetches": self.candle_fetches,
            "candle_timeouts": self.candle_timeouts,
            "single_flight_joins": self.single_flight_joins,
            "cache_hits": self.cache_hits,
            "duplicate_suppressions": self.duplicate_suppressions,
            "broker_synchronize_calls": getattr(self.broker, "synchronize_calls", None),
            "broker_order_calls": getattr(self.broker, "order_calls", None),
            "broker_mutation_calls": getattr(self.broker, "mutation_calls", None),
            "broker_candle_calls": getattr(self.broker, "candle_calls", None),
            "broker_connected": getattr(self.broker, "connected", None),
            "max_rpc_depth": getattr(self.broker, "max_rpc_depth", None),
            "you_do_not_sync": True,
        }

    async def ensure_connected(self) -> None:
        if self.connected:
            return
        async with self._sync_lock:
            if self.connected:
                return
            await self._release_slot()
            await self._sync_with_backoff()

    async def _release_slot(self) -> None:
        """Drop any previous synchronization before opening the single slot."""

        closer = getattr(self.broker, "close", None)
        if closer is None:
            return
        try:
            await closer()
        except Exception as exc:
            log.warning("Broker close before synchronization failed: %s", exc)

    async def _sync_with_backoff(self) -> None:
        """Caller holds ``_sync_lock``. Opens the single slot, with backoff on 429."""

        last: BaseException | None = None
        for attempt in range(1, self.max_sync_attempts + 1):
            self.sync_attempts += 1
            try:
                await self.broker.synchronize()
                self.synchronize_calls += 1
                self.connected = True
                log.info("Sync owner connected attempt=%s synchronize_calls=%s", attempt, self.synchronize_calls)
                return
            except Exception as exc:
                last = exc
                self.connected = False
                delay = self.backoff_base * (2 ** (attempt - 1))
                log.warning(
                    "Synchronization attempt %s/%s failed (%s). Backing off %.3fs. Not opening a second slot.",
                    attempt,
                    self.max_sync_attempts,
                    exc,
                    delay,
                )
                await self._sleep(delay)
        raise HubError("SYNC_FAILED", f"synchronization failed after {self.max_sync_attempts} attempts: {last}")

    async def _recover(self, seen_epoch: int) -> None:
        """One reconnect for every engine that observed the same disconnect."""

        async with self._sync_lock:
            if self._epoch != seen_epoch:
                return
            self.connected = False
            await self._release_slot()
            await self._sync_with_backoff()
            self._epoch += 1
            self.reconnects += 1
            log.info("Sync owner reconnected reconnects=%s epoch=%s", self.reconnects, self._epoch)

    async def read(self, method: str, *args: Any) -> Any:
        """Run a read RPC. Retry once if the terminal dropped. Never opens a second slot."""

        await self.ensure_connected()
        epoch = self._epoch
        try:
            async with self._rpc_lock:
                return await self._invoke(method, *args)
        except NotConnectedError:
            log.warning("Read %s saw 'not connected to broker'; one shared reconnect", method)
            await self._recover(epoch)
            async with self._rpc_lock:
                return await self._invoke(method, *args)

    async def historical_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        """Single-flight candle fetch with a short cache and 504 backoff."""

        if limit is not None:
            limit = int(limit)
            if limit < 0 or limit > 5000:
                raise HubError("BAD_REQUEST", "candle limit must be between 0 and 5000")
        key = (str(symbol), str(timeframe), limit)
        cached = self._cache.get(key)
        if cached and (self._clock() - cached[0]) <= self.cache_ttl:
            self.cache_hits += 1
            return [dict(item) for item in cached[1]]

        async with self._flight_lock:
            cached = self._cache.get(key)
            if cached and (self._clock() - cached[0]) <= self.cache_ttl:
                self.cache_hits += 1
                return [dict(item) for item in cached[1]]
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.get_running_loop().create_task(
                    self._load_candles(key, symbol, timeframe, limit)
                )
                self._inflight[key] = task
            else:
                self.single_flight_joins += 1
        try:
            result = await task
            return [dict(item) for item in result]
        finally:
            if task.done():
                async with self._flight_lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)

    async def _load_candles(self, key: tuple, symbol: str, timeframe: str, limit: int | None) -> list:
        delay = self.backoff_base
        last: BaseException | None = None
        for _attempt in range(self.candle_attempts):
            try:
                raw = await self.read("get_historical_candles", symbol, timeframe, limit)
                self.candle_fetches += 1
                normalized = normalize_candles(raw, limit)
                self._cache[key] = (self._clock(), normalized)
                return [dict(item) for item in normalized]
            except GatewayTimeoutError as exc:
                last = exc
                self.candle_timeouts += 1
                log.warning("Historical candles 504 for %s %s; retrying in %.3fs", symbol, timeframe, delay)
                await self._sleep(delay)
                delay *= 2
        assert last is not None
        raise last

    async def mutate(self, method: str, params: dict, *, engine: str) -> dict:
        """Place, cancel, close, or modify. Never retried. Blocked unless live is explicit."""

        if method not in MUTATING_METHODS:
            raise HubError("BAD_REQUEST", f"{method} is not a mutation")
        self._validate_mutation(method, params)
        if not self.orders_are_live():
            return self._refuse_mutation(method, params)

        await self.ensure_connected()
        dup_key = self._dup_key(engine, method, params)
        async with self._rpc_lock:
            previous = self._recent_mutations.get(dup_key)
            if previous is not None and (self._clock() - previous[0]) <= self.duplicate_window:
                self.duplicate_suppressions += 1
                log.warning("Suppressed duplicate %s from engine=%s inside %.1fs window", method, engine, self.duplicate_window)
                return previous[1]
            try:
                result = await self._invoke(method, params)
            except NotConnectedError:
                self.connected = False
                log.error("Mutation %s failed with not-connected. Not retrying, to avoid a double fill.", method)
                raise
            if not isinstance(result, dict):
                result = {"result": result}
            self._recent_mutations[dup_key] = (self._clock(), result)
            return result

    def _refuse_mutation(self, method: str, params: dict) -> dict:
        receipt = {
            "dryRun": self.orders_mode == "dry_run",
            "sent": False,
            "numericCode": None,
            "stringCode": "DRY_RUN" if self.orders_mode == "dry_run" else "ORDERS_DISABLED",
            "orderId": None,
            "method": method,
            "symbol": params.get("symbol"),
            "side": params.get("side"),
            "volume": params.get("volume"),
        }
        if self.orders_mode == "dry_run":
            raise DryRunOrderError(
                "Order was not sent to the broker. Hub orders_mode is dry_run.",
                receipt,
            )
        raise OrdersDisabledError(
            "Order was not sent. Hub orders are denied until a future approved cutover. "
            "This pull request does not enable live orders."
        )

    def _validate_mutation(self, method: str, params: dict) -> None:
        if method in {"create_market_order", "create_stop_order", "create_limit_order"}:
            comment = params.get("comment")
            if not comment or not str(comment).strip():
                raise HubError("COMMENT_REQUIRED", "entry orders must include a comment")
            side = params.get("side")
            if side not in {"BUY", "SELL"}:
                raise HubError("BAD_REQUEST", "side must be BUY or SELL")
            if not params.get("symbol"):
                raise HubError("BAD_REQUEST", "symbol is required")
            volume = params.get("volume")
            if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(float(volume)):
                raise HubError("BAD_REQUEST", "volume must be a finite number")
            if float(volume) < 0.01:
                raise HubError("BAD_REQUEST", "volume must be at least 0.01")
            if method in {"create_stop_order", "create_limit_order"}:
                price = params.get("price")
                if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(float(price)):
                    raise HubError("BAD_REQUEST", "price is required for stop and limit orders")
        if method == "cancel_order" and not params.get("order_id"):
            raise HubError("BAD_REQUEST", "order_id is required")
        if method in {"close_position", "close_position_partially", "modify_position"} and not params.get("position_id"):
            raise HubError("BAD_REQUEST", "position_id is required")

    @staticmethod
    def _dup_key(engine: str, method: str, params: dict) -> tuple:
        return (
            engine,
            method,
            params.get("symbol"),
            params.get("side"),
            params.get("volume"),
            params.get("comment"),
            params.get("stop_loss"),
            params.get("take_profit"),
            params.get("price"),
            params.get("order_id"),
            params.get("position_id"),
        )

    async def _invoke(self, method: str, *args: Any) -> Any:
        func = getattr(self.broker, method)
        return await func(*args)
