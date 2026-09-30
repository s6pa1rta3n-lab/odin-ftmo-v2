"""Omni Breakout live trading engine with dynamic JSON profile loading."""

import argparse
import asyncio
import fcntl
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple

import aiohttp
import pytz

try:
    from MetaApiWrapper import MetaApiWrapper
except ImportError:
    MetaApiWrapper = None

try:
    from metaapi_cloud_sdk.clients.timeout_exception import TimeoutException
except ImportError:
    class TimeoutException(Exception):
        pass

from modules.entry import evaluate_omni_entry
from modules.exit import ExitManager, ExitModel
from modules.filters import FilterEngine
from modules.pyramid import PyramidManager
from modules.risk import RiskSizer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("OMNI_BREAKOUT")


def log_info(msg: str) -> None:
    """Log informational message to stdout and handlers."""
    log.info(msg)
    for h in logging.root.handlers:
        if hasattr(h, "flush"):
            h.flush()


meta_api_wrapper: Optional[MetaApiWrapper] = None


async def fetch_positions_safe(wrapper: Optional[Any]) -> Optional[list]:
    """Fetch positions with timeout catching, logging, and REST fallback.

    Parameters:
        wrapper: Active MetaApiWrapper instance.

    Returns:
        List of MT5 positions or None on failure.
    """
    if wrapper is None:
        return None
    positions = None
    try:
        if hasattr(wrapper, "connection") and wrapper.connection:
            positions = await asyncio.wait_for(wrapper.connection.get_positions(), timeout=10.0)
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException fetching positions: {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_positions_rest"):
                positions = await wrapper.get_positions_rest()
        except Exception as rest_err:
            log_info(f"REST get_positions_rest retry failed: {rest_err}")
    except (asyncio.TimeoutError, Exception) as e:
        log_info(f"Connection get_positions error ({type(e).__name__}): {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_positions_rest"):
                positions = await wrapper.get_positions_rest()
        except Exception as rest_err:
            log_info(f"REST get_positions_rest retry failed: {rest_err}")

    if positions is None and hasattr(wrapper, "get_positions_rest"):
        try:
            positions = await wrapper.get_positions_rest()
        except Exception as rest_err:
            log_info(f"Secondary REST get_positions_rest failed: {rest_err}")

    return positions


async def fetch_account_information_safe(wrapper: Optional[Any]) -> Dict[str, Any]:
    """Fetch account information with timeout protection and REST fallback.

    Parameters:
        wrapper: Active MetaApiWrapper instance.

    Returns:
        Dictionary with account information or empty dict on failure.
    """
    if wrapper is None:
        return {}
    info = None
    try:
        if hasattr(wrapper, "get_account_information"):
            info = await wrapper.get_account_information()
        elif hasattr(wrapper, "get_account_information_rest"):
            info = await wrapper.get_account_information_rest()
        elif hasattr(wrapper, "connection") and wrapper.connection:
            info = await asyncio.wait_for(wrapper.connection.get_account_information(), timeout=10.0)
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException fetching account info: {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_account_information_rest"):
                info = await wrapper.get_account_information_rest()
        except Exception as rest_err:
            log_info(f"REST get_account_information_rest retry failed: {rest_err}")
    except (asyncio.TimeoutError, Exception) as e:
        log_info(f"Account info fetch error ({type(e).__name__}): {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_account_information_rest"):
                info = await wrapper.get_account_information_rest()
        except Exception as rest_err:
            log_info(f"REST get_account_information_rest retry failed: {rest_err}")

    if not info and hasattr(wrapper, "get_account_information_rest"):
        try:
            info = await wrapper.get_account_information_rest()
        except Exception as rest_err:
            log_info(f"Secondary REST get_account_information_rest failed: {rest_err}")

    return info or {}


async def fetch_orders_safe(wrapper: Optional[Any]) -> Optional[list]:
    """Fetch pending orders with timeout protection and REST fallback.

    Parameters:
        wrapper: Active MetaApiWrapper instance.

    Returns:
        List of pending orders or None on failure.
    """
    if wrapper is None:
        return None
    orders = None
    try:
        if hasattr(wrapper, "connection") and wrapper.connection:
            orders = await asyncio.wait_for(wrapper.connection.get_orders(), timeout=10.0)
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException fetching orders: {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_orders_rest"):
                orders = await wrapper.get_orders_rest()
        except Exception as rest_err:
            log_info(f"REST get_orders_rest retry failed: {rest_err}")
    except (asyncio.TimeoutError, Exception) as e:
        log_info(f"Order fetch error ({type(e).__name__}): {e}. Sleeping before REST retry.")
        await asyncio.sleep(1.0)
        try:
            if hasattr(wrapper, "get_orders_rest"):
                orders = await wrapper.get_orders_rest()
        except Exception as rest_err:
            log_info(f"REST get_orders_rest retry failed: {rest_err}")

    if orders is None and hasattr(wrapper, "get_orders_rest"):
        try:
            orders = await wrapper.get_orders_rest()
        except Exception as rest_err:
            log_info(f"Secondary REST get_orders_rest failed: {rest_err}")

    return orders


def get_hive_mind_throttle(hive_key: str) -> str:
    """Read throttle state from shared inter-engine state file.

    Parameters:
        hive_key: Instrument key in hive mind store.

    Returns:
        Throttle mode string (e.g. "NORMAL", "HALT").
    """
    try:
        with open("/home/solveetcoagula/odin_ftmo/berserker_hive_mind.json", "r") as f:
            data = json.load(f)
            return data.get("throttle_state", {}).get(hive_key, "NORMAL")
    except Exception:
        return "NORMAL"


def update_hive_mind_state(hive_key: str, upnl: float, hwm_value: Optional[float] = None) -> None:
    """Record current floating PnL and high watermark into shared state file.

    Parameters:
        hive_key: Traded instrument key.
        upnl: Current unrealized PnL.
        hwm_value: Current account balance/watermark.
    """
    try:
        with open("/home/solveetcoagula/odin_ftmo/berserker_hive_mind.json", "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)
            except Exception:
                data = {"floating_state": {}, "hwm": 0.0, "throttle_state": {}}

            if "floating_state" not in data:
                data["floating_state"] = {}

            if hwm_value is not None and hwm_value > data.get("hwm", 0.0):
                data["hwm"] = hwm_value

            data["floating_state"][hive_key] = {
                "upnl": upnl,
                "symbol": hive_key,
                "timestamp": time.time(),
            }

            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass


def load_lockouts() -> Dict[str, Any]:
    """Load daily lockout states from persistent disk store.

    Returns:
        Lockout state dictionary.
    """
    try:
        with open("/home/solveetcoagula/odin_ftmo/daily_lockouts.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_lockouts(states: Dict[str, Any], date_str: str) -> None:
    """Save daily trade lockouts to persistent disk store.

    Parameters:
        states: Mapping of symbol to state objects.
        date_str: UTC date string.
    """
    data = {"date": date_str}
    for sym, st in states.items():
        data[sym] = {"long": getattr(st, "daily_long_taken", False), "short": getattr(st, "daily_short_taken", False)}
    try:
        with open("/home/solveetcoagula/odin_ftmo/daily_lockouts.json", "w") as f:
            json.dump(data, f)
    except Exception:
        pass


async def execute_close(
    client_id: str,
    side_str: str,
    qty: float,
    label: str,
    symbol: str,
) -> bool:
    """Execute a market close order on the MetaApi broker terminal.

    Parameters:
        client_id: Order client identifier.
        side_str: Position direction ("LONG" or "SHORT").
        qty: Volume to close in lots.
        label: Descriptive label for logging.
        symbol: Traded instrument symbol.

    Returns:
        True if close successfully confirmed, False otherwise.
    """
    log_info(f"{label}: Executing MARKET CLOSE for {qty} lots of {side_str} on {symbol}.")
    if meta_api_wrapper is None:
        return False

    target_type = "POSITION_TYPE_BUY" if side_str == "LONG" else "POSITION_TYPE_SELL"
    success = False
    try:
        mt5_sym = meta_api_wrapper._to_mt5(symbol)
        positions = await fetch_positions_safe(meta_api_wrapper)
        remaining_qty = float(qty)
        if positions is not None:
            for p in positions:
                p_cid = str(p.get("comment") or p.get("clientId") or "")
                if not p_cid.startswith(client_id):
                    continue
                if p["symbol"] == mt5_sym and p["type"] == target_type:
                    vol = float(p.get("volume", 0))
                    if vol <= remaining_qty + 0.02:
                        try:
                            await asyncio.wait_for(meta_api_wrapper.connection.close_position(p["id"]), timeout=5.0)
                            remaining_qty -= vol
                            success = True
                        except TimeoutException as te:
                            log_info(f"MetaApi TimeoutException closing position {p['id']} for {symbol}: {te}")
                    if remaining_qty <= 0.01:
                        break
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException in execute_close for {symbol}: {e}")
    except Exception as e:
        err_str = str(e)
        if "ERR_TRADE_POSITION_NOT_FOUND" not in err_str and "Position not found" not in err_str:
            log_info(f"Close Failed/Timeout for {symbol}: {e}")
    await asyncio.sleep(1)
    return success


async def execute_open(
    client_id: str,
    side_str: str,
    qty: float,
    label: str,
    symbol: str,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
) -> bool:
    """Execute an immediate market entry order.

    Parameters:
        client_id: Order client identifier.
        side_str: Direction ("LONG" or "SHORT").
        qty: Lot size.
        label: Logging label.
        symbol: Traded instrument.
        tp: Take profit price.
        sl: Stop loss price.

    Returns:
        True if order routed successfully, False otherwise.
    """
    log_info(f"{label} [{client_id}]: Executing MARKET OPEN for {qty} lots of {side_str} on {symbol}. TP: {tp} SL: {sl}")
    if meta_api_wrapper is None:
        return False

    action = "BUY" if side_str == "LONG" else "SELL"
    req = {
        "symbol": symbol,
        "side": action,
        "type": "MARKET",
        "quantity": str(qty),
        "newClientOrderId": client_id,
    }
    if tp is not None:
        req["takeProfit"] = str(tp)
    if sl is not None:
        req["stopLoss"] = str(sl)

    success = False
    try:
        res = await asyncio.wait_for(meta_api_wrapper.route_order(req), timeout=10.0)
        log_info(f"Open Result ({symbol}): {res}")
        success = res.get("status") != "REJECTED"
    except Exception as e:
        log_info(f"Open Failed/Timeout for {symbol}: {e}")
    await asyncio.sleep(1)
    return success


async def execute_stop_order(
    client_id: str,
    side_str: str,
    qty: float,
    stop_price: float,
    label: str,
    symbol: str,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
) -> bool:
    """Place a pending stop breakout order.

    Parameters:
        client_id: Client identifier.
        side_str: Direction ("LONG" or "SHORT").
        qty: Lot size.
        stop_price: Breakout trigger price level.
        label: Logging label.
        symbol: Traded instrument.
        tp: Take profit level.
        sl: Stop loss level.

    Returns:
        True if stop order was routed successfully, False otherwise.
    """
    log_info(f"{label} [{client_id}]: Placing STOP ORDER for {qty} lots of {side_str} on {symbol} at {stop_price}. TP: {tp} SL: {sl}")
    if meta_api_wrapper is None:
        return False

    action = "BUY" if side_str == "LONG" else "SELL"
    req = {
        "symbol": symbol,
        "side": action,
        "type": "STOP",
        "quantity": str(qty),
        "stopPrice": str(stop_price),
        "newClientOrderId": client_id,
    }
    if tp is not None:
        req["takeProfit"] = str(tp)
    if sl is not None:
        req["stopLoss"] = str(sl)

    success = False
    try:
        res = await asyncio.wait_for(meta_api_wrapper.route_order(req), timeout=10.0)
        log_info(f"Stop Order Result ({symbol}): {res}")
        success = res.get("status") != "REJECTED"
    except Exception as e:
        log_info(f"Stop Order Failed/Timeout for {symbol}: {e}")
    await asyncio.sleep(1)
    return success


async def cancel_pending_orders(symbol: str, client_prefix: Optional[str] = None) -> None:
    """Cancel pending orders on MT5 for the specified symbol matching client_prefix.

    Parameters:
        symbol: Traded instrument symbol.
        client_prefix: Optional prefix to filter orders by comment or clientId.
    """
    if meta_api_wrapper is None:
        return
    try:
        mt5_sym = meta_api_wrapper._to_mt5(symbol)
        orders = await fetch_orders_safe(meta_api_wrapper)

        if orders is not None:
            for o in orders:
                if o.get("symbol") == mt5_sym:
                    o_cid = str(o.get("comment") or o.get("clientId") or "")
                    if client_prefix is not None and not o_cid.startswith(client_prefix):
                        continue
                    ord_id = o.get("id")
                    log_info(f"Canceling pending order {ord_id} on {symbol}")
                    try:
                        if hasattr(meta_api_wrapper, "cancel_order"):
                            await asyncio.wait_for(meta_api_wrapper.cancel_order(ord_id), timeout=5.0)
                        elif hasattr(meta_api_wrapper, "connection") and meta_api_wrapper.connection:
                            await asyncio.wait_for(meta_api_wrapper.connection.cancel_order(ord_id), timeout=5.0)
                    except TimeoutException as te:
                        log_info(f"MetaApi TimeoutException canceling order {ord_id}: {te}")
                    except Exception as e:
                        log_info(f"Failed to cancel order {ord_id}: {e}")
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException in cancel_pending_orders for {symbol}: {e}")
    except Exception as e:
        log_info(f"Cancel Orders Failed: {e}")


def is_eod_window(utc_dt: datetime) -> bool:
    """Check if timestamp falls into end-of-day liquidation window (>= 19:45 UTC).

    Parameters:
        utc_dt: Datetime in UTC.

    Returns:
        True if inside liquidation window, False otherwise.
    """
    if utc_dt.tzinfo is not None:
        utc_dt = utc_dt.astimezone(pytz.utc)
    h = utc_dt.hour
    m = utc_dt.minute
    return (h == 19 and m >= 45) or (h >= 20)


async def check_and_execute_eod_liquidation(
    current_utc: datetime,
    states: Dict[str, Any],
    symbols_cfg: Dict[str, Any],
    trading_halted: bool,
    eod_flattened_logged: bool,
) -> Tuple[bool, bool]:
    """Flatten positions and cancel orders if inside EOD window.

    Parameters:
        current_utc: Current UTC timestamp.
        states: Active BreakoutState instances.
        symbols_cfg: Symbol configuration dictionary.
        trading_halted: Flag indicating daily trading halt.
        eod_flattened_logged: Flag tracking EOD execution log.

    Returns:
        Tuple of (trading_halted, eod_flattened_logged).
    """
    if is_eod_window(current_utc):
        if not trading_halted:
            log_info("END OF DAY LIQUIDATION (>= 19:45 UTC). Flattening positions and pending orders.")
            trading_halted = True

        for sym in symbols_cfg.keys():
            sym_prefix = states[sym].client_id if sym in states else None
            await cancel_pending_orders(sym, client_prefix=sym_prefix)

        has_open_positions = any(s.side != 0 or s.lots > 0 for s in states.values())
        if has_open_positions or not eod_flattened_logged:
            log_info(f"Executing EOD flattening (open_positions={has_open_positions})...")
            flat_success = await flatten_all_positions(states, reason="EOD LIQUIDATION")
            if flat_success:
                eod_flattened_logged = True
                for s in states.values():
                    s.side = 0
                    s.lots = 0.0
                    s.trailing_stop = 0.0
                    s.broker_sl = 0.0
                    s.filled_tranches = 0
                    s.tranche_lots = 0.0

    return trading_halted, eod_flattened_logged


async def sync_trend_stop_to_broker(
    client_id: str,
    side_str: str,
    qty: float,
    sl: float,
    symbol: str,
) -> None:
    """Synchronize trailing stop level to broker MT5 position.

    Parameters:
        client_id: Client identifier prefix.
        side_str: Direction ("LONG" or "SHORT").
        qty: Position lot size.
        sl: New stop loss price level.
        symbol: Traded symbol.
    """
    if meta_api_wrapper is None:
        return
    target_type = "POSITION_TYPE_BUY" if side_str == "LONG" else "POSITION_TYPE_SELL"
    try:
        mt5_sym = meta_api_wrapper._to_mt5(symbol)
        positions = await fetch_positions_safe(meta_api_wrapper)
        if positions is not None:
            for p in positions:
                p_cid = str(p.get("comment") or p.get("clientId") or "")
                if not p_cid.startswith(client_id):
                    continue
                if p["symbol"] == mt5_sym and p["type"] == target_type:
                    try:
                        await asyncio.wait_for(
                            meta_api_wrapper.connection.modify_position(p["id"], stop_loss=sl, take_profit=p.get("takeProfit")),
                            timeout=5.0,
                        )
                        log_info(f"SYNCHRONIZED TREND STOP TO BROKER ({symbol}): Position {p['id']} -> SL: {sl}")
                    except TimeoutException as te:
                        log_info(f"MetaApi TimeoutException modifying SL for {p['id']} ({symbol}): {te}")
                    except Exception as e:
                        log_info(f"Failed to sync broker SL for {p['id']} ({symbol}): {e}")
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException in sync_trend_stop_to_broker for {symbol}: {e}")
    except Exception as e:
        log_info(f"Sync SL Failed/Timeout for {symbol}: {e}")
    await asyncio.sleep(1)


async def flatten_all_positions(client_prefix: Any = "POD_", reason: str = "CIRCUIT BREAKER") -> bool:
    """Close all open positions on the account for managed strategies.

    Parameters:
        client_prefix: Strategy prefix, BreakoutState, or states dict.
        reason: Cause for liquidation.

    Returns:
        True if all positions were closed, False otherwise.
    """
    if meta_api_wrapper is None:
        return False

    if isinstance(client_prefix, dict):
        valid_prefixes = [getattr(s, "client_id", str(s)) for s in client_prefix.values()]
    elif isinstance(client_prefix, (list, set, tuple)):
        valid_prefixes = [getattr(s, "client_id", str(s)) for s in client_prefix]
    elif hasattr(client_prefix, "client_id"):
        valid_prefixes = [client_prefix.client_id]
    elif isinstance(client_prefix, str):
        if reason == "CIRCUIT BREAKER" and (client_prefix.startswith("EOD") or client_prefix.startswith("CIRCUIT")):
            reason = client_prefix
            valid_prefixes = ["POD_"]
        else:
            valid_prefixes = [client_prefix]
    else:
        valid_prefixes = ["POD_"]

    log_info(f"FLATTENING POSITIONS FOR {valid_prefixes}! REASON: {reason}")
    all_closed = True
    try:
        positions = await fetch_positions_safe(meta_api_wrapper)

        if positions is not None:
            for p in positions:
                p_cid = str(p.get("comment") or p.get("clientId") or "")
                is_managed = any(p_cid.startswith(prefix) for prefix in valid_prefixes)
                if not is_managed:
                    continue
                pos_id = p.get("id")
                try:
                    if hasattr(meta_api_wrapper, "connection") and meta_api_wrapper.connection:
                        await asyncio.wait_for(meta_api_wrapper.connection.close_position(pos_id), timeout=5.0)
                        log_info(f"Successfully closed position {pos_id}")
                    elif hasattr(meta_api_wrapper, "route_order"):
                        side = "SELL" if p.get("type") == "POSITION_TYPE_BUY" else "BUY"
                        qty = p.get("volume", 0)
                        payload = {"symbol": p.get("symbol"), "side": side, "type": "MARKET", "quantity": str(qty)}
                        await asyncio.wait_for(meta_api_wrapper.route_order(payload), timeout=5.0)
                        log_info(f"Flattened position {pos_id} via route_order")
                except TimeoutException as te:
                    log_info(f"MetaApi TimeoutException closing position {pos_id}: {te}")
                    all_closed = False
                except Exception as e:
                    log_info(f"Failed to close position {pos_id}: {e}")
                    all_closed = False
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException during flatten: {e}")
        all_closed = False
    except Exception as e:
        log_info(f"Failed to flatten: {e}")
        all_closed = False
    return all_closed


async def hedge_all_positions(reason: str = "CIRCUIT BREAKER") -> None:
    """Engage 1:1 net exposure hedge lock to freeze equity mark-to-market.

    Parameters:
        reason: Trigger cause for circuit breaker hedge lock.
    """
    if meta_api_wrapper is None:
        return
    log_info(f"HEDGING ALL POSITIONS! REASON: {reason}")
    try:
        mt5_positions = await fetch_positions_safe(meta_api_wrapper)
        if mt5_positions is None:
            return
        total_long = sum(float(p.get("volume", 0)) for p in mt5_positions if p.get("type") == "POSITION_TYPE_BUY")
        total_short = sum(float(p.get("volume", 0)) for p in mt5_positions if p.get("type") != "POSITION_TYPE_BUY")
        net_exposure = total_long - total_short
        if abs(net_exposure) >= 0.01:
            action = "SELL" if net_exposure > 0 else "BUY"
            qty = abs(net_exposure)
            symbol = "US100.cash"
            log_info(f"HEDGE ENGAGED ({symbol}): Executing {action} {qty} to freeze equity.")
            await asyncio.wait_for(
                meta_api_wrapper.route_order({"symbol": symbol, "side": action, "type": "MARKET", "quantity": str(qty)}),
                timeout=10.0,
            )
    except TimeoutException as e:
        log_info(f"MetaApi TimeoutException hedging: {e}")
    except Exception as e:
        log_info(f"Failed to hedge: {e}")


class BreakoutState:
    """State tracker for Omni Breakout trading session."""

    def __init__(self, client_prefix: str) -> None:
        """Initialize breakout state."""
        self.client_id = client_prefix
        self.client_prefix = client_prefix
        self.side = 0
        self.lots = 0.0
        self.trailing_stop = 0.0
        self.broker_sl = 0.0
        self.entry_price = 0.0
        self.original_entry = 0.0
        self.filled_tranches = 0
        self.target_tranches = 3
        self.tranche_lots = 0.0
        self.long_cooldown_until = 0.0
        self.short_cooldown_until = 0.0
        self.order_pending_until = 0.0
        self.partial_closes = []


def load_config_and_profile() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse CLI flags and load credentials config and JSON strategy profile.

    Returns:
        Tuple of (conf, profile_data).
    """
    parser = argparse.ArgumentParser(description="Odin FTMO Omni Breakout Live Trading Engine")
    parser.add_argument("--profile", type=str, default="", help="Path to strategy JSON profile")
    parser.add_argument("--config", type=str, default="", help="Path to MetaApi config file")
    args, unknown = parser.parse_known_args()

    config_path = args.config
    if not config_path:
        candidate_configs = [
            "config_us100.json",
            "/home/solveetcoagula/odin_ftmo/config_us100.json",
            "config.template.json",
        ]
        for cp in candidate_configs:
            if os.path.exists(cp):
                config_path = cp
                break

    conf: Dict[str, Any] = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            conf = json.load(f)

    profile_path = args.profile
    if not profile_path:
        candidate_profiles = [
            "profiles/omni_breakout/omni_conservative_close_v1.json",
            "profiles/omni_breakout/omni_fixed_low_trail_v1.json",
        ]
        for pp in candidate_profiles:
            if os.path.exists(pp):
                profile_path = pp
                break

    profile_data: Dict[str, Any] = {
        "engine": "omni_breakout",
        "instrument": "US100.cash",
        "dimensions": {
            "risk_model": "conservative_ramp",
            "entry_mode": "close_confirmation",
            "pyramid_model": "no_pyramid",
            "exit_model": "fixed_sl_trail",
            "filters": ["spread_gate"],
        },
        "parameters": {
            "sl_pts": 75.0,
            "tp_pts": 50.0,
            "buffer_pts": 0.0,
            "trail_trigger_pts": 30.0,
            "trail_dist_pts": 20.0,
            "max_spread_pts": 5.0,
            "cooldown_seconds": 60.0,
        },
    }

    if profile_path and os.path.exists(profile_path):
        with open(profile_path, "r") as f:
            profile_data = json.load(f)
        log_info(f"Loaded JSON strategy profile from: {profile_path}")
    else:
        log_info("No profile file specified or found; utilizing built-in baseline configuration.")

    return conf, profile_data


class LiveCandle:
    """Lightweight candle representation for live filter and entry evaluation."""

    def __init__(
        self,
        timestamp: datetime,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: float = 0.0,
    ) -> None:
        """Initialize candle fields."""
        self.timestamp = timestamp
        self.open = open_p
        self.high = high_p
        self.low = low_p
        self.close = close_p
        self.volume = volume


async def main() -> None:
    """Run Omni Breakout primary event loop."""
    global meta_api_wrapper

    conf, profile = load_config_and_profile()
    symbol = profile.get("instrument", "US100.cash")
    dims = profile.get("dimensions", {})
    params = profile.get("parameters", {})

    risk_model_name = dims.get("risk_model", "conservative_ramp")
    entry_mode_name = dims.get("entry_mode", "close_confirmation")
    pyramid_model_name = dims.get("pyramid_model", "no_pyramid")
    exit_model_name = dims.get("exit_model", "fixed_sl_trail")
    active_filters = dims.get("filters", ["spread_gate"])

    sl_pts = float(params.get("sl_pts", 75.0))
    tp_pts = float(params.get("tp_pts", 50.0))
    trail_trigger_pts = float(params.get("trail_trigger_pts", 30.0))
    trail_dist_pts = float(params.get("trail_dist_pts", 20.0))
    buffer_pts = float(params.get("buffer_pts", 0.0))

    log_info(
        f"OMNI BREAKOUT ENGINE INITIALIZED | Symbol: {symbol} | "
        f"Risk: {risk_model_name} | Entry: {entry_mode_name} | "
        f"Pyramid: {pyramid_model_name} | Exit: {exit_model_name} | Filters: {active_filters}"
    )

    token = conf.get("metaapi", {}).get("token", "")
    account_id = conf.get("metaapi", {}).get("account_id", "")
    if not token or not account_id:
        log_info("MetaApi credentials missing from configuration. Halting.")
        return

    meta_api_wrapper = MetaApiWrapper(token, account_id)
    await meta_api_wrapper.connect()

    client_prefix = f"POD_{entry_mode_name[:4].upper()}"
    state = BreakoutState(client_prefix)

    try:
        await cancel_pending_orders(symbol, client_prefix=client_prefix)
    except Exception as e:
        log_info(f"Startup cleanup error: {e}")

    prev_high, prev_low = await meta_api_wrapper.get_us_open_range_levels(symbol)
    orb_date = datetime.now(pytz.utc).strftime("%Y-%m-%d") if (prev_high and prev_low) else "1970-01-01"

    current_atr = await meta_api_wrapper.get_14d_atr(symbol) if hasattr(meta_api_wrapper, "get_14d_atr") else 50.0
    if not current_atr or current_atr <= 0:
        current_atr = 50.0

    fallback_bal = 94939.28
    acc_info = await fetch_account_information_safe(meta_api_wrapper)
    if acc_info:
        fallback_bal = float(acc_info.get("balance", fallback_bal))

    watermark_path = "/home/solveetcoagula/odin_ftmo/daily_watermark.json"
    daily_start_equity = fallback_bal
    if os.path.exists(watermark_path):
        try:
            with open(watermark_path, "r") as wf:
                daily_start_equity = float(json.load(wf).get("watermark", fallback_bal))
        except Exception:
            pass

    circuit_breaker_floor = daily_start_equity * 0.955
    risk_sizer = RiskSizer(risk_model_name, starting_equity=daily_start_equity)
    exit_manager = ExitManager(exit_model_name, sl_pts=sl_pts, tp_pts=tp_pts, atr=current_atr)
    filter_engine = FilterEngine(active_filters)

    total_lots = risk_sizer.compute_lots(daily_start_equity, sl_pts, current_atr)
    pyramid_manager = PyramidManager(pyramid_model_name, total_planned_lots=total_lots)

    trading_halted_for_day = False
    eod_flattened_logged = False
    symbols_cfg = {symbol: {"prev_high": prev_high, "prev_low": prev_low, "sl_pts": sl_pts}}
    states = {symbol: state}

    mt5_sym = meta_api_wrapper._to_mt5(symbol)

    log_info(f"Omni Armed | Start Equity: ${daily_start_equity:.2f} | Floor: ${circuit_breaker_floor:.2f} | Lots: {total_lots}")

    while True:
        try:
            current_utc = datetime.now(pytz.utc)
            current_utc_date = current_utc.strftime("%Y-%m-%d")

            trading_halted_for_day, eod_flattened_logged = await check_and_execute_eod_liquidation(
                current_utc, states, symbols_cfg, trading_halted_for_day, eod_flattened_logged
            )

            if current_utc.hour >= 14 and current_utc.hour < 20:
                if orb_date != current_utc_date:
                    h, l = await meta_api_wrapper.get_us_open_range_levels(symbol)
                    if h and l:
                        prev_high, prev_low = h, l
                        orb_date = current_utc_date
                        symbols_cfg[symbol]["prev_high"] = h
                        symbols_cfg[symbol]["prev_low"] = l
                        log_info(f"US Open Range Locked ({symbol}) - High: {prev_high:.2f} | Low: {prev_low:.2f}")

            price_data = None
            try:
                price_data = await asyncio.wait_for(meta_api_wrapper.get_symbol_price(symbol), timeout=5.0)
            except Exception:
                await asyncio.sleep(1.0)
                continue

            if not price_data:
                await asyncio.sleep(1.0)
                continue

            bid = float(price_data.get("bidPrice", 0.0))
            ask = float(price_data.get("askPrice", 0.0))
            spread = ask - bid
            mid = (bid + ask) / 2.0

            acc_info = await fetch_account_information_safe(meta_api_wrapper)
            eq = float(acc_info.get("equity", daily_start_equity)) if acc_info else daily_start_equity
            bal = float(acc_info.get("balance", daily_start_equity)) if acc_info else daily_start_equity

            if circuit_breaker_floor > 0 and eq > 0 and eq <= circuit_breaker_floor:
                log_info("FLOOR BREACH DETECTED. ENGAGING 1:1 HEDGE LOCK.")
                await hedge_all_positions(reason="CIRCUIT BREAKER (FLOOR BREACH)")
                circuit_breaker_floor = eq - 200.0
                await asyncio.sleep(300.0)
                continue

            mt5_positions = await fetch_positions_safe(meta_api_wrapper)
            if mt5_positions is None:
                log_info("Broker positions unavailable due to disconnect or timeout. Preserving current state.")
                await asyncio.sleep(2.0)
                continue

            actual_lots = 0.0
            actual_side = 0
            for p in mt5_positions:
                p_cid = str(p.get("comment") or p.get("clientId") or "")
                if p.get("symbol") == mt5_sym and p_cid.startswith(state.client_id):
                    vol = float(p.get("volume", 0.0))
                    side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
                    actual_lots += vol
                    actual_side = side
                    
                    if p.get("openPrice") and getattr(state, "entry_price", 0.0) == 0.0:
                        state.entry_price = float(p["openPrice"])
                    if p.get("stopLoss"):
                        state.broker_sl = float(p["stopLoss"])

            state.side = actual_side if actual_lots > 0 else 0
            state.lots = actual_lots

            if state.side != 0:
                state.current_price = mid
                
                trail_dist = 15.0
                trigger_pts = 15.0
                sl_changed = False
                
                if state.side == 1 and state.broker_sl > 0.0:
                    favorable = state.current_price - state.entry_price
                    if favorable >= trigger_pts:
                        sl_changed = True
                        new_sl = state.current_price - trail_dist
                        if state.broker_sl == 0.0 or new_sl > state.broker_sl:
                            state.broker_sl = new_sl
                            
                elif state.side == -1 and state.broker_sl > 0.0:
                    favorable = state.entry_price - state.current_price
                    if favorable >= trigger_pts:
                        sl_changed = True
                        new_sl = state.current_price + trail_dist
                        if state.broker_sl == 0.0 or new_sl < state.broker_sl:
                            state.broker_sl = new_sl
                            
                if sl_changed:
                    pos_id = None
                    for p in mt5_positions:
                        p_cid = str(p.get("comment") or p.get("clientId") or "")
                        if p.get("symbol") == mt5_sym and p_cid.startswith(state.client_id):
                            pos_id = p.get("id")
                            break
                    if pos_id:
                        try:
                            await asyncio.wait_for(
                                meta_api_wrapper.connection.modify_position(pos_id, stop_loss=state.broker_sl),
                                timeout=5.0,
                            )
                            log_info(f"Trailing Stop Updated: Pos={pos_id}, New SL={state.broker_sl:.2f}, Favorable={favorable:.2f}")
                        except TimeoutException as te:
                            log_info(f"MetaApi TimeoutException trailing SL for pos {pos_id}: {te}")
                        except Exception as e:
                            log_info(f"Failed to trail SL: {e}")

            if trading_halted_for_day:
                await asyncio.sleep(2.0)
                continue

            current_candle = LiveCandle(
                timestamp=current_utc,
                open_p=mid,
                high_p=mid,
                low_p=mid,
                close_p=mid,
                volume=1.0,
            )
            range_width = (prev_high - prev_low) if (prev_high and prev_low) else 0.0

            filters_passed = filter_engine.should_trade(
                current_candle,
                atr=current_atr,
                range_width=range_width,
                spread=spread,
            )

            has_valid_orb = (orb_date == current_utc_date) and (prev_high is not None and prev_low is not None)
            is_us_open_window = (14 <= current_utc.hour < 20)

            if state.side == 0 and time.time() >= state.order_pending_until and has_valid_orb and is_us_open_window and filters_passed:
                entry_lots = pyramid_manager.get_initial_lots()

                if entry_mode_name == "stop_order_at_range":
                    long_level = round(prev_high + buffer_pts, 2)
                    short_level = round(prev_low - buffer_pts, 2)
                    sl_long, _ = exit_manager.compute_sl_tp(long_level, 1)
                    sl_short, _ = exit_manager.compute_sl_tp(short_level, -1)
                    await execute_stop_order(f"{client_prefix}_L", "LONG", entry_lots, long_level, "US_ORB_STOP", symbol, sl=sl_long)
                    await execute_stop_order(f"{client_prefix}_S", "SHORT", entry_lots, short_level, "US_ORB_STOP", symbol, sl=sl_short)
                    state.order_pending_until = time.time() + 60.0
                else:
                    eval_candle = LiveCandle(
                        timestamp=current_utc,
                        open_p=mid,
                        high_p=ask,
                        low_p=bid,
                        close_p=mid,
                        volume=1.0,
                    )
                    signal = evaluate_omni_entry(entry_mode_name, eval_candle, prev_high, prev_low, current_atr)
                    if signal is not None:
                        direction, fill_p = signal
                        side_str = "LONG" if direction == 1 else "SHORT"
                        sl_val, tp_val = exit_manager.compute_sl_tp(fill_p, direction)
                        res = await execute_open(
                            f"{client_prefix}_MKT",
                            side_str,
                            entry_lots,
                            f"OMNI_{entry_mode_name.upper()}",
                            symbol,
                            tp=tp_val,
                            sl=sl_val,
                        )
                        if res:
                            state.side = direction
                            state.lots = entry_lots
                            state.entry_price = fill_p
                        state.order_pending_until = time.time() + 60.0

            if state.side != 0:
                orders = await fetch_orders_safe(meta_api_wrapper)
                if orders is not None:
                    for o in orders:
                        o_cid = str(o.get("comment") or o.get("clientId") or "")
                        if o.get("symbol") == mt5_sym and o.get("type") in ["ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP"] and o_cid.startswith(state.client_id):
                            log_info(f"OCO Triggered: Canceling opposing stop order {o['id']}")
                            try:
                                await asyncio.wait_for(meta_api_wrapper.cancel_order(o["id"]), timeout=5.0)
                            except TimeoutException as te:
                                log_info(f"MetaApi TimeoutException canceling opposing stop order {o['id']}: {te}")
                            except Exception:
                                pass

            await asyncio.sleep(2.0)

        except TimeoutException as e:
            log_info(f"MetaApi TimeoutException in main loop: {e}. Cooldown for 2.0s.")
            await asyncio.sleep(2.0)
        except Exception as e:
            log_info(f"Main Loop Error: {e}")
            await asyncio.sleep(2.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("Omni Breakout Engine shutdown requested.")
