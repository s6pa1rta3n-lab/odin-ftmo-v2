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

## Encounters

- This checkout has no `metaapi_cloud_sdk` and no `config_us100.json`. `MetaApiBroker.synchronize` raises `SDK_MISSING` before any network call. Tests use that path to prove the token is absent from `repr` and from the error.
- `pytest.ini` points `testpaths` at `tests/e2e`. The hub suite is run explicitly so those e2e tests, which expect a local config and the SDK, are not mixed into this result.
- `griff_engine_us100.py` and `griff_engine_gold.py` imported `MetaApiWrapper` at import time, which imports the SDK. They now import the factory. With the flag off, the SDK is imported when the engine is constructed, which is the same dependency as before.
- Production Python on the VM is 3.9 (`PROJECT.md`). The hub uses `from __future__ import annotations` and does not use `asyncio.timeout` or `match`.
