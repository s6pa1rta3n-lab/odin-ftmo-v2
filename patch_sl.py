import re

with open("griff_engine_live.py", "r") as f:
    code = f.read()

init_patch = """        self.wrapper = wrapper
        self.active_position = None
        self.highest_sl_memory = {}
"""
code = code.replace("        self.wrapper = wrapper\n        self.active_position = None\n", init_patch)

ratchet_patch = """        direction = self.active_position["direction"]
        current_sl = float(self.active_position.get("sl", 0.0))
        bar_close = float(completed_bar["close"])
        ticket_id = self.active_position.get("id")

        if not ticket_id:
            return

        memory_sl = self.highest_sl_memory.get(ticket_id, current_sl)
        if direction.upper() in ("BUY", "LONG"):
            effective_current_sl = max(current_sl, memory_sl) if current_sl > 0 else memory_sl
        else:
            if current_sl > 0 and memory_sl > 0:
                effective_current_sl = min(current_sl, memory_sl)
            else:
                effective_current_sl = current_sl if current_sl > 0 else memory_sl

        candidate_sl = calculate_trailing_stop(direction, effective_current_sl, bar_close, atr_14)

        if candidate_sl != effective_current_sl:
            logger.info(
                "Ratcheting Trailing Stop for ticket %s (%s) from %.2f to %.2f (Bar Close: %.2f, ATR: %.2f)",
                ticket_id,
                direction,
                effective_current_sl,
                candidate_sl,
                bar_close,
                atr_14,
            )
            try:
                await asyncio.wait_for(
                    self.wrapper.connection.modify_position(ticket_id, stop_loss=candidate_sl),
                    timeout=8.0,
                )
                self.active_position["sl"] = candidate_sl
                self.highest_sl_memory[ticket_id] = candidate_sl
            except Exception as err:
                logger.error("Failed to update trailing stop on ticket %s: %s", ticket_id, err)"""

old_ratchet = """        direction = self.active_position["direction"]
        current_sl = float(self.active_position.get("sl", 0.0))
        bar_close = float(completed_bar["close"])
        ticket_id = self.active_position.get("id")

        if not ticket_id:
            return

        candidate_sl = calculate_trailing_stop(direction, current_sl, bar_close, atr_14)

        if candidate_sl != current_sl:
            logger.info(
                "Ratcheting Trailing Stop for ticket %s (%s) from %.2f to %.2f (Bar Close: %.2f, ATR: %.2f)",
                ticket_id,
                direction,
                current_sl,
                candidate_sl,
                bar_close,
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

code = code.replace(old_ratchet, ratchet_patch)

with open("griff_engine_live.py", "w") as f:
    f.write(code)

