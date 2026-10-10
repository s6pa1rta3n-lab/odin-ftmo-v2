"""Second-position rule (Odin, 2026-10-10 05:55 ET). Replaces the earlier
"max 1 auto position / no entries while a manual BTC position is open".

Multi-symbol (Odin 2026-10-10 17:07 ET): the limit is 2 open positions TOTAL
across the allowed symbols (BTCUSD, ETHUSD, SOLUSD), manual + auto, and every
condition below is evaluated combined across those symbols. "Same side" for
the averaging-down rule means same symbol and same side.

With no position open the normal single-entry guards apply. A SECOND
position (manual + auto counted together) is allowed only if ALL hold:

1. Every existing BTC position has its SL at breakeven or better
   (long: SL >= openPrice; short: SL <= openPrice; missing SL fails), and the
   total open risk at SL — existing positions' price risk to their SL plus the
   new trade's risk including spread and round-trip commission — is <= $250.
2. The new setup's reward:risk is >= 2.0 after spread and commission, and no
   existing BTC position on the same side is in floating loss (no averaging
   down). "Fresh setup" cannot be verified server-side.
3. Combined open risk at SL fits within the remaining daily-cap room, and
   equity minus combined open risk stays above the $90,750 halt.
4. Projected margin level after entry stays >= 200 %. Since 19:07 ET the same
   bound is enforced on every entry by :mod:`autoexec.margin` (broker
   calculate-margin first, then calibration env); this check re-verifies it.
5. Max 2 positions in total, account-wide (every open position, all symbols,
   manual and auto, incl. other engines) since 19:07 ET.

Definitions used here (documented in the README):

* Existing position risk at SL = max(0, directional price distance from
  openPrice to SL) x value_per_unit x volume. At breakeven or better this is 0.
  The entry commission already charged is in the floating P&L (daily cap);
  the pending exit commission is not added (listed as an open question).
* Floating loss = MetaAPI ``profit`` on the position < 0.
* Reward per lot = (TP distance from the fill side of the quote x value)
  - spread cost - round-trip commission. Risk per lot = the sizing per-lot loss.
* Daily-cap room = cap - max(0, -(closed + floating P&L today)).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from .guards import Quote, Rejected, Setup, DailyPnl
from .sizing import D, Sizing, SpecValues


def _num(x: Any) -> Optional[Decimal]:
    if x is None or x == "":
        return None
    try:
        return D(x)
    except Exception:
        return None


def position_side(p: Dict[str, Any]) -> str:
    t = str(p.get("type") or "")
    if t == "POSITION_TYPE_BUY":
        return "BUY"
    if t == "POSITION_TYPE_SELL":
        return "SELL"
    return "UNKNOWN"


@dataclass
class ExistingRisk:
    position_id: str
    symbol: str
    side: str
    volume: Decimal
    open_price: Decimal
    stop_loss: Optional[Decimal]
    breakeven_or_better: bool
    risk_at_sl_usd: Decimal
    floating_profit: Decimal
    magic: Any
    comment: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


def existing_position_risk(p: Dict[str, Any], value_per_unit: Decimal) -> ExistingRisk:
    side = position_side(p)
    volume = _num(p.get("volume")) or Decimal("0")
    open_price = _num(p.get("openPrice")) or Decimal("0")
    sl = _num(p.get("stopLoss"))
    if sl is not None and sl <= 0:
        sl = None
    if sl is None or side == "UNKNOWN" or open_price <= 0:
        be = False
        risk = Decimal("Infinity")
    else:
        if side == "BUY":
            be = sl >= open_price
            loss_dist = open_price - sl
        else:
            be = sl <= open_price
            loss_dist = sl - open_price
        risk = max(Decimal("0"), loss_dist) * value_per_unit * volume
    return ExistingRisk(
        position_id=str(p.get("id")),
        symbol=str(p.get("symbol") or ""),
        side=side,
        volume=volume,
        open_price=open_price,
        stop_loss=sl,
        breakeven_or_better=be,
        risk_at_sl_usd=risk,
        floating_profit=_num(p.get("profit")) or Decimal("0"),
        magic=p.get("magic"),
        comment=str(p.get("comment") or p.get("brokerComment") or ""),
    )


# ---------------------------------------------------------------- #5 count

def check_max_positions(n_open: int, *, max_total: int) -> None:
    if n_open >= max_total:
        raise Rejected("MAX_POSITIONS", f"{n_open} BTC position(s) open; maximum total is {max_total}")


# ---------------------------------------------------------------- #1 breakeven + combined risk

def check_all_breakeven(existing: Sequence[ExistingRisk]) -> None:
    bad = [e for e in existing if not e.breakeven_or_better]
    if bad:
        raise Rejected(
            "SECOND_SL_NOT_BREAKEVEN",
            "every existing BTC position must have its SL at breakeven or better before a second entry",
            positions=[e.as_dict() for e in bad],
        )


def combined_open_risk(existing: Sequence[ExistingRisk], new_risk_usd: Decimal) -> Decimal:
    total = new_risk_usd
    for e in existing:
        total += e.risk_at_sl_usd
    return total


def check_combined_risk(combined: Decimal, *, max_risk_usd: Decimal) -> None:
    if combined > max_risk_usd:
        raise Rejected("SECOND_COMBINED_RISK", f"combined open risk at SL ${combined} exceeds ${max_risk_usd}", combined=float(combined))


# ---------------------------------------------------------------- #2 R:R and averaging down

def reward_per_lot(setup: Setup, quote: Quote, *, value_per_unit: Decimal, spread_cost_per_lot: Decimal, commission_per_lot: Decimal) -> Decimal:
    if setup.side == "BUY":
        dist = setup.target - quote.ask
    else:
        dist = quote.bid - setup.target
    return dist * value_per_unit - spread_cost_per_lot - commission_per_lot


def reward_risk_ratio(setup: Setup, quote: Quote, sizing: Sizing) -> "tuple[Decimal, Decimal]":
    reward = reward_per_lot(
        setup,
        quote,
        value_per_unit=sizing.value_per_unit_per_lot,
        spread_cost_per_lot=sizing.spread_cost_per_lot,
        commission_per_lot=sizing.commission_per_lot_roundtrip,
    )
    if sizing.per_lot_loss <= 0:
        return reward, Decimal("0")
    return reward, reward / sizing.per_lot_loss


def check_reward_risk(rr: Decimal, *, min_rr: Decimal) -> None:
    if rr < min_rr:
        raise Rejected("SECOND_RR_TOO_LOW", f"reward:risk {rr.quantize(Decimal('0.01'))} after costs is below {min_rr}", rr=float(rr))


def check_no_averaging_down(existing: Sequence[ExistingRisk], side: str, symbol: Optional[str] = None) -> None:
    """Reject if an existing same-symbol, same-side position is in floating loss."""

    losers = [e for e in existing if e.side == side and e.floating_profit < 0 and (symbol is None or e.symbol == symbol)]
    if losers:
        raise Rejected(
            "SECOND_AVERAGING_DOWN",
            f"existing {symbol or ''} {side} position(s) in floating loss; never averaging down".replace("  ", " "),
            positions=[e.as_dict() for e in losers],
        )


# ---------------------------------------------------------------- #3 daily room + equity buffer

def daily_cap_room(pnl: DailyPnl, *, cap_usd: Decimal) -> Decimal:
    loss_so_far = max(Decimal("0"), -pnl.total)
    return cap_usd - loss_so_far


def check_daily_room(combined: Decimal, *, room: Decimal) -> None:
    if combined > room:
        raise Rejected("SECOND_DAILY_ROOM", f"combined open risk ${combined} exceeds remaining daily-cap room ${room}", combined=float(combined), room=float(room))


def check_equity_buffer(equity: Decimal, combined: Decimal, *, halt_usd: Decimal) -> None:
    if equity - combined <= halt_usd:
        raise Rejected(
            "SECOND_EQUITY_BUFFER",
            f"equity {equity} minus combined open risk {combined} would not stay above the halt {halt_usd}",
            equity=float(equity),
            combined=float(combined),
        )


# ---------------------------------------------------------------- #4 margin

@dataclass
class MarginEstimate:
    new_margin_usd: Optional[Decimal]
    method: str
    account_margin: Decimal
    equity: Decimal
    projected_margin: Optional[Decimal]
    projected_level_pct: Optional[Decimal]
    detail: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


def estimate_margin(
    *,
    lots: Decimal,
    fill_price: Decimal,
    spec_raw: Dict[str, Any],
    spec: SpecValues,
    account: Dict[str, Any],
    margin_per_lot_override: Optional[Decimal],
    symbol_leverage: Optional[Decimal],
    use_account_leverage: bool,
) -> MarginEstimate:
    equity = _num(account.get("equity")) or Decimal("0")
    acct_margin = _num(account.get("margin")) or Decimal("0")
    detail: Dict[str, Any] = {
        "initialMargin": spec_raw.get("initialMargin"),
        "marginCurrency": spec_raw.get("marginCurrency"),
        "contractSize": spec_raw.get("contractSize"),
        "account_leverage": account.get("leverage"),
        "account_marginLevel": account.get("marginLevel"),
        "symbol_leverage_env": float(symbol_leverage) if symbol_leverage else None,
        "margin_per_lot_override": float(margin_per_lot_override) if margin_per_lot_override else None,
    }
    new_margin: Optional[Decimal] = None
    method = "unavailable"
    init_margin = _num(spec_raw.get("initialMargin"))
    margin_ccy = str(spec_raw.get("marginCurrency") or "")
    acct_ccy = str(account.get("currency") or "")
    contract = spec.contract_size

    if margin_per_lot_override is not None and margin_per_lot_override > 0:
        new_margin = margin_per_lot_override * lots
        method = "override:AUTOEXEC_MARGIN_PER_LOT_USD x lots"
    elif init_margin is not None and init_margin > 0 and (not margin_ccy or not acct_ccy or margin_ccy == acct_ccy):
        new_margin = init_margin * lots
        method = "spec.initialMargin x lots"
    elif symbol_leverage is not None and symbol_leverage > 0 and contract is not None and contract > 0:
        new_margin = lots * contract * fill_price / symbol_leverage
        method = "notional / AUTOEXEC_SYMBOL_LEVERAGE"
    elif use_account_leverage and contract is not None and contract > 0:
        lev = _num(account.get("leverage"))
        if lev is not None and lev > 0:
            new_margin = lots * contract * fill_price / lev
            method = "notional / account.leverage (opt-in; crypto leverage usually differs)"
    projected = None
    level = None
    if new_margin is not None:
        projected = acct_margin + new_margin
        level = (equity / projected * 100) if projected > 0 else None
    return MarginEstimate(new_margin, method, acct_margin, equity, projected, level, detail)


def margin_estimate_from_per_lot(*, per_lot_usd: Optional[Decimal], method: str, lots: Decimal, account: Dict[str, Any], detail: Optional[Dict[str, Any]] = None) -> MarginEstimate:
    """Build the second-position margin view from a per-lot estimate (see :mod:`autoexec.margin`)."""

    equity = _num(account.get("equity")) or Decimal("0")
    acct_margin = _num(account.get("margin")) or Decimal("0")
    if per_lot_usd is None:
        return MarginEstimate(None, method, acct_margin, equity, None, None, dict(detail or {}))
    new_margin = per_lot_usd * lots
    projected = acct_margin + new_margin
    level = (equity / projected * 100) if projected > 0 else None
    return MarginEstimate(new_margin, method, acct_margin, equity, projected, level, dict(detail or {}))


def check_margin_level(est: MarginEstimate, *, min_level_pct: Decimal) -> None:
    if est.new_margin_usd is None:
        raise Rejected(
            "SECOND_MARGIN_UNKNOWN",
            "required margin cannot be estimated (no AUTOEXEC_MARGIN_PER_LOT_USD, no spec initialMargin, no AUTOEXEC_SYMBOL_LEVERAGE); skipping",
            margin=est.as_dict(),
        )
    if est.projected_level_pct is None:
        raise Rejected("SECOND_MARGIN_UNKNOWN", "projected margin is zero; cannot compute a margin level", margin=est.as_dict())
    if est.projected_level_pct < min_level_pct:
        raise Rejected(
            "SECOND_MARGIN_LEVEL",
            f"projected margin level {est.projected_level_pct.quantize(Decimal('0.1'))}% is below {min_level_pct}%",
            margin=est.as_dict(),
        )
