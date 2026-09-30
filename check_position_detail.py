import asyncio, json
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    positions = await api.connection.get_positions()
    for p in positions:
        print(f"[{p.get('id')}] {p.get('symbol')} | {p.get('type')} | Lots: {p.get('volume')} | Open: {p.get('openPrice')} | SL: {p.get('stopLoss')} | TP: {p.get('takeProfit')} | Profit: {p.get('profit')} | Comment: {p.get('comment')}")

asyncio.run(main())
