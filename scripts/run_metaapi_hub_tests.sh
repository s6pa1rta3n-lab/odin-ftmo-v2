#!/bin/sh
# Run the MetaAPI hub suite and the in-process shadow probe.
# Does not contact MetaAPI, does not read config tokens, does not place orders.
# Does not start a hub process and does not change systemd.
set -eu
cd "$(dirname "$0")/.."
unset ODIN_METAAPI_HUB
unset ODIN_METAAPI_HUB_ORDERS
python3 -V
python3 -m pytest tests/metaapi_hub -q
python3 -m metaapi_hub.shadow_probe >/tmp/odin-metaapi-hub-shadow-probe.json
python3 -c 'import json; data=json.load(open("/tmp/odin-metaapi-hub-shadow-probe.json")); assert data["ok"] is True; snap=data["snapshot"]; assert snap["synchronize_calls"]==1; assert snap["broker_order_calls"]==0; assert snap["orders_live"] is False; print("shadow probe ok", snap["synchronize_calls"], "orders", snap["broker_order_calls"])'
