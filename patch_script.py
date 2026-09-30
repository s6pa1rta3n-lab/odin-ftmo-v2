import re

with open('/Users/solveetcoagula/Desktop/google_cloud/griff_engine_live.py', 'r') as f:
    content = f.read()

# Add EMA calculation helper
ema_helper = """
def compute_ema_50(candles: List[Dict[str, Any]]) -> float:
    \"\"\"Calculate 50-period Exponential Moving Average.\"\"\"
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
    \"\"\"Calculate structural trailing stop loss using 1H swing points.\"\"\"
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
"""

# Insert helpers after compute_atr_14
content = re.sub(
    r'(def is_inside_bar)',
    ema_helper.strip() + '\n\n\n\\1',
    content
)

# Update ratchet_trailing_stop to use candles and the new function
new_ratchet = """    async def ratchet_trailing_stop(self, candles: List[Dict[str, Any]], atr_14: float) -> None:
        \"\"\"Evaluate structural trailing stop ratchet upon 1H bar close.

        Args:
            candles: List of historical completed candles.
            atr_14: Current 14-period ATR.
        \"\"\"
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
                logger.error("Failed to update trailing stop on ticket %s: %s", ticket_id, err)"""

content = re.sub(
    r'    async def ratchet_trailing_stop\(self, completed_bar: Dict\[str, Any\], atr_14: float\) -> None:.*?            except Exception as err:\n                logger\.error\("Failed to update trailing stop on ticket %s: %s", ticket_id, err\)',
    new_ratchet,
    content,
    flags=re.DOTALL
)

# Modify step() logic
new_step = """        candles = await self.fetch_completed_1h_candles(limit=60)
        if len(candles) < 50:
            logger.info("Accumulating history: %d/50 required completed 1H candles", len(candles))
            return {"status": "ACCUMULATING_HISTORY", "count": len(candles)}

        atr_14 = compute_atr_14(candles)
        ema_50 = compute_ema_50(candles)
        latest_completed_bar = candles[-1]
        latest_bar_time = latest_completed_bar.get("time")

        if self.state == "IN_TRADE" and self.active_position:
            if self.last_evaluated_bar_time != latest_bar_time:
                await self.ratchet_trailing_stop(candles, atr_14)
                self.last_evaluated_bar_time = latest_bar_time
            return {"status": "IN_TRADE", "position": self.active_position, "atr_14": atr_14}

        if self.state == "PENDING_PLACED":
            if self.pending_setup_bar_time and latest_bar_time != self.pending_setup_bar_time:
                logger.info("Breakout window for setup bar %s expired unfilled. Canceling pending orders.", self.pending_setup_bar_time)
                await self.cancel_pending_breakout_orders()
                self.state = "SEARCHING"

        if self.state == "SEARCHING":
            mother_bar = candles[-2]
            current_bar = candles[-1]
            if is_inside_bar(current_bar, mother_bar):
                # MACRO-TREND FILTER (50 EMA)
                close_price = float(current_bar["close"])
                trend_direction = "BUY" if close_price > ema_50 else "SELL"
                
                logger.info("Inside Bar confirmed on bar %s. Macro Trend: %s (EMA50: %.2f)", latest_bar_time, trend_direction, ema_50)
                
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
                )"""

content = re.sub(
    r'        candles = await self\.fetch_completed_1h_candles\(limit=30\).*?atr_14,\n                \)',
    new_step,
    content,
    flags=re.DOTALL
)

# Now update place_pending_breakout_orders to accept trend_direction
new_place = """    async def place_pending_breakout_orders(
        self,
        inside_bar: Dict[str, Any],
        atr_14: float,
        equity: float,
        trend_direction: str = "BOTH",
    ) -> bool:"""
    
content = content.replace(
    """    async def place_pending_breakout_orders(
        self,
        inside_bar: Dict[str, Any],
        atr_14: float,
        equity: float,
    ) -> bool:""",
    new_place
)

# Inside place_pending_breakout_orders, conditionally place BUY or SELL
new_place_orders = """        try:
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
                    logger.info("Sell Stop submitted at %.2f with SL %.2f (Order ID: %s)", sell_price, sell_sl, sell_order_id)"""

content = re.sub(
    r'        try:\n            if hasattr\(self\.wrapper, "connection"\) and self\.wrapper\.connection:\n                opts = \{"comment": self\.order_comment\}.*?logger\.info\("Sell Stop submitted at %\.2f with SL %\.2f \(Order ID: %s\)", sell_price, sell_sl, sell_order_id\)',
    new_place_orders,
    content,
    flags=re.DOTALL
)

with open('/Users/solveetcoagula/Desktop/google_cloud/griff_engine_live.py', 'w') as f:
    f.write(content)
