"""Risk sizing models and enumeration for Odin FTMO v2."""

from enum import Enum
from typing import List, Optional


class RiskModel(Enum):
    """Enumeration of the 7 supported risk sizing models."""

    CONSERVATIVE_RAMP = "conservative_ramp"
    FIXED_LOW = "fixed_low"
    AGGRESSIVE_FLAT = "aggressive_flat"
    KELLY_CRITERION = "kelly_criterion"
    ANTI_MARTINGALE = "anti_martingale"
    VOLATILITY_SCALED = "volatility_scaled"
    EQUITY_CURVE = "equity_curve"


def calculate_conservative_ramp(current_equity: float) -> float:
    """Compute risk percentage for Conservative Ramp model based on equity brackets.

    Parameters:
        current_equity: Account equity in dollars.

    Returns:
        Risk percentage as a float fraction.
    """
    if current_equity < 98000.0:
        return 0.0025
    if current_equity < 102000.0:
        return 0.0050
    return 0.0075


def calculate_fixed_low() -> float:
    """Compute risk percentage for Fixed Low model.

    Returns:
        Fixed risk percentage (0.35%).
    """
    return 0.0035


def calculate_aggressive_flat() -> float:
    """Compute risk percentage for Aggressive Flat model.

    Returns:
        Fixed risk percentage (0.75%).
    """
    return 0.0075


def calculate_kelly_criterion(recent_trades_pnl: List[float]) -> float:
    """Compute risk percentage using half-Kelly optimal fraction over rolling trade history.

    Parameters:
        recent_trades_pnl: Sequence of realized PnL values in dollars.

    Returns:
        Clamped risk percentage between 0.1% and 1.0%.
    """
    if len(recent_trades_pnl) < 20:
        return 0.0035
    wins = [p for p in recent_trades_pnl if p > 0]
    losses = [p for p in recent_trades_pnl if p < 0]
    if not wins or not losses:
        return 0.0035
    win_rate = len(wins) / len(recent_trades_pnl)
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses) / len(losses))
    if avg_loss == 0.0:
        return 0.0035
    payoff_ratio = avg_win / avg_loss
    kelly = win_rate - ((1.0 - win_rate) / payoff_ratio)
    half_kelly = kelly * 0.5
    return max(min(half_kelly, 0.010), 0.001)


def calculate_anti_martingale(recent_trades_pnl: List[float]) -> float:
    """Compute risk percentage for Anti-Martingale hot-streak compounding.

    Parameters:
        recent_trades_pnl: Sequence of realized PnL values in dollars.

    Returns:
        Risk percentage scaled by recent win streak.
    """
    if len(recent_trades_pnl) < 3:
        return 0.0050
    last_three = recent_trades_pnl[-3:]
    streak = sum(1 for p in last_three if p > 0)
    if streak >= 3:
        return 0.0075
    if streak >= 2:
        return 0.0050
    return 0.0025


def calculate_volatility_scaled(atr: Optional[float], target_vol: float = 50.0) -> float:
    """Compute risk percentage inversely proportional to ATR volatility.

    Parameters:
        atr: Current Average True Range in points.
        target_vol: Baseline target volatility in points.

    Returns:
        Risk percentage clamped between 0.1% and 1.0%.
    """
    if atr is None or atr <= 0.0:
        return 0.0050
    ratio = target_vol / atr
    scaled = 0.0050 * ratio
    return max(min(scaled, 0.010), 0.001)


def calculate_equity_curve(current_equity: float, equity_history: List[float]) -> float:
    """Compute risk percentage based on equity relative to its 20-period moving average.

    Parameters:
        current_equity: Account equity in dollars.
        equity_history: Historical equity readings.

    Returns:
        Risk percentage (0.50% above MA, 0.25% below MA).
    """
    if len(equity_history) < 20:
        return 0.0050
    moving_average = sum(equity_history[-20:]) / 20.0
    if current_equity > moving_average:
        return 0.0050
    return 0.0025
