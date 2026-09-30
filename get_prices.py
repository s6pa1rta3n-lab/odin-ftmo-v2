import asyncio
from metaapi_cloud_sdk import MetaApi
import os
import json

async def main():
    api = MetaApi("cc6fbaf9-f060-4963-8a30-36a44a1bb37f") # from monitor_griff.py / state
    acc = await api.metatrader_account_api.get_account("37bc945f-49b4-4ae4-954d-30a8f6675fbc")
    conn = acc.get_rpc_connection()
    await conn.connect()
    await conn.wait_synchronized()
    
    btc = await conn.get_symbol_price("BTCUSD")
    us100 = await conn.get_symbol_price("US100.cash")
    
    print("BTCUSD:", btc)
    print("US100.cash:", us100)

asyncio.run(main())
