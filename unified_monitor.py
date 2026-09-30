import asyncio
import json
import os
import subprocess
import sys
import time

# 1. Asterdex Telemetry
sys.path.insert(0, '/home/solveetcoagula/odin3.0')
from asterdex_client import AsterdexClient

aster_client = AsterdexClient()
acc = aster_client.get_account()
pos = aster_client.get_positions()

active_assets = []
true_equity = 0.0

for asset in acc.get('assets', []):
    wb = float(asset.get('walletBalance', 0.0))
    upnl = float(asset.get('unrealizedProfit', 0.0))
    mb = float(asset.get('marginBalance', 0.0))
    if wb != 0 or upnl != 0 or mb != 0:
        active_assets.append({
            'asset': asset.get('asset'),
            'wallet_balance': wb,
            'unrealized_profit': upnl,
            'margin_balance': mb,
            'cross_wallet_balance': float(asset.get('crossWalletBalance', 0.0))
        })
        true_equity += (wb + upnl)

active_positions = []
for p in pos:
    amt = float(p.get('positionAmt', 0.0))
    if amt != 0:
        entry = float(p.get('entryPrice', 0.0))
        mark = float(p.get('markPrice', 0.0) if 'markPrice' in p else 0.0)
        pnl = (mark - entry) * amt if mark > 0 else float(p.get('unrealizedProfit', 0.0))
        active_positions.append({
            'symbol': p.get('symbol'),
            'side': p.get('positionSide'),
            'amount': amt,
            'entry_price': entry,
            'mark_price': mark,
            'unrealized_pnl': pnl,
            'liquidation_price': float(p.get('liquidationPrice', 0.0) if 'liquidationPrice' in p else 0.0),
            'leverage': p.get('leverage'),
            'notional': float(p.get('notional', 0.0))
        })

# 2. FTMO Telemetry
sys.path.insert(0, '/home/solveetcoagula/odin_ftmo')
from MetaApiWrapper import MetaApiWrapper
from griff_engine_live import load_metaapi_token

async def get_ftmo():
    token = load_metaapi_token('/home/solveetcoagula/odin_ftmo/config_us100.json')
    wrapper = MetaApiWrapper(token, 'a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf')
    await wrapper.connect()
    info = await wrapper.get_account_information()
    positions = await wrapper.connection.get_positions()
    orders = await wrapper.connection.get_orders()
    try:
        await wrapper.connection.close()
    except Exception:
        pass
    return info, positions, orders

try:
    ftmo_info, ftmo_pos, ftmo_orders = asyncio.run(get_ftmo())
except Exception as e:
    ftmo_info = {'error': str(e)}
    ftmo_pos = []
    ftmo_orders = []

# 3. Systemd Service Status
service_status = subprocess.getoutput('systemctl is-active griff_engine_btc.service').strip()
latest_log = subprocess.getoutput('journalctl -u griff_engine_btc.service -n 5 --no-pager')

report = {
    'timestamp_utc': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
    'asterdex': {
        'true_total_equity': true_equity,
        'assets': active_assets,
        'positions': active_positions
    },
    'ftmo': {
        'account_info': ftmo_info,
        'open_positions': ftmo_pos,
        'open_orders': ftmo_orders,
        'engine_service_status': service_status,
        'engine_latest_logs': latest_log.splitlines()[-3:] if latest_log else []
    }
}

print('===UNIFIED_REPORT_BEGIN===')
print(json.dumps(report, indent=2))
print('===UNIFIED_REPORT_END===')
sys.stdout.flush()
os._exit(0)
