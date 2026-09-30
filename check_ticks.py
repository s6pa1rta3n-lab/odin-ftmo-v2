import asyncio, json, pytz
from datetime import datetime, timedelta
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    print("Connected.")
    # In MetaApi, getting historical ticks is via get_historical_market_data or something?
    # Or just getting symbols to see the schedule?
    sym = await api.connection.get_symbol_specification('US100.cash')
    print("Sessions:")
    for sess in sym.get('sessions', []):
        print(sess)
        
asyncio.run(main())
