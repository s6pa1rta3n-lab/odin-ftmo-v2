import time
import logging
from logging.handlers import TimedRotatingFileHandler
from asterdex_client import AsterdexClient
from backtester import fetch_klines, compute_atr, is_inside_bar

def compute_ema(candles, period=50):
    closes = [float(c["close"]) for c in candles[-period:]]
    if not closes: return 0.0
    ema = closes[0]
    multiplier = 2.0 / (period + 1)
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_structural_trailing_stop(direction, current_sl, completed_candles, current_atr):
    if len(completed_candles) < 2: return current_sl
    if direction == "BUY":
        new_sl = completed_candles[-1]["low"] - (1.5 * current_atr)
        if new_sl > current_sl: return round(new_sl, 1)
    else:
        new_sl = completed_candles[-1]["high"] + (1.5 * current_atr)
        if new_sl < current_sl: return round(new_sl, 1)
    return current_sl

import math

logger = logging.getLogger('OdinDaemon')
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('odin3.0.log', when='midnight', interval=1, backupCount=7)
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
logger.addHandler(handler)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
logger.addHandler(console)

class OdinDaemon:
    def __init__(self, symbol='BTCUSDT', risk_pct=0.01):
        self.client = AsterdexClient()
        self.symbol = symbol
        self.risk_pct = risk_pct
        self.state = 'SEARCHING'
        
        self.active_position = None
        self.buy_order_id = None
        self.sell_order_id = None
        
        self.last_evaluated_bar_time = None
        self.pending_setup_bar_time = None

    def fetch_equity(self) -> float:
        try:
            account = self.client.get_account()
            assets = account.get('assets', [])
            equity = 0.0
            for a in assets:
                asset = a.get('asset')
                if asset in ['USDT', 'USDC']:
                    wallet_bal = float(a.get('crossWalletBalance', 0))
                    un_pnl = float(a.get('crossUnPnl', 0))
                    equity += (wallet_bal + un_pnl)
            if equity <= 0:
                return 6000.0
            return equity
        except Exception as e:
            logger.error(f'Error fetching account: {e}')
            return 6000.0

    def _cancel_orders(self):
        if self.buy_order_id:
            try:
                self.client.cancel_order(self.symbol, self.buy_order_id)
            except Exception as e:
                pass
            self.buy_order_id = None
        if self.sell_order_id:
            try:
                self.client.cancel_order(self.symbol, self.sell_order_id)
            except Exception as e:
                pass
            self.sell_order_id = None

    def tick(self):
        try:
            logger.info('Tick: Fetching market data...')
            candles = fetch_klines(self.symbol, '1h', 60)
            if len(candles) < 55:
                return
                
            atr_list = compute_atr(candles)
            
            prev_bar = candles[-2]
            mother_bar = candles[-3]
            
            latest_completed_time = prev_bar['time']
            
            positions = self.client.get_positions()
            active = [p for p in positions if p['symbol'] == self.symbol and float(p['positionAmt']) != 0]
            
            if active:
                pos = active[0]
                amt = float(pos['positionAmt'])
                self.active_position = {
                    'direction': 'BUY' if amt > 0 else 'SELL',
                    'volume': abs(amt),
                    'entry': float(pos['entryPrice'])
                }
                self.state = 'IN_TRADE'
                self._cancel_orders()
            else:
                if self.state == 'IN_TRADE':
                    logger.info('Trade exited. Returning to SEARCHING.')
                    self.active_position = None
                    self.state = 'SEARCHING'
                    
            if self.state == 'PENDING':
                if self.pending_setup_bar_time and latest_completed_time != self.pending_setup_bar_time:
                    logger.info('Breakout window expired unfilled. Canceling pending orders.')
                    self._cancel_orders()
                    self.state = 'SEARCHING'
                    self.pending_setup_bar_time = None

            if self.state == 'SEARCHING':
                if self.last_evaluated_bar_time == latest_completed_time:
                    return
                
                self.last_evaluated_bar_time = latest_completed_time
                
                if is_inside_bar(prev_bar, mother_bar):
                    equity = self.fetch_equity()
                    atr_14 = atr_list[-2]
                    sl_points = 1.5 * atr_14
                    
                    if sl_points > 0:
                        risk_dollars = equity * self.risk_pct
                        volume = round(risk_dollars / sl_points, 3) 
                        
                        buy_price = prev_bar['high']
                        sell_price = prev_bar['low']
                        ema_50 = compute_ema(candles, 50)
                        trend_direction = 'BUY' if float(prev_bar['close']) > ema_50 else 'SELL'
                        
                        logger.info(f'Inside Bar found. Macro Trend: {trend_direction}. Placing STOP order (Vol: {volume})')
                        
                        try:
                            if trend_direction == 'BUY':
                                res_buy = self.client.place_order(self.symbol, 'BUY', 'STOP_MARKET', volume, stop_price=buy_price, positionSide='LONG')
                                self.buy_order_id = res_buy.get('orderId')
                            else:
                                res_sell = self.client.place_order(self.symbol, 'SELL', 'STOP_MARKET', volume, stop_price=sell_price, positionSide='SHORT')
                                self.sell_order_id = res_sell.get('orderId')
                            
                            self.state = 'PENDING'
                            self.pending_setup_bar_time = latest_completed_time
                        except Exception as e:
                            logger.error(f'Failed to place orders: {e}')
                            self._cancel_orders()
                else:
                    logger.info(f'Scanning 1H Bars | Latest Close: {prev_bar["close"]} | ATR_14: {atr_list[-2]:.2f} | Setup: None')

            elif self.state == 'IN_TRADE':
                direction = self.active_position['direction']
                entry_price = self.active_position['entry']
                pos_volume = self.active_position['volume']
                close_side = 'SELL' if direction == 'BUY' else 'BUY'
                close_pos_side = 'LONG' if direction == 'BUY' else 'SHORT'
                
                if not hasattr(self, 'sl_price'):
                    dist = 1.5 * atr_list[-2]
                    self.sl_price = round(entry_price - dist if direction == 'BUY' else entry_price + dist, 1)
                    logger.info(f'Initialized mechanical Stop Loss at {self.sl_price}')
                    try:
                        res = self.client.place_order(self.symbol, close_side, 'STOP_MARKET', pos_volume, stop_price=self.sl_price, positionSide=close_pos_side, closePosition=True)
                        self.sl_order_id = res.get('orderId')
                    except Exception as e:
                        logger.error(f'Failed to place initial mechanical SL: {e}')
                
                # We only trail the stop every 1H close.
                if getattr(self, 'last_trail_bar_time', None) != latest_completed_time:
                    self.last_trail_bar_time = latest_completed_time
                    
                    # Structural Trailing Stop
                    # Pass the last 3 completed bars to calculate_structural_trailing_stop
                    completed_candles = candles[:-1]  # Exclude the current open bar
                    new_sl = calculate_structural_trailing_stop(direction, self.sl_price, completed_candles, atr_list[-2])
                    
                    if new_sl and new_sl != self.sl_price:
                        logger.info(f'Trailing SL from {self.sl_price} to {new_sl}...')
                        self.sl_price = new_sl
                        if getattr(self, 'sl_order_id', None):
                            try:
                                self.client.cancel_order(self.symbol, self.sl_order_id)
                            except Exception as e:
                                logger.error(f'Failed to cancel old SL order: {e}')
                        try:
                            res = self.client.place_order(self.symbol, close_side, 'STOP_MARKET', pos_volume, stop_price=self.sl_price, positionSide=close_pos_side, closePosition=True)
                            self.sl_order_id = res.get('orderId')
                            logger.info(f'Successfully moved mechanical SL to {self.sl_price}')
                        except Exception as e:
                            logger.error(f'Failed to place new mechanical SL: {e}')
                            
        except Exception as e:
            logger.error(f'Error in tick: {e}', exc_info=True)

    def run(self):
        logger.info(f'Starting OdinDaemon for {self.symbol} with {self.risk_pct*100}% risk...')
        while True:
            self.tick()
            time.sleep(60)

if __name__ == '__main__':
    daemon = OdinDaemon()
    daemon.run()
