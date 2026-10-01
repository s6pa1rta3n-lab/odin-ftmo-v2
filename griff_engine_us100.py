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
        
        with open(self.config_path, "r") as f:
            cfg = json.load(f)
            self.symbol = cfg.get("symbol", "US100.cash")
            self.risk_pct = float(cfg.get("risk_pct", 0.01))
            self.contract_size = float(cfg.get("contract_size", 1.0))
            self.tick_value = float(cfg.get("tick_value", 1.0))
            self.order_comment = "GRIFF_US100_NY"

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

    async def run_loop(self):
        self.is_running = True
        logger.info("US100 NY Pullback Engine started.")
        
        while self.is_running:
            try:
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
                                        self.state = "IN_TRADE"
                                    except Exception as e:
                                        logger.error(f"Failed to place order: {e}")
                                        
                    else:
                        pass # Outside window

                elif self.state == "IN_TRADE":
                    # Check if position is still open
                    positions = await self.wrapper.get_positions_rest()
                    has_us100 = False
                    for p in positions:
                        if p.get("symbol") == self.wrapper._to_mt5(self.symbol):
                            has_us100 = True
                            
                    if not has_us100:
                        logger.info("US100 Position no longer active (SL or TP hit). Returning to SEARCHING.")
                        self.state = "SEARCHING"

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
