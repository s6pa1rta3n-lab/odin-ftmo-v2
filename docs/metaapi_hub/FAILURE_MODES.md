# Failure modes

| Symptom | Before | With the hub |
| --- | --- | --- |
| TooManyRequests, max 1 concurrent sync | Each engine calls `wait_synchronized`. The losers spin or restart. | Clients are forbidden from synchronizing. The owner retries the same slot with backoff (`0.05s`, `0.1s`, `0.2s`, ... up to 5 attempts) and does not open a second stream. If another process still holds the slot, the hub stops with `SYNC_FAILED` instead of storming. |
| 504 on historical candles | Every engine retries on its own against a terminal that is not stably synced. | One flight retries up to 4 times. Other engines await that flight. A 5s cache absorbs the poll loop. |
| "not connected to broker" on reads | Each engine reconnects and asks for a new sync. | Readers that saw the same generation share one `close()` plus one `synchronize()`. |
| "not connected to broker" on an order | A naive retry can double-fill. | The mutation is returned once. It is not sent again. The next read performs the single reconnect. |
| Duplicate orders after a hidden position | `update_log.md`: TooManyRequests made the book look flat. | The hub does not change position logic. It keeps one stream so position reads are against the synchronized terminal. Identical order payloads inside 3 seconds collapse to the first receipt. |
| Hub process down while engines are flagged on | Not applicable today. | Engines fail `connect_account` / the poll loop. They do not open a private MetaAPI sync. |
| Shadow engine pointed at a live hub | Not applicable today. | `hello` returns `MODE_MISMATCH`. |
| Engine account id differs from the live hub | A mis-set unit could trade the wrong book if it synced itself. | Live hub rejects `ACCOUNT_MISMATCH`. Shadow hub accepts any id because it has no broker account. |
| Token in logs or on the socket | Engines pass the token into `MetaApiWrapper`. | The adapter drops the token. The hub reads its own config file in live mode and does not put the token in health output or `repr`. |
| Dry-run mistaken for a fill | A success dict would set US100/Gold to `IN_TRADE`. | Deny raises `ORDERS_DISABLED`. Dry-run raises `DRY_RUN` with `sent: false` and `numericCode: null`. |
| Live orders enabled by accident | Direct wrappers trade whenever the engine is running. | CLI exits unless `--enable-live-orders` and `ODIN_METAAPI_HUB_ORDERS=live` are both present, and `--mode` is `live`. Example unit files do not contain those switches. |

## Added 2026-10-02 (resilience)

Observed on matt-berserker 04:43–06:43 EDT: hub-side `TimeoutError`/`TimeoutException`, `TooManyRequests`, one `504` on BTC candles, recurring "resynchronized … did not finish in time", and BTC stuck at `Accumulating history: 0/50` from 06:25 while `IN_TRADE`.

| Symptom | Before | Now |
| --- | --- | --- |
| Candle reply larger than 64 KiB | asyncio's default `readline` limit killed the engine's hub reader task on the first full history page. Every later request timed out; the process looked alive. The first visible sign was `Historical candle fetch timed out`, then `Primary get_account_information timed out`, then `0/50` forever. | Client and server create their streams with `limit=MAX_MESSAGE_BYTES` (8 MB). An oversized frame is logged with its size and treated as a connection loss, which the client recovers from (below). Health shows `server_oversized_frames` and `max_message_bytes`. |
| Engine gave up on a slow candle call | The hub served one request per connection at a time. The abandoned candle request still ran, so the engine's next account and position requests queued behind it and also hit their deadlines. | Requests on one connection are served concurrently; replies are written under a lock. A stale request finishing late only warms the cache. |
| Hub restarts (or drops the socket) | The engine's client had no reconnect. All requests failed until the engine was restarted. | On the next request the client reattaches with bounded jittered backoff (3 attempts), re-sends `hello`, and resends an idempotent read once. Mutations are never resent. `detach()` by the engine stays final. |
| SDK `TimeoutException` / `TooManyRequests` on a read | One attempt. Gold logged `Loop error: TIMEOUT`. | `read()` retries retryable errors up to `--read-attempts` (3) with exponential backoff, cap `--backoff-max`, and jitter `--backoff-jitter`. Still no new synchronization on a timeout. `read_retries` and `last_upstream_error` in health. |
| Candle fetch fails on every attempt | Only 504 was retried. Failure returned to the engine, which then counted `0/50`. | Any retryable error is retried `--candle-attempts` times with the same backoff. If all fail, the last good set for that symbol/timeframe is served when younger than `--candle-stale-ttl` (300 s), with a WARNING and `candle_stale_serves` in health. Older than that, the error is surfaced. `0` disables. |
| One slow RPC holds every read | Reads and mutations shared one lock. A 20 s candle RPC blocked all account and position reads for all engines. | Reads run under a semaphore of `--read-concurrency` (4). Mutations are still strictly one at a time. `1` restores the old behaviour. |
| Reconnect leaks SDK clients | `MetaApi(token)` was constructed again on every reconnect; the previous client's websocket stayed open. | The client and account handle are created once. `wait_synchronized` has its own `--sync-timeout` (60 s). `close()` is bounded by `--close-timeout` (10 s) so a hung SDK close cannot be awaited forever under the sync lock. |
| Engine `IN_TRADE` with fewer than 50 bars | `step()` returned `ACCUMULATING_HISTORY` before the `IN_TRADE` branch. The position was re-synced but trailing-stop management never ran. | `IN_TRADE` is handled before the setup-scan gate. With ≥ 15 bars the ratchet runs (identical numbers: ATR-14 uses 15 bars, the structural stop 3). With fewer, the engine logs that it is holding the ticket and defers. Setup scanning still needs 50. |
| Position read fails while `IN_TRADE` | `fetch_positions_safe` returned `[]` on error. The engine logged "Active trade closed on broker" and went `SEARCHING` with the ticket still open, which is the `update_log.md` duplicate-exposure path. | Returns `None` on failure. State is kept and the warning names the ticket. One **successful** empty read is still what flips `IN_TRADE` to `SEARCHING`. |
| Candle fetch times out once per poll | One 15 s attempt per 30 s cycle. | Two bounded attempts per cycle with a 1–2 s jittered pause. On the hub path the second attempt joins the flight the hub still has running. Consecutive failures are counted (`candle_fetch_failures`) and recovery is logged. |

None of these paths close, cancel, or modify a broker position. The engine's only mutations remain the strategy's own: cancelling the unfilled opposite pending leg once a position exists, and tightening the stop on a new completed bar.

## Added 2026-10-02 (candle single-flight release)

Observed on the live hub PID 2849217 at 19:26 ET. Historical candle attempts 1/4 and 2/4 logged at the 20 s SDK timeout; attempt 3 never logged and `candle_retries` froze at 2. No further candle HTTP line. Engines logged `timed out after 15s ()` and history `0/50`.

| Symptom | Before | Now |
| --- | --- | --- |
| Candle SDK call ignores cancellation | `MetaApiBroker._call` uses `asyncio.wait_for`. On Python 3.9 that does not raise until the cancelled SDK task finishes, so the shared candle flight never reached attempt 3. `historical_candles` is one shielded flight and the server does not cancel the handler when the engine's 15 s timeout fires, so every later candle request joined the stuck flight. | A cancelled candle call, or one that passes the existing `--rpc-timeout`, abandons the SDK task instead of waiting for it. When the last waiter leaves, the flight is dropped from the slot immediately. The next request starts a new call. A call that finishes normally is still shared. No new timeout flag. Health: `candle_flights_released`, `abandoned_calls`, `abandoned_calls_pending`. |

Entry, stop, size, and session are unchanged. `entry_guard` and `book_sync` are unchanged.

## Added 2026-10-02 (US100 / Gold restart adoption)

Observed on matt-berserker ~11:45 ET: `griff_engine_us100` was restarted after the double-book guard deploy while the broker still held BUY `172676142` (US100.cash 8.88 @ 30807.38, SL/TP set). The new process stayed `SEARCHING`.

| Symptom | Before | Now |
| --- | --- | --- |
| Restart mid-trade, outside the entry window (US100 after 11:30 ET, Gold after 10:00 ET) | The only position read on the `SEARCHING` path was the pre-entry check, which runs inside the window. Outside it the engine made no broker call, never saw the open ticket, and the 16:00 hard close (gated on `IN_TRADE`) would not have fired. BTC was unaffected: `GriffLiveEngine.step()` re-syncs positions every cycle. | `modules/book_sync.py` (`BrokerBookSync`) is called at the top of `step()` on the first iteration after startup, after the engine's own `connect()`, and whenever the hub client's `reattaches` counter has moved. It reads positions and adopts the one matching the symbol or `GRIFF_US100*` / `GRIFF_GOLD*` as `IN_TRADE` with the broker's ticket, size, SL, TP. Journal line: `Adopting open US100 position ticket 172676142 BUY 8.88 US100.cash @ 30807.38 SL=… TP=… -> IN_TRADE. Reason: engine startup`. |
| Startup position read fails | Not applicable (no read). | Unknown is not flat. The sync stays pending and is retried each iteration; while pending the `SEARCHING` branch evaluates no setup, so nothing can be placed before the book state is known. |
| Two matching positions open at restart | Pre-entry check adopted the first (inside the window only). | Same, now also outside the window: the first is managed, the rest are logged as an error, no entry is ever added. |
| Gold `IN_TRADE` position read fails | Bare exception → `Loop error`, state unchanged by accident. | Routed through the same helper: `None` keeps `IN_TRADE`; one successful empty read returns to `SEARCHING`. |

Adoption places nothing and never closes or modifies a position. The 16:00 hard close is unchanged; it now simply has the correct state to act on after a restart.

## Added 2026-10-02 (Gold place-time double-book guard)

The US100 race of 2026-10-02 (15:09:48 UTC BUY 9.46 placed → 15:09:58 broker fill `172673462` → 15:10:03 hub `NOT_CONNECTED` for that same mutation → engine stayed `SEARCHING` → 15:14:17 BUY 8.88 `172676142` placed on top → `172673462` SL −861.81) was closed for US100 by `modules/entry_guard.py` and `place_entry()` in `griff_engine_us100.py` (PR #31). `griff_engine_gold.py` had the identical place pattern (catch, log `Failed to place order`, do nothing) and the restart adoption above only covers startup and reconnect. The same guard is now wired into Gold.

| Symptom | Before | Now |
| --- | --- | --- |
| Gold entry filled, acknowledgement lost (`NOT_CONNECTED`, `TIMEOUT`, `CLOSED`, `BROKER_ERROR`, socket drop, any unexpected exception) | `Failed to place order: …`, state stayed `SEARCHING`, no position read. The next 15 s iteration re-evaluated the breakout (still true) and sent a second `GRIFF_GOLD_BREAKOUT` market order while the first was live. | `reconcile_after_place_error()` marks the entry unreconciled (`entry_sync_required`), waits 2 s, and re-reads positions. A matching `XAUUSD` / `GRIFF_GOLD*` position is the fill: `Adopting open Gold position ticket … -> IN_TRADE. Reason: pre-entry position check found an open Gold position`. The one-trade-per-day bookkeeping is applied exactly as on a confirmed success. |
| Reconciling read also fails | n/a | `entry_sync_required` stays set. The `SEARCHING` branch reconciles instead of evaluating setups, so no price poll and no order until a position read succeeds. Unknown is not flat. |
| Gold ticket already open when the breakout fires (other process, earlier instance, fill found late) | Placed on top of it. | `confirm_flat_before_entry()` requires a fresh, successful, empty read before every order. A matching position is adopted; two or more are logged as an error and the first is managed. Nothing is ever added to the book. |
| Hub refusal (`ORDERS_DISABLED`, `DRY_RUN`, `COMMENT_REQUIRED`, `BAD_REQUEST`, `FORBIDDEN_SYNC`) | Same catch-all. | Known never to have reached the broker: no 2 s wait, but the book is still re-read before the next entry. A refused order does not consume the day's trade, as before. |

Strategy parameters, the 03:15–10:00 window, sizing, the 16:00 hard close, and the startup/reconnect adoption are unchanged. The guard places nothing on its own and never closes or modifies a position.

## Operator signals

`health` (no login beyond the socket file mode) returns:

- `synchronize_calls` — successful owner syncs. Steady state after start is `1`. It increases by one on a real reconnect, not by one per engine.
- `clients` — engine names currently subscribed. Expect `btc`, `us100`, and `gold` once those processes are flagged on.
- `orders_live` — must stay `false` until a later, separate approval.
- `broker_order_calls` / `broker_mutation_calls` — must stay `0` in shadow, deny, and dry-run.
- `single_flight_joins` and `candle_timeouts` — non-zero joins with a small timeout count means the engines shared a 504 instead of multiplying it.
- `duplicate_suppressions` — identical orders that were not sent twice.
- `read_retries`, `candle_retries` — upstream hiccups the hub absorbed. Rising during degradation is expected; the engines keep their deadlines.
- `candle_stale_serves` — fetches answered from the last good set. Non-zero means candles were unavailable for a full retry cycle; look at `last_upstream_error`.
- `candle_flights_released` / `abandoned_calls` — a candle flight was dropped because every caller had already left, or an SDK call was cancelled without waiting for it. The next request starts a new call. `abandoned_calls_pending` is how many of those SDK tasks are still running.
- `last_upstream_error` — most recent upstream failure, as `method: CODE: message`.
- `server_oversized_frames` — must stay `0`.
- `read_concurrency`, `max_message_bytes` — configuration echo.

`python3 scripts/hub_health.py [socket]` prints this snapshot.

Health contains no token and no raw config.
