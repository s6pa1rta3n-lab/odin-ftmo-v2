import asyncio, json
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    orders = await api.connection.get_orders()
    for o in orders:
        print(f"[{o.get('id')}] {o.get('symbol')} | {o.get('type')} | Lots: {o.get('volume')} | Open Price: {o.get('openPrice')} | SL: {o.get('stopLoss')}")

asyncio.run(main())
