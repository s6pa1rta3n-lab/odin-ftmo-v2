"""Shared fixtures and synthetic data generators for E2E tests.

Provides deterministic data sources, simulated market sessions, and FTMO
account parameters for all test tiers.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Generator, List, Optional
import pytest

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backtester.engine import (
    BacktestProfile,
    Candle,
    EngineType,
    EntryMode,
    ExitModel,
    OmniEntryMode,
    PyramidModel,
    RiskModel,
)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def ftmo_asset_specs(project_root: Path) -> dict:
    """Load and return the authoritative FTMO asset specifications."""
    specs_path = project_root / "data" / "ftmo_asset_specs.json"
    with open(specs_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ftmo_account_state() -> dict:
    """Provide current FTMO verification account parameters.

    Based on the exact account state specified in ORIGINAL_REQUEST.md.
    """
    return {
        "starting_balance": 100000.0,
        "current_equity": 94939.28,
        "total_loss_floor": 90000.0,
        "emergency_floor": 90500.0,
        "remaining_margin_to_floor": 4939.28,
        "profit_target": 110000.0,
        "daily_loss_limit_pct": 0.05,
        "daily_circuit_breaker_pct": 0.045,
    }


@pytest.fixture
def candle_factory() -> Callable[..., Candle]:
    """Factory creating individual Candle instances."""
    def _create(
        timestamp: datetime,
        open_p: float = 19500.0,
        high_p: float = 19510.0,
        low_p: float = 19490.0,
        close_p: float = 19505.0,
        volume: float = 100.0,
    ) -> Candle:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return Candle(
            timestamp=timestamp,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
        )
    return _create


@pytest.fixture
def synthetic_asian_candles(candle_factory: Callable[..., Candle]) -> Callable[[datetime, float, float], List[Candle]]:
    """Generate 420 1-minute candles representing the Asian session (00:00 - 07:00 UTC)."""
    def _generator(session_date: datetime, asian_high: float = 19600.0, asian_low: float = 19500.0) -> List[Candle]:
        candles = []
        base_time = session_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        mid_price = (asian_high + asian_low) / 2.0
        amplitude = (asian_high - asian_low) / 2.0

        for minute in range(420):
            ts = base_time + timedelta(minutes=minute)
            phase = (minute / 420.0) * 6.283185307
            center = mid_price + amplitude * 0.8 * (1.0 if (minute % 60 < 30) else -0.8)
            candle_high = min(center + 5.0, asian_high)
            candle_low = max(center - 5.0, asian_low)
            candle_open = (candle_high + candle_low) / 2.0
            candle_close = candle_open + 1.0

            if minute == 100:
                candle_high = asian_high
            if minute == 250:
                candle_low = asian_low

            candles.append(candle_factory(
                timestamp=ts,
                open_p=candle_open,
                high_p=candle_high,
                low_p=candle_low,
                close_p=candle_close,
                volume=50.0 + (minute % 20),
            ))
        return candles
    return _generator


@pytest.fixture
def synthetic_london_candles(candle_factory: Callable[..., Candle]) -> Callable[..., List[Candle]]:
    """Generate 360 1-minute candles representing the London session (07:00 - 13:00 UTC)."""
    def _generator(
        session_date: datetime,
        asian_high: float = 19600.0,
        asian_low: float = 19500.0,
        scenario: str = "sweep_high_reversal",
    ) -> List[Candle]:
        candles = []
        base_time = session_date.replace(hour=7, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        for minute in range(360):
            ts = base_time + timedelta(minutes=minute)
            if scenario == "sweep_high_reversal":
                if minute < 30:
                    open_p = asian_high - 10.0 + (minute * 0.5)
                    high_p = open_p + 3.0
                    low_p = open_p - 2.0
                    close_p = open_p + 1.0
                elif minute == 30:
                    open_p = asian_high + 2.0
                    high_p = asian_high + 12.0
                    low_p = asian_high - 1.0
                    close_p = asian_high - 2.0
                else:
                    decay = (minute - 30) * 0.4
                    open_p = max(asian_high - 5.0 - decay, asian_low + 10.0)
                    high_p = open_p + 2.0
                    low_p = open_p - 4.0
                    close_p = open_p - 2.0
            elif scenario == "sweep_low_reversal":
                if minute < 30:
                    open_p = asian_low + 10.0 - (minute * 0.5)
                    high_p = open_p + 2.0
                    low_p = open_p - 3.0
                    close_p = open_p - 1.0
                elif minute == 30:
                    open_p = asian_low - 2.0
                    high_p = asian_low + 1.0
                    low_p = asian_low - 12.0
                    close_p = asian_low + 2.0
                else:
                    rally = (minute - 30) * 0.4
                    open_p = min(asian_low + 5.0 + rally, asian_high - 10.0)
                    high_p = open_p + 4.0
                    low_p = open_p - 2.0
                    close_p = open_p + 2.0
            elif scenario == "no_sweep":
                mid_p = (asian_high + asian_low) / 2.0
                open_p = mid_p + ((minute % 10) - 5)
                high_p = open_p + 3.0
                low_p = open_p - 3.0
                close_p = open_p + 1.0
            else:
                open_p = (asian_high + asian_low) / 2.0
                high_p = open_p + 5.0
                low_p = open_p - 5.0
                close_p = open_p

            candles.append(candle_factory(
                timestamp=ts,
                open_p=open_p,
                high_p=high_p,
                low_p=low_p,
                close_p=close_p,
                volume=120.0,
            ))
        return candles
    return _generator


@pytest.fixture
def synthetic_us_orb_candles(candle_factory: Callable[..., Candle]) -> Callable[..., List[Candle]]:
    """Generate 30 1-minute candles representing the US Open Range (14:00 - 14:30 UTC)."""
    def _generator(session_date: datetime, orb_high: float = 19700.0, orb_low: float = 19620.0) -> List[Candle]:
        candles = []
        base_time = session_date.replace(hour=14, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        mid_p = (orb_high + orb_low) / 2.0

        for minute in range(30):
            ts = base_time + timedelta(minutes=minute)
            open_p = mid_p
            high_p = mid_p + 10.0
            low_p = mid_p - 10.0
            close_p = mid_p + 2.0

            if minute == 10:
                high_p = orb_high
            if minute == 20:
                low_p = orb_low

            candles.append(candle_factory(
                timestamp=ts,
                open_p=open_p,
                high_p=high_p,
                low_p=low_p,
                close_p=close_p,
                volume=250.0,
            ))
        return candles
    return _generator


@pytest.fixture
def synthetic_us_session_candles(candle_factory: Callable[..., Candle]) -> Callable[..., List[Candle]]:
    """Generate 330 1-minute candles representing the US trading session (14:30 - 20:00 UTC)."""
    def _generator(
        session_date: datetime,
        orb_high: float = 19700.0,
        orb_low: float = 19620.0,
        scenario: str = "bullish_breakout",
    ) -> List[Candle]:
        candles = []
        base_time = session_date.replace(hour=14, minute=30, second=0, microsecond=0, tzinfo=timezone.utc)

        for minute in range(330):
            ts = base_time + timedelta(minutes=minute)
            if scenario == "bullish_breakout":
                if minute < 10:
                    open_p = orb_high - 5.0 + minute
                    high_p = open_p + 3.0
                    low_p = open_p - 2.0
                    close_p = open_p + 1.0
                elif minute == 10:
                    open_p = orb_high + 2.0
                    high_p = orb_high + 25.0
                    low_p = orb_high
                    close_p = orb_high + 20.0
                else:
                    continuation = (minute - 10) * 0.3
                    open_p = orb_high + 20.0 + continuation
                    high_p = open_p + 5.0
                    low_p = open_p - 3.0
                    close_p = open_p + 2.0
            elif scenario == "bearish_breakout":
                if minute < 10:
                    open_p = orb_low + 5.0 - minute
                    high_p = open_p + 2.0
                    low_p = open_p - 3.0
                    close_p = open_p - 1.0
                elif minute == 10:
                    open_p = orb_low - 2.0
                    high_p = orb_low
                    low_p = orb_low - 25.0
                    close_p = orb_low - 20.0
                else:
                    continuation = (minute - 10) * 0.3
                    open_p = orb_low - 20.0 - continuation
                    high_p = open_p + 3.0
                    low_p = open_p - 5.0
                    close_p = open_p - 2.0
            else:
                mid_p = (orb_high + orb_low) / 2.0
                open_p = mid_p
                high_p = mid_p + 10.0
                low_p = mid_p - 10.0
                close_p = mid_p

            candles.append(candle_factory(
                timestamp=ts,
                open_p=open_p,
                high_p=high_p,
                low_p=low_p,
                close_p=close_p,
                volume=300.0,
            ))
        return candles
    return _generator


@pytest.fixture
def default_london_profile() -> BacktestProfile:
    """Return a canonical valid London Reversal backtest profile."""
    return BacktestProfile(
        engine=EngineType.LONDON_REVERSAL,
        risk_model=RiskModel.CONSERVATIVE_RAMP,
        entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
        pyramid_model=PyramidModel.NO_PYRAMID,
        exit_model=ExitModel.FIXED_SL_TRAIL,
        filters=["spread_gate"],
        instrument="US100.cash",
    )


@pytest.fixture
def default_omni_profile() -> BacktestProfile:
    """Return a canonical valid Omni Breakout backtest profile."""
    return BacktestProfile(
        engine=EngineType.OMNI_BREAKOUT,
        risk_model=RiskModel.CONSERVATIVE_RAMP,
        entry_mode=OmniEntryMode.CLOSE_CONFIRMATION.value,
        pyramid_model=PyramidModel.NO_PYRAMID,
        exit_model=ExitModel.FIXED_SL_TRAIL,
        filters=["spread_gate"],
        instrument="US100.cash",
    )


@pytest.fixture
def temp_candle_csv(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary CSV file with 60 valid 1-minute candles."""
    csv_file = tmp_path / "US100cash_m1_sample.csv"
    base_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    lines = ["timestamp,open,high,low,close,volume\n"]

    for i in range(60):
        ts = base_time + timedelta(minutes=i)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        open_p = 19500.0 + i
        high_p = open_p + 4.0
        low_p = open_p - 3.0
        close_p = open_p + 1.0
        vol = 100.0 + i
        lines.append(f"{ts_str},{open_p},{high_p},{low_p},{close_p},{vol}\n")

    with open(csv_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    yield csv_file
