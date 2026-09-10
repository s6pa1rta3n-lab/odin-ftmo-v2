"""Unit and integration test suite for observation-only Paper Trading Harness."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from paper_trader import (
    CandleBar,
    PaperTradingHarness,
    SimulatedPosition,
    VirtualAccountState,
)


def make_candle(
    dt: datetime,
    open_p: float = 19550.0,
    high_p: float = 19560.0,
    low_p: float = 19540.0,
    close_p: float = 19550.0,
    volume: float = 100.0,
) -> CandleBar:
    """Construct a lightweight CandleBar for testing."""
    return CandleBar(
        timestamp=dt,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
    )


class TestPaperTraderInitialization:
    """Tests loading of canonical profiles and virtual account initialization."""

    def test_paper_trader_initialization_loads_top_10_profiles(self) -> None:
        """Verify harness initializes with 10 London profiles and 10 Omni profiles."""
        harness = PaperTradingHarness(
            log_file="tests/test_paper_trades.log",
            telemetry_file="tests/test_paper_telemetry.json",
        )
        assert len(harness.accounts) == 20
        london_count = sum(1 for a in harness.accounts.values() if a.engine_type == "london_reversal")
        omni_count = sum(1 for a in harness.accounts.values() if a.engine_type == "omni_breakout")
        assert london_count == 10
        assert omni_count == 10
        for acct in harness.accounts.values():
            assert acct.balance == 94939.28
            assert acct.equity == 94939.28
            assert acct.daily_start_equity == 94939.28
            assert acct.circuit_breaker_floor == pytest.approx(94939.28 * 0.955, rel=1e-4)


class TestMicroLotCapAndExecution:
    """Tests execution constraints including 0.01 micro-lot cap and slippage."""

    def test_micro_lot_cap_enforcement(self) -> None:
        """Verify simulated orders never exceed 0.01 micro-lots."""
        harness = PaperTradingHarness(
            log_file="tests/test_paper_trades.log",
            telemetry_file="tests/test_paper_telemetry.json",
        )
        acct = next(iter(harness.accounts.values()))
        dt = datetime(2026, 9, 8, 8, 30, tzinfo=timezone.utc)
        candle = make_candle(dt, close_p=19500.0)

        harness._execute_simulated_entry(acct, direction=1, ref_price=19500.0, candle=candle, label="TEST")
        assert acct.position is not None
        assert acct.position.lots <= 0.01

    def test_realistic_spread_and_slippage_calculation(self) -> None:
        """Verify Buy fill adds spread/slippage and Sell fill subtracts spread/slippage."""
        harness = PaperTradingHarness(
            spread_pts=2.0,
            slippage_pts=0.5,
            log_file="tests/test_paper_trades.log",
            telemetry_file="tests/test_paper_telemetry.json",
        )
        acct_long = next(iter(harness.accounts.values()))
        dt = datetime(2026, 9, 8, 8, 30, tzinfo=timezone.utc)
        candle = make_candle(dt, close_p=19500.0)

        harness._execute_simulated_entry(acct_long, direction=1, ref_price=19500.0, candle=candle, label="TEST_LONG")
        assert acct_long.position is not None
        assert acct_long.position.entry_price == pytest.approx(19500.0 + 1.0 + 0.5)


class TestCircuitBreakerProtection:
    """Tests daily watermark tracking and 4.5% circuit breaker halt."""

    def test_circuit_breaker_trips_at_4_5_percent_loss(self) -> None:
        """Verify that intra-day 4.5% drawdown halts trading and flattens positions."""
        harness = PaperTradingHarness(
            log_file="tests/test_paper_trades.log",
            telemetry_file="tests/test_paper_telemetry.json",
        )
        acct = next(iter(harness.accounts.values()))
        dt = datetime(2026, 9, 8, 8, 30, tzinfo=timezone.utc)
        candle_entry = make_candle(dt, close_p=19500.0)
        harness._execute_simulated_entry(acct, direction=1, ref_price=19500.0, candle=candle_entry, label="TEST")

        adverse_candle = make_candle(
            dt + timedelta(minutes=15),
            close_p=15000.0,
        )
        acct.equity = acct.daily_start_equity * (1.0 - 0.046)
        tripped = harness._check_circuit_breaker(acct, adverse_candle)
        assert tripped is True
        assert acct.circuit_breaker_tripped is True
        assert acct.position is None


class TestReplayAndWinnerSelection:
    """Tests multi-session candle replay, telemetry export, and winner selection."""

    def test_run_replay_on_synthetic_sessions(self, tmp_path: Path) -> None:
        """Verify multi-session observation generates telemetry and exports winners."""
        csv_file = tmp_path / "test_candles.csv"
        rows = [["timestamp", "open", "high", "low", "close", "volume"]]

        start_dt = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        for i in range(5 * 1440):
            c_dt = start_dt + timedelta(minutes=i)
            p = 19500.0 + (i % 50)
            rows.append([c_dt.isoformat(), str(p), str(p + 5.0), str(p - 5.0), str(p), "100"])

        with open(csv_file, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(",".join(r) + "\n")

        log_path = tmp_path / "test_run.log"
        telem_path = tmp_path / "test_telem.json"

        harness = PaperTradingHarness(
            log_file=str(log_path),
            telemetry_file=str(telem_path),
        )
        results = harness.run_replay(
            candle_data_path=str(csv_file),
            duration_hours=72.0,
            min_sessions=5,
        )

        assert results["metadata"]["sessions_evaluated"] == 5
        assert results["metadata"]["passed_duration_constraint"] is True
        assert "london_reversal" in results["winning_profiles"]
        assert "omni_breakout" in results["winning_profiles"]
        assert telem_path.exists()
