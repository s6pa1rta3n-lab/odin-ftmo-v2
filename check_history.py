import asyncio, json
from datetime import datetime, timedelta
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    start_time = datetime.utcnow() - timedelta(hours=2)
    history = await api.connection.get_history_orders_by_time_range(start_time, datetime.utcnow())
    deals = await api.connection.get_deals_by_time_range(start_time, datetime.utcnow())
    
    print("--- RECENT DEALS (Last 2 hours) ---")
    for d in deals:
        print(f"[{d.get('id')}] {d.get('symbol')} | {d.get('type')} | Lots: {d.get('volume')} | Price: {d.get('price')} | Profit: {d.get('profit')} | Comment: {d.get('comment')}")
        
    print("\n--- OPEN POSITIONS ---")
    positions = await api.connection.get_positions()
    for p in positions:
        print(f"[{p.get('id')}] {p.get('symbol')} | {p.get('type')} | Lots: {p.get('volume')} | Profit: {p.get('profit')}")

asyncio.run(main())
