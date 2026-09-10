"""Omni Breakout entry modes implementing US Open momentum and breakout mechanics."""

from enum import Enum
from typing import Any, Optional, Tuple


class OmniEntryMode(Enum):
    """Enumeration of 7 Omni Breakout entry modes."""

    STOP_ORDER_AT_RANGE = "stop_order_at_range"
    CLOSE_CONFIRMATION = "close_confirmation"
    VOLUME_SPIKE_GATE = "volume_spike_gate"
    RETEST_ENTRY = "retest_entry"
    MOMENTUM_THRESHOLD = "momentum_threshold"
    DUAL_TIMEFRAME = "dual_timeframe"
    HYBRID_RETEST_VOLUME_SPREAD = "hybrid_retest_volume_spread"


def check_stop_order_at_range(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout stop order triggering at exact ORB boundary.

    Parameters:
        candle: Candle object with high and low attributes.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) where 1 is long and -1 is short, or None.
    """
    if candle.high >= orb_high:
        return 1, orb_high
    if candle.low <= orb_low:
        return -1, orb_low
    return None


def check_close_confirmation(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout requiring candle close completely outside ORB boundaries.

    Parameters:
        candle: Candle object with close attribute.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.close > orb_high:
        return 1, candle.close
    if candle.close < orb_low:
        return -1, candle.close
    return None


def check_volume_spike_gate(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout contingent on volume surge confirmation.

    Parameters:
        candle: Candle object with high, low, and volume attributes.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    volume = getattr(candle, "volume", 0.0)
    if candle.high >= orb_high and volume > 0:
        return 1, orb_high
    if candle.low <= orb_low and volume > 0:
        return -1, orb_low
    return None


def check_retest_entry(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout retest hold where price dips to boundary and closes favorably.

    Parameters:
        candle: Candle object with high, low, and close attributes.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.low <= orb_high and candle.close > orb_high:
        return 1, candle.close
    if candle.high >= orb_low and candle.close < orb_low:
        return -1, candle.close
    return None


def check_momentum_threshold(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
    threshold_pts: float = 10.0,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout with momentum extension beyond threshold distance.

    Parameters:
        candle: Candle object with close attribute.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.
        threshold_pts: Required point extension beyond boundary.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.close > orb_high + threshold_pts:
        return 1, candle.close
    if candle.close < orb_low - threshold_pts:
        return -1, candle.close
    return None


def check_dual_timeframe(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Evaluate breakout confirmed by directional candle closure alignment.

    Parameters:
        candle: Candle object with open and close attributes.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    if candle.close > orb_high and candle.close > candle.open:
        return 1, candle.close
    if candle.close < orb_low and candle.close < candle.open:
        return -1, candle.close
    return None


def check_hybrid_retest_volume_spread(
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
    max_spread: float = 5.0,
) -> Optional[Tuple[int, float]]:
    """Evaluate hybrid entry combining retest hold with volume spike and tight spread.

    Parameters:
        candle: Candle object with high, low, close, and volume attributes.
        orb_high: Opening range breakout high level.
        orb_low: Opening range breakout low level.
        atr: Current ATR in points if available.
        max_spread: Maximum allowable spread in points.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    spread = candle.high - candle.low
    volume = getattr(candle, "volume", 0.0)
    if spread < max_spread and volume > 0:
        if candle.low <= orb_high and candle.close > orb_high:
            return 1, candle.close
        if candle.high >= orb_low and candle.close < orb_low:
            return -1, candle.close
    return None


OMNI_DISPATCH = {
    OmniEntryMode.STOP_ORDER_AT_RANGE.value: check_stop_order_at_range,
    OmniEntryMode.CLOSE_CONFIRMATION.value: check_close_confirmation,
    OmniEntryMode.VOLUME_SPIKE_GATE.value: check_volume_spike_gate,
    OmniEntryMode.RETEST_ENTRY.value: check_retest_entry,
    OmniEntryMode.MOMENTUM_THRESHOLD.value: check_momentum_threshold,
    OmniEntryMode.DUAL_TIMEFRAME.value: check_dual_timeframe,
    OmniEntryMode.HYBRID_RETEST_VOLUME_SPREAD.value: check_hybrid_retest_volume_spread,
}


def evaluate_omni_entry(
    mode: Any,
    candle: Any,
    orb_high: float,
    orb_low: float,
    atr: Optional[float] = None,
) -> Optional[Tuple[int, float]]:
    """Dispatch entry evaluation to the selected Omni Breakout entry mode handler.

    Parameters:
        mode: OmniEntryMode enum or string key.
        candle: Current candle object.
        orb_high: ORB session high.
        orb_low: ORB session low.
        atr: Current ATR value.

    Returns:
        Tuple of (direction, entry_price) or None.
    """
    key = mode.value if hasattr(mode, "value") else str(mode).lower()
    handler = OMNI_DISPATCH.get(key)
    if handler is None:
        return None
    return handler(candle, orb_high, orb_low, atr)
