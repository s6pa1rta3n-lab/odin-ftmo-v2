import re

with open("griff_engine_live.py", "r") as f:
    content = f.read()

# 1. fetch_positions_safe: return None instead of []
content = content.replace(
    'return positions or []\n\n    async def fetch_completed_1h_candles',
    'return positions\n\n    async def fetch_completed_1h_candles'
)

# 2. synchronize_active_positions: return bool
content = content.replace(
    'async def synchronize_active_positions(self) -> None:',
    'async def synchronize_active_positions(self) -> bool:'
)

# 3. Handle None in synchronize_active_positions
sync_body = """        positions = await self.fetch_positions_safe()
        if positions is None:
            logger.warning("Failed to sync positions. Skipping evaluation to prevent duplicate orders.")
            return False
            
        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol"""

content = content.replace(
    '        positions = await self.fetch_positions_safe()\n        mt5_sym = self.wrapper._to_mt5(self.symbol) if hasattr(self.wrapper, "_to_mt5") else self.symbol',
    sync_body
)

# 4. Return True at the end of synchronize_active_positions
content = re.sub(
    r'(        else:\n            if self\.state == "IN_TRADE":\n                logger\.info\("Active trade closed.*\n                self\.active_position = None\n                self\.state = "SEARCHING"\n)',
    r'\1        return True\n',
    content
)

# 5. step() aborts on False
step_call = """        if not await self.synchronize_active_positions():
            return {"status": "SKIPPED", "reason": "Failed to synchronize positions"}"""
            
content = content.replace(
    '        await self.synchronize_active_positions()',
    step_call
)

with open("griff_engine_live.py", "w") as f:
    f.write(content)

print("Patch applied.")
