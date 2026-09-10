"""London Reversal entry modes implementing range-fade mechanics."""

from enum import Enum
from typing import Any, Optional, Tuple


class LondonEntryMode(Enum):
    """Enumeration of 7 London Reversal range-fade entry modes."""

    BLIND_LIMIT = "blind_limit"
    SWEEP_CONFIRMATION = "sweep_confirmation"
    DYNAMIC_BUFFER = "dynamic_buffer"
    TIME_WEIGHTED = "time_weighted"
    ORDER_FLOW_SPREAD_GATE = "order_flow_spread_gate"
    MULTI_TIMEFRAME = "multi_timeframe"
    HYBRID_SWEEP_TIME_SPREAD = "hybrid_sweep_time_spread"


def check_blind_limit(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate blind limit entry at exact Asian range boundary extremes.

    Parameters:
        candle: Candle object with high and low attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) where -1 is short and 1 is long, or None.
    """
    if candle.high >= asian_high:
        return -1, asian_high
    if candle.low <= asian_low:
        return 1, asian_low
    return None


def check_sweep_confirmation(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate sweep confirmation requiring probe beyond extreme and candle close inside.

    Parameters:
        candle: Candle object with high, low, and close attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.high > asian_high and candle.close < asian_high:
        return -1, candle.close
    if candle.low < asian_low and candle.close > asian_low:
        return 1, candle.close
    return None


def check_dynamic_buffer(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
    buffer_mult: float = 0.3,
) -> Optional[Tuple[int, float]]:
    """Evaluate dynamic buffer entry offset by ATR fraction.

    Parameters:
        candle: Candle object with high and low attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points.
        buffer_mult: Multiplier applied to ATR to compute buffer.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    buffer = (atr * buffer_mult) if atr else 5.0
    if candle.high >= asian_high + buffer:
        return -1, asian_high + buffer
    if candle.low <= asian_low - buffer:
        return 1, asian_low - buffer
    return None


def check_time_weighted(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate time-weighted entry condition at boundary.

    Parameters:
        candle: Candle object with high and low attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.high >= asian_high:
        return -1, asian_high
    if candle.low <= asian_low:
        return 1, asian_low
    return None


def check_order_flow_spread_gate(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
    max_spread: float = 3.0,
) -> Optional[Tuple[int, float]]:
    """Evaluate entry contingent on candle spread remaining below maximum allowable threshold.

    Parameters:
        candle: Candle object with high and low attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.
        max_spread: Maximum allowable spread in points.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    spread = candle.high - candle.low
    if spread < max_spread:
        if candle.high >= asian_high:
            return -1, asian_high
        if candle.low <= asian_low:
            return 1, asian_low
    return None


def check_multi_timeframe(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate multi-timeframe directional rejection confirmation on current candle.

    Parameters:
        candle: Candle object with open, high, low, and close attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.high >= asian_high and candle.close < candle.open:
        return -1, candle.close
    if candle.low <= asian_low and candle.close > candle.open:
        return 1, candle.close
    return None


def check_hybrid_sweep_time_spread(
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
    max_spread: float = 3.0,
) -> Optional[Tuple[int, float]]:
    """Evaluate hybrid entry combining sweep confirmation with spread gate filter.

    Parameters:
        candle: Candle object with high, low, and close attributes.
        asian_high: Asian session high watermark.
        asian_low: Asian session low watermark.
        atr: Current ATR in points if available.
        max_spread: Maximum allowable spread in points.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    spread = candle.high - candle.low
    if spread < max_spread:
        if candle.high > asian_high and candle.close < asian_high:
            return -1, candle.close
        if candle.low < asian_low and candle.close > asian_low:
            return 1, candle.close
    return None


LONDON_DISPATCH = {
    LondonEntryMode.BLIND_LIMIT.value: check_blind_limit,
    LondonEntryMode.SWEEP_CONFIRMATION.value: check_sweep_confirmation,
    LondonEntryMode.DYNAMIC_BUFFER.value: check_dynamic_buffer,
    LondonEntryMode.TIME_WEIGHTED.value: check_time_weighted,
    LondonEntryMode.ORDER_FLOW_SPREAD_GATE.value: check_order_flow_spread_gate,
    LondonEntryMode.MULTI_TIMEFRAME.value: check_multi_timeframe,
    LondonEntryMode.HYBRID_SWEEP_TIME_SPREAD.value: check_hybrid_sweep_time_spread,
}


def evaluate_london_entry(
    mode: Any,
    candle: Any,
    asian_high: float,
    asian_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Dispatch entry evaluation to the selected London Reversal entry mode handler.

    Parameters:
        mode: LondonEntryMode enum or string key.
        candle: Current candle object.
        asian_high: Asian session high.
        asian_low: Asian session low.
        atr: Current ATR value.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    key = mode.value if hasattr(mode, "value") else str(mode).lower()
    handler = LONDON_DISPATCH.get(key)
    if handler is None:
        return None
    return handler(candle, asian_high, asian_low, atr)
