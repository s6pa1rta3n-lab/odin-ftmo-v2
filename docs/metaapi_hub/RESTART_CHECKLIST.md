# Restart checklist: resilience deploy with an open BTC position

Scope: deploying the resilience changes on this branch to `matt-berserker` and restarting the hub and the three Griff units while `griff_engine_btc` is `IN_TRADE`. Nothing here closes, cancels, or modifies a position or order. This file does not run anything; the operator does.

Units: `odin-metaapi-hub`, `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold`. Not `griff_engine`, not `griff_engine_xau`. Do not touch NordVPN, `openvpn@asterdex`, `odin_daemon`, London, or Omni.

## 0. Why a restart is safe while IN_TRADE

The engine keeps no position state that matters across a restart. Every cycle it re-derives the open position from the broker:

1. A new process starts in `SEARCHING`.
2. `step()` calls `synchronize_active_positions()`. That reads positions through the hub and keeps the ones with `symbol == BTCUSD` and `comment` starting with `GRIFF_`.
3. If one is found it is adopted as-is: `id` (ticket), direction from `type`, `openPrice`, `volume`, and the broker's current `stopLoss`. State becomes `IN_TRADE`. Journal line: `Position Detected: BUY 1.12 lots on BTCUSD at 86404.90 (SL: 85724.30, Ticket: …). Adopting it as-is; the position is not touched.`
4. The only broker call that adoption can issue is the strategy's own cancel of an unfilled opposite breakout **pending order** (`GRIFF_`-commented orders on the same symbol). The 2026-10-02 report says BTC has no pending buy/sell ids, so this is a no-op. It never touches positions.
5. Trailing-stop management resumes from the broker's stop, not from a remembered one. With at least 15 completed 1H bars the ratchet is evaluated on the latest completed bar. It only ever tightens (`max` for BUY, `min` for SELL) and only when the structural swing condition holds, which is exactly what the previous process would have done on that bar. With fewer than 15 bars the engine logs `History incomplete (N/50 bars). Holding IN_TRADE for ticket …` and does nothing to the position.
6. `live_state.json` is write-only. The engine never reads it back. There is no local file that can disagree with the broker after a restart.

What a restart does reset, unchanged from before this branch and left alone because it is risk logic:

- `day_start_equity` is set to the equity at start, so the daily-loss baseline moves to the restart point.
- `last_evaluated_bar_time` is `None`, so the first full cycle evaluates the latest completed bar once. The ratchet is idempotent, so a second evaluation of the same bar cannot move the stop again.

## 1. Preconditions (read-only)

`$SRC` below is a checkout of this branch somewhere other than the live tree.

```sh
# Hub health. Expect connected=true, synchronize_calls=1, clients btc/gold/us100.
sudo -u solveetcoagula python3 "$SRC/scripts/hub_health.py" /run/odin/metaapi-hub.sock

# Record the open BTC position as the engine sees it.
sudo -u solveetcoagula cat /home/solveetcoagula/odin_ftmo/live_state.json

# Record PIDs. Liveness checks later use ps -p on these, never kill -0, never pkill -f.
systemctl show -p MainPID odin-metaapi-hub griff_engine_btc griff_engine_us100 griff_engine_gold
```

Write down the BTC ticket id, direction, volume, and SL. The post-restart `Position Detected` line must match them exactly.

Run the suite from a **copy** of this branch, not from the live tree (a pull into `/home/solveetcoagula/odin_ftmo` is a deploy):

```sh
cd /path/to/a/checkout/of/this/branch
unset ODIN_METAAPI_HUB ODIN_METAAPI_HUB_ORDERS
sh scripts/run_metaapi_hub_tests.sh
```

Expect Python 3.9, all passed, `shadow probe ok 1 orders 0`.

## 2. Code deploy (no env flip, no unit edits)

The hub process imports `metaapi_hub` from `PYTHONPATH=/home/solveetcoagula/odin-ftmo-hub`. The engines import it from their script directory, `/home/solveetcoagula/odin_ftmo/metaapi_hub/`, because that is first on `sys.path`. **Both copies must be updated**, or the engines keep the 64 KiB client bug while the hub is fixed.

```sh
STAMP=$(date +%Y%m%d)
LIVE=/home/solveetcoagula/odin_ftmo
HUB=/home/solveetcoagula/odin-ftmo-hub
SRC=/path/to/a/checkout/of/this/branch

# Backups
sudo -u solveetcoagula cp -a "$LIVE/griff_engine_live.py" "$LIVE/griff_engine_live.py.pre-resilience-$STAMP"
sudo -u solveetcoagula cp -a "$LIVE/metaapi_hub" "$LIVE/metaapi_hub.pre-resilience-$STAMP"
sudo -u solveetcoagula cp -a "$HUB/metaapi_hub"  "$HUB/metaapi_hub.pre-resilience-$STAMP"

# The live engine file was factory-patched by hand at Stage 4. Confirm it differs
# from git only by that wiring before replacing it. If it differs elsewhere, stop
# and port the engine patch instead of overwriting.
diff "$SRC/griff_engine_live.py" "$LIVE/griff_engine_live.py" | head -80

sudo -u solveetcoagula rsync -a --delete --exclude '__pycache__' "$SRC/metaapi_hub/" "$HUB/metaapi_hub/"
sudo -u solveetcoagula rsync -a --delete --exclude '__pycache__' "$SRC/metaapi_hub/" "$LIVE/metaapi_hub/"
sudo -u solveetcoagula cp "$SRC/griff_engine_live.py" "$LIVE/griff_engine_live.py"
git -C "$SRC" rev-parse HEAD | sudo -u solveetcoagula tee "$HUB/HUB_SHA.txt"

# Import check from the engine working directory. Must print: off
sudo -u solveetcoagula bash -c "cd $LIVE && python3 -c 'from metaapi_hub.factory import hub_mode; print(hub_mode())'"
sudo -u solveetcoagula bash -c "cd $LIVE && python3 -c 'from metaapi_hub.protocol import MAX_MESSAGE_BYTES; print(MAX_MESSAGE_BYTES)'"
```

`griff_engine_us100.py` and `griff_engine_gold.py` are not changed by this branch. Config JSON, risk, sessions, and the `hub.conf` drop-ins are not touched. The hub unit needs no new flags; every new knob has a production default.

Running processes still execute the old code until restarted. Nothing changes until step 3.

## 3. Restart order

Hub first, then the flat engines, then BTC. One unit at a time, verify each before the next.

**Why hub first.** An engine that starts while the hub is down fails `connect_account` and exits; `Restart=` brings it back and it fails again until the hub is up. Restarting the hub first means each engine restart attaches on the first try. With the new client code the engines also reattach on their own after a hub restart, but the old client code the engines are still running at this point does not, so they must be restarted anyway.

```sh
# 3a. Hub
sudo systemctl restart odin-metaapi-hub
sleep 5
journalctl -u odin-metaapi-hub -n 30 --no-pager
# Expect: "Hub resilience: rpc_timeout=20s sync_timeout=60s backoff=0.50s..30s jitter=0.25 read_attempts=3 read_concurrency=4 candle_attempts=4 candle_stale_ttl=300s"
#         "Sync owner connected attempt=1 synchronize_calls=1"
sudo -u solveetcoagula python3 "$SRC/scripts/hub_health.py" /run/odin/metaapi-hub.sock
# Expect connected=true, synchronize_calls=1, max_message_bytes=8000000, clients=[] (old engines lost their socket).
```

```sh
# 3b. US100, then Gold (both flat per the report). Verify each before the next.
sudo systemctl restart griff_engine_us100
sleep 20
journalctl -u griff_engine_us100 -n 20 --no-pager   # expect "attached to MetaAPI hub without a local synchronization"

sudo systemctl restart griff_engine_gold
sleep 20
journalctl -u griff_engine_gold -n 20 --no-pager
```

```sh
# 3c. BTC, while IN_TRADE.
sudo systemctl restart griff_engine_btc
sleep 45                                            # one poll interval plus connect
journalctl -u griff_engine_btc -n 40 --no-pager
```

Expected BTC journal, in order:

1. `Initializing execution wrapper … (hub_mode=on)`
2. `Engine btc attached to MetaAPI hub without a local synchronization`
3. `FTMO Account Connected | … | Equity: $…`
4. `Position Detected: BUY 1.12 lots on BTCUSD at 86404.90 (SL: 85724.30, Ticket: <id>). Adopting it as-is; the position is not touched.` — ticket, direction, volume, and SL must match step 1.
5. Then one of:
   - `Scanning`-free `IN_TRADE` cycles with no further output (normal; a healthy IN_TRADE cycle logs nothing unless a ratchet fires), or
   - `History N/50 bars while IN_TRADE: managing ticket … with ATR_14 …` (history still filling, management active), or
   - `History incomplete (N/50 bars). Holding IN_TRADE for ticket … Position stays untouched.` (upstream still degraded; engine alive, position held).

`systemctl stop`/`restart` sends SIGTERM. The engine's handler sets `is_running=False`; the loop finishes the in-flight `step()` and exits. If a ratchet `modify_position` was mid-flight it either reached the broker or it did not; the new process reads the broker's stop either way, so the two cannot disagree.

## 4. Verify

```sh
sudo -u solveetcoagula python3 "$SRC/scripts/hub_health.py" /run/odin/metaapi-hub.sock
```

- `clients` is exactly `["btc","gold","us100"]`, `client_count` 3.
- `synchronize_calls` is 1 and stays 1. `reconnects` only moves on a real broker disconnect.
- `broker_order_calls` and `broker_mutation_calls` move only when the strategies act. A restart alone must leave them at 0.
- `read_retries`, `candle_retries`, `candle_stale_serves` may be non-zero during upstream degradation. That is the hub absorbing it; the engines keep their deadlines.
- `server_oversized_frames` must be 0.
- `last_upstream_error` names the most recent upstream failure so the journal does not have to be searched.

```sh
sudo -u solveetcoagula cat /home/solveetcoagula/odin_ftmo/live_state.json
```

`state` is `IN_TRADE`, `active_position.id` is the recorded ticket, `history_count` is climbing or 60, `candle_fetch_failures` and `position_sync_failures` are 0 or falling, `updated_at` advances every poll.

Abort criteria: any `Historical candle fetch failed on all 2 attempts` **and** `updated_at` not advancing for more than 3 minutes (that would mean the loop is not completing cycles; with this branch it should complete every cycle even with upstream down); `Position Detected` showing a different ticket or SL than recorded; `broker_mutation_calls` moving on a restart; any line containing the token.

## 5. Rollback

Hub flags did not change, so no unit edits are needed in either direction.

```sh
sudo systemctl stop griff_engine_btc griff_engine_us100 griff_engine_gold
sudo -u solveetcoagula cp -a "$LIVE/griff_engine_live.py.pre-resilience-$STAMP" "$LIVE/griff_engine_live.py"
sudo -u solveetcoagula rsync -a --delete "$LIVE/metaapi_hub.pre-resilience-$STAMP/" "$LIVE/metaapi_hub/"
sudo -u solveetcoagula rsync -a --delete "$HUB/metaapi_hub.pre-resilience-$STAMP/"  "$HUB/metaapi_hub/"
sudo systemctl restart odin-metaapi-hub
sleep 5
sudo systemctl start griff_engine_us100 griff_engine_gold griff_engine_btc
```

The same reattach in section 0 applies on rollback: BTC adopts the open ticket again.

## 6. Do not

- Do not close, cancel, or modify the BTC position or any order by hand to "help" the restart. The engine adopts the position as it is.
- Do not restart while skipping the hub, and do not restart BTC before the hub is `connected=true`.
- Do not `pkill -f`. Do not use `kill -0` across users (EPERM looks like "gone"). Use the recorded PIDs with `ps -p`.
- Do not pull or checkout inside `/home/solveetcoagula/odin_ftmo`.
- Do not change `config_us100.json`, `config_gold.json`, risk, or session windows. This branch does not.
