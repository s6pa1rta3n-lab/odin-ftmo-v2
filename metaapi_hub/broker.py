"""Broker ports.

``InMemoryBroker`` is the shadow broker and the test double. It never opens a
network connection. ``MetaApiBroker`` is the only class that imports the
MetaAPI SDK, and it does so lazily inside ``synchronize``.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from metaapi_hub.errors import (
    GatewayTimeoutError,
    HubError,
    NotConnectedError,
    TooManyRequestsError,
    classify_metaapi_error,
)

log = logging.getLogger("odin.metaapi_hub.broker")


class InMemoryBroker:
    """Process-local broker with a one-slot synchronization limit.

    The slot model is the root cause we are fixing: a second overlapping
    ``synchronize()`` raises ``TooManyRequestsError`` while the first holder
    is still connected. The hub owner must call ``synchronize`` once and keep
    that slot.
    """

    def __init__(
        self,
        *,
        max_concurrent_sync: int = 1,
        sync_delay: float = 0.0,
        rpc_delay: float = 0.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.max_concurrent_sync = max_concurrent_sync
        self.sync_delay = sync_delay
        self.rpc_delay = rpc_delay
        self._sleep = sleep or asyncio.sleep
        self._mu = asyncio.Lock()
        self._sync_inflight = 0
        self._holders = 0
        self.connected = False
        self.external_sync_held = False
        self.synchronize_calls = 0
        self.sync_attempts = 0
        self.rejected_syncs = 0
        self.close_calls = 0
        self.candle_calls = 0
        self.order_calls = 0
        self.mutation_calls = 0
        self.read_calls = 0
        self.rpc_depth = 0
        self.max_rpc_depth = 0
        self.fail_candles_remaining = 0
        self.fail_reads_remaining = 0
        self.fail_mutations_remaining = 0
        self.orders: list[dict] = []
        self.account_info: dict[str, Any] = {
            "name": "shadow",
            "server": "FTMO-Demo",
            "login": 0,
            "balance": 100000.0,
            "equity": 100000.0,
            "margin": 0.0,
            "freeMargin": 100000.0,
            "marginLevel": 0.0,
        }
        self.positions: list[dict] = []
        self.open_orders: list[dict] = []
        self.prices: dict[str, dict] = {}

    async def synchronize(self) -> None:
        """Take the single synchronization slot, or raise TooManyRequests."""

        async with self._mu:
            self.sync_attempts += 1
            # The slot stays taken until close(), even if a later RPC reports
            # "not connected". Otherwise a reconnect would open a second sync.
            slot_busy = (
                self.external_sync_held
                or self._sync_inflight >= self.max_concurrent_sync
                or self._holders >= self.max_concurrent_sync
            )
            if slot_busy:
                self.rejected_syncs += 1
                raise TooManyRequestsError(max_sync=self.max_concurrent_sync)
            self._sync_inflight += 1
        try:
            if self.sync_delay:
                await self._sleep(self.sync_delay)
            async with self._mu:
                self._holders += 1
                self.connected = True
                self.synchronize_calls += 1
        finally:
            async with self._mu:
                self._sync_inflight -= 1

    async def close(self) -> None:
        """Release the synchronization slot. Idempotent."""

        async with self._mu:
            self.close_calls += 1
            self.connected = False
            self._holders = 0

    async def get_account_information(self) -> dict:
        return await self._read(lambda: copy.deepcopy(self.account_info))

    async def get_positions(self) -> list:
        return await self._read(lambda: copy.deepcopy(self.positions))

    async def get_orders(self) -> list:
        return await self._read(lambda: copy.deepcopy(self.open_orders))

    async def get_symbol_price(self, symbol: str) -> dict:
        def _price() -> dict:
            cached = self.prices.get(symbol)
            if cached:
                return dict(cached)
            return {
                "symbol": symbol,
                "bid": 100.0,
                "ask": 100.2,
                "bidPrice": 100.0,
                "askPrice": 100.2,
            }

        return await self._read(_price)

    async def get_symbol_specification(self, symbol: str) -> dict:
        return await self._read(lambda: {"symbol": symbol, "contractSize": 1.0})

    async def calculate_margin(self, order: dict) -> dict:
        return await self._read(lambda: {"margin": 100.0, "symbol": order.get("symbol")})

    async def get_historical_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        """Return completed candles older than the current hour.

        ``fail_candles_remaining`` injects 504s for retry and single-flight tests.
        """

        async def _candles() -> list:
            self.candle_calls += 1
            if self.fail_candles_remaining > 0:
                self.fail_candles_remaining -= 1
                raise GatewayTimeoutError()
            return _sample_candles(symbol, timeframe, limit or 40)

        return await self._read(_candles, count_read=False)

    async def create_market_order(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="market")

    async def create_stop_order(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="stop")

    async def create_limit_order(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="limit")

    async def cancel_order(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="cancel")

    async def close_position(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="close")

    async def close_position_partially(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="close_partial")

    async def modify_position(self, payload: dict) -> dict:
        return await self._mutate(payload, kind="modify")

    async def _enter(self) -> None:
        async with self._mu:
            self.rpc_depth += 1
            if self.rpc_depth > self.max_rpc_depth:
                self.max_rpc_depth = self.rpc_depth

    async def _exit(self) -> None:
        async with self._mu:
            self.rpc_depth -= 1

    async def _read(self, producer: Callable[[], Any], *, count_read: bool = True) -> Any:
        await self._enter()
        try:
            if self.rpc_delay:
                await self._sleep(self.rpc_delay)
            if not self.connected:
                raise NotConnectedError()
            if self.fail_reads_remaining > 0:
                self.fail_reads_remaining -= 1
                self.connected = False
                raise NotConnectedError("not connected to broker")
            if count_read:
                self.read_calls += 1
            produced = producer()
            if asyncio.iscoroutine(produced):
                return await produced
            return produced
        finally:
            await self._exit()

    async def _mutate(self, payload: dict, *, kind: str) -> dict:
        await self._enter()
        try:
            if self.rpc_delay:
                await self._sleep(self.rpc_delay)
            self.mutation_calls += 1
            if kind in {"market", "stop", "limit"}:
                self.order_calls += 1
            if not self.connected:
                raise NotConnectedError()
            if self.fail_mutations_remaining > 0:
                self.fail_mutations_remaining -= 1
                self.connected = False
                raise NotConnectedError("not connected to broker")
            record = dict(payload)
            record["kind"] = kind
            self.orders.append(record)
            if kind == "cancel":
                return {"status": "CANCELED", "orderId": payload.get("order_id"), "dryRun": False}
            if kind in {"close", "close_partial", "modify"}:
                return {
                    "numericCode": 10009,
                    "stringCode": "TRADE_RETCODE_DONE",
                    "positionId": payload.get("position_id"),
                    "dryRun": False,
                }
            return {
                "orderId": f"ord-{self.order_calls}",
                "positionId": f"pos-{self.order_calls}",
                "numericCode": 10009,
                "stringCode": "TRADE_RETCODE_DONE",
                "openPrice": payload.get("price") or payload.get("open_price") or 0.0,
                "dryRun": False,
            }
        finally:
            await self._exit()


def _sample_candles(symbol: str, timeframe: str, count: int) -> list[dict]:
    """Build ascending historical bars that are already closed."""

    step = {
        "1m": timedelta(minutes=1),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
    }.get(timeframe, timedelta(hours=1))
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - (step * (count + 2))
    candles = []
    for index in range(count):
        stamp = start + (step * index)
        price = 100.0 + index
        candles.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "time": stamp.isoformat(),
                "open": price,
                "high": price + 2.0,
                "low": price - 2.0,
                "close": price + 1.0,
            }
        )
    return candles


class MetaApiBroker:
    """One MetaAPI streaming connection. Constructing this does not connect.

    The SDK import happens in ``synchronize`` so unit tests and shadow mode
    never load it. The token is kept on the instance and is not included in
    ``repr`` or log lines.
    """

    def __init__(self, token: str, account_id: str, *, rpc_timeout: float = 20.0) -> None:
        if not token:
            raise HubError("CONFIG", "MetaAPI token is empty")
        if not account_id:
            raise HubError("CONFIG", "MetaAPI account id is empty")
        self._token = token
        self.account_id = account_id
        self.rpc_timeout = rpc_timeout
        self._api: Any = None
        self._account: Any = None
        self._streaming: Any = None
        self._rpc: Any = None
        self.connected = False
        self.synchronize_calls = 0
        self.close_calls = 0
        self.candle_calls = 0
        self.order_calls = 0
        self.mutation_calls = 0
        self.read_calls = 0
        self.max_rpc_depth = 1
        self.orders: list[dict] = []

    def __repr__(self) -> str:
        return f"MetaApiBroker(account_id={self.account_id!r}, token=present, connected={self.connected})"

    async def synchronize(self) -> None:
        """Open exactly one streaming connection and wait until it synchronizes."""

        try:
            from metaapi_cloud_sdk import MetaApi
        except ImportError as exc:
            raise HubError(
                "SDK_MISSING",
                "metaapi_cloud_sdk is not installed; refusing to pretend this process is synchronized",
            ) from exc

        try:
            if self._streaming is None:
                self._api = MetaApi(self._token)
                self._account = await self._call(self._api.metatrader_account_api.get_account(self.account_id))
                self._streaming = self._account.get_streaming_connection()
                self._rpc = self._account.get_rpc_connection()
                await self._call(self._streaming.connect())
                await self._call(self._rpc.connect())
            await self._call(self._streaming.wait_synchronized())
        except Exception:
            await self.close()
            raise
        self.connected = True
        self.synchronize_calls += 1
        log.info("MetaAPI synchronization established for account %s", self.account_id)

    async def close(self) -> None:
        """Drop both connections so the account synchronization slot is released."""

        self.close_calls += 1
        self.connected = False
        for conn in (self._rpc, self._streaming):
            if conn is None:
                continue
            try:
                await conn.close()
            except Exception as exc:
                log.warning("Error closing MetaAPI connection: %s", type(exc).__name__)
        self._rpc = None
        self._streaming = None

    async def get_account_information(self) -> dict:
        self._require()
        self.read_calls += 1
        return await self._call(self._rpc.get_account_information())

    async def get_positions(self) -> list:
        self._require()
        self.read_calls += 1
        return await self._call(self._rpc.get_positions())

    async def get_orders(self) -> list:
        self._require()
        self.read_calls += 1
        return await self._call(self._rpc.get_orders())

    async def get_symbol_price(self, symbol: str) -> dict:
        self._require()
        self.read_calls += 1
        price = await self._call(self._rpc.get_symbol_price(symbol))
        if isinstance(price, dict):
            bid = price.get("bid", price.get("bidPrice"))
            ask = price.get("ask", price.get("askPrice"))
            price = dict(price)
            price.setdefault("bid", bid)
            price.setdefault("ask", ask)
            price.setdefault("bidPrice", bid)
            price.setdefault("askPrice", ask)
        return price

    async def get_symbol_specification(self, symbol: str) -> dict:
        self._require()
        self.read_calls += 1
        return await self._call(self._rpc.get_symbol_specification(symbol))

    async def calculate_margin(self, order: dict) -> dict:
        self._require()
        self.read_calls += 1
        return await self._call(self._rpc.calculate_margin(order))

    async def get_historical_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        """Fetch candles from the account history API.

        ``limit`` is applied by the owner after normalization. It is accepted
        here so the broker method signature matches ``InMemoryBroker``.
        """

        self._require()
        self.candle_calls += 1
        candles = await self._call(self._account.get_historical_candles(symbol, timeframe))
        return list(candles or [])

    async def create_market_order(self, payload: dict) -> dict:
        self._require()
        self._count_order()
        side = payload["side"]
        kwargs = _order_kwargs(payload)
        if side == "BUY":
            result = await self._call(
                self._rpc.create_market_buy_order(payload["symbol"], payload["volume"], **kwargs)
            )
        elif side == "SELL":
            result = await self._call(
                self._rpc.create_market_sell_order(payload["symbol"], payload["volume"], **kwargs)
            )
        else:
            raise HubError("BAD_REQUEST", f"unsupported market side {side}")
        return result

    async def create_stop_order(self, payload: dict) -> dict:
        self._require()
        self._count_order()
        kwargs = _order_kwargs(payload)
        price = payload["price"]
        if payload["side"] == "BUY":
            result = await self._call(
                self._rpc.create_stop_buy_order(payload["symbol"], payload["volume"], price, **kwargs)
            )
        elif payload["side"] == "SELL":
            result = await self._call(
                self._rpc.create_stop_sell_order(payload["symbol"], payload["volume"], price, **kwargs)
            )
        else:
            raise HubError("BAD_REQUEST", "unsupported stop side")
        return result

    async def create_limit_order(self, payload: dict) -> dict:
        self._require()
        self._count_order()
        kwargs = _order_kwargs(payload)
        price = payload["price"]
        if payload["side"] == "BUY":
            result = await self._call(
                self._rpc.create_limit_buy_order(payload["symbol"], payload["volume"], price, **kwargs)
            )
        elif payload["side"] == "SELL":
            result = await self._call(
                self._rpc.create_limit_sell_order(payload["symbol"], payload["volume"], price, **kwargs)
            )
        else:
            raise HubError("BAD_REQUEST", "unsupported limit side")
        return result

    async def cancel_order(self, payload: dict) -> dict:
        self._require()
        self.mutation_calls += 1
        await self._call(self._rpc.cancel_order(payload["order_id"]))
        return {"status": "CANCELED", "orderId": payload.get("order_id")}

    async def close_position(self, payload: dict) -> dict:
        self._require()
        self.mutation_calls += 1
        return await self._call(self._rpc.close_position(payload["position_id"]))

    async def close_position_partially(self, payload: dict) -> dict:
        self._require()
        self.mutation_calls += 1
        return await self._call(
            self._rpc.close_position_partially(payload["position_id"], payload["volume"])
        )

    async def modify_position(self, payload: dict) -> dict:
        self._require()
        self.mutation_calls += 1
        kwargs = {}
        if payload.get("stop_loss") is not None:
            kwargs["stop_loss"] = payload["stop_loss"]
        if payload.get("take_profit") is not None:
            kwargs["take_profit"] = payload["take_profit"]
        return await self._call(self._rpc.modify_position(payload["position_id"], **kwargs))

    def _require(self) -> None:
        state = getattr(self._streaming, "terminal_state", None)
        if state is not None and not getattr(state, "connected", True):
            self.connected = False
        if not self.connected or self._rpc is None:
            raise NotConnectedError("not connected to broker")

    def _count_order(self) -> None:
        self.order_calls += 1
        self.mutation_calls += 1

    async def _call(self, coro: Awaitable[Any]) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=self.rpc_timeout)
        except asyncio.TimeoutError as exc:
            raise HubError("TIMEOUT", "MetaAPI call timed out", retryable=True) from exc
        except Exception as exc:
            mapped = classify_metaapi_error(exc)
            if mapped is exc:
                raise
            raise mapped from exc


def _order_kwargs(payload: dict) -> dict:
    kwargs: dict[str, Any] = {}
    if payload.get("stop_loss") is not None:
        kwargs["stop_loss"] = payload["stop_loss"]
    if payload.get("take_profit") is not None:
        kwargs["take_profit"] = payload["take_profit"]
    if payload.get("comment"):
        kwargs["options"] = {"comment": payload["comment"]}
    return kwargs
