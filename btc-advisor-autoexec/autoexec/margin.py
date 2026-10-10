"""Margin estimate and the margin cap (Odin 2026-10-10 19:07 ET, mechanic #3).

After ANY entry (first or second) the projected margin level
``equity / (account.margin + new_margin) x 100`` must stay >= 200 %. Lots are
shrunk (floored to the volume step) until it holds; if even the minimum lot
breaks it the entry is skipped. If the margin per lot cannot be computed the
entry is skipped. The estimate and its method are logged on every decision.

Margin per lot, first available wins:

1. ``metaapi.calculate-margin`` — broker-reported margin for the probe volume
   (MetaAPI ``POST .../calculate-margin``; read-only), divided by that volume.
2. ``AUTOEXEC_MARGIN_PER_LOT_USD[_<SYMBOL>]`` — explicit calibration.
3. ``spec.initialMargin`` when > 0 and in the account currency.
4. notional / ``AUTOEXEC_SYMBOL_LEVERAGE[_<SYMBOL>]``.
5. notional / ``account.leverage`` only if ``AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE=1``.

Hedged-margin relief is ignored (projected margin is treated as additive).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from .sizing import D, SizingError, SpecValues, floor_to_step


def _num(x: Any) -> Optional[Decimal]:
    if x is None or x == "":
        return None
    try:
        return D(x)
    except Exception:
        return None


@dataclass
class MarginPerLot:
    per_lot_usd: Optional[Decimal]
    method: str
    detail: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {"per_lot_usd": float(self.per_lot_usd) if self.per_lot_usd is not None else None, "method": self.method, "detail": self.detail}


def margin_per_lot(
    *,
    symbol: str,
    side: str,
    probe_lots: Decimal,
    fill_price: Decimal,
    spec_raw: Dict[str, Any],
    spec: SpecValues,
    account: Dict[str, Any],
    margin_per_lot_override: Optional[Decimal],
    symbol_leverage: Optional[Decimal],
    use_account_leverage: bool,
    broker_calc: Optional[Callable[[str, str, float, float], Dict[str, Any]]] = None,
) -> MarginPerLot:
    """Margin required per 1.0 lot in account currency, or None with the reasons tried."""

    detail: Dict[str, Any] = {
        "probe_lots": float(probe_lots),
        "fill_price": float(fill_price),
        "initialMargin": spec_raw.get("initialMargin"),
        "marginCurrency": spec_raw.get("marginCurrency"),
        "contractSize": spec_raw.get("contractSize"),
        "account_leverage": account.get("leverage"),
        "account_margin": account.get("margin"),
        "account_marginLevel": account.get("marginLevel"),
        "symbol_leverage_env": float(symbol_leverage) if symbol_leverage else None,
        "margin_per_lot_override": float(margin_per_lot_override) if margin_per_lot_override else None,
        "tried": [],
    }
    if broker_calc is not None and probe_lots > 0:
        order_type = "ORDER_TYPE_BUY" if side == "BUY" else "ORDER_TYPE_SELL"
        try:
            res = broker_calc(symbol, order_type, float(probe_lots), float(fill_price))
            margin = _num(res.get("margin")) if isinstance(res, dict) else None
            detail["broker_calc"] = res if isinstance(res, dict) else {"raw": str(res)[:200]}
            if margin is not None and margin > 0:
                return MarginPerLot(margin / probe_lots, "metaapi.calculate-margin", detail)
            detail["tried"].append("metaapi.calculate-margin: no positive margin in response")
        except Exception as exc:  # BrokerError after retries, or a malformed payload
            detail["tried"].append(f"metaapi.calculate-margin: {type(exc).__name__}: {str(exc)[:200]}")
    if margin_per_lot_override is not None and margin_per_lot_override > 0:
        return MarginPerLot(margin_per_lot_override, "override:AUTOEXEC_MARGIN_PER_LOT_USD", detail)
    init_margin = _num(spec_raw.get("initialMargin"))
    margin_ccy = str(spec_raw.get("marginCurrency") or "")
    acct_ccy = str(account.get("currency") or "")
    if init_margin is not None and init_margin > 0:
        if not margin_ccy or not acct_ccy or margin_ccy == acct_ccy:
            return MarginPerLot(init_margin, "spec.initialMargin", detail)
        detail["tried"].append(f"spec.initialMargin is in {margin_ccy}, account is {acct_ccy}")
    contract = spec.contract_size
    if symbol_leverage is not None and symbol_leverage > 0 and contract is not None and contract > 0:
        return MarginPerLot(contract * fill_price / symbol_leverage, "notional / AUTOEXEC_SYMBOL_LEVERAGE", detail)
    if use_account_leverage and contract is not None and contract > 0:
        lev = _num(account.get("leverage"))
        if lev is not None and lev > 0:
            return MarginPerLot(contract * fill_price / lev, "notional / account.leverage (opt-in)", detail)
    detail["tried"].append("no calibration: set AUTOEXEC_SYMBOL_LEVERAGE_<SYMBOL> or AUTOEXEC_MARGIN_PER_LOT_USD_<SYMBOL>")
    return MarginPerLot(None, "unavailable", detail)


@dataclass
class MarginCap:
    lots_before: Decimal
    lots_after: Decimal
    per_lot_usd: Decimal
    method: str
    account_margin: Decimal
    equity: Decimal
    max_new_margin_usd: Decimal
    max_lots: Decimal
    projected_margin_usd: Decimal
    projected_level_pct: Optional[Decimal]
    min_level_pct: Decimal
    capped: bool
    ok: bool
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


def apply_margin_cap(
    *,
    lots: Decimal,
    per_lot_usd: Decimal,
    method: str,
    equity: Decimal,
    account_margin: Decimal,
    min_level_pct: Decimal,
    spec: SpecValues,
) -> MarginCap:
    """Shrink ``lots`` (floored to step) until the projected margin level is >= ``min_level_pct``."""

    if per_lot_usd <= 0:
        raise SizingError("margin per lot must be positive")
    if min_level_pct <= 0:
        raise SizingError("minimum margin level must be positive")
    # equity / (acct + new) * 100 >= min  <=>  new <= equity * 100 / min - acct
    max_new = equity * Decimal("100") / min_level_pct - account_margin
    max_lots = floor_to_step(max_new / per_lot_usd, spec.volume_step) if max_new > 0 else Decimal("0")
    if max_lots < spec.min_volume:
        projected = account_margin + spec.min_volume * per_lot_usd
        level = (equity / projected * Decimal("100")) if projected > 0 else None
        return MarginCap(lots, Decimal("0"), per_lot_usd, method, account_margin, equity, max_new, max_lots, projected, level, min_level_pct, True, False,
                         f"skip: even the minimum volume {spec.min_volume} would put the margin level at {level.quantize(Decimal('0.1')) if level is not None else 'n/a'}% < {min_level_pct}%")
    capped = lots > max_lots
    final = min(lots, max_lots)
    projected = account_margin + final * per_lot_usd
    level = (equity / projected * Decimal("100")) if projected > 0 else None
    reason = f"capped from {lots} to {final} lots to keep the margin level >= {min_level_pct}%" if capped else "margin level ok"
    return MarginCap(lots, final, per_lot_usd, method, account_margin, equity, max_new, max_lots, projected, level, min_level_pct, capped, True, reason)
