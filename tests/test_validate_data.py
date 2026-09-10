"""Unit tests for data/validate_data.py validation functions."""

import csv
from datetime import datetime, timezone
from pathlib import Path
import pytest

from data.validate_data import (
    is_weekend_gap,
    parse_timestamp_flexible,
    validate_csv_file,
    verify_candle_loader,
)


def test_parse_timestamp_flexible_formats():
    """Verify parse_timestamp_flexible parses milliseconds, ISO, and epoch."""
    dt_iso_ms = parse_timestamp_flexible("2024-01-01T12:00:00.000Z")
    assert dt_iso_ms == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    dt_offset = parse_timestamp_flexible("2024-01-01T12:00:00.000+00:00")
    assert dt_offset == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    dt_space = parse_timestamp_flexible("2024-01-01 12:00:00")
    assert dt_space == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    dt_epoch = parse_timestamp_flexible("1704110400000")
    assert dt_epoch == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_is_weekend_gap_detection():
    """Verify weekend detection distinguishes weekend closes from intraday gaps."""
    fri_close = datetime(2024, 1, 5, 21, 59, tzinfo=timezone.utc)
    sun_open = datetime(2024, 1, 7, 22, 0, tzinfo=timezone.utc)
    assert is_weekend_gap(fri_close, sun_open) is True

    t1 = datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 1, 3, 10, 5, tzinfo=timezone.utc)
    assert is_weekend_gap(t1, t2) is False


def test_validate_csv_file_clean_data(tmp_path: Path):
    """Verify validate_csv_file reports clean data as valid."""
    csv_file = tmp_path / "EURUSD_m1_test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T10:00:00Z", "1.1000", "1.1010", "1.0990", "1.1005", "100"])
        writer.writerow(["2024-01-02T10:01:00Z", "1.1005", "1.1015", "1.1000", "1.1010", "110"])
        writer.writerow(["2024-01-02T10:02:00Z", "1.1010", "1.1020", "1.1008", "1.1018", "90"])

    stats = validate_csv_file(csv_file, fix=True)
    assert stats["valid"] is True
    assert stats["total_rows"] == 3
    assert stats["duplicates_found"] == 0
    assert stats["invalid_ohlc"] == 0


def test_validate_csv_file_removes_duplicates(tmp_path: Path):
    """Verify duplicate rows are detected and removed when fix=True."""
    csv_file = tmp_path / "US100.cash_m1_test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T14:30:00.000Z", "16500.0", "16510.0", "16490.0", "16505.0", "50"])
        writer.writerow(["2024-01-02T14:30:00.000Z", "16500.0", "16510.0", "16490.0", "16505.0", "50"])
        writer.writerow(["2024-01-02T14:31:00.000Z", "16505.0", "16515.0", "16500.0", "16512.0", "60"])

    stats = validate_csv_file(csv_file, fix=True)
    assert stats["duplicates_found"] == 1
    assert stats["duplicates_removed"] == 1
    assert stats["valid"] is True

    with open(csv_file, "r") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 3


def test_validate_csv_file_detects_invalid_ohlc(tmp_path: Path):
    """Verify non-positive prices and invalid ranges are flagged."""
    csv_file = tmp_path / "BAD_m1_test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T10:00:00Z", "0.0", "1.1010", "1.0990", "1.1005", "100"])

    stats = validate_csv_file(csv_file, fix=False)
    assert stats["valid"] is False
    assert stats["invalid_ohlc"] > 0


def test_verify_candle_loader_integration(tmp_path: Path):
    """Verify verify_candle_loader confirms CandleDataLoader loads the candles."""
    csv_file = tmp_path / "US100.cash_m1_2024-01-01_2026-09-09.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2024-01-02T14:30:00.000Z", "16500.0", "16510.0", "16490.0", "16505.0", "50"])
        writer.writerow(["2024-01-02T14:31:00.000Z", "16505.0", "16515.0", "16500.0", "16512.0", "60"])

    loader_stats = verify_candle_loader("US100.cash", tmp_path)
    assert loader_stats["valid"] is True
    assert loader_stats["candles_loaded"] == 2
