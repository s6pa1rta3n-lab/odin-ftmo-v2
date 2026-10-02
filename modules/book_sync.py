"""Adopt an already-open broker position on engine startup and after a hub reconnect.

Why this exists (US100, matt-berserker, 2026-10-02):

The double-book guard (``modules/entry_guard.py``) was deployed and
``griff_engine_us100`` was restarted at ~11:45 ET while the broker still held
BUY ticket 172676142 (US100.cash 8.88 @ 30807.38, SL/TP set). The new process
started in ``SEARCHING``. The only code that read positions while
``SEARCHING`` was the pre-entry check, and that only runs inside the 09:45 to
11:30 ET window. Outside the window the engine made no broker call at all, so
it never learned about the open ticket:

* the 16:00 ET hard close is gated on ``state == "IN_TRADE"`` and would not
  have fired, leaving an intraday index position open overnight;
* the next day's first trigger would have gone through the pre-entry check,
  which adopts, so a second entry was unlikely but the overnight gap was not.

The fix is a sync that does not depend on the session window: on the first
loop iteration after startup, and whenever the hub client has reattached,
read open positions and adopt the one that belongs to this book.

Rules, shared by every market-entry engine:

1. Read positions through the wrapper. A failed read is *unknown*, never
   *flat*: the sync stays pending and is retried on the next iteration, and
   while it is pending no setup may be evaluated.
2. If one matching position is open, adopt it as ``IN_TRADE`` using the
   broker's ticket, size, SL, and TP. Nothing is placed, closed, or modified.
3. If more than one matching position is open, adopt the first and log the
   rest. ``IN_TRADE`` is still the only safe state: it blocks new entries.
4. If none is open and the engine is ``SEARCHING``, stay ``SEARCHING``.
   Returning ``IN_TRADE`` to ``SEARCHING`` on an empty read is left to the
   engine's own ``IN_TRADE`` branch so there is exactly one place that does it.

Everything here that is not the position read is side-effect free.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from modules.entry_guard import matching_positions, position_comment

PositionReader = Callable[[], Awaitable[Any]]


def position_direction(position: dict) -> str:
    """``BUY`` or ``SELL`` from a MetaAPI position ``type``."""

    kind = str(position.get("type") or "").upper()
    if "SELL" in kind:
        return "SELL"
    return "BUY"


def _float_or_none(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def adopted_position_record(position: dict, *, symbol: Optional[str] = None, comment: Optional[str] = None) -> dict:
    """Normalise a broker position into the record engines keep as ``active_position``.

    Every field comes from the broker. ``symbol`` and ``comment`` are only
    fallbacks for a position reported without them. The record carries both
    ``type`` (MetaAPI spelling) and ``direction`` so the engines that read
    either keep working.
    """

    record_symbol = position.get("symbol") or symbol
    record_comment = position_comment(position) or (comment or "")
    direction = position_direction(position)
    return {
        "id": str(position.get("id") or ""),
        "symbol": record_symbol,
        "type": position.get("type") or ("POSITION_TYPE_SELL" if direction == "SELL" else "POSITION_TYPE_BUY"),
        "direction": direction,
        "volume": _float_or_none(position.get("volume")),
        "openPrice": _float_or_none(position.get("openPrice")),
        "stopLoss": _float_or_none(position.get("stopLoss")),
        "takeProfit": _float_or_none(position.get("takeProfit")),
        "comment": record_comment,
    }


def choose_position_to_adopt(matched: Optional[list[dict]]) -> tuple[Optional[dict], list[dict]]:
    """Return ``(position_to_manage, extra_positions)`` from a matching-position list."""

    if not matched:
        return None, []
    return matched[0], list(matched[1:])


def describe_position(position: Optional[dict]) -> str:
    """Log-friendly one-liner: ticket, side, size, open, SL, TP, comment."""

    if not position:
        return "<none>"
    return (
        f"ticket {position.get('id')} {position_direction(position)} {position.get('volume')} "
        f"{position.get('symbol')} @ {position.get('openPrice')} "
        f"SL={position.get('stopLoss')} TP={position.get('takeProfit')} "
        f"comment={position_comment(position) or position.get('comment')!r}"
    )


def hub_reattach_count(wrapper: Any) -> Optional[int]:
    """``wrapper.client.reattaches`` on the hub path, ``None`` on the direct SDK path."""

    client = getattr(wrapper, "client", None)
    count = getattr(client, "reattaches", None)
    if isinstance(count, bool) or not isinstance(count, int):
        return None
    return count


class BookResyncTracker:
    """Decide when the broker book must be re-read, independent of any session window.

    A resync is due on the first iteration after construction (startup),
    after the engine re-ran its own ``connect()``, and whenever the hub
    client's reattach counter has moved since the last successful sync.
    ``mark_synced`` is only called after a *successful* position read, so a
    failed read keeps the resync due.
    """

    def __init__(self) -> None:
        self.startup_pending = True
        self.reconnect_reason: Optional[str] = None
        self.last_reattaches: Optional[int] = None
        self.syncs_completed = 0

    def note_reconnect(self, reason: str = "engine reconnected") -> None:
        self.reconnect_reason = reason

    def resync_reason(self, wrapper: Any) -> Optional[str]:
        if self.startup_pending:
            return "engine startup"
        if self.reconnect_reason:
            return self.reconnect_reason
        reattaches = hub_reattach_count(wrapper)
        if reattaches is not None and self.last_reattaches is not None and reattaches != self.last_reattaches:
            return f"hub reconnect (reattaches {self.last_reattaches} -> {reattaches})"
        return None

    @property
    def pending(self) -> bool:
        return self.startup_pending or self.reconnect_reason is not None

    def mark_synced(self, wrapper: Any) -> None:
        self.startup_pending = False
        self.reconnect_reason = None
        self.last_reattaches = hub_reattach_count(wrapper)
        self.syncs_completed += 1


class BrokerBookSync:
    """Startup / reconnect adoption for one engine's book.

    The engine owns the state machine. This object owns the position read,
    the consecutive-failure counter, and the "is a resync due" decision, and
    it hands back a plain result the engine applies. It never calls anything
    on the wrapper except ``get_positions_rest``.
    """

    def __init__(
        self,
        *,
        book_name: str,
        symbol: Optional[str],
        comment_prefix: Optional[str],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.book_name = book_name
        self.symbol = symbol
        self.comment_prefix = comment_prefix
        self.log = logger or logging.getLogger(f"odin.book_sync.{book_name}")
        self.tracker = BookResyncTracker()
        self.read_failures = 0
        self.adoptions = 0

    def note_reconnect(self, reason: str = "engine reconnected") -> None:
        self.tracker.note_reconnect(reason)

    def resync_reason(self, wrapper: Any) -> Optional[str]:
        return self.tracker.resync_reason(wrapper)

    @property
    def pending(self) -> bool:
        return self.tracker.pending

    async def read_book(self, wrapper: Any) -> Optional[list[dict]]:
        """Return this book's open positions, or ``None`` when the read failed.

        ``None`` must be treated as unknown by every caller.
        """

        try:
            positions = await wrapper.get_positions_rest()
        except Exception as exc:
            self.read_failures += 1
            self.log.error(
                f"{self.book_name} position read failed ({self.read_failures} consecutive): {exc}. "
                "Book state is unknown; not treating this as flat."
            )
            return None
        if self.read_failures:
            self.log.info(f"{self.book_name} position read recovered after {self.read_failures} consecutive failures.")
        self.read_failures = 0
        return matching_positions(positions, symbol=self.symbol, comment_prefix=self.comment_prefix)

    async def sync(self, wrapper: Any, *, reason: str, current_state: str) -> dict:
        """Read the book once and say what the engine should do.

        Returns a dict with ``ok`` (read succeeded), ``matched`` (list or
        ``None``), ``adopt`` (the position to manage, or ``None``) and
        ``extras`` (other matching positions). On success the resync is
        marked done; on failure it stays due so the next iteration retries.
        """

        matched = await self.read_book(wrapper)
        if matched is None:
            self.log.warning(
                f"{self.book_name} book sync ({reason}) could not read positions; "
                f"state {current_state} unchanged, retrying next iteration. No order will be placed until a read succeeds."
            )
            return {"ok": False, "matched": None, "adopt": None, "extras": []}

        self.tracker.mark_synced(wrapper)
        adopt, extras = choose_position_to_adopt(matched)
        if adopt is None:
            self.log.info(f"{self.book_name} book sync ({reason}): broker shows no open {self.book_name} position; state {current_state}.")
        else:
            self.adoptions += 1
            if extras:
                self.log.error(
                    f"{len(matched)} open {self.book_name} positions found ({[p.get('id') for p in matched]}). "
                    "Managing the first and never adding to the book."
                )
        return {"ok": True, "matched": matched, "adopt": adopt, "extras": extras}


__all__: list[str] = [
    "BookResyncTracker",
    "BrokerBookSync",
    "adopted_position_record",
    "choose_position_to_adopt",
    "describe_position",
    "hub_reattach_count",
    "position_direction",
]
