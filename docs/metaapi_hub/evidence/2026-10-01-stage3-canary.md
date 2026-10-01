# MetaAPI Hub Stage 3 — SAFE LIVE order canary (matt-berserker)

Copied from the operator report for the successful window. This file is the git copy of that evidence. It does not contain a MetaAPI token. Token presence was recorded as a length only (2589). This commit did not run the canary and did not change units on the VM.

**When:** 2026-10-01 ~12:38–12:41 ET (successful window)
**Branch/SHA:** `cursor/metaapi-hub-230c` @ `bcd48ff0b6900c24ce2bb861f9b7410740507cc4`
**Sandbox:** `/tmp/odin-ftmo-hub-shadow`
**Verdict:** **PASS**

## Hard rules compliance

| Rule | Result |
|------|--------|
| Live orders via hub (`--orders live` + `--enable-live-orders` + `ODIN_METAAPI_HUB_ORDERS=live`) | YES (Odin-approved canary) |
| Tiny volume + far-from-market BUY limits only (no market / near-touch) | YES (0.01 lots; BTC/US100 @ 10000; XAU @ 1000) |
| nordvpn / openvpn@asterdex / odin_daemon untouched | YES (all stayed active) |
| Three Griff engines always restarted hub-free | YES (EXIT trap + postflight) |
| No permanent `ODIN_METAAPI_HUB` on production units | YES (Environment=[] DropInPaths=[]) |
| Secrets not logged | YES (token presence/len only; len 2589) |
| Hub kill by recorded PID only (no `pkill -f`) | YES |
| London/Omni inactive for window | YES (all inactive) |
| Live tree not git-pulled | YES (sandbox only) |

## Per-symbol create / cancel

| Symbol | Mark (15m close) | Limit BUY | Vol | orderId | Create stringCode / numericCode | Cancel |
|--------|------------------|-----------|-----|---------|----------------------------------|--------|
| BTCUSD | 84231.67 | 10000.0 | 0.01 | 172310476 | TRADE_RETCODE_DONE / 10009 | CANCELED |
| US100.cash | 30363.28 | 10000.0 | 0.01 | 172310493 | TRADE_RETCODE_DONE / 10009 | CANCELED |
| XAUUSD | 4165.37 | 1000.0 | 0.01 | 172310505 | TRADE_RETCODE_DONE / 10009 | CANCELED |

Comments: `hub-canary-btc`, `hub-canary-us100`, `hub-canary-gold`.
Post-cancel broker list: **orders=[]**, **positions=[]** (no leftovers / no fills).

## Health snapshot (after probe)

```json
{
  "mode": "live",
  "orders_mode": "live",
  "orders_live": true,
  "connected": true,
  "synchronize_calls": 1,
  "broker_synchronize_calls": 1,
  "broker_order_calls": 3,
  "broker_mutation_calls": 6,
  "broker_candle_calls": 3
}
```

Notes:

- `synchronize_calls == 1` (single shared sync).
- Hub accounting: creates increment `broker_order_calls` (3); creates+cancels increment `broker_mutation_calls` (6). Matches 3×create + 3×cancel.

## Downtime

| Window | Engines down |
|--------|----------------|
| Abort attempt v1 (false `kill -0` cross-user; engines restored; leftover hub cleaned before v2) | ~96s |
| Successful canary v2 | **135 seconds** (stop ~16:38:42Z → restore ~16:40:53Z) |

## Engine restore

- Units: `griff_engine_btc`, `griff_engine_us100`, `griff_engine_gold` → **active**
- Environment / DropInPaths: empty (hub-free OLD path)
- Journals: MetaAPI synchronization / price stream active after restore
- Equity: **94061.91** SEARCHING (unchanged)
- Hub process / canary socket: gone

## Anomalies / lessons

1. **v1 abort:** `kill -0` from `reemanos8422` on `solveetcoagula` hub PID returns EPERM → false “PID gone”. Script fixed to use `ps -p` + `sudo kill` by recorded PID. Leftover hub briefly coexisted with restored engines; emergency cleanup stopped engines, killed hub PID, restored engines before v2.
2. Launch script ownership noise (`Permission denied` rewriting launch from prior run) did not block hub start (prior executable launch reused / new launch still ran).
3. Hub needed KILL after TERM (SDK write-loop hang on shutdown) — still PID-targeted only.

## Evidence locations (as reported)

- Box: `/workspace/metaapi-hub-stage3-safe-canary-evidence/` (`REPORT.md`, `probe.json`, `canary-run-v2.log`, `postflight-v2.txt`, hub log copy)
- VM: `/tmp/odin-stage3-canary-probe.json`, `/tmp/odin-stage3-canary-evidence.txt`, `/tmp/odin-stage3-canary-hub.log`, `/tmp/odin-stage3-canary.sh`

Those paths are where the operator stored the run. This repository copy is this file plus the summary in [TEST_EVIDENCE.md](../TEST_EVIDENCE.md). The sandbox `/tmp/odin-ftmo-hub-shadow` is not a durable production checkout.

## Probe JSON summary

Source: the uploaded `probe.json` for the same PASS window. `ok` is true, `verdict_hint` is `PASS`, `errors` is empty, `cleanup.clean` is true, `cleanup.orders` is `[]`, `cleanup.positions` is `[]`, `fills` is false.

| Field | Value |
| --- | --- |
| started_at | 2026-10-01T16:40:12.028484+00:00 |
| finished_at | 2026-10-01T16:40:42.015261+00:00 |
| account_id | `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` (same id already in `setup_us100_service.sh` and `setup_gold_service.sh`; not a token) |
| creates_ok / cancels_ok | 3 / 3 |
| equity | 94061.91 on each symbol |

Create `tradeStartTime` (UTC) and broker `tradeExecutionTime` as recorded, not reinterpreted:

| orderId | tradeStartTime | tradeExecutionTime |
| --- | --- | --- |
| 172310476 | 2026-10-01T16:40:28.370000+00:00 | 2026-10-01T19:40:28.876000+00:00 |
| 172310493 | 2026-10-01T16:40:35.009000+00:00 | 2026-10-01T19:40:35.513000+00:00 |
| 172310505 | 2026-10-01T16:40:40.363000+00:00 | 2026-10-01T19:40:40.872000+00:00 |

Each result: `local_synchronize_calls` 0, `candles` 5, `volume_used` 0.01, `errors` empty.

`health_before` (probe attached, sync not yet done): `connected` false, `synchronize_calls` 0, `sync_attempts` 0, `reconnects` 0, `broker_order_calls` 0, `broker_mutation_calls` 0, `clients` `["probe-health"]`, `client_count` 1, `max_rpc_depth` 1, `you_do_not_sync` true.

`health_after`:

| Field | Value |
| --- | --- |
| mode | live |
| orders_mode | live |
| orders_live | true |
| connected | true |
| synchronize_calls | 1 |
| broker_synchronize_calls | 1 |
| sync_attempts | 1 |
| reconnects | 0 |
| broker_order_calls | 3 |
| broker_mutation_calls | 6 |
| broker_candle_calls | 3 |
| candle_fetches | 3 |
| candle_timeouts | 0 |
| single_flight_joins | 0 |
| cache_hits | 0 |
| duplicate_suppressions | 0 |
| clients | probe-health only (`client_count` 1) |
| max_rpc_depth | 1 |
| you_do_not_sync | true |

The three Griff engines were not hub clients during this probe. They were stopped for the window and restored hub-free afterward. `broker_order_calls` 3 and `broker_mutation_calls` 6 are the canary creates and cancels, not leftover broker orders. Cleanup reported `orders=[]` and `positions=[]`.
