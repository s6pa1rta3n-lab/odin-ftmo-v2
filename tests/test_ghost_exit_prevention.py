"""Unit tests for state isolation and ghost exit prevention across trading engines."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

import london_reversal_engine_live as london_engine
import omni_breakout_engine as omni_engine
from omni_breakout_engine import BreakoutState, is_eod_window


def test_is_eod_window_all_24_hours():
    """Verify is_eod_window accurately restricts liquidation to >= 19:45 UTC."""
    for hour in range(24):
        for minute in [0, 15, 30, 44, 45, 59]:
            utc_dt = datetime(2026, 9, 15, hour, minute, 0, tzinfo=timezone.utc)
            result = is_eod_window(utc_dt)
            if hour >= 20 or (hour == 19 and minute >= 45):
                assert result is True, f"Expected True for {hour:02d}:{minute:02d} UTC"
            else:
                assert result is False, f"Expected False for {hour:02d}:{minute:02d} UTC"


def test_is_eod_window_specific_ghost_exit_timestamp():
    """Verify 07:57:15 UTC evaluates to False and never triggers liquidation."""
    ghost_time = datetime(2026, 9, 15, 7, 57, 15, tzinfo=timezone.utc)
    assert is_eod_window(ghost_time) is False


def test_omni_position_sync_isolation():
    """Verify Omni position sync ignores London Reversal positions."""
    state = BreakoutState("POD_ORB_")
    mt5_sym = "US100.cash"
    foreign_positions = [
        {
            "id": "292583560",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 11.87,
            "comment": "LNDN_HYBR_MKT",
            "clientId": "LNDN_HYBR_MKT",
        },
        {
            "id": "292583561",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 5.0,
            "comment": "MANUAL_TRADE",
            "clientId": "MANUAL",
        },
    ]

    actual_lots = 0.0
    actual_side = 0
    for p in foreign_positions:
        p_cid = str(p.get("comment", p.get("clientId", "")))
        if p.get("symbol") == mt5_sym and state.client_id in p_cid:
            vol = float(p.get("volume", 0.0))
            side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
            actual_lots += vol
            actual_side = side

    state.side = actual_side if actual_lots > 0 else 0
    state.lots = actual_lots

    assert state.lots == 0.0
    assert state.side == 0

    own_positions = [
        {
            "id": "292583570",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 2.5,
            "comment": "POD_ORB_MKT",
            "clientId": "POD_ORB_MKT",
        }
    ]

    for p in own_positions:
        p_cid = str(p.get("comment", p.get("clientId", "")))
        if p.get("symbol") == mt5_sym and state.client_id in p_cid:
            vol = float(p.get("volume", 0.0))
            side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
            actual_lots += vol
            actual_side = side

    state.side = actual_side if actual_lots > 0 else 0
    state.lots = actual_lots

    assert state.lots == 2.5
    assert state.side == 1


@pytest.mark.asyncio
async def test_omni_flatten_all_positions_isolation():
    """Verify Omni flatten_all_positions closes only Omni positions and preserves others."""
    mock_wrapper = MagicMock()
    mock_conn = MagicMock()
    mock_conn.close_position = AsyncMock()

    mock_positions = [
        {
            "id": "pos_london_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 11.87,
            "comment": "LNDN_HYBR_MKT",
        },
        {
            "id": "pos_omni_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 3.0,
            "comment": "POD_ORB_TRANCHE_1",
        },
        {
            "id": "pos_manual_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_SELL",
            "volume": 1.0,
            "comment": "DISCRETIONARY",
        },
    ]
    mock_conn.get_positions = AsyncMock(return_value=mock_positions)
    mock_wrapper.connection = mock_conn

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        success = await omni_engine.flatten_all_positions("POD_ORB", reason="TEST_EOD")
        assert success is True

        mock_conn.close_position.assert_called_once_with("pos_omni_1")


@pytest.mark.asyncio
async def test_london_flatten_all_positions_isolation():
    """Verify London Reversal flatten_all_positions closes only London positions."""
    mock_wrapper = MagicMock()
    mock_wrapper.route_order = AsyncMock(return_value={"status": "FILLED"})

    mock_positions = [
        {
            "id": "pos_london_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 11.87,
            "comment": "LNDN_HYBR_MKT",
            "clientId": "LNDN_HYBR_MKT",
        },
        {
            "id": "pos_omni_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 3.0,
            "comment": "POD_ORB_TRANCHE_1",
            "clientId": "POD_ORB_TRANCHE_1",
        },
    ]
    mock_wrapper.get_positions_rest = AsyncMock(return_value=mock_positions)

    with patch.object(london_engine, "meta_api_wrapper", mock_wrapper):
        await london_engine.flatten_all_positions("LNDN_HYBR", reason="TEST_FLATTEN")

        assert mock_wrapper.route_order.call_count == 1
        call_payload = mock_wrapper.route_order.call_args[0][0]
        assert call_payload["symbol"] == "US100.cash"
        assert call_payload["side"] == "SELL"
        assert call_payload["quantity"] == "11.87"


@pytest.mark.asyncio
async def test_omni_cancel_pending_orders_isolation():
    """Verify cancel_pending_orders only cancels orders matching client_prefix."""
    mock_wrapper = MagicMock()
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")
    mock_wrapper.cancel_order = AsyncMock()
    mock_conn = MagicMock()

    mock_orders = [
        {"id": "ord_omni_1", "symbol": "US100.cash", "comment": "POD_ORB_STOP"},
        {"id": "ord_london_1", "symbol": "US100.cash", "comment": "LNDN_HYBR_LIMIT"},
        {"id": "ord_other_1", "symbol": "US100.cash", "comment": "MANUAL_LIMIT"},
    ]
    mock_conn.get_orders = AsyncMock(return_value=mock_orders)
    mock_wrapper.connection = mock_conn

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        await omni_engine.cancel_pending_orders("US100.cash", client_prefix="POD_ORB")
        mock_wrapper.cancel_order.assert_called_once_with("ord_omni_1")


@pytest.mark.asyncio
async def test_london_cancel_pending_orders_isolation():
    """Verify london cancel_pending_orders only cancels orders matching client_prefix."""
    mock_wrapper = MagicMock()
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")
    mock_wrapper.cancel_order = AsyncMock()

    mock_orders = [
        {"id": "ord_omni_1", "symbol": "US100.cash", "comment": "POD_ORB_STOP"},
        {"id": "ord_london_1", "symbol": "US100.cash", "comment": "LNDN_HYBR_LIMIT"},
    ]
    mock_wrapper.get_orders_rest = AsyncMock(return_value=mock_orders)

    with patch.object(london_engine, "meta_api_wrapper", mock_wrapper):
        await london_engine.cancel_pending_orders("US100.cash", client_prefix="LNDN_HYBR")
        mock_wrapper.cancel_order.assert_called_once_with("ord_london_1")
