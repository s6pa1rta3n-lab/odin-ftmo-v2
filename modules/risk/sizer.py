"""Position sizing engine using dictionary dispatch for Python 3.9 compatibility."""

from typing import Any, Dict, List, Optional
from modules.risk.models import (
    RiskModel,
    calculate_aggressive_flat,
    calculate_anti_martingale,
    calculate_conservative_ramp,
    calculate_equity_curve,
    calculate_fixed_low,
    calculate_kelly_criterion,
    calculate_volatility_scaled,
)


class RiskSizer:
    """Computes risk percentages and lot sizes across all 7 risk models."""

    def __init__(
        self,
        model: Any,
        starting_equity: float,
        tick_value: float = 1.0,
        min_lots: float = 0.01,
        max_lots: float = 50.0,
    ) -> None:
        """Initialize risk sizer.

        Parameters:
            model: RiskModel enum instance or string identifier.
            starting_equity: Account starting equity.
            tick_value: Dollar value per point per lot.
            min_lots: Minimum allowable lot size.
            max_lots: Maximum allowable lot size.
        """
        if isinstance(model, str):
            model_key = model.lower()
            try:
                self.model = RiskModel(model_key)
            except ValueError:
                self.model = RiskModel.CONSERVATIVE_RAMP
        else:
            self.model = model

        self.starting_equity = starting_equity
        self.tick_value = tick_value
        self.min_lots = min_lots
        self.max_lots = max_lots
        self._recent_trades: List[Any] = []
        self._equity_history: List[float] = []

        self._dispatch_table = {
            RiskModel.CONSERVATIVE_RAMP: self._eval_conservative_ramp,
            RiskModel.FIXED_LOW: self._eval_fixed_low,
            RiskModel.AGGRESSIVE_FLAT: self._eval_aggressive_flat,
            RiskModel.KELLY_CRITERION: self._eval_kelly_criterion,
            RiskModel.ANTI_MARTINGALE: self._eval_anti_martingale,
            RiskModel.VOLATILITY_SCALED: self._eval_volatility_scaled,
            RiskModel.EQUITY_CURVE: self._eval_equity_curve,
        }

    def compute_risk_pct(self, current_equity: float, atr: Optional[float] = None) -> float:
        """Compute the fractional risk percentage based on the selected risk model.

        Parameters:
            current_equity: Current account equity in dollars.
            atr: Current ATR in points if available.

        Returns:
            Calculated fractional risk percentage.
        """
        handler = self._dispatch_table.get(self.model, self._eval_default)
        return handler(current_equity, atr)

    def compute_lots(
        self,
        current_equity: float,
        sl_points: float,
        atr: Optional[float] = None,
    ) -> float:
        """Compute position volume in lots clamped to bounds.

        Parameters:
            current_equity: Current account equity in dollars.
            sl_points: Distance from entry to stop loss in points.
            atr: Current ATR in points if available.

        Returns:
            Position lot size rounded to 2 decimal places.
        """
        if sl_points <= 0:
            return 0.0
        risk_pct = self.compute_risk_pct(current_equity, atr)
        risk_dollars = current_equity * risk_pct
        calculated_lots = risk_dollars / (sl_points * self.tick_value)
        clamped_lots = max(min(round(calculated_lots, 2), self.max_lots), self.min_lots)
        return clamped_lots

    def record_trade(self, trade: Any) -> None:
        """Record completed trade object or numeric PnL.

        Parameters:
            trade: Trade dataclass instance or numeric dollar PnL.
        """
        self._recent_trades.append(trade)
        if len(self._recent_trades) > 100:
            self._recent_trades = self._recent_trades[-100:]

    def record_equity(self, equity: float) -> None:
        """Record equity timestamp reading for equity-curve tracking.

        Parameters:
            equity: Account equity in dollars.
        """
        self._equity_history.append(equity)
        if len(self._equity_history) > 200:
            self._equity_history = self._equity_history[-200:]

    def _get_pnls(self) -> List[float]:
        pnls: List[float] = []
        for t in self._recent_trades:
            if hasattr(t, "pnl_dollars"):
                pnls.append(float(t.pnl_dollars))
            elif isinstance(t, (int, float)):
                pnls.append(float(t))
            elif isinstance(t, dict) and "pnl_dollars" in t:
                pnls.append(float(t["pnl_dollars"]))
        return pnls

    def _eval_conservative_ramp(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_conservative_ramp(current_equity)

    def _eval_fixed_low(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_fixed_low()

    def _eval_aggressive_flat(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_aggressive_flat()

    def _eval_kelly_criterion(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_kelly_criterion(self._get_pnls())

    def _eval_anti_martingale(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_anti_martingale(self._get_pnls())

    def _eval_volatility_scaled(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_volatility_scaled(atr)

    def _eval_equity_curve(self, current_equity: float, atr: Optional[float]) -> float:
        return calculate_equity_curve(current_equity, self._equity_history)

    def _eval_default(self, current_equity: float, atr: Optional[float]) -> float:
        return 0.0050
