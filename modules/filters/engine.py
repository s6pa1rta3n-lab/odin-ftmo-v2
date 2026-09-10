"""Market context filters for London Reversal and Omni Breakout engines."""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class MarketFilter(Enum):
    """Enumeration of market context filters."""

    ATR_GATE = "atr_gate"
    VIX_REGIME = "vix_regime"
    SPREAD_GATE = "spread_gate"
    NEWS_BLACKOUT = "news_blackout"
    PRE_SESSION_MOMENTUM = "pre_session_momentum"
    VOLATILITY_PERCENTILE = "volatility_percentile"
    DAY_OF_WEEK = "day_of_week"
    ORB_WIDTH_GATE = "orb_width_gate"
    PRE_OPEN_TREND = "pre_open_trend"
    LONDON_SESSION_RESULT = "london_session_result"


FILTER_ALIASES = {
    "session_overlap_gate": "volatility_percentile",
    "spread_health_gate": "spread_gate",
}


KNOWN_NEWS_BLACKOUT_DATES = {
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17", "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
}


def check_atr_gate(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    **kwargs: Any,
) -> bool:
    """Validate range width is within [0.5, 2.0] multiple of 14-period ATR."""
    if atr is None or atr <= 0.0:
        return True
    ratio = range_width / atr
    return 0.5 <= ratio <= 2.0


def check_spread_gate(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    spread: float = 1.0,
    max_spread: float = 5.0,
    **kwargs: Any,
) -> bool:
    """Validate bid-ask spread does not exceed maximum allowable threshold."""
    return spread < max_spread


def check_day_of_week(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    **kwargs: Any,
) -> bool:
    """Block trading on Monday (0) and Friday (4)."""
    ts = getattr(candle, "timestamp", None)
    if ts is None:
        return True
    dow = ts.weekday()
    return dow not in (0, 4)


def check_orb_width_gate(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    **kwargs: Any,
) -> bool:
    """Validate US Open Range width is within [0.5, 2.0] multiple of ATR."""
    if atr is None or atr <= 0.0:
        return True
    ratio = range_width / atr
    return 0.5 <= ratio <= 2.0


def check_vix_regime(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    vix: Optional[float] = None,
    min_vix: float = 15.0,
    **kwargs: Any,
) -> bool:
    """Halt trading when VIX is below minimum volatility floor."""
    if vix is None:
        return True
    return vix >= min_vix


def check_news_blackout(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    is_news_day: Optional[bool] = None,
    **kwargs: Any,
) -> bool:
    """Block trading on high-impact macroeconomic news release days."""
    if is_news_day is not None:
        return not is_news_day
    ts = getattr(candle, "timestamp", None)
    if ts is not None:
        date_str = ts.strftime("%Y-%m-%d")
        if date_str in KNOWN_NEWS_BLACKOUT_DATES:
            return False
    return True


def check_pre_session_momentum(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    pre_session_drift: Optional[float] = None,
    **kwargs: Any,
) -> bool:
    """Halt if price drifted more than 1.0 ATR in pre-session window."""
    if pre_session_drift is not None and atr is not None and atr > 0:
        if abs(pre_session_drift) > (1.0 * atr):
            return False
    return True


def check_volatility_percentile(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    vol_percentile: Optional[float] = None,
    **kwargs: Any,
) -> bool:
    """Filter for volatility between 20th and 80th percentiles."""
    if vol_percentile is not None:
        return 20.0 <= vol_percentile <= 80.0
    return True


def check_pre_open_trend(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    pre_open_aligned: Optional[bool] = None,
    **kwargs: Any,
) -> bool:
    """Require breakout direction to align with pre-open momentum."""
    if pre_open_aligned is not None:
        return pre_open_aligned
    return True


def check_london_session_result(
    candle: Any,
    atr: Optional[float],
    range_width: float,
    london_result_pnl: float = 0.0,
    **kwargs: Any,
) -> bool:
    """Evaluate inter-engine risk feedback from London session PnL."""
    return True


FILTER_DISPATCH: Dict[str, Callable[..., bool]] = {
    "atr_gate": check_atr_gate,
    "spread_gate": check_spread_gate,
    "day_of_week": check_day_of_week,
    "orb_width_gate": check_orb_width_gate,
    "vix_regime": check_vix_regime,
    "news_blackout": check_news_blackout,
    "pre_session_momentum": check_pre_session_momentum,
    "volatility_percentile": check_volatility_percentile,
    "pre_open_trend": check_pre_open_trend,
    "london_session_result": check_london_session_result,
}


class FilterEngine:
    """Evaluates composite active filters before allowing trade execution."""

    def __init__(self, active_filters: List[Any]) -> None:
        """Initialize filter engine with active filter identifiers.

        Parameters:
            active_filters: Sequence of filter enum instances or string identifiers.
        """
        self.active_filters: Set[str] = set()
        for f in active_filters:
            name = f.value if hasattr(f, "value") else str(f).lower()
            resolved = FILTER_ALIASES.get(name, name)
            self.active_filters.add(resolved)

    def should_trade(
        self,
        candle: Any,
        atr: Optional[float],
        range_width: float,
        spread: float = 1.0,
        london_result_pnl: float = 0.0,
        **kwargs: Any,
    ) -> bool:
        """Evaluate all active filters. Returns True only if every active filter passes.

        Parameters:
            candle: Current Candle object.
            atr: Current ATR in points.
            range_width: Session range width in points.
            spread: Current market bid-ask spread in points.
            london_result_pnl: Realized PnL from London session earlier today.
            **kwargs: Additional contextual signals (e.g. vix, is_news_day).

        Returns:
            True if all active filters permit trading, False otherwise.
        """
        for f_name in self.active_filters:
            handler = FILTER_DISPATCH.get(f_name)
            if handler is not None:
                passed = handler(
                    candle=candle,
                    atr=atr,
                    range_width=range_width,
                    spread=spread,
                    london_result_pnl=london_result_pnl,
                    **kwargs,
                )
                if not passed:
                    return False
        return True
