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

## Operator signals

`health` (no login beyond the socket file mode) returns:

- `synchronize_calls` — successful owner syncs. Steady state after start is `1`. It increases by one on a real reconnect, not by one per engine.
- `clients` — engine names currently subscribed. Expect `btc`, `us100`, and `gold` once those processes are flagged on.
- `orders_live` — must stay `false` until a later, separate approval.
- `broker_order_calls` / `broker_mutation_calls` — must stay `0` in shadow, deny, and dry-run.
- `single_flight_joins` and `candle_timeouts` — non-zero joins with a small timeout count means the engines shared a 504 instead of multiplying it.
- `duplicate_suppressions` — identical orders that were not sent twice.

Health contains no token and no raw config.
