import re

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'r') as f:
    content = f.read()

# 1. Remove CancelledError block in run_loop
content = re.sub(
    r'except asyncio\.CancelledError:\s+logger\.error\(\"Task cancelled[^\"]+\"\)\s+continue',
    '',
    content
)

# 2. In place_pending_breakout_orders, update self.pending_orders
content = content.replace(
    'self.pending_buy_order_id = buy_order_id\n        self.pending_sell_order_id = sell_order_id',
    'self.pending_buy_order_id = buy_order_id\n        self.pending_sell_order_id = sell_order_id\n        self.pending_orders = []\n        if buy_order_id:\n            self.pending_orders.append({"id": buy_order_id, "type": "STOP_BUY", "price": buy_price, "sl": buy_sl, "volume": lots})\n        if sell_order_id:\n            self.pending_orders.append({"id": sell_order_id, "type": "STOP_SELL", "price": sell_price, "sl": sell_sl, "volume": lots})'
)

# 3. Add live_state.json persistence at the end of step()
replacement_end_of_step = '''
        state_dump = {
            "state": self.state,
            "equity": self.current_equity,
            "active_position": self.active_position,
            "pending_buy_order_id": self.pending_buy_order_id,
            "pending_sell_order_id": self.pending_sell_order_id,
            "pending_setup_bar_time": self.pending_setup_bar_time.isoformat() if hasattr(self.pending_setup_bar_time, "isoformat") else self.pending_setup_bar_time,
        }
        import json
        with open("/home/solveetcoagula/odin_ftmo/live_state.json", "w") as f:
            json.dump(state_dump, f)

        return {"status": self.state}

    async def cancel_pending_breakout_orders(self) -> None:'''

content = content.replace(
    '        return {"status": "SEARCHING"}\n\n    async def cancel_pending_breakout_orders(self) -> None:',
    replacement_end_of_step
)

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'w') as f:
    f.write(content)
