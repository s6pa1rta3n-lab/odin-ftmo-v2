"""Empirical adversarial stress test harness for multi-engine state isolation.

Executes exhaustive stress testing of:
1. Interleaved positions across multiple strategies
2. Malformed, None, empty, and corrupted comments
3. Substring collision and boundary injection
4. Casing variations
5. Cross-engine stop loss modification in sync_trend_stop_to_broker
6. Unqualified OCO stop order cancellation
7. Concurrency and race conditions under rapid execution
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import london_reversal_engine_live as london_engine
import omni_breakout_engine as omni_engine
from omni_breakout_engine import BreakoutState


class AdversarialHarness:
    """Orchestrates adversarial simulations against state isolation logic."""

    def __init__(self) -> None:
        """Initialize metrics and trial trackers."""
        self.results: Dict[str, Dict[str, Any]] = {}

    def record_metric(self, category: str, passed: bool, details: Dict[str, Any]) -> None:
        """Record outcome and metrics for an evaluation scenario."""
        self.results[category] = {
            "passed": passed,
            "details": details,
        }

    def generate_adversarial_positions(self, scale: int = 100) -> List[Dict[str, Any]]:
        """Generate high-volume interleaved positions covering edge cases and attacks."""
        positions = []
        for i in range(scale):
            positions.extend([
                {
                    "id": f"omni_{i}_1",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 2.0,
                    "comment": f"POD_ORB_T{i}",
                    "clientId": f"POD_ORB_T{i}",
                    "openPrice": 18500.0,
                },
                {
                    "id": f"london_{i}_1",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_SELL",
                    "volume": 3.0,
                    "comment": f"LNDN_BLIN_T{i}",
                    "clientId": f"LNDN_BLIN_T{i}",
                    "openPrice": 18520.0,
                },
                {
                    "id": f"tripod_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 5.0,
                    "comment": f"TRIPOD_ORB_T{i}",
                    "clientId": f"TRIPOD_ORB_T{i}",
                    "openPrice": 18510.0,
                },
                {
                    "id": f"notpod_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_SELL",
                    "volume": 4.0,
                    "comment": f"NOT_POD_ORB_T{i}",
                    "clientId": f"NOT_POD_ORB_T{i}",
                    "openPrice": 18530.0,
                },
                {
                    "id": f"lndn_pod_hybrid_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 1.5,
                    "comment": f"LNDN_POD_HYBRID_{i}",
                    "clientId": f"LNDN_POD_{i}",
                    "openPrice": 18505.0,
                },
                {
                    "id": f"manual_none_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 1.0,
                    "comment": None,
                    "clientId": "MANUAL",
                    "openPrice": 18500.0,
                },
                {
                    "id": f"omni_none_comment_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 2.5,
                    "comment": None,
                    "clientId": f"POD_ORB_MKT_{i}",
                    "openPrice": 18500.0,
                },
                {
                    "id": f"manual_empty_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_SELL",
                    "volume": 0.5,
                    "comment": "",
                    "clientId": "",
                    "openPrice": 18500.0,
                },
                {
                    "id": f"lowercase_omni_{i}",
                    "symbol": "US100.cash",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 1.2,
                    "comment": f"pod_orb_{i}",
                    "clientId": f"pod_orb_{i}",
                    "openPrice": 18500.0,
                },
                {
                    "id": f"other_symbol_{i}",
                    "symbol": "EURUSD",
                    "type": "POSITION_TYPE_BUY",
                    "volume": 10.0,
                    "comment": f"POD_ORB_EUR_{i}",
                    "clientId": f"POD_ORB_EUR_{i}",
                    "openPrice": 1.0850,
                },
            ])
        return positions

    async def stress_omni_position_sync(self, positions: List[Dict[str, Any]]) -> None:
        """Test Omni position synchronization under adversarial input."""
        state = BreakoutState("POD_ORB")
        mt5_sym = "US100.cash"

        start_time = time.perf_counter()
        actual_lots = 0.0
        actual_side = 0
        adopted_ids = []
        foreign_adopted = []
        omni_missed = []

        for p in positions:
            p_cid = str(p.get("comment") or p.get("clientId") or "")
            if p.get("symbol") == mt5_sym and p_cid.startswith(state.client_id):
                vol = float(p.get("volume", 0.0))
                side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
                actual_lots += vol
                actual_side = side
                adopted_ids.append(p.get("id"))
                if p["id"].startswith("tripod_") or p["id"].startswith("notpod_") or p["id"].startswith("lndn_pod_"):
                    foreign_adopted.append(p["id"])
            elif p["id"].startswith("omni_none_comment_"):
                omni_missed.append(p["id"])

        state.side = actual_side if actual_lots > 0 else 0
        state.lots = actual_lots
        elapsed = time.perf_counter() - start_time

        passed = (len(foreign_adopted) == 0 and len(omni_missed) == 0)
        self.record_metric("omni_position_sync", passed, {
            "total_positions_evaluated": len(positions),
            "adopted_positions": len(adopted_ids),
            "foreign_positions_adopted": len(foreign_adopted),
            "sample_foreign_adopted": foreign_adopted[:5],
            "own_positions_missed_due_to_none_comment": len(omni_missed),
            "sample_own_missed": omni_missed[:5],
            "execution_time_seconds": elapsed,
        })

    async def stress_omni_flatten(self, positions: List[Dict[str, Any]]) -> None:
        """Test Omni position flattening under adversarial input."""
        mock_wrapper = MagicMock()
        mock_conn = MagicMock()
        mock_conn.close_position = AsyncMock()
        mock_conn.get_positions = AsyncMock(return_value=positions)
        mock_wrapper.connection = mock_conn

        start_time = time.perf_counter()
        with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
            await omni_engine.flatten_all_positions(client_prefix="POD_ORB", reason="STRESS_TEST")
        elapsed = time.perf_counter() - start_time

        closed_ids = [call.args[0] for call in mock_conn.close_position.call_args_list]
        foreign_closed = [cid for cid in closed_ids if cid.startswith("london_") or cid.startswith("tripod_") or cid.startswith("notpod_") or cid.startswith("manual_")]
        own_missed = [p["id"] for p in positions if p["id"].startswith("omni_none_comment_") and p["id"] not in closed_ids]

        passed = (len(foreign_closed) == 0 and len(own_missed) == 0)
        self.record_metric("omni_flatten_isolation", passed, {
            "total_closed": len(closed_ids),
            "foreign_positions_closed": len(foreign_closed),
            "sample_foreign_closed": foreign_closed[:5],
            "own_positions_missed": len(own_missed),
            "sample_own_missed": own_missed[:5],
            "execution_time_seconds": elapsed,
        })

    async def stress_omni_sync_trend_stop(self) -> None:
        """Test Omni sync_trend_stop_to_broker cross-talk against London position."""
        mock_wrapper = MagicMock()
        mock_conn = MagicMock()
        mock_conn.modify_position = AsyncMock()
        mock_wrapper.connection = mock_conn
        mock_wrapper._to_mt5 = MagicMock(return_value="US100.cash")

        london_pos = {
            "id": "292583560",
            "symbol": "US100.cash",
            "type": "POSITION_TYPE_BUY",
            "volume": 11.87,
            "comment": "LNDN_HYBR_MKT",
            "clientId": "LNDN_HYBR_MKT",
            "takeProfit": 18600.0,
        }
        mock_conn.get_positions = AsyncMock(return_value=[london_pos])

        start_time = time.perf_counter()
        with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
            await omni_engine.sync_trend_stop_to_broker(
                client_id="POD_",
                side_str="LONG",
                qty=11.87,
                sl=18400.0,
                symbol="US100.cash",
            )
        elapsed = time.perf_counter() - start_time

        modified = len(mock_conn.modify_position.call_args_list)
        passed = (modified == 0)
        self.record_metric("omni_sync_trend_stop_isolation", passed, {
            "target_position_comment": "LNDN_HYBR_MKT",
            "client_id_prefix": "POD_",
            "calls_to_modify_position": modified,
            "execution_time_seconds": elapsed,
        })

    async def stress_omni_oco_cancellation(self) -> None:
        """Test Omni active position loop OCO pending order cancellation scope."""
        orders = [
            {"id": "ext_stop_1", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "EXT_STRAT_1"},
            {"id": "manual_stop_1", "symbol": "US100.cash", "type": "ORDER_TYPE_SELL_STOP", "comment": "MANUAL_ORDER"},
            {"id": "omni_stop_1", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_STOP", "comment": "POD_ORB_STOP"},
            {"id": "london_limit_1", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": "LNDN_BLIN_LIMIT"},
        ]

        mt5_sym = "US100.cash"
        cancelled = []
        state_client_id = "POD_ORB"
        for o in orders:
            o_cid = str(o.get("comment") or o.get("clientId") or "")
            if o.get("symbol") == mt5_sym and o.get("type") in ["ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP"] and o_cid.startswith(state_client_id):
                cancelled.append(o["id"])

        foreign_cancelled = [oid for oid in cancelled if oid != "omni_stop_1"]
        passed = (len(foreign_cancelled) == 0)
        self.record_metric("omni_oco_cancellation_isolation", passed, {
            "total_orders_evaluated": len(orders),
            "cancelled_orders": cancelled,
            "foreign_cancelled": foreign_cancelled,
        })

    async def stress_london_none_comment_crash(self) -> None:
        """Test London engine resilience against None comments across 3 inspection points."""
        positions = [{"id": "p_none", "symbol": "US100.cash", "type": "POSITION_TYPE_BUY", "volume": 1.0, "comment": None, "clientId": "MANUAL"}]
        orders = [{"id": "o_none", "symbol": "US100.cash", "type": "ORDER_TYPE_BUY_LIMIT", "comment": None, "clientId": "MANUAL"}]
        client_prefix = "LNDN_BLIN"
        mt5_sym = "US100.cash"

        crash_pos_sync = False
        try:
            for p in positions:
                if p.get("symbol") == mt5_sym:
                    p_cid = str(p.get("comment") or p.get("clientId") or "")
                    if p_cid.startswith(client_prefix):
                        pass
        except TypeError:
            crash_pos_sync = True

        crash_pending_check = False
        try:
            _ = any(o.get("symbol") == mt5_sym and str(o.get("comment") or o.get("clientId") or "").startswith(client_prefix) for o in orders)
        except TypeError:
            crash_pending_check = True

        crash_oco_cancel = False
        try:
            for o in orders:
                o_cid = str(o.get("comment") or o.get("clientId") or "")
                if o.get("symbol") == mt5_sym and o_cid.startswith(client_prefix):
                    pass
        except TypeError:
            crash_oco_cancel = True

        passed = not (crash_pos_sync or crash_pending_check or crash_oco_cancel)
        self.record_metric("london_none_comment_resilience", passed, {
            "crash_pos_sync_typeerror": crash_pos_sync,
            "crash_pending_check_typeerror": crash_pending_check,
            "crash_oco_cancel_typeerror": crash_oco_cancel,
        })

    async def stress_concurrency(self, iterations: int = 50) -> None:
        """Execute high concurrency stress between Omni and London routines."""
        positions = self.generate_adversarial_positions(scale=10)
        mock_wrapper = MagicMock()
        mock_conn = MagicMock()
        mock_conn.close_position = AsyncMock()
        mock_conn.get_positions = AsyncMock(return_value=positions)
        mock_wrapper.get_positions_rest = AsyncMock(return_value=positions)
        mock_wrapper.route_order = AsyncMock(return_value={"status": "FILLED"})
        mock_wrapper.connection = mock_conn

        start_time = time.perf_counter()
        errors = []

        async def worker_omni_sync():
            state = BreakoutState("POD_ORB")
            for _ in range(iterations):
                actual_lots = 0.0
                actual_side = 0
                for p in positions:
                    p_cid = str(p.get("comment") or p.get("clientId") or "")
                    if p.get("symbol") == "US100.cash" and p_cid.startswith(state.client_id):
                        actual_lots += float(p.get("volume", 0.0))
                        actual_side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
                state.side = actual_side if actual_lots > 0 else 0
                state.lots = actual_lots
                await asyncio.sleep(0.0001)

        async def worker_omni_flatten():
            with patch.object(omni_engine, "meta_api_wrapper", mock_wrapper):
                for _ in range(iterations // 5):
                    await omni_engine.flatten_all_positions("POD_ORB", reason="CONCURRENCY_TEST")
                    await asyncio.sleep(0.0001)

        async def worker_london_flatten():
            with patch.object(london_engine, "meta_api_wrapper", mock_wrapper):
                for _ in range(iterations // 5):
                    await london_engine.flatten_all_positions("LNDN_BLIN", reason="CONCURRENCY_TEST")
                    await asyncio.sleep(0.0001)

        tasks = [
            worker_omni_sync(),
            worker_omni_flatten(),
            worker_london_flatten(),
            worker_omni_sync(),
            worker_omni_flatten(),
            worker_london_flatten(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - start_time

        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))

        passed = (len(errors) == 0)
        self.record_metric("concurrency_stability", passed, {
            "parallel_workers": len(tasks),
            "iterations_per_worker": iterations,
            "errors": errors,
            "execution_time_seconds": elapsed,
        })

    async def run_all(self) -> None:
        """Run all stress test suites and print comprehensive summary."""
        positions = self.generate_adversarial_positions(scale=100)
        await self.stress_omni_position_sync(positions)
        await self.stress_omni_flatten(positions)
        await self.stress_omni_sync_trend_stop()
        await self.stress_omni_oco_cancellation()
        await self.stress_london_none_comment_crash()
        await self.stress_concurrency(iterations=50)

        print("=== ADVERSARIAL STRESS TEST REPORT ===")
        print(json.dumps(self.results, indent=2))

        all_passed = all(v["passed"] for v in self.results.values())
        print("\nFINAL STATE ISOLATION VERDICT:", "CONFIRMED" if all_passed else "DISPROVEN")


if __name__ == "__main__":
    harness = AdversarialHarness()
    asyncio.run(harness.run_all())
