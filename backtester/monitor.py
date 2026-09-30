import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta

async def main():
    from metaapi_cloud_sdk import MetaApi

    config = json.load(open("config_us100.json"))
    token = config["metaapi"]["token"]
    account_id = "37bee990-bc0e-4571-9470-51db1c192c7c"

    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()

    acct = await connection.get_account_information()
    positions = await connection.get_positions()
    orders = await connection.get_orders()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals_resp = await connection.get_deals_by_time_range(today_start, now)
    if isinstance(deals_resp, dict):
        deals = deals_resp.get("deals", [])
    elif isinstance(deals_resp, list):
        deals = deals_resp
    else:
        deals = []

    closed_positions = {}
    for d in deals:
        if not isinstance(d, dict):
            continue
        pos_id = d.get("positionId")
        if not pos_id:
            continue
        if pos_id not in closed_positions:
            closed_positions[pos_id] = {
                "symbol": d.get("symbol", ""),
                "type": "",
                "profit": 0,
                "volume": 0,
                "comment": "",
                "commission": 0,
                "swap": 0,
                "open_time": None,
                "close_time": None,
            }
        entry = d.get("entryType", "")
        if entry == "DEAL_ENTRY_IN":
            closed_positions[pos_id]["open_time"] = d.get("time", "")
            closed_positions[pos_id]["type"] = d.get("type", "")
            closed_positions[pos_id]["volume"] = d.get("volume", 0)
            closed_positions[pos_id]["comment"] = d.get("comment", "")
        elif entry == "DEAL_ENTRY_OUT":
            closed_positions[pos_id]["close_time"] = d.get("time", "")
            closed_positions[pos_id]["profit"] += d.get("profit", 0)
        closed_positions[pos_id]["commission"] += d.get("commission", 0)
        closed_positions[pos_id]["swap"] += d.get("swap", 0)

    balance = acct.get("balance", 0)
    equity = acct.get("equity", 0)
    margin = acct.get("margin", 0)
    free_margin = acct.get("freeMargin", 0)

    utc_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    london_active = 7 <= now.hour < 13
    omni_active = 14 <= now.hour < 20

    report = {}
    report["timestamp"] = utc_str
    report["balance"] = balance
    report["equity"] = equity
    report["margin"] = margin
    report["free_margin"] = free_margin
    report["distance_to_floor"] = equity - 90000
    report["distance_to_target"] = 110000 - equity
    report["daily_pnl"] = equity - 93837.35
    report["london_session"] = "ACTIVE" if london_active else "CLOSED"
    report["omni_session"] = "ACTIVE" if omni_active else "CLOSED"

    report["open_positions"] = []
    if isinstance(positions, list):
        for p in positions:
            if isinstance(p, dict):
                pos_data = {
                    "id": p.get("id"),
                    "symbol": p.get("symbol"),
                    "type": "LONG" if "BUY" in str(p.get("type", "")) else "SHORT",
                    "volume": p.get("volume"),
                    "entry_price": p.get("openPrice"),
                    "current_price": p.get("currentPrice"),
                    "stop_loss": p.get("stopLoss"),
                    "take_profit": p.get("takeProfit"),
                    "unrealized_pnl": p.get("unrealizedProfit", p.get("profit", 0)),
                    "comment": p.get("comment", p.get("brokerComment", "")),
                    "open_time": p.get("time"),
                }
                report["open_positions"].append(pos_data)

    report["pending_orders"] = []
    if isinstance(orders, list):
        for o in orders:
            if isinstance(o, dict):
                ord_data = {
                    "id": o.get("id"),
                    "symbol": o.get("symbol"),
                    "type": o.get("type"),
                    "volume": o.get("volume"),
                    "price": o.get("openPrice"),
                    "stop_loss": o.get("stopLoss"),
                    "comment": o.get("comment", o.get("brokerComment", "")),
                }
                report["pending_orders"].append(ord_data)

    report["todays_closed_trades"] = []
    for pos_id, t in closed_positions.items():
        if t.get("close_time"):
            net = t["profit"] + t["commission"] + t["swap"]
            report["todays_closed_trades"].append({
                "open_time": str(t["open_time"])[:19],
                "close_time": str(t["close_time"])[:19],
                "type": "LONG" if "BUY" in str(t["type"]) else "SHORT",
                "symbol": t["symbol"],
                "volume": t["volume"],
                "gross_pnl": round(t["profit"], 2),
                "net_pnl": round(net, 2),
                "comment": t["comment"],
            })

    today_net = sum(t["net_pnl"] for t in report["todays_closed_trades"])
    report["todays_realized_pnl"] = round(today_net, 2)
    report["todays_trade_count"] = len(report["todays_closed_trades"])

    print(json.dumps(report, indent=2, default=str))

    try:
        api.close()
    except:
        pass

asyncio.run(main())
