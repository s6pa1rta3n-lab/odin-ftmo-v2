"""Monitor script for the 3 concurrent Griff Trading Engines on GCP VM and MetaAPI FTMO account."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from MetaApiWrapper import MetaApiWrapper
from griff_engine_live import load_metaapi_token

TARGET_ACCOUNT_ID = "6ccd891f-8728-4e37-ad41-1e695c6008ef"
TARGET_LOGIN = 1514659088
CONFIG_PATH = "config_us100.json"
GCP_VM_NAME = "matt-berserker"
GCP_VM_ZONE = "us-central1-a"
GCP_PROJECT = "project-45c3b27c-b597-4704-a50"
GCP_ACCOUNT = "reemanos8422@gmail.com"

MONITORED_SERVICES = {
    "griff_engine.service": "US100",
    "griff_engine_btc.service": "BTCUSD",
    "griff_engine_xau.service": "XAUUSD",
}


def get_all_services_status() -> Dict[str, Dict[str, Any]]:
    """Retrieve systemd status, properties, and recent journal log lines for all monitored services on GCP VM.

    Returns:
        Dictionary mapping service unit names to their active status, PID, and latest journal log snippets.
    """
    env = os.environ.copy()
    env["CLOUDSDK_METRICS_ENVIRONMENT"] = "datacloud.antigravity"

    services_data: Dict[str, Dict[str, Any]] = {}
    service_names = list(MONITORED_SERVICES.keys())

    sub_commands = []
    for srv in service_names:
        sub_commands.append(
            f"echo '###SRV_START:{srv}###' && systemctl is-active {srv} && systemctl show {srv} --property=ActiveState,SubState,MainPID && echo '###LOGS_START###' && journalctl -u {srv} -n 4 --no-pager && echo '###SRV_END###'"
        )

    full_cmd_str = " && ".join(sub_commands)

    if os.path.exists("/bin/systemctl") or os.path.exists("/usr/bin/systemctl"):
        cmd = ["/bin/bash", "-c", full_cmd_str]
    else:
        cmd = [
            "gcloud",
            "compute",
            "ssh",
            GCP_VM_NAME,
            f"--zone={GCP_VM_ZONE}",
            f"--project={GCP_PROJECT}",
            f"--account={GCP_ACCOUNT}",
            f"--command={full_cmd_str}",
        ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25,
            env=env,
        )
        stdout = proc.stdout

        for srv in service_names:
            start_tag = f"###SRV_START:{srv}###"
            end_tag = "###SRV_END###"
            if start_tag not in stdout:
                services_data[srv] = {
                    "asset": MONITORED_SERVICES[srv],
                    "is_active": False,
                    "active_state": "missing",
                    "sub_state": "unknown",
                    "main_pid": "unknown",
                    "recent_logs": [],
                }
                continue

            after_start = stdout.split(start_tag, 1)[1]
            block = after_start.split(end_tag, 1)[0].strip()

            lines = [line.strip() for line in block.splitlines() if line.strip()]
            is_active = any(line == "active" for line in lines[:3])
            active_state = "unknown"
            sub_state = "unknown"
            main_pid = "unknown"
            recent_logs = []

            in_logs = False
            for line in lines:
                if line == "###LOGS_START###":
                    in_logs = True
                    continue
                if in_logs:
                    if not line.startswith("-- Journal begins"):
                        recent_logs.append(line)
                elif "=" in line:
                    k, v = line.split("=", 1)
                    if k == "ActiveState":
                        active_state = v
                    elif k == "SubState":
                        sub_state = v
                    elif k == "MainPID":
                        main_pid = v

            services_data[srv] = {
                "asset": MONITORED_SERVICES[srv],
                "is_active": is_active,
                "active_state": active_state,
                "sub_state": sub_state,
                "main_pid": main_pid,
                "recent_logs": recent_logs[-3:],
            }

    except Exception as exc:
        for srv in service_names:
            services_data[srv] = {
                "asset": MONITORED_SERVICES[srv],
                "is_active": False,
                "active_state": "error",
                "sub_state": str(exc),
                "main_pid": "unknown",
                "recent_logs": [],
            }

    return services_data


async def fetch_metaapi_telemetry() -> Dict[str, Any]:
    """Connect to MetaAPI FTMO account and extract equity, balance, positions, and pending orders for target assets.

    Returns:
        Dictionary containing account info and asset-specific position/unrealized PnL and pending order mappings.
    """
    token = load_metaapi_token(CONFIG_PATH)
    wrapper = MetaApiWrapper(token, TARGET_ACCOUNT_ID)
    await wrapper.connect()

    account_info = await wrapper.get_account_information()
    positions = await wrapper.connection.get_positions()
    orders = await wrapper.connection.get_orders()

    asset_positions: Dict[str, List[Dict[str, Any]]] = {
        "US100": [],
        "BTCUSD": [],
        "XAUUSD": [],
    }
    asset_orders: Dict[str, List[Dict[str, Any]]] = {
        "US100": [],
        "BTCUSD": [],
        "XAUUSD": [],
    }

    for pos in positions:
        sym = pos.get("symbol", "")
        pos_data = {
            "id": pos.get("id"),
            "symbol": sym,
            "type": pos.get("type"),
            "volume": pos.get("volume"),
            "openPrice": pos.get("openPrice"),
            "currentPrice": pos.get("currentPrice"),
            "stopLoss": pos.get("stopLoss"),
            "unrealizedProfit": pos.get("unrealizedProfit"),
            "profit": pos.get("profit"),
            "commission": pos.get("commission"),
            "comment": pos.get("comment"),
        }
        if "US100" in sym:
            asset_positions["US100"].append(pos_data)
        elif "BTC" in sym:
            asset_positions["BTCUSD"].append(pos_data)
        elif "XAU" in sym:
            asset_positions["XAUUSD"].append(pos_data)

    for ord_ in orders:
        sym = ord_.get("symbol", "")
        ord_data = {
            "id": ord_.get("id"),
            "symbol": sym,
            "type": ord_.get("type"),
            "volume": ord_.get("volume"),
            "openPrice": ord_.get("openPrice"),
            "stopLoss": ord_.get("stopLoss"),
            "comment": ord_.get("comment"),
        }
        if "US100" in sym:
            asset_orders["US100"].append(ord_data)
        elif "BTC" in sym:
            asset_orders["BTCUSD"].append(ord_data)
        elif "XAU" in sym:
            asset_orders["XAUUSD"].append(ord_data)

    return {
        "account": {
            "id": TARGET_ACCOUNT_ID,
            "login": account_info.get("login"),
            "server": account_info.get("server"),
            "equity": account_info.get("equity"),
            "balance": account_info.get("balance"),
            "margin": account_info.get("margin"),
            "freeMargin": account_info.get("freeMargin"),
            "marginLevel": account_info.get("marginLevel"),
        },
        "total_positions_count": len(positions),
        "total_orders_count": len(orders),
        "asset_positions": asset_positions,
        "asset_orders": asset_orders,
    }


async def main_async() -> None:
    """Run full multi-service diagnostic cycle and print structured JSON telemetry."""
    services_status = get_all_services_status()
    meta_telemetry = await fetch_metaapi_telemetry()

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "services_status": services_status,
        "telemetry": meta_telemetry,
    }

    print("--- TELEMETRY_JSON_START ---", flush=True)
    print(json.dumps(result, indent=2), flush=True)
    print("--- TELEMETRY_JSON_END ---", flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main_async())
