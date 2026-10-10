# btc-advisor-autoexec

Execution endpoint for FTMO BTC Advisor setups. **Order placement is DISABLED by
default** (`AUTOEXEC_ORDERS_ENABLED=0`). In dry-run every guard runs against live
read-only MetaAPI data (account, positions, quote, symbol spec, today's deals), the
would-be order is logged, and nothing is sent.

Authorization

- Odin James, Strategy Implementer chat, Sat 2026-10-10 05:45 ET: build as a DRAFT PR,
  orders disabled by default, dry-run mode, tests. Trading Ops deploys, arms and owns
  rollback on the VM after Odin's OK. This code does not deploy, place live orders, or
  touch any VM.
- Correction 05:47 ET: equity halt is **$90,750** (not $91,000); commission fallback
  configurable, default **$27 round-trip per 1.0 lot**, broker-reported value preferred.
- Spec change 05:55 ET: the "max 1 auto position / no entry while a manual BTC
  position is open" guard is **replaced** by the two-position rule in
  [Guard 3](#3-position-count-and-the-second-position-rule).

Target: FTMO login `541458001`, MetaAPI account `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf`,
symbol `BTCUSD`, London client host `https://mt-client-api-v1.london.agiliumtrade.ai`
(the same REST host/transport pattern as the crawl-back package). All configurable via env.

Nothing here touches `modules/entry_guard.py`, `modules/book_sync.py`, `metaapi_hub/`
or any other engine. The package is self-contained under this directory and uses only
the Python standard library (Python 3.9+, as on the VM).

---

## Layout

```
btc-advisor-autoexec/
  autoexec/
    config.py           env -> Config; token loading (never logged)
    broker.py           MetaAPI REST client (urllib, London host); reads + one trade() call
    guards.py           request validation, position classification, tighten-only, daily cap, equity halt
    sizing.py           $250 risk sizing incl. spread + commission, floor to volume step
    commission.py       commission source resolution (spec -> deals -> env)
    second_position.py  the 05:55 ET two-position rule
    trading_day.py      Europe/Prague day boundary (DST-aware)
    state.py            HALT latch file, state.json (daily-cap latch, post-place cooldown)
    engine.py           Executor: reads -> guards -> sizing -> (gated) order
    server.py           stdlib HTTP endpoint
    cli.py / __main__   CLI equivalent
  scripts/preflight.py  read-only preflight for Trading Ops
  deploy/btc-advisor-autoexec.service.example   systemd unit, orders disabled
  tests/                unit tests with a fake MetaAPI broker (no network, no token)
```

## Interface

### HTTP (loopback by default, `127.0.0.1:8787`)

| Method | Path       | Body                                                                 | Purpose |
|--------|------------|----------------------------------------------------------------------|---------|
| GET    | `/health`  | –                                                                    | liveness, arming flags; no broker call |
| GET    | `/status`  | –                                                                    | read-only guard states from live data |
| POST   | `/setup`   | `{"side":"BUY|SELL","entry_type":"MARKET","stop":<px>,"target":<px>}` + optional `request_id`, `dry_run:true` | entry decision |
| POST   | `/tighten` | `{"stop":<px>}` + optional `position_id`, `request_id`, `dry_run:true` | tighten the auto position's stop |

If `AUTOEXEC_API_KEY` is set, every request must send `X-Autoexec-Key`.

Decision JSON (both routes) always carries: `ok`/`accepted`, `action`, `mode`
(`dry_run`|`live`), `sent`, `code`, `reason`, `guards` (equity, halt, book, daily P&L,
cooldown, …), and for entries `lots`, `risk_usd`, `per_lot_loss`, `spread`,
`spread_cost_per_lot`, `commission_per_lot_roundtrip`, `commission_source`,
`stop_distance`, `reward_risk`, `sizing`, `commission`, `order` (the payload that was
or would be sent), `broker_response` when something was sent, and `second_position`
when a BTC position was already open.

```bash
curl -s -XPOST 127.0.0.1:8787/setup -d '{"side":"BUY","entry_type":"MARKET","stop":84500,"target":86500}'
curl -s -XPOST 127.0.0.1:8787/tighten -d '{"stop":84800}'
curl -s 127.0.0.1:8787/status
```

### CLI

```bash
cd /path/to/btc-advisor-autoexec
python3 -m autoexec serve
python3 -m autoexec setup --side BUY --entry-type MARKET --stop 84500 --target 86500 [--dry-run]
python3 -m autoexec tighten --stop 84800 [--position-id ID] [--dry-run]
python3 -m autoexec status
python3 -m autoexec kill | unkill          # kill file on/off
python3 -m autoexec halt-clear --yes       # manual re-enable after an equity halt
```

`setup`/`tighten` exit 0 when accepted (dry-run or live), 2 when rejected.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `AUTOEXEC_TOKEN` | – | MetaAPI token (preferred over the file). Never logged. |
| `AUTOEXEC_TOKEN_SOURCE` | `/home/solveetcoagula/odin_ftmo/config_us100.json` | JSON file with `metaapi.token` (or `metaapi_token`). |
| `AUTOEXEC_ACCOUNT_ID` | `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` | MetaAPI account id. |
| `AUTOEXEC_EXPECTED_LOGIN` | `541458001` | Broker login that `account-information` must report; mismatch refuses everything. |
| `AUTOEXEC_SYMBOL` | `BTCUSD` | |
| `AUTOEXEC_CLIENT_HOST` | `https://mt-client-api-v1.london.agiliumtrade.ai` | MetaAPI client REST host. |
| `AUTOEXEC_ORDERS_ENABLED` | `0` | **Arming flag.** `1` allows `/trade` calls. |
| `AUTOEXEC_KILL` | `0` | Kill switch (env). |
| `AUTOEXEC_KILL_FILE` | `<state_dir>/KILL` | Kill switch (file). Presence blocks every entry and modify, no restart needed. |
| `AUTOEXEC_MAX_RISK_USD` | `250` | Guard 2. |
| `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP` | `27` | Fallback round-trip commission per 1.0 lot (Odin's advisor figure). |
| `AUTOEXEC_COMMISSION_SOURCE` | `auto` | `auto` (spec → deals → env), or pin `spec` / `deals` / `env`. Pinned sources with no data fail closed. |
| `AUTOEXEC_COMMISSION_LOOKBACK_DAYS` | `30` | Window for the deals-derived commission. |
| `AUTOEXEC_MAX_POSITIONS_TOTAL` | `2` | Guard 3 (values above 2 are refused). |
| `AUTOEXEC_SECOND_POSITION_MIN_RR` | `2.0` | Guard 3 condition 2. |
| `AUTOEXEC_MIN_MARGIN_LEVEL_PCT` | `200` | Guard 3 condition 4. |
| `AUTOEXEC_MARGIN_PER_LOT_USD` | unset | Margin estimate override (per 1.0 lot). |
| `AUTOEXEC_SYMBOL_LEVERAGE` | unset | Margin estimate: notional / leverage. |
| `AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE` | `0` | Opt-in last-resort margin estimate from `account.leverage`. |
| `AUTOEXEC_DAILY_LOSS_CAP_USD` | `500` | Guard 5. |
| `AUTOEXEC_DAY_TZ` | `Europe/Prague` | FTMO day boundary. |
| `AUTOEXEC_EQUITY_HALT_USD` | `90750` | Guard 6. |
| `AUTOEXEC_HALT_FILE` | `<state_dir>/HALT` | Halt latch file. |
| `AUTOEXEC_POST_PLACE_COOLDOWN_SEC` | `60` | No new entry for this long after any place attempt (ambiguous-fill protection). |
| `AUTOEXEC_MAGIC` | `20261010` | Magic number on the auto-trader's orders (must be non-zero). |
| `AUTOEXEC_COMMENT` | `BTC_ADVISOR_AUTO` | Order comment. |
| `AUTOEXEC_STATE_DIR` | `/home/solveetcoagula/btc-advisor-autoexec/state` | HALT, KILL, `state.json`, log. |
| `AUTOEXEC_LOG_PATH` | `<state_dir>/autoexec.jsonl` | JSON-lines log. |
| `AUTOEXEC_BIND_HOST` / `AUTOEXEC_BIND_PORT` | `127.0.0.1` / `8787` | |
| `AUTOEXEC_API_KEY` | unset | Optional shared secret for the HTTP endpoint. |
| `AUTOEXEC_HTTP_TIMEOUT_SEC` / `AUTOEXEC_TRADE_TIMEOUT_SEC` | `30` / `120` | |

## Guards (server-side, in evaluation order)

Every live read must succeed or the request is rejected (`READ_FAILED`); the broker
login must equal `AUTOEXEC_EXPECTED_LOGIN` (`ACCOUNT_MISMATCH`). The kill switch is
checked first (`KILL_SWITCH`).

### 1. Entry type and SL/TP
`entry_type` must be `MARKET` (`ENTRY_TYPE_NOT_MARKET`). `stop` and `target` are
required and positive (`MISSING_SL`, `MISSING_TP`) and must be on the correct side of the
live quote (`SL_WRONG_SIDE`, `TP_WRONG_SIDE`). SL and TP are attached in the same
`ORDER_TYPE_BUY|SELL` request as `stopLoss` and `takeProfit`. An order is never built
without both.

### 2. Risk sizing ($250 max incl. costs)
```
value_per_unit = lossTickValue|profitTickValue|tickValue / tickSize   (else contractSize; else fail closed)
stop_distance  = ask - stop  (BUY, fills at ask)   |   stop - bid  (SELL, fills at bid)
per_lot_loss   = stop_distance * value_per_unit + (ask - bid) * value_per_unit + commission_roundtrip
lots           = floor_to_step(250 / per_lot_loss, volumeStep), capped at maxVolume
risk_usd       = lots * per_lot_loss
```
If `lots < minVolume` the entry is skipped (`SKIP_MIN_VOLUME`). Spread, commission (and
its source), and per-lot loss are logged on every decision, including rejected ones.

Commission source (`commission_source` in every decision):
1. `spec` – a commission field on the MetaAPI symbol specification, if the broker exposes one
   (MetaAPI's documented spec has none, so this is normally absent).
2. `deals` – observed from the account's own closed `BTCUSD` round trips in the last
   `AUTOEXEC_COMMISSION_LOOKBACK_DAYS`: Σ|commission| over IN+OUT deals of positions with
   both legs in the window ÷ Σ IN volume. Open positions (one leg) are ignored.
3. `env` – `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP` (default 27).

### 3. Position count and the second-position rule
All open `BTCUSD` positions count, manual (magic 0) and auto alike.

- 0 open: normal single-entry guards.
- ≥ `AUTOEXEC_MAX_POSITIONS_TOTAL` (2) open: `MAX_POSITIONS`.
- 1 open: a second entry is allowed only if **all** of the following hold
  (first failure wins, all values logged under `second_position`):

| # | Condition | Reject code |
|---|---|---|
| 1 | Every existing BTC position has SL at breakeven or better (long: `SL >= openPrice`; short: `SL <= openPrice`; missing/zero SL fails). | `SECOND_SL_NOT_BREAKEVEN` |
| 1 | Combined open risk at SL ≤ $250: Σ existing `max(0, directional distance openPrice→SL) × value × volume` (0 at breakeven+) + the new trade's `risk_usd` (which already includes spread + round-trip commission). | `SECOND_COMBINED_RISK` |
| 2 | New setup reward:risk ≥ 2.0 after costs. `reward_per_lot = (target − ask) × value − spread_cost − commission` (BUY; mirrored for SELL); ratio = `reward_per_lot / per_lot_loss`. | `SECOND_RR_TOO_LOW` |
| 2 | Never averaging down: no existing BTC position on the **same side** with MetaAPI `profit < 0`. | `SECOND_AVERAGING_DOWN` |
| 3 | Combined open risk ≤ remaining daily-cap room, `room = 500 − max(0, −(closed + floating today))`. | `SECOND_DAILY_ROOM` |
| 3 | `equity − combined open risk > 90,750`. | `SECOND_EQUITY_BUFFER` |
| 4 | Projected margin level `equity / (account.margin + new_margin) × 100 > 200 %`. | `SECOND_MARGIN_LEVEL` / `SECOND_MARGIN_UNKNOWN` |
| 5 | Max 2 BTC positions total. | `MAX_POSITIONS` |

**Limitation:** "fresh setup" cannot be verified server-side. The decision carries
`fresh_setup_verified: false`; the advisor is responsible for that judgement.

**Margin estimate method** (condition 4), first available wins, else the second entry is
skipped with `SECOND_MARGIN_UNKNOWN`:
1. `AUTOEXEC_MARGIN_PER_LOT_USD × lots` (explicit override, from preflight observation).
2. `spec.initialMargin × lots` when `initialMargin > 0` and `marginCurrency` equals the
   account currency.
3. `lots × contractSize × fill_price / AUTOEXEC_SYMBOL_LEVERAGE`.
4. Only if `AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE=1`: `lots × contractSize × fill_price /
   account.leverage` (crypto leverage on FTMO usually differs from the account leverage,
   so this is opt-in).
Hedged-margin relief is ignored (projected margin is treated as additive — conservative).
The preflight prints the estimate alongside the account's live `margin`/`marginLevel` so
Trading Ops can calibrate `AUTOEXEC_SYMBOL_LEVERAGE` or `AUTOEXEC_MARGIN_PER_LOT_USD`.

After any live place attempt (success, broker rejection, or transport error with unknown
fill state) entries are blocked for `AUTOEXEC_POST_PLACE_COOLDOWN_SEC`
(`POST_PLACE_COOLDOWN`) and positions are re-read and logged (`post_place_sync`). This
is the lesson from `modules/entry_guard.py`: a place error is not proof nothing filled.

### 4. Tighten-only stops
`/tighten` modifies the open auto position (by magic/comment; `position_id` required if two
are open). New stop must be strictly tighter: long `new > current`, short `new < current`
(`SL_NOT_TIGHTER`); moves above entry that lock profit are tightening. A missing/zero stop
is `SL_REMOVED`. The TP is preserved as-is and always re-sent; a position without TP is
refused (`TP_MISSING_ON_POSITION`); TP changes are not supported
(`TP_CHANGE_NOT_SUPPORTED`). Tightening is allowed while halted or capped — it reduces risk.

### 5. Daily loss cap ($500, Prague day)
`closed` = Σ(profit + commission + swap) of today's deals whose magic (or comment) is the
auto-trader's; balance/credit deals are ignored. `floating` = Σ(profit + commission + swap)
of open auto positions. If `closed + floating ≤ −500` the entry is rejected
(`DAILY_CAP_HIT`) and the day is latched in `state.json`; later entries that day are
`DAILY_CAP_LATCHED` even if floating P&L recovers. "Today" is the Europe/Prague calendar
day (window computed with `zoneinfo`, DST-aware: 22:00Z in CEST, 23:00Z in CET).

### 6. Equity halt ($90,750, latched)
If `account.equity ≤ 90,750` the entry is rejected (`EQUITY_HALT`) and the file
`AUTOEXEC_HALT_FILE` is written. While that file exists every entry is
`EQUITY_HALT_LATCHED`, across restarts, whatever the equity is now.

**Re-enable (manual, after Odin/Trading Ops approval):**
```bash
rm /home/solveetcoagula/btc-advisor-autoexec/state/HALT
# or
python3 -m autoexec halt-clear --yes      # logs halt_cleared_manually with the previous record
```
If equity is still at or below the threshold the next entry latches again.

### 7. Logging
Everything is one JSON object per line in `AUTOEXEC_LOG_PATH` (and stdout under
`serve`): `request`, `decision` (request, code, reason, guard values, sizing, commission,
the order payload), `order_send`, `post_place_sync`, `equity_halt_latched`,
`daily_cap_latched`, `halt_cleared_manually`, `server_start`, `http`. Keys containing
`token`, `auth`, `secret`, `password`, `api_key` are redacted recursively, and the loaded
token value itself is scrubbed from every line as a second layer.

## Dry-run

With `AUTOEXEC_ORDERS_ENABLED=0` (default) or the kill switch on, `/setup` and
`/tighten` run every read and guard against live data and return
`DRY_RUN_WOULD_PLACE` / `DRY_RUN_WOULD_MODIFY` with the exact payload that would be
sent. `broker.trade()` is not called. A request can also force dry-run while armed with
`"dry_run": true` (HTTP) or `--dry-run` (CLI).

## Preflight (read-only)

```bash
cd /home/solveetcoagula/odin_ftmo/btc-advisor-autoexec     # or wherever Trading Ops checks it out
AUTOEXEC_TOKEN_SOURCE=/home/solveetcoagula/odin_ftmo/config_us100.json \
python3 scripts/preflight.py --stop-distance 500          # add --json for machine output
```
Prints login/equity/margin, the raw symbol spec and derived value per unit, live
bid/ask/spread, the commission resolution (which source will be used and the observed
deals estimate), lot math for the sample stop, the margin estimate for a hypothetical
second entry, and every guard state (halt latch, daily cap, position count, cooldown,
kill, orders flag). The broker object is wrapped so `trade()` cannot be reached.

## Tests

```bash
cd btc-advisor-autoexec
python3 -m pytest tests -q
```
138 tests with a fake MetaAPI broker; no network, no token file. Coverage per mechanic:
sizing incl. spread + commission and floor to step, skip when min lot > $250, non-market
rejected, missing SL/TP rejected, max-2 total, every second-position condition (accept
and reject paths, incl. margin unknown/level/override/spec), tighten-only accept and
widen/remove reject, daily cap incl. floating and the Prague reset across the 2026-10-25
DST end, equity halt latch across restart and manual re-enable (file delete and CLI),
dry-run sends nothing, kill switch, fail-closed reads, login mismatch, post-place
cooldown, commission source resolution, token redaction, HTTP and CLI surfaces.
Verified on Python 3.12 and 3.9 (the VM runtime).

## Trading Ops: install, arm, rollback (after Odin's OK — not performed by this PR)

**Install (orders stay disabled):**
1. Check out this directory on the VM, e.g. `/home/solveetcoagula/odin_ftmo/btc-advisor-autoexec`.
2. `mkdir -p /home/solveetcoagula/btc-advisor-autoexec/state`.
3. Run the preflight above; confirm login `541458001`, equity, spec values, commission
   source, and that `orders_enabled: False`.
4. Copy `deploy/btc-advisor-autoexec.service.example` to
   `/etc/systemd/system/btc-advisor-autoexec.service`, `systemctl daemon-reload`,
   `systemctl start btc-advisor-autoexec`. `curl 127.0.0.1:8787/health` must show
   `"orders_enabled": false, "armed": false`.
5. Exercise `/setup` and `/tighten` in dry-run and review `autoexec.jsonl`.

**Arm (only after Odin's explicit OK):**
```bash
sudo systemctl edit btc-advisor-autoexec       # creates a drop-in; do NOT edit the committed file
# [Service]
# Environment=AUTOEXEC_ORDERS_ENABLED=1
# Environment=AUTOEXEC_SYMBOL_LEVERAGE=<value confirmed from preflight>   # or AUTOEXEC_MARGIN_PER_LOT_USD
sudo systemctl restart btc-advisor-autoexec
curl -s 127.0.0.1:8787/health      # "armed": true
```

**Kill (instant, no restart):**
```bash
touch /home/solveetcoagula/btc-advisor-autoexec/state/KILL     # or: python3 -m autoexec kill
```

**Rollback:**
```bash
sudo rm -f /etc/systemd/system/btc-advisor-autoexec.service.d/override.conf   # removes the arm drop-in
sudo systemctl daemon-reload && sudo systemctl restart btc-advisor-autoexec     # back to dry-run
# or stop entirely:
sudo systemctl stop btc-advisor-autoexec && sudo systemctl disable btc-advisor-autoexec
```
Open positions are not touched by a rollback; manage them in the terminal or with
`/tighten` (which works in dry-run only as a check — a stop change needs the unit armed).

## Open questions for Odin

Each is left configurable with a safe default rather than guessed (mirrored in the PR body).

1. **Stop-distance reference.** Sizing measures the stop distance from the fill side of the
   live quote (ask for BUY, bid for SELL) and then adds the spread cost again, as the
   approved formula lists both. That double-counts the spread (conservative). Confirm, or
   specify measuring from mid.
2. **Deals-derived commission below the fallback.** In `auto`, an observed round-trip
   commission from closed BTCUSD deals is used even if it is lower than $27 (e.g. 0).
   Confirm, or pin `AUTOEXEC_COMMISSION_SOURCE=env`.
3. **Pending exit commission on existing positions** is not added to "open risk at SL"
   (second-position condition 1). Confirm.
4. **"Floating loss"** for the no-averaging-down rule = MetaAPI position `profit < 0`
   (swap/commission fields not included). Confirm.
5. **Margin estimate inputs.** MetaAPI exposes no per-symbol margin rate; until
   `AUTOEXEC_SYMBOL_LEVERAGE` or `AUTOEXEC_MARGIN_PER_LOT_USD` is set from preflight
   observation, every second entry is skipped (`SECOND_MARGIN_UNKNOWN`). Confirm the
   BTCUSD leverage/margin figure for this account.
6. **Griff BTC positions.** `griff_engine_btc.service` trades BTCUSD on this account
   (`GRIFF_*` comments). They count toward the 2-position total and must be at breakeven+
   for a second entry; they are not in the auto-trader's daily cap (by magic). Confirm.
7. **Post-place cooldown (60 s)** after any place attempt is an implementation safeguard
   from the `entry_guard` history, not in the approved list. Confirm or set to 0.
8. **Tightening while halted/capped** is allowed (risk-reducing). Confirm.
9. **TP changes** via `/tighten` are refused; only the stop moves. Confirm.
10. **Daily-cap latch** holds for the rest of the Prague day once hit, even if floating
    P&L recovers. Confirm.
11. **`request_id`** is logged but not de-duplicated beyond the cooldown. Confirm whether
    idempotent replay is needed.
12. **Magic number** default `20261010`; **token source** default
    `/home/solveetcoagula/odin_ftmo/config_us100.json` (`metaapi.token`). Confirm both
    (the token must have access to account `a60dfd98-…`).
