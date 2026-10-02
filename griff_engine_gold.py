"""Live trading engine implementing the XAUUSD Asian Range Breakout Strategy.

This engine operates on the 15-minute timeframe specifically for Gold:
- Time Filter: Tracks Asian range (20:00 to 03:00 EST) and trades breakout from 03:15 to 10:00 EST.
- Entry: Market order when real-time price breaks the Asian High or Asian Low.
- Risk Parity: 1% risk per trade.
- Exits: Native MetaApi SL (1.5x ATR) and TP (3.0x ATR) placed on order.
- Time Exit: Hard close of all positions at 16:00 EST to eliminate overnight gap risk.
"""

import argparse
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
from modules.book_sync import (
    BrokerBookSync,
    adopted_position_record,
    describe_position,
)

# Any open position whose comment starts with this belongs to the Gold book.
GOLD_COMMENT_PREFIX = "GRIFF_GOLD"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Gold_Engine")

class GoldEngine:
    def __init__(self, token, account_id, config_path: str = "config_gold.json"):
        self.config_path = config_path
        # Default ODIN_METAAPI_HUB=off keeps the direct MetaApiWrapper path.
        self.wrapper = build_execution_wrapper(token, account_id, engine_name="gold")
        self.is_running = False
        self.state = "SEARCHING"
        self.active_position = None
        self.eastern = pytz.timezone('US/Eastern')
        self.asian_high = 0.0
        self.asian_low = 0.0
        self.day_triggered = False
        
        # Default config values
        self.symbol = "XAUUSD"
        self.risk_pct = 0.005
        self.contract_size = 100.0 # Standard Gold contract size
        self.tick_value = 1.0
        self.order_comment = "GRIFF_GOLD_BREAKOUT"
        self.comment_prefix = GOLD_COMMENT_PREFIX

        # Startup / reconnect adoption of an open Gold position (see
        # modules/book_sync.py for the 2026-10-02 US100 restart gap; Gold had
        # the same shape: SEARCHING after a restart never read positions).
        self.book_sync = BrokerBookSync(
            book_name="Gold",
            symbol=self.mt5_symbol(),
            comment_prefix=self.comment_prefix,
            logger=logger,
        )

    @property
    def position_sync_failures(self) -> int:
        return self.book_sync.read_failures

    def mt5_symbol(self):
        return self.wrapper._to_mt5(self.symbol)

    async def fetch_engine_positions(self):
        """Open positions that belong to the Gold book; ``None`` when the read failed."""

        return await self.book_sync.read_book(self.wrapper)

    def adopt_position(self, position, reason):
        """Switch to IN_TRADE around a position this process did not open. Broker values as-is."""

        self.active_position = adopted_position_record(position, symbol=self.mt5_symbol(), comment=self.order_comment)
        self.state = "IN_TRADE"
        logger.warning(f"Adopting open Gold position {describe_position(position)} -> IN_TRADE. Reason: {reason}")

    async def sync_book_with_broker(self, reason):
        """Startup / reconnect sync: adopt an open Gold position regardless of the session window."""

        result = await self.book_sync.sync(self.wrapper, reason=reason, current_state=self.state)
        if not result["ok"]:
            return False
        adopt = result["adopt"]
        if adopt is None:
            return True
        if self.state != "IN_TRADE":
            self.adopt_position(adopt, reason)
        else:
            self.active_position = adopted_position_record(adopt, symbol=self.mt5_symbol(), comment=self.order_comment)
        return True

    async def connect(self):
        logger.info(f"Connecting to MetaApi for account {self.wrapper.account_id}...")
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

    async def fetch_15m_candles(self, limit=30):
        mt5_sym = self.wrapper._to_mt5(self.symbol)
        try:
            if not self.wrapper.connection: return []
            candles = await self.wrapper.connection.get_historical_candles(mt5_sym, '15m', startTime=None, limit=limit)
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

    async def step(self):
        """One pass of the engine loop. Split out of ``run_loop`` so it is testable."""

        if not self.wrapper.connection:
            await self.connect()
            self.book_sync.note_reconnect("engine reconnected to the execution wrapper")

        # Startup / reconnect sync runs before anything that depends on
        # ``state`` (including the 16:00 hard close) and regardless of the
        # 03:15-10:00 trading window, so a restart mid-trade lands in IN_TRADE.
        resync_reason = self.book_sync.resync_reason(self.wrapper)
        if resync_reason:
            await self.sync_book_with_broker(resync_reason)

        est_now = self.get_est_time()
        time_str = est_now.strftime('%H:%M')
        
        if time_str == "00:01":
            # Reset daily trigger flag at midnight
            self.day_triggered = False
        
        # Check for 4 PM hard close
        if time_str >= "16:00" and time_str < "16:15":
            if self.state == "IN_TRADE":
                logger.warning("16:00 EST Reached. Hard closing all open Gold positions.")
                positions = await self.wrapper.get_positions_rest()
                for p in positions:
                    if p.get("symbol") == self.wrapper._to_mt5(self.symbol):
                        try:
                            await self.wrapper.connection.close_position(p['id'])
                            logger.info(f"Closed position {p['id']}")
                        except Exception as e:
                            logger.error(f"Failed to close position: {e}")
                self.state = "SEARCHING"
                self.active_position = None
        
        if self.state == "SEARCHING" and self.book_sync.pending:
            # The startup/reconnect read has not succeeded yet, so it is not
            # known whether the broker already holds a Gold position. Unknown
            # is not flat: evaluate no setup until a read succeeds.
            return

        if self.state == "SEARCHING" and not self.day_triggered:
            # Capture Asian Range at exactly 03:00 EST
            if time_str == "03:00":
                candles = await self.fetch_15m_candles(limit=28) # 28 * 15m = 7 hours
                if len(candles) >= 28:
                    self.asian_high = max([c['high'] for c in candles])
                    self.asian_low = min([c['low'] for c in candles])
                    logger.info(f"Asian Range Captured. High: {self.asian_high}, Low: {self.asian_low}")
                    
            # Trade Breakout between 03:15 and 10:00 EST
            elif "03:15" <= time_str <= "10:00" and self.asian_high > 0:
                price_obj = await self.wrapper.connection.get_symbol_price(self.wrapper._to_mt5(self.symbol))
                ask = float(price_obj.get("ask", price_obj.get("askPrice", 0.0)))
                bid = float(price_obj.get("bid", price_obj.get("bidPrice", 0.0)))
                
                trend = None
                entry_price = 0
                
                if ask >= self.asian_high:
                    trend = 'BUY'
                    entry_price = ask
                elif bid <= self.asian_low:
                    trend = 'SELL'
                    entry_price = bid
                    
                if trend:
                    logger.info(f"Asian Range Breakout! Trend: {trend}, Price: {entry_price}")
                    candles = await self.fetch_15m_candles(limit=20)
                    if candles:
                        current_atr = self.compute_atr(candles, 14)[-1]
                        account_info = await self.wrapper.get_account_information()
                        equity = account_info.get("equity", 100000)
                        
                        sl_dist = 1.5 * current_atr
                        lots = self.calculate_position_size(equity, sl_dist)
                        
                        if lots >= 0.01:
                            sl = entry_price - sl_dist if trend == 'BUY' else entry_price + sl_dist
                            tp = entry_price + (3.0 * current_atr) if trend == 'BUY' else entry_price - (3.0 * current_atr)
                            
                            logger.info(f"Placing {trend} {lots} lots. SL: {sl}, TP: {tp}")
                            options = {"comment": self.order_comment}
                            
                            try:
                                if trend == 'BUY':
                                    res = await self.wrapper.connection.create_market_buy_order(
                                        self.wrapper._to_mt5(self.symbol), lots, stop_loss=round(sl, 2), take_profit=round(tp, 2), options=options
                                    )
                                else:
                                    res = await self.wrapper.connection.create_market_sell_order(
                                        self.wrapper._to_mt5(self.symbol), lots, stop_loss=round(sl, 2), take_profit=round(tp, 2), options=options
                                    )
                                logger.info(f"Order Success: {res}")
                                result = res if isinstance(res, dict) else {}
                                self.active_position = adopted_position_record(
                                    {
                                        "id": str(result.get("positionId") or result.get("orderId") or ""),
                                        "symbol": self.mt5_symbol(),
                                        "type": "POSITION_TYPE_BUY" if trend == 'BUY' else "POSITION_TYPE_SELL",
                                        "volume": lots,
                                        "openPrice": result.get("openPrice"),
                                        "stopLoss": round(sl, 2),
                                        "takeProfit": round(tp, 2),
                                        "comment": self.order_comment,
                                    }
                                )
                                self.state = "IN_TRADE"
                                self.asian_high = 0 # Prevent multiple triggers
                                self.day_triggered = True # One trade per day limit
                            except Exception as e:
                                logger.error(f"Failed to place order: {e}")

        elif self.state == "IN_TRADE":
            # Check if position is still open. A failed read is "unknown",
            # not "flat": only a successful empty read returns to SEARCHING.
            matched = await self.fetch_engine_positions()
            if matched is None:
                return
            if not matched:
                logger.info("Gold Position no longer active (SL or TP hit). Returning to SEARCHING.")
                self.active_position = None
                self.state = "SEARCHING"
            else:
                self.active_position = adopted_position_record(matched[0], symbol=self.mt5_symbol(), comment=self.order_comment)

    async def run_loop(self):
        self.is_running = True
        logger.info("Gold Asian Range Breakout Engine started.")
        
        while self.is_running:
            try:
                await self.step()
            except Exception as e:
                logger.error(f"Loop error: {e}")
                
            await asyncio.sleep(15.0)

def load_metaapi_token(config_path="config.json"):
    with open(config_path, "r") as f:
        cfg = json.load(f)
    return cfg.get("metaapi", {}).get("token", "")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    
    token = load_metaapi_token(args.config)
    engine = GoldEngine(token=token, account_id=args.account_id)
    
    def handle_sigint(sig, frame):
        logger.info("Received termination signal.")
        engine.is_running = False
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    
    await engine.run_loop()

if __name__ == "__main__":
    asyncio.run(main())
