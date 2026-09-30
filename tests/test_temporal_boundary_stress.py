"""Adversarial stress tests for temporal boundary conditions and order cancellation isolation."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import zoneinfo

import pytest
import pytz

import london_reversal_engine_live as london_engine
import omni_breakout_engine as omni_engine
from omni_breakout_engine import is_eod_window


def test_eod_window_full_86400_second_utc_sweep() -> None:
    """Execute exhaustive 86,400-second sweep for a 24-hour UTC day against is_eod_window.

    Verifies that every second from 00:00:00 to 19:44:59 evaluates to False,
    and every second from 19:45:00 to 23:59:59 evaluates to True.
    """
    base_date = datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)
    false_count = 0
    true_count = 0
    cutoff_second = 19 * 3600 + 45 * 60

    for s in range(86400):
        current_dt = base_date + timedelta(seconds=s)
        res = is_eod_window(current_dt)
        if s < cutoff_second:
            assert res is False, f"Expected False at second {s} ({current_dt.strftime('%H:%M:%S')} UTC)"
            false_count += 1
        else:
            assert res is True, f"Expected True at second {s} ({current_dt.strftime('%H:%M:%S')} UTC)"
            true_count += 1

    assert false_count == 71100
    assert true_count == 15300
    assert false_count + true_count == 86400


def test_eod_window_full_86400_second_naive_sweep() -> None:
    """Execute exhaustive 86,400-second sweep using naive datetimes (no tzinfo).

    Verifies that naive timestamps assume UTC and produce identical partitioning.
    """
    base_date = datetime(2026, 9, 15, 0, 0, 0)
    false_count = 0
    true_count = 0
    cutoff_second = 19 * 3600 + 45 * 60

    for s in range(86400):
        current_dt = base_date + timedelta(seconds=s)
        res = is_eod_window(current_dt)
        if s < cutoff_second:
            assert res is False
            false_count += 1
        else:
            assert res is True
            true_count += 1

    assert false_count == 71100
    assert true_count == 15300


def test_eod_window_exact_boundary_seconds() -> None:
    """Verify exact boundary seconds with microsecond resolution."""
    assert is_eod_window(datetime(2026, 9, 15, 0, 0, 0, 0, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 0, 0, 0, 1, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 7, 57, 15, 0, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 19, 44, 58, 999999, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 19, 44, 59, 0, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 19, 44, 59, 999999, tzinfo=timezone.utc)) is False
    assert is_eod_window(datetime(2026, 9, 15, 19, 45, 0, 0, tzinfo=timezone.utc)) is True
    assert is_eod_window(datetime(2026, 9, 15, 19, 45, 0, 1, tzinfo=timezone.utc)) is True
    assert is_eod_window(datetime(2026, 9, 15, 23, 59, 59, 0, tzinfo=timezone.utc)) is True
    assert is_eod_window(datetime(2026, 9, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)) is True


@pytest.mark.parametrize(
    "tz_name",
    [
        "America/New_York",
        "Europe/London",
        "Asia/Tokyo",
        "Australia/Adelaide",
        "Asia/Kathmandu",
        "Pacific/Honolulu",
    ],
)
def test_eod_window_full_86400_second_timezone_sweep(tz_name: str) -> None:
    """Execute complete 86,400-second sweep for non-UTC timezone conversions.

    Parameters:
        tz_name: IANA timezone identifier tested.
    """
    target_tz = zoneinfo.ZoneInfo(tz_name)
    base_utc = datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)
    cutoff_second = 19 * 3600 + 45 * 60
    false_count = 0
    true_count = 0

    for s in range(86400):
        utc_moment = base_utc + timedelta(seconds=s)
        localized_moment = utc_moment.astimezone(target_tz)
        res = is_eod_window(localized_moment)
        expected = s >= cutoff_second
        assert res == expected, (
            f"Failed for tz {tz_name} at second {s} "
            f"(UTC: {utc_moment.strftime('%H:%M:%S')}, Local: {localized_moment.strftime('%H:%M:%S %Z')})"
        )
        if res:
            true_count += 1
        else:
            false_count += 1

    assert false_count == 71100
    assert true_count == 15300


@pytest.mark.parametrize(
    "offset_minutes",
    [
        -720,
        -660,
        -300,
        -240,
        0,
        60,
        120,
        210,
        330,
        345,
        540,
        570,
        765,
        840,
    ],
)
def test_eod_window_fixed_offset_timezones(offset_minutes: int) -> None:
    """Verify arbitrary fixed-offset timezones including half-hour and 45-minute offsets.

    Parameters:
        offset_minutes: Minutes offset from UTC.
    """
    tz = timezone(timedelta(minutes=offset_minutes))
    base_utc = datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)
    cutoff_second = 19 * 3600 + 45 * 60

    boundary_offsets = [-3600, -60, -1, 0, 1, 60, 3600]
    for b in boundary_offsets:
        utc_m = base_utc + timedelta(seconds=cutoff_second + b)
        loc_m = utc_m.astimezone(tz)
        expected = b >= 0
        assert is_eod_window(loc_m) == expected


def test_eod_window_dst_transition_resilience() -> None:
    """Verify daylight saving transition dates in US and UK."""
    ny_tz = zoneinfo.ZoneInfo("America/New_York")
    lon_tz = zoneinfo.ZoneInfo("Europe/London")

    dst_days = [
        datetime(2026, 3, 8, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
    ]

    cutoff_second = 19 * 3600 + 45 * 60
    for day in dst_days:
        for tz in [ny_tz, lon_tz]:
            before_cutoff = (day + timedelta(seconds=cutoff_second - 1)).astimezone(tz)
            at_cutoff = (day + timedelta(seconds=cutoff_second)).astimezone(tz)
            after_cutoff = (day + timedelta(seconds=cutoff_second + 1)).astimezone(tz)

            assert is_eod_window(before_cutoff) is False
            assert is_eod_window(at_cutoff) is True
            assert is_eod_window(after_cutoff) is True


@pytest.mark.asyncio
async def test_omni_cancel_pending_orders_multi_order_type_isolation() -> None:
    """Verify omni cancel_pending_orders isolates cancellation across diverse MT5 order types."""
    mock_wrapper = MagicMock()
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")
    mock_wrapper.cancel_order = AsyncMock()
    mock_conn = MagicMock()

    orders_dataset: List[Dict[str, Any]] = [
        {"id": "ord_omni_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "POD_ORB_L1"},
        {"id": "ord_omni_sl", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_LIMIT", "comment": "POD_ORB_L2"},
        {"id": "ord_omni_bs", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "POD_ORB_S1"},
        {"id": "ord_omni_ss", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "POD_ORB_S2"},
        {"id": "ord_omni_bsl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP_LIMIT", "comment": "POD_ORB_BSL"},
        {"id": "ord_omni_ssl", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP_LIMIT", "comment": "POD_ORB_SSL"},
        {"id": "ord_omni_cid", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "clientId": "POD_ORB_TR1"},
        {"id": "ord_lndn_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "LNDN_HYBR_BL"},
        {"id": "ord_lndn_sl", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_LIMIT", "comment": "LNDN_HYBR_SL"},
        {"id": "ord_lndn_bs", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "LNDN_HYBR_BS"},
        {"id": "ord_lndn_ss", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "LNDN_HYBR_SS"},
        {"id": "ord_manual_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "MANUAL_LIMIT"},
        {"id": "ord_manual_ss", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "DISCRETIONARY"},
        {"id": "ord_omni_other_sym", "symbol": "EURUSD", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "POD_ORB_L1"},
    ]

    mock_conn.get_orders = AsyncMock(return_value=orders_dataset)
    mock_wrapper.connection = mock_conn

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        await omni_engine.cancel_pending_orders("US100.cash", client_prefix="POD_ORB")

        expected_canceled = [
            "ord_omni_bl",
            "ord_omni_sl",
            "ord_omni_bs",
            "ord_omni_ss",
            "ord_omni_bsl",
            "ord_omni_ssl",
            "ord_omni_cid",
        ]
        actual_canceled = [call.args[0] for call in mock_wrapper.cancel_order.call_args_list]

        assert actual_canceled == expected_canceled
        assert mock_wrapper.cancel_order.call_count == len(expected_canceled)


@pytest.mark.asyncio
async def test_london_cancel_pending_orders_multi_order_type_isolation() -> None:
    """Verify london cancel_pending_orders isolates cancellation across diverse MT5 order types."""
    mock_wrapper = MagicMock()
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")
    mock_wrapper.cancel_order = AsyncMock()

    orders_dataset: List[Dict[str, Any]] = [
        {"id": "ord_omni_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "POD_ORB_L1"},
        {"id": "ord_omni_sl", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_LIMIT", "comment": "POD_ORB_L2"},
        {"id": "ord_omni_bs", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "POD_ORB_S1"},
        {"id": "ord_omni_ss", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "POD_ORB_S2"},
        {"id": "ord_lndn_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "LNDN_HYBR_BL"},
        {"id": "ord_lndn_sl", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_LIMIT", "comment": "LNDN_HYBR_SL"},
        {"id": "ord_lndn_bs", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "LNDN_HYBR_BS"},
        {"id": "ord_lndn_ss", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "LNDN_HYBR_SS"},
        {"id": "ord_lndn_bsl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP_LIMIT", "comment": "LNDN_HYBR_BSL"},
        {"id": "ord_lndn_cid", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_LIMIT", "clientId": "LNDN_HYBR_L1"},
        {"id": "ord_manual_bl", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "MANUAL_LIMIT"},
        {"id": "ord_lndn_other_sym", "symbol": "GER40.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "LNDN_HYBR_BL"},
    ]

    mock_wrapper.get_orders_rest = AsyncMock(return_value=orders_dataset)

    with patch.object(london_engine, "meta_api_wrapper", mock_wrapper):
        await london_engine.cancel_pending_orders("US100.cash", client_prefix="LNDN_HYBR")

        expected_canceled = [
            "ord_lndn_bl",
            "ord_lndn_sl",
            "ord_lndn_bs",
            "ord_lndn_ss",
            "ord_lndn_bsl",
            "ord_lndn_cid",
        ]
        actual_canceled = [call.args[0] for call in mock_wrapper.cancel_order.call_args_list]

        assert actual_canceled == expected_canceled
        assert mock_wrapper.cancel_order.call_count == len(expected_canceled)


@pytest.mark.asyncio
async def test_cancel_pending_orders_resilience_and_fallbacks() -> None:
    """Verify cancel_pending_orders handles REST fallback, timeouts, and individual cancellation failures."""
    mock_wrapper = MagicMock()
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")
    mock_wrapper.cancel_order = AsyncMock(side_effect=[Exception("Broker network drop"), None])

    mock_conn = MagicMock()
    mock_conn.get_orders = AsyncMock(side_effect=Exception("WebSocket closed"))
    mock_wrapper.connection = mock_conn

    fallback_orders = [
        {"id": "ord_fail", "symbol": "US100.cash", "comment": "POD_ORB_1"},
        {"id": "ord_succeed", "symbol": "US100.cash", "comment": "POD_ORB_2"},
    ]
    mock_wrapper.get_orders_rest = AsyncMock(return_value=fallback_orders)

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        await omni_engine.cancel_pending_orders("US100.cash", client_prefix="POD_ORB")

        assert mock_wrapper.get_orders_rest.call_count == 1
        assert mock_wrapper.cancel_order.call_count == 2
