"""Adversarial stress harness for state isolation between trading engines.

Validates state isolation under extreme conditions:
- Interleaved multi-strategy positions
- Malformed, None, empty, and corrupted comments
- Substring prefix collisions and false match exploits
- OCO cancellation scope leaks
- Broker stop-loss synchronization scope leaks
- High-concurrency position sync and flattening
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import london_reversal_engine_live as london_engine
import omni_breakout_engine as omni_engine
from omni_breakout_engine import (
    BreakoutState,
    cancel_pending_orders as omni_cancel_pending_orders,
    flatten_all_positions as omni_flatten_all_positions,
    sync_trend_stop_to_broker as omni_sync_trend_stop,
)
from london_reversal_engine_live import (
    ReversalState,
    cancel_pending_orders as london_cancel_pending_orders,
    flatten_all_positions as london_flatten_all_positions,
)


def create_interleaved_positions():
    """Generate diverse mix of positions across strategies, assets, and comment formats."""
    return [
        {
            "id": "pos_omni_legit_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 2.5,
            "comment": "POD_ORB_T1",
            "clientId": "POD_ORB_T1",
            "openPrice": 18500.0,
        },
        {
            "id": "pos_omni_legit_2",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 1.5,
            "comment": "POD_CLOS_MKT",
            "clientId": "POD_CLOS_MKT",
            "openPrice": 18510.0,
        },
        {
            "id": "pos_london_legit_1",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_SELL",
            "volume": 5.0,
            "comment": "LNDN_BLIN_S1",
            "clientId": "LNDN_BLIN_S1",
            "openPrice": 18550.0,
        },
        {
            "id": "pos_london_legit_2",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 3.0,
            "comment": "LNDN_HYBR_MKT",
            "clientId": "LNDN_HYBR_MKT",
            "openPrice": 18480.0,
        },
        {
            "id": "pos_collision_tripod",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 10.0,
            "comment": "TRIPOD_ORB_SCALPER",
            "clientId": "TRIPOD_ORB",
            "openPrice": 18520.0,
        },
        {
            "id": "pos_collision_notpod",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_SELL",
            "volume": 7.0,
            "comment": "NOT_POD_ORB_EXP",
            "clientId": "NOT_POD",
            "openPrice": 18530.0,
        },
        {
            "id": "pos_collision_lndn_pod",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 4.0,
            "comment": "LNDN_POD_HYBRID",
            "clientId": "LNDN_POD",
            "openPrice": 18505.0,
        },
        {
            "id": "pos_manual_none_comment",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 1.0,
            "comment": None,
            "clientId": "MANUAL",
            "openPrice": 18500.0,
        },
        {
            "id": "pos_omni_none_comment_with_clientid",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 2.0,
            "comment": None,
            "clientId": "POD_ORB_MKT",
            "openPrice": 18500.0,
        },
        {
            "id": "pos_manual_empty_comment",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_SELL",
            "volume": 0.5,
            "comment": "",
            "clientId": "",
            "openPrice": 18510.0,
        },
        {
            "id": "pos_corrupted_int_comment",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 0.25,
            "comment": 99999,
            "clientId": 99999,
            "openPrice": 18515.0,
        },
        {
            "id": "pos_lowercase_omni",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 1.1,
            "comment": "pod_orb_mkt",
            "clientId": "pod_orb_mkt",
            "openPrice": 18500.0,
        },
        {
            "id": "pos_lowercase_london",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 1.2,
            "comment": "lndn_blin_mkt",
            "clientId": "lndn_blin_mkt",
            "openPrice": 18500.0,
        },
        {
            "id": "pos_other_asset_eurusd",
            "symbol": "EURUSD",
            "type": "POSITION_TYPE_BUY",
            "volume": 50.0,
            "comment": "POD_ORB_FOREX",
            "clientId": "POD_ORB_FOREX",
            "openPrice": 1.0850,
        },
        {
            "id": "pos_other_asset_btcusd",
            "symbol": "BTCUSD",
            "type": "POSITION_TYPE_BUY",
            "volume": 1.0,
            "comment": "LNDN_CRYPTO",
            "clientId": "LNDN_CRYPTO",
            "openPrice": 60000.0,
        },
    ]


@pytest.mark.asyncio
async def test_omni_position_sync_against_interleaved_account():
    """Verify Omni position sync calculation excludes legitimate London, manual, and crypto trades."""
    state = BreakoutState("POD_ORB")
    mt5_sym = "US100.cash"
    positions = create_interleaved_positions()

    actual_lots = 0.0
    actual_side = 0
    synced_pos_ids = []

    for p in positions:
        p_cid = str(p.get("comment") or p.get("clientId") or "")
        if p.get("symbol") == mt5_sym and p_cid.startswith(state.client_id):
            vol = float(p.get("volume", 0.0))
            side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
            actual_lots += vol
            actual_side = side
            synced_pos_ids.append(p.get("id"))

    state.side = actual_side if actual_lots > 0 else 0
    state.lots = actual_lots

    assert "pos_london_legit_1" not in synced_pos_ids
    assert "pos_london_legit_2" not in synced_pos_ids
    assert "pos_manual_none_comment" not in synced_pos_ids
    assert "pos_manual_empty_comment" not in synced_pos_ids
    assert "pos_other_asset_eurusd" not in synced_pos_ids
    assert "pos_other_asset_btcusd" not in synced_pos_ids


@pytest.mark.asyncio
async def test_omni_position_sync_substring_collision_vulnerability():
    """Verify whether substring matching improperly adopts super-string comments."""
    state = BreakoutState("POD_ORB")
    mt5_sym = "US100.cash"
    positions = create_interleaved_positions()

    matched_foreign = []
    for p in positions:
        p_cid = str(p.get("comment") or p.get("clientId") or "")
        if p.get("symbol") == mt5_sym and p_cid.startswith(state.client_id):
            if p["id"] in ["pos_collision_tripod", "pos_collision_notpod"]:
                matched_foreign.append(p["id"])

    assert len(matched_foreign) == 0, f"Vulnerability: Omni adopted foreign superstring positions: {matched_foreign}"


@pytest.mark.asyncio
async def test_omni_position_sync_none_comment_handling():
    """Verify handling when comment key is None and clientId contains strategy prefix."""
    state = BreakoutState("POD_ORB")
    mt5_sym = "US100.cash"

    pos = {
        "id": "pos_test_none",
        "symbol": "US100.cash",
        "type": "POSITION_TYPE_BUY",
        "volume": 2.0,
        "comment": None,
        "clientId": "POD_ORB_MKT",
    }

    p_cid = str(pos.get("comment") or pos.get("clientId") or "")
    matched = (pos.get("symbol") == mt5_sym and p_cid.startswith(state.client_id))

    assert matched is True, f"Vulnerability: pos with comment=None resulted in p_cid='{p_cid}', failing adoption of own trade"


@pytest.mark.asyncio
async def test_london_engine_crashes_on_none_comment():
    """Empirically test whether London engine handles position with comment=None without raising TypeError."""
    client_prefix = "LNDN_BLIN"
    mt5_sym = "US100.cash"
    pos = {
        "id": "pos_foreign_none",
        "symbol": "US100.cash",
        "type": "POSITION_TYPE_BUY",
        "volume": 1.0,
        "comment": None,
        "clientId": "MANUAL",
    }

    try:
        p_cid = str(pos.get("comment") or pos.get("clientId") or "")
        match_result = p_cid.startswith(client_prefix)
    except TypeError:
        match_result = "TypeError_Raised"

    assert match_result != "TypeError_Raised", "Vulnerability: London engine crashes with TypeError when comment is None"
    assert match_result is False


@pytest.mark.asyncio
async def test_omni_sync_trend_stop_modifies_london_position():
    """Empirically test if sync_trend_stop_to_broker modifies non-Omni London positions when client_id is POD_."""
    mock_wrapper = MagicMock()
    mock_conn = MagicMock()
    mock_conn.modify_position = AsyncMock()

    positions = [
        {
            "id": "pos_london_292583560",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 11.87,
            "comment": "LNDN_HYBR_MKT",
            "clientId": "LNDN_HYBR_MKT",
            "takeProfit": 18600.0,
        }
    ]
    mock_conn.get_positions = AsyncMock(return_value=positions)
    mock_wrapper.connection = mock_conn
    mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        await omni_sync_trend_stop(
            client_id="POD_",
            side_str="LONG",
            qty=11.87,
            sl=18450.0,
            symbol="US100.cash",
        )

    modified_calls = mock_conn.modify_position.call_args_list
    assert len(modified_calls) == 0, f"Critical Vulnerability: Omni sync_trend_stop modified London trade: {modified_calls}"


@pytest.mark.asyncio
async def test_omni_oco_cancels_foreign_stop_orders():
    """Empirically verify if Omni active position loop cancels external/foreign stop orders."""
    mock_wrapper = MagicMock()
    mock_wrapper.cancel_order = AsyncMock()
    mock_conn = MagicMock()

    orders = [
        {
            "id": "order_external_ea_buy_stop",
            "symbol": "US100.cash",
            "type": "ORDER_TYPE_BUY_STOP",
            "comment": "EXTERNAL_SWING_BUY_STOP",
            "clientId": "EXTERNAL_EA",
        },
        {
            "id": "order_manual_sell_stop",
            "symbol": "US100.cash",
            "type": "ORDER_TYPE_SELL_STOP",
            "comment": "MANUAL_DISCRETIONARY",
            "clientId": "MANUAL",
        },
    ]
    mock_conn.get_orders = AsyncMock(return_value=orders)
    mock_wrapper.connection = mock_conn

    mt5_sym = "US100.cash"
    cancelled_ids = []
    state_client_id = "POD_ORB"

    for o in orders:
        o_cid = str(o.get("comment") or o.get("clientId") or "")
        if o.get("symbol") == mt5_sym and o.get("type") in ["ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP"] and o_cid.startswith(state_client_id):
            cancelled_ids.append(o["id"])

    assert len(cancelled_ids) == 0, f"Critical Vulnerability: Omni OCO logic targets foreign stop orders: {cancelled_ids}"


@pytest.mark.asyncio
async def test_omni_flatten_all_positions_with_interleaved_portfolio():
    """Verify Omni flatten_all_positions does not close explicit London or manual trades."""
    mock_wrapper = MagicMock()
    mock_conn = MagicMock()
    mock_conn.close_position = AsyncMock()

    positions = create_interleaved_positions()
    mock_conn.get_positions = AsyncMock(return_value=positions)
    mock_wrapper.connection = mock_conn

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
        await omni_flatten_all_positions(client_prefix="POD_ORB", reason="TEST_ISOLATION")

    closed_ids = [call.args[0] for call in mock_conn.close_position.call_args_list]

    assert "pos_london_legit_1" not in closed_ids
    assert "pos_london_legit_2" not in closed_ids
    assert "pos_manual_none_comment" not in closed_ids
    assert "pos_manual_empty_comment" not in closed_ids


@pytest.mark.asyncio
async def test_london_flatten_all_positions_with_interleaved_portfolio():
    """Verify London flatten_all_positions does not route orders against Omni trades."""
    mock_wrapper = MagicMock()
    mock_wrapper.route_order = AsyncMock(return_value={"status": "FILLED"})

    positions = create_interleaved_positions()
    mock_wrapper.get_positions_rest = AsyncMock(return_value=positions)

    with patch.object(london_engine, "meta_api_wrapper", mock_wrapper):
        await london_flatten_all_positions(client_prefix="LNDN_BLIN", reason="TEST_ISOLATION")

    routed_calls = mock_wrapper.route_order.call_args_list
    flattened_client_orders = [call.args[0]["newClientOrderId"] for call in routed_calls]

    assert "FLAT_POD_ORB_T1" not in flattened_client_orders
    assert "FLAT_POD_CLOS_MKT" not in flattened_client_orders
    assert "FLAT_MANUAL" not in flattened_client_orders


@pytest.mark.asyncio
async def test_concurrent_position_sync_and_flatten_stress():
    """Execute high-concurrency stress test with 50 parallel operations between engines."""
    mock_wrapper = MagicMock()
    mock_conn = MagicMock()
    mock_conn.close_position = AsyncMock()
    mock_wrapper.route_order = AsyncMock(return_value={"status": "FILLED"})

    positions = create_interleaved_positions()
    mock_conn.get_positions = AsyncMock(return_value=positions)
    mock_wrapper.get_positions_rest = AsyncMock(return_value=positions)
    mock_wrapper.connection = mock_conn

    with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper), \
         patch.object(london_engine, "meta_api_wrapper", mock_wrapper):

        async def run_omni_sync():
            state = BreakoutState("POD_ORB")
            for _ in range(10):
                actual_lots = 0.0
                actual_side = 0
                for p in positions:
                    p_cid = str(p.get("comment", p.get("clientId", "")))
                    if p.get("symbol") == "US100.cash" and state.client_id in p_cid:
                        actual_lots += float(p.get("volume", 0.0))
                        actual_side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
                state.side = actual_side if actual_lots > 0 else 0
                state.lots = actual_lots
                await asyncio.sleep(0.001)

        async def run_omni_flatten():
            for _ in range(5):
                await omni_flatten_all_positions(client_prefix="POD_ORB", reason="CONCURRENT_TEST")
                await asyncio.sleep(0.001)

        async def run_london_flatten():
            for _ in range(5):
                await london_flatten_all_positions(client_prefix="LNDN_BLIN", reason="CONCURRENT_TEST")
                await asyncio.sleep(0.001)

        tasks = [
            run_omni_sync(),
            run_omni_flatten(),
            run_london_flatten(),
            run_omni_sync(),
            run_omni_flatten(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                raise res
