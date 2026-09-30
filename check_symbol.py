import asyncio
import json
from metaapi_cloud_sdk import MetaApi
import os
from datetime import datetime

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config.json', 'r') as f:
        config = json.load(f)
    token = config.get('metaapi', {}).get('token', '')
    account_id = config.get('metaapi', {}).get('accountId', '')
    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    
    symbol_info = await connection.get_symbol_specification('BTCUSD')
    print("SYMBOL INFO:", json.dumps(symbol_info, indent=2))
    
    price = await connection.get_symbol_price('BTCUSD')
    print("CURRENT PRICE:", price)
    
asyncio.run(main())
