#!/bin/sh
# Run the MetaAPI hub suite and the in-process shadow probe.
# Does not contact MetaAPI, does not read config tokens, does not place orders.
set -eu
cd "$(dirname "$0")/.."
python3 -m pytest tests/metaapi_hub -q
python3 -m metaapi_hub.shadow_probe >/tmp/odin-metaapi-hub-shadow-probe.json
python3 -c 'import json; data=json.load(open("/tmp/odin-metaapi-hub-shadow-probe.json")); assert data["ok"] is True; print("shadow probe ok", data["snapshot"]["synchronize_calls"])'
