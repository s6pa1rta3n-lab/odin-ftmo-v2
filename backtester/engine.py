"""Odin FTMO v2 Backtesting Harness.

Replays 1-minute OHLCV candle data through configurable trading profiles.
Supports both London Reversal and Omni Breakout engines with all 5 design
dimensions (risk sizing, entry mode, pyramiding, exit model, market filters).
"""

import json
import math
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from modules.entry import evaluate_london_entry, evaluate_omni_entry
from modules.pyramid import PyramidManager


class EngineType(Enum):
    LONDON_REVERSAL = "london_reversal"
    OMNI_BREAKOUT = "omni_breakout"


class RiskModel(Enum):
    CONSERVATIVE_RAMP = "conservative_ramp"
    FIXED_LOW = "fixed_low"
    AGGRESSIVE_FLAT = "aggressive_flat"
    KELLY_CRITERION = "kelly_criterion"
    ANTI_MARTINGALE = "anti_martingale"
    VOLATILITY_SCALED = "volatility_scaled"
    EQUITY_CURVE = "equity_curve"


class EntryMode(Enum):
    BLIND_LIMIT = "blind_limit"
    SWEEP_CONFIRMATION = "sweep_confirmation"
    DYNAMIC_BUFFER = "dynamic_buffer"
    TIME_WEIGHTED = "time_weighted"
    ORDER_FLOW_SPREAD_GATE = "order_flow_spread_gate"
    MULTI_TIMEFRAME = "multi_timeframe"
    HYBRID_SWEEP_TIME_SPREAD = "hybrid_sweep_time_spread"


class OmniEntryMode(Enum):
    STOP_ORDER_AT_RANGE = "stop_order_at_range"
    CLOSE_CONFIRMATION = "close_confirmation"
    VOLUME_SPIKE_GATE = "volume_spike_gate"
    RETEST_ENTRY = "retest_entry"
    MOMENTUM_THRESHOLD = "momentum_threshold"
    DUAL_TIMEFRAME = "dual_timeframe"
    HYBRID_RETEST_VOLUME_SPREAD = "hybrid_retest_volume_spread"


class PyramidModel(Enum):
    NO_PYRAMID = "no_pyramid"
    EQUAL_SPLIT = "equal_split"
    FRONT_LOADED = "front_loaded"
    INVERSE_PYRAMID = "inverse_pyramid"
    MOMENTUM_CONFIRMED = "momentum_confirmed"
    RISK_FREE_RUNNER = "risk_free_runner"
    ADAPTIVE_TRANCHE = "adaptive_tranche"


class ExitModel(Enum):
    FIXED_SL_TP = "fixed_sl_tp"
    FIXED_SL_TRAIL = "fixed_sl_trail"
    ATR_DYNAMIC_TRAIL = "atr_dynamic_trail"
    BREAKEVEN_RUNNER = "breakeven_runner"
    TIME_BASED = "time_based"
    CHANDELIER = "chandelier"
    MULTI_TARGET_CASCADE = "multi_target_cascade"


class MarketFilter(Enum):
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


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    direction: int
    entry_price: float
    exit_price: float
    lots: float
    pnl_dollars: float
    pnl_points: float
    exit_reason: str
    tranches: int = 1


@dataclass
class Position:
    direction: int
    entry_price: float
    entry_time: datetime
    lots: float
    sl_price: float
    tp_price: Optional[float]
    trailing_active: bool = False
    trailing_stop: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    tranches_filled: int = 1
    time_in_trade_minutes: int = 0
    partial_closes: list = field(default_factory=list)


@dataclass
class BacktestProfile:
    """A single configuration profile to backtest."""
    engine: EngineType
    risk_model: RiskModel
    entry_mode: str
    pyramid_model: PyramidModel
    exit_model: ExitModel
    filters: list
    instrument: str = "US100.cash"

    def profile_id(self) -> str:
        """Unique identifier string for this profile."""
        filter_str = "+".join(sorted(self.filters)) if self.filters else "none"
        return f"{self.engine.value}|{self.risk_model.value}|{self.entry_mode}|{self.pyramid_model.value}|{self.exit_model.value}|{filter_str}|{self.instrument}"


@dataclass
class BacktestMetrics:
    """Aggregated performance metrics for a completed backtest."""
    profile_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    win_rate: float
    avg_win: float
    avg_loss: float
    avg_rr: float
    max_consecutive_losses: int
    total_days: int
    trades_per_day: float
    starting_equity: float
    ending_equity: float

    def tournament_score(self) -> float:
        """Weighted tournament ranking score.

        Sharpe 40%, Max Drawdown 30%, Profit Factor 20%, Trade Count 10%.
        """
        sharpe_component = max(self.sharpe_ratio, -3.0) * 0.4
        mdd_component = (1.0 - min(abs(self.max_drawdown_pct), 1.0)) * 0.3
        pf_component = min(self.profit_factor, 5.0) / 5.0 * 0.2
        count_component = min(self.total_trades / 100.0, 1.0) * 0.1
        return sharpe_component + mdd_component + pf_component + count_component


class CandleDataLoader:
    """Loads and serves 1-minute candle data from CSV files."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)

    def load(self, symbol: str, start_date: datetime, end_date: datetime) -> list[Candle]:
        """Load candles for a symbol within a date range.

        Searches for CSV files matching the symbol pattern in the data directory.
        Expected CSV format: timestamp,open,high,low,close,volume
        """
        candles = []
        csv_files = []
        resolved_files = set()
        symbol_patterns = [
            f"{symbol}*_m1_*.csv",
            f"{symbol.replace('.', '')}*_m1_*.csv",
            f"{symbol.lower()}*_m1_*.csv",
            f"{symbol.lower().replace('.', '')}*_m1_*.csv",
            f"*{symbol}*_m1_*.csv",
            f"*{symbol.replace('.', '')}*_m1_*.csv",
        ]
        for pattern in symbol_patterns:
            for file_path in sorted(self.data_dir.glob(pattern)):
                resolved = file_path.resolve()
                if file_path not in csv_files and resolved not in resolved_files:
                    csv_files.append(file_path)
                    resolved_files.add(resolved)

        if not csv_files:
            alt_symbol = symbol.lower().replace(".", "").replace("cash", "")
            for pattern in [f"*{alt_symbol}*m1*.csv", f"*{alt_symbol}*_m1_*.csv"]:
                for file_path in sorted(self.data_dir.glob(pattern)):
                    resolved = file_path.resolve()
                    if file_path not in csv_files and resolved not in resolved_files:
                        csv_files.append(file_path)
                        resolved_files.add(resolved)
            if not csv_files and ("us100" in alt_symbol or "nasdaq" in alt_symbol):
                for file_path in sorted(self.data_dir.glob("*usatechidxusd*m1*.csv")):
                    resolved = file_path.resolve()
                    if file_path not in csv_files and resolved not in resolved_files:
                        csv_files.append(file_path)
                        resolved_files.add(resolved)

        for csv_file in csv_files:
            with open(csv_file, "r") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    f.seek(0)
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) < 6:
                            continue
                        try:
                            ts = self._parse_timestamp(row[0])
                        except (ValueError, IndexError):
                            continue
                        if ts < start_date or ts > end_date:
                            continue
                        candles.append(Candle(
                            timestamp=ts,
                            open=float(row[1]),
                            high=float(row[2]),
                            low=float(row[3]),
                            close=float(row[4]),
                            volume=float(row[5]) if len(row) > 5 else 0.0
                        ))
                else:
                    for row in reader:
                        try:
                            ts = self._parse_timestamp(row.get("timestamp", row.get("time", "")))
                        except (ValueError, KeyError):
                            continue
                        if ts < start_date or ts > end_date:
                            continue
                        candles.append(Candle(
                            timestamp=ts,
                            open=float(row.get("open", row.get("Open", 0))),
                            high=float(row.get("high", row.get("High", 0))),
                            low=float(row.get("low", row.get("Low", 0))),
                            close=float(row.get("close", row.get("Close", 0))),
                            volume=float(row.get("volume", row.get("Volume", 0)))
                        ))

        candles.sort(key=lambda c: c.timestamp)
        seen_timestamps = set()
        deduped_candles = []
        for c in candles:
            if c.timestamp not in seen_timestamps:
                seen_timestamps.add(c.timestamp)
                deduped_candles.append(c)
        return deduped_candles

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse various timestamp formats into UTC datetime."""
        ts_str = ts_str.strip()
        if ts_str.isdigit():
            epoch = float(ts_str)
            if epoch > 1e12:
                epoch = epoch / 1000.0
            return datetime.fromtimestamp(epoch, tz=timezone.utc)

        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y.%m.%d %H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(ts_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except ValueError:
                continue

        try:
            epoch = float(ts_str)
            if epoch > 1e12:
                epoch = epoch / 1000.0
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except ValueError:
            raise ValueError(f"Cannot parse timestamp: {ts_str}")


class ATRCalculator:
    """Rolling Average True Range calculator."""

    def __init__(self, period: int = 14):
        self.period = period
        self._values: list[float] = []
        self._prev_close: Optional[float] = None

    def update(self, candle: Candle) -> Optional[float]:
        """Update with a new candle and return current ATR or None if insufficient data."""
        if self._prev_close is not None:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_close),
                abs(candle.low - self._prev_close)
            )
        else:
            tr = candle.high - candle.low

        self._prev_close = candle.close
        self._values.append(tr)

        if len(self._values) < self.period:
            return None

        if len(self._values) > self.period:
            self._values = self._values[-self.period:]

        return sum(self._values) / len(self._values)

    def current(self) -> Optional[float]:
        """Return the current ATR value or None if insufficient data."""
        if len(self._values) < self.period:
            return None
        return sum(self._values) / len(self._values)


class RiskSizer:
    """Computes position size in lots based on the selected risk model."""

    def __init__(self, model: RiskModel, starting_equity: float, tick_value: float = 1.0):
        self.model = model
        self.starting_equity = starting_equity
        self.tick_value = tick_value
        self._recent_trades: list[Trade] = []
        self._equity_history: list[float] = []

    def compute_risk_pct(self, current_equity: float, atr: Optional[float] = None) -> float:
        """Return the risk percentage for the current trade based on the model."""
        if self.model == RiskModel.CONSERVATIVE_RAMP:
            if current_equity < 98000:
                return 0.0025
            elif current_equity < 102000:
                return 0.005
            else:
                return 0.0075
        elif self.model == RiskModel.FIXED_LOW:
            return 0.0035
        elif self.model == RiskModel.AGGRESSIVE_FLAT:
            return 0.0075
        elif self.model == RiskModel.KELLY_CRITERION:
            return self._kelly_f()
        elif self.model == RiskModel.ANTI_MARTINGALE:
            return self._anti_martingale()
        elif self.model == RiskModel.VOLATILITY_SCALED:
            return self._volatility_scaled(atr)
        elif self.model == RiskModel.EQUITY_CURVE:
            return self._equity_curve(current_equity)
        else:
            return 0.005

    def compute_lots(self, current_equity: float, sl_points: float, atr: Optional[float] = None) -> float:
        """Return position size in lots."""
        risk_pct = self.compute_risk_pct(current_equity, atr)
        risk_dollars = current_equity * risk_pct
        if sl_points <= 0:
            return 0.0
        lots = risk_dollars / (sl_points * self.tick_value)
        return max(round(lots, 2), 0.01)

    def record_trade(self, trade: Trade):
        """Record a completed trade for adaptive risk models."""
        self._recent_trades.append(trade)
        if len(self._recent_trades) > 100:
            self._recent_trades = self._recent_trades[-100:]

    def record_equity(self, equity: float):
        """Record current equity for equity curve risk model."""
        self._equity_history.append(equity)
        if len(self._equity_history) > 200:
            self._equity_history = self._equity_history[-200:]

    def _kelly_f(self) -> float:
        if len(self._recent_trades) < 20:
            return 0.0035
        wins = [t for t in self._recent_trades if t.pnl_dollars > 0]
        losses = [t for t in self._recent_trades if t.pnl_dollars < 0]
        if not wins or not losses:
            return 0.0035
        w = len(wins) / len(self._recent_trades)
        avg_win = sum(t.pnl_dollars for t in wins) / len(wins)
        avg_loss = abs(sum(t.pnl_dollars for t in losses) / len(losses))
        if avg_loss == 0:
            return 0.0035
        r = avg_win / avg_loss
        kelly = w - ((1 - w) / r)
        return max(min(kelly * 0.5, 0.01), 0.001)

    def _anti_martingale(self) -> float:
        if len(self._recent_trades) < 3:
            return 0.005
        last_3 = self._recent_trades[-3:]
        consecutive_wins = sum(1 for t in last_3 if t.pnl_dollars > 0)
        if consecutive_wins >= 3:
            return 0.0075
        elif consecutive_wins >= 2:
            return 0.005
        else:
            return 0.0025

    def _volatility_scaled(self, atr: Optional[float]) -> float:
        if atr is None or atr <= 0:
            return 0.005
        target_vol = 50.0
        ratio = target_vol / atr
        scaled = 0.005 * ratio
        return max(min(scaled, 0.01), 0.001)

    def _equity_curve(self, current_equity: float) -> float:
        if len(self._equity_history) < 20:
            return 0.005
        ma = sum(self._equity_history[-20:]) / 20
        if current_equity > ma:
            return 0.005
        return 0.0025


class AsianRangeDetector:
    """Detects Asian session range (00:00-07:00 UTC) from candle data."""

    @staticmethod
    def detect(candles: list[Candle], target_date: datetime) -> tuple[Optional[float], Optional[float]]:
        """Return (high, low) of the Asian range for a given date."""
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        session_end = day_start.replace(hour=7)

        session_candles = [c for c in candles if day_start <= c.timestamp < session_end]
        if not session_candles:
            return None, None

        high = max(c.high for c in session_candles)
        low = min(c.low for c in session_candles)
        return high, low


class USOpenRangeDetector:
    """Detects US Open Range (14:00-14:30 UTC) from candle data."""

    @staticmethod
    def detect(candles: list[Candle], target_date: datetime) -> tuple[Optional[float], Optional[float]]:
        """Return (high, low) of the US open range for a given date."""
        orb_start = target_date.replace(hour=14, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        orb_end = target_date.replace(hour=14, minute=30)

        orb_candles = [c for c in candles if orb_start <= c.timestamp < orb_end]
        if not orb_candles:
            return None, None

        high = max(c.high for c in orb_candles)
        low = min(c.low for c in orb_candles)
        return high, low


class FilterEngine:
    """Evaluates market context filters to decide whether to allow entry."""

    def __init__(self, active_filters: list[str]):
        self.active_filters = set(active_filters)

    def should_trade(self, candle: Candle, atr: Optional[float], range_width: float,
                     spread: float = 1.0, london_result_pnl: float = 0.0) -> bool:
        """Return True if all active filters pass."""
        for f in self.active_filters:
            if not self._check_filter(f, candle, atr, range_width, spread, london_result_pnl):
                return False
        return True

    def _check_filter(self, filter_name: str, candle: Candle, atr: Optional[float],
                      range_width: float, spread: float, london_result_pnl: float) -> bool:
        if filter_name == "atr_gate":
            if atr is None or atr <= 0:
                return True
            ratio = range_width / atr
            return 0.5 <= ratio <= 2.0
        elif filter_name == "vix_regime":
            return True
        elif filter_name == "spread_gate":
            return spread < 5.0
        elif filter_name == "news_blackout":
            return True
        elif filter_name == "pre_session_momentum":
            return True
        elif filter_name == "volatility_percentile":
            return True
        elif filter_name == "day_of_week":
            dow = candle.timestamp.weekday()
            return dow not in (0, 4)
        elif filter_name == "orb_width_gate":
            if atr is None or atr <= 0:
                return True
            ratio = range_width / atr
            return 0.5 <= ratio <= 2.0
        elif filter_name == "pre_open_trend":
            return True
        elif filter_name == "london_session_result":
            if london_result_pnl < 0:
                return True
            return True
        else:
            return True


class ExitManager:
    """Manages position exit logic based on the selected exit model."""

    def __init__(self, model: ExitModel, sl_pts: float = 40.0, tp_pts: float = 20.0, atr: Optional[float] = None):
        self.model = model
        self.sl_pts = sl_pts
        self.tp_pts = tp_pts
        self.atr = atr

    def compute_sl_tp(self, entry_price: float, direction: int) -> tuple[float, Optional[float]]:
        """Return (stop_loss_price, take_profit_price_or_None) for a new position."""
        if self.model == ExitModel.FIXED_SL_TP:
            sl = entry_price - self.sl_pts * direction
            tp = entry_price + self.tp_pts * direction
            return sl, tp
        elif self.model == ExitModel.FIXED_SL_TRAIL:
            sl = entry_price - 30.0 * direction
            return sl, None
        elif self.model == ExitModel.ATR_DYNAMIC_TRAIL:
            atr_val = self.atr if self.atr else 40.0
            sl = entry_price - 1.5 * atr_val * direction
            return sl, None
        elif self.model == ExitModel.BREAKEVEN_RUNNER:
            sl = entry_price - 30.0 * direction
            return sl, None
        elif self.model == ExitModel.TIME_BASED:
            sl = entry_price - 40.0 * direction
            return sl, None
        elif self.model == ExitModel.CHANDELIER:
            atr_val = self.atr if self.atr else 40.0
            sl = entry_price - 3.0 * atr_val * direction
            return sl, None
        elif self.model == ExitModel.MULTI_TARGET_CASCADE:
            sl = entry_price - 30.0 * direction
            return sl, None
        else:
            sl = entry_price - self.sl_pts * direction
            tp = entry_price + self.tp_pts * direction
            return sl, tp

    def check_exit(self, position: Position, candle: Candle) -> Optional[tuple[float, str]]:
        """Check if position should be exited on this candle.

        Returns (exit_price, reason) or None if position stays open.
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
                lowest = position.lowest_price if position.lowest_price > 0 else candle.low
                position.lowest_price = min(lowest, candle.low)
                new_sl = position.lowest_price + 3.0 * atr_val
                position.sl_price = min(position.sl_price, new_sl)
        elif self.model == ExitModel.MULTI_TARGET_CASCADE:
            favorable = (candle.high - position.entry_price) if d == 1 else (position.entry_price - candle.low)
            if favorable >= 15.0 and 0 not in [pc for pc in position.partial_closes]:
                position.partial_closes.append(0)
                position.lots *= 0.67
            if favorable >= 30.0 and 1 not in [pc for pc in position.partial_closes]:
                position.partial_closes.append(1)
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
    def _update_trailing(position: Position, candle: Candle, trigger_pts: float, trail_dist: float):
        """Update trailing stop for a position."""
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


class LondonReversalSimulator:
    """Simulates the London Reversal strategy for a single trading day."""

    def __init__(self, profile: BacktestProfile, equity: float, tick_value: float = 1.0):
        self.profile = profile
        self.equity = equity
        self.tick_value = tick_value

    def simulate_day(self, day_candles: list[Candle], asian_high: float, asian_low: float,
                     atr: Optional[float], risk_sizer: RiskSizer) -> list[Trade]:
        """Simulate one day of London Reversal trading.

        London session: 07:00-13:00 UTC.
        """
        trades = []
        london_candles = [c for c in day_candles if 7 <= c.timestamp.hour < 13]
        if not london_candles:
            return trades

        range_width = asian_high - asian_low
        if range_width <= 0:
            return trades

        filter_engine = FilterEngine(self.profile.filters)
        if not filter_engine.should_trade(london_candles[0], atr, range_width):
            return trades

        exit_manager = ExitManager(
            self.profile.exit_model,
            sl_pts=40.0,
            tp_pts=20.0,
            atr=atr
        )

        sl_pts = self._get_sl_pts(atr)
        lots = risk_sizer.compute_lots(self.equity, sl_pts, atr)
        if lots <= 0:
            return trades

        pyramid_manager = PyramidManager(self.profile.pyramid_model, total_planned_lots=lots)
        initial_lots = pyramid_manager.get_initial_lots()

        position: Optional[Position] = None
        trade_taken = False

        for candle in london_candles:
            if position is not None:
                scale_in = pyramid_manager.check_scale_in(position, candle)
                if scale_in is not None:
                    position.lots = round(position.lots + scale_in.additional_lots, 2)
                    position.tranches_filled = scale_in.tranche_index
                    if scale_in.move_to_be and scale_in.new_sl is not None:
                        if position.direction == 1:
                            position.sl_price = max(position.sl_price, scale_in.new_sl)
                        else:
                            position.sl_price = min(position.sl_price, scale_in.new_sl)

                scale_out = pyramid_manager.check_scale_out(position, candle)
                if scale_out is not None:
                    scalp_pts = (scale_out.exit_price - position.entry_price) * position.direction
                    scalp_dollars = scalp_pts * scale_out.lots_to_close * self.tick_value
                    self.equity += scalp_dollars
                    position.lots = max(round(position.lots - scale_out.lots_to_close, 2), 0.01)
                    position.partial_closes.append(scale_out.fraction_to_close)
                    if scale_out.move_to_be and scale_out.new_sl is not None:
                        position.sl_price = scale_out.new_sl
                        position.trailing_active = True

                exit_result = exit_manager.check_exit(position, candle)
                if exit_result:
                    exit_price, reason = exit_result
                    pnl_pts = (exit_price - position.entry_price) * position.direction
                    pnl_dollars = pnl_pts * position.lots * self.tick_value
                    trade = Trade(
                        entry_time=position.entry_time,
                        exit_time=candle.timestamp,
                        direction=position.direction,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        lots=position.lots,
                        pnl_dollars=pnl_dollars,
                        pnl_points=pnl_pts,
                        exit_reason=reason,
                        tranches=position.tranches_filled
                    )
                    trades.append(trade)
                    self.equity += pnl_dollars
                    risk_sizer.record_trade(trade)
                    position = None
                continue

            if trade_taken:
                continue

            entry_result = self._check_entry(candle, asian_high, asian_low, atr)
            if entry_result:
                direction, entry_price = entry_result
                sl_price, tp_price = exit_manager.compute_sl_tp(entry_price, direction)
                position = Position(
                    direction=direction,
                    entry_price=entry_price,
                    entry_time=candle.timestamp,
                    lots=initial_lots,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    highest_price=entry_price,
                    lowest_price=entry_price
                )
                trade_taken = True

        if position is not None:
            exit_price = london_candles[-1].close
            pnl_pts = (exit_price - position.entry_price) * position.direction
            pnl_dollars = pnl_pts * position.lots * self.tick_value
            trade = Trade(
                entry_time=position.entry_time,
                exit_time=london_candles[-1].timestamp,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=exit_price,
                lots=position.lots,
                pnl_dollars=pnl_dollars,
                pnl_points=pnl_pts,
                exit_reason="session_close",
                tranches=position.tranches_filled
            )
            trades.append(trade)
            self.equity += pnl_dollars
            risk_sizer.record_trade(trade)

        return trades

    def _check_entry(self, candle: Candle, asian_high: float, asian_low: float,
                     atr: Optional[float]) -> Optional[tuple[int, float]]:
        """Check if entry conditions are met.

        Returns (direction, entry_price) or None.
        direction: 1 = long (fade low), -1 = short (fade high).
        """
        return evaluate_london_entry(self.profile.entry_mode, candle, asian_high, asian_low, atr)

    def _get_sl_pts(self, atr: Optional[float]) -> float:
        """Return the stop-loss distance in points for position sizing."""
        if self.profile.exit_model == ExitModel.ATR_DYNAMIC_TRAIL:
            return (atr * 1.5) if atr else 40.0
        elif self.profile.exit_model == ExitModel.CHANDELIER:
            return (atr * 3.0) if atr else 40.0
        else:
            return 40.0


class OmniBreakoutSimulator:
    """Simulates the Omni Breakout strategy for a single trading day."""

    def __init__(self, profile: BacktestProfile, equity: float, tick_value: float = 1.0):
        self.profile = profile
        self.equity = equity
        self.tick_value = tick_value

    def simulate_day(self, day_candles: list[Candle], orb_high: float, orb_low: float,
                     atr: Optional[float], risk_sizer: RiskSizer,
                     london_pnl: float = 0.0) -> list[Trade]:
        """Simulate one day of Omni Breakout trading.

        US session: 14:30-20:00 UTC (after ORB formation 14:00-14:30).
        """
        trades = []
        us_candles = [c for c in day_candles
                      if (c.timestamp.hour == 14 and c.timestamp.minute >= 30) or c.timestamp.hour > 14]
        us_candles = [c for c in us_candles if c.timestamp.hour < 20]
        if not us_candles:
            return trades

        range_width = orb_high - orb_low
        if range_width <= 0:
            return trades

        filter_engine = FilterEngine(self.profile.filters)
        if not filter_engine.should_trade(us_candles[0], atr, range_width, london_result_pnl=london_pnl):
            return trades

        exit_manager = ExitManager(
            self.profile.exit_model,
            sl_pts=75.0,
            tp_pts=50.0,
            atr=atr
        )

        sl_pts = 75.0
        if self.profile.exit_model == ExitModel.ATR_DYNAMIC_TRAIL and atr:
            sl_pts = atr * 1.5
        lots = risk_sizer.compute_lots(self.equity, sl_pts, atr)
        if lots <= 0:
            return trades

        pyramid_manager = PyramidManager(self.profile.pyramid_model, total_planned_lots=lots)
        initial_lots = pyramid_manager.get_initial_lots()

        position: Optional[Position] = None
        trade_taken = False

        for candle in us_candles:
            if position is not None:
                scale_in = pyramid_manager.check_scale_in(position, candle)
                if scale_in is not None:
                    position.lots = round(position.lots + scale_in.additional_lots, 2)
                    position.tranches_filled = scale_in.tranche_index
                    if scale_in.move_to_be and scale_in.new_sl is not None:
                        if position.direction == 1:
                            position.sl_price = max(position.sl_price, scale_in.new_sl)
                        else:
                            position.sl_price = min(position.sl_price, scale_in.new_sl)

                scale_out = pyramid_manager.check_scale_out(position, candle)
                if scale_out is not None:
                    scalp_pts = (scale_out.exit_price - position.entry_price) * position.direction
                    scalp_dollars = scalp_pts * scale_out.lots_to_close * self.tick_value
                    self.equity += scalp_dollars
                    position.lots = max(round(position.lots - scale_out.lots_to_close, 2), 0.01)
                    position.partial_closes.append(scale_out.fraction_to_close)
                    if scale_out.move_to_be and scale_out.new_sl is not None:
                        position.sl_price = scale_out.new_sl
                        position.trailing_active = True

                exit_result = exit_manager.check_exit(position, candle)
                if exit_result:
                    exit_price, reason = exit_result
                    pnl_pts = (exit_price - position.entry_price) * position.direction
                    pnl_dollars = pnl_pts * position.lots * self.tick_value
                    trade = Trade(
                        entry_time=position.entry_time,
                        exit_time=candle.timestamp,
                        direction=position.direction,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        lots=position.lots,
                        pnl_dollars=pnl_dollars,
                        pnl_points=pnl_pts,
                        exit_reason=reason,
                        tranches=position.tranches_filled
                    )
                    trades.append(trade)
                    self.equity += pnl_dollars
                    risk_sizer.record_trade(trade)
                    position = None
                continue

            if trade_taken:
                continue

            entry_result = self._check_entry(candle, orb_high, orb_low, atr)
            if entry_result:
                direction, entry_price = entry_result
                sl_price, tp_price = exit_manager.compute_sl_tp(entry_price, direction)
                position = Position(
                    direction=direction,
                    entry_price=entry_price,
                    entry_time=candle.timestamp,
                    lots=initial_lots,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    highest_price=entry_price,
                    lowest_price=entry_price
                )
                trade_taken = True

        if position is not None:
            exit_price = us_candles[-1].close
            pnl_pts = (exit_price - position.entry_price) * position.direction
            pnl_dollars = pnl_pts * position.lots * self.tick_value
            trade = Trade(
                entry_time=position.entry_time,
                exit_time=us_candles[-1].timestamp,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=exit_price,
                lots=position.lots,
                pnl_dollars=pnl_dollars,
                pnl_points=pnl_pts,
                exit_reason="session_close",
                tranches=position.tranches_filled
            )
            trades.append(trade)
            self.equity += pnl_dollars
            risk_sizer.record_trade(trade)

        return trades

    def _check_entry(self, candle: Candle, orb_high: float, orb_low: float,
                     atr: Optional[float]) -> Optional[tuple[int, float]]:
        """Check breakout entry conditions.

        Returns (direction, entry_price) or None.
        """
        return evaluate_omni_entry(self.profile.entry_mode, candle, orb_high, orb_low, atr)


class BacktestEngine:
    """Main backtesting orchestrator.

    Runs a profile through historical candle data and computes metrics.
    """

    def __init__(self, profile: BacktestProfile, candles: Optional[list[Candle]] = None,
                 starting_equity: float = 100000.0, tick_value: float = 1.0,
                 commission_per_lot: float = 0.0,
                 trading_days: Optional[list[tuple[datetime, list[Candle]]]] = None):
        """Initialize backtest engine with profile and historical candles or pre-grouped days."""
        self.profile = profile
        self.candles = candles if candles is not None else []
        self.starting_equity = starting_equity
        self.tick_value = tick_value
        self.commission_per_lot = commission_per_lot
        self.trading_days = trading_days

    def run(self) -> BacktestMetrics:
        """Execute the backtest and return aggregated metrics."""
        equity = self.starting_equity
        all_trades: list[Trade] = []
        risk_sizer = RiskSizer(self.profile.risk_model, self.starting_equity, self.tick_value)
        atr_calc = ATRCalculator(period=14)

        trading_days = self.trading_days if self.trading_days is not None else self._group_by_day()

        for day_item in trading_days:
            if len(day_item) == 5:
                day_date, day_candles, range_high, range_low, atr = day_item
            else:
                day_date, day_candles = day_item[0], day_item[1]
                for c in day_candles:
                    atr_calc.update(c)
                atr = atr_calc.current()
                if self.profile.engine == EngineType.LONDON_REVERSAL:
                    range_high, range_low = AsianRangeDetector.detect(day_candles, day_date)
                elif self.profile.engine == EngineType.OMNI_BREAKOUT:
                    range_high, range_low = USOpenRangeDetector.detect(day_candles, day_date)
                else:
                    range_high, range_low = None, None

            if range_high is None or range_low is None:
                continue

            risk_sizer.record_equity(equity)

            if self.profile.engine == EngineType.LONDON_REVERSAL:
                sim = LondonReversalSimulator(self.profile, equity, self.tick_value)
                day_trades = sim.simulate_day(day_candles, range_high, range_low, atr, risk_sizer)
                equity = sim.equity

            elif self.profile.engine == EngineType.OMNI_BREAKOUT:
                sim = OmniBreakoutSimulator(self.profile, equity, self.tick_value)
                day_trades = sim.simulate_day(day_candles, range_high, range_low, atr, risk_sizer)
                equity = sim.equity
            else:
                continue

            for trade in day_trades:
                commission = trade.lots * self.commission_per_lot * 2
                trade.pnl_dollars -= commission
                equity -= commission

            all_trades.extend(day_trades)

        return self._compute_metrics(all_trades, equity)

    @staticmethod
    def group_candles_by_day(candles: list[Candle]) -> list[tuple[datetime, list[Candle]]]:
        """Group candles by trading day."""
        days: dict[str, list[Candle]] = {}
        for c in candles:
            day_key = c.timestamp.strftime("%Y-%m-%d")
            if day_key not in days:
                days[day_key] = []
            days[day_key].append(c)

        result = []
        for day_key in sorted(days.keys()):
            day_date = datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            result.append((day_date, days[day_key]))
        return result

    def _group_by_day(self) -> list[tuple[datetime, list[Candle]]]:
        """Group candles by trading day using instance candles."""
        return self.group_candles_by_day(self.candles)

    def _compute_metrics(self, trades: list[Trade], ending_equity: float) -> BacktestMetrics:
        """Compute aggregated metrics from trade list."""
        if not trades:
            return BacktestMetrics(
                profile_id=self.profile.profile_id(),
                total_trades=0, winning_trades=0, losing_trades=0,
                total_pnl=0.0, max_drawdown=0.0, max_drawdown_pct=0.0,
                sharpe_ratio=0.0, profit_factor=0.0, win_rate=0.0,
                avg_win=0.0, avg_loss=0.0, avg_rr=0.0,
                max_consecutive_losses=0, total_days=0, trades_per_day=0.0,
                starting_equity=self.starting_equity, ending_equity=ending_equity
            )

        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars <= 0]

        total_pnl = sum(t.pnl_dollars for t in trades)
        gross_profit = sum(t.pnl_dollars for t in wins) if wins else 0.0
        gross_loss = abs(sum(t.pnl_dollars for t in losses)) if losses else 0.0

        equity_curve = [self.starting_equity]
        for t in trades:
            equity_curve.append(equity_curve[-1] + t.pnl_dollars)

        peak = equity_curve[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = dd / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        daily_returns = []
        prev_eq = self.starting_equity
        for t in trades:
            ret = t.pnl_dollars / prev_eq if prev_eq > 0 else 0.0
            daily_returns.append(ret)
            prev_eq += t.pnl_dollars

        if len(daily_returns) > 1:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_ret = math.sqrt(variance) if variance > 0 else 1e-10
            sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0.0
        else:
            sharpe = 0.0

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        avg_rr = avg_win / avg_loss if avg_loss > 0 else 0.0

        max_consec_loss = 0
        current_streak = 0
        for t in trades:
            if t.pnl_dollars <= 0:
                current_streak += 1
                max_consec_loss = max(max_consec_loss, current_streak)
            else:
                current_streak = 0

        if trades:
            first_day = trades[0].entry_time
            last_day = trades[-1].entry_time
            total_days = max((last_day - first_day).days, 1)
        else:
            total_days = 0

        return BacktestMetrics(
            profile_id=self.profile.profile_id(),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            win_rate=len(wins) / len(trades) if trades else 0.0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_rr=avg_rr,
            max_consecutive_losses=max_consec_loss,
            total_days=total_days,
            trades_per_day=len(trades) / total_days if total_days > 0 else 0.0,
            starting_equity=self.starting_equity,
            ending_equity=ending_equity
        )
