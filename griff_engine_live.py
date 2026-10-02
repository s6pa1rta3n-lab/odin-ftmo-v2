"""Live trading engine implementing Griff's 1-hour inside-bar ATR breakout strategy.

This engine operates on the 1-hour timeframe using pure price action:
- 1-hour candle ingestion and 14-period ATR calculation on completed 1H bars
- Inside bar detection: (high < prev_high) and (low > prev_low)
- Strict 1% account equity risk position sizing:
    lots = (equity * 0.01) / (1.5 * ATR * tick_value)
- 1.5x ATR initial stop loss and dynamic trailing stop ratcheting on 1H bar close
- Native MetaApiWrapper integration connecting to target FTMO account
- Resilient balance watermark logging without TimeoutException
- CLI entrypoint supporting --run, --test, and --daemon execution modes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from MetaApiWrapper import MetaApiWrapper
except ImportError:
    MetaApiWrapper = None

from metaapi_hub.factory import build_execution_wrapper, engine_name_for_symbol, hub_mode

try:
    from metaapi_cloud_sdk.clients.timeout_exception import TimeoutException
except ImportError:
    class TimeoutException(Exception):
        """Fallback exception when timeout exception cannot be imported."""
        pass


DEFAULT_ACCOUNT_ID = "6ccd891f-8728-4e37-ad41-1e695c6008ef"
DEFAULT_SYMBOL = "US100.cash"
DEFAULT_CONFIG_PATH = "config_us100.json"
GRIFF_ORDER_COMMENT = "GRIFF_1H_BREAKOUT"

# Completed 1H bars required before the engine searches for a new setup.
# EMA-50 and ADX need this much history. Unchanged strategy parameter.
MIN_CANDLES_FOR_SETUP_SCAN = 50
# Completed 1H bars required to manage an already-open position. ATR-14 uses
# the last 14 true ranges (15 bars) and the structural trailing stop uses the
# last 3 bars, so results are identical to the 50-bar case. This only decides
# whether trailing-stop evaluation can run while history is still filling.
MIN_CANDLES_FOR_POSITION_MANAGEMENT = 15
# In-cycle attempts for the candle fetch. Each attempt is bounded; the hub
# single-flights the fetch so a retry joins the in-progress request.
CANDLE_FETCH_ATTEMPTS = 2
CANDLE_FETCH_TIMEOUT_SECONDS = 15.0

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("GriffTradingEngine")


def compute_true_range(high: float, low: float, prev_close: float) -> float:
    """Compute True Range for a single price bar.

    Args:
        high: Current bar high price.
        low: Current bar low price.
        prev_close: Previous bar close price.

    Returns:
        Maximum of (high - low), abs(high - prev_close), abs(low - prev_close).
    """
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def compute_atr_14(candles: List[Dict[str, Any]]) -> float:
    """Calculate 14-period Simple Moving Average of True Range.

    Args:
        candles: Chronologically ordered list of candle dicts with
            'high', 'low', 'close'. Requires at least 15 candles.

    Returns:
        14-period ATR value as a positive float rounded to 4 decimals.

    Raises:
        ValueError: If fewer than 15 candles are provided.
    """
    if len(candles) < 15:
        raise ValueError(f"Need at least 15 candles for 14-period ATR, received {len(candles)}")

    tr_values: List[float] = []
    for i in range(1, len(candles)):
        tr = compute_true_range(
            float(candles[i]["high"]),
            float(candles[i]["low"]),
            float(candles[i - 1]["close"]),
        )
        tr_values.append(tr)

    recent_14_tr = tr_values[-14:]
    return round(sum(recent_14_tr) / 14.0, 4)



def compute_adx(candles, period=14):
    if len(candles) <= period: return [0]*len(candles)
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(candles)):
        c, pc = candles[i], candles[i-1]
        tr = max(float(c['high']) - float(c['low']), abs(float(c['high']) - float(pc['close'])), abs(float(c['low']) - float(pc['close'])))
        up = float(c['high']) - float(pc['high'])
        dn = float(pc['low']) - float(c['low'])
        pos = up if up > dn and up > 0 else 0
        neg = dn if dn > up and dn > 0 else 0
        tr_list.append(tr)
        pdm.append(pos)
        ndm.append(neg)
    
    adx, dx = [0]*len(candles), [0]*len(candles)
    if len(candles) <= period*2: return adx
    
    sm_tr = sum(tr_list[1:period+1])
    sm_pdm = sum(pdm[1:period+1])
    sm_ndm = sum(ndm[1:period+1])
    
    for i in range(period, len(candles)):
        if i > period:
            sm_tr = sm_tr - (sm_tr / period) + tr_list[i]
            sm_pdm = sm_pdm - (sm_pdm / period) + pdm[i]
            sm_ndm = sm_ndm - (sm_ndm / period) + ndm[i]
        
        pdi = 100 * (sm_pdm / sm_tr) if sm_tr > 0 else 0
        ndi = 100 * (sm_ndm / sm_tr) if sm_tr > 0 else 0
        diff = abs(pdi - ndi)
        summ = pdi + ndi
        dx[i] = 100 * (diff / summ) if summ > 0 else 0
        
    adx[period*2 - 1] = sum(dx[period:period*2]) / period
    for i in range(period*2, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx

def compute_ema_50(candles: List[Dict[str, Any]]) -> float:
    """Calculate 50-period Exponential Moving Average."""
    closes = [float(c["close"]) for c in candles[-50:]]
    if not closes:
        return 0.0
    ema = closes[0]
    multiplier = 2 / (50 + 1)
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_structural_trailing_stop(
    direction: str,
    current_sl: float,
    candles: List[Dict[str, Any]],
    current_atr_14: float,
) -> float:
    """Calculate structural trailing stop loss using 1H swing points."""
    if len(candles) < 3:
        return current_sl

    c1 = candles[-1] # latest
    c2 = candles[-2] # previous
    c3 = candles[-3] # older

    # Distance buffer from structural point (tighter than initial, but based on structure)
    distance = 0.5 * current_atr_14

    if direction.upper() in ("BUY", "LONG"):
        if float(c2["low"]) < float(c3["low"]) and float(c1["low"]) > float(c2["low"]):
            candidate_sl = round(float(c2["low"]) - distance, 2)
            return max(current_sl, candidate_sl)
        return current_sl

    if direction.upper() in ("SELL", "SHORT"):
        if float(c2["high"]) > float(c3["high"]) and float(c1["high"]) < float(c2["high"]):
            candidate_sl = round(float(c2["high"]) + distance, 2)
            return min(current_sl, candidate_sl)
        return current_sl

    raise ValueError(f"Invalid direction: {direction}")


def is_inside_bar(current: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    """Determine if current bar is strictly inside previous mother bar.

    Args:
        current: Current candle dict with 'high' and 'low'.
        previous: Previous candle dict with 'high' and 'low'.

    Returns:
        True if current high < previous high AND current low > previous low.
    """
    return (float(current["high"]) < float(previous["high"])) and (
        float(current["low"]) > float(previous["low"])
    )


def coerce_utc_datetime(value: Any) -> Optional[datetime]:
    """Normalize a broker timestamp (datetime or ISO-8601 string) to an aware UTC datetime.

    Returns:
        Aware UTC datetime, or None when the value cannot be interpreted.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def calculate_position_size(
    equity: float,
    atr_14: float,
    tick_value: float = 1.0,
    contract_size: float = 1.0,
    risk_pct: float = 0.01,
    min_lot: float = 0.01,
    max_lot: float = 50.0,
) -> float:
    """Calculate lot size strictly risking 1% of account equity with 1.5x ATR stop loss.

    Formula:
        risk_dollars = equity * risk_pct
        sl_points = 1.5 * atr_14
        lots = risk_dollars / (sl_points * tick_value * contract_size)
        clamped = clamp(round(lots, 2), min_lot, max_lot)

    Args:
        equity: Current account equity in USD.
        atr_14: 14-period ATR in index points.
        tick_value: Value per point per lot (1.0 for US100.cash).
        contract_size: Contract multiplier (1.0 for US100.cash).
        risk_pct: Fractional risk (0.01 for 1%).
        min_lot: Minimum allowable lot size (0.01).
        max_lot: Maximum allowable lot size (50.0).

    Returns:
        Calculated lot size rounded to 2 decimal places and clamped.

    Raises:
        ValueError: If equity <= 0, atr_14 <= 0, or parameters are invalid.
    """
    if equity <= 0:
        raise ValueError(f"Equity must be positive, received {equity}")
    if atr_14 <= 0 or math.isnan(atr_14):
        raise ValueError(f"ATR must be positive and finite, received {atr_14}")
    if tick_value <= 0 or contract_size <= 0:
        raise ValueError("Tick value and contract size must be positive")

    risk_dollars = equity * risk_pct
    sl_points = 1.5 * atr_14
    raw_lots = risk_dollars / (sl_points * tick_value * contract_size)
    rounded_lots = round(raw_lots, 2)
    return max(min(rounded_lots, max_lot), min_lot)


def calculate_initial_stop_loss(direction: str, entry_price: float, atr_14: float) -> float:
    """Calculate initial protective stop loss level.

    Args:
        direction: 'BUY' or 'SELL'.
        entry_price: Executed entry price.
        atr_14: 14-period ATR at time of entry.

    Returns:
        Stop loss price level rounded to 2 decimal places.
    """
    distance = 1.5 * atr_14
    if direction.upper() in ("BUY", "LONG"):
        return round(entry_price - distance, 2)
    if direction.upper() in ("SELL", "SHORT"):
        return round(entry_price + distance, 2)
    raise ValueError(f"Invalid direction: {direction}")


def calculate_trailing_stop(
    direction: str,
    current_sl: float,
    bar_close: float,
    current_atr_14: float,
) -> float:
    """Calculate ratcheted trailing stop loss based on latest bar close.

    Rules:
        Long: candidate_sl = bar_close - (1.5 * current_atr_14); ratchets UP only.
        Short: candidate_sl = bar_close + (1.5 * current_atr_14); ratchets DOWN only.

    Args:
        direction: 'BUY' or 'SELL'.
        current_sl: Active stop loss level.
        bar_close: Close price of completed bar.
        current_atr_14: Latest 14-period ATR.

    Returns:
        Updated stop loss level (never loosened).
    """
    distance = 1.5 * current_atr_14
    if direction.upper() in ("BUY", "LONG"):
        candidate_sl = round(bar_close - distance, 2)
        return max(current_sl, candidate_sl)
    if direction.upper() in ("SELL", "SHORT"):
        candidate_sl = round(bar_close + distance, 2)
        return min(current_sl, candidate_sl)
    raise ValueError(f"Invalid direction: {direction}")


class GriffSimulationEngine:
    """State machine simulation harness for Griff 1H Inside Bar ATR Breakout."""

    def __init__(
        self,
        starting_equity: float = 100000.0,
        day_start_equity: float = 100000.0,
        hard_floor: float = 90000.0,
        max_daily_loss_pct: float = 0.05,
    ) -> None:
        """Initialize simulator with FTMO constraints."""
        self.equity = starting_equity
        self.day_start_equity = day_start_equity
        self.hard_floor = hard_floor
        self.max_daily_loss_pct = max_daily_loss_pct
        self.state = "SEARCHING"
        self.active_position: Optional[Dict[str, Any]] = None
        self.pending_orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.halted = False

    def check_risk_limits(self) -> bool:
        """Verify equity preserves FTMO daily loss limit and hard floor.

        Returns:
            True if trading is allowed; False if halted.
        """
        if self.equity <= self.hard_floor:
            self.halted = True
            return False
        daily_loss = (self.day_start_equity - self.equity) / self.day_start_equity
        if daily_loss >= self.max_daily_loss_pct:
            self.halted = True
            return False
        return True

    def process_completed_bar(
        self,
        current_bar: Dict[str, float],
        mother_bar: Optional[Dict[str, float]],
        atr_14: float,
    ) -> Dict[str, Any]:
        """Evaluate completed bar for setups, breakout fills, trailing stops, or exits."""
        if not self.check_risk_limits():
            self.state = "HALTED"
            return {"action": "HALTED", "reason": "Risk limit reached"}

        if self.state == "SEARCHING":
            if mother_bar is not None and is_inside_bar(current_bar, mother_bar):
                lots = calculate_position_size(self.equity, atr_14)
                buy_stop = {
                    "type": "STOP_BUY",
                    "price": current_bar["high"],
                    "sl": calculate_initial_stop_loss("BUY", current_bar["high"], atr_14),
                    "volume": lots,
                }
                sell_stop = {
                    "type": "STOP_SELL",
                    "price": current_bar["low"],
                    "sl": calculate_initial_stop_loss("SELL", current_bar["low"], atr_14),
                    "volume": lots,
                }
                self.pending_orders = [buy_stop, sell_stop]
                self.state = "PENDING_PLACED"
                return {
                    "action": "PENDING_PLACED",
                    "orders": self.pending_orders,
                    "inside_bar": current_bar,
                }
            return {"action": "NO_SETUP"}

        if self.state == "PENDING_PLACED":
            buy_order = next((o for o in self.pending_orders if o["type"] == "STOP_BUY"), None)
            sell_order = next((o for o in self.pending_orders if o["type"] == "STOP_SELL"), None)

            if buy_order and current_bar["high"] >= buy_order["price"]:
                self.active_position = {
                    "direction": "BUY",
                    "entry_price": buy_order["price"],
                    "sl": buy_order["sl"],
                    "volume": buy_order["volume"],
                    "atr_entry": atr_14,
                }
                self.pending_orders.clear()
                self.state = "IN_TRADE"
                return {"action": "FILLED_BUY", "position": self.active_position}

            if sell_order and current_bar["low"] <= sell_order["price"]:
                self.active_position = {
                    "direction": "SELL",
                    "entry_price": sell_order["price"],
                    "sl": sell_order["sl"],
                    "volume": sell_order["volume"],
                    "atr_entry": atr_14,
                }
                self.pending_orders.clear()
                self.state = "IN_TRADE"
                return {"action": "FILLED_SELL", "position": self.active_position}

            self.pending_orders.clear()
            self.state = "SEARCHING"
            return {"action": "EXPIRED_PENDING_ORDERS"}

        if self.state == "IN_TRADE" and self.active_position:
            direction = self.active_position["direction"]
            sl = self.active_position["sl"]
            volume = self.active_position["volume"]
            entry = self.active_position["entry_price"]

            if direction == "BUY" and current_bar["low"] <= sl:
                pnl = round((sl - entry) * volume, 2)
                self.equity = round(self.equity + pnl, 2)
                trade_record = {
                    "direction": "BUY",
                    "entry": entry,
                    "exit": sl,
                    "volume": volume,
                    "pnl": pnl,
                }
                self.trade_history.append(trade_record)
                self.active_position = None
                self.state = "SEARCHING"
                return {"action": "STOP_EXIT", "record": trade_record}

            if direction == "SELL" and current_bar["high"] >= sl:
                pnl = round((entry - sl) * volume, 2)
                self.equity = round(self.equity + pnl, 2)
                trade_record = {
                    "direction": "SELL",
                    "entry": entry,
                    "exit": sl,
                    "volume": volume,
                    "pnl": pnl,
                }
                self.trade_history.append(trade_record)
                self.active_position = None
                self.state = "SEARCHING"
                return {"action": "STOP_EXIT", "record": trade_record}

            new_sl = calculate_trailing_stop(direction, sl, current_bar["close"], atr_14)
            self.active_position["sl"] = new_sl
            return {"action": "TRAILED", "new_sl": new_sl}

        return {"action": "NOOP"}


class GriffLiveEngine:
    """Production live execution engine for Griff's 1H Inside Bar Breakout Strategy."""

    def __init__(
        self,
        token: str,
        account_id: str = DEFAULT_ACCOUNT_ID,
        symbol: str = DEFAULT_SYMBOL,
        risk_pct: float = 0.01,
        contract_size: float = 1.0,
        tick_value: float = 1.0,
        hard_floor: float = 90000.0,
        max_daily_loss_pct: float = 0.05,
        order_comment: str = GRIFF_ORDER_COMMENT,
    ) -> None:
        """Initialize live engine configuration and state attributes."""
        self.token = token
        self.account_id = account_id
        self.symbol = symbol
        if self.symbol == "US100.cash":
            self.risk_pct = 0.0065
        elif self.symbol == "BTCUSD":
            self.risk_pct = 0.0080
        else:
            self.risk_pct = risk_pct
        self.contract_size = contract_size
        self.tick_value = tick_value
        self.hard_floor = hard_floor
        self.max_daily_loss_pct = max_daily_loss_pct
        self.order_comment = order_comment

        self.wrapper: Optional[Any] = None
        self.account_info: Dict[str, Any] = {}
        self.starting_balance: float = 100000.0
        self.current_equity: float = 100000.0
        self.day_start_equity: float = 100000.0

        self.state: str = "SEARCHING"
        self.active_position: Optional[Dict[str, Any]] = None
        self.pending_buy_order_id: Optional[str] = None
        self.pending_sell_order_id: Optional[str] = None
        self.pending_setup_bar_time: Optional[datetime] = None
        self.last_evaluated_bar_time: Optional[datetime] = None

        # Resilience counters. Consecutive failures reset on the next success.
        self.candle_fetch_failures: int = 0
        self.position_sync_failures: int = 0
        self.last_candle_count: int = 0

        # Order ids whose cancel was requested but the broker has not yet
        # confirmed removal (order id -> number of cancel attempts). An id stays
        # here, and in its pending_*_order_id slot, until the order book no
        # longer lists it. Not persisted: on restart the broker book is re-read
        # by reconcile_griff_pending_orders() and tracking is rebuilt from it.
        self.unconfirmed_cancel_order_ids: Dict[str, int] = {}
        self.pending_orders_reconciled: bool = False
        self.cycle_count: int = 0
        self._last_cancel_attempt_cycle: int = -1

        self.is_running: bool = False
        self.halted: bool = False

    async def connect_account(self) -> bool:
        """Establish connection to MetaAPI and verify account credentials.

        Returns:
            True if connection and balance validation succeed; False otherwise.
        """
        if hub_mode() == "off" and MetaApiWrapper is None:
            logger.error("MetaApiWrapper module not available")
            return False

        logger.info(
            "Initializing execution wrapper for account %s (hub_mode=%s)",
            self.account_id,
            hub_mode(),
        )
        try:
            # Default hub_mode is off, which keeps constructing MetaApiWrapper.
            self.wrapper = build_execution_wrapper(
                self.token,
                self.account_id,
                engine_name=engine_name_for_symbol(self.symbol),
            )
        except Exception as err:
            logger.error("Failed to build execution wrapper: %s", err)
            return False

        try:
            await self.wrapper.connect()
        except TimeoutException as err:
            logger.warning("MetaApi TimeoutException during connect: %s. Operating in REST fallback.", err)
        except Exception as err:
            logger.warning("MetaApi connection warning: %s. Proceeding with REST interface.", err)

        info = await self.fetch_account_information_safe()
        if not info:
            logger.error("Failed to retrieve account information from MetaAPI")
            return False

        self.account_info = info
        self.starting_balance = float(info.get("balance", 100000.0))
        self.current_equity = float(info.get("equity", self.starting_balance))
        self.day_start_equity = self.current_equity

        logger.info(
            "FTMO Account Connected | Name: %s | Server: %s | Login: %s | Balance: $%.2f | Equity: $%.2f | Free Margin: $%.2f",
            info.get("name", "FTMO Demo"),
            info.get("server", "FTMO-Demo"),
            info.get("login", "N/A"),
            self.starting_balance,
            self.current_equity,
            float(info.get("freeMargin", self.current_equity)),
        )
        return True

    async def fetch_account_information_safe(self) -> Dict[str, Any]:
        """Fetch account information with timeout protection and REST fallback.

        Returns:
            Dictionary containing account metrics.
        """
        if not self.wrapper:
            return {}

        info: Dict[str, Any] = {}
        try:
            info = await asyncio.wait_for(self.wrapper.get_account_information(), timeout=12.0)
        except (TimeoutException, asyncio.TimeoutError) as err:
            logger.warning("Primary get_account_information timed out: %s. Invoking REST fallback.", err)
            try:
                info = await self.wrapper.get_account_information_rest()
            except Exception as rest_err:
                logger.error("REST fallback account info error: %s", rest_err)
        except Exception as err:
            logger.warning("Account info lookup error: %s. Invoking REST fallback.", err)
            try:
                info = await self.wrapper.get_account_information_rest()
            except Exception as rest_err:
                logger.error("Secondary REST fallback error: %s", rest_err)

        return info

    async def fetch_positions_safe(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch active positions with dual streaming and REST fallback.

        Returns:
            List of position dictionaries, or ``None`` when every lookup
            failed. ``None`` is deliberately distinct from ``[]``: a failed
            read must never be interpreted as "the book is flat".
        """
        if not self.wrapper:
            return None

        positions: Optional[List[Dict[str, Any]]] = None
        try:
            positions = await asyncio.wait_for(self.wrapper.get_positions(), timeout=10.0)
        except (TimeoutException, asyncio.TimeoutError) as err:
            logger.warning("Position lookup timed out: %s. Invoking REST fallback.", err)
            try:
                positions = await self.wrapper.get_positions_rest()
            except Exception as rest_err:
                logger.error("REST position lookup error: %s", rest_err)
        except Exception as err:
            logger.warning("Position lookup error: %s. Invoking REST fallback.", err)
            try:
                positions = await self.wrapper.get_positions_rest()
            except Exception as rest_err:
                logger.error("Secondary REST position lookup error: %s", rest_err)

        if positions is None:
            return None
        return list(positions)

    async def fetch_completed_1h_candles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve historical 1H candles and filter to completed hourly bars.

        Makes up to ``CANDLE_FETCH_ATTEMPTS`` bounded attempts per call with a
        short jittered pause between them. On the hub path a retry joins the
        fetch the hub already has in flight, so the second attempt usually
        returns what the first one ran out of time waiting for. Failure
        returns ``[]`` and increments ``candle_fetch_failures``; the caller
        decides what that means for the current state.

        Args:
            limit: Maximum number of recent candles to retrieve.

        Returns:
            List of completed candle dictionaries sorted chronologically.
        """
        if not self.wrapper or not hasattr(self.wrapper, "account") or not self.wrapper.account:
            return []

        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol
        raw_candles: Optional[List[Dict[str, Any]]] = None
        last_error: Optional[str] = None

        for attempt in range(1, CANDLE_FETCH_ATTEMPTS + 1):
            try:
                raw_candles = await asyncio.wait_for(
                    self.wrapper.account.get_historical_candles(mt5_sym, "1h"),
                    timeout=CANDLE_FETCH_TIMEOUT_SECONDS,
                )
                break
            except (TimeoutException, asyncio.TimeoutError) as err:
                last_error = f"timed out after {CANDLE_FETCH_TIMEOUT_SECONDS:.0f}s ({err or 'no detail'})"
            except Exception as err:
                last_error = f"{type(err).__name__}: {err}"
            if attempt < CANDLE_FETCH_ATTEMPTS:
                pause = 1.0 + random.random()
                logger.warning(
                    "Historical candle fetch attempt %d/%d failed: %s. Retrying in %.1fs.",
                    attempt,
                    CANDLE_FETCH_ATTEMPTS,
                    last_error,
                    pause,
                )
                await asyncio.sleep(pause)

        if raw_candles is None:
            self.candle_fetch_failures += 1
            logger.warning(
                "Historical candle fetch failed on all %d attempts (%s). Consecutive failures: %d. "
                "State=%s. The engine keeps polling; no broker action is taken because of this.",
                CANDLE_FETCH_ATTEMPTS,
                last_error,
                self.candle_fetch_failures,
                self.state,
            )
            return []

        if self.candle_fetch_failures:
            logger.info(
                "Historical candle fetch recovered after %d consecutive failures.",
                self.candle_fetch_failures,
            )
        self.candle_fetch_failures = 0

        if not raw_candles:
            return []

        now_utc = datetime.now(timezone.utc)
        current_hour_floor = now_utc.replace(minute=0, second=0, microsecond=0)

        completed: List[Dict[str, Any]] = []
        for c in raw_candles:
            c_time = c.get("time")
            if isinstance(c_time, datetime):
                if c_time.tzinfo is None:
                    c_time = c_time.replace(tzinfo=timezone.utc)
                if c_time < current_hour_floor:
                    completed.append(c)
            elif isinstance(c_time, str):
                try:
                    dt = datetime.fromisoformat(c_time.replace("Z", "+00:00"))
                    if dt < current_hour_floor:
                        completed.append(c)
                except ValueError:
                    completed.append(c)
            else:
                completed.append(c)

        completed.sort(key=lambda x: x["time"])
        return completed[-limit:]

    def check_risk_limits(self, equity: float) -> bool:
        """Verify account equity respects FTMO drawdown floor and daily loss limit.

        Args:
            equity: Active mark-to-market equity.

        Returns:
            True if trading permitted; False if halted.
        """
        if equity <= self.hard_floor:
            logger.critical("Hard equity floor reached: $%.2f <= $%.2f. Halting engine.", equity, self.hard_floor)
            self.halted = True
            self.state = "HALTED"
            return False

        daily_loss_pct = (self.day_start_equity - equity) / self.day_start_equity
        if daily_loss_pct >= self.max_daily_loss_pct:
            logger.critical(
                "Daily loss limit breach: %.2f%% >= %.2f%%. Halting engine.",
                daily_loss_pct * 100.0,
                self.max_daily_loss_pct * 100.0,
            )
            self.halted = True
            self.state = "HALTED"
            return False

        return True

    def _mt5_symbol(self) -> str:
        """Return the broker-side symbol name for this engine's symbol."""
        if self.wrapper is not None and hasattr(self.wrapper, "_to_mt5"):
            return self.wrapper._to_mt5(self.symbol)
        return self.symbol

    def _tracked_pending_order_ids(self) -> List[str]:
        """Return the order ids currently tracked as this engine's breakout legs."""
        return [str(oid) for oid in (self.pending_buy_order_id, self.pending_sell_order_id) if oid]

    def has_unfinished_pending_cancels(self) -> bool:
        """True while any GRIFF pending order still needs a cancel or a cancel confirmation."""
        return bool(self.unconfirmed_cancel_order_ids)

    def _can_verify_order_book(self) -> bool:
        """True when the wrapper exposes an order-book read usable for cancel confirmation."""
        return self.wrapper is not None and hasattr(self.wrapper, "get_orders_rest")

    async def fetch_griff_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        """Read the broker order book and return GRIFF_ pending orders on this symbol.

        Returns:
            List of order dicts (possibly empty) when the book was read
            successfully; None when the book could not be read. None must never
            be treated as "no orders": it means the broker state is unknown.
        """
        if not self._can_verify_order_book():
            return None
        try:
            orders = await self.wrapper.get_orders_rest()
        except Exception as err:
            logger.warning("Order book read failed: %s", err)
            return None
        if orders is None:
            return None

        mt5_sym = self._mt5_symbol()
        griff_orders: List[Dict[str, Any]] = []
        for o in orders:
            cid = str(o.get("comment", "") or o.get("clientId", ""))
            if o.get("symbol") == mt5_sym and cid.startswith("GRIFF_"):
                griff_orders.append(o)
        return griff_orders

    @staticmethod
    def _cancel_request_error(result: Any) -> Optional[str]:
        """Extract an error message from a cancel_order result, or None if it was accepted.

        MetaApiWrapper.cancel_order swallows broker exceptions and returns
        ``{"status": "REJECTED", "msg": ...}``; that return value was previously
        discarded, which is why "Market is closed" never reached the state machine.
        """
        if isinstance(result, dict):
            status = str(result.get("status", "")).upper()
            if status in ("REJECTED", "ERROR", "BROKER_ERROR", "FAILED"):
                return str(result.get("msg") or result.get("message") or status)
        return None

    def _mark_order_gone(self, order_id: str) -> None:
        """Drop an order id from every tracking structure once the broker no longer lists it."""
        self.unconfirmed_cancel_order_ids.pop(order_id, None)
        if self.pending_buy_order_id is not None and str(self.pending_buy_order_id) == order_id:
            self.pending_buy_order_id = None
        if self.pending_sell_order_id is not None and str(self.pending_sell_order_id) == order_id:
            self.pending_sell_order_id = None

    async def cancel_orders_until_confirmed(self, order_ids: List[str]) -> bool:
        """Request cancellation of the given GRIFF order ids and confirm against the order book.

        Retry rule: an order id is forgotten only when the broker order book no
        longer lists it. A rejected or failed cancel request (for example
        ``BROKER_ERROR Market is closed``), an exception, or an unreadable order
        book all keep the id tracked in ``unconfirmed_cancel_order_ids`` (and in
        its ``pending_*_order_id`` slot) so the next cycle retries. A cancel
        error on an order the book no longer lists (already filled or deleted
        manually) counts as confirmation that it is gone.

        Args:
            order_ids: Order ids to cancel. Duplicates are ignored.

        Returns:
            True only if every requested id is confirmed absent from the broker.
        """
        ids = list(dict.fromkeys(str(oid) for oid in order_ids if oid))
        if not ids:
            return True
        self._last_cancel_attempt_cycle = self.cycle_count

        if not self.wrapper or not hasattr(self.wrapper, "cancel_order"):
            for oid in ids:
                self.unconfirmed_cancel_order_ids.setdefault(oid, 0)
            logger.error("Cannot cancel GRIFF pending orders %s: broker wrapper unavailable. Keeping them tracked.", ids)
            return False

        request_errors: Dict[str, Optional[str]] = {}
        for oid in ids:
            attempt = self.unconfirmed_cancel_order_ids.get(oid, 0) + 1
            logger.info("Canceling pending breakout order %s (attempt %d)", oid, attempt)
            try:
                result = await self.wrapper.cancel_order(oid)
                request_errors[oid] = self._cancel_request_error(result)
            except Exception as err:
                request_errors[oid] = str(err)
            if request_errors[oid]:
                logger.warning("Cancel request for order %s failed: %s", oid, request_errors[oid])

        remaining = await self.fetch_griff_pending_orders()
        if remaining is None:
            if not self._can_verify_order_book():
                # No order book available at all: the cancel response is the
                # only evidence there is, so an accepted request is treated as confirmed.
                for oid in ids:
                    if request_errors.get(oid) is None:
                        self._mark_order_gone(oid)
                    else:
                        self.unconfirmed_cancel_order_ids[oid] = self.unconfirmed_cancel_order_ids.get(oid, 0) + 1
                return not any(oid in self.unconfirmed_cancel_order_ids for oid in ids)

            for oid in ids:
                self.unconfirmed_cancel_order_ids[oid] = self.unconfirmed_cancel_order_ids.get(oid, 0) + 1
            logger.warning(
                "Order book unavailable; cannot confirm cancellation of %s. Keeping tracked for retry.", ids
            )
            return False

        remaining_ids = {str(o.get("id")) for o in remaining}
        all_confirmed = True
        for oid in ids:
            if oid in remaining_ids:
                all_confirmed = False
                self.unconfirmed_cancel_order_ids[oid] = self.unconfirmed_cancel_order_ids.get(oid, 0) + 1
                logger.warning(
                    "Broker still lists GRIFF pending order %s after cancel attempt %d (%s). "
                    "Keeping it tracked; will retry next cycle.",
                    oid,
                    self.unconfirmed_cancel_order_ids[oid],
                    request_errors.get(oid) or "request accepted but order still working",
                )
            else:
                if request_errors.get(oid):
                    logger.info("Order %s is no longer on the broker book; treating failed cancel as already gone.", oid)
                else:
                    logger.info("Broker confirmed pending order %s is gone.", oid)
                self._mark_order_gone(oid)
        return all_confirmed

    async def cancel_pending_breakout_orders(self) -> bool:
        """Cancel this engine's pending breakout legs and any stray GRIFF_ pending on the symbol.

        Covers the tracked Buy Stop / Sell Stop ids, every id whose earlier
        cancel is still unconfirmed, and any other GRIFF_ pending order the
        broker lists for this symbol. Nothing is forgotten until the broker
        order book confirms it is gone (see cancel_orders_until_confirmed).

        Returns:
            True only when the broker confirms no tracked or stray GRIFF pending remains.
        """
        order_ids = self._tracked_pending_order_ids() + list(self.unconfirmed_cancel_order_ids)

        book = await self.fetch_griff_pending_orders()
        if book is not None:
            known = set(order_ids)
            for o in book:
                oid = str(o.get("id"))
                if oid not in known:
                    logger.info("Canceling stray Griff pending order %s", oid)
                    order_ids.append(oid)

        if not order_ids:
            return True
        return await self.cancel_orders_until_confirmed(order_ids)

    async def retry_unconfirmed_cancels(self) -> bool:
        """Re-attempt cancels whose removal the broker has not confirmed yet."""
        if not self.unconfirmed_cancel_order_ids:
            return True
        return await self.cancel_orders_until_confirmed(list(self.unconfirmed_cancel_order_ids))

    async def reconcile_griff_pending_orders(self) -> bool:
        """Restart/reconcile path: account for every GRIFF_ pending order on this symbol.

        A fresh process starts with no tracked ids, so without this step a
        pending order left by the previous process (for example one whose
        cancel failed with "Market is closed") would keep working at the broker
        with nobody tracking it. Each untracked GRIFF_ pending is classified by
        the hour it was placed:

        - Placed in the current UTC hour: its setup window (the completed bar
          before placement) is still live, so it is re-adopted into the
          matching pending_*_order_id slot and the state machine resumes
          PENDING_PLACED exactly as if the process had never restarted. Normal
          window expiry then cancels it on the next completed bar.
        - Placed in an earlier hour, with an unparseable time, with an unknown
          type, or when its slot is already taken: its window has expired. It is
          cancelled through cancel_orders_until_confirmed and stays tracked in
          unconfirmed_cancel_order_ids until the broker confirms it is gone.

        Returns:
            True once the order book was read and classified (even if some
            cancels are still unconfirmed); False if the book could not be read,
            in which case the next cycle retries the whole reconcile.
        """
        book = await self.fetch_griff_pending_orders()
        if book is None:
            logger.warning("Pending order reconcile deferred: broker order book unavailable.")
            return False

        tracked = set(self._tracked_pending_order_ids())
        now_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        expired_ids: List[str] = []

        for o in book:
            oid = str(o.get("id"))
            if oid in tracked or oid in self.unconfirmed_cancel_order_ids:
                continue

            placed_at = coerce_utc_datetime(o.get("time"))
            placed_hour = placed_at.replace(minute=0, second=0, microsecond=0) if placed_at else None
            order_type = str(o.get("type", ""))
            slot = "buy" if order_type == "ORDER_TYPE_BUY_STOP" else "sell" if order_type == "ORDER_TYPE_SELL_STOP" else None
            slot_free = (slot == "buy" and not self.pending_buy_order_id) or (
                slot == "sell" and not self.pending_sell_order_id
            )

            if placed_hour == now_hour and slot_free and self.state in ("SEARCHING", "PENDING_PLACED"):
                if slot == "buy":
                    self.pending_buy_order_id = oid
                else:
                    self.pending_sell_order_id = oid
                self.pending_setup_bar_time = placed_hour - timedelta(hours=1)
                self.state = "PENDING_PLACED"
                logger.info(
                    "Re-adopted live GRIFF pending %s order %s placed %s (setup bar %s).",
                    order_type,
                    oid,
                    placed_at.isoformat(),
                    self.pending_setup_bar_time.isoformat(),
                )
            else:
                logger.warning(
                    "Found GRIFF pending order %s (%s, placed %s) outside its setup window with no tracking. Canceling.",
                    oid,
                    order_type or "unknown type",
                    placed_at.isoformat() if placed_at else "unknown time",
                )
                expired_ids.append(oid)

        if expired_ids:
            confirmed = await self.cancel_orders_until_confirmed(expired_ids)
            if not confirmed and self.state == "SEARCHING":
                self.state = "CANCEL_PENDING"
        return True

    async def place_pending_breakout_orders(
        self,
        inside_bar: Dict[str, Any],
        atr_14: float,
        equity: float,
        trend_direction: str = "BOTH",
    ) -> bool:
        """Place Buy Stop at inside bar high and Sell Stop at inside bar low.

        Args:
            inside_bar: Inside bar candle dictionary.
            atr_14: 14-period ATR calculated from completed candles.
            equity: Current mark-to-market account equity.

        Returns:
            True if orders were submitted; False otherwise.
        """
        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol
        
        dynamic_contract_size = self.contract_size
        try:
            if hasattr(self.wrapper, "connection") and self.wrapper.connection:
                spec = await self.wrapper.connection.get_symbol_specification(mt5_sym)
                dynamic_contract_size = float(spec.get("contractSize", self.contract_size))
        except Exception as err:
            logger.warning("Could not fetch symbol specs, using default contract_size: %s", err)

        lots = calculate_position_size(
            equity=equity,
            atr_14=atr_14,
            tick_value=self.tick_value,
            contract_size=dynamic_contract_size,
            risk_pct=self.risk_pct,
        )

        buy_price = round(float(inside_bar["high"]), 2)
        buy_sl = calculate_initial_stop_loss("BUY", buy_price, atr_14)

        sell_price = round(float(inside_bar["low"]), 2)
        sell_sl = calculate_initial_stop_loss("SELL", sell_price, atr_14)

        try:
            if hasattr(self.wrapper, "connection") and self.wrapper.connection:
                account_info = await self.wrapper.get_account_information()
                free_margin = account_info.get("freeMargin", equity)
                
                margin_calc = await self.wrapper.connection.calculate_margin({
                    "symbol": mt5_sym,
                    "type": "ORDER_TYPE_BUY",
                    "volume": 1.0,
                    "openPrice": buy_price
                })
                margin_per_lot = margin_calc.get("margin", 0.0)
                
                if margin_per_lot > 0:
                    max_affordable_lots = (free_margin * 0.90) / margin_per_lot
                    if lots > max_affordable_lots:
                        old_lots = lots
                        lots = max(round(max_affordable_lots, 2), 0.01)
                        logger.warning(
                            "Margin constraint applied: calculated %.2f lots exceeds 90%% of free margin ($%.2f). Capped to %.2f lots.",
                            old_lots, free_margin, lots
                        )
        except Exception as err:
            logger.warning("Failed to calculate margin constraints, falling back to pure risk sizing: %s", err)

        logger.info(
            "Inside Bar Detected | High: %.2f | Low: %.2f | ATR_14: %.2f | Sizing: %.2f lots ($%.2f risk)",
            buy_price,
            sell_price,
            atr_14,
            lots,
            equity * self.risk_pct,
        )

        buy_order_id = None
        sell_order_id = None

        try:
            if hasattr(self.wrapper, "connection") and self.wrapper.connection:
                opts = {"comment": self.order_comment}
                
                if trend_direction in ("BUY", "BOTH"):
                    res_buy = await self.wrapper.connection.create_stop_buy_order(
                        mt5_sym,
                        lots,
                        buy_price,
                        stop_loss=buy_sl,
                        options=opts,
                    )
                    buy_order_id = res_buy.get("orderId") or res_buy.get("id")
                    logger.info("Buy Stop submitted at %.2f with SL %.2f (Order ID: %s)", buy_price, buy_sl, buy_order_id)

                if trend_direction in ("SELL", "BOTH"):
                    res_sell = await self.wrapper.connection.create_stop_sell_order(
                        mt5_sym,
                        lots,
                        sell_price,
                        stop_loss=sell_sl,
                        options=opts,
                    )
                    sell_order_id = res_sell.get("orderId") or res_sell.get("id")
                    logger.info("Sell Stop submitted at %.2f with SL %.2f (Order ID: %s)", sell_price, sell_sl, sell_order_id)
        except Exception as err:
            logger.error("Failed to place pending stop orders: %s", err)
            return False

        self.pending_buy_order_id = buy_order_id
        self.pending_sell_order_id = sell_order_id
        self.pending_orders = []
        if buy_order_id:
            self.pending_orders.append({"id": buy_order_id, "type": "STOP_BUY", "price": buy_price, "sl": buy_sl, "volume": lots})
        if sell_order_id:
            self.pending_orders.append({"id": sell_order_id, "type": "STOP_SELL", "price": sell_price, "sl": sell_sl, "volume": lots})
        self.pending_orders = []
        if buy_order_id:
            self.pending_orders.append({"id": buy_order_id, "type": "STOP_BUY", "price": buy_price, "sl": buy_sl, "volume": lots})
        if sell_order_id:
            self.pending_orders.append({"id": sell_order_id, "type": "STOP_SELL", "price": sell_price, "sl": sell_sl, "volume": lots})
        self.pending_setup_bar_time = inside_bar.get("time")
        self.state = "PENDING_PLACED"
        return True

    async def synchronize_active_positions(self) -> None:
        """Synchronize local state with active broker positions and pending orders.

        This is also the restart path: a fresh process starts in SEARCHING,
        sees the GRIFF_ position the previous process opened, and adopts its
        ticket, direction, volume, and current broker stop loss. Nothing is
        closed, cancelled, or modified to make that adoption happen. The only
        broker call it can issue is the strategy's own cancel of the unfilled
        opposite breakout leg (pending orders only, never positions).

        A failed position read keeps the current state. ``None`` from the
        lookup is not "flat"; treating it as flat is how a phantom
        "closed on broker" transition would strand an open ticket.
        """
        positions = await self.fetch_positions_safe()
        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol

        if positions is None:
            self.position_sync_failures += 1
            if self.state == "IN_TRADE" and self.active_position:
                logger.warning(
                    "Position lookup failed (consecutive: %d). Keeping IN_TRADE for ticket %s "
                    "(%s %.2f lots, SL %.2f). Not treating the book as flat; no broker action taken.",
                    self.position_sync_failures,
                    self.active_position.get("id"),
                    self.active_position.get("direction"),
                    float(self.active_position.get("volume", 0.0)),
                    float(self.active_position.get("sl", 0.0)),
                )
            else:
                logger.warning(
                    "Position lookup failed (consecutive: %d). State %s unchanged until a read succeeds.",
                    self.position_sync_failures,
                    self.state,
                )
            return

        if self.position_sync_failures:
            logger.info("Position lookup recovered after %d consecutive failures.", self.position_sync_failures)
        self.position_sync_failures = 0

        griff_positions = [
            p for p in positions
            if p.get("symbol") == mt5_sym and str(p.get("comment", "")).startswith("GRIFF_")
        ]

        if griff_positions:
            active = griff_positions[0]
            direction = "BUY" if active.get("type") == "POSITION_TYPE_BUY" else "SELL"
            self.active_position = {
                "id": active.get("id"),
                "direction": direction,
                "entry_price": float(active.get("openPrice", 0.0)),
                "volume": float(active.get("volume", 0.0)),
                "sl": float(active.get("stopLoss", 0.0)),
            }
            if self.state != "IN_TRADE":
                logger.info(
                    "Position Detected: %s %.2f lots on %s at %.2f (SL: %.2f, Ticket: %s). "
                    "Adopting it as-is; the position is not touched.",
                    direction,
                    self.active_position["volume"],
                    self.symbol,
                    self.active_position["entry_price"],
                    self.active_position["sl"],
                    self.active_position["id"],
                )
                self.state = "IN_TRADE"
                await self.cancel_pending_breakout_orders()
            self.pending_orders_reconciled = True
        else:
            if self.state == "IN_TRADE":
                logger.info("Active trade closed on broker (confirmed by a successful position read). Returning state to SEARCHING.")
                self.active_position = None
                self.state = "SEARCHING"
            if not self.pending_orders_reconciled:
                self.pending_orders_reconciled = await self.reconcile_griff_pending_orders()

    async def ratchet_trailing_stop(self, candles: List[Dict[str, Any]], atr_14: float) -> None:
        """Evaluate structural trailing stop ratchet upon 1H bar close.

        Args:
            candles: List of historical completed candles.
            atr_14: Current 14-period ATR.
        """
        if not self.active_position or not self.wrapper or not hasattr(self.wrapper, "connection"):
            return

        direction = self.active_position["direction"]
        current_sl = float(self.active_position.get("sl", 0.0))
        ticket_id = self.active_position.get("id")

        if not ticket_id:
            return

        candidate_sl = calculate_structural_trailing_stop(direction, current_sl, candles, atr_14)

        if candidate_sl != current_sl:
            logger.info(
                "Ratcheting Structural Trailing Stop for ticket %s (%s) from %.2f to %.2f (ATR: %.2f)",
                ticket_id,
                direction,
                current_sl,
                candidate_sl,
                atr_14,
            )
            try:
                await asyncio.wait_for(
                    self.wrapper.connection.modify_position(ticket_id, stop_loss=candidate_sl),
                    timeout=8.0,
                )
                self.active_position["sl"] = candidate_sl
            except Exception as err:
                logger.error("Failed to update trailing stop on ticket %s: %s", ticket_id, err)

    async def step(self) -> Dict[str, Any]:
        """Execute a single strategy evaluation cycle.

        Returns:
            Dictionary containing cycle summary and executed actions.
        """
        self.cycle_count += 1
        info = await self.fetch_account_information_safe()
        if info:
            self.current_equity = float(info.get("equity", self.current_equity))

        if not self.check_risk_limits(self.current_equity):
            return {"status": "HALTED", "reason": "Risk limit breach"}

        await self.synchronize_active_positions()

        if self.state == "SEARCHING" and self.has_unfinished_pending_cancels():
            # A GRIFF pending whose cancel is unconfirmed is still working at the
            # broker; do not search for a new setup on top of it.
            self.state = "CANCEL_PENDING"

        needs_cancel_retry = self.has_unfinished_pending_cancels() or (
            self.state == "CANCEL_PENDING" and bool(self._tracked_pending_order_ids())
        )
        if needs_cancel_retry and self._last_cancel_attempt_cycle != self.cycle_count:
            # One cancel attempt per cycle. synchronize_active_positions may
            # already have attempted this cycle (position adoption / reconcile).
            if self.state == "CANCEL_PENDING":
                await self.cancel_pending_breakout_orders()
            else:
                # IN_TRADE (unfilled opposite leg) or PENDING_PLACED (orphans
                # found at restart): retry without disturbing the current state.
                await self.retry_unconfirmed_cancels()

        if self.state == "CANCEL_PENDING":
            if self.has_unfinished_pending_cancels() or self._tracked_pending_order_ids():
                return {
                    "status": "CANCEL_PENDING",
                    "unconfirmed_cancel_order_ids": dict(self.unconfirmed_cancel_order_ids),
                }
            logger.info("Broker confirmed all GRIFF pending orders are gone. Returning state to SEARCHING.")
            self.state = "SEARCHING"

        candles = await self.fetch_completed_1h_candles(limit=60)
        self.last_candle_count = len(candles)

        # Open-position management comes before the setup-scan history gate.
        # The position was already re-synchronized above; the only thing
        # candles add here is the trailing-stop ratchet, which needs 15 bars.
        # Incomplete history never closes, cancels, or modifies the position.
        if self.state == "IN_TRADE" and self.active_position:
            if len(candles) < MIN_CANDLES_FOR_POSITION_MANAGEMENT:
                logger.warning(
                    "History incomplete (%d/%d bars). Holding IN_TRADE for ticket %s (%s %.2f lots, SL %.2f); "
                    "trailing-stop evaluation deferred until %d completed 1H bars are available. "
                    "Position stays untouched.",
                    len(candles),
                    MIN_CANDLES_FOR_SETUP_SCAN,
                    self.active_position.get("id"),
                    self.active_position.get("direction"),
                    float(self.active_position.get("volume", 0.0)),
                    float(self.active_position.get("sl", 0.0)),
                    MIN_CANDLES_FOR_POSITION_MANAGEMENT,
                )
                return {
                    "status": "IN_TRADE",
                    "position": self.active_position,
                    "atr_14": None,
                    "history_count": len(candles),
                }
            atr_14 = compute_atr_14(candles)
            latest_bar_time = candles[-1].get("time")
            if len(candles) < MIN_CANDLES_FOR_SETUP_SCAN:
                logger.info(
                    "History %d/%d bars while IN_TRADE: managing ticket %s with ATR_14 %.2f; setup scan resumes at %d bars.",
                    len(candles),
                    MIN_CANDLES_FOR_SETUP_SCAN,
                    self.active_position.get("id"),
                    atr_14,
                    MIN_CANDLES_FOR_SETUP_SCAN,
                )
            if self.last_evaluated_bar_time != latest_bar_time:
                await self.ratchet_trailing_stop(candles, atr_14)
                self.last_evaluated_bar_time = latest_bar_time
            return {
                "status": "IN_TRADE",
                "position": self.active_position,
                "atr_14": atr_14,
                "history_count": len(candles),
            }

        if len(candles) < MIN_CANDLES_FOR_SETUP_SCAN:
            logger.info(
                "Accumulating history: %d/%d required completed 1H candles (state=%s, consecutive fetch failures=%d)",
                len(candles),
                MIN_CANDLES_FOR_SETUP_SCAN,
                self.state,
                self.candle_fetch_failures,
            )
            return {"status": "ACCUMULATING_HISTORY", "count": len(candles)}

        atr_14 = compute_atr_14(candles)
        ema_50 = compute_ema_50(candles)
        latest_completed_bar = candles[-1]
        latest_bar_time = latest_completed_bar.get("time")

        if self.state == "PENDING_PLACED":
            if self.pending_setup_bar_time and latest_bar_time != self.pending_setup_bar_time:
                logger.info("Breakout window for setup bar %s expired unfilled. Canceling pending orders.", self.pending_setup_bar_time)
                self.state = "CANCEL_PENDING"
                if await self.cancel_pending_breakout_orders():
                    self.state = "SEARCHING"
                else:
                    logger.warning(
                        "Cancel of expired GRIFF pending order(s) %s not confirmed by broker. "
                        "Holding CANCEL_PENDING (no new setups) and retrying every cycle.",
                        list(self.unconfirmed_cancel_order_ids),
                    )
                    return {
                        "status": "CANCEL_PENDING",
                        "unconfirmed_cancel_order_ids": dict(self.unconfirmed_cancel_order_ids),
                        "atr_14": atr_14,
                    }

        if self.state == "SEARCHING":
            mother_bar = candles[-2]
            current_bar = candles[-1]
            if is_inside_bar(current_bar, mother_bar):
                # MACRO-TREND FILTER (50 EMA)
                close_price = float(current_bar["close"])
                trend_direction = "BUY" if close_price > ema_50 else "SELL"
                
                logger.info("Inside Bar confirmed on bar %s. Macro Trend: %s (EMA50: %.2f)", latest_bar_time, trend_direction, ema_50)
                
                adx_values = compute_adx(candles, 14)
                current_adx = adx_values[-1] if adx_values else 0
                
                if current_adx < 25:
                    logger.info("ADX Filter Blocked Trade: Current ADX is %.2f (Requires >= 25). Skipping chop.", current_adx)
                    return {"status": "SKIPPED_ADX_LOW", "atr_14": atr_14, "bar": latest_bar_time}
                
                logger.info("ADX is %.2f. Trend is strong. Proceeding to place orders.", current_adx)
                
                # We place the pending breakout orders, but the place_pending_breakout_orders method needs to be aware of the trend
                # We'll pass the trend to place_pending_breakout_orders to only place the aligned order
                await self.place_pending_breakout_orders(current_bar, atr_14, self.current_equity, trend_direction)
                return {"status": "SETUP_PLACED", "atr_14": atr_14, "bar": latest_bar_time}
            else:
                logger.info(
                    "Scanning 1H Bars | Latest Close: %.2f | EMA_50: %.2f | ATR_14: %.2f | Setup: None",
                    float(latest_completed_bar.get("close", 0.0)),
                    ema_50,
                    atr_14,
                )

        return {"status": self.state, "atr_14": atr_14, "equity": self.current_equity}

    async def run_loop(self, poll_interval_seconds: float = 30.0) -> None:
        """Run continuous strategy monitoring event loop.

        Args:
            poll_interval_seconds: Interval between evaluation cycles in seconds.
        """
        self.is_running = True
        logger.info("Griff Live Engine loop started (Poll interval: %.1fs)", poll_interval_seconds)

        while self.is_running and not self.halted:
            try:
                await self.step()
                import json
                state_dump = {
                    "state": self.state,
                    "equity": self.current_equity,
                    "active_position": self.active_position,
                    "pending_buy_order_id": self.pending_buy_order_id,
                    "pending_sell_order_id": self.pending_sell_order_id,
                    "pending_setup_bar_time": self.pending_setup_bar_time.isoformat() if hasattr(self.pending_setup_bar_time, "isoformat") else self.pending_setup_bar_time,
                    "unconfirmed_cancel_order_ids": dict(self.unconfirmed_cancel_order_ids),
                    "history_count": self.last_candle_count,
                    "candle_fetch_failures": self.candle_fetch_failures,
                    "position_sync_failures": self.position_sync_failures,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                with open("/home/solveetcoagula/odin_ftmo/live_state.json", "w") as f:
                    json.dump(state_dump, f)
            except Exception as err:
                logger.error("Unexpected error during strategy cycle: %s", err, exc_info=True)
            

            await asyncio.sleep(poll_interval_seconds)

        logger.info("Griff Live Engine loop terminated.")

    def stop(self) -> None:
        """Signal engine event loop to stop."""
        logger.info("Engine stop requested.")
        self.is_running = False

    async def execute_live_trade(self, direction: str = "BUY") -> Dict[str, Any]:
        """Execute a genuine live breakout market trade on FTMO demo account.

        Args:
            direction: 'BUY' or 'SELL'.

        Returns:
            Dictionary containing order placement confirmation and broker state.
        """
        connected = await self.connect_account()
        if not connected:
            raise RuntimeError("Failed to connect to MetaAPI account")

        candles = await self.fetch_completed_1h_candles(limit=25)
        if len(candles) < 15:
            raise RuntimeError(f"Insufficient completed 1H candles: {len(candles)}")

        atr_14 = compute_atr_14(candles)
        lots = calculate_position_size(
            equity=self.current_equity,
            atr_14=atr_14,
            tick_value=self.tick_value,
            contract_size=self.contract_size,
            risk_pct=self.risk_pct,
            max_lot=5.0 if "BTC" in self.symbol else 50.0,
        )

        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol
        price_obj = await self.wrapper.connection.get_symbol_price(mt5_sym)
        ask = float(price_obj.get("ask", price_obj.get("askPrice", 0.0)))
        bid = float(price_obj.get("bid", price_obj.get("bidPrice", 0.0)))

        if direction.upper() in ("BUY", "LONG"):
            entry_price = ask
            sl = calculate_initial_stop_loss("BUY", entry_price, atr_14)
            options = {"comment": self.order_comment}
            res = await self.wrapper.connection.create_market_buy_order(
                mt5_sym,
                lots,
                stop_loss=sl,
                options=options,
            )
        else:
            entry_price = bid
            sl = calculate_initial_stop_loss("SELL", entry_price, atr_14)
            options = {"comment": self.order_comment}
            res = await self.wrapper.connection.create_market_sell_order(
                mt5_sym,
                lots,
                stop_loss=sl,
                options=options,
            )

        logger.info("Broker Response: %s", json.dumps(res, default=str))
        await asyncio.sleep(2.0)
        positions = await self.fetch_positions_safe() or []
        griff_pos = [
            p for p in positions
            if str(p.get("id")) == str(res.get("orderId"))
            or str(p.get("positionId")) == str(res.get("positionId"))
            or (p.get("symbol") == mt5_sym and str(p.get("comment", "")).startswith("GRIFF_"))
        ]

        return {
            "orderResult": res,
            "orderId": res.get("orderId"),
            "numericCode": res.get("numericCode"),
            "stringCode": res.get("stringCode"),
            "openPrice": res.get("openPrice", entry_price),
            "stopLoss": sl,
            "volume": lots,
            "atr_14": atr_14,
            "equity": self.current_equity,
            "symbol": self.symbol,
            "direction": direction.upper(),
            "comment": self.order_comment,
            "matchedPositions": griff_pos,
        }

    async def run_self_test(self) -> bool:
        """Execute comprehensive self-test suite validating all engine components.

        Returns:
            True if all unit calculations and broker queries succeed; False otherwise.
        """
        logger.info("Commencing Griff Engine Self-Test Suite...")

        assert compute_true_range(20100.0, 20000.0, 20050.0) == 100.0
        assert compute_true_range(20200.0, 20120.0, 20000.0) == 200.0
        assert compute_true_range(19950.0, 19800.0, 20100.0) == 300.0
        logger.info("True Range calculation assertions passed.")

        mother = {"high": 28994.13, "low": 28744.73}
        inside = {"high": 28973.64, "low": 28922.84}
        outside = {"high": 29000.0, "low": 28700.0}
        assert is_inside_bar(inside, mother) is True
        assert is_inside_bar(outside, mother) is False
        assert is_inside_bar(mother, mother) is False
        logger.info("Inside bar detection assertions passed.")

        lots = calculate_position_size(equity=100000.0, atr_14=92.24)
        assert lots == 7.23
        assert calculate_position_size(equity=100.0, atr_14=100.0) == 0.01
        assert calculate_position_size(equity=100000.0, atr_14=0.1, max_lot=50.0) == 50.0
        logger.info("Position sizing formula assertions passed.")

        initial_buy_sl = calculate_initial_stop_loss("BUY", 20000.0, 50.0)
        assert initial_buy_sl == 19925.0
        initial_sell_sl = calculate_initial_stop_loss("SELL", 20000.0, 50.0)
        assert initial_sell_sl == 20075.0

        trailed_buy_sl = calculate_trailing_stop("BUY", 19925.0, 20100.0, 50.0)
        assert trailed_buy_sl == 20025.0
        non_loosened_buy = calculate_trailing_stop("BUY", 20025.0, 19980.0, 50.0)
        assert non_loosened_buy == 20025.0

        trailed_sell_sl = calculate_trailing_stop("SELL", 20075.0, 19900.0, 50.0)
        assert trailed_sell_sl == 19975.0
        non_loosened_sell = calculate_trailing_stop("SELL", 19975.0, 20050.0, 50.0)
        assert non_loosened_sell == 19975.0
        logger.info("Stop loss and trailing stop assertions passed.")

        sim = GriffSimulationEngine()
        res_setup = sim.process_completed_bar(inside, mother, atr_14=50.0)
        assert res_setup["action"] == "PENDING_PLACED"
        logger.info("Simulation engine setup lifecycle passed.")

        connected = await self.connect_account()
        if not connected:
            logger.error("Broker connectivity validation failed during self-test.")
            return False

        assert abs(self.starting_balance - 100000.0) < 5000.0
        assert self.account_info.get("server") == "FTMO-Demo"
        logger.info("Account balance watermark validated: $%.2f (FTMO-Demo)", self.starting_balance)

        candles = await self.fetch_completed_1h_candles(limit=25)
        if len(candles) >= 15:
            atr = compute_atr_14(candles)
            logger.info("Retrieved %d completed 1H candles. Live ATR_14: %.2f points.", len(candles), atr)
            assert atr > 0.0

        if hasattr(self.wrapper, "streaming_connection") and self.wrapper.streaming_connection:
            await self.wrapper.streaming_connection.close()
        if hasattr(self.wrapper, "connection") and self.wrapper.connection:
            await self.wrapper.connection.close()

        logger.info("Self-Test completed with zero errors.")
        return True


def load_metaapi_token(config_path: str = DEFAULT_CONFIG_PATH) -> str:
    """Read MetaAPI token from local configuration JSON file.

    Args:
        config_path: Absolute or relative path to config_us100.json.

    Returns:
        Token string.

    Raises:
        FileNotFoundError: If configuration file is missing.
        KeyError: If token key is absent.
    """
    candidates = [
        config_path,
        os.path.join(os.path.dirname(__file__), config_path),
        "/home/solveetcoagula/odin_ftmo/config_us100.json",
    ]
    resolved_path = None
    for p in candidates:
        if os.path.exists(p):
            resolved_path = p
            break

    if not resolved_path:
        raise FileNotFoundError(f"Configuration file not found in candidates: {candidates}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    token = cfg.get("metaapi", {}).get("token", "")
    if not token:
        raise KeyError("MetaAPI token missing under 'metaapi.token' path in config")
    return token


def parse_arguments() -> argparse.Namespace:
    """Configure and parse CLI command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Griff Trading Engine: 1H Inside-Bar ATR Breakout Live System",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute active live trading loop",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Execute self-test suite and exit with code 0",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Execute continuous background daemon service with signal handling",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute genuine live breakout market trade with 1% risk position sizing and 14-period ATR",
    )
    parser.add_argument(
        "--direction",
        type=str,
        default="BUY",
        choices=["BUY", "SELL"],
        help="Order direction for live execution (default: BUY)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to MetaAPI config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--account-id",
        type=str,
        default=DEFAULT_ACCOUNT_ID,
        help=f"MetaAPI Account ID (default: {DEFAULT_ACCOUNT_ID})",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=DEFAULT_SYMBOL,
        help=f"Trading symbol (default: {DEFAULT_SYMBOL})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=30.0,
        help="Polling interval in seconds (default: 30.0)",
    )
    return parser.parse_args()


async def async_main() -> int:
    """Async main dispatcher handling execution flags.

    Returns:
        Process exit code integer.
    """
    args = parse_arguments()

    if not args.run and not args.test and not args.daemon and not args.execute:
        logger.info("No execution mode specified. Defaulting to --test mode.")
        args.test = True

    try:
        token = load_metaapi_token(args.config)
    except Exception as err:
        logger.error("Configuration error: %s", err)
        return 1

    engine = GriffLiveEngine(
        token=token,
        account_id=args.account_id,
        symbol=args.symbol,
    )

    if args.test:
        success = await engine.run_self_test()
        return 0 if success else 1

    if args.execute:
        try:
            exec_res = await engine.execute_live_trade(direction=args.direction)
            logger.info("Live Trade Execution Completed: %s", json.dumps(exec_res, default=str, indent=2))
            return 0 if exec_res.get("numericCode") == 10009 else 1
        except Exception as err:
            logger.error("Live trade execution failed: %s", err)
            return 1

    connected = await engine.connect_account()
    if not connected:
        logger.error("Failed to connect to MetaAPI account")
        return 1

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, engine.stop)
        except NotImplementedError:
            pass

    if args.daemon or args.run:
        await engine.run_loop(poll_interval_seconds=args.poll_interval)

    return 0


def main() -> None:
    """Synchronous process entrypoint."""
    try:
        exit_code = asyncio.run(async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user. Terminating.")
        sys.exit(0)


if __name__ == "__main__":
    main()
