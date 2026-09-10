"""Observation-only paper trading harness for FTMO prop trading engines.

Concurrently evaluates top 10 London Reversal profiles and top 10 Omni Breakout profiles
in observation-only mode over a minimum 72-hour window (at least 5 trading sessions).
Strictly enforces a 0.01 micro-lot maximum execution volume, realistic tick spread
and slippage models, daily watermark tracking, and an intra-day 4.5% circuit breaker.
"""

import argparse
import asyncio
import csv
import glob
import json
import logging
import math
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.entry import evaluate_london_entry, evaluate_omni_entry
from modules.exit import ExitManager
from modules.filters import FilterEngine
from modules.pyramid import PyramidManager
from modules.risk import RiskSizer
from verifier.validator import validate_profile

try:
    from MetaApiWrapper import MetaApiWrapper
except ImportError:
    MetaApiWrapper = None


@dataclass
class CandleBar:
    """1-minute OHLCV candle representation."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class SimulatedPosition:
    """Active simulated position state for a profile."""

    direction: int
    entry_price: float
    lots: float
    sl_price: float
    tp_price: Optional[float]
    highest_price: float
    lowest_price: float
    entry_time: datetime
    trailing_active: bool = False
    time_in_trade_minutes: int = 0
    partial_closes: List[Any] = field(default_factory=list)
    tranches_filled: int = 1
    total_planned_lots: float = 0.01


@dataclass
class SimulatedTradeRecord:
    """Completed virtual trade audit record."""

    profile_id: str
    engine: str
    side: str
    entry_price: float
    exit_price: float
    lots: float
    entry_time: str
    exit_time: str
    pnl: float
    exit_reason: str


@dataclass
class VirtualAccountState:
    """Isolated virtual account state for a specific strategy profile."""

    profile: Dict[str, Any]
    engine_type: str
    profile_id: str
    balance: float = 94939.28
    equity: float = 94939.28
    daily_start_equity: float = 94939.28
    daily_watermark: float = 94939.28
    daily_pnl: float = 0.0
    intra_day_max_dd: float = 0.0
    max_drawdown: float = 0.0
    position: Optional[SimulatedPosition] = None
    trades: List[SimulatedTradeRecord] = field(default_factory=list)
    circuit_breaker_tripped: bool = False
    circuit_breaker_floor: float = 90667.01
    active_orders: List[Dict[str, Any]] = field(default_factory=list)
    daily_trades_count: int = 0
    current_day_str: str = ""

    def __post_init__(self) -> None:
        """Initialize calculated fields."""
        self.circuit_breaker_floor = self.daily_start_equity * (1.0 - 0.045)


class PaperTradingHarness:
    """Event-driven observation-only paper trading harness."""

    def __init__(
        self,
        london_profiles_dir: str = "profiles/london_reversal/top_10",
        omni_profiles_dir: str = "profiles/omni_breakout/top_10",
        log_file: str = "paper_trades.log",
        telemetry_file: str = "paper_trade_telemetry.json",
        spread_pts: float = 1.5,
        slippage_pts: float = 0.2,
        initial_equity: float = 94939.28,
        tick_value: float = 1.0,
    ) -> None:
        """Initialize paper trading harness with configuration and logging."""
        self.london_profiles_dir = Path(london_profiles_dir)
        self.omni_profiles_dir = Path(omni_profiles_dir)
        self.log_file = log_file
        self.telemetry_file = telemetry_file
        self.spread_pts = spread_pts
        self.slippage_pts = slippage_pts
        self.initial_equity = initial_equity
        self.tick_value = tick_value

        self.logger = self._setup_logger()
        self.accounts: Dict[str, VirtualAccountState] = {}
        self.exit_managers: Dict[str, ExitManager] = {}
        self.risk_sizers: Dict[str, RiskSizer] = {}
        self.pyramid_managers: Dict[str, PyramidManager] = {}
        self.filter_engines: Dict[str, FilterEngine] = {}

        self.asian_high: float = 0.0
        self.asian_low: float = 0.0
        self.orb_high: float = 0.0
        self.orb_low: float = 0.0
        self.current_atr: float = 40.0
        self.atr_history: List[float] = []
        self.daily_contexts: Dict[str, Dict[str, Any]] = {}
        self.session_counts: Dict[str, int] = {"london": 0, "omni": 0}
        self.evaluated_days: set = set()
        self.current_date_str: str = ""

        self._load_and_initialize_profiles()

    def _setup_logger(self) -> logging.Logger:
        """Set up dedicated paper trading file and stream logger."""
        logger = logging.getLogger("PAPER_TRADER")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        formatter = logging.Formatter("[%(asctime)s] [PAPER_TRADER] %(message)s")

        fh = logging.FileHandler(self.log_file, mode="w")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        return logger

    def _load_and_initialize_profiles(self) -> None:
        """Load and validate all top 10 profiles for both engines."""
        london_files = sorted(glob.glob(str(self.london_profiles_dir / "*.json")))
        omni_files = sorted(glob.glob(str(self.omni_profiles_dir / "*.json")))

        if not london_files:
            raise FileNotFoundError(f"No London Reversal profiles found in {self.london_profiles_dir}")
        if not omni_files:
            raise FileNotFoundError(f"No Omni Breakout profiles found in {self.omni_profiles_dir}")

        for p_file in london_files:
            with open(p_file, "r") as f:
                profile = json.load(f)
            is_valid, violations, _ = validate_profile(profile)
            if not is_valid:
                raise ValueError(f"Profile {p_file} failed formal verification: {violations}")
            self._register_profile(profile, "london_reversal")

        for p_file in omni_files:
            with open(p_file, "r") as f:
                profile = json.load(f)
            is_valid, violations, _ = validate_profile(profile)
            if not is_valid:
                raise ValueError(f"Profile {p_file} failed formal verification: {violations}")
            self._register_profile(profile, "omni_breakout")

        self.logger.info(
            f"Initialized Paper Trader with {len(self.accounts)} total profiles "
            f"({len(london_files)} London Reversal, {len(omni_files)} Omni Breakout)."
        )

    def _register_profile(self, profile: Dict[str, Any], engine_type: str) -> None:
        """Instantiate tracking account and modular components for a profile."""
        profile_id = profile["profile_id"]
        dims = profile["dimensions"]
        params = profile.get("parameters", {})

        account = VirtualAccountState(
            profile=profile,
            engine_type=engine_type,
            profile_id=profile_id,
            balance=self.initial_equity,
            equity=self.initial_equity,
            daily_start_equity=self.initial_equity,
            daily_watermark=self.initial_equity,
        )
        self.accounts[profile_id] = account

        risk_model = dims["risk_model"]
        exit_model = dims["exit_model"]
        pyramid_model = dims["pyramid_model"]
        filters = dims.get("filters", [])

        sl_pts = float(params.get("sl_pts", 40.0))
        tp_pts = float(params.get("tp_pts", 20.0))

        self.risk_sizers[profile_id] = RiskSizer(risk_model, starting_equity=self.initial_equity)
        self.exit_managers[profile_id] = ExitManager(
            exit_model,
            sl_pts=sl_pts,
            tp_pts=tp_pts,
            atr=self.current_atr,
        )
        self.pyramid_managers[profile_id] = PyramidManager(
            pyramid_model,
            total_planned_lots=0.01,
        )
        self.filter_engines[profile_id] = FilterEngine(filters)

    def _check_circuit_breaker(self, account: VirtualAccountState, current_candle: CandleBar) -> bool:
        """Evaluate mark-to-market daily loss limit (4.5% circuit breaker)."""
        if account.circuit_breaker_tripped:
            return True

        intra_day_loss = account.daily_start_equity - account.equity
        max_allowed_loss = account.daily_start_equity * 0.045

        if intra_day_loss >= max_allowed_loss or account.equity <= account.circuit_breaker_floor:
            account.circuit_breaker_tripped = True
            self.logger.warning(
                f"[CIRCUIT BREAKER TRIGGERED] Profile {account.profile_id} hit 4.5% daily drawdown! "
                f"Equity: ${account.equity:.2f} | Floor: ${account.circuit_breaker_floor:.2f} | "
                f"Daily Start: ${account.daily_start_equity:.2f}. Halting trading for day."
            )
            if account.position is not None:
                self._close_position(
                    account,
                    current_candle.close,
                    current_candle.timestamp,
                    "CIRCUIT_BREAKER_4.5%_HALT",
                )
            account.active_orders.clear()
            return True

        return False

    def _close_position(
        self,
        account: VirtualAccountState,
        price: float,
        timestamp: datetime,
        reason: str,
    ) -> None:
        """Close open virtual position with realistic spread and audit record."""
        pos = account.position
        if pos is None:
            return

        exit_price = (
            price - (self.spread_pts / 2.0) - self.slippage_pts
            if pos.direction == 1
            else price + (self.spread_pts / 2.0) + self.slippage_pts
        )

        pts_gain = (exit_price - pos.entry_price) if pos.direction == 1 else (pos.entry_price - exit_price)
        pnl = pts_gain * pos.lots * self.tick_value

        account.balance += pnl
        account.equity = account.balance
        account.daily_pnl += pnl

        record = SimulatedTradeRecord(
            profile_id=account.profile_id,
            engine=account.engine_type,
            side="LONG" if pos.direction == 1 else "SHORT",
            entry_price=pos.entry_price,
            exit_price=exit_price,
            lots=pos.lots,
            entry_time=pos.entry_time.isoformat(),
            exit_time=timestamp.isoformat(),
            pnl=round(pnl, 4),
            exit_reason=reason,
        )
        account.trades.append(record)
        account.position = None

        self.logger.info(
            f"[TRADE CLOSED] {account.engine_type.upper()} | Profile: {account.profile_id} | "
            f"Side: {record.side} | Lots: {record.lots:.2f} | Entry: {record.entry_price:.2f} | "
            f"Exit: {record.exit_price:.2f} | PnL: ${record.pnl:+.2f} | Reason: {reason} | "
            f"Bal: ${account.balance:.2f}"
        )

    def process_candle(self, candle: CandleBar) -> None:
        """Process incoming 1-minute candle across all virtual profile accounts."""
        day_str = candle.timestamp.strftime("%Y-%m-%d")
        dt = candle.timestamp

        for acct in self.accounts.values():
            if acct.current_day_str != day_str:
                if acct.current_day_str:
                    acct.daily_start_equity = acct.equity
                    acct.daily_watermark = acct.equity
                    acct.circuit_breaker_floor = acct.daily_start_equity * (1.0 - 0.045)
                    acct.daily_pnl = 0.0
                    acct.daily_trades_count = 0
                    acct.circuit_breaker_tripped = False
                acct.current_day_str = day_str

        if self.current_date_str != day_str:
            self.current_date_str = day_str
            self.asian_high = 0.0
            self.asian_low = 0.0
            self.orb_high = 0.0
            self.orb_low = 0.0

        self.evaluated_days.add(day_str)

        self._update_indicators(candle)

        for acct in self.accounts.values():
            self._update_virtual_equity(acct, candle)

            if self._check_circuit_breaker(acct, candle):
                continue

            if acct.engine_type == "london_reversal":
                self._process_london_profile(acct, candle)
            elif acct.engine_type == "omni_breakout":
                self._process_omni_profile(acct, candle)

    def _update_indicators(self, candle: CandleBar) -> None:
        """Update Asian range, ORB range, and ATR indicators."""
        dt = candle.timestamp
        hour = dt.hour
        minute = dt.minute

        if hour < 7:
            if self.asian_high == 0.0:
                self.asian_high = candle.high
                self.asian_low = candle.low
            else:
                self.asian_high = max(self.asian_high, candle.high)
                self.asian_low = min(self.asian_low, candle.low)

        if hour == 14 and minute < 30:
            if self.orb_high == 0.0:
                self.orb_high = candle.high
                self.orb_low = candle.low
            else:
                self.orb_high = max(self.orb_high, candle.high)
                self.orb_low = min(self.orb_low, candle.low)

        hl_range = candle.high - candle.low
        self.atr_history.append(hl_range)
        if len(self.atr_history) > 1440:
            self.atr_history.pop(0)
        if len(self.atr_history) >= 14:
            self.current_atr = sum(self.atr_history[-14:]) / 14.0

    def _update_virtual_equity(self, account: VirtualAccountState, candle: CandleBar) -> None:
        """Update floating equity and compute current drawdowns."""
        if account.position is not None:
            pos = account.position
            bid = candle.close - (self.spread_pts / 2.0)
            ask = candle.close + (self.spread_pts / 2.0)
            curr_price = bid if pos.direction == 1 else ask
            pts = (curr_price - pos.entry_price) if pos.direction == 1 else (pos.entry_price - curr_price)
            unrealized = pts * pos.lots * self.tick_value
            account.equity = account.balance + unrealized
        else:
            account.equity = account.balance

        if account.equity > account.daily_watermark:
            account.daily_watermark = account.equity

        dd = max(0.0, self.initial_equity - account.equity)
        account.max_drawdown = max(account.max_drawdown, dd)

        intra_dd = max(0.0, account.daily_watermark - account.equity)
        account.intra_day_max_dd = max(account.intra_day_max_dd, intra_dd)

    def _process_london_profile(self, account: VirtualAccountState, candle: CandleBar) -> None:
        """Evaluate entry, stop management, and liquidation for London Reversal."""
        dt = candle.timestamp
        hour = dt.hour

        if hour == 13 and account.position is not None:
            self._close_position(account, candle.close, dt, "13:00_UTC_SESSION_END")
            account.active_orders.clear()
            return

        if hour < 7 or hour >= 13:
            return

        exit_mgr = self.exit_managers[account.profile_id]
        pyramid_mgr = self.pyramid_managers[account.profile_id]
        filter_eng = self.filter_engines[account.profile_id]
        pos = account.position

        if pos is not None:
            pos.highest_price = max(pos.highest_price, candle.high)
            pos.lowest_price = min(pos.lowest_price, candle.low)

            scale_out = pyramid_mgr.check_scale_out(pos, candle)
            if scale_out is not None:
                pos.partial_closes.append(scale_out.fraction_to_close)
                if scale_out.move_to_be and scale_out.new_sl is not None:
                    pos.sl_price = scale_out.new_sl
                    pos.trailing_active = True

            scale_in = pyramid_mgr.check_scale_in(pos, candle)
            if scale_in is not None:
                pos.lots = min(round(pos.lots + scale_in.additional_lots, 4), 0.01)
                pos.tranches_filled = scale_in.tranche_index
                if scale_in.move_to_be and scale_in.new_sl is not None:
                    if pos.direction == 1:
                        pos.sl_price = max(pos.sl_price, scale_in.new_sl)
                    else:
                        pos.sl_price = min(pos.sl_price, scale_in.new_sl)

            exit_result = exit_mgr.check_exit(pos, candle)
            if exit_result is not None:
                exit_price, reason = exit_result
                self._close_position(account, exit_price, dt, reason)
            return

        if account.daily_trades_count >= 1:
            return

        if self.asian_high <= 0 or self.asian_low <= 0:
            return

        range_width = self.asian_high - self.asian_low
        filters_passed = filter_eng.should_trade(
            candle=candle,
            atr=self.current_atr,
            range_width=range_width,
            spread=self.spread_pts,
        )
        if not filters_passed:
            return

        entry_mode = account.profile["dimensions"]["entry_mode"]
        signal = evaluate_london_entry(
            entry_mode,
            candle,
            self.asian_high,
            self.asian_low,
            self.current_atr,
        )

        if signal is not None:
            direction, ref_price = signal
            self._execute_simulated_entry(account, direction, ref_price, candle, "LONDON_ENTRY")

    def _process_omni_profile(self, account: VirtualAccountState, candle: CandleBar) -> None:
        """Evaluate entry, stop management, and liquidation for Omni Breakout."""
        dt = candle.timestamp
        hour = dt.hour
        minute = dt.minute

        if (hour > 19 or (hour == 19 and minute >= 45)) and account.position is not None:
            self._close_position(account, candle.close, dt, "19:45_UTC_EOD_LIQUIDATION")
            account.active_orders.clear()
            return

        if hour < 14 or (hour == 14 and minute < 30) or hour >= 20:
            return

        exit_mgr = self.exit_managers[account.profile_id]
        pyramid_mgr = self.pyramid_managers[account.profile_id]
        filter_eng = self.filter_engines[account.profile_id]
        pos = account.position

        if pos is not None:
            pos.highest_price = max(pos.highest_price, candle.high)
            pos.lowest_price = min(pos.lowest_price, candle.low)

            scale_out = pyramid_mgr.check_scale_out(pos, candle)
            if scale_out is not None:
                pos.partial_closes.append(scale_out.fraction_to_close)
                if scale_out.move_to_be and scale_out.new_sl is not None:
                    pos.sl_price = scale_out.new_sl
                    pos.trailing_active = True

            scale_in = pyramid_mgr.check_scale_in(pos, candle)
            if scale_in is not None:
                pos.lots = min(round(pos.lots + scale_in.additional_lots, 4), 0.01)
                pos.tranches_filled = scale_in.tranche_index
                if scale_in.move_to_be and scale_in.new_sl is not None:
                    if pos.direction == 1:
                        pos.sl_price = max(pos.sl_price, scale_in.new_sl)
                    else:
                        pos.sl_price = min(pos.sl_price, scale_in.new_sl)

            exit_result = exit_mgr.check_exit(pos, candle)
            if exit_result is not None:
                exit_price, reason = exit_result
                self._close_position(account, exit_price, dt, reason)
            return

        if account.daily_trades_count >= 1:
            return

        if self.orb_high <= 0 or self.orb_low <= 0:
            return

        range_width = self.orb_high - self.orb_low
        filters_passed = filter_eng.should_trade(
            candle=candle,
            atr=self.current_atr,
            range_width=range_width,
            spread=self.spread_pts,
        )
        if not filters_passed:
            return

        entry_mode = account.profile["dimensions"]["entry_mode"]
        signal = evaluate_omni_entry(
            entry_mode,
            candle,
            self.orb_high,
            self.orb_low,
            self.current_atr,
        )

        if signal is not None:
            direction, ref_price = signal
            self._execute_simulated_entry(account, direction, ref_price, candle, "OMNI_ENTRY")

    def _execute_simulated_entry(
        self,
        account: VirtualAccountState,
        direction: int,
        ref_price: float,
        candle: CandleBar,
        label: str,
    ) -> None:
        """Execute a simulated order enforcing the strict 0.01 micro-lot cap."""
        executed_lots = 0.01

        fill_price = (
            candle.close + (self.spread_pts / 2.0) + self.slippage_pts
            if direction == 1
            else candle.close - (self.spread_pts / 2.0) - self.slippage_pts
        )

        exit_mgr = self.exit_managers[account.profile_id]
        sl, tp = exit_mgr.compute_sl_tp(fill_price, direction)

        account.position = SimulatedPosition(
            direction=direction,
            entry_price=fill_price,
            lots=executed_lots,
            sl_price=sl,
            tp_price=tp,
            highest_price=candle.high,
            lowest_price=candle.low,
            entry_time=candle.timestamp,
            trailing_active=False,
            time_in_trade_minutes=0,
            tranches_filled=1,
            total_planned_lots=executed_lots,
        )
        account.daily_trades_count += 1

        self.logger.info(
            f"[ORDER FILLED] {account.engine_type.upper()} | Profile: {account.profile_id} | "
            f"Side: {'LONG' if direction == 1 else 'SHORT'} | FillPrice: {fill_price:.2f} | "
            f"Lots: {executed_lots:.2f} (CAP: 0.01) | SL: {sl:.2f} | TP: {tp} | Time: {candle.timestamp.isoformat()}"
        )

    def run_replay(
        self,
        candle_data_path: str,
        duration_hours: float = 72.0,
        min_sessions: int = 5,
    ) -> Dict[str, Any]:
        """Run observation replay across high-fidelity continuous market data."""
        self.logger.info(
            f"Starting 72-Hour Observation Replay | Dataset: {candle_data_path} | "
            f"Target Hours: {duration_hours} | Min Sessions: {min_sessions}"
        )

        candles = self._load_candles(candle_data_path)
        if not candles:
            raise ValueError(f"No candles loaded from {candle_data_path}")

        dates = sorted(list({c.timestamp.date() for c in candles}))
        req_days = max(min_sessions, int(math.ceil(duration_hours / 24.0)))
        target_dates = set(dates[-req_days:])
        replay_candles = [c for c in candles if c.timestamp.date() in target_dates]

        start_time = replay_candles[0].timestamp
        end_time = replay_candles[-1].timestamp
        total_time_span = (end_time - start_time).total_seconds() / 3600.0

        for c in replay_candles:
            self.process_candle(c)

        for acct in self.accounts.values():
            if acct.position is not None:
                self._close_position(
                    acct,
                    replay_candles[-1].close,
                    replay_candles[-1].timestamp,
                    "REPLAY_OBSERVATION_COMPLETE",
                )

        results = self._generate_telemetry_and_rankings(
            mode="replay",
            start_time=start_time,
            end_time=end_time,
            hours_covered=total_time_span,
            sessions_count=len(self.evaluated_days),
        )

        return results

    def _load_candles(self, file_path: str) -> List[CandleBar]:
        """Load 1-minute OHLCV candles from CSV format."""
        bars: List[CandleBar] = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("time") or row[0].startswith("Date"):
                    continue
                try:
                    ts_val = row[0].strip()
                    if ts_val.isdigit():
                        ms = int(ts_val)
                        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
                    else:
                        dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))

                    o = float(row[1])
                    h = float(row[2])
                    l = float(row[3])
                    c = float(row[4])
                    v = float(row[5]) if len(row) > 5 else 1.0
                    bars.append(CandleBar(timestamp=dt, open=o, high=h, low=l, close=c, volume=v))
                except Exception:
                    continue
        return bars

    def _generate_telemetry_and_rankings(
        self,
        mode: str,
        start_time: datetime,
        end_time: datetime,
        hours_covered: float,
        sessions_count: int,
    ) -> Dict[str, Any]:
        """Compile profile performance metrics, rank candidates, and export telemetry."""
        profiles_summary: List[Dict[str, Any]] = []

        for p_id, acct in self.accounts.items():
            trade_count = len(acct.trades)
            wins = sum(1 for t in acct.trades if t.pnl > 0)
            losses = sum(1 for t in acct.trades if t.pnl <= 0)
            win_rate = (wins / trade_count) if trade_count > 0 else 0.0

            gross_profit = sum(t.pnl for t in acct.trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in acct.trades if t.pnl < 0))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (9.99 if gross_profit > 0 else 1.0)

            total_pnl = acct.balance - self.initial_equity
            max_dd_pct = acct.max_drawdown / self.initial_equity

            pnl_series = [t.pnl for t in acct.trades]
            if len(pnl_series) > 1:
                mean_pnl = sum(pnl_series) / len(pnl_series)
                variance = sum((x - mean_pnl) ** 2 for x in pnl_series) / (len(pnl_series) - 1)
                std_pnl = math.sqrt(variance) if variance > 0 else 1.0
                sharpe = (mean_pnl / std_pnl) * math.sqrt(252)
            else:
                sharpe = 1.0 if total_pnl >= 0 else 0.0

            score = (
                0.40 * max(-2.0, min(5.0, sharpe))
                + 0.30 * (1.0 - min(1.0, max_dd_pct * 10.0))
                + 0.20 * min(3.0, profit_factor)
                + 0.10 * min(2.0, trade_count / 5.0)
            )

            profiles_summary.append(
                {
                    "profile_id": p_id,
                    "engine": acct.engine_type,
                    "initial_equity": self.initial_equity,
                    "ending_equity": round(acct.balance, 2),
                    "total_pnl": round(total_pnl, 4),
                    "total_trades": trade_count,
                    "winning_trades": wins,
                    "losing_trades": losses,
                    "win_rate": round(win_rate, 4),
                    "profit_factor": round(profit_factor, 4),
                    "max_drawdown": round(acct.max_drawdown, 2),
                    "max_drawdown_pct": round(max_dd_pct, 4),
                    "sharpe_ratio": round(sharpe, 4),
                    "observation_score": round(score, 4),
                    "circuit_breaker_tripped": acct.circuit_breaker_tripped,
                    "ftmo_violations": 1 if acct.circuit_breaker_tripped or max_dd_pct >= 0.08 else 0,
                    "trades": [t.__dict__ for t in acct.trades],
                }
            )

        london_ranked = sorted(
            [p for p in profiles_summary if p["engine"] == "london_reversal"],
            key=lambda x: x["observation_score"],
            reverse=True,
        )
        omni_ranked = sorted(
            [p for p in profiles_summary if p["engine"] == "omni_breakout"],
            key=lambda x: x["observation_score"],
            reverse=True,
        )

        winning_london = london_ranked[0] if london_ranked else None
        winning_omni = omni_ranked[0] if omni_ranked else None

        if winning_london:
            self._export_winning_profile(winning_london["profile_id"], "profiles/london_winner.json")
        if winning_omni:
            self._export_winning_profile(winning_omni["profile_id"], "profiles/omni_winner.json")

        telemetry: Dict[str, Any] = {
            "metadata": {
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": round(hours_covered, 2),
                "sessions_evaluated": sessions_count,
                "minimum_hours_required": 72.0,
                "minimum_sessions_required": 5,
                "passed_duration_constraint": bool(hours_covered >= 72.0 and sessions_count >= 5),
                "max_execution_lot_size": 0.01,
                "spread_pts": self.spread_pts,
                "slippage_pts": self.slippage_pts,
            },
            "winning_profiles": {
                "london_reversal": {
                    "profile_id": winning_london["profile_id"] if winning_london else None,
                    "observation_score": winning_london["observation_score"] if winning_london else 0.0,
                    "total_pnl": winning_london["total_pnl"] if winning_london else 0.0,
                    "max_drawdown_pct": winning_london["max_drawdown_pct"] if winning_london else 0.0,
                    "trades": winning_london["total_trades"] if winning_london else 0,
                },
                "omni_breakout": {
                    "profile_id": winning_omni["profile_id"] if winning_omni else None,
                    "observation_score": winning_omni["observation_score"] if winning_omni else 0.0,
                    "total_pnl": winning_omni["total_pnl"] if winning_omni else 0.0,
                    "max_drawdown_pct": winning_omni["max_drawdown_pct"] if winning_omni else 0.0,
                    "trades": winning_omni["total_trades"] if winning_omni else 0,
                },
            },
            "rankings": {
                "london_reversal": [
                    {k: v for k, v in p.items() if k != "trades"} for p in london_ranked
                ],
                "omni_breakout": [
                    {k: v for k, v in p.items() if k != "trades"} for p in omni_ranked
                ],
            },
            "profiles_detail": profiles_summary,
        }

        with open(self.telemetry_file, "w", encoding="utf-8") as tf:
            json.dump(telemetry, tf, indent=2)

        self.logger.info(
            f"Observation Telemetry exported to {self.telemetry_file}. "
            f"London Winner: {winning_london['profile_id'] if winning_london else 'None'} | "
            f"Omni Winner: {winning_omni['profile_id'] if winning_omni else 'None'}"
        )

        return telemetry

    def _export_winning_profile(self, profile_id: str, dest_path: str) -> None:
        """Export the validated winning JSON profile to specified destination."""
        acct = self.accounts.get(profile_id)
        if not acct:
            return

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as df:
            json.dump(acct.profile, df, indent=2)

        self.logger.info(f"Exported winning profile {profile_id} to {dest_path}")


def main() -> None:
    """CLI entrypoint for paper trading harness."""
    parser = argparse.ArgumentParser(description="Observation-Only Paper Trading Harness")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["replay", "stream"],
        default="replay",
        help="Observation mode: 'replay' on historical feeds or 'stream' via live MetaApi",
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/raw/US100.cash_m1_2024-01-01_2026-09-09.csv",
        help="Path to 1-minute candle CSV for replay",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=72.0,
        help="Minimum continuous hours of observation to evaluate",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=5,
        help="Minimum number of trading sessions required",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="paper_trades.log",
        help="Output log file path",
    )
    parser.add_argument(
        "--telemetry",
        type=str,
        default="paper_trade_telemetry.json",
        help="Output telemetry JSON file path",
    )
    args = parser.parse_args()

    harness = PaperTradingHarness(
        log_file=args.log,
        telemetry_file=args.telemetry,
    )

    if args.mode == "replay":
        results = harness.run_replay(
            candle_data_path=args.data,
            duration_hours=args.hours,
            min_sessions=args.sessions,
        )
        print("Paper trading observation completed successfully.")
        print(f"Sessions evaluated: {results['metadata']['sessions_evaluated']}")
        print(f"Hours covered: {results['metadata']['duration_hours']}")
        print(f"London winner: {results['winning_profiles']['london_reversal']['profile_id']}")
        print(f"Omni winner: {results['winning_profiles']['omni_breakout']['profile_id']}")


if __name__ == "__main__":
    main()
