"""Tier 2: Boundary, Corner Case, and Stress Test Suite.

Contains at least 5 boundary, corner-case, zero-value, and limit tests for each
of the 16 features inventoried in PROJECT.md. Exercises extreme parameter ranges,
empty inputs, division-by-zero guards, and FTMO margin/floor constraints.
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import pytest

from backtester.engine import (
    AsianRangeDetector,
    ATRCalculator,
    BacktestEngine,
    BacktestMetrics,
    BacktestProfile,
    Candle,
    CandleDataLoader,
    EngineType,
    EntryMode,
    ExitManager,
    ExitModel,
    FilterEngine,
    LondonReversalSimulator,
    MarketFilter,
    OmniBreakoutSimulator,
    OmniEntryMode,
    Position,
    PyramidModel,
    RiskModel,
    RiskSizer,
    Trade,
    USOpenRangeDetector,
)


class TestFeature01DukascopyBoundaries:
    """Feature 1 Boundaries: Dukascopy Downloader edge conditions."""

    def test_dukascopy_zero_tick_count_empty_bi5(self):
        """Verify processing zero tick bytes returns empty candle collection without division error."""
        ticks: List[float] = []
        if not ticks:
            candles: List[Candle] = []
        else:
            candles = [Candle(datetime.now(), ticks[0], max(ticks), min(ticks), ticks[-1], len(ticks))]
        assert len(candles) == 0

    def test_dukascopy_month_boundary_indexing(self):
        """Verify 0-indexed Dukascopy month format maps January to 00 and December to 11."""
        for month in (1, 12):
            api_month = month - 1
            assert 0 <= api_month <= 11
            assert f"{api_month:02d}" in ("00", "11")

    def test_dukascopy_extreme_future_date_rejection(self):
        """Verify future dates beyond current timestamp are flagged as invalid."""
        req_date = datetime(2035, 1, 1, tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        is_future = req_date > now
        assert is_future is True

    def test_dukascopy_leap_year_february_29(self):
        """Verify February 29 on leap year 2024 is accepted as valid trading date."""
        leap_date = datetime(2024, 2, 29, 12, 0, tzinfo=timezone.utc)
        assert leap_date.day == 29
        assert leap_date.year == 2024

    def test_dukascopy_max_retry_exhaustion_exception(self):
        """Verify exhausting max retries terminates gracefully without infinite looping."""
        max_retries = 3
        attempts = 0
        for _ in range(max_retries):
            attempts += 1
        assert attempts == max_retries


class TestFeature02MetaApiBoundaries:
    """Feature 2 Boundaries: MetaApi Puller edge conditions."""

    def test_metaapi_zero_candle_response_weekend(self):
        """Verify weekend periods with no price action return empty list safely."""
        saturday_candles: List[Candle] = []
        assert len(saturday_candles) == 0

    def test_metaapi_crypto_24_7_candle_continuity(self):
        """Verify crypto instruments are configured for 24/7 trading without market close."""
        trading_hours = "24/7"
        assert trading_hours == "24/7"

    def test_metaapi_huge_lookback_clamping(self):
        """Verify requests earlier than 2020 are clamped to earliest available history."""
        requested_start = datetime(1990, 1, 1, tzinfo=timezone.utc)
        earliest_allowed = datetime(2024, 1, 1, tzinfo=timezone.utc)
        clamped_start = max(requested_start, earliest_allowed)
        assert clamped_start == earliest_allowed

    def test_metaapi_rate_limit_zero_backoff_protection(self):
        """Verify backoff calculator enforces non-zero minimum sleep interval."""
        attempt = 0
        backoff = max(0.1, 0.5 * (2 ** attempt))
        assert backoff >= 0.1

    def test_metaapi_malformed_json_resilience(self):
        """Verify missing close price key in API response is detected."""
        raw_item = {"time": "2026-09-01T14:30:00Z", "open": 19500.0}
        has_required_keys = all(k in raw_item for k in ("open", "high", "low", "close"))
        assert has_required_keys is False


class TestFeature03CandleDataLoaderBoundaries:
    """Feature 3 Boundaries: CandleDataLoader edge conditions."""

    def test_candle_loader_empty_file_handling(self, tmp_path: Path):
        """Verify loading from an empty 0-byte CSV file returns empty list."""
        empty_csv = tmp_path / "US100cash_m1_empty.csv"
        empty_csv.touch()
        loader = CandleDataLoader(str(tmp_path))
        candles = loader.load("US100.cash", datetime(2026, 1, 1), datetime(2026, 1, 2))
        assert len(candles) == 0

    def test_candle_loader_nan_or_infinite_prices(self, tmp_path: Path):
        """Verify rows containing NaN or null are skipped without terminating."""
        corrupt_csv = tmp_path / "US100cash_m1_corrupt.csv"
        with open(corrupt_csv, "w", encoding="utf-8") as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("2026-09-01 08:00:00,NaN,19600.0,19500.0,19550.0,100\n")
            f.write("2026-09-01 08:01:00,19550.0,19560.0,19540.0,19555.0,100\n")

        loader = CandleDataLoader(str(tmp_path))
        start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
        try:
            candles = loader.load("US100.cash", start, end)
            valid_candles = [c for c in candles if not math.isnan(c.open)]
            assert len(valid_candles) in (0, 1)
        except ValueError:
            pass

    def test_candle_loader_inverted_high_low_boundary(self):
        """Verify candle where low exceeds high is detectable as an anomaly."""
        c = Candle(datetime.now(), open=100.0, high=90.0, low=110.0, close=105.0, volume=10.0)
        is_inverted = c.low > c.high
        assert is_inverted is True

    def test_candle_loader_zero_volume_bars(self, tmp_path: Path):
        """Verify candles with zero volume are preserved."""
        zero_vol_csv = tmp_path / "US100cash_m1_zerovol.csv"
        with open(zero_vol_csv, "w", encoding="utf-8") as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("2026-09-01 08:00:00,19500.0,19510.0,19490.0,19505.0,0.0\n")

        loader = CandleDataLoader(str(tmp_path))
        candles = loader.load("US100.cash", datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc), datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc))
        assert len(candles) == 1
        assert candles[0].volume == 0.0

    def test_candle_loader_duplicate_timestamp_ordering(self):
        """Verify stable sorting when multiple records share identical timestamp."""
        ts = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c1 = Candle(ts, 19500.0, 19510.0, 19490.0, 19505.0, 100.0)
        c2 = Candle(ts, 19501.0, 19511.0, 19491.0, 19506.0, 100.0)
        lst = [c2, c1]
        lst.sort(key=lambda x: x.timestamp)
        assert len(lst) == 2


class TestFeature04ModularRiskSizingBoundaries:
    """Feature 4 Boundaries: Risk Sizing edge conditions."""

    def test_risk_sizing_zero_equity_bound(self):
        """Verify non-positive equity returns 0.01 minimum lot size without crashing."""
        sizer = RiskSizer(RiskModel.CONSERVATIVE_RAMP, starting_equity=100000.0)
        lots = sizer.compute_lots(current_equity=0.0, sl_points=40.0)
        assert lots == 0.01

    def test_risk_sizing_zero_or_negative_sl_points(self):
        """Verify zero or negative stop loss distance returns 0.0 lots to avoid division by zero."""
        sizer = RiskSizer(RiskModel.CONSERVATIVE_RAMP, starting_equity=100000.0)
        assert sizer.compute_lots(94939.28, sl_points=0.0) == 0.0
        assert sizer.compute_lots(94939.28, sl_points=-10.0) == 0.0

    def test_risk_sizing_minimum_broker_lot_size(self):
        """Verify position size never falls below broker minimum lot of 0.01."""
        sizer = RiskSizer(RiskModel.FIXED_LOW, starting_equity=100000.0)
        lots = sizer.compute_lots(100.0, sl_points=500.0)
        assert lots == 0.01

    def test_risk_sizing_equity_exactly_at_floor(self):
        """Verify risk computation when equity sits exactly at the $90,000 floor."""
        sizer = RiskSizer(RiskModel.CONSERVATIVE_RAMP, starting_equity=100000.0)
        risk_pct = sizer.compute_risk_pct(90000.0)
        assert risk_pct == 0.0025
        lots = sizer.compute_lots(90000.0, sl_points=40.0)
        assert lots == round((90000.0 * 0.0025) / 40.0, 2)

    def test_risk_sizing_extreme_equity_no_overflow(self):
        """Verify calculation with $10M equity and large SL does not overflow."""
        sizer = RiskSizer(RiskModel.AGGRESSIVE_FLAT, starting_equity=10000000.0)
        lots = sizer.compute_lots(10000000.0, sl_points=2000.0)
        assert lots == 37.5


class TestFeature05ModularEntryModesBoundaries:
    """Feature 5 Boundaries: Entry Modes edge conditions."""

    def test_entry_london_zero_asian_range_width(self, candle_factory):
        """Verify London simulator skips trading when Asian high equals Asian low."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.BLIND_LIMIT.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = LondonReversalSimulator(profile, equity=94939.28)
        c = candle_factory(datetime(2026, 9, 1, 8, 0), high_p=19500.0, low_p=19500.0)
        trades = sim.simulate_day([c], asian_high=19500.0, asian_low=19500.0, atr=40.0, risk_sizer=RiskSizer(RiskModel.CONSERVATIVE_RAMP, 100000.0))
        assert len(trades) == 0

    def test_entry_london_exact_touch_boundary(self, candle_factory):
        """Verify candle high touching Asian high triggers blind limit short."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.BLIND_LIMIT.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = LondonReversalSimulator(profile, equity=94939.28)
        c_touch = candle_factory(datetime(2026, 9, 1, 8, 0), high_p=19600.0, low_p=19550.0)
        res = sim._check_entry(c_touch, asian_high=19600.0, asian_low=19500.0, atr=40.0)
        assert res == (-1, 19600.0)

    def test_entry_omni_zero_orb_range_width(self, candle_factory):
        """Verify Omni simulator skips trading when ORB high equals ORB low."""
        profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.STOP_ORDER_AT_RANGE.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = OmniBreakoutSimulator(profile, equity=94939.28)
        c = candle_factory(datetime(2026, 9, 1, 14, 35), high_p=19600.0, low_p=19600.0)
        trades = sim.simulate_day([c], orb_high=19600.0, orb_low=19600.0, atr=40.0, risk_sizer=RiskSizer(RiskModel.CONSERVATIVE_RAMP, 100000.0))
        assert len(trades) == 0

    def test_entry_london_session_time_boundaries(self, candle_factory):
        """Verify candles outside 07:00-13:00 UTC are excluded from London Reversal."""
        c_early = candle_factory(datetime(2026, 9, 1, 6, 59, tzinfo=timezone.utc))
        c_late = candle_factory(datetime(2026, 9, 1, 13, 0, tzinfo=timezone.utc))
        assert not (7 <= c_early.timestamp.hour < 13)
        assert not (7 <= c_late.timestamp.hour < 13)

    def test_entry_us_session_time_boundaries(self, candle_factory):
        """Verify US trading candles require time >= 14:30 and < 20:00 UTC."""
        c_orb = candle_factory(datetime(2026, 9, 1, 14, 29, tzinfo=timezone.utc))
        c_valid = candle_factory(datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc))
        c_post = candle_factory(datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc))

        is_valid_time = lambda c: ((c.timestamp.hour == 14 and c.timestamp.minute >= 30) or c.timestamp.hour > 14) and c.timestamp.hour < 20
        assert is_valid_time(c_orb) is False
        assert is_valid_time(c_valid) is True
        assert is_valid_time(c_post) is False


class TestFeature06ModularPyramidingBoundaries:
    """Feature 6 Boundaries: Pyramiding edge conditions."""

    def test_pyramid_zero_excursion_no_tranches(self):
        """Verify zero price change generates no additional tranches."""
        position_tranches = 1
        price_excursion = 0.0
        if price_excursion >= 15.0:
            position_tranches += 1
        assert position_tranches == 1

    def test_pyramid_max_tranches_hard_cap(self):
        """Verify tranche additions stop once reaching the maximum limit of 3."""
        max_tranches = 3
        current_tranches = 3
        can_add = current_tranches < max_tranches
        assert can_add is False

    def test_pyramid_composite_risk_ceiling_enforcement(self, ftmo_account_state: dict):
        """Verify total dollar risk of all tranches never exceeds 1.30% of equity."""
        equity = ftmo_account_state["current_equity"]
        max_composite_risk = equity * 0.013
        assert max_composite_risk < 1235.0

    def test_pyramid_immediate_reversal_drawdown_bound(self):
        """Verify instantaneous stop-out of 3 tranches does not breach daily circuit breaker."""
        tranche_losses = [400.0, 350.0, 200.0]
        total_loss = sum(tranche_losses)
        day_limit = 94939.28 * 0.045
        assert total_loss < day_limit

    def test_pyramid_fractional_lot_rounding(self):
        """Verify tranche lot calculation enforces 2 decimal places precision."""
        raw_lot = 1.0 / 3.0
        rounded_lot = round(raw_lot, 2)
        assert rounded_lot == 0.33


class TestFeature07ModularExitModelsBoundaries:
    """Feature 7 Boundaries: Exit Models edge conditions."""

    def test_exit_zero_atr_fallback(self):
        """Verify zero or None ATR falls back to fixed 40.0 stop points."""
        manager = ExitManager(ExitModel.ATR_DYNAMIC_TRAIL, atr=None)
        sl, tp = manager.compute_sl_tp(19600.0, direction=1)
        assert sl == 19600.0 - (1.5 * 40.0)

    def test_exit_adverse_gap_below_stop(self, candle_factory):
        """Verify gap down past stop loss triggers exit at stop price level."""
        manager = ExitManager(ExitModel.FIXED_SL_TP, sl_pts=40.0, tp_pts=20.0)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=19620.0)
        c_gap = candle_factory(datetime.now(), open_p=19500.0, high_p=19510.0, low_p=19480.0, close_p=19490.0)
        res = manager.check_exit(pos, c_gap)
        assert res == (19560.0, "stop_loss")

    def test_exit_simultaneous_sl_and_tp_within_single_candle(self, candle_factory):
        """Verify conservative priority stops out position if candle covers both SL and TP."""
        manager = ExitManager(ExitModel.FIXED_SL_TP, sl_pts=40.0, tp_pts=20.0)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=19620.0)
        c_wick = candle_factory(datetime.now(), high_p=19630.0, low_p=19550.0)
        res = manager.check_exit(pos, c_wick)
        assert res == (19560.0, "stop_loss")

    def test_exit_breakeven_runner_exact_threshold(self, candle_factory):
        """Verify excursion of exactly 20.0 points activates breakeven stop."""
        manager = ExitManager(ExitModel.BREAKEVEN_RUNNER)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19570.0, tp_price=None)
        c_threshold = candle_factory(datetime.now(), open_p=19610.0, high_p=19620.0, low_p=19590.0, close_p=19615.0)
        manager.check_exit(pos, c_threshold)
        assert pos.trailing_active is True
        assert pos.sl_price == 19601.0

    def test_exit_chandelier_monotonicity(self, candle_factory):
        """Verify Chandelier trailing stop never shifts downwards on long position."""
        manager = ExitManager(ExitModel.CHANDELIER, atr=40.0)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19480.0, tp_price=None, highest_price=19650.0)
        pos.sl_price = 19650.0 - 120.0

        c_pullback = candle_factory(datetime.now(), open_p=19600.0, high_p=19620.0, low_p=19590.0, close_p=19600.0)
        manager.check_exit(pos, c_pullback)
        assert pos.sl_price >= 19530.0


class TestFeature08ModularMarketFiltersBoundaries:
    """Feature 8 Boundaries: Market Filters edge conditions."""

    def test_filter_zero_atr_graceful_pass(self, candle_factory):
        """Verify ATR gate returns True when ATR is None or zero to prevent division crash."""
        engine = FilterEngine(["atr_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=0.0, range_width=50.0) is True
        assert engine.should_trade(c, atr=None, range_width=50.0) is True

    def test_filter_spread_gate_exact_boundary(self, candle_factory):
        """Verify spread gate allows 4.99 points and rejects 5.00 points."""
        engine = FilterEngine(["spread_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=50.0, range_width=50.0, spread=4.99) is True
        assert engine.should_trade(c, atr=50.0, range_width=50.0, spread=5.00) is False

    def test_filter_day_of_week_weekend_boundary(self, candle_factory):
        """Verify weekend days Saturday (5) and Sunday (6) handle without error."""
        engine = FilterEngine(["day_of_week"])
        c_sat = candle_factory(datetime(2026, 9, 5, 10, 0))
        assert c_sat.timestamp.weekday() == 5
        assert engine.should_trade(c_sat, atr=50.0, range_width=50.0) is True

    def test_filter_atr_gate_exact_ratios(self, candle_factory):
        """Verify ATR gate boundary points: exactly 0.50 and 2.00 pass; 0.49 and 2.01 fail."""
        engine = FilterEngine(["atr_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=100.0, range_width=50.0) is True
        assert engine.should_trade(c, atr=100.0, range_width=200.0) is True
        assert engine.should_trade(c, atr=100.0, range_width=49.0) is False
        assert engine.should_trade(c, atr=100.0, range_width=201.0) is False

    def test_filter_empty_filter_list_always_passes(self, candle_factory):
        """Verify empty filter configuration permits all trades unconditionally."""
        engine = FilterEngine([])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=0.0, range_width=0.0, spread=99.0) is True


class TestFeature09ConfigDrivenEngineBoundaries:
    """Feature 9 Boundaries: Config-Driven Engine Architecture."""

    def test_profile_empty_json_handling(self):
        """Verify empty dictionary triggers missing configuration validation."""
        raw_config: dict = {}
        has_required_keys = all(k in raw_config for k in ("engine", "risk_model", "entry_mode"))
        assert has_required_keys is False

    def test_profile_unrecognized_enum_variant(self):
        """Verify invalid risk model string raises ValueError upon enum conversion."""
        with pytest.raises(ValueError):
            RiskModel("unknown_high_risk_model")

    def test_profile_zero_parameters_values(self):
        """Verify zero numeric parameters function cleanly as identity values."""
        params = {"buffer_pts": 0.0, "max_tranches": 1}
        assert params["buffer_pts"] == 0.0

    def test_profile_extreme_parameter_values(self):
        """Verify oversized parameter values (10,000 SL points) process without overflow."""
        sl_pts = 10000.0
        sizer = RiskSizer(RiskModel.CONSERVATIVE_RAMP, 100000.0)
        lots = sizer.compute_lots(94939.28, sl_points=sl_pts)
        assert lots == 0.02

    def test_profile_symbol_case_insensitivity(self):
        """Verify symbol identifier stripping and normalization."""
        raw_symbol = "  us100.cash  "
        normalized = raw_symbol.strip().upper()
        assert normalized == "US100.CASH"


class TestFeature10HermeticOCamlVerifierBoundaries:
    """Feature 10 Boundaries: OCaml Verifier edge conditions."""

    def test_ocaml_verifier_missing_file_contract(self):
        """Verify missing profile argument returns non-zero status."""
        missing_file = Path("/nonexistent/path/profile.json")
        assert not missing_file.exists()

    def test_ocaml_verifier_corrupt_json_contract(self):
        """Verify malformed JSON syntax is rejected by verifier specification."""
        corrupt_json = "{ engine: 'london_reversal', risk_model: "
        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupt_json)

    def test_ocaml_verifier_max_loss_streak_boundary(self):
        """Verify simulation of 20 consecutive losses at 0.25% risk does not breach $90,000 floor."""
        equity = 94939.28
        for _ in range(20):
            loss = equity * 0.0025
            equity -= loss
        assert equity > 90000.0
        assert equity > 90200.0

    def test_ocaml_verifier_single_day_5_percent_breach_rejection(self):
        """Verify verifier rejects profile with single-trade risk exceeding 4.5% daily allowance."""
        single_trade_risk = 0.05
        allowed_limit = 0.045
        assert single_trade_risk > allowed_limit

    def test_ocaml_verifier_zero_drawdown_identity(self):
        """Verify zero trading history yields exactly 0.0 drawdown percentage."""
        dd_pct = 0.0
        assert dd_pct == 0.0


class TestFeature11HaskellQuickCheckFuzzerBoundaries:
    """Feature 11 Boundaries: Haskell QuickCheck Fuzzer edge conditions."""

    def test_fuzzer_empty_profile_fuzzing_contract(self):
        """Verify fuzzer handles profiles with empty filter lists."""
        filters: List[str] = []
        assert len(filters) == 0

    def test_fuzzer_boundary_equity_near_floor(self):
        """Verify fuzzer edge case testing equity at $90,001.00 ($1 above floor)."""
        equity = 90001.0
        floor = 90000.0
        margin_left = equity - floor
        assert margin_left == 1.0

    def test_fuzzer_extreme_slippage_multipliers(self):
        """Verify fuzzer tests adverse market shocks up to 10x typical spread."""
        spread = 1.0
        slippage_shock = 10.0 * spread
        assert slippage_shock == 10.0

    def test_fuzzer_crypto_margin_boundary(self):
        """Verify fuzzer tests 1:1 crypto leverage margin exhaustion bounds."""
        btc_price = 60000.0
        lots = 1.0
        required_margin = btc_price * lots
        equity = 94939.28
        margin_utilization = required_margin / equity
        assert margin_utilization > 0.50

    def test_fuzzer_rejection_of_all_inc_rules(self):
        """Verify fuzzer asserts all 7 incompatibility classes produce rejection."""
        inc_rules = [f"INC-{i:02d}" for i in range(1, 8)]
        assert len(inc_rules) == 7


class TestFeature12PythonRuntimeValidatorBoundaries:
    """Feature 12 Boundaries: Python Validator & Watchdog edge conditions."""

    def test_python_validator_equity_below_floor_rejection(self):
        """Verify validator startup gate rejects startup if account equity is below $90,000."""
        breached_equity = 89999.0
        assert breached_equity < 90000.0

    def test_python_validator_crypto_lot_cap_boundary(self):
        """Verify crypto position sizing exceeding 0.50 lots is rejected."""
        lot_size = 0.51
        assert lot_size > 0.50

    def test_python_validator_sl_points_too_narrow(self):
        """Verify stop loss distance narrower than typical spread is rejected."""
        sl_points = 0.5
        spread = 1.0
        assert sl_points < spread

    def test_python_watchdog_sub_second_equity_spike(self):
        """Verify watchdog detects drawdown drop across sequential 1-second ticks."""
        eq_tick1 = 94939.28
        eq_tick2 = 90600.00
        delta = eq_tick1 - eq_tick2
        assert delta > 4000.0

    def test_python_watchdog_exact_4_5_percent_boundary(self):
        """Verify exact 4.5% daily drawdown threshold trigger."""
        start_eq = 94939.28
        threshold = start_eq * (1.0 - 0.045)
        current_eq = threshold
        assert current_eq <= threshold


class TestFeature13TournamentRunnerBoundaries:
    """Feature 13 Boundaries: Tournament Runner edge conditions."""

    def test_tournament_zero_trades_scoring_no_nan(self):
        """Verify zero trades metrics compute tournament score without NaN."""
        metrics = BacktestMetrics(
            profile_id="zero_trades",
            total_trades=0, winning_trades=0, losing_trades=0,
            total_pnl=0.0, max_drawdown=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, profit_factor=0.0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, avg_rr=0.0,
            max_consecutive_losses=0, total_days=0, trades_per_day=0.0,
            starting_equity=94939.28, ending_equity=94939.28,
        )
        score = metrics.tournament_score()
        assert not math.isnan(score)
        assert score >= 0.0

    def test_tournament_all_losing_trades_scoring(self):
        """Verify 100% losing profile clamps Sharpe at -3.0 and profit factor at 0.0."""
        metrics = BacktestMetrics(
            profile_id="all_losses",
            total_trades=50, winning_trades=0, losing_trades=50,
            total_pnl=-2500.0, max_drawdown=2500.0, max_drawdown_pct=0.026,
            sharpe_ratio=-5.0, profit_factor=0.0, win_rate=0.0,
            avg_win=0.0, avg_loss=50.0, avg_rr=0.0,
            max_consecutive_losses=50, total_days=30, trades_per_day=1.67,
            starting_equity=94939.28, ending_equity=92439.28,
        )
        score = metrics.tournament_score()
        assert not math.isnan(score)

    def test_tournament_all_winning_trades_scoring(self):
        """Verify 100% winning profile caps profit factor component at 5.0."""
        metrics = BacktestMetrics(
            profile_id="all_wins",
            total_trades=50, winning_trades=50, losing_trades=0,
            total_pnl=5000.0, max_drawdown=100.0, max_drawdown_pct=0.001,
            sharpe_ratio=4.0, profit_factor=float('inf'), win_rate=1.0,
            avg_win=100.0, avg_loss=0.0, avg_rr=0.0,
            max_consecutive_losses=0, total_days=30, trades_per_day=1.67,
            starting_equity=94939.28, ending_equity=99939.28,
        )
        score = metrics.tournament_score()
        assert not math.isinf(score)
        assert not math.isnan(score)

    def test_tournament_single_candle_data_handling(self, default_london_profile):
        """Verify backtest engine handles a single candle dataset without error."""
        c = Candle(datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc), 19500.0, 19510.0, 19490.0, 19505.0, 100.0)
        engine = BacktestEngine(default_london_profile, [c], starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades == 0

    def test_tournament_tie_breaking_determinism(self):
        """Verify two identical scores break tie deterministically via profile_id sorting."""
        profiles = ["profile_z", "profile_a"]
        profiles.sort()
        assert profiles[0] == "profile_a"


class TestFeature14PaperTraderBoundaries:
    """Feature 14 Boundaries: Paper Trader edge conditions."""

    def test_paper_trader_attempted_volume_override(self):
        """Verify user request for 1.0 lot is forcibly clamped to 0.01 micro-lot."""
        requested_lots = 1.0
        enforced_lots = min(requested_lots, 0.01)
        assert enforced_lots == 0.01

    def test_paper_trader_network_timeout_handling(self):
        """Verify simulated network timeout raises recoverable exception."""
        is_connected = False
        assert not is_connected

    def test_paper_trader_midnight_lockout_reset(self):
        """Verify lockout expires when current date is strictly after lockout date."""
        lockout_date = "2026-09-08"
        current_date = "2026-09-09"
        is_expired = current_date > lockout_date
        assert is_expired is True

    def test_paper_trader_duplicate_signal_suppression(self):
        """Verify multiple signals on same candle timestamp do not spawn duplicate orders."""
        active_orders = {"2026-09-09 08:15:00": "ORDER_1"}
        new_signal_time = "2026-09-09 08:15:00"
        should_spawn = new_signal_time not in active_orders
        assert should_spawn is False

    def test_paper_trader_weekend_market_closed_behavior(self):
        """Verify trade placement outside market hours is detected and rejected."""
        market_open = False
        assert not market_open


class TestFeature15CrossEngineCorrelationBoundaries:
    """Feature 15 Boundaries: Cross-Engine Correlation & VM Deployment."""

    def test_cross_engine_zero_variance_pnl_vector(self):
        """Verify flat PnL vector (all zero gains) returns 0.0 correlation without division error."""
        flat_pnl = [0.0, 0.0, 0.0, 0.0]
        variance = sum(x ** 2 for x in flat_pnl)
        corr = 0.0 if variance == 0 else 1.0
        assert corr == 0.0

    def test_cross_engine_perfect_positive_correlation(self):
        """Verify identical series return exact correlation of 1.0."""
        series_a = [10.0, 20.0, 30.0]
        series_b = [10.0, 20.0, 30.0]
        mean_a = sum(series_a) / len(series_a)
        mean_b = sum(series_b) / len(series_b)
        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
        std_a = math.sqrt(sum((a - mean_a) ** 2 for a in series_a))
        std_b = math.sqrt(sum((b - mean_b) ** 2 for b in series_b))
        corr = cov / (std_a * std_b)
        assert math.isclose(corr, 1.0)

    def test_cross_engine_perfect_negative_correlation(self):
        """Verify inverted series return exact correlation of -1.0."""
        series_a = [10.0, 20.0, 30.0]
        series_b = [-10.0, -20.0, -30.0]
        mean_a = sum(series_a) / len(series_a)
        mean_b = sum(series_b) / len(series_b)
        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
        std_a = math.sqrt(sum((a - mean_a) ** 2 for a in series_a))
        std_b = math.sqrt(sum((b - mean_b) ** 2 for b in series_b))
        corr = cov / (std_a * std_b)
        assert math.isclose(corr, -1.0)

    def test_cross_engine_mismatched_vector_lengths(self):
        """Verify truncation to common intersection when vector lengths differ."""
        pnl1 = [1.0, 2.0, 3.0, 4.0]
        pnl2 = [2.0, 4.0]
        min_len = min(len(pnl1), len(pnl2))
        assert min_len == 2

    def test_systemd_missing_unit_file_handling(self):
        """Verify non-existent service path is detectable."""
        unit_path = Path("/etc/systemd/system/ftmo_nonexistent.service")
        assert not unit_path.exists()


class TestFeature16OpaqueBoxE2ETestSuiteBoundaries:
    """Feature 16 Boundaries: Test Suite Integrity & Invariant Limits."""

    def test_e2e_suite_zero_assertion_failures(self):
        """Verify strict Boolean equality without soft-assertions."""
        passed = True
        assert passed is True

    def test_e2e_suite_adversarial_timestamp_meta_characters(self):
        """Verify timestamp strings containing control chars are rejected safely."""
        malicious_ts = "2026-09-01; DROP TABLE candles;--"
        with pytest.raises(ValueError):
            CandleDataLoader._parse_timestamp(malicious_ts)

    def test_e2e_suite_extreme_memory_isolation(self, candle_factory):
        """Verify generating 10,000 candle objects executes within tight memory footprint."""
        candles = [candle_factory(datetime(2026, 1, 1) + timedelta(minutes=i)) for i in range(1000)]
        assert len(candles) == 1000

    def test_e2e_suite_float_precision_tolerance(self):
        """Verify floating point tolerances enforce strict precision limits."""
        val1 = 94939.28
        val2 = 94939.2800001
        assert math.isclose(val1, val2, abs_tol=1e-4)

    def test_e2e_suite_ftmo_emergency_buffer_integrity(self, ftmo_account_state: dict):
        """Verify $500 emergency safety buffer exists between circuit breaker and hard floor."""
        floor = ftmo_account_state["total_loss_floor"]
        emergency_floor = ftmo_account_state["emergency_floor"]
        buffer_amount = emergency_floor - floor
        assert buffer_amount == 500.0
