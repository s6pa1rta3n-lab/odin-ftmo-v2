"""Round-trip commission per lot, with the source recorded on every decision.

Priority in ``auto`` mode (Odin: prefer a broker-reported value when one is
available, otherwise the configurable fallback):

1. ``spec``  — a commission field on the MetaAPI symbol specification, if the
   broker exposes one (MetaAPI's documented specification has no standard
   commission field, so this is usually absent).
2. ``deals`` — observed from the account's own closed round trips on the
   symbol inside the lookback window: sum of |commission| over the IN and OUT
   deals of positions that have *both* legs in the window, divided by the IN
   volume. Positions with only one leg in the window are ignored so a
   per-side charge is never mistaken for a round trip.
3. ``env``   — ``AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP`` (default 27.0, the
   figure Odin's advisor cited for 1.0 lot BTCUSD).

``AUTOEXEC_COMMISSION_SOURCE`` can pin one source. A pinned ``spec`` or
``deals`` that has no data fails closed (the entry is rejected) rather than
silently using another number.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from .sizing import D

SPEC_COMMISSION_KEYS = ("commissionPerLotRoundtrip", "commissionRoundTrip", "commissionPerLot", "commission")


@dataclass
class CommissionResolution:
    per_lot_roundtrip: Optional[Decimal]
    source: str  # spec | deals | env | none
    spec_value: Optional[Decimal]
    spec_field: Optional[str]
    deals_value: Optional[Decimal]
    deals_round_trips: int
    deals_in_volume: Decimal
    env_value: Decimal
    note: str

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


def resolve_commission(
    *,
    mode: str,
    env_value: Decimal,
    spec: Optional[Dict[str, Any]],
    deals: Optional[List[Dict[str, Any]]],
    symbol: str,
) -> CommissionResolution:
    spec_value, spec_field = commission_from_spec(spec or {})
    deals_value, n_rt, in_vol = commission_from_deals(deals or [], symbol)

    if mode == "env":
        return CommissionResolution(env_value, "env", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, "pinned to env")
    if mode == "spec":
        if spec_value is None:
            return CommissionResolution(None, "none", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, "pinned to spec but the specification exposes no commission field")
        return CommissionResolution(spec_value, "spec", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, f"pinned to spec field {spec_field}")
    if mode == "deals":
        if deals_value is None:
            return CommissionResolution(None, "none", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, "pinned to deals but no closed round trip in the lookback window")
        return CommissionResolution(deals_value, "deals", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, f"observed over {n_rt} closed round trip(s)")
    # auto
    if spec_value is not None:
        return CommissionResolution(spec_value, "spec", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, f"auto: spec field {spec_field}")
    if deals_value is not None:
        return CommissionResolution(deals_value, "deals", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, f"auto: observed over {n_rt} closed round trip(s)")
    return CommissionResolution(env_value, "env", spec_value, spec_field, deals_value, n_rt, in_vol, env_value, "auto: no broker-reported commission; using env fallback")
