"""Socket message helpers. Newline-delimited JSON, no secrets."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

MAX_MESSAGE_BYTES = 8_000_000
FORBIDDEN_CLIENT_METHODS = frozenset(
    {
        "synchronize",
        "wait_synchronized",
        "connect",
        "get_streaming_connection",
        "get_rpc_connection",
    }
)
MUTATING_METHODS = frozenset(
    {
        "create_market_order",
        "create_stop_order",
        "create_limit_order",
        "cancel_order",
        "close_position",
        "close_position_partially",
        "modify_position",
    }
)


def json_default(value: Any) -> Any:
    """Serialize the few non-JSON types the SDK returns."""

    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps(payload: dict) -> bytes:
    """Encode one hub message, including the trailing newline."""

    data = json.dumps(payload, default=json_default, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_MESSAGE_BYTES:
        raise HubPayloadTooLarge(len(data))
    return data + b"\n"


def loads(line: bytes) -> dict:
    """Decode one hub message."""

    if len(line) > MAX_MESSAGE_BYTES:
        raise HubPayloadTooLarge(len(line))
    text = line.decode("utf-8").strip()
    if not text:
        raise ValueError("empty hub message")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("hub message must be a JSON object")
    return value


class HubPayloadTooLarge(ValueError):
    """A single socket message exceeded ``MAX_MESSAGE_BYTES``."""

    def __init__(self, size: int) -> None:
        super().__init__(f"hub message is {size} bytes")
        self.size = size


def candle_sort_key(candle: dict) -> str:
    """Sort key that accepts ISO strings and datetimes."""

    stamp = candle.get("time")
    if isinstance(stamp, datetime):
        return stamp.isoformat()
    return str(stamp or "")


def normalize_candles(candles: list | None, limit: int | None = None) -> list:
    """Return candles in ascending time order, optionally the newest ``limit``.

    Engines index ``[-1]`` as the latest bar and ``[i - 1]`` as the previous
    bar. The hub normalizes order so BTC, US100, and Gold see the same shape.
    Direct ``MetaApiWrapper`` behavior is unchanged when the hub is off.
    """

    normalized: list[dict] = []
    for candle in candles or []:
        item = dict(candle)
        stamp = item.get("time")
        if isinstance(stamp, datetime):
            item["time"] = stamp.isoformat()
        normalized.append(item)
    normalized.sort(key=candle_sort_key)
    if limit is not None:
        if limit < 0:
            raise ValueError("candle limit must be >= 0")
        if limit == 0:
            return []
        normalized = normalized[-int(limit) :]
    return normalized
