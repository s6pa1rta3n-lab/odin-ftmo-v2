# Cutover

Odin approved production cutover (Stage 4) on 2026-10-01, after Stage 2 and the Stage 3 safe canary were recorded, so the procedure and the rollback live in git.

**This commit does not cut over the VM.** It does not install a unit, `daemon-reload`, start or stop a process, or change a live systemd file. The default in code remains `ODIN_METAAPI_HUB` off. Engines keep constructing `MetaApiWrapper` until an operator sets the flag on purpose. Strategy logic and config files stay as they are. The hub is plumbing.

Stage 2 and the Stage 3 canary were run by operators on `matt-berserker` at `bcd48ff0b6900c24ce2bb861f9b7410740507cc4`. This documentation records what they reported. It does not re-verify the host.

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

### Stage 4 — production cutover — approved by Odin 2026-10-01

Approved so it can be done from this document and rolled back from git. **Not performed by the commit that added this section.**

Strategies, risk, session windows, and order comments in the engines stay as they are. The hub does not replace them. Canary comments `hub-canary-*` were probe orders, not strategy comments.

#### Prerequisites

1. Durable checkout of this branch, **not** `/tmp`. The canary sandbox `/tmp/odin-ftmo-hub-shadow` was deleted with the window. Recommended path for the operator to create by copying git (this commit has not checked that the directory exists on the VM):

    `/home/solveetcoagula/odin-metaapi-hub`

2. Hub process from that checkout, with every live-order interlock:

    - `--mode live`
    - `--orders live`
    - `--enable-live-orders`
    - `ODIN_METAAPI_HUB_ORDERS=live` on the hub process

    The example that contains all four, and only that example, is `deploy/examples/odin-metaapi-hub.live-orders.service.example`. Installing it is the cutover. The shadow unit and the live-readonly example stay on `--orders deny`.

3. Config stays the existing file, which is not in git:

    `/home/solveetcoagula/odin_ftmo/config_us100.json`

    Account id used by the canary and already in the setup scripts: `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf`. Do not put the token in the unit file or in git.

4. Socket: `/run/odin/metaapi-hub.sock`. User: `solveetcoagula`.

5. Engine drop-ins, one per Griff unit, from `deploy/examples/griff-hub-on.conf.example`:

    ```
    Environment=ODIN_METAAPI_HUB=on
    Environment=ODIN_METAAPI_HUB_SOCKET=/run/odin/metaapi-hub.sock
    Environment=PYTHONPATH=/home/solveetcoagula/odin-metaapi-hub
    ```

    `PYTHONPATH` must include the checkout that contains the `metaapi_hub` package when the live tree does not. The Stage 3 report says the live tree was not git-pulled. `ODIN_METAAPI_HUB` is read only by the hub-aware modules on this branch (`build_execution_wrapper` in `griff_engine_live.py`, `griff_engine_us100.py`, `griff_engine_gold.py`). If a unit still executes a pre-hub copy of those files, the drop-in does not attach it and that process keeps calling `wait_synchronized` itself. Run the hub-aware modules. Leave each unit's `WorkingDirectory`, `ExecStart`, and `--config` in place so strategy config is not replaced.

6. London and Omni inactive, or explicitly stopped for the window. The three Griff units stopped **before** the hub starts.

#### Procedure

1. Record the hub-free state you will restore: `systemctl show` Environment and DropInPaths for the three units (the canary postflight was `Environment=[]` and `DropInPaths=[]`).
2. Stop `griff_engine_btc`, `griff_engine_us100`, and `griff_engine_gold`. Confirm `systemctl is-active` is inactive for each. Confirm London and Omni are inactive.
3. Start the hub from the durable checkout (the live-orders example unit, or the same command by hand). Do not start it from `/tmp`.
4. Health before the engines attach: `mode` live, `orders_mode` live, `orders_live` true, `synchronize_calls` 1 once it has connected, `connected` true. The Stage 3 probe saw `synchronize_calls` 0 until the first sync, then 1. It must not climb once per engine.
5. Start the three engines **one by one**. After each start, health `clients` includes that engine and `synchronize_calls` is still 1. `local_synchronize_calls` on the client stays 0.
6. Confirm a candle read for BTCUSD, US100.cash, and XAUUSD comes back through the hub (`broker_synchronize_calls` stays 1).
7. Leave the drop-ins in place only if that health check held. If `synchronize_calls` climbs once per engine, the engines are still synchronizing themselves. Roll back.

#### Rollback

Fast path. No git revert is required when the only production change was the hub unit and the engine drop-ins. Strategy files are unchanged by this documentation, and the canary did not edit them.

1. Stop `griff_engine_btc`, `griff_engine_us100`, and `griff_engine_gold`.
2. Remove the drop-ins so Environment and DropInPaths are empty again (the hub-free state from the canary postflight). `daemon-reload` after the files are gone.
3. Stop the hub unit if one was installed: `systemctl disable --now` that unit and delete the unit file. If the hub was started by hand, stop it by the recorded PID (next section). Confirm the socket `/run/odin/metaapi-hub.sock` is gone.
4. Start the three engines on the old path, with no `ODIN_METAAPI_HUB`. Confirm the units are active and hub-free.
5. Journals should show each engine on its own MetaAPI sync again. That is the known TooManyRequests behavior. It is the rollback. Do not invent a third topology during the incident.

PID check, including when SIGTERM does not exit (the Stage 3 hub needed KILL after TERM because the SDK write loop hung):

```sh
ps -p "$HUB_PID" -o pid,user,cmd
sudo kill "$HUB_PID"
ps -p "$HUB_PID" -o pid,user,cmd
# if it is still there:
sudo kill -KILL "$HUB_PID"
ps -p "$HUB_PID" -o pid,user,cmd
```

Use the PID you recorded when the hub started. `ps -p` is the liveness check. `kill -0` across users returns EPERM and is not proof the process died. Never `pkill -f`. Never kill a PID you did not record for this hub.

Git: the canary code is `bcd48ff0b6900c24ce2bb861f9b7410740507cc4`. Later commits on this branch document evidence and this procedure. Reverting them does not restore or remove strategy behavior. Abandoning the hub is the systemd rollback above.

## Production checklist

Stage 2 and the Stage 3 canary are done. Stage 4 is approved and still operator-executed.

- [x] Odin approved production cutover in writing on 2026-10-01, after the evidence below was documented for rollback.
- [x] Stage 1 shadow passed on matt-berserker.
- [x] Stage 2 read-only live passed: `synchronize_calls=1`, orders deny, engines restored hub-free, ~148s downtime, SHA `bcd48ff`.
- [x] Stage 3 safe canary passed: orderIds 172310476, 172310493, 172310505, one sync, no leftover orders or positions, engines restored hub-free. Evidence file in this tree.
- [ ] Stage 4 itself has not been performed by the documentation commit. The operator still has to do the procedure above.
- [ ] Durable checkout exists and is not under `/tmp`. Live tree was not git-pulled for the canary; do not assume `/home/solveetcoagula/odin_ftmo` contains `metaapi_hub`.
- [ ] Engine processes that start are the hub-aware modules. `PYTHONPATH` includes that checkout. Config paths stay the existing files.
- [ ] No `metaapi.token` value is in the diff (`git diff` / `git log -p`).
- [ ] `setup_gold_service.sh`, `setup_us100_service.sh`, `ftmo_hft_omni.service`, and `ftmo_london_reversal.service` do not grow a hub flag. The drop-in is separate and removable.
- [ ] Shadow and live-readonly example units were not installed as the trader. Only the live-orders example has the four interlocks, and only as the intentional cutover.
- [ ] London and Omni are inactive for the window.
- [ ] The three Griff units (`griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold`) are stopped before the live hub starts.
- [ ] Hub command is `--mode live --orders live --enable-live-orders` with `ODIN_METAAPI_HUB_ORDERS=live`.
- [ ] Health after all three engines attach: `synchronize_calls` is 1.
- [ ] Rollback PID is the one recorded at start. Liveness is `ps -p`. No `kill -0` across users. No `pkill -f`.

## VM path

| Item | Value |
| --- | --- |
| Host | `matt-berserker`, zone `us-central1-a` |
| Live tree | `/home/solveetcoagula/odin_ftmo` (not git-pulled for the canary) |
| Config | `/home/solveetcoagula/odin_ftmo/config_us100.json` (not in git) |
| Canary sandbox | `/tmp/odin-ftmo-hub-shadow` (not for Stage 4) |
| Durable checkout to create | `/home/solveetcoagula/odin-metaapi-hub` (recommended; not verified by this commit) |
| Units | `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` |
| Socket | `/run/odin/metaapi-hub.sock` |
