import asyncio
from MetaApiWrapper import MetaApiWrapper
import json
import os
import sys

async def main():
    with open("config_xau.json", "r") as f:
        conf = json.load(f)
    token = conf["metaapi_token"]
    wrapper = MetaApiWrapper(token=token, account_id="45a2565b-4f53-4bd5-8c58-667b3660430f")
    await wrapper.connect()
    
    for sym in ["XAUUSD", "BTCUSD", "US100.cash"]:
        try:
            spec = await wrapper.connection.get_symbol_specification(sym)
            print(f"--- {sym} ---")
            print(f"Contract Size: {spec.get('contractSize')}")
            print(f"Tick Size: {spec.get('tickSize')}")
            print(f"Tick Value (Profit): {spec.get('profitTickValue')}")
            print(f"Tick Value (Loss): {spec.get('lossTickValue')}")
        except Exception as e:
            print(f"Failed {sym}: {e}")
            
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
