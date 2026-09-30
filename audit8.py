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

    eod_breaches = []
    for pid, p in positions.items():
        if not p['open_time'] or not p['close_time']: continue
        
        # A position breaches EOD if it is open past 20:55 UTC.
        # We can check this by seeing if the time span between open and close includes 20:55 UTC of the open_time's day
        # OR if it just closed on a different day.
        
        open_t = p['open_time']
        close_t = p['close_time']
        
        # Create a datetime for 20:55 UTC on the same day it opened
        eod_cutoff = open_t.replace(hour=20, minute=55, second=0, microsecond=0)
        
        # If it was opened before 20:55, but closed after 20:55
        if open_t < eod_cutoff and close_t > eod_cutoff:
            eod_breaches.append(p)
            continue
            
        # If it was opened after 20:55 but before midnight, and closed the next day
        if open_t.hour >= 21 and close_t.date() > open_t.date():
            eod_breaches.append(p)
            continue

    print(f'Total positions analyzed: {len(positions)}')
    print(f'Positions held past US session close (20:55 UTC): {len(eod_breaches)}')
    for p in eod_breaches:
        print(f"Sym: {p['symbol']} | Open: {p['open_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC | Close: {p['close_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC | PnL: ${p['profit']:.2f}")

asyncio.run(main())
