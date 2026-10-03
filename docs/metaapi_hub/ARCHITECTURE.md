# Architecture

## What is broken today

Three engine processes trade one MetaAPI account. Each process builds its own `MetaApiWrapper` and `connect()` opens both an RPC connection and a streaming connection, then calls `wait_synchronized()`:

- `MetaApiWrapper.connect` in `MetaApiWrapper.py`
- `GriffLiveEngine.connect_account` in `griff_engine_live.py` (BTC and US100, selected with `--symbol`; the fixed copy is `griff_engine_live_fixed.py`)
- `US100Engine` in `griff_engine_us100.py`
- `GoldEngine` in `griff_engine_gold.py`

`monitor_griff.py` watches these unit names:

- `griff_engine.service` — US100
- `griff_engine_btc.service` — BTCUSD
- `griff_engine_xau.service` — XAUUSD

The Stage 3 canary on matt-berserker stopped and restored different unit names: `griff_engine_btc`, `griff_engine_us100`, and `griff_engine_gold`. Cutover and rollback use those three. Stopping the names in `monitor_griff.py` can leave `griff_engine_us100` or `griff_engine_gold` running. See [CUTOVER.md](CUTOVER.md).

MetaAPI allows one synchronized copy of an account. The second and third `wait_synchronized()` receive TooManyRequests. `update_log.md` already records that failure in production: the error hid open positions and a duplicate US100 breakout was placed.

The same contention produces the other symptoms:

- **Reconnect storms.** The unit files use `Restart=always`. A failed sync exits or retries, and the new process asks for another synchronization slot.
- **504 on historical candles.** Each engine calls `get_historical_candles` on its own. While the terminal is fighting for the sync slot, the history API times out at the gateway.
- **"not connected to broker".** RPC such as positions, prices, and orders requires the terminal stream. Competing syncs leave the account disconnected, so reads come back empty and the strategy treats a live position as flat.

An in-process lock does not fix this. The engines are separate operating-system processes. A lock that forces them to take turns connecting and disconnecting would churn the only slot and recreate the 504s. The working shape is one long-lived synchronization, with the engines as clients.

## Layout

```
griff_engine_live.py        symbol BTCUSD / US100.cash / XAUUSD
griff_engine_us100.py
griff_engine_gold.py
        |
        |  ODIN_METAAPI_HUB=off (default)
        |      -> MetaApiWrapper, unchanged
        |
        |  ODIN_METAAPI_HUB=shadow or on
        v
HubBackedWrapper  --unix socket JSON-->  metaapi_hub server
                                              |
                                              |  one SyncOwner
                                              v
                                    InMemoryBroker (shadow)
                                    or MetaApiBroker (live, one stream)
                                              |
                                              v
                                         MetaAPI / FTMO
```

The socket is local. There is no TCP listener. Clients cannot call `synchronize`, `wait_synchronized`, or `connect`. The server rejects those methods with `FORBIDDEN_SYNC`.

`HubBackedWrapper` exposes the methods the engines already call: `connect`, `get_account_information`, `get_positions`, `get_orders_rest`, `cancel_order`, `connection.get_historical_candles`, `get_symbol_price`, `create_market_*_order`, `create_stop_*_order`, `close_position`, `modify_position`, and `account.get_historical_candles`. Gold's `startTime=None` argument is ignored on this path. That keyword is the invalid argument removed from the other 15m fetch in commit `96fadca`. The gold strategy file is unchanged; the adapter absorbs it.

Closing `streaming_connection` or `connection` unsubscribes that engine. It does not drop the shared synchronization.

## Flags

| Control | Where | Default | Effect |
| --- | --- | --- | --- |
| `ODIN_METAAPI_HUB` | engine process | unset / `off` | `off` uses `MetaApiWrapper`. `shadow` and `on` use the hub. Unknown values stay off. |
| `ODIN_METAAPI_HUB_SOCKET` | engine process | `/tmp/odin-metaapi-hub.sock` | Unix socket path. |
| `--mode` | hub process | `shadow` | `shadow` uses `InMemoryBroker` and never imports the SDK. `live` loads the token from `--config` and opens one MetaAPI stream. |
| `--orders` | hub process | `deny` | `deny` and `dry_run` never call broker order methods. `live` is refused unless the interlocks below are all set. |
| `--enable-live-orders` | hub process | absent | Required acknowledgement for `--orders live`. |
| `ODIN_METAAPI_HUB_ORDERS=live` | hub process | absent | Second acknowledgement, read on every mutation. |

Shadow mode forces `orders_mode` off `live`. A shadow engine (`ODIN_METAAPI_HUB=shadow`) is rejected by a live hub (`MODE_MISMATCH`) so a rehearsal client cannot attach to a process that is allowed to trade.

When the engine flag is on, a dead hub does **not** fall back to `MetaApiWrapper`. Falling back would open another synchronization and bring the storm back. The engine stops instead.

## Reads and writes

Reads (account, positions, orders, prices, specs, margin, candles) run under a small semaphore (`--read-concurrency`, default 4; mutations keep an exclusive lock). On `not connected to broker`, every waiter that saw the same generation shares one reconnect. The owner closes the old slot before opening another, so a reconnect cannot leak a second synchronization. Other retryable errors (TIMEOUT, TooManyRequests, 504) are retried a bounded number of times with capped, jittered exponential backoff; a timeout never opens a new synchronization.

Historical candles are single-flight per `(symbol, timeframe, limit)` and cached for 5 seconds. Retryable errors are retried on that one flight. Concurrent engines join the flight through `asyncio.shield`; they do not each retry, and one engine giving up does not cancel the flight while another engine is still waiting. A candle call that is cancelled, or that passes the broker's existing `--rpc-timeout`, is abandoned instead of waiting for an SDK task that does not finish, and a flight whose last waiter has left is dropped from the slot so the next request starts a new call. There is no separate candle timeout. If every attempt fails, the last good set for that key is served while it is younger than `--candle-stale-ttl` (default 300 s), with a warning and a health counter.

Socket frames are newline-delimited JSON up to `MAX_MESSAGE_BYTES` (8 MB); both stream readers are created with that limit because one history page exceeds asyncio's 64 KiB default. Requests on one connection are served concurrently so an abandoned slow request does not delay the next one. The client reattaches to the hub on the next request after the socket drops; it re-sends `hello` and never synchronizes.

Mutations (market, stop, limit, cancel, close, partial close, modify) are never retried. A disconnect during an order returns the error and leaves a resync for the next read. The same engine, method, symbol, side, volume, comment, and prices inside a 3 second window returns the first receipt instead of sending a second order.

Entry orders must carry a comment and a finite volume of at least 0.01. Dry-run and deny raise. They do not return a success dict. The US100 and Gold loops only mark `IN_TRADE` when the order call returns, so a refused order does not advance strategy state.

`numericCode` 10009 is returned only by a broker call. Dry-run receipts set `numericCode` to null and `sent` to false. `GriffLiveEngine.execute_live_trade` treats anything other than 10009 as failure.

## What this does not change

Strategy math, risk percent, session windows, and order comments stay in the engine files. `MetaApiWrapper` itself is not rewritten. London and Omni units are out of this hub; they are separate processes and are not switched by the flag. Do not start a live hub while those units, or the three Griff units, are still synchronizing on their own.
