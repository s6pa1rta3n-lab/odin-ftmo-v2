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
- `last_upstream_error` — most recent upstream failure, as `method: CODE: message`.
- `server_oversized_frames` — must stay `0`.
- `read_concurrency`, `max_message_bytes` — configuration echo.

`python3 scripts/hub_health.py [socket]` prints this snapshot.

Health contains no token and no raw config.
