import re

with open('/tmp/odin_daemon.py', 'r') as f:
    content = f.read()

# Add compute_ema and calculate_structural_trailing_stop
helpers = """
def compute_ema(candles, period=50):
    closes = [float(c['close']) for c in candles[-period:]]
    if not closes: return 0.0
    ema = closes[0]
    multiplier = 2 / (period + 1)
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_structural_trailing_stop(direction, current_sl, candles, atr_14):
    c1, c2, c3 = candles[-1], candles[-2], candles[-3]
    if direction == "BUY":
        if float(c1["low"]) > float(c2["low"]) > float(c3["low"]) and float(c1["close"]) > float(c2["high"]):
            proposed_sl = float(c2["low"]) - (0.5 * atr_14)
            return round(max(proposed_sl, current_sl), 2)
    elif direction == "SELL":
        if float(c1["high"]) < float(c2["high"]) < float(c3["high"]) and float(c1["close"]) < float(c2["low"]):
            proposed_sl = float(c2["high"]) + (0.5 * atr_14)
            return round(min(proposed_sl, current_sl), 2)
    return current_sl

"""

# Insert helpers after compute_atr if not present
if "def compute_ema" not in content:
    content = content.replace("def is_inside_bar", helpers + "def is_inside_bar")

# Change fetch_klines to 60
content = content.replace("fetch_klines(self.symbol, '1h', 20)", "fetch_klines(self.symbol, '1h', 60)")
content = content.replace("len(candles) < 16", "len(candles) < 55")

# Update SEARCHING state
old_searching = """                        buy_price = prev_bar['high']
                        sell_price = prev_bar['low']
                        
                        logger.info(f'Inside Bar found. Placing STOP orders at High: {buy_price}, Low: {sell_price} (Vol: {volume})')
                        
                        try:
                            res_buy = self.client.place_order(self.symbol, 'BUY', 'STOP_MARKET', volume, stop_price=buy_price, positionSide='LONG')
                            self.buy_order_id = res_buy.get('orderId')
                            
                            res_sell = self.client.place_order(self.symbol, 'SELL', 'STOP_MARKET', volume, stop_price=sell_price, positionSide='SHORT')
                            self.sell_order_id = res_sell.get('orderId')
                            
                            self.state = 'PENDING'
                            self.pending_setup_bar_time = latest_completed_time
                        except Exception as e:
                            logger.error(f'Failed to place orders: {e}')
                            self._cancel_orders()"""

new_searching = """                        buy_price = prev_bar['high']
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
                            self._cancel_orders()"""

content = content.replace(old_searching, new_searching)

# Update IN_TRADE trailing stop
old_trailing = """                # We only trail the stop every 1H close.
                if getattr(self, 'last_trail_bar_time', None) != latest_completed_time:
                    self.last_trail_bar_time = latest_completed_time
                    dist = 1.5 * atr_list[-2]
                    new_sl = None
                    if direction == 'BUY':
                        proposed_sl = round(prev_bar["close"] - dist, 1)
                        if proposed_sl > self.sl_price:
                            new_sl = proposed_sl
                    else:
                        proposed_sl = round(prev_bar["close"] + dist, 1)
                        if proposed_sl < self.sl_price:
                            new_sl = proposed_sl"""

new_trailing = """                # We only trail the stop every 1H close.
                if getattr(self, 'last_trail_bar_time', None) != latest_completed_time:
                    self.last_trail_bar_time = latest_completed_time
                    
                    # Structural Trailing Stop
                    # Pass the last 3 completed bars to calculate_structural_trailing_stop
                    completed_candles = candles[:-1]  # Exclude the current open bar
                    new_sl = calculate_structural_trailing_stop(direction, self.sl_price, completed_candles, atr_list[-2])
                    
                    if new_sl != self.sl_price:"""

content = content.replace(old_trailing, new_trailing)

with open('/tmp/odin_daemon.py', 'w') as f:
    f.write(content)

print("Patch applied to /tmp/odin_daemon.py")
