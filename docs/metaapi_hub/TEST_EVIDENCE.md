# Test evidence

The suite does not import a usable MetaAPI SDK, does not open a broker socket, and does not read `config_us100.json`. Order tests that return `numericCode` 10009 use `InMemoryBroker` only. `MetaApiBroker.synchronize` is covered by the missing-SDK path and must raise `SDK_MISSING`.

Command:

```sh
sh scripts/run_metaapi_hub_tests.sh
```

Results are filled in after that command runs on this branch. If this file still says "pending", the run has not been recorded yet.

## Pending

Record:

- pytest summary line
- shadow probe `ok`, `synchronize_calls`, `broker_order_calls`
- any failure and the fix

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
- An external holder causes backoff, not a tight loop, then one sync once the holder is gone.
- The server and the client both reject `synchronize` / `wait_synchronized`.
- Closing one engine client leaves the broker slot up.
- Deny and dry-run cover every mutating method and leave `order_calls` and `mutation_calls` at 0.
- Shadow downgrades `--orders live`. Live orders without `ODIN_METAAPI_HUB_ORDERS=live` are denied.
- Duplicate window and parallel orders from two engines.
- Comment and volume checks.
- Live owner rejects a shadow client and a mismatched account id, with zero syncs.
- Default flag off, unknown flag off, direct wrapper import fails closed without the SDK.
- Shadow probe across btc, us100, and gold.
- `GriffLiveEngine` for BTCUSD, US100.cash, and XAUUSD, plus `US100Engine` and `GoldEngine`, one synchronization.
- Hub outage does not fall back to a private sync.
- `GriffLiveEngine.run_self_test` against the shadow hub sends no orders.
- Installer scripts and the existing unit files do not mention the hub. Example units contain `DO NOT` and do not contain `--orders live` or `--enable-live-orders`.
- CLI rejects live orders unless every interlock is present.
