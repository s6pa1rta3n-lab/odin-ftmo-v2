"""Live trading engine implementing the US100 NY Session Pullback Strategy.

This engine operates on the 15-minute timeframe specifically for US100.cash:
- Time Filter: Only searches for setups between 09:45 and 11:30 EST.
- Trend Identification: Close of the previous 15m candle relative to 20 EMA.
- Entry: Market order when real-time price pulls back to touch the 20 EMA.
- Risk Parity: 1% risk per trade.
- Exits: Native MetaApi SL (1.5x ATR) and TP (3.0x ATR) placed on order.
- Time Exit: Hard close of all positions at 16:00 EST to eliminate overnight gap risk.
"""

import asyncio
import json
import logging
import math
import os
import signal
import sys
import time
from datetime import datetime
import pytz

from metaapi_hub.factory import build_execution_wrapper
from modules.entry_guard import (
    describe_place_error,
    is_ambiguous_place_error,
    matching_positions,
)

# Seconds to wait after an ambiguous place error before the reconciling
# position read. A fill reported right as the acknowledgement is lost can
# take a moment to show up in the position list.
POST_PLACE_ERROR_SYNC_DELAY_SECONDS = 2.0

# Any open position whose comment starts with this belongs to the US100 book,
# regardless of which symbol alias the broker reports it under.
US100_COMMENT_PREFIX = "GRIFF_US100"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("US100_Engine")

class US100Engine:
    def __init__(self, token, account_id, config_path: str = "config_us100.json"):
        self.config_path = config_path
        # Default ODIN_METAAPI_HUB=off keeps the direct MetaApiWrapper path.
        self.wrapper = build_execution_wrapper(token, account_id, engine_name="us100")
        self.is_running = False
        self.state = "SEARCHING"
        self.active_position = None
        self.eastern = pytz.timezone('US/Eastern')
        # Double-book guard state (see modules/entry_guard.py for the incident).
        # ``entry_sync_required`` is set by any entry failure and only cleared by
        # a successful position read; while set, no new entry may be sent.
        self.entry_sync_required = False
        self.last_place_error = None
        self.position_sync_failures = 0
        self.post_place_error_sync_delay = POST_PLACE_ERROR_SYNC_DELAY_SECONDS
        
        with open(self.config_path, "r") as f:
            cfg = json.load(f)
            self.symbol = cfg.get("symbol", "US100.cash")
            self.risk_pct = float(cfg.get("risk_pct", 0.01))
            self.contract_size = float(cfg.get("contract_size", 1.0))
            self.tick_value = float(cfg.get("tick_value", 1.0))
            self.order_comment = "GRIFF_US100_NY"
            self.comment_prefix = US100_COMMENT_PREFIX

    async def connect(self):
        logger.info("Connecting to MetaApi for US100...")
        return await self.wrapper.connect()

    def get_est_time(self):
        return datetime.now(pytz.utc).astimezone(self.eastern)

    def compute_atr(self, candles, period=14):
        if len(candles) <= period: return [0]*len(candles)
        tr_list = [0]
        for i in range(1, len(candles)):
            c, pc = candles[i], candles[i-1]
            tr = max(c['high'] - c['low'], abs(c['high'] - pc['close']), abs(c['low'] - pc['close']))
            tr_list.append(tr)
        atr = [0]*len(candles)
        atr[period] = sum(tr_list[1:period+1])/period
        for i in range(period+1, len(candles)):
            atr[i] = (atr[i-1] * (period - 1) + tr_list[i]) / period
        return atr

    def compute_ema(self, candles, period=20):
        closes = [c['close'] for c in candles]
        emas = [0]*len(candles)
        if len(closes) < period: return emas
        ema = sum(closes[:period])/period
        emas[period-1] = ema
        multiplier = 2.0 / (period + 1)
        for i in range(period, len(closes)):
            ema = (closes[i] - ema) * multiplier + ema
            emas[i] = ema
        return emas

    async def fetch_15m_candles(self):
        mt5_sym = self.wrapper._to_mt5(self.symbol)
        try:
            # We fetch 15m candles. Wait, MetaApiWrapper might only fetch 1h natively.
            # We must use MetaApi connection directly.
            if not self.wrapper.connection: return []
            
            # 15m is '15m' in MetaAPI
            candles = await self.wrapper.account.get_historical_candles(mt5_sym, '15m')
            formatted = []
            for c in candles:
                formatted.append({
                    'time': c['time'],
                    'open': c['open'],
                    'high': c['high'],
                    'low': c['low'],
                    'close': c['close']
                })
            return formatted
        except Exception as e:
            logger.error(f"Error fetching 15m candles: {e}")
            return []

    def calculate_position_size(self, equity, sl_distance):
        risk_dollars = equity * self.risk_pct
        if sl_distance <= 0: return 0.0
        lots = risk_dollars / (sl_distance * self.tick_value * self.contract_size)
        return round(lots, 2)

    # ------------------------------------------------------------------
    # Double-book guard
    #
    # 2026-10-02: a BUY 9.46 was filled by the broker, the hub then answered
    # NOT_CONNECTED for that same mutation, this engine logged the failure
    # and stayed SEARCHING, and five minutes later it placed BUY 8.88 on top
    # of the live 9.46. Every entry now goes through ``place_entry`` which
    # (a) refuses to send unless a fresh position read shows the book flat
    # and (b) reconciles against positions after any place error.
    # ------------------------------------------------------------------

    def mt5_symbol(self):
        return self.wrapper._to_mt5(self.symbol)

    async def fetch_engine_positions(self):
        """Read open positions and return the ones that belong to this book.

        Returns ``None`` when the read itself failed. Callers must treat
        ``None`` as "unknown", never as "flat".
        """

        try:
            positions = await self.wrapper.get_positions_rest()
        except Exception as e:
            self.position_sync_failures += 1
            logger.error(
                f"Position read failed ({self.position_sync_failures} consecutive): {e}. "
                "Book state is unknown; not treating this as flat."
            )
            return None
        if self.position_sync_failures:
            logger.info(f"Position read recovered after {self.position_sync_failures} consecutive failures.")
        self.position_sync_failures = 0
        return matching_positions(positions, symbol=self.mt5_symbol(), comment_prefix=self.comment_prefix)

    def adopt_position(self, position, reason):
        """Switch to IN_TRADE around a position this engine did not knowingly open."""

        self.active_position = position
        self.state = "IN_TRADE"
        self.entry_sync_required = False
        self.last_place_error = None
        logger.warning(
            f"Adopting open US100 position {position.get('id')} "
            f"({position.get('type')} {position.get('volume')} @ {position.get('openPrice')}, "
            f"comment={position.get('comment') or position.get('brokerComment')!r}) -> IN_TRADE. Reason: {reason}"
        )

    async def confirm_flat_before_entry(self):
        """Return True only when a successful position read shows no US100 book.

        Any other outcome blocks entry: a failed read leaves the state
        unknown, and a matching position means the previous entry (or
        another process) already holds the book, so we adopt it instead.
        """

        matched = await self.fetch_engine_positions()
        if matched is None:
            logger.warning("Cannot confirm the US100 book is flat (position read failed). No new entry.")
            return False
        if matched:
            self.adopt_position(matched[0], "pre-entry position check found an open US100 position")
            if len(matched) > 1:
                logger.error(
                    f"{len(matched)} open US100 positions found ({[p.get('id') for p in matched]}). "
                    "This engine will manage the first and will not add to the book."
                )
            return False
        if self.entry_sync_required:
            logger.info("Position sync confirmed the US100 book is flat after the last failed entry; entries re-enabled.")
        self.entry_sync_required = False
        self.last_place_error = None
        return True

    async def reconcile_after_place_error(self, exc):
        """A place error is not proof of no fill. Sync positions before anything else."""

        self.last_place_error = exc
        self.entry_sync_required = True
        if is_ambiguous_place_error(exc):
            logger.error(
                f"Ambiguous place result ({describe_place_error(exc)}). The order may have filled; "
                "syncing positions before any further entry."
            )
            if self.post_place_error_sync_delay > 0:
                await asyncio.sleep(self.post_place_error_sync_delay)
        else:
            logger.info(
                f"Order was refused before reaching the broker ({describe_place_error(exc)}); "
                "confirming the book is flat before the next entry."
            )
        await self.confirm_flat_before_entry()

    async def place_entry(self, trend, lots, sl, tp):
        """Send one market entry, guarded on both sides by a position sync."""

        if self.entry_sync_required:
            logger.warning("A previous entry attempt is still unreconciled; syncing positions before this one.")
        if not await self.confirm_flat_before_entry():
            logger.warning(f"Skipping {trend} {lots} lots: the US100 book is not confirmed flat.")
            return False

        logger.info(f"Placing {trend} {lots} lots. SL: {sl}, TP: {tp}")
        options = {"comment": self.order_comment}
        try:
            if trend == 'BUY':
                res = await self.wrapper.connection.create_market_buy_order(
                    self.mt5_symbol(), lots, stop_loss=round(sl, 2), take_profit=round(tp, 2), options=options
                )
            else:
                res = await self.wrapper.connection.create_market_sell_order(
                    self.mt5_symbol(), lots, stop_loss=round(sl, 2), take_profit=round(tp, 2), options=options
                )
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            await self.reconcile_after_place_error(e)
            return False

        logger.info(f"Order Success: {res}")
        result = res if isinstance(res, dict) else {}
        self.active_position = {
            "id": str(result.get("positionId") or result.get("orderId") or ""),
            "symbol": self.mt5_symbol(),
            "type": "POSITION_TYPE_BUY" if trend == 'BUY' else "POSITION_TYPE_SELL",
            "volume": lots,
            "openPrice": result.get("openPrice"),
            "comment": self.order_comment,
        }
        self.state = "IN_TRADE"
        self.entry_sync_required = False
        self.last_place_error = None
        return True

    async def step(self):
        """One pass of the engine loop. Split out of ``run_loop`` so it is testable."""

        if not self.wrapper.connection:
            await self.connect()

        est_now = self.get_est_time()
        time_str = est_now.strftime('%H:%M')
        
        # Check for 4 PM hard close
        if time_str >= "16:00" and time_str < "16:15":
            if self.state == "IN_TRADE":
                logger.warning("16:00 EST Reached. Hard closing all open US100 positions.")
                positions = await self.wrapper.get_positions_rest()
                for p in positions:
                    if p.get("symbol") == self.wrapper._to_mt5(self.symbol):
                        try:
                            # Wait, MetaAPI has no native close_position, we just send an opposite market order or use close_position
                            await self.wrapper.connection.close_position(p['id'])
                            logger.info(f"Closed position {p['id']}")
                        except Exception as e:
                            logger.error(f"Failed to close position: {e}")
                self.state = "SEARCHING"
        
        if self.state == "SEARCHING":
            if self.entry_sync_required:
                # A previous entry attempt ended in an error and no position
                # read has succeeded since. Reconcile first; this may adopt a
                # fill (-> IN_TRADE) or re-enable entries. Either way, no
                # setup is evaluated until the book state is known.
                await self.confirm_flat_before_entry()
                return

            if "09:45" <= time_str <= "11:30":
                candles = await self.fetch_15m_candles()
                if len(candles) > 25:
                    atr = self.compute_atr(candles, 14)
                    ema = self.compute_ema(candles, 20)
                    
                    prev = candles[-2]
                    current_ema = ema[-1]
                    current_atr = atr[-1]
                    
                    trend = 'BUY' if prev['close'] > ema[-2] else 'SELL'
                    
                    price_obj = await self.wrapper.connection.get_symbol_price(self.wrapper._to_mt5(self.symbol))
                    ask = float(price_obj.get("ask", price_obj.get("askPrice", 0.0)))
                    bid = float(price_obj.get("bid", price_obj.get("bidPrice", 0.0)))
                    
                    triggered = False
                    entry_price = 0
                    
                    if trend == 'BUY' and ask <= current_ema:
                        triggered = True
                        entry_price = ask
                    elif trend == 'SELL' and bid >= current_ema:
                        triggered = True
                        entry_price = bid
                        
                    if triggered:
                        logger.info(f"NY Pullback Triggered! Trend: {trend}, Price: {entry_price}, EMA: {current_ema}")
                        
                        account_info = await self.wrapper.get_account_information()
                        equity = account_info.get("equity", 100000)
                        
                        sl_dist = 1.5 * current_atr
                        lots = self.calculate_position_size(equity, sl_dist)
                        
                        if lots >= 0.01:
                            sl = entry_price - sl_dist if trend == 'BUY' else entry_price + sl_dist
                            tp = entry_price + (3.0 * current_atr) if trend == 'BUY' else entry_price - (3.0 * current_atr)
                            await self.place_entry(trend, lots, sl, tp)
                                
            else:
                pass # Outside window

        elif self.state == "IN_TRADE":
            # Check if position is still open. A failed read is "unknown",
            # not "flat": only a successful empty read returns to SEARCHING.
            matched = await self.fetch_engine_positions()
            if matched is None:
                return
            if not matched:
                logger.info("US100 Position no longer active (SL or TP hit). Returning to SEARCHING.")
                self.active_position = None
                self.state = "SEARCHING"
            else:
                self.active_position = matched[0]

    async def run_loop(self):
        self.is_running = True
        logger.info("US100 NY Pullback Engine started.")
        
        while self.is_running:
            try:
                await self.step()
            except Exception as e:
                logger.error(f"Loop error: {e}")
                
            await asyncio.sleep(15.0)


import argparse
import json

def load_metaapi_token(config_path="config_us100.json"):
    with open(config_path, "r") as f:
        cfg = json.load(f)
    return cfg.get("metaapi", {}).get("token", "")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--config", default="config_us100.json")
    args = parser.parse_args()
    
    token = load_metaapi_token(args.config)
    
    async def main():
        engine = US100Engine(token=token, account_id=args.account_id)
        
        def handle_sigint(sig, frame):
            logger.info("Received termination signal.")
            engine.is_running = False
            import sys
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_sigint)
        signal.signal(signal.SIGTERM, handle_sigint)
        
        await engine.run_loop()

    asyncio.run(main())
