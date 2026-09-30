import asyncio, json, pytz
from datetime import datetime, timedelta
from MetaApiWrapper import MetaApiWrapper

async def main():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f: conf = json.load(f)
    api = MetaApiWrapper(conf['metaapi']['token'], conf['metaapi']['account_id'])
    await api.connect()
    start_time = datetime.now(pytz.utc) - timedelta(days=90)
    deals_resp = await api.connection.get_deals_by_time_range(start_time, datetime.now(pytz.utc))
    
    deals = deals_resp.get('deals', []) if isinstance(deals_resp, dict) else deals_resp
    
    positions = {}
    for d in sorted(deals, key=lambda x: x.get('time', datetime.min.replace(tzinfo=pytz.utc))):
        pos_id = d.get('positionId')
        if not pos_id: continue
        if pos_id not in positions:
            positions[pos_id] = {'symbol': d.get('symbol'), 'open_time': None, 'close_time': None, 'profit': 0.0, 'deals': 0}
        
        deal_time = d.get('time')
        # make sure it is timezone aware
        if deal_time and deal_time.tzinfo is None:
            deal_time = deal_time.replace(tzinfo=pytz.utc)
            
        entry_type = d.get('entryType')
        if entry_type == 'DEAL_ENTRY_IN' or positions[pos_id]['open_time'] is None:
            if positions[pos_id]['open_time'] is None or deal_time < positions[pos_id]['open_time']:
                positions[pos_id]['open_time'] = deal_time
        
        if entry_type == 'DEAL_ENTRY_OUT' or entry_type == 'DEAL_ENTRY_INOUT':
            if positions[pos_id]['close_time'] is None or deal_time > positions[pos_id]['close_time']:
                positions[pos_id]['close_time'] = deal_time
        
        positions[pos_id]['profit'] += float(d.get('profit', 0.0))
        positions[pos_id]['deals'] += 1

    failed_closes = []
    for pid, p in positions.items():
        if not p['open_time'] or not p['close_time']: continue
        duration = p['close_time'] - p['open_time']
        if duration > timedelta(hours=10):
            failed_closes.append((pid, p['symbol'], p['open_time'], p['close_time'], duration, p['profit']))
    
    print(f'Total positions analyzed: {len(positions)}')
    print(f'Positions held longer than 10 hours: {len(failed_closes)}')
    for f in failed_closes:
        print(f'Pos {f[0]} | {f[1]} | Open: {f[2]} | Close: {f[3]} | Duration: {f[4]} | PnL: ${f[5]:.2f}')

asyncio.run(main())
