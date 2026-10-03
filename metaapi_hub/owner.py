"""Single synchronization owner.

Engines never call ``synchronize``. This object does, at most one at a time.
Mutations are serialized on that connection. Reads run under a small
semaphore (``read_concurrency``) so one slow candle RPC does not hold every
account and position read for all engines behind it. Read calls may be
retried once after a disconnect and a bounded number of times after a
retryable upstream error (TIMEOUT, TooManyRequests, 504). Order calls are
never retried.

Backoff is exponential with a cap and jitter so three engines that hit the
same upstream hiccup do not retry in lockstep.

Historical candles are one flight per key. A timed-out or cancelled candle
call releases that slot even when the SDK task underneath it never finishes:
the call is abandoned instead of waiting out ``asyncio.wait_for``, and a
flight every waiter has left is dropped so the next request starts a new call.
There is no separate candle timeout; the budget is the broker's existing
``rpc_timeout``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import time
import uuid
from typing import Any, Awaitable, Callable

from metaapi_hub.locks import LazyLock, LazySemaphore
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
        backoff_max: float = 30.0,
        backoff_jitter: float = 0.25,
        candle_attempts: int = 4,
        candle_stale_ttl: float = 300.0,
        read_attempts: int = 3,
        read_concurrency: int = 4,
        duplicate_window: float = 3.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], float] | None = None,
        rand: Callable[[], float] | None = None,
    ) -> None:
        if mode not in {"shadow", "live"}:
            raise HubError("CONFIG", f"unsupported hub mode {mode}")
        if orders_mode not in {"deny", "dry_run", "live"}:
            raise HubError("CONFIG", f"unsupported orders mode {orders_mode}")
        if mode == "shadow" and orders_mode == "live":
            log.warning("Shadow mode cannot place live orders; forcing orders_mode=dry_run")
            orders_mode = "dry_run"
        if read_attempts < 1:
            raise HubError("CONFIG", "read_attempts must be at least 1")
        if candle_attempts < 1:
            raise HubError("CONFIG", "candle_attempts must be at least 1")
        if read_concurrency < 1:
            raise HubError("CONFIG", "read_concurrency must be at least 1")
        self.broker = broker
        self.mode = mode
        self.orders_mode = orders_mode
        self.account_id = account_id
        self.cache_ttl = cache_ttl
        self.max_sync_attempts = max_sync_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.backoff_jitter = max(0.0, backoff_jitter)
        self.candle_attempts = candle_attempts
        self.candle_stale_ttl = candle_stale_ttl
        self.read_attempts = read_attempts
        self.read_concurrency = read_concurrency
        self.duplicate_window = duplicate_window
        self._sleep = sleep or asyncio.sleep
        self._clock = clock or time.monotonic
        self._rand = rand or random.random
        self.connected = False
        self.synchronize_calls = 0
        self.sync_attempts = 0
        self.reconnects = 0
        self.candle_fetches = 0
        self.candle_timeouts = 0
        self.candle_retries = 0
        self.candle_stale_serves = 0
        self.abandoned_calls = 0
        self.candle_flights_released = 0
        self.read_retries = 0
        self.single_flight_joins = 0
        self.cache_hits = 0
        self.duplicate_suppressions = 0
        self.last_upstream_error: str | None = None
        self._epoch = 0
        self._sync_lock = LazyLock()
        self._rpc_lock = LazyLock()
        self._read_gate = LazySemaphore(read_concurrency)
        self._flight_lock = LazyLock()
        self._inflight: dict[tuple, _Flight] = {}
        self._orphans: set[asyncio.Task] = set()
        self._cache: dict[tuple, tuple[float, list]] = {}
        self._last_good: dict[tuple, tuple[float, list]] = {}
        self._recent_mutations: dict[tuple, tuple[float, dict]] = {}
        self.clients: dict[str, dict] = {}

    def backoff_delay(self, attempt: int) -> float:
        """Exponential delay for ``attempt`` (1-based), capped, plus jitter.

        ``jitter`` adds up to ``backoff_jitter`` of the capped delay. With
        ``rand`` pinned to 0 the schedule is exactly ``base * 2**(n-1)``.
        """

        delay = min(self.backoff_base * (2 ** (attempt - 1)), self.backoff_max)
        return delay + delay * self.backoff_jitter * self._rand()

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
            "candle_retries": self.candle_retries,
            "candle_stale_serves": self.candle_stale_serves,
            "abandoned_calls": self.abandoned_calls,
            "candle_flights_released": self.candle_flights_released,
            "abandoned_calls_pending": len(self._orphans),
            "read_retries": self.read_retries,
            "read_concurrency": self.read_concurrency,
            "last_upstream_error": self.last_upstream_error,
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
                self.last_upstream_error = f"sync: {exc}"
                delay = self.backoff_delay(attempt)
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

    async def read(
        self,
        method: str,
        *args: Any,
        attempts: int | None = None,
        release_on_cancel: bool = False,
    ) -> Any:
        """Run a read RPC. Never opens a second slot.

        * ``NotConnectedError`` triggers one shared reconnect, then one resend.
        * Other retryable errors (TIMEOUT, TooManyRequests, 504) are resent up
          to ``attempts`` times (default ``read_attempts``) with jittered
          backoff. Reads are idempotent, so this cannot double-fill.
        * ``release_on_cancel`` is set for historical candles. The broker call
          then runs as its own task: cancellation, and the broker's existing
          ``rpc_timeout`` when it has one, abandon that task instead of waiting
          for it. Other reads are unchanged.
        """

        total = self.read_attempts if attempts is None else max(1, attempts)
        for attempt in range(1, total + 1):
            await self.ensure_connected()
            epoch = self._epoch
            try:
                try:
                    async with self._read_gate:
                        return await self._invoke_read(method, args, release_on_cancel=release_on_cancel)
                except NotConnectedError:
                    log.warning("Read %s saw 'not connected to broker'; one shared reconnect", method)
                    await self._recover(epoch)
                    async with self._read_gate:
                        return await self._invoke_read(method, args, release_on_cancel=release_on_cancel)
            except HubError as exc:
                self.last_upstream_error = f"{method}: {exc}"
                if not exc.retryable or isinstance(exc, NotConnectedError) or attempt >= total:
                    raise
                self.read_retries += 1
                delay = self.backoff_delay(attempt)
                log.warning(
                    "Read %s failed attempt %s/%s (%s). Retrying in %.2fs. The slot is kept; no new sync.",
                    method,
                    attempt,
                    total,
                    exc,
                    delay,
                )
                await self._sleep(delay)
        raise AssertionError("unreachable")

    async def historical_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        """Single-flight candle fetch with a short cache, backoff, and a stale fallback.

        Joiners await the shared flight through ``asyncio.shield`` so one
        engine giving up (its ``wait_for`` expired, or its socket closed)
        cannot cancel the fetch the other engines are still waiting on.

        The slot is released even when the SDK task does not finish:

        * the broker call is abandoned, not awaited, when its caller is
          cancelled or when the broker's existing ``rpc_timeout`` expires;
        * when the last waiter leaves before the flight finishes, the flight
          is dropped from the slot without waiting for it, so the next request
          starts a new call instead of joining a fetch nobody is waiting for.
        """

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
            flight = self._inflight.get(key)
            if flight is None or flight.task.done():
                # A finished task can linger here when every waiter was
                # cancelled before it completed. Never hand out its old result.
                task = asyncio.get_running_loop().create_task(
                    self._load_candles(key, symbol, timeframe, limit)
                )
                task.add_done_callback(_consume_task_result)
                flight = _Flight(task)
                self._inflight[key] = flight
            else:
                self.single_flight_joins += 1
            flight.waiters += 1
        try:
            result = await asyncio.shield(flight.task)
            return [dict(item) for item in result]
        finally:
            # No await here: a second cancellation while leaving must not
            # skip the bookkeeping that frees the slot.
            self._leave_flight(key, flight)

    def _leave_flight(self, key: tuple, flight: "_Flight") -> None:
        flight.waiters -= 1
        if flight.task.done():
            if self._inflight.get(key) is flight:
                self._inflight.pop(key, None)
            return
        if flight.waiters > 0:
            return
        # Every caller timed out or was cancelled. Release the slot now and
        # do not wait for the task: on Python 3.9 asyncio.wait_for inside the
        # SDK path only returns once the cancelled SDK task finishes, which is
        # the hang seen live (candle_retries frozen at 2, attempt 3 never
        # logged). The next request must be free to start a new call.
        if self._inflight.get(key) is flight:
            self._inflight.pop(key, None)
        self.candle_flights_released += 1
        flight.task.cancel()
        log.warning(
            "Historical candles %s %s: every waiter left before the flight finished; "
            "slot released, flight cancelled and not awaited (released=%s)",
            key[0],
            key[1],
            self.candle_flights_released,
        )

    def _rpc_timeout(self) -> float | None:
        """The broker's existing RPC budget, if it has one. Not a new setting."""

        raw = getattr(self.broker, "rpc_timeout", None)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        if raw <= 0:
            return None
        return float(raw)

    async def _invoke_read(self, method: str, args: tuple, *, release_on_cancel: bool) -> Any:
        """Run one broker read.

        Candle reads pass ``release_on_cancel``. The call is its own task, so
        a cancel or the existing ``rpc_timeout`` returns without waiting for
        an SDK task that ignores cancellation. ``asyncio.wait_for`` does not:
        on Python 3.9 it returns only after that task finishes. Every other
        read awaits the broker directly, as before.
        """

        if not release_on_cancel:
            return await self._invoke(method, *args)
        budget = self._rpc_timeout()
        inner = asyncio.get_running_loop().create_task(self._invoke(method, *args))
        try:
            done, _ = await asyncio.wait({inner}, timeout=budget)
        except asyncio.CancelledError:
            self._abandon(inner, method, "caller cancelled")
            raise
        if inner in done:
            return inner.result()
        self._abandon(inner, method, f"exceeded the RPC timeout of {budget:.0f}s")
        raise HubError(
            "TIMEOUT",
            f"{method} exceeded the RPC timeout of {budget:.0f}s; the SDK call was abandoned",
            retryable=True,
        )

    def _abandon(self, inner: asyncio.Task, method: str, why: str) -> None:
        """Cancel a broker call and stop tracking it without awaiting it."""

        if inner.done():
            return
        self.abandoned_calls += 1
        self._orphans.add(inner)
        inner.add_done_callback(self._orphan_finished)
        inner.cancel()
        log.warning(
            "Abandoning %s (%s). Not waiting for the SDK task to finish; abandoned=%s pending=%s",
            method,
            why,
            self.abandoned_calls,
            len(self._orphans),
        )

    def _orphan_finished(self, inner: asyncio.Task) -> None:
        self._orphans.discard(inner)
        if inner.cancelled():
            return
        exc = inner.exception()
        if exc is not None:
            log.info("Abandoned SDK call finished later with %s; pending=%s", type(exc).__name__, len(self._orphans))

    async def _load_candles(self, key: tuple, symbol: str, timeframe: str, limit: int | None) -> list:
        last: BaseException | None = None
        for attempt in range(1, self.candle_attempts + 1):
            try:
                # Candle retries are owned here so the schedule is one loop,
                # not read_attempts * candle_attempts.
                raw = await self.read(
                    "get_historical_candles",
                    symbol,
                    timeframe,
                    limit,
                    attempts=1,
                    release_on_cancel=True,
                )
                self.candle_fetches += 1
                normalized = normalize_candles(raw, limit)
                now = self._clock()
                self._cache[key] = (now, normalized)
                self._last_good[key] = (now, normalized)
                return [dict(item) for item in normalized]
            except HubError as exc:
                if not exc.retryable or isinstance(exc, NotConnectedError):
                    raise
                last = exc
                if isinstance(exc, GatewayTimeoutError):
                    self.candle_timeouts += 1
                if attempt >= self.candle_attempts:
                    break
                self.candle_retries += 1
                delay = self.backoff_delay(attempt)
                log.warning(
                    "Historical candles %s %s failed attempt %s/%s (%s); retrying in %.3fs",
                    symbol,
                    timeframe,
                    attempt,
                    self.candle_attempts,
                    exc,
                    delay,
                )
                await self._sleep(delay)
        assert last is not None
        stale = self._last_good.get(key)
        if stale is not None:
            age = self._clock() - stale[0]
            if age <= self.candle_stale_ttl:
                self.candle_stale_serves += 1
                log.warning(
                    "Historical candles %s %s unavailable after %s attempts (%s). "
                    "Serving last good set from %.0fs ago (%d bars). Engines keep running; "
                    "a fresh fetch is attempted on their next poll.",
                    symbol,
                    timeframe,
                    self.candle_attempts,
                    last,
                    age,
                    len(stale[1]),
                )
                return [dict(item) for item in stale[1]]
        log.error(
            "Historical candles %s %s failed after %s attempts and no recent good set is cached: %s",
            symbol,
            timeframe,
            self.candle_attempts,
            last,
        )
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


class _Flight:
    """One in-flight candle fetch and the number of callers awaiting it."""

    __slots__ = ("task", "waiters")

    def __init__(self, task: asyncio.Task) -> None:
        self.task = task
        self.waiters = 0


def _consume_task_result(task: asyncio.Task) -> None:
    """Mark a shared flight's outcome as observed when every waiter already left."""

    if not task.cancelled():
        task.exception()
