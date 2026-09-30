import asyncio
from metaapi_cloud_sdk import MetaApi
import sys
import json

async def main():
    with open('config_us100.json', 'r') as f:
        cfg = json.load(f)
    api = MetaApi(cfg['metaapi']['token'])
    
    ACCOUNT_ID = "6ccd891f-8728-4e37-ad41-1e695c6008ef"
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    
    positions = await connection.get_positions()
    for p in positions:
        print(f"POSITION: {p.get('symbol')} {p.get('volume')} @ {p.get('openPrice')} (Current: {p.get('currentPrice')}) -> PnL: {p.get('unrealizedProfit')} | SL: {p.get('stopLoss')}")
        
    orders = await connection.get_orders()
    for o in orders:
        print(f"ORDER: {o.get('symbol')} {o.get('type')} {o.get('volume')} @ {o.get('openPrice')} | SL: {o.get('stopLoss')}")
        
    info = await connection.get_account_information()
    print(f"EQUITY: {info.get('equity')}")
    
    await connection.close()
    
asyncio.run(main())
