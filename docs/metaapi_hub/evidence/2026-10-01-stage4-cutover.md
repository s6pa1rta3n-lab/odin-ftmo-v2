# MetaAPI Hub Production Cutover — PASS

Copied from the operator report for version control. This file does not contain a MetaAPI token. The report says the token was never logged; the hub reads it from the live `config_us100.json` only. This commit records the report. It does not change the VM.

| Field | Value |
|-------|-------|
| Verdict | **PASS** |
| Host | matt-berserker (GCP us-central1-a) |
| Operator | Trading Ops executor (Odin James approved 2026-10-01 after stage3 canary PASS) |
| Hub SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Account | `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` |
| Cutover start (stop Griff) | 2026-10-01T16:44:58Z (12:44:58 EDT) |
| Hub started | 2026-10-01T16:46:08Z (12:46:08 EDT) |
| Report written | 2026-10-01T16:49:38Z (12:49:38 EDT) |
| Hub MainPID | 2775860 |

## Success criteria checklist

- [x] `odin-metaapi-hub` active (enabled)
- [x] `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` active with `ODIN_METAAPI_HUB=on`
- [x] Health: `synchronize_calls==1`, `orders_live==true`, `connected==true`, `clients` = btc/gold/us100
- [x] No `TooManyRequests` in journals first ~3 minutes; `reconnects==0` over 120s soak
- [x] Equity readable: **94061.91** (`live_state.json`)
- [x] NordVPN / openvpn@asterdex / odin_daemon untouched (all active)
- [x] London/Omni inactive (`ftmo_london_reversal`, `ftmo_hft_omni`, `ftmo_omnibus`)
- [x] Strategies/config JSON unchanged; factory wiring only

## Preflight (before flip)

| Check | Result |
|-------|--------|
| Griff BTC/US100/Gold | active |
| Hub leftover socket/proc | none |
| Sandbox `/tmp/odin-ftmo-hub-shadow` SHA | `bcd48ff0…` |
| Durable hub | absent → installed |
| Live tree hub wiring | **missing** — engines constructed `MetaApiWrapper` directly |
| London/Omni | inactive |
| Equity | 94061.91 |

## Code deploy (before env flip)

Durable hub package:

- `/home/solveetcoagula/odin-ftmo-hub/metaapi_hub/` (+ `HUB_SHA.txt`)
- Also copied into live tree: `/home/solveetcoagula/odin_ftmo/metaapi_hub/`

Engine backups (`.pre-hub-20261001`):

- `griff_engine_live.py.pre-hub-20261001`
- `griff_engine_us100.py.pre-hub-20261001`
- `griff_engine_gold.py.pre-hub-20261001`

Minimal factory patches applied from sandbox (strategy/risk/config untouched):

- Import `build_execution_wrapper` / `hub_mode` / `engine_name_for_symbol`
- Replace direct `MetaApiWrapper(...)` with factory (default off preserves old path)

Import check as `solveetcoagula` from WorkingDirectory:

```
python3 -c 'from metaapi_hub.factory import hub_mode; print(hub_mode())'
→ off
```

## Unit: `/etc/systemd/system/odin-metaapi-hub.service`

```
[Unit]
Description=Odin MetaAPI shared hub (live orders) — production cutover 2026-10-01
After=network.target

[Service]
Type=simple
User=solveetcoagula
WorkingDirectory=/home/solveetcoagula/odin_ftmo
RuntimeDirectory=odin
RuntimeDirectoryMode=0755
Environment=PYTHONPATH=/home/solveetcoagula/odin-ftmo-hub
Environment=ODIN_METAAPI_HUB_ORDERS=live
ExecStart=/usr/bin/python3 -m metaapi_hub --mode live --orders live --enable-live-orders --config /home/solveetcoagula/odin_ftmo/config_us100.json --account-id a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf --socket /run/odin/metaapi-hub.sock
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Drop-ins: `/etc/systemd/system/griff_engine_*.service.d/hub.conf`

(identical for btc, us100, gold)

```
[Service]
Environment=ODIN_METAAPI_HUB=on
Environment=ODIN_METAAPI_HUB_SOCKET=/run/odin/metaapi-hub.sock
Environment=PYTHONPATH=/home/solveetcoagula/odin_ftmo
```

## Cutover sequence

1. Stopped three Griff units; cooldown ~25s
2. `systemctl enable --now odin-metaapi-hub` → socket `/run/odin/metaapi-hub.sock` ready
3. Started engines **one at a time**: BTC → US100 → Gold
4. After each: clients grew; `synchronize_calls` stayed **1**
5. 120s soak: sync=1, reconnects=0, orders_live=true

Journal confirms hub-backed (no local sync):

```
Engine btc attached to MetaAPI hub without a local synchronization
Engine us100 attached to MetaAPI hub without a local synchronization
Engine gold attached to MetaAPI hub without a local synchronization
```

## Final health JSON (2026-10-01T16:49:27Z)

```json
{"id":"1","ok":true,"result":{"mode":"live","orders_mode":"live","orders_live":true,"account_id":"a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf","connected":true,"synchronize_calls":1,"sync_attempts":1,"reconnects":0,"clients":["btc","gold","us100"],"client_count":3,"candle_fetches":2,"candle_timeouts":0,"single_flight_joins":0,"cache_hits":0,"duplicate_suppressions":0,"broker_synchronize_calls":1,"broker_order_calls":0,"broker_mutation_calls":0,"broker_candle_calls":2,"broker_connected":true,"max_rpc_depth":1,"you_do_not_sync":true}}
```

## Postflight units

| Unit | State |
|------|-------|
| odin-metaapi-hub | active |
| griff_engine_btc | active |
| griff_engine_us100 | active |
| griff_engine_gold | active |
| nordvpnd | active |
| openvpn@asterdex | active |
| odin_daemon | active |
| ftmo_london_reversal | inactive |
| ftmo_hft_omni | inactive |
| ftmo_omnibus | inactive |

## Rollback commands (exact)

```bash
# 1. Stop three Griff
sudo systemctl stop griff_engine_btc griff_engine_us100 griff_engine_gold

# 2. Remove hub drop-ins; daemon-reload
sudo rm -f /etc/systemd/system/griff_engine_btc.service.d/hub.conf
sudo rm -f /etc/systemd/system/griff_engine_us100.service.d/hub.conf
sudo rm -f /etc/systemd/system/griff_engine_gold.service.d/hub.conf
sudo systemctl daemon-reload

# 3. Stop/disable hub (by systemd only — never pkill -f)
sudo systemctl stop odin-metaapi-hub
sudo systemctl disable odin-metaapi-hub
# optional: sudo systemctl kill -s TERM odin-metaapi-hub  # only if needed; prefer stop
# kill by recorded PID if required: sudo kill <MainPID from systemctl show>

# 4. Optional: restore pre-hub engine sources
# sudo -u solveetcoagula cp -a /home/solveetcoagula/odin_ftmo/griff_engine_live.py.pre-hub-20261001 /home/solveetcoagula/odin_ftmo/griff_engine_live.py
# sudo -u solveetcoagula cp -a /home/solveetcoagula/odin_ftmo/griff_engine_us100.py.pre-hub-20261001 /home/solveetcoagula/odin_ftmo/griff_engine_us100.py
# sudo -u solveetcoagula cp -a /home/solveetcoagula/odin_ftmo/griff_engine_gold.py.pre-hub-20261001 /home/solveetcoagula/odin_ftmo/griff_engine_gold.py
# (Not required for env-off rollback: factory defaults to MetaApiWrapper when ODIN_METAAPI_HUB unset)

# 5. Start three Griff without hub env
sudo systemctl start griff_engine_btc griff_engine_us100 griff_engine_gold

# 6. Confirm old path: journals show MetaApiWrapper / local sync (not hub-backed)
journalctl -u griff_engine_btc -n 40 --no-pager
```

**Hard rules on rollback:** never disconnect NordVPN / openvpn@asterdex / odin_daemon; never `pkill -f`; cross-user checks use `ps -p` + `sudo kill`.

## Notes

- Token never logged; hub reads token from live `config_us100.json` only.
- `griff_engine_xau.service` exists but was not part of this cutover (live trio is btc/us100/gold).
