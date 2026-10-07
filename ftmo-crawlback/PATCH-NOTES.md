# Crawl-back patch notes — 2026-10-07 (paranoid pre-arm)

Odin via BTC Strategies review before tonight 18:00 ET arm. Box-only; not armed; VM untouched.

## Fixes in `crawlback_eurusd_asia.py`

1. **`crawl_positions()` — comment-only isolation**  
   Dropped `(symbol).startswith("EUR")`. Positions match only when `comment == CRAWLBACK_EURUSD_ASIA`.

2. **`cancel_orders()` — scoped**  
   Cancels only crawl pendings: `comment == COMMENT`, or (if comment missing) exact `symbol == EURUSD`. Never cancels unrelated symbols/comments.

3. **`CRAWL_TEST_ORDER=1` one-shot**  
   After token load: refresh pip/$ from MetaAPI, place min-lot (`LOT_STEP`, default 0.01) EURUSD market with hard SL/TP (±`SL_PIPS` / `RR`) and comment `CRAWLBACK_EURUSD_ASIA`, log full result, close if opened, exit 0 on success path / non-zero on hard failure. Works with `CRAWL_ARMED=0`. Does **not** enter the polling loop. Do not leave `CRAWL_TEST_ORDER=1` in the systemd unit.

4. **Pip $/lot from MetaAPI specification**  
   `GET /users/current/accounts/{id}/symbols/{symbol}/specification` → `tickValue * (PIP_SIZE / tickSize)` cached into `PIP_VALUE_PER_LOT`. Falls back to env/default `10` with alert log on failure. Called before sizing in the normal loop and before the test order.

Also: `crawlback-eurusd-asia.service` documents `CRAWL_TEST_ORDER` (commented; unit still `CRAWL_ARMED=0`, no permanent test flag).
