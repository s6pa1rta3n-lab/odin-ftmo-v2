import asyncio, json
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    positions = await api.connection.get_positions()
    orders = await api.connection.get_orders()
    
    print("--- POSITIONS ---")
    for p in positions:
        print(f"[{p.get('id')}] {p.get('symbol')} | {p.get('type')} | Lots: {p.get('volume')} | Profit: {p.get('profit')}")
    if not positions: print("No open positions.")
        
    print("\n--- ORDERS ---")
    for o in orders:
        print(f"[{o.get('id')}] {o.get('symbol')} | {o.get('type')} | Lots: {o.get('volume')}")
    if not orders: print("No pending orders.")

asyncio.run(main())
