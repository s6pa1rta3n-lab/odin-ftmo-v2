import os
import re

def fix_file(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, "r") as f: content = f.read()
    
    content = content.replace(
        "self.wrapper.account.get_historical_candles(mt5_sym, '15m', startTime=None, limit=50)",
        "self.wrapper.account.get_historical_candles(mt5_sym, '15m')"
    )
    
    with open(filepath, "w") as f: f.write(content)

fix_file("griff_engine_us100.py")
fix_file("griff_engine_gold.py")
