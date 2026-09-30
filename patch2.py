import re

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'return {"status": "SEARCHING", "atr_14": atr_14, "equity": self.current_equity}' in line:
        indent = line[:len(line) - len(line.lstrip())]
        replacement = f"""{indent}state_dump = {{
{indent}    "state": self.state,
{indent}    "equity": self.current_equity,
{indent}    "active_position": self.active_position,
{indent}    "pending_buy_order_id": self.pending_buy_order_id,
{indent}    "pending_sell_order_id": self.pending_sell_order_id,
{indent}    "pending_setup_bar_time": self.pending_setup_bar_time.isoformat() if hasattr(self.pending_setup_bar_time, "isoformat") else self.pending_setup_bar_time,
{indent}}}
{indent}import json
{indent}with open("/home/solveetcoagula/odin_ftmo/live_state.json", "w") as f:
{indent}    json.dump(state_dump, f)
{indent}return {{"status": self.state, "atr_14": atr_14, "equity": self.current_equity}}
"""
        lines[i] = replacement
        break

with open('/home/solveetcoagula/odin_ftmo/griff_engine_live.py', 'w') as f:
    f.writelines(lines)
