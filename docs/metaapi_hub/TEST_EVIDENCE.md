# Test evidence

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
- Installer scripts and the existing unit files do not mention the hub. Example `ExecStart` lines do not contain `--orders live` or `--enable-live-orders`.
- CLI rejects live orders unless every interlock is present.
- Python 3.9: an owner built after `asyncio.run()` still synchronizes once and denies orders.
- `SDK_MISSING` is forced by hiding the SDK module, so an installed SDK cannot turn the test into a live synchronize.
- Off mode returns the direct wrapper when that module imports, and raises when the import is blocked. Neither path builds `HubBackedWrapper` or calls `MetaApi(token)`.

## Encounter during the run

The first full run hung. `HubServer.close` called `wait_closed()` while Griff clients were still blocked in `readline`, so shutdown never returned. The fix closes those sockets before waiting. Re-run: 27 passed in 0.38s. That behavior is now what SIGTERM uses as well, so a hub stop does not wait for the engines to exit.
