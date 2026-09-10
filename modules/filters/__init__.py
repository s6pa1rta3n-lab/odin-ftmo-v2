"""Modular market context filters package."""

from modules.filters.engine import (
    FILTER_ALIASES,
    FILTER_DISPATCH,
    KNOWN_NEWS_BLACKOUT_DATES,
    FilterEngine,
    MarketFilter,
    check_atr_gate,
    check_day_of_week,
    check_london_session_result,
    check_news_blackout,
    check_orb_width_gate,
    check_pre_open_trend,
    check_pre_session_momentum,
    check_spread_gate,
    check_vix_regime,
    check_volatility_percentile,
)

__all__ = [
    "MarketFilter",
    "FilterEngine",
    "FILTER_ALIASES",
    "FILTER_DISPATCH",
    "KNOWN_NEWS_BLACKOUT_DATES",
    "check_atr_gate",
    "check_spread_gate",
    "check_day_of_week",
    "check_orb_width_gate",
    "check_vix_regime",
    "check_news_blackout",
    "check_pre_session_momentum",
    "check_volatility_percentile",
    "check_pre_open_trend",
    "check_london_session_result",
]
