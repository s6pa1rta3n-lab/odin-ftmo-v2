"""Risk sizing (approved mechanic #2).

per_lot_loss = stop_distance * value_per_price_unit_per_lot
             + spread * value_per_price_unit_per_lot
             + commission_per_lot_roundtrip

lots = floor_to_step(max_risk / per_lot_loss)

If even ``minVolume`` would lose more than ``max_risk``, the entry is skipped.

``value_per_price_unit_per_lot`` comes from the MetaAPI symbol specification:
``tickValue / tickSize`` when both are present (``lossTickValue`` is preferred
over ``profitTickValue`` over ``tickValue`` because sizing is about the losing
side), else ``contractSize`` for a USD-quoted symbol. No hard-coded fallback:
if the spec exposes neither, sizing fails closed.

All arithmetic is in ``Decimal`` to make the floor-to-step exact.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional


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


def parse_spec(spec: Dict[str, Any]) -> SpecValues:
    """Extract the fields sizing needs and derive $/price-unit/lot."""

    tick_size = _opt(spec, "tickSize")
    tick_value: Optional[Decimal] = None
    tick_value_field: Optional[str] = None
    for key in ("lossTickValue", "profitTickValue", "tickValue"):
        tv = _opt(spec, key)
        if tv is not None and tv > 0:
            tick_value, tick_value_field = tv, key
            break
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

    if tick_size is not None and tick_size > 0 and tick_value is not None and tick_value > 0:
        value = tick_value / tick_size
        source = f"{tick_value_field}/tickSize"
    elif contract_size is not None and contract_size > 0:
        value = contract_size
        source = "contractSize"
    else:
        raise SizingError("symbol specification exposes neither tickValue/tickSize nor contractSize")
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
        value_source=source,
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
