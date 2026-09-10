"""London Reversal live trading engine with dynamic JSON profile loading."""

import argparse
import asyncio
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
from modules.entry import evaluate_london_entry
from modules.exit import ExitManager, ExitModel
from modules.filters import FilterEngine
from modules.pyramid import PyramidManager
from modules.risk import RiskSizer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def log_info(msg: str) -> None:
    """Log informational message to stdout and active handlers."""
    logging.info(msg)


meta_api_wrapper: Optional[MetaApiWrapper] = None


class ReversalState:
    """Tracks position and execution state for a traded symbol."""

    def __init__(self, prefix: str) -> None:
        """Initialize reversal state with client identifier prefix."""
        self.client_prefix = prefix
        self.side = 0
        self.lots = 0.0
        self.entry_price = 0.0
        self.trailing_stop = 0.0
        self.long_cooldown_until = 0.0
        self.short_cooldown_until = 0.0
        self.order_pending_until = 0.0
        self.tranches_filled = 1
        self.partial_closes = []


async def execute_close(
    client_id: str,
    side_str: str,
    qty: float,
    label: str,
    symbol: str,
) -> Dict[str, Any]:
    """Execute a market order to close an open position.

    Parameters:
        client_id: Client identifier string.
        side_str: Current open position side ("LONG" or "SHORT").
        qty: Volume to close in lots.
        label: Descriptive label for audit logging.
        symbol: Traded instrument symbol.

    Returns:
        Order response dictionary from MetaApi broker.
    """
    log_info(f"CLOSING {side_str} ({label}) on {symbol}")
    payload = {
        "symbol": symbol,
        "side": "SELL" if side_str == "LONG" else "BUY",
        "type": "MARKET",
        "quantity": str(qty),
        "newClientOrderId": f"{client_id}_C",
    }
    if meta_api_wrapper is None:
        return {"status": "ERROR", "error": "wrapper_not_initialized"}
    res = await meta_api_wrapper.route_order(payload)
    if res.get("status") != "FILLED":
        log_info(f"Close failed: {res}")
    return res


async def execute_limit_order(
    client_id: str,
    side_str: str,
    qty: float,
    limit_price: float,
    label: str,
    symbol: str,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
) -> Dict[str, Any]:
    """Place a limit order at specified price level.

    Parameters:
        client_id: Unique order client identifier.
        side_str: Order direction ("LONG" or "SHORT").
        qty: Order volume in lots.
        limit_price: Limit price level.
        label: Descriptive strategy label.
        symbol: Traded instrument symbol.
        tp: Take profit price level.
        sl: Stop loss price level.

    Returns:
        Order response dictionary.
    """
    log_info(f"PLACING LIMIT {side_str} at {limit_price} ({label}) on {symbol} | SL: {sl} TP: {tp}")
    payload = {
        "symbol": symbol,
        "side": "BUY" if side_str == "LONG" else "SELL",
        "type": "LIMIT",
        "price": str(limit_price),
        "quantity": str(qty),
        "newClientOrderId": client_id,
    }
    if tp is not None:
        payload["takeProfit"] = str(tp)
    if sl is not None:
        payload["stopLoss"] = str(sl)

    if meta_api_wrapper is None:
        return {"status": "ERROR", "error": "wrapper_not_initialized"}
    res = await meta_api_wrapper.route_order(payload)
    if res.get("status") not in ["FILLED", "NEW"]:
        log_info(f"Limit order failed: {res}")
    return res


async def execute_market_order(
    client_id: str,
    side_str: str,
    qty: float,
    label: str,
    symbol: str,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
) -> Dict[str, Any]:
    """Place an immediate market order.

    Parameters:
        client_id: Unique order client identifier.
        side_str: Order direction ("LONG" or "SHORT").
        qty: Order volume in lots.
        label: Descriptive strategy label.
        symbol: Traded instrument symbol.
        tp: Take profit price level.
        sl: Stop loss price level.

    Returns:
        Order response dictionary.
    """
    log_info(f"PLACING MARKET {side_str} ({label}) on {symbol} | SL: {sl} TP: {tp}")
    payload = {
        "symbol": symbol,
        "side": "BUY" if side_str == "LONG" else "SELL",
        "type": "MARKET",
        "quantity": str(qty),
        "newClientOrderId": client_id,
    }
    if tp is not None:
        payload["takeProfit"] = str(tp)
    if sl is not None:
        payload["stopLoss"] = str(sl)

    if meta_api_wrapper is None:
        return {"status": "ERROR", "error": "wrapper_not_initialized"}
    res = await meta_api_wrapper.route_order(payload)
    if res.get("status") != "FILLED":
        log_info(f"Market order failed: {res}")
    return res


async def cancel_pending_orders(symbol: str) -> None:
    """Cancel all active pending orders for the specified symbol.

    Parameters:
        symbol: Symbol whose pending orders should be canceled.
    """
    if meta_api_wrapper is None:
        return
    try:
        mt5_sym = meta_api_wrapper._to_mt5(symbol)
        orders = await meta_api_wrapper.get_orders_rest()
        if orders is not None:
            for o in orders:
                if o.get("symbol") == mt5_sym:
                    await meta_api_wrapper.cancel_order(o["id"])
                    log_info(f"Canceled pending limit order {o['id']} on {mt5_sym}")
    except Exception as e:
        log_info(f"Error canceling orders: {e}")


async def flatten_all_positions(reason: str = "LIQUIDATION") -> None:
    """Close all open positions on the account at market.

    Parameters:
        reason: Audit explanation for position liquidation.
    """
    if meta_api_wrapper is None:
        return
    log_info(f"FLATTENING ALL POSITIONS | Reason: {reason}")
    try:
        positions = await meta_api_wrapper.get_positions_rest()
        if positions is not None:
            for p in positions:
                sym = p.get("symbol")
                qty = p.get("volume")
                side = "LONG" if p.get("type") == "POSITION_TYPE_BUY" else "SHORT"
                client_id = p.get("clientId", "MANUAL")
                payload = {
                    "symbol": sym,
                    "side": "SELL" if side == "LONG" else "BUY",
                    "type": "MARKET",
                    "quantity": str(qty),
                    "newClientOrderId": f"FLAT_{client_id}",
                }
                res = await meta_api_wrapper.route_order(payload)
                log_info(f"Flatten {side} {qty} {sym}: {res}")
    except Exception as e:
        log_info(f"Flatten Error: {e}")


def load_config_and_profile() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse command-line arguments and load credentials config and strategy profile.

    Returns:
        Tuple of (conf, profile_data).
    """
    parser = argparse.ArgumentParser(description="Odin FTMO London Reversal Live Trading Engine")
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
            "profiles/london_reversal/london_conservative_sweep_v1.json",
            "profiles/london_reversal/london_fixed_low_be_v1.json",
        ]
        for pp in candidate_profiles:
            if os.path.exists(pp):
                profile_path = pp
                break

    profile_data: Dict[str, Any] = {
        "engine": "london_reversal",
        "instrument": "US100.cash",
        "dimensions": {
            "risk_model": "conservative_ramp",
            "entry_mode": "blind_limit",
            "pyramid_model": "no_pyramid",
            "exit_model": "fixed_sl_tp",
            "filters": ["atr_gate", "spread_gate"],
        },
        "parameters": {
            "sl_pts": 40.0,
            "tp_pts": 20.0,
            "buffer_pts": 0.0,
            "max_spread_pts": 3.0,
            "cooldown_seconds": 60.0,
            "trail_trigger_pts": 15.0,
            "trail_dist_pts": 15.0,
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
    """Run primary live event orchestration loop."""
    global meta_api_wrapper

    conf, profile = load_config_and_profile()
    symbol = profile.get("instrument", "US100.cash")
    dims = profile.get("dimensions", {})
    params = profile.get("parameters", {})

    risk_model_name = dims.get("risk_model", "conservative_ramp")
    entry_mode_name = dims.get("entry_mode", "blind_limit")
    pyramid_model_name = dims.get("pyramid_model", "no_pyramid")
    exit_model_name = dims.get("exit_model", "fixed_sl_tp")
    active_filters = dims.get("filters", ["atr_gate", "spread_gate"])

    sl_pts = float(params.get("sl_pts", 40.0))
    tp_pts = float(params.get("tp_pts", 20.0))
    max_spread = float(params.get("max_spread_pts", 3.0))

    log_info(
        f"LONDON REVERSAL ENGINE INITIALIZED | Symbol: {symbol} | "
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

    mt5_sym = meta_api_wrapper._to_mt5(symbol)
    if mt5_sym and hasattr(meta_api_wrapper, "streaming_connection") and meta_api_wrapper.streaming_connection:
        await meta_api_wrapper.streaming_connection.subscribe_to_market_data(mt5_sym)
        log_info(f"Subscribed to market data stream for {mt5_sym}")

    client_prefix = f"LNDN_{entry_mode_name[:4].upper()}"
    state = ReversalState(client_prefix)

    try:
        await cancel_pending_orders(symbol)
    except Exception as e:
        log_info(f"Startup order cleanup error: {e}")

    prev_high, prev_low = await meta_api_wrapper.get_asian_range_levels(symbol)
    orb_date = datetime.now(pytz.utc).strftime("%Y-%m-%d") if (prev_high and prev_low) else "1970-01-01"

    current_atr = await meta_api_wrapper.get_14d_atr(symbol) if hasattr(meta_api_wrapper, "get_14d_atr") else 40.0
    if not current_atr or current_atr <= 0:
        current_atr = 40.0

    fallback_bal = 94939.28
    try:
        acc_info = await meta_api_wrapper.get_account_information_rest()
        if acc_info:
            fallback_bal = float(acc_info.get("balance", fallback_bal))
    except Exception:
        pass

    watermark_path = "/home/solveetcoagula/odin_ftmo/daily_watermark.json"
    daily_start_equity = fallback_bal
    if os.path.exists(watermark_path):
        try:
            with open(watermark_path, "r") as wf:
                daily_start_equity = float(json.load(wf).get("watermark", fallback_bal))
        except Exception:
            pass

    risk_sizer = RiskSizer(risk_model_name, starting_equity=daily_start_equity)
    exit_manager = ExitManager(exit_model_name, sl_pts=sl_pts, tp_pts=tp_pts, atr=current_atr)
    filter_engine = FilterEngine(active_filters)

    total_lots = risk_sizer.compute_lots(daily_start_equity, sl_pts, current_atr)
    pyramid_manager = PyramidManager(pyramid_model_name, total_planned_lots=total_lots)

    trading_halted_for_day = False
    trades_today = 0
    last_positions_check = 0.0
    cached_positions = []
    last_orders_check = 0.0
    cached_orders = []

    log_info(f"Engine Armed | Start Equity: ${daily_start_equity:.2f} | Total Lots: {total_lots} | Initial Lots: {pyramid_manager.get_initial_lots()}")

    while True:
        try:
            current_utc = datetime.now(pytz.utc)
            current_utc_date = current_utc.strftime("%Y-%m-%d")

            if current_utc.hour >= 7 and current_utc.hour < 13:
                if orb_date != current_utc_date:
                    h, l = await meta_api_wrapper.get_asian_range_levels(symbol)
                    if h and l:
                        prev_high, prev_low = h, l
                        orb_date = current_utc_date
                        trades_today = 0
                        trading_halted_for_day = False
                        state.long_cooldown_until = 0.0
                        state.short_cooldown_until = 0.0
                        log_info(f"Asian Range Locked ({symbol}) - High: {prev_high:.2f} | Low: {prev_low:.2f}")

            if current_utc.hour == 13 and current_utc.minute >= 0 and not trading_halted_for_day:
                log_info("End of Session Liquidation (13:00 UTC). Flattening positions.")
                await flatten_all_positions(reason="13:00 UTC HANDOFF")
                await cancel_pending_orders(symbol)
                state.side = 0
                state.lots = 0.0
                trading_halted_for_day = True

            price_data = None
            try:
                price_data = await asyncio.wait_for(meta_api_wrapper.get_symbol_price(symbol), timeout=5.0)
            except Exception:
                await asyncio.sleep(0.5)
                continue

            if not price_data:
                await asyncio.sleep(0.5)
                continue

            bid = float(price_data.get("bidPrice", 0.0))
            ask = float(price_data.get("askPrice", 0.0))
            spread = ask - bid
            mid = (bid + ask) / 2.0

            check_interval_pos = 1.0 if state.side != 0 else 5.0
            if time.time() - last_positions_check >= check_interval_pos:
                last_positions_check = time.time()
                res_pos = await meta_api_wrapper.get_positions_rest()
                if res_pos is not None:
                    cached_positions = res_pos

            actual_side = 0
            actual_lots = 0.0
            open_price = 0.0
            pos_id = None
            for p in cached_positions:
                if p.get("symbol") == mt5_sym:
                    if client_prefix in p.get("comment", p.get("clientId", "")):
                        actual_side = 1 if p.get("type") == "POSITION_TYPE_BUY" else -1
                        actual_lots += float(p.get("volume", 0.0))
                        open_price = float(p.get("openPrice", mid))
                        pos_id = p.get("id")
                        break

            state.side = actual_side
            state.lots = actual_lots

            has_valid_range = (orb_date == current_utc_date) and (prev_high is not None and prev_low is not None)
            is_london_window = (7 <= current_utc.hour < 13)

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

            if state.side == 0 and has_valid_range and is_london_window and trades_today < 1 and not trading_halted_for_day and filters_passed:
                check_interval_ord = 5.0
                if time.time() - last_orders_check >= check_interval_ord:
                    last_orders_check = time.time()
                    res_ord = await meta_api_wrapper.get_orders_rest()
                    if res_ord is not None:
                        cached_orders = res_ord

                has_pending = any(
                    o.get("symbol") == mt5_sym and client_prefix in o.get("comment", o.get("clientId", ""))
                    for o in cached_orders
                )

                if not has_pending and time.time() > state.order_pending_until:
                    entry_lots = pyramid_manager.get_initial_lots()

                    if entry_mode_name == "blind_limit":
                        sl_sell, tp_sell = exit_manager.compute_sl_tp(prev_high, -1)
                        sl_buy, tp_buy = exit_manager.compute_sl_tp(prev_low, 1)
                        await execute_limit_order(f"{client_prefix}_S", "SHORT", entry_lots, prev_high, "LNDN_FADE_HIGH", symbol, tp=tp_sell, sl=sl_sell)
                        await execute_limit_order(f"{client_prefix}_L", "LONG", entry_lots, prev_low, "LNDN_FADE_LOW", symbol, tp=tp_buy, sl=sl_buy)
                        state.order_pending_until = time.time() + 60.0

                    elif entry_mode_name == "dynamic_buffer":
                        buf = current_atr * 0.3
                        high_level = prev_high + buf
                        low_level = prev_low - buf
                        sl_sell, tp_sell = exit_manager.compute_sl_tp(high_level, -1)
                        sl_buy, tp_buy = exit_manager.compute_sl_tp(low_level, 1)
                        await execute_limit_order(f"{client_prefix}_S", "SHORT", entry_lots, high_level, "LNDN_DYN_HIGH", symbol, tp=tp_sell, sl=sl_sell)
                        await execute_limit_order(f"{client_prefix}_L", "LONG", entry_lots, low_level, "LNDN_DYN_LOW", symbol, tp=tp_buy, sl=sl_buy)
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
                        signal = evaluate_london_entry(entry_mode_name, eval_candle, prev_high, prev_low, current_atr)
                        if signal is not None:
                            direction, fill_p = signal
                            side_str = "LONG" if direction == 1 else "SHORT"
                            sl_val, tp_val = exit_manager.compute_sl_tp(fill_p, direction)
                            res = await execute_market_order(
                                f"{client_prefix}_MKT",
                                side_str,
                                entry_lots,
                                f"LNDN_{entry_mode_name.upper()}",
                                symbol,
                                tp=tp_val,
                                sl=sl_val,
                            )
                            if res.get("status") == "FILLED":
                                state.side = direction
                                state.lots = entry_lots
                                state.entry_price = fill_p
                                trades_today += 1
                            state.order_pending_until = time.time() + 60.0

            if state.side != 0:
                check_interval_ord = 2.0
                if time.time() - last_orders_check >= check_interval_ord:
                    last_orders_check = time.time()
                    res_ord = await meta_api_wrapper.get_orders_rest()
                    if res_ord is not None:
                        cached_orders = res_ord
                for o in cached_orders:
                    if o.get("symbol") == mt5_sym and client_prefix in o.get("comment", o.get("clientId", "")):
                        log_info(f"OCO Triggered: Canceling opposing limit order {o['id']}")
                        await meta_api_wrapper.cancel_order(o["id"])

                if trades_today == 0:
                    trades_today = 1

            await asyncio.sleep(0.5)

        except Exception as e:
            log_info(f"Main Loop Error: {e}")
            await asyncio.sleep(5.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("London Reversal Engine shutdown requested.")
