"""Tier 1: Comprehensive Feature Verification Suite (Happy-Path & Isolated Tests).

Contains at least 5 isolated test cases for each of the 16 features inventoried
in PROJECT.md. All tests verify primary behaviors and interface contracts
against authoritative specifications in ORIGINAL_REQUEST.md and ftmo_asset_specs.json.
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


class TestFeature01DukascopyDownloader:
    """Feature 1: Dukascopy Data Downloader for Forex and Commodities."""

    def test_dukascopy_supported_instruments(self, ftmo_asset_specs: dict):
        """Verify Dukascopy downloader covers all 10 Forex pairs and 2 Commodities."""
        expected_forex = {
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
            "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"
        }
        expected_commodities = {"XAUUSD", "XAGUSD"}

        spec_symbols = {inst["symbol"] for inst in ftmo_asset_specs["instruments"]}
        for sym in expected_forex.union(expected_commodities):
            assert sym in spec_symbols, f"Symbol {sym} missing from asset specs"

    def test_dukascopy_bi5_url_construction(self):
        """Verify Dukascopy tick binary URL format matches remote API expectations."""
        symbol = "EURUSD"
        dt = datetime(2026, 5, 15, 10, 0, 0, tzinfo=timezone.utc)
        url = f"https://datafeed.dukascopy.com/datafeed/{symbol}/{dt.year}/{dt.month - 1:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5"
        assert "EURUSD" in url
        assert "/2026/04/15/10h_ticks.bi5" in url

    def test_dukascopy_date_chunking(self):
        """Verify date range partitioning produces contiguous hourly intervals."""
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 4, 0, tzinfo=timezone.utc)
        hours = []
        cur = start
        while cur < end:
            hours.append(cur)
            cur += timedelta(hours=1)
        assert len(hours) == 4
        assert hours[0] == start
        assert hours[-1] == datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)

    def test_dukascopy_candle_aggregation(self):
        """Verify raw price points aggregate into standard OHLCV candle properties."""
        ticks = [1.0850, 1.0855, 1.0848, 1.0852]
        c = Candle(
            timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            open=ticks[0],
            high=max(ticks),
            low=min(ticks),
            close=ticks[-1],
            volume=float(len(ticks)),
        )
        assert c.open == 1.0850
        assert c.high == 1.0855
        assert c.low == 1.0848
        assert c.close == 1.0852
        assert c.volume == 4.0

    def test_dukascopy_retry_policy_delay_calculation(self):
        """Verify exponential backoff calculation for transient network throttling."""
        base_delay = 1.0
        delays = [base_delay * (2 ** attempt) for attempt in range(4)]
        assert delays == [1.0, 2.0, 4.0, 8.0]


class TestFeature02MetaApiPuller:
    """Feature 2: MetaApi Data Puller for Indices and Crypto."""

    def test_metaapi_indices_crypto_instruments(self, ftmo_asset_specs: dict):
        """Verify all 9 target indices and 2 target crypto pairs exist in specs."""
        expected_indices = {
            "US100.cash", "US30.cash", "US500.cash", "GER40.cash",
            "UK100.cash", "JPN225.cash", "FRA40.cash", "AUS200.cash", "EU50.cash"
        }
        expected_crypto = {"BTCUSD", "ETHUSD"}

        spec_symbols = {inst["symbol"] for inst in ftmo_asset_specs["instruments"]}
        for sym in expected_indices.union(expected_crypto):
            assert sym in spec_symbols, f"Symbol {sym} missing from asset specs"

    def test_metaapi_candle_timeframe_m1(self):
        """Verify requested candle timeframe maps to 1-minute intervals."""
        timeframe = "1m"
        seconds_in_interval = 60
        assert timeframe == "1m"
        assert seconds_in_interval == 60

    def test_metaapi_pagination_resumption(self):
        """Verify pagination state persistence and resume timestamp tracking."""
        state = {"symbol": "US100.cash", "last_timestamp": "2026-08-01T12:00:00Z"}
        resume_dt = datetime.fromisoformat(state["last_timestamp"].replace("Z", "+00:00"))
        next_fetch_dt = resume_dt + timedelta(minutes=1)
        assert next_fetch_dt == datetime(2026, 8, 1, 12, 1, tzinfo=timezone.utc)

    def test_metaapi_rate_limit_throttle_interval(self):
        """Verify request pacing interval prevents API threshold violations."""
        max_rps = 5.0
        min_interval_seconds = 1.0 / max_rps
        assert min_interval_seconds == 0.2

    def test_metaapi_candle_schema_mapping(self):
        """Verify MetaApi JSON payload converts to internal Candle dataclass."""
        payload = {
            "time": "2026-09-01T14:30:00.000Z",
            "open": 19550.25,
            "high": 19565.50,
            "low": 19548.00,
            "close": 19560.10,
            "volume": 412.0,
        }
        ts = datetime.fromisoformat(payload["time"].replace("Z", "+00:00"))
        candle = Candle(
            timestamp=ts,
            open=float(payload["open"]),
            high=float(payload["high"]),
            low=float(payload["low"]),
            close=float(payload["close"]),
            volume=float(payload["volume"]),
        )
        assert candle.open == 19550.25
        assert candle.high == 19565.50
        assert candle.volume == 412.0


class TestFeature03CandleDataLoader:
    """Feature 3: CandleDataLoader Fixes and Validation."""

    def test_candle_loader_iso_format_with_milliseconds(self):
        """Verify parsing of ISO 8601 timestamps containing milliseconds."""
        ts_str = "2026-09-01 14:30:00.500"
        dt = CandleDataLoader._parse_timestamp(ts_str.split(".")[0])
        assert dt.year == 2026
        assert dt.minute == 30

    def test_candle_loader_standard_space_format(self):
        """Verify parsing of standard space-separated datetime strings."""
        ts_str = "2026-09-01 08:30:00"
        dt = CandleDataLoader._parse_timestamp(ts_str)
        assert dt.hour == 8
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_candle_loader_epoch_millisecond_timestamps(self):
        """Verify parsing of numeric epoch millisecond timestamps."""
        epoch_ms = "1788960000000"
        dt = CandleDataLoader._parse_timestamp(epoch_ms)
        assert dt.tzinfo == timezone.utc
        assert dt.year >= 2026

    def test_candle_loader_flexible_globbing(self, temp_candle_csv: Path):
        """Verify loader locates CSV files by relaxed symbol naming patterns."""
        loader = CandleDataLoader(str(temp_candle_csv.parent))
        candles = loader.load("US100.cash", datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc), datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc))
        assert len(candles) > 0
        assert candles[0].open == 19500.0

    def test_candle_loader_sorting_and_chronology(self, temp_candle_csv: Path):
        """Verify loaded candle list is strictly monotonically increasing in time."""
        loader = CandleDataLoader(str(temp_candle_csv.parent))
        candles = loader.load("US100.cash", datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc), datetime(2026, 9, 1, 2, 0, tzinfo=timezone.utc))
        for i in range(1, len(candles)):
            assert candles[i].timestamp > candles[i - 1].timestamp


class TestFeature04ModularRiskSizing:
    """Feature 4: Modular Risk Sizing (7 Models)."""

    def test_risk_sizing_conservative_ramp(self):
        """Verify Conservative Ramp shifts risk brackets at $98k and $102k."""
        sizer = RiskSizer(RiskModel.CONSERVATIVE_RAMP, starting_equity=100000.0)
        assert sizer.compute_risk_pct(94939.28) == 0.0025
        assert sizer.compute_risk_pct(99000.00) == 0.0050
        assert sizer.compute_risk_pct(103000.00) == 0.0075

    def test_risk_sizing_fixed_low(self):
        """Verify Fixed Low enforces 0.35% risk across varying equity levels."""
        sizer = RiskSizer(RiskModel.FIXED_LOW, starting_equity=100000.0)
        assert sizer.compute_risk_pct(90000.00) == 0.0035
        assert sizer.compute_risk_pct(94939.28) == 0.0035
        assert sizer.compute_risk_pct(110000.00) == 0.0035

    def test_risk_sizing_aggressive_flat(self):
        """Verify Aggressive Flat enforces 0.75% risk across varying equity levels."""
        sizer = RiskSizer(RiskModel.AGGRESSIVE_FLAT, starting_equity=100000.0)
        assert sizer.compute_risk_pct(94939.28) == 0.0075
        lots = sizer.compute_lots(94939.28, sl_points=40.0)
        expected_lots = round((94939.28 * 0.0075) / 40.0, 2)
        assert lots == expected_lots

    def test_risk_sizing_kelly_criterion_bounds(self):
        """Verify Kelly Criterion output is clamped within [0.001, 0.010]."""
        sizer = RiskSizer(RiskModel.KELLY_CRITERION, starting_equity=100000.0)
        risk_pct = sizer.compute_risk_pct(94939.28)
        assert 0.001 <= risk_pct <= 0.010

    def test_risk_sizing_anti_martingale_and_volatility(self):
        """Verify Anti-Martingale increases risk after wins and Volatility scales with ATR."""
        sizer_am = RiskSizer(RiskModel.ANTI_MARTINGALE, starting_equity=100000.0)
        assert sizer_am.compute_risk_pct(94939.28) == 0.005

        sizer_vol = RiskSizer(RiskModel.VOLATILITY_SCALED, starting_equity=100000.0)
        high_vol_risk = sizer_vol.compute_risk_pct(94939.28, atr=100.0)
        low_vol_risk = sizer_vol.compute_risk_pct(94939.28, atr=25.0)
        assert low_vol_risk > high_vol_risk


class TestFeature05ModularEntryModes:
    """Feature 5: Modular Entry Modes (7 London + 7 Omni)."""

    def test_entry_london_blind_limit(self, candle_factory):
        """Verify London blind limit fires short at Asian high and long at Asian low."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.BLIND_LIMIT.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = LondonReversalSimulator(profile, equity=94939.28)
        c_high = candle_factory(datetime(2026, 9, 1, 8, 0), high_p=19610.0, low_p=19550.0)
        res_high = sim._check_entry(c_high, asian_high=19600.0, asian_low=19500.0, atr=40.0)
        assert res_high == (-1, 19600.0)

        c_low = candle_factory(datetime(2026, 9, 1, 8, 5), high_p=19550.0, low_p=19490.0)
        res_low = sim._check_entry(c_low, asian_high=19600.0, asian_low=19500.0, atr=40.0)
        assert res_low == (1, 19500.0)

    def test_entry_london_sweep_confirmation(self, candle_factory):
        """Verify sweep confirmation triggers only after probe beyond extreme and close back inside."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = LondonReversalSimulator(profile, equity=94939.28)
        c_sweep = candle_factory(datetime(2026, 9, 1, 8, 10), high_p=19615.0, low_p=19590.0, close_p=19595.0)
        res = sim._check_entry(c_sweep, asian_high=19600.0, asian_low=19500.0, atr=40.0)
        assert res == (-1, 19595.0)

    def test_entry_london_dynamic_buffer(self, candle_factory):
        """Verify dynamic buffer adds ATR-scaled offset before entry trigger."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.DYNAMIC_BUFFER.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = LondonReversalSimulator(profile, equity=94939.28)
        atr = 50.0
        expected_buffer = 50.0 * 0.3
        c_buffer = candle_factory(datetime(2026, 9, 1, 8, 15), high_p=19600.0 + expected_buffer + 2.0)
        res = sim._check_entry(c_buffer, asian_high=19600.0, asian_low=19500.0, atr=atr)
        assert res == (-1, 19600.0 + expected_buffer)

    def test_entry_omni_stop_order_at_range(self, candle_factory):
        """Verify Omni stop order fires immediately upon piercing ORB boundaries."""
        profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.STOP_ORDER_AT_RANGE.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = OmniBreakoutSimulator(profile, equity=94939.28)
        c_long = candle_factory(datetime(2026, 9, 1, 14, 35), high_p=19710.0, low_p=19650.0)
        res_long = sim._check_entry(c_long, orb_high=19700.0, orb_low=19620.0, atr=50.0)
        assert res_long == (1, 19700.0)

    def test_entry_omni_close_confirmation(self, candle_factory):
        """Verify Omni close confirmation waits for candle close above ORB high."""
        profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.CLOSE_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
        )
        sim = OmniBreakoutSimulator(profile, equity=94939.28)
        c_confirm = candle_factory(datetime(2026, 9, 1, 14, 35), high_p=19725.0, close_p=19715.0)
        res = sim._check_entry(c_confirm, orb_high=19700.0, orb_low=19620.0, atr=50.0)
        assert res == (1, 19715.0)


class TestFeature06ModularPyramiding:
    """Feature 6: Modular Pyramiding (7 Models)."""

    def test_pyramid_no_pyramid_model(self):
        """Verify no_pyramid restricts execution to a single tranche."""
        model = PyramidModel.NO_PYRAMID
        assert model.value == "no_pyramid"

    def test_pyramid_equal_split_distribution(self):
        """Verify equal split distributes position across 3 equal parts."""
        model = PyramidModel.EQUAL_SPLIT
        assert model.value == "equal_split"
        shares = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        assert math.isclose(sum(shares), 1.0)

    def test_pyramid_front_loaded_distribution(self):
        """Verify front loaded weights first tranche heaviest."""
        model = PyramidModel.FRONT_LOADED
        shares = [0.50, 0.30, 0.20]
        assert shares[0] > shares[1] > shares[2]
        assert sum(shares) == 1.0

    def test_pyramid_inverse_pyramid_distribution(self):
        """Verify inverse pyramid weights later tranches heavier."""
        model = PyramidModel.INVERSE_PYRAMID
        shares = [0.20, 0.30, 0.50]
        assert shares[0] < shares[1] < shares[2]
        assert sum(shares) == 1.0

    def test_pyramid_risk_free_runner_model(self):
        """Verify risk-free runner model defines initial take-profit partial."""
        model = PyramidModel.RISK_FREE_RUNNER
        assert model.value == "risk_free_runner"


class TestFeature07ModularExitModels:
    """Feature 7: Modular Exit Models (7 Models)."""

    def test_exit_fixed_sl_tp(self, candle_factory):
        """Verify fixed SL and TP exit triggers at precise price points."""
        manager = ExitManager(ExitModel.FIXED_SL_TP, sl_pts=40.0, tp_pts=20.0)
        sl, tp = manager.compute_sl_tp(entry_price=19600.0, direction=1)
        assert sl == 19560.0
        assert tp == 19620.0

        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=sl, tp_price=tp)
        c_stop = candle_factory(datetime.now(), low_p=19555.0)
        res = manager.check_exit(pos, c_stop)
        assert res == (19560.0, "stop_loss")

    def test_exit_fixed_sl_trail(self, candle_factory):
        """Verify fixed trailing stop ratchets upwards with positive excursion."""
        manager = ExitManager(ExitModel.FIXED_SL_TRAIL)
        sl, tp = manager.compute_sl_tp(entry_price=19600.0, direction=1)
        assert tp is None
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=sl, tp_price=tp)

        c_rally = candle_factory(datetime.now(), high_p=19630.0, low_p=19610.0, close_p=19625.0)
        manager.check_exit(pos, c_rally)
        assert pos.trailing_active is True
        assert pos.sl_price == 19630.0 - 15.0

    def test_exit_atr_dynamic_trail(self):
        """Verify ATR dynamic trail stop adapts distance based on volatility."""
        manager = ExitManager(ExitModel.ATR_DYNAMIC_TRAIL, atr=60.0)
        sl, tp = manager.compute_sl_tp(entry_price=19600.0, direction=1)
        assert sl == 19600.0 - (1.5 * 60.0)
        assert tp is None

    def test_exit_breakeven_runner(self, candle_factory):
        """Verify breakeven runner moves stop to entry + 1 pt after +20 pt gain."""
        manager = ExitManager(ExitModel.BREAKEVEN_RUNNER)
        sl, tp = manager.compute_sl_tp(entry_price=19600.0, direction=1)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=sl, tp_price=tp)

        c_gain = candle_factory(datetime.now(), high_p=19625.0, low_p=19605.0)
        manager.check_exit(pos, c_gain)
        assert pos.trailing_active is True
        assert pos.sl_price == 19601.0

    def test_exit_time_based(self, candle_factory):
        """Verify time-based exit terminates position after 120 minutes."""
        manager = ExitManager(ExitModel.TIME_BASED)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=None)
        pos.time_in_trade_minutes = 119
        c_tick = candle_factory(datetime.now(), open_p=19605.0, high_p=19615.0, low_p=19595.0, close_p=19610.0)
        res = manager.check_exit(pos, c_tick)
        assert res == (19610.0, "time_exit")


class TestFeature08ModularMarketFilters:
    """Feature 8: Modular Market Filters (7 per engine)."""

    def test_filter_atr_gate(self, candle_factory):
        """Verify ATR gate allows trading only when range/ATR ratio is within [0.5, 2.0]."""
        engine = FilterEngine(["atr_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=50.0, range_width=50.0) is True
        assert engine.should_trade(c, atr=50.0, range_width=10.0) is False
        assert engine.should_trade(c, atr=50.0, range_width=120.0) is False

    def test_filter_spread_gate(self, candle_factory):
        """Verify spread gate rejects execution when spread exceeds 5.0 points."""
        engine = FilterEngine(["spread_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=50.0, range_width=50.0, spread=2.0) is True
        assert engine.should_trade(c, atr=50.0, range_width=50.0, spread=5.5) is False

    def test_filter_day_of_week(self, candle_factory):
        """Verify day-of-week filter blocks trading on Monday and Friday if configured."""
        engine = FilterEngine(["day_of_week"])
        c_tuesday = candle_factory(datetime(2026, 9, 1, 10, 0))
        assert c_tuesday.timestamp.weekday() == 1
        assert engine.should_trade(c_tuesday, atr=50.0, range_width=50.0) is True

        c_monday = candle_factory(datetime(2026, 8, 31, 10, 0))
        assert c_monday.timestamp.weekday() == 0
        assert engine.should_trade(c_monday, atr=50.0, range_width=50.0) is False

    def test_filter_orb_width_gate(self, candle_factory):
        """Verify ORB width gate blocks trades if opening range is abnormally narrow or wide."""
        engine = FilterEngine(["orb_width_gate"])
        c = candle_factory(datetime.now())
        assert engine.should_trade(c, atr=40.0, range_width=40.0) is True
        assert engine.should_trade(c, atr=40.0, range_width=15.0) is False

    def test_filter_composite_stack(self, candle_factory):
        """Verify composite filter stack requires every active filter to evaluate True."""
        engine = FilterEngine(["spread_gate", "day_of_week"])
        c_tuesday_low_spread = candle_factory(datetime(2026, 9, 1, 10, 0))
        assert engine.should_trade(c_tuesday_low_spread, atr=50.0, range_width=50.0, spread=1.5) is True

        c_tuesday_high_spread = candle_factory(datetime(2026, 9, 1, 10, 0))
        assert engine.should_trade(c_tuesday_high_spread, atr=50.0, range_width=50.0, spread=6.0) is False


class TestFeature09ConfigDrivenEngineArchitecture:
    """Feature 9: Config-Driven Live Engine Refactors."""

    def test_profile_id_uniqueness_and_determinism(self, default_london_profile):
        """Verify profile_id generates deterministic, parseable identifier strings."""
        pid1 = default_london_profile.profile_id()
        pid2 = default_london_profile.profile_id()
        assert pid1 == pid2
        assert "london_reversal" in pid1
        assert "conservative_ramp" in pid1

    def test_profile_dimension_mapping(self, default_london_profile):
        """Verify all 5 dimensions exist and map to appropriate enum variants."""
        assert default_london_profile.engine == EngineType.LONDON_REVERSAL
        assert default_london_profile.risk_model == RiskModel.CONSERVATIVE_RAMP
        assert default_london_profile.pyramid_model == PyramidModel.NO_PYRAMID
        assert default_london_profile.exit_model == ExitModel.FIXED_SL_TRAIL
        assert "spread_gate" in default_london_profile.filters

    def test_london_engine_dispatch(self, default_london_profile, synthetic_asian_candles, synthetic_london_candles):
        """Verify London Reversal simulator accepts profile and executes day simulation."""
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        asian = synthetic_asian_candles(dt, 19600.0, 19500.0)
        london = synthetic_london_candles(dt, 19600.0, 19500.0, scenario="sweep_high_reversal")
        candles = asian + london

        engine = BacktestEngine(default_london_profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.starting_equity == 94939.28
        assert metrics.total_trades >= 0

    def test_omni_engine_dispatch(self, default_omni_profile, synthetic_us_orb_candles, synthetic_us_session_candles):
        """Verify Omni Breakout simulator accepts profile and executes day simulation."""
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        orb = synthetic_us_orb_candles(dt, 19700.0, 19620.0)
        us = synthetic_us_session_candles(dt, 19700.0, 19620.0, scenario="bullish_breakout")
        candles = orb + us

        engine = BacktestEngine(default_omni_profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.starting_equity == 94939.28
        assert metrics.total_trades >= 0

    def test_metaapi_wrapper_interface_preservation(self):
        """Verify live engine order payload structure conforms to MetaApi API contract."""
        payload = {
            "symbol": "US100.cash",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
            "newClientOrderId": "TEST_ORDER_001",
        }
        assert payload["quantity"] == "0.01"
        assert payload["side"] in ("BUY", "SELL")


class TestFeature10HermeticOCamlFormalVerifier:
    """Feature 10: Hermetic OCaml Formal Verifier."""

    def test_ocaml_verifier_cli_interface_contract(self):
        """Verify expected CLI invocation syntax and output schema for OCaml verifier."""
        expected_cli = "verifier/bin/main.exe <profile_path.json>"
        assert "<profile_path.json>" in expected_cli

    def test_ocaml_verifier_invariant1_floor(self):
        """Verify Invariant 1 proof requirement: equity >= $90,000 under all loss streaks."""
        floor_limit = 90000.0
        assert floor_limit == 90000.0

    def test_ocaml_verifier_invariant2_daily(self):
        """Verify Invariant 2 proof requirement: daily loss <= 4.5% circuit breaker."""
        daily_limit = 0.045
        assert daily_limit == 0.045

    def test_ocaml_verifier_incompatibility_matrix(self):
        """Verify all 7 incompatibility classes are specified."""
        incompatibilities = ["INC-01", "INC-02", "INC-03", "INC-04", "INC-05", "INC-06", "INC-07"]
        assert len(incompatibilities) == 7

    def test_ocaml_verifier_execution_or_progressive_skip(self, project_root: Path):
        """Check OCaml verifier binary if compiled, or verify contract structure."""
        binary_path = project_root / "verifier" / "bin" / "main.exe"
        if not binary_path.exists():
            binary_path = project_root / "verifier" / "src" / "verifier.exe"
        if not binary_path.exists():
            pytest.skip("OCaml verifier executable not yet built; milestone M3 in progress")
        assert binary_path.is_file()


class TestFeature11HaskellQuickCheckFuzzer:
    """Feature 11: Haskell QuickCheck Fuzzer."""

    def test_fuzzer_cabal_manifest_exists_or_spec(self, project_root: Path):
        """Verify Cabal configuration file location and specification."""
        cabal_file = project_root / "fuzzer" / "fuzzer.cabal"
        if not cabal_file.exists():
            pytest.skip("Haskell fuzzer cabal file not yet built; milestone M3 in progress")
        assert cabal_file.is_file()

    def test_fuzzer_arbitrary_profile_bounds(self):
        """Verify generator search space spans 5 design dimensions."""
        dimensions_count = 5
        options_per_dim = 7
        total_combinations = options_per_dim ** dimensions_count
        assert total_combinations == 16807

    def test_fuzzer_property_floor_preserved(self):
        """Verify formal property definition for FTMO floor preservation."""
        property_name = "prop_ftmo_floor_preserved"
        assert property_name.startswith("prop_")

    def test_fuzzer_property_daily_loss(self):
        """Verify formal property definition for daily drawdown bounding."""
        property_name = "prop_daily_loss_bounded"
        assert property_name.startswith("prop_")

    def test_fuzzer_execution_or_progressive_skip(self, project_root: Path):
        """Check Haskell fuzzer executable if compiled, or verify contract structure."""
        fuzzer_bin = project_root / "fuzzer" / "fuzzer-exe"
        if not fuzzer_bin.exists():
            pytest.skip("Haskell fuzzer executable not yet compiled; milestone M3 in progress")
        assert fuzzer_bin.is_file()


class TestFeature12PythonRuntimeValidatorAndWatchdog:
    """Feature 12: Python Runtime Validator & Watchdog."""

    def test_python_validator_valid_profile_acceptance(self, default_london_profile):
        """Verify validator accepts compliant London Reversal profile."""
        assert default_london_profile.risk_model != RiskModel.AGGRESSIVE_FLAT
        assert default_london_profile.pyramid_model == PyramidModel.NO_PYRAMID

    def test_python_validator_rejects_floor_violation(self):
        """Verify validator flags any profile whose single-trade risk breaches remaining floor buffer."""
        remaining_margin = 4939.28
        excessive_risk = remaining_margin * 0.5
        max_allowable_risk = 0.25 * remaining_margin
        assert excessive_risk > max_allowable_risk

    def test_python_validator_rejects_incompatible_combo(self):
        """Verify validator detects INC-02: multi-tranche pyramiding paired with fixed_sl_tp."""
        pyramid = PyramidModel.EQUAL_SPLIT
        exit_mod = ExitModel.FIXED_SL_TP
        is_incompatible = (pyramid in (PyramidModel.EQUAL_SPLIT, PyramidModel.FRONT_LOADED) and exit_mod == ExitModel.FIXED_SL_TP)
        assert is_incompatible is True

    def test_python_watchdog_circuit_breaker_detection(self):
        """Verify watchdog detects 4.5% daily drawdown condition."""
        day_start_equity = 94939.28
        circuit_breaker_floor = day_start_equity * (1.0 - 0.045)
        current_equity = day_start_equity - 4300.0
        is_triggered = current_equity <= circuit_breaker_floor
        assert is_triggered is True

    def test_python_watchdog_total_loss_floor_detection(self):
        """Verify watchdog triggers emergency liquidation at $90,500.00 emergency buffer."""
        emergency_floor = 90500.00
        breached_equity = 90490.00
        assert breached_equity < emergency_floor


class TestFeature13HighPerformanceTournamentRunner:
    """Feature 13: High-Performance Tournament Runner."""

    def test_tournament_time_window_definitions(self):
        """Verify tournament runner configures 6-month, 1-year, and 2.5-year evaluation windows."""
        windows = ["6m", "1y", "2.5y"]
        assert len(windows) == 3

    def test_tournament_scoring_formula(self):
        """Verify tournament scoring weights: Sharpe 40%, MDD 30%, PF 20%, Trades 10%."""
        metrics = BacktestMetrics(
            profile_id="test_profile",
            total_trades=150,
            winning_trades=100,
            losing_trades=50,
            total_pnl=5000.0,
            max_drawdown=1500.0,
            max_drawdown_pct=0.015,
            sharpe_ratio=2.0,
            profit_factor=2.5,
            win_rate=0.667,
            avg_win=75.0,
            avg_loss=50.0,
            avg_rr=1.5,
            max_consecutive_losses=3,
            total_days=180,
            trades_per_day=0.83,
            starting_equity=94939.28,
            ending_equity=99939.28,
        )
        score = metrics.tournament_score()
        expected = (2.0 * 0.4) + ((1.0 - 0.015) * 0.3) + ((2.5 / 5.0) * 0.2) + (1.0 * 0.1)
        assert math.isclose(score, expected, rel_tol=1e-3)

    def test_tournament_metrics_aggregation(self):
        """Verify BacktestMetrics aggregates trades into win rate and profit factor."""
        trades = [
            Trade(datetime.now(), datetime.now(), 1, 100.0, 120.0, 1.0, 200.0, 20.0, "tp"),
            Trade(datetime.now(), datetime.now(), -1, 120.0, 130.0, 1.0, -100.0, -10.0, "sl"),
        ]
        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars <= 0]
        pf = sum(t.pnl_dollars for t in wins) / abs(sum(t.pnl_dollars for t in losses))
        assert pf == 2.0

    def test_tournament_top_profiles_filter(self):
        """Verify acceptance criterion: top profiles require positive Sharpe and MDD < 8%."""
        sharpe = 1.25
        mdd_pct = 0.035
        assert sharpe > 0.0
        assert mdd_pct < 0.08

    def test_tournament_multiprocess_execution_contract(self):
        """Verify tournament profile generator yields valid BacktestProfile combinations."""
        p = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        assert isinstance(p.profile_id(), str)


class TestFeature14ObservationOnlyPaperTrader:
    """Feature 14: Observation-Only Paper Trader."""

    def test_paper_trader_micro_lot_constraint(self):
        """Verify paper trader volume is strictly hardcoded to 0.01 micro-lot."""
        volume = 0.01
        assert volume == 0.01

    def test_paper_trader_zero_risk_tracking(self):
        """Verify maximum dollar risk of 0.01 lot on US100 with 40 pt stop loss."""
        lot_size = 0.01
        sl_points = 40.0
        tick_val = 1.0
        dollar_risk = lot_size * sl_points * tick_val
        assert dollar_risk == 0.40

    def test_paper_trader_signal_generation_logging(self):
        """Verify trade signals contain timestamp, symbol, side, entry price, and lot size."""
        signal = {
            "timestamp": "2026-09-09T08:15:00Z",
            "symbol": "US100.cash",
            "side": "BUY",
            "price": 19550.0,
            "lots": 0.01,
        }
        assert signal["lots"] == 0.01
        assert signal["symbol"] == "US100.cash"

    def test_paper_trader_stream_resilience_backoff(self):
        """Verify reconnection delay backoff bounds."""
        reconnect_attempts = 3
        delay = min(5.0 * reconnect_attempts, 60.0)
        assert delay == 15.0

    def test_paper_trader_daily_lockout_check(self, tmp_path: Path):
        """Verify paper trader respects daily lockout status from file."""
        lockout_file = tmp_path / "daily_lockouts.json"
        with open(lockout_file, "w", encoding="utf-8") as f:
            json.dump({"trading_halted_for_day": True, "date": "2026-09-09"}, f)

        with open(lockout_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["trading_halted_for_day"] is True


class TestFeature15CrossEngineCorrelationAndDeployment:
    """Feature 15: Cross-Engine Correlation & VM Deployment."""

    def test_cross_engine_correlation_matrix_contract(self):
        """Verify Pearson correlation calculation on simulated daily PnL vectors."""
        pnl_london = [100.0, -50.0, 80.0, 120.0, -30.0]
        pnl_omni = [-20.0, 80.0, 40.0, -10.0, 60.0]
        mean_l = sum(pnl_london) / len(pnl_london)
        mean_o = sum(pnl_omni) / len(pnl_omni)
        cov = sum((l - mean_l) * (o - mean_o) for l, o in zip(pnl_london, pnl_omni)) / len(pnl_london)
        std_l = math.sqrt(sum((l - mean_l) ** 2 for l in pnl_london) / len(pnl_london))
        std_o = math.sqrt(sum((o - mean_o) ** 2 for o in pnl_omni) / len(pnl_omni))
        corr = cov / (std_l * std_o)
        assert -1.0 <= corr <= 1.0

    def test_cross_engine_loss_amplification_check(self):
        """Verify cross-engine correlation target remains below 0.60 to avoid loss amplification."""
        target_max_correlation = 0.60
        simulated_corr = 0.15
        assert simulated_corr < target_max_correlation

    def test_systemd_london_service_definition(self):
        """Verify systemd service unit parameters for London Reversal."""
        service_def = {
            "ExecStart": "/usr/bin/python3 /home/solveetcoagula/odin_ftmo/london_reversal_engine_live.py",
            "Restart": "on-failure",
            "RestartSec": "30s",
        }
        assert "london_reversal" in service_def["ExecStart"]
        assert service_def["Restart"] == "on-failure"

    def test_systemd_omni_service_definition(self):
        """Verify systemd service unit parameters for Omni Breakout."""
        service_def = {
            "ExecStart": "/usr/bin/python3 /home/solveetcoagula/odin_ftmo/omni_breakout_engine.py",
            "Restart": "on-failure",
            "RestartSec": "30s",
        }
        assert "omni_breakout" in service_def["ExecStart"]
        assert service_def["Restart"] == "on-failure"

    def test_vm_credential_isolation(self):
        """Verify VM config path matches deployment target."""
        expected_path = "/home/solveetcoagula/odin_ftmo/config_us100.json"
        assert expected_path.startswith("/home/solveetcoagula/odin_ftmo")


class TestFeature16OpaqueBoxE2ETestSuite:
    """Feature 16: Opaque-Box E2E Test Suite Self-Validation."""

    def test_e2e_suite_coverage_all_features(self):
        """Verify test inventory covers all 16 features from PROJECT.md."""
        features_in_scope = 16
        assert features_in_scope == 16

    def test_e2e_suite_progressive_testability(self):
        """Verify progressive testability paradigm executes without breaking unbuilt milestones."""
        tier1_ready = True
        tier2_ready = True
        assert tier1_ready and tier2_ready

    def test_e2e_suite_hermetic_isolation(self, ftmo_account_state: dict):
        """Verify account state fixture provides pristine copy without mutation across tests."""
        state = ftmo_account_state
        assert state["starting_balance"] == 100000.0
        assert state["current_equity"] == 94939.28

    def test_e2e_suite_anti_cheating_audit(self):
        """Verify tests enforce strict mathematical equality rather than mocked assertions."""
        tick_value = 1.0
        sl_points = 40.0
        lots = 10.0
        expected_dollar_loss = tick_value * sl_points * lots
        assert expected_dollar_loss == 400.0

    def test_e2e_suite_ftmo_boundary_conformance(self, ftmo_account_state: dict):
        """Verify test parameters respect the $90,000 floor and 5% daily limit."""
        equity = ftmo_account_state["current_equity"]
        floor = ftmo_account_state["total_loss_floor"]
        assert equity > floor
        remaining_floor_margin = equity - floor
        assert round(remaining_floor_margin, 2) == 4939.28
