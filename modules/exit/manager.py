"""Exit models and trade management implementing 7 distinct exit strategies."""

from enum import Enum
from typing import Any, Dict, Optional, Tuple


class ExitModel(Enum):
    """Enumeration of 7 modular exit strategies."""

    FIXED_SL_TP = "fixed_sl_tp"
    FIXED_SL_TRAIL = "fixed_sl_trail"
    ATR_DYNAMIC_TRAIL = "atr_dynamic_trail"
    BREAKEVEN_RUNNER = "breakeven_runner"
    TIME_BASED = "time_based"
    CHANDELIER = "chandelier"
    MULTI_TARGET_CASCADE = "multi_target_cascade"


class ExitManager:
    """Manages position initial protection, trailing stops, and exit signals."""

    def __init__(
        self,
        model: Any,
        sl_pts: float = 40.0,
        tp_pts: float = 20.0,
        atr: Optional[float] = None,
    ) -> None:
        """Initialize exit manager with strategy parameters.

        Parameters:
            model: ExitModel enum instance or string identifier.
            sl_pts: Fixed stop loss distance in points.
            tp_pts: Fixed take profit distance in points.
            atr: Current ATR in points if available.
        """
        if isinstance(model, str):
            try:
                self.model = ExitModel(model.lower())
            except ValueError:
                self.model = ExitModel.FIXED_SL_TP
        else:
            self.model = model

        self.sl_pts = sl_pts
        self.tp_pts = tp_pts
        self.atr = atr

    def compute_sl_tp(
        self,
        entry_price: float,
        direction: int,
    ) -> Tuple[float, Optional[float]]:
        """Calculate initial stop loss and take profit prices.

        Parameters:
            entry_price: Executed fill price.
            direction: Trade direction (1 for Long, -1 for Short).

        Returns:
            Tuple of (stop_loss_price, take_profit_price_or_None).
        """
        if self.model == ExitModel.FIXED_SL_TP:
            sl = entry_price - self.sl_pts * direction
            tp = entry_price + self.tp_pts * direction
            return sl, tp

        if self.model == ExitModel.FIXED_SL_TRAIL:
            sl = entry_price - 30.0 * direction
            return sl, None

        if self.model == ExitModel.ATR_DYNAMIC_TRAIL:
            atr_val = self.atr if self.atr else 40.0
            sl = entry_price - 1.5 * atr_val * direction
            return sl, None

        if self.model == ExitModel.BREAKEVEN_RUNNER:
            sl = entry_price - 30.0 * direction
            return sl, None

        if self.model == ExitModel.TIME_BASED:
            sl = entry_price - 40.0 * direction
            return sl, None

        if self.model == ExitModel.CHANDELIER:
            atr_val = self.atr if self.atr else 40.0
            sl = entry_price - 3.0 * atr_val * direction
            return sl, None

        if self.model == ExitModel.MULTI_TARGET_CASCADE:
            sl = entry_price - 30.0 * direction
            return sl, None

        sl = entry_price - self.sl_pts * direction
        tp = entry_price + self.tp_pts * direction
        return sl, tp

    def check_exit(
        self,
        position: Any,
        candle: Any,
    ) -> Optional[Tuple[float, str]]:
        """Evaluate whether the current candle triggers an exit signal.

        Parameters:
            position: Active Position object.
            candle: Current Candle object.

        Returns:
            Tuple of (exit_price, exit_reason) if triggered, else None.
        """
        d = position.direction

        if d == 1:
            if candle.low <= position.sl_price:
                return position.sl_price, "stop_loss"
            if position.tp_price and candle.high >= position.tp_price:
                return position.tp_price, "take_profit"
        elif d == -1:
            if candle.high >= position.sl_price:
                return position.sl_price, "stop_loss"
            if position.tp_price and candle.low <= position.tp_price:
                return position.tp_price, "take_profit"

        if self.model == ExitModel.FIXED_SL_TRAIL:
            self._update_trailing(position, candle, trigger_pts=15.0, trail_dist=15.0)

        elif self.model == ExitModel.ATR_DYNAMIC_TRAIL:
            atr_val = self.atr if self.atr else 40.0
            self._update_trailing(position, candle, trigger_pts=atr_val, trail_dist=atr_val)

        elif self.model == ExitModel.BREAKEVEN_RUNNER:
            favorable = (candle.high - position.entry_price) if d == 1 else (position.entry_price - candle.low)
            if favorable >= 20.0 and not position.trailing_active:
                position.sl_price = position.entry_price + 1.0 * d
                position.trailing_active = True

        elif self.model == ExitModel.TIME_BASED:
            position.time_in_trade_minutes += 1
            if position.time_in_trade_minutes >= 120:
                return candle.close, "time_exit"

        elif self.model == ExitModel.CHANDELIER:
            atr_val = self.atr if self.atr else 40.0
            if d == 1:
                position.highest_price = max(position.highest_price, candle.high)
                new_sl = position.highest_price - 3.0 * atr_val
                position.sl_price = max(position.sl_price, new_sl)
            else:
                current_low = position.lowest_price if position.lowest_price > 0 else candle.low
                position.lowest_price = min(current_low, candle.low)
                new_sl = position.lowest_price + 3.0 * atr_val
                position.sl_price = min(position.sl_price, new_sl)

        elif self.model == ExitModel.MULTI_TARGET_CASCADE:
            favorable = (candle.high - position.entry_price) if d == 1 else (position.entry_price - candle.low)
            partial_closes = getattr(position, "partial_closes", [])
            if favorable >= 15.0 and 0 not in partial_closes:
                partial_closes.append(0)
                position.lots *= 0.67
            if favorable >= 30.0 and 1 not in partial_closes:
                partial_closes.append(1)
                position.lots *= 0.5
                position.trailing_active = True
            if position.trailing_active:
                self._update_trailing(position, candle, trigger_pts=0.0, trail_dist=15.0)

        if d == 1 and candle.low <= position.sl_price:
            return position.sl_price, "trailing_stop"
        elif d == -1 and candle.high >= position.sl_price:
            return position.sl_price, "trailing_stop"

        return None

    @staticmethod
    def _update_trailing(
        position: Any,
        candle: Any,
        trigger_pts: float,
        trail_dist: float,
    ) -> None:
        """Update ratcheting trailing stop loss for an open position."""
        d = position.direction
        if d == 1:
            favorable = candle.high - position.entry_price
            if favorable >= trigger_pts:
                position.trailing_active = True
                new_sl = candle.high - trail_dist
                position.sl_price = max(position.sl_price, new_sl)
        else:
            favorable = position.entry_price - candle.low
            if favorable >= trigger_pts:
                position.trailing_active = True
                new_sl = candle.low + trail_dist
                position.sl_price = min(position.sl_price, new_sl)
