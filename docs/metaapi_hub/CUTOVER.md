# Cutover

Odin approved production cutover (Stage 4) on 2026-10-01. Operators then completed it on matt-berserker the same day. **Verdict: PASS** (~12:44–12:49 EDT). Full report: [evidence/2026-10-01-stage4-cutover.md](evidence/2026-10-01-stage4-cutover.md).

This documentation commit only records that report. It does not install a unit, `daemon-reload`, or start or stop a process. The default in code remains `ODIN_METAAPI_HUB` off, so removing the drop-in returns each engine to `MetaApiWrapper`. Strategy logic and config files stay as they are. The hub is plumbing.

Stage 2, the Stage 3 canary, and the Stage 4 hub package are the operator's run of `bcd48ff0b6900c24ce2bb861f9b7410740507cc4`. This file records what they reported. It does not re-verify the host.

## Unit names on matt-berserker

Use the names observed during the Stage 3 canary:

- `griff_engine_btc`
- `griff_engine_us100`
- `griff_engine_gold`

`monitor_griff.py` still lists `griff_engine.service` (US100), `griff_engine_btc.service`, and `griff_engine_xau.service`. Those older names are not the units the canary stopped and restored. Stopping `griff_engine` or `griff_engine_xau` can leave `griff_engine_us100` or `griff_engine_gold` synchronizing.

London (`ftmo_london_reversal.service`) and Omni (`ftmo_hft_omni.service`) are not wired to the hub. During the Stage 3 window both were inactive. If either is active on the same account when a live hub starts, it is another synchronization. Stop them for the window or leave them stopped. Do not add the hub drop-in to those units.

A live hub must not be started while any of the three Griff units is still synchronizing. That would be another synchronization on an account that allows one.

## Stages

### Stage 0 — pull request code

Hub code, tests, and example units. Engines unchanged at runtime until a later stage sets `ODIN_METAAPI_HUB`. Completed on this branch before the VM stages.

### Stage 1 — shadow rehearsal

Completed earlier on matt-berserker (functional pass). Shadow mode does not read the token file and does not connect to the broker. `orders_live` is false. A later test-script run on the VM was 24/27 for environment reasons; the suite was fixed on this branch. Re-run steps are in [RUNBOOK.md](RUNBOOK.md). Re-running tests is not a cutover.

### Stage 2 — read-only live hub — completed 2026-10-01

Operator summary from the successful window. This commit did not re-run it and does not add timestamps, order ids, or health fields beyond what was reported.

| Item | Reported result |
| --- | --- |
| Date | 2026-10-01, before the Stage 3 canary |
| SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Orders | deny |
| `synchronize_calls` | 1 |
| Engines afterward | restored hub-free |
| Downtime | ~148s on the successful window |

That window is separate from the Stage 3 downtimes below. Do not treat 148s as the canary window.

The shape of the stage, for the record:

1. Stop `griff_engine_btc`, `griff_engine_us100`, and `griff_engine_gold`. Confirm they are inactive. Confirm London and Omni are not holding the account.
2. Start the hub by hand, or from the read-only example, with `--mode live --orders deny`. No `--enable-live-orders`. No `ODIN_METAAPI_HUB_ORDERS=live`.
3. Health: `synchronize_calls == 1`, orders still denied, `connected == true`.
4. Start the three engines one at a time with a drop-in that is easy to delete (`ODIN_METAAPI_HUB=on` and the socket path). `synchronize_calls` stays 1.
5. Orders raise `ORDERS_DISABLED` and must not show broker code 10009. This stage cannot trade. It is a proof, not the trading configuration.
6. Restore the engines hub-free when the window ends.

### Stage 3 — safe live-order canary — completed 2026-10-01

**PASS.** Full write-up: [evidence/2026-10-01-stage3-canary.md](evidence/2026-10-01-stage3-canary.md).

| Item | Reported result |
| --- | --- |
| When | 2026-10-01 ~12:38–12:41 ET (successful window) |
| SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Where | sandbox `/tmp/odin-ftmo-hub-shadow` only; live tree not git-pulled |
| Orders | far-from-market BUY limits, 0.01 lots, then canceled |
| orderIds | 172310476 (BTCUSD), 172310493 (US100.cash), 172310505 (XAUUSD) |
| Create | `TRADE_RETCODE_DONE` / 10009, then `CANCELED` |
| After cancel | `orders=[]`, `positions=[]`, no fills |
| Health after | `synchronize_calls` 1, `broker_order_calls` 3, `broker_mutation_calls` 6 (3 creates + 3 cancels), `reconnects` 0 |
| Equity | 94061.91 SEARCHING, unchanged |
| Engines afterward | `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` active, hub-free (`Environment=[]`, `DropInPaths=[]`) |
| v1 abort downtime | ~96s (false `kill -0`; engines restored; leftover hub cleaned before v2) |
| Successful window | 135 seconds (stop ~16:38:42Z → restore ~16:40:53Z) |

The canary used all four live-order interlocks, on a sandbox checkout, for those three orders only. It did not leave `ODIN_METAAPI_HUB` on the production units. `/tmp` is not the production checkout.

Anomaly that must not be repeated: `kill -0` from `reemanos8422` against the `solveetcoagula` hub PID returns EPERM, and a script treated that as "PID gone". See [RUNBOOK.md](RUNBOOK.md).

### Stage 4 — production cutover — COMPLETED / PASS 2026-10-01

Operator report, ~12:44–12:49 EDT. This commit did not perform the cutover. Details and the installed unit text: [evidence/2026-10-01-stage4-cutover.md](evidence/2026-10-01-stage4-cutover.md).

| Item | Reported result |
| --- | --- |
| Verdict | PASS |
| Hub SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Stop Griff | 2026-10-01T16:44:58Z (12:44:58 EDT) |
| Hub started | 2026-10-01T16:46:08Z (12:46:08 EDT) |
| Report written | 2026-10-01T16:49:38Z (12:49:38 EDT) |
| Hub unit | `odin-metaapi-hub` active and enabled, MainPID 2775860 |
| Durable package | `/home/solveetcoagula/odin-ftmo-hub/metaapi_hub/` plus `HUB_SHA.txt` |
| Also copied | `/home/solveetcoagula/odin_ftmo/metaapi_hub/` |
| Drop-ins | `/etc/systemd/system/griff_engine_{btc,us100,gold}.service.d/hub.conf` |
| Engine backups | `griff_engine_live.py.pre-hub-20261001`, `griff_engine_us100.py.pre-hub-20261001`, `griff_engine_gold.py.pre-hub-20261001` |
| Health 16:49:27Z | `synchronize_calls` 1, `orders_live` true, `connected` true, `reconnects` 0, `sync_attempts` 1 |
| Clients | btc, gold, us100 (`client_count` 3) |
| Soak | 120s, sync stayed 1, reconnects stayed 0, no `TooManyRequests` in the first ~3 minutes of journals |
| Orders through hub since flip | `broker_order_calls` 0, `broker_mutation_calls` 0 |
| Candles | `candle_fetches` 2, `broker_candle_calls` 2, `broker_synchronize_calls` 1 |
| Equity | 94061.91 (`live_state.json`) |
| Left active | `nordvpnd`, `openvpn@asterdex`, `odin_daemon` |
| Left inactive | `ftmo_london_reversal`, `ftmo_hft_omni`, `ftmo_omnibus` |

Strategies, risk, and config JSON were unchanged. The live tree had no hub wiring before the flip (engines constructed `MetaApiWrapper` directly). Operators applied a factory patch from the sandbox: import `build_execution_wrapper` / `hub_mode` / `engine_name_for_symbol`, and replace the direct `MetaApiWrapper(...)` call. An import check from the engine WorkingDirectory printed `off` before the env flip. Journals after start: each engine "attached to MetaAPI hub without a local synchronization". `griff_engine_xau.service` exists and was not part of this cutover.

Installed hub unit (not the example file in this repo): `WorkingDirectory=/home/solveetcoagula/odin_ftmo`, `PYTHONPATH=/home/solveetcoagula/odin-ftmo-hub`, `ODIN_METAAPI_HUB_ORDERS=live`, and `ExecStart` with `--mode live --orders live --enable-live-orders`, the existing `config_us100.json`, account `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf`, socket `/run/odin/metaapi-hub.sock`.

Installed drop-in (identical on btc, us100, gold):

```
Environment=ODIN_METAAPI_HUB=on
Environment=ODIN_METAAPI_HUB_SOCKET=/run/odin/metaapi-hub.sock
Environment=PYTHONPATH=/home/solveetcoagula/odin_ftmo
```

Sequence reported: stop the three Griff units, cooldown ~25s, `systemctl enable --now odin-metaapi-hub`, then start BTC, then US100, then Gold. After each start, `clients` grew and `synchronize_calls` stayed 1.

#### Rollback

Use this order. Removing the drop-ins is enough to leave the factory on `MetaApiWrapper`, because `hub_mode()` is off when `ODIN_METAAPI_HUB` is unset. Restoring the `.pre-hub-20261001` sources is optional and is not required for that env-off path.

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

Do not disconnect NordVPN, `openvpn@asterdex`, or `odin_daemon`. Never `pkill -f`. If `systemctl stop` does not exit the hub, liveness is `ps -p` on the MainPID from `systemctl show` (2775860 at report time). `kill -0` across users returns EPERM and is not proof the process died. The Stage 3 hub needed KILL after TERM; that signal still targets only the recorded PID:

```sh
ps -p "$HUB_PID" -o pid,user,cmd
sudo kill "$HUB_PID"
ps -p "$HUB_PID" -o pid,user,cmd
# if it is still there:
sudo kill -KILL "$HUB_PID"
```

After this rollback each engine synchronizes itself again. That is the known TooManyRequests behavior. It is the rollback. Git revert of this documentation does not undo the unit files on the VM. The systemd steps above do.

## Production checklist

Stages 1–4 are recorded PASS from operator reports. This commit did not re-check the host.

- [x] Odin approved production cutover on 2026-10-01.
- [x] Stage 1 shadow passed on matt-berserker.
- [x] Stage 2 read-only live passed: `synchronize_calls=1`, orders deny, engines restored hub-free, ~148s downtime, SHA `bcd48ff`.
- [x] Stage 3 safe canary passed: orderIds 172310476, 172310493, 172310505, one sync, no leftover orders or positions, engines restored hub-free.
- [x] Stage 4 production cutover PASS ~12:44–12:49 EDT. Hub SHA `bcd48ff`. `odin-metaapi-hub` enabled. Drop-ins `hub.conf`. Durable path `/home/solveetcoagula/odin-ftmo-hub`. Backups `.pre-hub-20261001`.
- [x] Health: `synchronize_calls=1`, `orders_live=true`, clients btc/gold/us100, `reconnects=0` over 120s soak, equity 94061.91, no `TooManyRequests` in the first ~3 minutes.
- [x] London, Omni, and `ftmo_omnibus` inactive during the window. `nordvpnd`, `openvpn@asterdex`, and `odin_daemon` left active.
- [x] Rollback is stop Griff, remove the three `hub.conf` drop-ins, `daemon-reload`, stop and disable `odin-metaapi-hub`, start Griff. Factory stays off when the env is gone. Source restore from `.pre-hub-20261001` is optional.
- [x] No `metaapi.token` value is in this documentation. The report records that the token was not logged.

## VM path

| Item | Value |
| --- | --- |
| Host | `matt-berserker`, zone `us-central1-a` |
| Live tree | `/home/solveetcoagula/odin_ftmo` |
| Config | `/home/solveetcoagula/odin_ftmo/config_us100.json` (not in git) |
| Canary sandbox | `/tmp/odin-ftmo-hub-shadow` (Stage 3 only) |
| Durable hub package | `/home/solveetcoagula/odin-ftmo-hub` |
| Hub unit | `/etc/systemd/system/odin-metaapi-hub.service` (enabled) |
| Drop-ins | `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` → `service.d/hub.conf` |
| Not in this cutover | `griff_engine_xau.service` (the report says it exists) |
| Socket | `/run/odin/metaapi-hub.sock` |
| Hub MainPID at report | 2775860 |
