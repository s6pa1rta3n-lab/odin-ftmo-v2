import asyncio
from metaapi_cloud_sdk import MetaApi
from datetime import datetime, timezone, timedelta
import json

async def main():
    token = json.load(open("config_us100.json"))["metaapi"]["token"]
    account_id = "37bee990-bc0e-4571-9470-51db1c192c7c"
    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()

    start = datetime.now(timezone.utc) - timedelta(days=30)
    end = datetime.now(timezone.utc)
    deals_response = await connection.get_deals_by_time_range(start, end)
    if isinstance(deals_response, dict):
        deals = deals_response.get("deals", [])
    elif isinstance(deals_response, list):
        deals = deals_response
    else:
        deals = []
    print("Raw deals count: {}".format(len(deals)))

    positions = {}
    for d in deals:
        pos_id = d.get("positionId")
        if not pos_id:
            continue
        if pos_id not in positions:
            positions[pos_id] = {
                "symbol": d.get("symbol", ""),
                "type": "",
                "profit": 0,
                "volume": 0,
                "open_time": None,
                "close_time": None,
                "comment": "",
                "commission": 0,
                "swap": 0,
            }
        entry = d.get("entryType", "")
        if entry == "DEAL_ENTRY_IN":
            positions[pos_id]["open_time"] = d.get("time", "")
            positions[pos_id]["type"] = d.get("type", "")
            positions[pos_id]["volume"] = d.get("volume", 0)
            positions[pos_id]["comment"] = d.get("comment", "")
        elif entry == "DEAL_ENTRY_OUT":
            positions[pos_id]["close_time"] = d.get("time", "")
            positions[pos_id]["profit"] += d.get("profit", 0)
        positions[pos_id]["commission"] += d.get("commission", 0)
        positions[pos_id]["swap"] += d.get("swap", 0)

    trades = [(v["open_time"], v) for v in positions.values() if v["open_time"]]
    trades.sort(key=lambda x: str(x[0]))

    print("DEAL HISTORY (Last 30 Days)")
    print("=" * 90)
    total_pnl = 0
    for _, t in trades:
        dt = str(t["open_time"])[:19] if t["open_time"] else "N/A"
        tp = "BUY" if "BUY" in str(t["type"]) else "SELL"
        net = t["profit"] + t["commission"] + t["swap"]
        total_pnl += net
        status = "CLOSED" if t["close_time"] else "OPEN"
        print("{:<22} {:<8} {:<14} vol={:<6.2f} gross={:>8.2f} comm={:>6.2f} net={:>8.2f} {} | {}".format(
            dt, tp, t["symbol"], t["volume"], t["profit"], t["commission"], net, status, t["comment"]
        ))

    print("=" * 90)
    print("Total Net PnL: ${:.2f}".format(total_pnl))
    print("Total Trades: {}".format(len(trades)))

    account_info = await connection.get_account_information()
    print("\nAccount Balance: ${:.2f}".format(account_info.get("balance", 0)))
    print("Account Equity: ${:.2f}".format(account_info.get("equity", 0)))

    await api.close()

asyncio.run(main())
