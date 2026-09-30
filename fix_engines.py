import os
import re

def fix_file(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, "r") as f: content = f.read()
    
    content = re.sub(
        r"self\.wrapper\.connection\.get_historical_candles\(mt5_sym, '15m', startTime=None, limit=50\)",
        r"self.wrapper.account.get_historical_candles(mt5_sym, '15m', startTime=None, limit=50)",
        content
    )
    
    with open(filepath, "w") as f: f.write(content)

fix_file("griff_engine_us100.py")
fix_file("griff_engine_gold.py")
