import asyncio, json, pytz
from datetime import datetime, timedelta
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    
    start_time = datetime.now(pytz.utc) - timedelta(days=5)
    deals_resp = await api.connection.get_deals_by_time_range(start_time, datetime.now(pytz.utc))
    deals = deals_resp.get('deals', []) if isinstance(deals_resp, dict) else deals_resp
    
    for d in deals:
        if d.get('positionId') == '290574452':
            print(d.get('time'), d.get('entryType'), d.get('type'))

asyncio.run(main())
