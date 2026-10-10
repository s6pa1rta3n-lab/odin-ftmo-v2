# btc-advisor-autoexec

Execution endpoint for FTMO Advisor setups on any symbol the FTMO broker lists
(crypto CFDs, indices, metals, FX); `symbol` defaults to BTCUSD. **Order placement is DISABLED by
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
- Multi-symbol 17:07 ET: ETHUSD and SOLUSD alongside BTCUSD on the same account; same
  per-trade guards per symbol from each symbol's own spec/quote/commission; the $500 daily
  cap, the $90,750 halt and the kill switch are account-wide.
- Any symbol 19:07 ET: any symbol the broker lists, validated live against MetaAPI's
  symbol list and a complete specification; a **margin cap on every entry** (projected
  margin level >= 200 %, lots shrink, else skip); **commission as a percentage of
  notional** (0.065 % per round trip = 0.0325 %/side default, crypto only; other classes need broker/deals data or an
  explicit value); position limit and breakeven rule **account-wide** (every open position,
  all symbols, manual and auto, incl. other engines); `/symbol` endpoint; preflight for a
  symbol list. See [Symbols](#symbols), [Margin cap](#margin-cap-every-entry) and
  [Commission models](#commission-models).

Target: FTMO login `541458001`, MetaAPI account `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf`,
any broker-listed symbol (default `BTCUSD`), London client host `https://mt-client-api-v1.london.agiliumtrade.ai`
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
| POST   | `/setup`   | `{"symbol":"<broker symbol>","side":"BUY|SELL","entry_type":"MARKET","stop":<px>,"target":<px>}` + optional `request_id`, `dry_run:true`. `symbol` defaults to `BTCUSD`; it must pass the env allow/deny lists (`SYMBOL_NOT_ALLOWED`), be in the broker's live list (`SYMBOL_NOT_LISTED`) and have a complete spec (`SPEC_UNAVAILABLE` / `SPEC_INCOMPLETE`). | entry decision |
| POST   | `/tighten` | `{"stop":<px>}` + optional `symbol` (default `BTCUSD`), `position_id` (auto position on any symbol), `request_id`, `dry_run:true` | tighten an auto position's stop |
| GET    | `/symbol`  | `?symbol=XAUUSD[,US100.cash][&stop_distance=25][&side=BUY]` | read-only per-symbol report (see below) |

If `AUTOEXEC_API_KEY` is set, every request must send `X-Autoexec-Key`.

Decision JSON (both routes) always carries: `ok`/`accepted`, `action`, `symbol`, `mode`
(`dry_run`|`live`), `sent`, `code`, `reason`, `guards` (equity, halt, book, daily P&L,
cooldown, …), and for entries `lots`, `risk_usd`, `per_lot_loss`, `spread`,
`spread_cost_per_lot`, `commission_per_lot_roundtrip`, `commission_source`,
`stop_distance`, `reward_risk`, `sizing`, `commission`, `order` (the payload that was
or would be sent), `broker_response` when something was sent, and `second_position`
when any position was already open on the account.

```bash
curl -s -XPOST 127.0.0.1:8787/setup -d '{"side":"BUY","entry_type":"MARKET","stop":84500,"target":86500}'            # BTCUSD
curl -s -XPOST 127.0.0.1:8787/setup -d '{"symbol":"ETHUSD","side":"BUY","entry_type":"MARKET","stop":2900,"target":3300}'
curl -s -XPOST 127.0.0.1:8787/tighten -d '{"stop":84800}'                      # BTCUSD auto position
curl -s -XPOST 127.0.0.1:8787/tighten -d '{"symbol":"ETHUSD","stop":2960}'
curl -s 127.0.0.1:8787/status
```

### CLI

```bash
cd /path/to/btc-advisor-autoexec
python3 -m autoexec serve
python3 -m autoexec setup [--symbol ETHUSD] --side BUY --entry-type MARKET --stop 84500 --target 86500 [--dry-run]
python3 -m autoexec tighten [--symbol ETHUSD] --stop 84800 [--position-id ID] [--dry-run]
python3 -m autoexec status
python3 -m autoexec symbol XAUUSD US100.cash [--stop-distance 25] [--side BUY]
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
| `AUTOEXEC_SYMBOL` | `BTCUSD` | Default symbol when a request has no `symbol`. |
| `AUTOEXEC_SYMBOLS` | *(empty)* | Optional **allowlist**. Empty = every symbol the broker lists. |
| `AUTOEXEC_SYMBOLS_DENY` | *(empty)* | Optional denylist. |
| `AUTOEXEC_STATUS_SYMBOLS` | *(empty)* | Extra symbols to report in `/status` (default symbol, allowlist and open-position symbols are always included). |
| `AUTOEXEC_SECOND_POSITION_SCOPE` | `all` | `all` = every open position on the account counts (Odin 19:07 ET); `allowed` = allowlist symbols only. |
| `AUTOEXEC_SAMPLE_STOP_PCT` | `1.0` | Default sample stop distance for `/symbol` / preflight, as % of price. |
| `AUTOEXEC_CLIENT_HOST` | `https://mt-client-api-v1.london.agiliumtrade.ai` | MetaAPI client REST host. |
| `AUTOEXEC_ORDERS_ENABLED` | `0` | **Arming flag.** `1` allows `/trade` calls. |
| `AUTOEXEC_KILL` | `0` | Kill switch (env). |
| `AUTOEXEC_KILL_FILE` | `<state_dir>/KILL` | Kill switch (file). Presence blocks every entry and modify, no restart needed. |
| `AUTOEXEC_MAX_RISK_USD` | `250` | Guard 2. |
| `AUTOEXEC_COMMISSION_PCT_PER_SIDE` | `0.0325` | Percentage-of-notional commission per side (round trip = 2 × rate × contractSize × fill price = 0.065 % per round trip). Default model for **crypto** only. Rate decided by Odin 2026-10-10 19:30 ET from Trading Ops' measured $54.31/lot round trip on ~83.5k notional. |
| `AUTOEXEC_COMMISSION_PCT_PER_SIDE_<SYMBOL|CLASS>` | unset | Per-symbol or per-class rate (`_CRYPTO`, `_FOREX`, `_INDEX`, `_METALS`). |
| `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_<SYMBOL>` | unset | Flat per-lot round trip for a symbol (selects the `flat` model). |
| `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP` | `27` | Legacy flat BTCUSD figure (Odin 05:47 ET); used only when BTCUSD resolves to the `flat` model (no asset class from the broker, or `AUTOEXEC_COMMISSION_MODEL_BTCUSD=flat`). |
| `AUTOEXEC_COMMISSION_MODEL_<SYMBOL|CLASS>` | per class, see "Confirmed per-asset commission defaults" | `pct` or `flat` per symbol or class. Unknown groups have **no default**: broker/deals data or an explicit value, else `COMMISSION_UNAVAILABLE`. |
| `AUTOEXEC_ASSET_CLASS_<SYMBOL>` | unset | Override the class derived from the broker's group/name (`crypto|forex|metals|index|oil|equity|energy|dollar_index|agri`). |
| `AUTOEXEC_COMMISSION_SOURCE` | `auto` | `auto` (spec → deals → env), or pin `spec` / `deals` / `env`. Pinned sources with no data fail closed. |
| `AUTOEXEC_COMMISSION_LOOKBACK_DAYS` | `30` | Window for the deals-derived commission. |
| `AUTOEXEC_MAX_POSITIONS_TOTAL` | `2` | Guard 3 (values above 2 are refused). |
| `AUTOEXEC_SECOND_POSITION_MIN_RR` | `2.0` | Guard 3 condition 2. |
| `AUTOEXEC_MIN_MARGIN_LEVEL_PCT` | `200` | Guard 3 condition 4. |
| `AUTOEXEC_MARGIN_CALC_BROKER` | `1` | Use MetaAPI `calculate-margin` (broker-reported) as the first margin source. |
| `AUTOEXEC_MARGIN_PER_LOT_USD[_<SYMBOL>]` | unset | Margin calibration override per 1.0 lot (un-suffixed = BTCUSD). |
| `AUTOEXEC_SYMBOL_LEVERAGE[_<SYMBOL>]` | unset | Margin calibration: notional / leverage (un-suffixed = BTCUSD). |
| `AUTOEXEC_MIN_MARGIN_LEVEL_PCT` | `200` | Margin cap on every entry and second-position condition 4. |
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

## Symbols

Authorization: Odin 17:07 ET (ETH/SOL) and 19:07 ET (any broker-listed symbol).

- `/setup`, `/tighten`, `/symbol` and the CLI take `symbol`; absent → `BTCUSD`.
- Validation, in order: env allow/deny lists (`SYMBOL_NOT_ALLOWED`); the broker's live symbol
  list from MetaAPI (`SYMBOL_NOT_LISTED`; canonical case comes from the list; if the list
  cannot be read the spec read decides and the failure is logged `symbol_list_unavailable`);
  the specification must be readable (`SPEC_UNAVAILABLE`) and expose `contractSize`,
  `tickSize`, `minVolume` and `volumeStep` (`SPEC_INCOMPLETE`, listing the missing fields);
  a tick value must be derivable (`TICK_VALUE_UNAVAILABLE`, see Guard 2). No spec value is
  ever guessed.
- Every per-trade guard is evaluated from **that symbol's own** spec and live quote: $250
  sizing incl. that symbol's spread and round-trip commission, lots floored to its step, skip
  if its minimum lot exceeds $250, MARKET only, SL + TP required, stops only tighten.
- Account-wide: the $500 daily cap (closed + floating + commissions on every auto-magic trade
  on any symbol), the $90,750 equity-halt latch, the kill switch, the post-place cooldown,
  the position limit and the margin cap.
- Caches and retry from the reliability fix apply per symbol (symbol list and spec cached per
  the spec TTL, quotes always fresh, one shared commission-lookback read, `/symbol` views
  cached per the status TTL).
- `symbol` is logged on every decision line, including rejections.

## Margin cap (every entry)

Authorization: Odin 19:07 ET #3. After any entry, first or second, the projected margin level
`equity / (account.margin + margin_per_lot × lots) × 100` must be **>= 200 %**
(`AUTOEXEC_MIN_MARGIN_LEVEL_PCT`). Lots are shrunk, floored to the volume step, until it
holds (`margin.cap.capped: true`, the reason is appended to `sizing.reason`); if even the
minimum lot breaks it the entry is skipped (`MARGIN_CAP_SKIP`). If the margin per lot cannot
be computed the entry is skipped (`MARGIN_UNKNOWN`). The estimate and its method are in
`margin` on every decision.

Margin per lot, first available wins (`margin.per_lot.method`):
1. `metaapi.calculate-margin` — broker-reported margin for the sized volume via MetaAPI
   `POST .../calculate-margin` (read-only), divided by that volume.
2. `AUTOEXEC_MARGIN_PER_LOT_USD[_<SYMBOL>]` override.
3. `spec.initialMargin` when > 0 and in the account currency.
4. notional / `AUTOEXEC_SYMBOL_LEVERAGE[_<SYMBOL>]`.
5. notional / `account.leverage`, opt-in only.
Hedged-margin relief is ignored (conservative).

## Commission models

Authorization: Odin 19:07 ET #4. Per symbol, `auto` resolves: a commission field on the spec
(broker) → closed round trips of that symbol in the lookback (deals-derived) → the configured
model. Models:
- `pct`: round trip = 2 × `AUTOEXEC_COMMISSION_PCT_PER_SIDE` (0.0325 %, i.e. 0.065 % per round trip) × contractSize × fill
  price, in account currency (a symbol quoted in another currency is `COMMISSION_UNAVAILABLE`
  under `pct`; no FX conversion is attempted). **Default for crypto only** (Trading Ops
  measured FTMO crypto round trips at this rate).
- `flat`: `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_<SYMBOL>` per 1.0 lot.
- Groups without a confirmed default (see the table below) have no model: without
  broker/deals data or an explicit per-symbol value (or `AUTOEXEC_COMMISSION_MODEL_<CLASS>` +
  rate) the entry is skipped with `COMMISSION_UNAVAILABLE` naming the variables to set.
The decision reports `commission.asset_class`, `commission.model`, `commission.source`,
`pct_per_side`, `notional_per_lot`.

### Asset-class map (broker group + symbol name)

Case-insensitive on the first segment of the broker's spec `path` (the MT5 group), with
symbol-name exceptions inside shared groups; slash names (`XAU/USD`) are normalised to
`XAUUSD`. `AUTOEXEC_ASSET_CLASS_<SYMBOL>` overrides everything.

| Class | Matches |
|---|---|
| `crypto` | groups containing `Crypto` — `Crypto`, `Crypto CFD`, `Crypto II CFD` (e.g. UNIUSD) |
| `forex` | `Forex`, `Exotics`, `FX`, `Currencies` |
| `metals` | `Metals CFD`, `Metals`, `Gold`, `Silver` |
| `index` | `Cash CFD` (e.g. US100.cash, US30.cash), `Indices` |
| `oil` | by name: `USOIL.cash`, `UKOIL.cash` (inside `Cash CFD`) |
| `energy` | by name: `NATGAS.cash`, `HEATOIL.c` |
| `dollar_index` | by name: `DXY.cash` |
| `equity` | `Equities CFD`, `Stocks`, `Shares` |
| `agri` | `Agricultural`, or any other `*.c` name (COCOA.c, CORN.c, SUGAR.c …) |
| *(none)* | anything else → no default commission |

### Confirmed per-asset commission defaults

Sources: FTMO official trading updates (Jul–Sep 2025) and FTMO's official symbols data
(`https://ftmo.com/wp-json/ftmo/symbols`, behind `ftmo.com/en/symbols`, last modified
2026-10-08 — its figures are round trip, exactly 2× the per-side rates), reconciled with this
account's broker deals measured by Trading Ops on 2026-10-10 (BTC $27.17/side over 306 round
trips; FX $2.508/side; US100.cash $0.00 over 2 round trips; no metals deals yet). Decision
delegated to the implementer by Odin (19:30 ET). Broker/deals-derived values still take
precedence when available.

| Class | Default | Published / measured |
|---|---|---|
| `crypto` | `pct` **0.0325 %/side** (`AUTOEXEC_COMMISSION_PCT_PER_SIDE`) | page 0.065 % round trip; measured $27.17/side |
| `forex` | `flat` **$5.02** round trip | page $5 round trip ($2.50/side); measured $2.508/side |
| `metals` | `pct` **0.0007 %/side** | page 0.0014 % round trip; no deals yet — no padded flat guess |
| `index` | `flat` **$0** | page zero; measured $0.00 on US100.cash |
| `oil` | `flat` **$0** | page zero (USOIL.cash, UKOIL.cash) |
| `equity` | `pct` **0.002 %/side** | page 0.004 % round trip |
| `energy` | `pct` **0.0007 %/side** | page 0.0014 % round trip (NATGAS.cash, HEATOIL.c) |
| `dollar_index` | `pct` **0.0007 %/side** | page 0.0014 % round trip (DXY.cash) |
| `agri` | `flat` **$0** | page zero (COCOA.c, CORN.c, SUGAR.c …) |
| other | none | skip with `COMMISSION_UNAVAILABLE` unless env set |

Per-class overrides: `AUTOEXEC_COMMISSION_MODEL_<CLASS>`, `AUTOEXEC_COMMISSION_PCT_PER_SIDE_<CLASS>`,
`AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_<CLASS>` (class names as in the table, e.g. `_DOLLAR_INDEX`).

### Env-variable names for symbols with dots

Per-symbol variables accept the exact broker name or an upper-cased form with non-alphanumerics
replaced by `_`: `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_US100.cash`,
`..._US100_CASH` and `..._us100.cash` all address `US100.cash` (systemd `Environment=`
accepts dots; a POSIX shell does not, so use the underscore form there). A flat commission of
**`0` is a valid, set value** (e.g. indices), not `COMMISSION_UNAVAILABLE`; only an empty
value means unset.

**Rate decision (Odin, 2026-10-10 19:30 ET, delegated after Trading Ops' measured data):**
the crypto `pct` commission is **0.065 % of notional per round trip = 0.0325 % per side**.
Trading Ops measured **$54.31 per lot round trip on ~83.5k BTC notional**
(54.31 / 83,500 = 0.065 %).

**BTCUSD numeric difference from the flat $27 (documented per Odin's request).** At 85,020
the `pct` model gives 2 × 0.0325 % × 85,020 = **$55.26** round trip per lot versus the legacy
flat **$27**. On the reference setup (520-point stop, 20-point spread): flat $27 → per-lot
loss 567 → 0.44 lots; `pct` → per-lot loss 595.26 → 250 / 595.26 = 0.41998 → **0.41 lots**
after the floor to the 0.01 step (about 0.42; exactly 0.42 with the measured $54.31 at
~83.5k notional). When the broker reports no asset class for BTCUSD the legacy flat $27 still
applies (identical to #85).

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
value_per_unit = tick value / tickSize
   tick value   = quote.lossTickValue (current-price quote; conservative loss side)
                  else a spec tick value (lossTickValue | profitTickValue | tickValue)
                  else contractSize x tickSize ONLY if the symbol's profit currency == account currency
                  else fail closed (TICK_VALUE_UNAVAILABLE)
stop_distance  = ask - stop  (BUY, fills at ask)   |   stop - bid  (SELL, fills at bid)
per_lot_loss   = stop_distance * value_per_unit + (ask - bid) * value_per_unit + commission_roundtrip
lots           = floor_to_step(250 / per_lot_loss, volumeStep), capped at maxVolume
risk_usd       = lots * per_lot_loss
```
If `lots < minVolume` the entry is skipped (`SKIP_MIN_VOLUME`). Spread, commission (and
its source), per-lot loss and `value_source` are logged on every decision, including
rejected ones.

**Tick value source (Trading Ops preflight at b54c805, 2026-10-10):** on this account
MetaAPI returns `tickValue`/`lossTickValue` as **null in the symbol specification**; tick
values are only present in the current-price quote (`lossTickValue` / `profitTickValue`).
Sizing therefore takes `quote.lossTickValue` first, then a spec tick value, then
`contractSize × tickSize` only for symbols quoted in the account currency (the #84–#86
behaviour for USD-quoted symbols); otherwise it fails closed. Spec completeness no longer
requires a tick value in the spec (`contractSize`, `tickSize`, `minVolume`, `volumeStep`
remain required).

Commission source (`commission_source` in every decision):
1. `spec` – a commission field on the MetaAPI symbol specification, if the broker exposes one
   (MetaAPI's documented spec has none, so this is normally absent).
2. `deals` – observed from the account's own closed `BTCUSD` round trips in the last
   `AUTOEXEC_COMMISSION_LOOKBACK_DAYS`: Σ|commission| over IN+OUT deals of positions with
   both legs in the window ÷ Σ IN volume. Open positions (one leg) are ignored.
3. `env` – `AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP` (default 27).

### 3. Position count and the second-position rule
**Every open position on the account counts** — all symbols, manual (magic 0), auto and
other engines (e.g. the gold engine's XAUUSD) — with `AUTOEXEC_SECOND_POSITION_SCOPE=all`
(default since 19:07 ET; `allowed` restricts to the allowlist).

- 0 open: normal single-entry guards.
- ≥ `AUTOEXEC_MAX_POSITIONS_TOTAL` (2) open: `MAX_POSITIONS`.
- 1 open: a second entry is allowed only if **all** of the following hold
  (first failure wins, all values logged under `second_position`):

| # | Condition | Reject code |
|---|---|---|
| 1 | Every open position on the account has SL at breakeven or better (long: `SL >= openPrice`; short: `SL <= openPrice`; missing/zero SL fails). | `SECOND_SL_NOT_BREAKEVEN` |
| 1 | Combined open risk at SL ≤ $250: Σ existing `max(0, directional distance openPrice→SL) × that symbol's value per unit × volume` (0 at breakeven+) + the new trade's `risk_usd` (which already includes spread + round-trip commission). | `SECOND_COMBINED_RISK` |
| 2 | New setup reward:risk ≥ 2.0 after costs. `reward_per_lot = (target − ask) × value − spread_cost − commission` (BUY; mirrored for SELL); ratio = `reward_per_lot / per_lot_loss`. | `SECOND_RR_TOO_LOW` |
| 2 | Never averaging down: no existing position on the **same symbol and same side** with MetaAPI `profit < 0`. | `SECOND_AVERAGING_DOWN` |
| 3 | Combined open risk ≤ remaining daily-cap room, `room = 500 − max(0, −(closed + floating today))`. | `SECOND_DAILY_ROOM` |
| 3 | `equity − combined open risk > 90,750`. | `SECOND_EQUITY_BUFFER` |
| 4 | Projected margin level `equity / (account.margin + new_margin) × 100 >= 200 %` (already enforced by the margin cap; re-verified here). | `SECOND_MARGIN_LEVEL` / `SECOND_MARGIN_UNKNOWN` |
| 5 | Max 2 positions total on the account. | `MAX_POSITIONS` |

**Limitation:** "fresh setup" cannot be verified server-side. The decision carries
`fresh_setup_verified: false`; the advisor is responsible for that judgement.

**Margin estimate method** (condition 4): see [Margin cap](#margin-cap-every-entry); the
same per-lot estimate is used.

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

### 5. Daily loss cap ($500, Prague day, shared across symbols)
`closed` = Σ(profit + commission + swap) of today's deals on any symbol whose magic (or
comment) is the auto-trader's; balance/credit deals are ignored. `floating` =
Σ(profit + commission + swap) of open auto positions on any symbol. If `closed + floating ≤ −500` the entry is rejected
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

## Reliability: caches and 429/5xx retry

Assigned by Trading Ops on 2026-10-10 09:57 ET after a MetaAPI 429 at 09:51 ET. This
layer sits under the guards; guards, sizing, decisions and the `state.json` format are
unchanged, and the deploy is a restart only.

| Variable | Default | Meaning |
|---|---|---|
| `AUTOEXEC_SPEC_CACHE_SEC` | `1800` | Symbol specification cache (in memory). `0` disables. |
| `AUTOEXEC_COMMISSION_CACHE_SEC` | `1800` | Deals-derived commission lookback (30-day `history-deals`) cache. `0` disables. |
| `AUTOEXEC_STATUS_CACHE_SEC` | `15` | Snapshot cache used **only** by `GET /status` / `status`. `/setup` and `/tighten` always read fresh. Failures are cached for the same TTL so a poller cannot amplify rate limiting. `0` disables. |
| `AUTOEXEC_RETRY_ATTEMPTS` | `3` | Tries for reads and for `POSITION_MODIFY`. `1` = no retry. |
| `AUTOEXEC_RETRY_BUDGET_SEC` | `10` | Wall-clock budget for all tries of one call. |
| `AUTOEXEC_RETRY_BASE_SEC` / `AUTOEXEC_RETRY_MAX_SEC` | `1` / `4` | Exponential backoff when no `Retry-After` is present. |

Retry rules (`autoexec/retry.py`):
- Retried: HTTP 429 and 5xx on every read (`account-information`, `positions`,
  `current-price`, `specification`, `history-deals`) and on the `POSITION_MODIFY`
  behind `/tighten` (idempotent: the same SL/TP is re-sent).
- `Retry-After` (seconds or HTTP-date) is honoured when present; otherwise backoff
  `1s, 2s, 4s…`. A delay that would overrun the budget ends the loop and the call fails.
- **Never retried: new-order placement** (`ORDER_TYPE_BUY/SELL`). A 429/5xx on `/trade`
  does not prove the order was never accepted, so a retry could double-fill. Entry
  placement keeps exactly one attempt plus the existing ambiguous-place handling and
  `POST_PLACE_COOLDOWN`.
- Other errors (4xx, transport) are not retried.

Log events: `broker_rate_limited` (every 429, with `retry_after_sec`), `broker_retry`
(attempt, delay, source), `broker_retry_succeeded`, `broker_retry_exhausted`
(`outcome: failed`), `status_read_failed` (`alert: true`), and `tighten_failed`
(`alert: true, level: ALERT`) for **every** `/tighten` that does not go through —
read failure after retries, modify error after retries, broker rejection, or a guard
rejection. The decision JSON of a failed tighten also carries `alert: true` and a clear
`code` (`READ_FAILED`, `MODIFY_ERROR`, `MODIFY_REJECTED`, `SL_NOT_TIGHTER`, …).

`/status` responses include `snapshot: {cached, age_sec, ttl_sec, cache_hits}`. Local
inputs (HALT file, KILL file, cooldown, daily-cap latch) are recomputed on every call
even when the broker snapshot is cached. Live calls per `/status`: 6 on the first call,
then at most 4 per `AUTOEXEC_STATUS_CACHE_SEC` window while the spec/lookback caches
are warm.

## Dry-run

With `AUTOEXEC_ORDERS_ENABLED=0` (default) or the kill switch on, `/setup` and
`/tighten` run every read and guard against live data and return
`DRY_RUN_WOULD_PLACE` / `DRY_RUN_WOULD_MODIFY` with the exact payload that would be
sent. `broker.trade()` is not called. A request can also force dry-run while armed with
`"dry_run": true` (HTTP) or `--dry-run` (CLI).

## /symbol and the preflight (read-only)

`GET /symbol?symbol=XAUUSD&stop_distance=25` (or `python3 -m autoexec symbol XAUUSD`) returns,
per symbol: `broker_symbol`, `description`, `path`, `currencies`, `spec` and `spec_missing`,
`quote` (bid/ask/spread in price and `spread_cost_per_lot_usd`), `asset_class` and the model it
selects, `commission` (model/source/value per lot round trip, rate, notional),
`margin` (per lot and method), `sample` (stop distance, sizing, margin cap, resulting lots and
risk) and `ok` / `reason` (`pass`, or the skip code with its reason). Several symbols:
`symbol=A,B,C`. Cached per `AUTOEXEC_STATUS_CACHE_SEC`. `/status` carries the same view for
the active symbols under `guards.per_symbol`.

```bash
cd /home/solveetcoagula/odin_ftmo/btc-advisor-autoexec     # or wherever Trading Ops checks it out
AUTOEXEC_TOKEN_SOURCE=/home/solveetcoagula/odin_ftmo/config_us100.json \
python3 scripts/preflight.py --symbols UNIUSD,US100.cash,XAUUSD --stop-pct 1   # or --stop-distance 25
```
Prints the account-wide guard states and, per symbol, the `/symbol` view with **PASS/FAIL
and the reason**; exit code 0 when all pass, 2 otherwise; `--json` for machine output.
Prints login/equity/margin and the account-wide guard states (halt latch, shared daily
cap, position count by symbol, cooldown, kill, orders flag), then **for each allowed
symbol**: the broker's symbol name / description / path, the raw spec and derived value
per unit, live bid/ask/spread, the commission resolution (source and value, or the exact
env variable to set), lot math for the sample stop and the margin estimate for a
hypothetical second entry. The broker object is wrapped so `trade()` cannot be reached.

## Tests

```bash
cd btc-advisor-autoexec
python3 -m pytest tests -q
```
289 tests with a fake MetaAPI broker; no network, no token file. Coverage per mechanic:
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
13. **Per-asset-class confirmation (Trading Ops, before arming a class):**
    commission defaults are confirmed per class (see the table); confirm the broker's group
    `path` strings match the map (the preflight prints `asset_class.source`), and set a
    per-symbol value for anything that lands in "other";
    margin — confirm MetaAPI `calculate-margin` works on this account (the preflight prints the
    method), else set `AUTOEXEC_SYMBOL_LEVERAGE_<SYMBOL>` / `AUTOEXEC_MARGIN_PER_LOT_USD_<SYMBOL>`.
14. **Scope** is account-wide by default (19:07 ET); `AUTOEXEC_SECOND_POSITION_SCOPE=allowed`
    is the opt-out.
15. **Order comment** stays `BTC_ADVISOR_AUTO` on every symbol (the magic is the identity).
    Confirm or set `AUTOEXEC_COMMENT`.
