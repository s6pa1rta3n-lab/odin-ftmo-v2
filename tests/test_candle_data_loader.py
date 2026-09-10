"""Unit tests for CandleDataLoader timestamp parsing and filename globbing."""

import csv
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backtester.engine import CandleDataLoader, Candle


def test_parse_timestamp_iso_milliseconds_z():
    """Verify ISO 8601 timestamps with millisecond precision and Z suffix."""
    ts_str = "2024-01-01T00:00:00.000Z"
    expected = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    actual = CandleDataLoader._parse_timestamp(ts_str)
    assert actual == expected


def test_parse_timestamp_iso_milliseconds_timezone_offset():
    """Verify ISO 8601 timestamps with millisecond precision and +00:00 suffix."""
    ts_str = "2024-01-01T00:00:00.000+00:00"
    expected = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    actual = CandleDataLoader._parse_timestamp(ts_str)
    assert actual == expected


def test_parse_timestamp_standard_iso():
    """Verify standard ISO 8601 timestamps without milliseconds."""
    ts_str = "2024-01-01T15:30:00Z"
    expected = datetime(2024, 1, 1, 15, 30, tzinfo=timezone.utc)
    actual = CandleDataLoader._parse_timestamp(ts_str)
    assert actual == expected


def test_parse_timestamp_space_separated():
    """Verify space-separated datetime strings."""
    ts_str = "2024-01-01 15:30:00"
    expected = datetime(2024, 1, 1, 15, 30, tzinfo=timezone.utc)
    actual = CandleDataLoader._parse_timestamp(ts_str)
    assert actual == expected


def test_parse_timestamp_epoch_milliseconds():
    """Verify unix epoch timestamps in milliseconds."""
    epoch_ms = 1704067200000
    expected = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    actual = CandleDataLoader._parse_timestamp(str(epoch_ms))
    assert actual == expected


def test_parse_timestamp_invalid_raises_error():
    """Verify invalid timestamp strings raise ValueError."""
    with pytest.raises(ValueError):
        CandleDataLoader._parse_timestamp("invalid_date_string")


def test_load_matches_dot_syntax_filename(tmp_path: Path):
    """Verify CandleDataLoader.load matches US100.cash_m1_*.csv format."""
    csv_file = tmp_path / "US100.cash_m1_2024-01-01_2026-09-09.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T14:30:00.000Z", "16500.0", "16520.0", "16490.0", "16510.0", "100.0"])
        writer.writerow(["2024-01-02T14:31:00.000Z", "16510.0", "16530.0", "16505.0", "16525.0", "120.0"])

    loader = CandleDataLoader(str(tmp_path))
    start_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 3, tzinfo=timezone.utc)
    candles = loader.load("US100.cash", start_dt, end_dt)

    assert len(candles) == 2
    assert candles[0].open == 16500.0
    assert candles[0].close == 16510.0
    assert candles[1].high == 16530.0


def test_load_matches_nodot_syntax_filename(tmp_path: Path):
    """Verify CandleDataLoader.load matches US100cash_m1_*.csv format."""
    csv_file = tmp_path / "US100cash_m1_20240101_20260909.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T10:00:00.000Z", "16400.0", "16410.0", "16390.0", "16405.0", "50.0"])

    loader = CandleDataLoader(str(tmp_path))
    start_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 3, tzinfo=timezone.utc)
    candles = loader.load("US100.cash", start_dt, end_dt)

    assert len(candles) == 1
    assert candles[0].open == 16400.0


def test_load_filters_by_date_range(tmp_path: Path):
    """Verify CandleDataLoader.load strictly excludes out-of-range candles."""
    csv_file = tmp_path / "EURUSD_m1_20240101_20260909.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-01T00:00:00Z", "1.1000", "1.1010", "1.0990", "1.1005", "10"])
        writer.writerow(["2024-01-02T00:00:00Z", "1.1005", "1.1020", "1.1000", "1.1015", "15"])
        writer.writerow(["2024-01-03T00:00:00Z", "1.1015", "1.1030", "1.1010", "1.1025", "20"])

    loader = CandleDataLoader(str(tmp_path))
    start_dt = datetime(2024, 1, 2, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    candles = loader.load("EURUSD", start_dt, end_dt)

    assert len(candles) == 1
    assert candles[0].timestamp == datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
