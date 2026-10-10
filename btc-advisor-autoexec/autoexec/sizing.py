"""Risk sizing (approved mechanic #2).

per_lot_loss = stop_distance * value_per_price_unit_per_lot
             + spread * value_per_price_unit_per_lot
             + commission_per_lot_roundtrip

lots = floor_to_step(max_risk / per_lot_loss)

If even ``minVolume`` would lose more than ``max_risk``, the entry is skipped.

``value_per_price_unit_per_lot`` = tick value / ``tickSize``. The tick value
comes from the current-price quote's ``lossTickValue`` (this account's MetaAPI
reports null tick values in the spec), else a spec tick value, else
``contractSize x tickSize`` only for symbols quoted in the account currency.
No hard-coded fallback: otherwise sizing fails closed.

All arithmetic is in ``Decimal`` to make the floor-to-step exact.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional


def D(x: Any) -> Decimal:
    return Decimal(str(x))


@dataclass
class SpecValues:
    tick_size: Optional[Decimal]
    tick_value: Optional[Decimal]
    tick_value_field: Optional[str]
    contract_size: Optional[Decimal]
    volume_step: Decimal
    min_volume: Decimal
    max_volume: Optional[Decimal]
    digits: Optional[int]
    value_per_unit_per_lot: Decimal
    value_source: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


class SizingError(ValueError):
    pass


def _opt(spec: Dict[str, Any], key: str) -> Optional[Decimal]:
    v = spec.get(key)
    if v is None or v == "":
        return None
    try:
        d = D(v)
    except Exception:
        return None
    return d


REQUIRED_SPEC_FIELDS = ("contractSize", "tickSize", "minVolume", "volumeStep")


def missing_spec_fields(spec: Dict[str, Any]) -> List[str]:
    """Spec fields a tradable symbol must expose (Odin 2026-10-10 19:07 ET: never guess a spec value).

    The tick value is NOT required in the spec: on this account MetaAPI reports
    ``tickValue``/``lossTickValue`` as null in the specification and only in the
    current-price quote (Trading Ops preflight, 2026-10-10). See :func:`parse_spec`.
    """

    missing: List[str] = []
    for key in REQUIRED_SPEC_FIELDS:
        v = _opt(spec, key)
        if v is None or v <= 0:
            missing.append(key)
    return missing


def _symbol_currency(spec: Dict[str, Any]) -> str:
    return str(spec.get("profitCurrency") or spec.get("quoteCurrency") or "")


def parse_spec(
    spec: Dict[str, Any],
    *,
    strict: bool = False,
    quote: Optional[Dict[str, Any]] = None,
    account_currency: Optional[str] = None,
) -> SpecValues:
    """Extract the fields sizing needs and derive $/price-unit/lot.

    Tick value source, in order (``value_source`` records which one was used):

    1. ``quote.lossTickValue`` from the current-price quote (conservative, loss side).
    2. a spec tick value (``lossTickValue`` / ``profitTickValue`` / ``tickValue``).
    3. ``contractSize x tickSize`` — ONLY when the symbol's profit/quote currency equals
       the account currency (this is the #84–#86 behaviour for USD-quoted symbols).
    Otherwise the symbol fails closed (``SizingError``).

    ``strict=True`` additionally requires every field in ``REQUIRED_SPEC_FIELDS``.
    """

    if strict:
        missing = missing_spec_fields(spec)
        if missing:
            raise SizingError(f"symbol specification is missing {missing}")

    tick_size = _opt(spec, "tickSize")
    contract_size = _opt(spec, "contractSize")
    volume_step = _opt(spec, "volumeStep")
    min_volume = _opt(spec, "minVolume")
    max_volume = _opt(spec, "maxVolume")
    digits_raw = spec.get("digits")
    digits = int(digits_raw) if digits_raw is not None else None

    if volume_step is None or volume_step <= 0:
        raise SizingError("symbol specification missing volumeStep")
    if min_volume is None or min_volume <= 0:
        raise SizingError("symbol specification missing minVolume")
    if tick_size is None or tick_size <= 0:
        raise SizingError("symbol specification missing tickSize")

    tick_value: Optional[Decimal] = None
    tick_value_field: Optional[str] = None
    source: Optional[str] = None
    q_loss = _opt(quote or {}, "lossTickValue")
    if q_loss is not None and q_loss > 0:
        tick_value, tick_value_field, source = q_loss, "quote.lossTickValue", "quote.lossTickValue/tickSize"
    else:
        for key in ("lossTickValue", "profitTickValue", "tickValue"):
            tv = _opt(spec, key)
            if tv is not None and tv > 0:
                tick_value, tick_value_field, source = tv, f"spec.{key}", f"spec.{key}/tickSize"
                break
    if tick_value is not None:
        value = tick_value / tick_size
    else:
        sym_ccy = _symbol_currency(spec)
        acct_ccy = str(account_currency or "")
        if contract_size is not None and contract_size > 0 and sym_ccy and acct_ccy and sym_ccy == acct_ccy:
            tick_value = contract_size * tick_size
            tick_value_field = "contractSize x tickSize"
            source = f"contractSize x tickSize ({sym_ccy}-quoted, account {acct_ccy})"
            value = contract_size
        else:
            why = "profit currency not reported" if not sym_ccy else (f"profit currency {sym_ccy} != account currency {acct_ccy or '?'}")
            raise SizingError(
                "no tick value: quote.lossTickValue and spec tickValue are absent, and contractSize x tickSize "
                f"is only used when the symbol is quoted in the account currency ({why})"
            )
    if value <= 0:
        raise SizingError(f"derived value per price unit is not positive ({value})")
    return SpecValues(
        tick_size=tick_size,
        tick_value=tick_value,
        tick_value_field=tick_value_field,
        contract_size=contract_size,
        volume_step=volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
        digits=digits,
        value_per_unit_per_lot=value,
        value_source=source or "unknown",
    )


def floor_to_step(volume: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise SizingError("volume step must be positive")
    return (volume / step).to_integral_value(rounding=ROUND_DOWN) * step


@dataclass
class Sizing:
    stop_distance: Decimal
    spread: Decimal
    value_per_unit_per_lot: Decimal
    stop_loss_per_lot: Decimal
    spread_cost_per_lot: Decimal
    commission_per_lot_roundtrip: Decimal
    per_lot_loss: Decimal
    raw_lots: Decimal
    lots: Decimal
    risk_usd: Decimal
    max_risk_usd: Decimal
    min_volume: Decimal
    volume_step: Decimal
    max_volume: Optional[Decimal]
    ok: bool
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


def size_position(
    *,
    stop_distance: Decimal,
    spread: Decimal,
    spec: SpecValues,
    commission_per_lot_roundtrip: Decimal,
    max_risk_usd: Decimal,
) -> Sizing:
    """Compute lots for the approved max-risk rule. Pure; no I/O."""

    if stop_distance <= 0:
        raise SizingError("stop distance must be positive")
    if spread < 0:
        raise SizingError("spread must be >= 0")
    if commission_per_lot_roundtrip < 0:
        raise SizingError("commission must be >= 0")

    v = spec.value_per_unit_per_lot
    stop_loss_per_lot = stop_distance * v
    spread_cost_per_lot = spread * v
    per_lot_loss = stop_loss_per_lot + spread_cost_per_lot + commission_per_lot_roundtrip
    if per_lot_loss <= 0:
        raise SizingError("per-lot loss is not positive")

    raw_lots = max_risk_usd / per_lot_loss
    lots = floor_to_step(raw_lots, spec.volume_step)
    reason = "sized"
    ok = True
    if spec.max_volume is not None and lots > spec.max_volume:
        lots = floor_to_step(spec.max_volume, spec.volume_step)
        reason = "capped_at_max_volume"
    if lots < spec.min_volume:
        min_loss = spec.min_volume * per_lot_loss
        ok = False
        lots = Decimal("0")
        reason = (
            f"skip: minimum volume {spec.min_volume} would risk ${min_loss.quantize(Decimal('0.01'))} "
            f"> max ${max_risk_usd}"
        )
    risk = lots * per_lot_loss
    return Sizing(
        stop_distance=stop_distance,
        spread=spread,
        value_per_unit_per_lot=v,
        stop_loss_per_lot=stop_loss_per_lot,
        spread_cost_per_lot=spread_cost_per_lot,
        commission_per_lot_roundtrip=commission_per_lot_roundtrip,
        per_lot_loss=per_lot_loss,
        raw_lots=raw_lots,
        lots=lots,
        risk_usd=risk,
        max_risk_usd=max_risk_usd,
        min_volume=spec.min_volume,
        volume_step=spec.volume_step,
        max_volume=spec.max_volume,
        ok=ok,
        reason=reason,
    )
