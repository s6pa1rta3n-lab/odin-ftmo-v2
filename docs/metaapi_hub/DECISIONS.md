# Decisions

Date of this work: 2026-10-01. No production host was contacted. No systemd unit was installed or restarted. No MetaAPI token was read or committed. `config_us100.json` is gitignored and is not in this checkout. `metaapi-cloud-sdk` is not installed in the agent environment, so nothing here could place an FTMO order.

## Root cause

Hypothesis: three engines each synchronize one MetaAPI account, and the account allows one concurrent synchronization.

Checked in this repo:

1. `MetaApiWrapper.connect` always calls `get_rpc_connection`, `get_streaming_connection`, `connect` on both, and `wait_synchronized` on the stream.
2. BTC and the 1H US100 book construct that wrapper in `GriffLiveEngine.connect_account`. Gold and the 15m US100 engine construct it in `__init__` and connect on startup. `griff_engine_live_fixed.py` is the same pattern.
3. `monitor_griff.py` names the three systemd units that run together against one account.
4. `update_log.md` records a production `TooManyRequestsError` that masked positions and produced a duplicate US100 order.
5. Candle fetches are per process (`account.get_historical_candles` or `connection.get_historical_candles`) with no shared cache. Gold still passes `startTime=None`, which does not match the call the other engines use.
6. `Restart=always` is in `ftmo_hft_omni.service`, `ftmo_london_reversal.service`, and the gold/US100 setup scripts. A failed process comes back and asks for the slot again.

Conclusion: the hypothesis holds. The hub is the fix we implemented. We did not reproduce the live HTTP 429 against MetaAPI. The slot limit is modeled by `InMemoryBroker` and covered by tests. The production incident in `update_log.md` is the in-repo evidence that the error already happened.

## Rejected designs

**Per-engine asyncio lock.** The engines do not share a process. A lock inside `MetaApiWrapper` cannot see the other two.

**File lock around connect/disconnect.** The holder would have to drop `wait_synchronized` before the next engine could run. That churns the slot on every poll (15s to 30s) and is the reconnect storm in a different shape. Rejected.

**Each engine keeps its stream and serializes only orders.** Orders are not the 429. Synchronization is. Rejected.

**Silent fallback from the hub client to `MetaApiWrapper`.** A hub outage would open three new syncs. The adapter fails closed. Test: `test_griff_engines_share_one_sync_and_do_not_fallback_when_the_hub_is_down`.

**Enabling the hub in the existing unit files.** The user constraint is no live cutover and no edits to running units. The example units live under `deploy/examples/` and are not referenced by `setup_gold_service.sh` or `setup_us100_service.sh`. A test reads those installers and fails if they mention the hub.

**Default `--mode live`.** A mistaken `python -m metaapi_hub` must not touch FTMO. The default is shadow, and shadow cannot place live orders even if `--orders live` is passed (the CLI rejects that combination; the owner also downgrades it).

## What we shipped

- One sync owner, unix socket, engine adapter, flag default off.
- Order policy default deny. Live orders need `--mode live`, `--orders live`, `--enable-live-orders`, and `ODIN_METAAPI_HUB_ORDERS=live` on the hub process. Engines cannot set that.
- Shadow probe (`python -m metaapi_hub.shadow_probe`) runs three clients, asserts one synchronization, and asserts zero broker mutations.
- Duplicate-order window of 3 seconds for identical mutations from the same engine name. This does not replace the engines' own position checks. A process restart gets a new chance to send. That residual risk is the same one `update_log.md` hit, and the hub does not hide it.
- Candle cache of 5 seconds and four attempts on 504, one flight for all clients.
- Timeouts stay timeouts. They do not open a new synchronization. Disconnects do, once, after closing the old slot.
- Hub shutdown closes idle client sockets. `Server.wait_closed()` would otherwise block until every engine disconnects, including on SIGTERM.
- Python 3.9 creates `asyncio.Lock` against the current loop. `asyncio.run` then clears that loop, so the next constructor crashed with "no current event loop". Locks are created on first use. This does not change who is allowed to synchronize or send orders.
- Tests must not assume the SDK is absent. `SDK_MISSING` is forced by hiding `metaapi_cloud_sdk` so a VM that has the package does not open a real client. Off mode, when `MetaApiWrapper` imports, must return that class and must not call `MetaApi(token)` from the test.

## Encounters

- This checkout has no `metaapi_cloud_sdk` and no `config_us100.json`. `MetaApiBroker.synchronize` raises `SDK_MISSING` before any network call. Tests use that path to prove the token is absent from `repr` and from the error.
- `pytest.ini` points `testpaths` at `tests/e2e`. The hub suite is run explicitly so those e2e tests, which expect a local config and the SDK, are not mixed into this result.
- `griff_engine_us100.py` and `griff_engine_gold.py` imported `MetaApiWrapper` at import time, which imports the SDK. They now import the factory. With the flag off, the SDK is imported when the engine is constructed, which is the same dependency as before.
- Production Python on the VM is 3.9 (`PROJECT.md`). The hub uses `from __future__ import annotations` and does not use `asyncio.timeout` or `match`.

## 2026-10-02 resilience pass

Input: the 04:43–06:43 EDT timeout audit on matt-berserker (hub `TimeoutError`×77, `TimeoutException`×32, `TooManyRequests`×4, one 504 on BTC candles, recurring resync warnings; BTC at `Accumulating 0/50` since 06:25 while `IN_TRADE`, process alive).

Root cause of the BTC wedge, reproduced locally against the shadow hub: a 1000-bar candle reply is larger than asyncio's 64 KiB default `readline` limit. The client's reader task raised and exited; every later request waited on a future nobody would resolve; the engine logged timeouts and `0/50` on each poll with no path out. Shadow and test traffic never hit this because `InMemoryBroker` returns 40 bars. Secondary amplifiers: one request at a time per connection (an abandoned candle request delayed the next account read into its own deadline), one RPC at a time across all engines, no client reconnect after a hub restart.

Decisions:

- **Frame limit** is `MAX_MESSAGE_BYTES` on both ends. The protocol already defined that constant for `dumps`/`loads`; the streams simply were not told.
- **Concurrent dispatch per connection**, with a per-connection write lock. In-flight work is not cancelled when a client disconnects: a mutation that reached the broker must finish, and a shared candle flight is still useful to the other engines. Joiners await the flight through `asyncio.shield` for the same reason.
- **Bounded read concurrency (4) instead of strict serialization.** The lock protected nothing the SDK requires; it existed to keep `max_rpc_depth` observable. It is kept for mutations, which are the only calls with a double-fill risk. `--read-concurrency 1` restores the previous behaviour if a reviewer prefers it.
- **Retries are for idempotent reads only.** TIMEOUT, TooManyRequests, and 504 are retried with capped, jittered exponential backoff. A timeout still never opens a new synchronization. Mutations stay at one attempt.
- **Stale candle fallback, 300 s, hub-side only.** Completed 1H bars older than the current hour do not change, so a five-minute-old set is correct data served late. It is served only after a full retry cycle fails, logged at WARNING, counted in health, and never used by the engine for anything the fresh set would not have been used for. No stale data is kept in the engine; entry scanning still requires 50 fresh bars from the call that just returned.
- **Client reattach is the engine's recovery, not a private sync.** On socket loss the client reopens the socket and re-sends `hello`. The fail-closed rule from the first PR stands: if the hub is unreachable the engine errors, it does not construct `MetaApiWrapper`.
- **Engine: `IN_TRADE` before the history gate.** The 50-bar requirement protects EMA-50 and ADX, which only entries use. Position management needs 15 bars for ATR-14 and 3 for the structural stop. Running it with 15–49 bars produces the same numbers as with 60, so this is sequencing, not a strategy change. Under 15 bars the engine holds and says so.
- **A failed position read is not a flat book.** `fetch_positions_safe` distinguishes `None` from `[]`. This closes the `update_log.md` path where a hidden position led to a duplicate order. One confirmed empty read still ends `IN_TRADE`, as before; a confirmation window was considered and rejected because it would delay the strategy's re-arm after a stop-out, which is a strategy change.
- **Not changed, deliberately:** `day_start_equity` resetting on restart, engine poll interval and per-call deadlines (10/12/15 s), `cancel_pending_breakout_orders` sweeping stray `GRIFF_` pending orders on adoption (strategy behaviour: the OCO leg), US100 and Gold engine code (they benefit from the hub and client fixes without edits).

## Cutover approval

Odin approved production cutover on 2026-10-01 after Stage 2 (read-only live) and the Stage 3 safe canary were documented. Operators then reported Stage 4 PASS the same day (~12:44–12:49 EDT). The approval, the installed unit, and the rollback are in [CUTOVER.md](CUTOVER.md) and [evidence/2026-10-01-stage4-cutover.md](evidence/2026-10-01-stage4-cutover.md). The commits that recorded this do not install units or change the VM. The report says strategy and config JSON were unchanged and only factory wiring was added. With `ODIN_METAAPI_HUB` unset, that factory returns `MetaApiWrapper`. The hub remains plumbing in front of the existing engines.
