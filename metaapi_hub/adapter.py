"""Drop-in wrapper so existing engines call the hub instead of MetaAPI.

The public surface matches the methods BTC, US100, and Gold already use on
``MetaApiWrapper``. When this adapter is in use it does not import
``metaapi_cloud_sdk`` and it does not call ``wait_synchronized``.
"""

from __future__ import annotations

import logging
from typing import Any

from metaapi_hub.client import HubClient

log = logging.getLogger("odin.metaapi_hub.adapter")


def to_mt5(symbol: str | None) -> str | None:
    """Same symbol mapping as ``MetaApiWrapper._to_mt5``."""

    if not symbol:
        return None
    if symbol == "DOTUSDT":
        return "DOTUSD"
    return symbol.replace("USDT", "USD")


class HubBackedWrapper:
    """Engine-facing stand-in for ``MetaApiWrapper``."""

    def __init__(
        self,
        token: str | None,
        account_id: str,
        *,
        engine_name: str,
        socket_path: str | None = None,
        shadow: bool = False,
    ) -> None:
        # The token is accepted so call sites stay unchanged. It is not stored
        # and it is not sent to the hub. The hub process loads its own config.
        del token
        self.account_id = account_id
        self.engine_name = engine_name
        self.shadow = shadow
        self.socket_path = socket_path or _default_socket_path()
        self.client = HubClient(
            self.socket_path,
            engine_name=engine_name,
            account_id=account_id,
            expects_mode="shadow" if shadow else "on",
        )
        self.connection: ConnectionProxy | None = None
        self.account: AccountProxy | None = None
        self.streaming_connection: StreamingProxy | None = None
        self.local_synchronize_calls = 0
        self._detached = False

    def __repr__(self) -> str:
        return (
            f"HubBackedWrapper(engine={self.engine_name!r}, account_id={self.account_id!r}, "
            f"shadow={self.shadow}, socket={self.socket_path!r})"
        )

    async def connect(self) -> bool:
        """Attach to the hub. Does not synchronize this process."""

        self._detached = False
        await self.client.connect()
        self.connection = ConnectionProxy(self)
        self.account = AccountProxy(self)
        self.streaming_connection = StreamingProxy(self)
        self.local_synchronize_calls = self.client.local_synchronize_calls
        log.info("Engine %s attached to MetaAPI hub without a local synchronization", self.engine_name)
        return True

    def _to_mt5(self, symbol: str | None) -> str | None:
        return to_mt5(symbol)

    async def get_positions(self) -> list:
        return await self.client.request("positions", {})

    async def get_positions_rest(self) -> list:
        return await self.get_positions()

    async def get_account_information(self) -> dict:
        return await self.client.request("account_information", {})

    async def get_account_information_rest(self) -> dict:
        return await self.get_account_information()

    async def get_orders_rest(self) -> list:
        return await self.client.request("orders", {})

    async def cancel_order(self, order_id: str) -> dict:
        return await self.client.request("cancel_order", {"order_id": order_id})

    async def detach(self) -> None:
        """Drop this engine's subscription. The shared synchronization stays up."""

        if self._detached:
            return
        self._detached = True
        await self.client.close()


class ConnectionProxy:
    """Methods engines call on ``wrapper.connection``."""

    def __init__(self, wrapper: HubBackedWrapper) -> None:
        self._wrapper = wrapper

    def __bool__(self) -> bool:
        return not self._wrapper._detached

    async def close(self) -> None:
        await self._wrapper.detach()

    async def get_historical_candles(self, symbol: str, timeframe: str = "1h", *args: Any, **kwargs: Any) -> list:
        # Gold currently passes startTime=None. That keyword is not part of the
        # account history call the other engines use. Ignore it on the hub path
        # so the engine source can stay unchanged.
        del args
        limit = kwargs.get("limit")
        return await self._wrapper.client.request(
            "historical_candles",
            {"symbol": symbol, "timeframe": timeframe, "limit": limit},
        )

    async def get_symbol_price(self, symbol: str) -> dict:
        return await self._wrapper.client.request("symbol_price", {"symbol": symbol})

    async def get_symbol_specification(self, symbol: str) -> dict:
        return await self._wrapper.client.request("symbol_specification", {"symbol": symbol})

    async def calculate_margin(self, order: dict) -> dict:
        return await self._wrapper.client.request("calculate_margin", {"order": order})

    async def get_positions(self) -> list:
        return await self._wrapper.get_positions()

    async def get_orders(self) -> list:
        return await self._wrapper.get_orders_rest()

    async def get_account_information(self) -> dict:
        return await self._wrapper.get_account_information()

    async def create_market_buy_order(self, symbol: str, volume: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("BUY", symbol, volume, None, stop_loss, take_profit, options, "create_market_order")

    async def create_market_sell_order(self, symbol: str, volume: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("SELL", symbol, volume, None, stop_loss, take_profit, options, "create_market_order")

    async def create_stop_buy_order(self, symbol: str, volume: float, price: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("BUY", symbol, volume, price, stop_loss, take_profit, options, "create_stop_order")

    async def create_stop_sell_order(self, symbol: str, volume: float, price: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("SELL", symbol, volume, price, stop_loss, take_profit, options, "create_stop_order")

    async def create_limit_buy_order(self, symbol: str, volume: float, price: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("BUY", symbol, volume, price, stop_loss, take_profit, options, "create_limit_order")

    async def create_limit_sell_order(self, symbol: str, volume: float, price: float, stop_loss: float | None = None, take_profit: float | None = None, options: dict | None = None) -> dict:
        return await self._entry("SELL", symbol, volume, price, stop_loss, take_profit, options, "create_limit_order")

    async def close_position(self, position_id: str) -> dict:
        return await self._wrapper.client.request("close_position", {"position_id": position_id})

    async def close_position_partially(self, position_id: str, volume: float) -> dict:
        return await self._wrapper.client.request(
            "close_position_partially",
            {"position_id": position_id, "volume": volume},
        )

    async def modify_position(self, position_id: str, stop_loss: float | None = None, take_profit: float | None = None) -> dict:
        return await self._wrapper.client.request(
            "modify_position",
            {"position_id": position_id, "stop_loss": stop_loss, "take_profit": take_profit},
        )

    async def cancel_order(self, order_id: str) -> dict:
        return await self._wrapper.cancel_order(order_id)

    async def _entry(self, side: str, symbol: str, volume: float, price: float | None, stop_loss: float | None, take_profit: float | None, options: dict | None, method: str) -> dict:
        comment = None
        if isinstance(options, dict):
            comment = options.get("comment") or options.get("clientId")
        return await self._wrapper.client.request(
            method,
            {
                "side": side,
                "symbol": symbol,
                "volume": volume,
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "comment": comment,
            },
        )


class AccountProxy:
    """Methods engines call on ``wrapper.account``."""

    def __init__(self, wrapper: HubBackedWrapper) -> None:
        self._wrapper = wrapper

    def __bool__(self) -> bool:
        return not self._wrapper._detached

    async def get_historical_candles(self, symbol: str, timeframe: str = "1h", *args: Any, **kwargs: Any) -> list:
        return await self._wrapper.connection.get_historical_candles(symbol, timeframe, *args, **kwargs)  # type: ignore[union-attr]


class _TerminalState:
    def __init__(self, wrapper: HubBackedWrapper) -> None:
        self._wrapper = wrapper

    @property
    def connected(self) -> bool:
        return not self._wrapper._detached


class StreamingProxy:
    """Present so engines that close the streaming connection do not kill the hub.

    ``close`` unsubscribes this engine only.
    """

    def __init__(self, wrapper: HubBackedWrapper) -> None:
        self._wrapper = wrapper
        self.terminal_state = _TerminalState(wrapper)

    def __bool__(self) -> bool:
        return not self._wrapper._detached

    async def close(self) -> None:
        await self._wrapper.detach()


def _default_socket_path() -> str:
    import os

    return os.environ.get("ODIN_METAAPI_HUB_SOCKET", "/tmp/odin-metaapi-hub.sock")
