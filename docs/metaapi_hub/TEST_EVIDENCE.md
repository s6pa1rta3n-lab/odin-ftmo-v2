# Test evidence

## 2026-10-02 resilience branch (`cursor/metaapi-hub-resilience-4d1b`)

Local, no MetaAPI contact, no token, no orders. `sh scripts/run_metaapi_hub_tests.sh`:

| Interpreter | Result |
| --- | --- |
| Python 3.12.3 | `43 passed, 1 skipped`, `shadow probe ok 1 orders 0` |
| Python 3.9.25 (uv-managed venv, pytest + pytz only) | `43 passed, 1 skipped` |

The skip is the installed-`MetaApiWrapper` test; the SDK is not present here. New files: `tests/metaapi_hub/test_resilience.py` (8 tests: >64 KiB candle frame, head-of-line blocking, hub restart reattach, read retry/backoff with mutations not retried, candle retry then stale fallback, stale TTL 0, shared flight survives a cancelled waiter, health transport fields) and `tests/metaapi_hub/test_engine_open_position_resilience.py` (6 tests against the real `GriffLiveEngine`: restart adopts an open BTC ticket with 20 bars and manages it, zero history while `IN_TRADE` holds the position across polls and recovers, failed position reads never flip `IN_TRADE` to `SEARCHING`, the in-cycle candle retry joins the hub's in-flight fetch, 40 bars when flat is still `ACCUMULATING_HISTORY`, 14 bars while `IN_TRADE` defers the ratchet). Every engine test asserts `broker.mutation_calls == 0` and `broker.order_calls == 0`.

Before the fix, the >64 KiB test fails exactly as the 2026-10-02 audit describes: `HubRequestError CLOSED: hub connection closed` on the candle call, then `TimeoutError` on the next account-information call, reader task done. The VM re-run on Python 3.9 with the SDK installed is the remaining confirmation; see [RESTART_CHECKLIST.md](RESTART_CHECKLIST.md) step 1.

## 2026-10-01 hub branch

Recorded 2026-10-01 on this branch after the shutdown fix (idle client sockets are closed so `wait_closed` cannot hang).

A later VM run of the same script on matt-berserker (Python 3.9, MetaAPI SDK installed) was 24/27. The three failures were environment checks, not sync or order safety. They are fixed on this branch: lazy asyncio locks, `SDK_MISSING` forced without importing the real SDK, and off-mode assertions that accept an installed `MetaApiWrapper` without constructing `MetaApi`. Re-run steps are in [RUNBOOK.md](RUNBOOK.md). Do not deploy and do not enable the live hub to re-run them.

Local check after that fix, Python 3.12: `28 passed, 1 skipped` when `MetaApiWrapper` cannot be imported. With a stub `metaapi_cloud_sdk` whose `MetaApi()` raises if called: `29 passed`. The installed-wrapper test ran, and the masked-SDK test still returned `SDK_MISSING` with zero orders. This checkout has no Python 3.9 interpreter; the VM re-run is the 3.9 confirmation.

Command:

```sh
sh scripts/run_metaapi_hub_tests.sh
```

Result:

```text
27 passed in 0.38s
shadow probe ok 1
```

The shadow probe did not contact MetaAPI. Its snapshot:

| Field | Value |
| --- | --- |
| ok | true |
| mode | shadow |
| orders_mode | dry_run |
| orders_live | false |
| synchronize_calls | 1 |
| broker_synchronize_calls | 1 |
| broker_order_calls | 0 |
| broker_mutation_calls | 0 |
| clients | btc, us100, gold |
| local_synchronize_calls per engine | 0 |
| order_sent per engine | false (`DRY_RUN`, `sent: false`) |
| max_rpc_depth | 1 |

`candle_fetches` was 3 because the three engines asked for three symbols. That is three reads on one synchronization, not three syncs. `single_flight_joins` was 0 in the probe for the same reason: different symbols do not share a flight. The 504 test covers the shared flight (`single_flight_joins == 2`, `broker.candle_calls == 3` for two failures plus one success).

`pytest` with no path still uses `pytest.ini` `testpaths = tests/e2e`. Those tests are not part of this result. They expect `config_us100.json` and `metaapi-cloud-sdk`, which are not in this checkout. The hub suite is the command above.

`MetaApiBroker.synchronize` was not pointed at FTMO. The missing-SDK test expects `SDK_MISSING` and checks that the token is absent from `repr` and from the error string.

## What the tests cover

- Three overlapping `synchronize()` calls: one success, two `TooManyRequestsError`.
- A held slot rejects a later sync until `close()`.
- Unserialized broker RPC overlaps; hub RPC depth stays 1.
- SDK exception classification for 429, 504, not connected, and timeout. Timeouts do not become reconnects.
- `MetaApiBroker` refuses to synchronize without the SDK and does not echo the token.
- Three socket clients, two injected 504s, one shared retry flight, one synchronization.
- Candle cache TTL.
- Concurrent readers share one reconnect after `not connected to broker`.
- A failed order is not resent; the following read resynchronizes once.
- An external holder causes backoff (`0.2`, `0.4`, `0.8`), not a tight loop, then one sync once the holder is gone.
- The server and the client both reject `synchronize` / `wait_synchronized`.
- Closing one engine client leaves the broker slot up.
- Deny and dry-run cover every mutating method and leave `order_calls` and `mutation_calls` at 0.
- Shadow downgrades live orders. Live orders without `ODIN_METAAPI_HUB_ORDERS=live` are denied.
- Duplicate window and parallel orders from two engines stay at RPC depth 1.
- Comment and volume checks.
- Live owner rejects a shadow client and a mismatched account id, with zero syncs.
- Default flag off, unknown flag off, direct wrapper import fails closed without the SDK.
- Shadow probe across btc, us100, and gold.
- `GriffLiveEngine` for BTCUSD, US100.cash, and XAUUSD, plus `US100Engine` and `GoldEngine`, one synchronization.
- Hub outage does not fall back to a private sync.
- `GriffLiveEngine.run_self_test` against the shadow hub sends no orders.
- Installer scripts and the London/Omni unit files do not mention the hub. The shadow and live-readonly example `ExecStart` lines do not contain `--orders live` or `--enable-live-orders`. The separate live-orders example must contain `--mode live`, `--orders live`, `--enable-live-orders`, and `ODIN_METAAPI_HUB_ORDERS=live`. Installing that file is the Stage 4 cutover, not the default.
- CLI rejects live orders unless every interlock is present.
- Python 3.9: an owner built after `asyncio.run()` still synchronizes once and denies orders.
- `SDK_MISSING` is forced by hiding the SDK module, so an installed SDK cannot turn the test into a live synchronize.
- Off mode returns the direct wrapper when that module imports, and raises when the import is blocked. Neither path builds `HubBackedWrapper` or calls `MetaApi(token)`.

## Encounter during the run

The first full run hung. `HubServer.close` called `wait_closed()` while Griff clients were still blocked in `readline`, so shutdown never returned. The fix closes those sockets before waiting. Re-run: 27 passed in 0.38s. That behavior is now what SIGTERM uses as well, so a hub stop does not wait for the engines to exit.

## Stage 2 — read-only live on matt-berserker

Operator summary of the successful window. This documentation commit did not re-run it and did not add measurements beyond what was reported. It is a different window from Stage 3.

| Item | Reported |
| --- | --- |
| When | 2026-10-01, before the Stage 3 canary |
| SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` on `cursor/metaapi-hub-230c` |
| Orders | deny |
| `synchronize_calls` | 1 |
| Engines after the window | restored hub-free |
| Downtime | ~148s |

No order ids, broker codes, or extra health fields were supplied for this stage. Do not read the Stage 3 table as Stage 2.

## Stage 3 — safe live order canary on matt-berserker

**PASS.** Operator report plus the uploaded probe for the same window. Full copy: [evidence/2026-10-01-stage3-canary.md](evidence/2026-10-01-stage3-canary.md). This commit did not execute the canary and did not inspect the VM afterward.

| Item | Value |
| --- | --- |
| When | 2026-10-01 ~12:38–12:41 ET |
| Probe | 2026-10-01T16:40:12Z → 2026-10-01T16:40:42Z |
| SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Sandbox | `/tmp/odin-ftmo-hub-shadow` (live tree not git-pulled) |
| Account | `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` |
| Verdict | PASS, `cleanup.clean` true, `fills` false |

Orders were far-from-market BUY limits, 0.01 lots, then canceled. No market orders.

| Symbol | Mark | Limit | orderId | Create | Cancel | Comment |
| --- | --- | --- | --- | --- | --- | --- |
| BTCUSD | 84231.67 | 10000.0 | 172310476 | TRADE_RETCODE_DONE / 10009 | CANCELED | hub-canary-btc |
| US100.cash | 30363.28 | 10000.0 | 172310493 | TRADE_RETCODE_DONE / 10009 | CANCELED | hub-canary-us100 |
| XAUUSD | 4165.37 | 1000.0 | 172310505 | TRADE_RETCODE_DONE / 10009 | CANCELED | hub-canary-gold |

Post-cancel broker list: `orders=[]`, `positions=[]`. Equity 94061.91, SEARCHING, unchanged. Each engine row in the probe: `local_synchronize_calls` 0, `candles` 5.

Health after the probe (`health_before` was `connected` false and `synchronize_calls` 0 because the probe attached before the sync):

| Field | After |
| --- | --- |
| mode / orders_mode / orders_live | live / live / true |
| connected | true |
| synchronize_calls | 1 |
| broker_synchronize_calls | 1 |
| sync_attempts | 1 |
| reconnects | 0 |
| broker_order_calls | 3 |
| broker_mutation_calls | 6 |
| broker_candle_calls | 3 |
| candle_fetches | 3 |
| clients | probe-health only (`client_count` 1) |
| max_rpc_depth | 1 |

`broker_order_calls` 3 and `broker_mutation_calls` 6 are the three creates plus three cancels. They are not leftover working orders. The Griff engines were not hub clients in this probe; they were restored hub-free afterward (`griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` active, `Environment=[]`, `DropInPaths=[]`).

Downtime:

| Window | Engines down |
| --- | --- |
| v1 abort | ~96s |
| Successful canary v2 | 135 seconds (stop ~16:38:42Z → restore ~16:40:53Z) |

### Anomalies

1. **Cross-user `kill -0` false abort.** From `reemanos8422`, `kill -0` on the `solveetcoagula` hub PID returns EPERM. The v1 script treated that as "PID gone" and aborted. A leftover hub then coexisted with the restored engines. Emergency cleanup stopped the engines, killed the hub by its recorded PID, and restored the engines before v2. Liveness is `ps -p`. Stop is `sudo kill` of that PID, then `sudo kill -KILL` of that same PID if TERM does not exit. Never `kill -0` across users. Never `pkill -f`.
2. Launch-script `Permission denied` while rewriting a prior launch file did not block start.
3. The hub needed KILL after TERM (SDK write-loop hang on shutdown). The signal still targeted only the recorded PID.

`nordvpn`, `openvpn@asterdex`, and `odin_daemon` stayed active. London and Omni stayed inactive. Secrets were not logged (token length 2589 only). No permanent `ODIN_METAAPI_HUB` was left on the production units.

## Stage 4 — production cutover on matt-berserker

**COMPLETED / PASS.** Operator report for 2026-10-01 ~12:44–12:49 EDT. Full copy, including the installed unit and the exact rollback: [evidence/2026-10-01-stage4-cutover.md](evidence/2026-10-01-stage4-cutover.md). This commit did not run the cutover and did not inspect the VM afterward.

| Item | Reported |
| --- | --- |
| Hub SHA | `bcd48ff0b6900c24ce2bb861f9b7410740507cc4` |
| Stop Griff | 2026-10-01T16:44:58Z (12:44:58 EDT) |
| Hub started | 2026-10-01T16:46:08Z (12:46:08 EDT) |
| Health time | 2026-10-01T16:49:27Z |
| Report written | 2026-10-01T16:49:38Z (12:49:38 EDT) |
| Unit | `odin-metaapi-hub` active and enabled, MainPID 2775860 |
| Durable path | `/home/solveetcoagula/odin-ftmo-hub` (`metaapi_hub/` + `HUB_SHA.txt`) |
| Live-tree copy | `/home/solveetcoagula/odin_ftmo/metaapi_hub/` |
| Drop-ins | `griff_engine_{btc,us100,gold}.service.d/hub.conf` |
| Backups | `.pre-hub-20261001` on `griff_engine_live.py`, `griff_engine_us100.py`, `griff_engine_gold.py` |
| Account | `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` |
| Equity | 94061.91 (`live_state.json`) |

Health at 16:49:27Z:

| Field | Value |
| --- | --- |
| mode / orders_mode / orders_live | live / live / true |
| connected | true |
| synchronize_calls | 1 |
| broker_synchronize_calls | 1 |
| sync_attempts | 1 |
| reconnects | 0 |
| clients | btc, gold, us100 (`client_count` 3) |
| candle_fetches / broker_candle_calls | 2 / 2 |
| broker_order_calls / broker_mutation_calls | 0 / 0 |
| max_rpc_depth | 1 |

120s soak held `synchronize_calls=1`, `reconnects=0`, `orders_live=true`. Journals for the first ~3 minutes had no `TooManyRequests`. Each engine logged that it attached without a local synchronization. Preflight equity was the same 94061.91. `nordvpnd`, `openvpn@asterdex`, and `odin_daemon` stayed active. `ftmo_london_reversal`, `ftmo_hft_omni`, and `ftmo_omnibus` stayed inactive. `griff_engine_xau.service` was not part of the cutover.

Hub `PYTHONPATH` is `/home/solveetcoagula/odin-ftmo-hub`. Engine drop-in `PYTHONPATH` is `/home/solveetcoagula/odin_ftmo`. Both are what the report installed. The token was not logged.

Rollback, if needed: stop the three Griff units, remove the three `hub.conf` drop-ins, `daemon-reload`, stop and disable `odin-metaapi-hub`, start the three Griff units. With `ODIN_METAAPI_HUB` unset, the factory returns `MetaApiWrapper`. Copying the `.pre-hub-20261001` files back is optional and is not required for that path. Never `pkill -f`. Cross-user PID checks use `ps -p` and `sudo kill` of the recorded PID.
