import asyncio
import json
from datetime import datetime, timedelta, timezone
from metaapi_cloud_sdk import MetaApi

async def main():
    token = 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiI4OWM2YmEzNGVlYWM2MWVhMTZkNTc3YTA2NTQ1YzFjNSIsImFjY2Vzc1J1bGVzIjpbeyJpZCI6InRyYWRpbmctYWNjb3VudC1tYW5hZ2VtZW50LWFwaSIsIm1ldGhvZHMiOlsidHJhZGluZy1hY2NvdW50LW1hbmFnZW1lbnQtYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVzdC1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcnBjLWFwaSIsIm1ldGhvZHMiOlsibWV0YWFwaS1hcGk6d3M6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVhbC10aW1lLXN0cmVhbWluZy1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOndzOnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJtZXRhc3RhdHMtYXBpIiwibWV0aG9kcyI6WyJtZXRhc3RhdHMtYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6InJpc2stbWFuYWdlbWVudC1hcGkiLCJtZXRob2RzIjpbInJpc2stbWFuYWdlbWVudC1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoiY29weWZhY3RvcnktYXBpIiwibWV0aG9kcyI6WyJjb3B5ZmFjdG9yeS1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoibXQtbWFuYWdlci1hcGkiLCJtZXRob2RzIjpbIm10LW1hbmFnZXItYXBpOnJlc3Q6ZGVhbGluZzoqOioiLCJtdC1tYW5hZ2VyLWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJiaWxsaW5nLWFwaSIsIm1ldGhvZHMiOlsiYmlsbGluZy1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfV0sImlnbm9yZVJhdGVMaW1pdHMiOmZhbHNlLCJ0b2tlbklkIjoiMjAyMTAyMTMiLCJpbXBlcnNvbmF0ZWQiOmZhbHNlLCJyZWFsVXNlcklkIjoiODljNmJhMzRlZWFjNjFlYTE2ZDU3N2EwNjU0NWMxYzUiLCJpYXQiOjE3ODQwNDE0NjV9.OA2jO5kUtt2kjp-OEfF4P6nYSea82bJo1xUhIAsVOHBhVJUo4Me3visIU8C5imCrvJ-yLRONEZGycyFvUKMBgzmobCPTW_-1Slx3tt8aWTgpDZyKLXHOIr0UCV4k787OrGPzqS5ViGmHMfzlvJdW9W8cMXvnz4vSUc0-uiiNuFXKIxSGMQQf55SHi9asfs8PUPEUbu4dzzlJ8ttcz6NEFJ1SdJLFKiwalDex6-qr0NVjebvZBRNoaY8H9H45ksNW7bhjUYs58y70Dx5bSt0O4PhspWVIj6v6nYpKlHr9pYKa9piHV9J7bMKhKCJXdEGCGj8ezQSeeiMjJusx1sjg4wmwIgfLvB-7GlRbiq-GoDqOZbOILsUJyJHUAffB6ofl_BrlEVoyJBn1nkAwtovfHHEBwkay8L0o5nFPhAxFea_DPHsXNIQuknaNIjfL-uAJbejuFwSmU3KusRuVR2ZdqEDRm1c1rRWMbCeHToreHoVtDmJ4jpEh5Rg7CdVXQ1nkbR1FajFAz1JV90Ji0DJ_N3EPJ8f4VBpayGOmO83LfZJQJNDa_xkJIemAGLl0bUSkV19GXHjoNdTMJpIzGq0TUV1zfM8A85Tp5HcdrbcnrEBcW7P-GbKh0OUUaSPxEPihpzAYQyvC_K_joAPFZuaSRJVAxsNMqG5lInHSLDyoevg'
    account_id = '37bee990-bc0e-4571-9470-51db1c192c7c'
    
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        if account.state != 'DEPLOYED':
            await account.deploy()
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        start = datetime.now(timezone.utc) - timedelta(days=90)
        end = datetime.now(timezone.utc)
        
        deals = await connection.get_deals_by_time_range(start, end)
        
        positions = {}
        for d in deals:
            pos_id = d.get('positionId')
            if not pos_id: continue
            if pos_id not in positions:
                positions[pos_id] = {'symbol': d.get('symbol'), 'open_time': None, 'close_time': None, 'profit': 0, 'deals': 0}
            
            deal_time_str = d.get('time')
            try:
                deal_time = datetime.strptime(deal_time_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            except:
                try:
                    deal_time = datetime.strptime(deal_time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                except:
                    continue
                
            entry_type = d.get('entryType')
            if entry_type == 'DEAL_ENTRY_IN' or positions[pos_id]['open_time'] is None:
                if positions[pos_id]['open_time'] is None or deal_time < positions[pos_id]['open_time']:
                    positions[pos_id]['open_time'] = deal_time
            
            if entry_type == 'DEAL_ENTRY_OUT' or entry_type == 'DEAL_ENTRY_INOUT':
                if positions[pos_id]['close_time'] is None or deal_time > positions[pos_id]['close_time']:
                    positions[pos_id]['close_time'] = deal_time
            
            positions[pos_id]['profit'] += d.get('profit', 0)
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

    except Exception as e:
        print(f'Error: {e}')

asyncio.run(main())
