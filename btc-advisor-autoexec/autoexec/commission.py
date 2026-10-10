"""Round-trip commission per lot, with the source recorded on every decision.

Priority in ``auto`` mode (Odin: prefer a broker-reported value when one is
available, otherwise the configured model; 2026-10-10 19:07 ET added the
percentage-of-notional model, default for crypto only):

1. ``spec``  — a commission field on the MetaAPI symbol specification, if the
   broker exposes one (MetaAPI's documented specification has no standard
   commission field, so this is usually absent).
2. ``deals`` — observed from the account's own closed round trips on the
   symbol inside the lookback window: sum of |commission| over the IN and OUT
   deals of positions that have *both* legs in the window, divided by the IN
   volume. Positions with only one leg in the window are ignored so a
   per-side charge is never mistaken for a round trip.
3. model    — ``pct``: 2 x AUTOEXEC_COMMISSION_PCT_PER_SIDE (0.0325 %, = 0.065 % per
   round trip per Odin 2026-10-10 19:30 ET) x notional per
   lot (contractSize x fill price); ``flat``: AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_<SYMBOL>
   (the un-suffixed 27.0 is BTCUSD's legacy figure). Which model applies comes from
   ``Config.commission_model_for`` (per symbol, else per asset class; crypto -> pct).

``AUTOEXEC_COMMISSION_SOURCE`` can pin one source. A pinned ``spec`` or
``deals`` that has no data fails closed (the entry is rejected) rather than
silently using another number.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from .config import env_suffix
from .sizing import D

SPEC_COMMISSION_KEYS = ("commissionPerLotRoundtrip", "commissionRoundTrip", "commissionPerLot", "commission")


@dataclass
class CommissionResolution:
    per_lot_roundtrip: Optional[Decimal]
    source: str  # spec | deals | env | pct | none
    spec_value: Optional[Decimal]
    spec_field: Optional[str]
    deals_value: Optional[Decimal]
    deals_round_trips: int
    deals_in_volume: Decimal
    env_value: Optional[Decimal]  # flat per-lot round trip from env, if any
    note: str
    model: Optional[str] = None  # configured model for this symbol: pct | flat | None
    asset_class: Optional[str] = None
    pct_per_side: Optional[Decimal] = None
    notional_per_lot: Optional[Decimal] = None
    pct_value: Optional[Decimal] = None  # 2 * pct/100 * notional per lot

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for k, v in asdict(self).items():
            out[k] = float(v) if isinstance(v, Decimal) else v
        return out


def commission_from_spec(spec: Dict[str, Any]) -> "tuple[Optional[Decimal], Optional[str]]":
    for key in SPEC_COMMISSION_KEYS:
        v = spec.get(key)
        if v is None or v == "":
            continue
        try:
            d = abs(D(v))
        except Exception:
            continue
        return d, key
    return None, None


def commission_from_deals(deals: Iterable[Dict[str, Any]], symbol: str) -> "tuple[Optional[Decimal], int, Decimal]":
    """Observed round-trip commission per lot from closed positions with both legs present."""

    by_pos: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        if (d.get("symbol") or "") != symbol:
            continue
        pid = str(d.get("positionId") or "")
        if not pid:
            continue
        entry = str(d.get("entryType") or "")
        rec = by_pos.setdefault(pid, {"in": Decimal("0"), "has_in": False, "has_out": False, "commission": Decimal("0")})
        rec["commission"] += abs(D(d.get("commission") or 0))
        if entry == "DEAL_ENTRY_IN":
            rec["has_in"] = True
            rec["in"] += D(d.get("volume") or 0)
        elif entry in ("DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT", "DEAL_ENTRY_OUT_BY"):
            rec["has_out"] = True
    total_comm = Decimal("0")
    total_in = Decimal("0")
    n = 0
    for rec in by_pos.values():
        if rec["has_in"] and rec["has_out"] and rec["in"] > 0:
            total_comm += rec["commission"]
            total_in += rec["in"]
            n += 1
    if n == 0 or total_in <= 0:
        return None, 0, Decimal("0")
    return total_comm / total_in, n, total_in


def _model_value(
    *,
    model: Optional[str],
    env_value: Optional[Decimal],
    pct_per_side: Optional[Decimal],
    notional_per_lot: Optional[Decimal],
    symbol: str,
) -> "tuple[Optional[Decimal], str, str]":
    """(value, source, note) for the configured model; value None when it cannot be applied."""

    if model == "pct":
        if pct_per_side is None or notional_per_lot is None or notional_per_lot <= 0:
            return None, "none", f"pct model configured for {symbol} but notional per lot is unavailable (contractSize x price in account currency)"
        value = Decimal("2") * pct_per_side / Decimal("100") * notional_per_lot
        return value, "pct", f"model: {pct_per_side}% of notional per side x 2 sides x notional {notional_per_lot.quantize(Decimal('0.01'))}/lot"
    if model == "flat":
        if env_value is None:
            return None, "none", f"flat model configured for {symbol} but no AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_{env_suffix(symbol)} value is set (0 is a valid value)"
        return env_value, "env", "model: flat per-lot round trip from env"
    suffix = env_suffix(symbol)
    return None, "none", (
        f"no commission model for {symbol}: no broker-reported commission, no closed round trips, and no "
        f"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_{suffix} (flat), AUTOEXEC_COMMISSION_PCT_PER_SIDE_{suffix} or "
        f"AUTOEXEC_COMMISSION_MODEL_{suffix}=pct|flat (or a model for its asset class); skipping"
    )


def resolve_commission(
    *,
    mode: str,
    env_value: Optional[Decimal],
    spec: Optional[Dict[str, Any]],
    deals: Optional[List[Dict[str, Any]]],
    symbol: str,
    model: Optional[str] = None,
    pct_per_side: Optional[Decimal] = None,
    notional_per_lot: Optional[Decimal] = None,
    asset_class: Optional[str] = None,
) -> CommissionResolution:
    """Resolve the round-trip commission per lot for ``symbol``.

    ``auto``: spec field -> closed round trips in the lookback -> configured model
    (``pct`` of notional per side x 2, or ``flat`` from env). ``env`` pins the model;
    ``spec`` / ``deals`` pin those sources. Anything unavailable resolves to ``none``
    (the entry is skipped); nothing is guessed.
    """

    spec_value, spec_field = commission_from_spec(spec or {})
    deals_value, n_rt, in_vol = commission_from_deals(deals or [], symbol)
    model_value, model_source, model_note = _model_value(model=model, env_value=env_value, pct_per_side=pct_per_side, notional_per_lot=notional_per_lot, symbol=symbol)
    pct_value = model_value if model_source == "pct" else None
    common = dict(
        spec_value=spec_value,
        spec_field=spec_field,
        deals_value=deals_value,
        deals_round_trips=n_rt,
        deals_in_volume=in_vol,
        env_value=env_value,
        model=model,
        asset_class=asset_class,
        pct_per_side=pct_per_side,
        notional_per_lot=notional_per_lot,
        pct_value=pct_value,
    )

    if mode == "env":
        if model_value is None:
            return CommissionResolution(None, "none", note="pinned to env/model: " + model_note, **common)
        return CommissionResolution(model_value, model_source, note="pinned to env/model; " + model_note, **common)
    if mode == "spec":
        if spec_value is None:
            return CommissionResolution(None, "none", note="pinned to spec but the specification exposes no commission field", **common)
        return CommissionResolution(spec_value, "spec", note=f"pinned to spec field {spec_field}", **common)
    if mode == "deals":
        if deals_value is None:
            return CommissionResolution(None, "none", note="pinned to deals but no closed round trip in the lookback window", **common)
        return CommissionResolution(deals_value, "deals", note=f"observed over {n_rt} closed round trip(s)", **common)
    # auto
    if spec_value is not None:
        return CommissionResolution(spec_value, "spec", note=f"auto: spec field {spec_field}", **common)
    if deals_value is not None:
        return CommissionResolution(deals_value, "deals", note=f"auto: observed over {n_rt} closed round trip(s)", **common)
    if model_value is None:
        return CommissionResolution(None, "none", note="auto: " + model_note, **common)
    return CommissionResolution(model_value, model_source, note="auto: no broker-reported commission; " + model_note, **common)
