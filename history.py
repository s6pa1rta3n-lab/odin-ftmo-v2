import asyncio
import os
import json
from metaapi_cloud_sdk import MetaApi

async def main():
    with open('/Users/solveetcoagula/Desktop/google_cloud/config_us100.json', 'r') as f:
        cfg = json.load(f)
    api = MetaApi(cfg['metaapi']['token'])
    try:
        account = await api.metatrader_account_api.get_account(cfg['metaapi']['account_id'])
        initial_state = account.state
        if initial_state != 'DEPLOYED':
            await account.deploy()
        
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        from datetime import datetime, timedelta, timezone
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        
        deals = await connection.get_deals_by_time_range(start, end)
        for deal in deals:
            if deal.get('symbol') == 'US100.cash':
                print(f"Time: {deal.get('time')}, Type: {deal.get('type')}, Price: {deal.get('price')}, Vol: {deal.get('volume')}, PnL: {deal.get('profit')}, Reason: {deal.get('reason')}")
                
        if initial_state != 'DEPLOYED':
            await account.undeploy()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
