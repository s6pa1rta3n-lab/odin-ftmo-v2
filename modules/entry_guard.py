"""Pure helpers that stop a market-entry engine from booking the same trade twice.

Why this exists (US100, matt-berserker, 2026-10-02 UTC):

* 15:09:48  engine in SEARCHING placed BUY 9.46 US100.cash
* 15:09:58  broker filled it -> position 172673462 @ 30826.23
* 15:10:03  hub answered ``NOT_CONNECTED`` for that same mutation
* engine logged "Failed to place order" and stayed SEARCHING without
  re-reading positions
* 15:14:17  the next trigger placed BUY 8.88 -> position 172676142 while
  172673462 was still open (hedging account, so two separate books)
* 15:24:57  172673462 hit SL for -861.81

A place error is not proof that nothing filled. The order can reach the
broker and the acknowledgement can still be lost (socket drop, hub
reconnect, RPC timeout). The functions here encode the two rules that
close that gap:

1. Never send an entry without a *fresh, successful* position read that
   shows no open position for this engine's symbol or order comment.
2. After an ambiguous place error, sync positions before any further
   entry. If a matching position appeared, that was the fill.

Everything here is side-effect free so it can be unit tested without a
hub, a broker, or an event loop.
"""

from __future__ import annotations

from typing import Iterable, Optional

# Hub error codes that are raised *before* the request reaches the broker.
# Anything else (NOT_CONNECTED, TIMEOUT, CLOSED, BROKER_ERROR, raw SDK or
# socket exceptions) leaves the fill state unknown.
NEVER_SENT_CODES = frozenset(
    {
        "ORDERS_DISABLED",
        "DRY_RUN",
        "COMMENT_REQUIRED",
        "BAD_REQUEST",
        "FORBIDDEN_SYNC",
    }
)


def position_comment(position: dict) -> str:
    """Return the broker comment on a position, tolerating both field names."""

    comment = position.get("comment")
    if not comment:
        comment = position.get("brokerComment")
    return str(comment or "")


def matching_positions(
    positions: Optional[Iterable[dict]],
    *,
    symbol: Optional[str],
    comment_prefix: Optional[str],
) -> list[dict]:
    """Return the open positions this engine must treat as its own book.

    A position matches when its symbol equals ``symbol`` *or* its comment
    starts with ``comment_prefix``. Either alone is enough: the symbol check
    catches a fill whose comment the broker rewrote, and the comment check
    catches a fill reported under a symbol alias.
    """

    if not positions:
        return []
    matched: list[dict] = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        same_symbol = bool(symbol) and position.get("symbol") == symbol
        same_comment = bool(comment_prefix) and position_comment(position).startswith(comment_prefix)
        if same_symbol or same_comment:
            matched.append(position)
    return matched


def is_ambiguous_place_error(exc: Optional[BaseException]) -> bool:
    """True when an entry failure leaves it unknown whether the broker filled.

    Only hub-side validation and policy refusals are known to have never
    reached the broker. Every other failure, including ``NOT_CONNECTED``,
    timeouts, dropped sockets, wrapped SDK errors, and unexpected exception
    types, must be followed by a position sync before another entry.
    """

    if exc is None:
        return False
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.upper() in NEVER_SENT_CODES:
        return False
    return True


def should_skip_entry(
    positions: Optional[Iterable[dict]],
    last_place_error: Optional[BaseException],
    *,
    symbol: Optional[str] = None,
    comment_prefix: Optional[str] = None,
) -> bool:
    """Decide whether a SEARCHING engine must *not* send a new market entry.

    ``positions`` is the result of the most recent position read: ``None``
    means the read failed (or has not happened), so the book cannot be
    confirmed flat. ``last_place_error`` is the error from the most recent
    entry attempt that has not yet been reconciled against a successful
    position read; it is cleared by the caller once that read succeeds.

    Skip when any of these hold:

    * the position read failed, so flatness is unknown;
    * a matching position is open (the previous "failed" order filled, or
      another process already holds the book);
    * an ambiguous place error is still unreconciled.
    """

    if positions is None:
        return True
    if matching_positions(positions, symbol=symbol, comment_prefix=comment_prefix):
        return True
    if is_ambiguous_place_error(last_place_error):
        return True
    return False


def describe_place_error(exc: BaseException) -> str:
    """Short, log-friendly rendering of a place failure (code first when present)."""

    code = getattr(exc, "code", None)
    text = str(exc)
    if isinstance(code, str) and code and not text.startswith(code):
        return f"{code}: {text}"
    return text or type(exc).__name__


__all__: list[str] = [
    "NEVER_SENT_CODES",
    "describe_place_error",
    "is_ambiguous_place_error",
    "matching_positions",
    "position_comment",
    "should_skip_entry",
]
