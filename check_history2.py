import asyncio, json
from datetime import datetime, timedelta
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    start_time = datetime.utcnow() - timedelta(hours=2)
    deals = await api.connection.get_deals_by_time_range(start_time, datetime.utcnow())
    print(deals)

asyncio.run(main())
