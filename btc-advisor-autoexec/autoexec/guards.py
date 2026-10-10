"""Server-side guards. Pure functions over broker snapshots; no I/O.

Mechanics (Odin, 2026-10-10 05:45 ET; #6 corrected 05:47 ET; #3 replaced
05:55 ET by the second-position rule in :mod:`autoexec.second_position`):

1. MARKET entries only, SL and TP attached in the same request.
2. Max $250 risk per trade (see :mod:`autoexec.sizing`).
3. Position count: max 2 BTC positions total (manual + auto); a second one
   only under the conditions in :mod:`autoexec.second_position`.
4. Stops may only tighten, never widen; removing SL/TP is rejected.
5. Daily loss cap $500 on the auto-trader's own trades, closed + floating,
   incl. commissions and swaps, reset at midnight Europe/Prague.
6. Equity halt at or below $90,750, latched until manually re-enabled.
7. Everything logged as JSON lines (see :mod:`autoexec.jsonlog`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from .sizing import D

ALLOWED_SIDES = ("BUY", "SELL")
ALLOWED_ENTRY_TYPES = ("MARKET",)


class Rejected(Exception):
    """A guard rejected the request. ``code`` is stable for the JSON response."""

    def __init__(self, code: str, reason: str, **detail: Any) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# #1 request validation

@dataclass
class Setup:
    side: str
    entry_type: str
    stop: Decimal
    target: Decimal
    request_id: Optional[str] = None
    note: Optional[str] = None


def parse_setup(payload: Dict[str, Any]) -> Setup:
    if not isinstance(payload, dict):
        raise Rejected("BAD_REQUEST", "body must be a JSON object")
    side = str(payload.get("side") or "").strip().upper()
    if side not in ALLOWED_SIDES:
        raise Rejected("BAD_SIDE", f"side must be BUY or SELL, got {payload.get('side')!r}")
    raw_type = payload.get("entry_type", payload.get("entryType"))
    entry_type = str(raw_type or "").strip().upper()
    if entry_type != "MARKET":
        raise Rejected("ENTRY_TYPE_NOT_MARKET", f"only MARKET entries are allowed, got {raw_type!r}")
    stop_raw = payload.get("stop", payload.get("stop_price", payload.get("sl")))
    target_raw = payload.get("target", payload.get("target_price", payload.get("tp")))
    if stop_raw in (None, "", 0, "0"):
        raise Rejected("MISSING_SL", "stop price is required; orders are never sent without SL and TP")
    if target_raw in (None, "", 0, "0"):
        raise Rejected("MISSING_TP", "target price is required; orders are never sent without SL and TP")
    try:
        stop = D(stop_raw)
        target = D(target_raw)
    except Exception:
        raise Rejected("BAD_PRICE", "stop and target must be numeric")
    if stop <= 0 or target <= 0:
        raise Rejected("BAD_PRICE", "stop and target must be positive")
    rid = payload.get("request_id", payload.get("requestId"))
    return Setup(
        side=side,
        entry_type=entry_type,
        stop=stop,
        target=target,
        request_id=str(rid) if rid else None,
        note=str(payload.get("note")) if payload.get("note") else None,
    )


@dataclass
class Quote:
    bid: Decimal
    ask: Decimal

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


def parse_quote(raw: Dict[str, Any]) -> Quote:
    bid = raw.get("bid")
    ask = raw.get("ask")
    if bid is None or ask is None:
        raise Rejected("NO_QUOTE", "live quote missing bid/ask")
    q = Quote(D(bid), D(ask))
    if q.bid <= 0 or q.ask <= 0 or q.ask < q.bid:
        raise Rejected("BAD_QUOTE", f"implausible quote bid={q.bid} ask={q.ask}")
    return q


def check_levels(setup: Setup, quote: Quote) -> Decimal:
    """Validate SL/TP sides for a market fill and return the stop distance.

    BUY fills at ask; its SL triggers on bid, so the stop must be below bid.
    SELL fills at bid; its SL triggers on ask, so the stop must be above ask.
    """

    if setup.side == "BUY":
        if setup.stop >= quote.bid:
            raise Rejected("SL_WRONG_SIDE", f"BUY stop {setup.stop} must be below bid {quote.bid}")
        if setup.target <= quote.ask:
            raise Rejected("TP_WRONG_SIDE", f"BUY target {setup.target} must be above ask {quote.ask}")
        return quote.ask - setup.stop
    if setup.stop <= quote.ask:
        raise Rejected("SL_WRONG_SIDE", f"SELL stop {setup.stop} must be above ask {quote.ask}")
    if setup.target >= quote.bid:
        raise Rejected("TP_WRONG_SIDE", f"SELL target {setup.target} must be below bid {quote.bid}")
    return setup.stop - quote.bid


# ---------------------------------------------------------------------------
# #3 position classification

def _magic(p: Dict[str, Any]) -> int:
    m = p.get("magic")
    try:
        return int(m) if m is not None else 0
    except (TypeError, ValueError):
        return 0


def _comment(p: Dict[str, Any]) -> str:
    return str(p.get("comment") or p.get("brokerComment") or p.get("clientId") or "")


@dataclass
class Book:
    auto: List[Dict[str, Any]] = field(default_factory=list)
    manual: List[Dict[str, Any]] = field(default_factory=list)
    other: List[Dict[str, Any]] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        def brief(p: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": p.get("id"),
                "type": p.get("type"),
                "volume": p.get("volume"),
                "openPrice": p.get("openPrice"),
                "stopLoss": p.get("stopLoss"),
                "takeProfit": p.get("takeProfit"),
                "magic": p.get("magic"),
                "comment": _comment(p),
                "profit": p.get("profit"),
            }

        return {"auto": [brief(p) for p in self.auto], "manual": [brief(p) for p in self.manual], "other": [brief(p) for p in self.other]}


def is_auto_position(p: Dict[str, Any], *, magic: int, comment: str) -> bool:
    return _magic(p) == magic or _comment(p) == comment


def classify_positions(positions: Sequence[Dict[str, Any]], *, symbol: str, magic: int, comment: str) -> Book:
    book = Book()
    for p in positions:
        if (p.get("symbol") or "") != symbol:
            continue
        if is_auto_position(p, magic=magic, comment=comment):
            book.auto.append(p)
        elif _magic(p) == 0:
            book.manual.append(p)
        else:
            book.other.append(p)
    return book


def all_symbol_positions(book: Book) -> List[Dict[str, Any]]:
    """Every open position on the symbol, whatever its magic."""

    return list(book.auto) + list(book.manual) + list(book.other)


# ---------------------------------------------------------------------------
# #4 tighten-only

def check_tighten(position: Dict[str, Any], new_stop: Decimal, quote: Quote) -> Dict[str, Any]:
    """Return the modify levels after verifying the new stop is strictly tighter."""

    ptype = str(position.get("type") or "")
    if ptype not in ("POSITION_TYPE_BUY", "POSITION_TYPE_SELL"):
        raise Rejected("BAD_POSITION", f"unknown position type {ptype!r}")
    if new_stop <= 0:
        raise Rejected("SL_REMOVED", "a modify that removes the stop loss is rejected")
    cur_sl_raw = position.get("stopLoss")
    cur_tp_raw = position.get("takeProfit")
    cur_tp = D(cur_tp_raw) if cur_tp_raw not in (None, 0, "0", "") else Decimal("0")
    if cur_tp <= 0:
        raise Rejected("TP_MISSING_ON_POSITION", "position has no take profit; refusing a modify that would leave TP absent")
    cur_sl = D(cur_sl_raw) if cur_sl_raw not in (None, 0, "0", "") else None

    if ptype == "POSITION_TYPE_BUY":
        if cur_sl is not None and new_stop <= cur_sl:
            raise Rejected("SL_NOT_TIGHTER", f"BUY stop {new_stop} is not above current stop {cur_sl}; stops may only tighten")
        if new_stop >= quote.bid:
            raise Rejected("SL_WRONG_SIDE", f"BUY stop {new_stop} must be below bid {quote.bid}")
    else:
        if cur_sl is not None and new_stop >= cur_sl:
            raise Rejected("SL_NOT_TIGHTER", f"SELL stop {new_stop} is not below current stop {cur_sl}; stops may only tighten")
        if new_stop <= quote.ask:
            raise Rejected("SL_WRONG_SIDE", f"SELL stop {new_stop} must be above ask {quote.ask}")
    return {"positionId": str(position.get("id")), "stopLoss": float(new_stop), "takeProfit": float(cur_tp), "previousStopLoss": float(cur_sl) if cur_sl is not None else None}


# ---------------------------------------------------------------------------
# #5 daily loss cap

def _num(x: Any) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    try:
        return D(x)
    except Exception:
        return Decimal("0")


@dataclass
class DailyPnl:
    closed: Decimal
    floating: Decimal
    deals_counted: int
    positions_counted: int

    @property
    def total(self) -> Decimal:
        return self.closed + self.floating

    def as_dict(self) -> Dict[str, Any]:
        return {
            "closed": float(self.closed),
            "floating": float(self.floating),
            "total": float(self.total),
            "deals_counted": self.deals_counted,
            "positions_counted": self.positions_counted,
        }


def daily_pnl(deals: Sequence[Dict[str, Any]], auto_positions: Sequence[Dict[str, Any]], *, magic: int, comment: str) -> DailyPnl:
    """Closed P&L from today's deals (profit+commission+swap) plus floating on open auto positions."""

    closed = Decimal("0")
    n_deals = 0
    for d in deals:
        if str(d.get("type") or "").startswith("DEAL_TYPE_BALANCE") or str(d.get("type") or "") in ("DEAL_TYPE_CREDIT", "DEAL_TYPE_CHARGE", "DEAL_TYPE_CORRECTION"):
            continue
        if not is_auto_position(d, magic=magic, comment=comment):
            continue
        closed += _num(d.get("profit")) + _num(d.get("commission")) + _num(d.get("swap"))
        n_deals += 1
    floating = Decimal("0")
    for p in auto_positions:
        floating += _num(p.get("profit")) + _num(p.get("commission")) + _num(p.get("swap"))
    return DailyPnl(closed=closed, floating=floating, deals_counted=n_deals, positions_counted=len(auto_positions))


def check_daily_cap(pnl: DailyPnl, *, cap_usd: Decimal, today_iso: str, latched_day: Optional[str]) -> None:
    """Raise if the cap is latched for today or breached now (the caller latches on DAILY_CAP_HIT)."""

    if latched_day == today_iso:
        raise Rejected("DAILY_CAP_LATCHED", f"daily loss cap already hit on {today_iso}; no entries until the next Prague day", pnl=pnl.as_dict())
    if pnl.total <= -cap_usd:
        raise Rejected("DAILY_CAP_HIT", f"daily P&L {pnl.total} is at or below -{cap_usd}", pnl=pnl.as_dict())


# ---------------------------------------------------------------------------
# #6 equity halt

def check_equity_halt(equity: Decimal, *, threshold: Decimal, latched: bool) -> None:
    """Raise if halted (the caller latches the HALT file on EQUITY_HALT)."""

    if latched:
        raise Rejected("EQUITY_HALT_LATCHED", "equity halt is latched (HALT file present); manual re-enable required", equity=float(equity), threshold=float(threshold))
    if equity <= threshold:
        raise Rejected("EQUITY_HALT", f"equity {equity} is at or below the halt threshold {threshold}", equity=float(equity), threshold=float(threshold))
