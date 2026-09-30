import re

with open('griff_engine_live.py', 'r') as f:
    content = f.read()

# 1. Remove the bad json dump from the end of step
bad_json = """        state_dump = {
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

        return {"status": self.state, "atr_14": atr_14, "equity": self.current_equity}"""
content = content.replace(bad_json, '        return {"status": "SEARCHING", "atr_14": atr_14, "equity": self.current_equity}')

# 2. Add the json dump to run_loop
good_json = """            try:
                await self.step()
                import json
                state_dump = {
                    "state": self.state,
                    "equity": self.current_equity,
                    "active_position": self.active_position,
                    "pending_buy_order_id": self.pending_buy_order_id,
                    "pending_sell_order_id": self.pending_sell_order_id,
                    "pending_setup_bar_time": self.pending_setup_bar_time.isoformat() if hasattr(self.pending_setup_bar_time, "isoformat") else self.pending_setup_bar_time,
                }
                with open("/home/solveetcoagula/odin_ftmo/live_state.json", "w") as f:
                    json.dump(state_dump, f)
            except Exception as err:"""
content = content.replace("""            try:
                await self.step()
            except Exception as err:""", good_json)

with open('griff_engine_live_fixed.py', 'w') as f:
    f.write(content)
