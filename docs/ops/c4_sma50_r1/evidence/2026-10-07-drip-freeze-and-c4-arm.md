# 2026-10-07 — Live catalogue drip freeze + Candidate 4 (C4_SMA50_R1) armed — FINAL

Copied from the Trading Ops FINAL status (~8:33 AM ET) and the attached deploy brief, pre-flight checklist, and live unit snapshot. This file records what Trading Ops already did on the VM. **It does not change the VM.** Nothing in this pull request installs, enables, restarts, or edits any service, and nothing here changes trading code behaviour.

| Field | Value |
|---|---|
| Host | matt-berserker (GCP `us-central1-a`) |
| Operator | Trading Ops (Grok Bot executor) |
| Odin approval | ~8:05 AM ET — freeze live catalogue drip **and** set up Candidate 4; "test and see" |
| Addendum | Watch a min-size live fill + SL + TP before the nightly arm |
| Live work completed | ~8:33 AM ET |
| This record | Docs-only PR, per Odin via Trading Ops ~8:46 AM ET |
| Research status | **CONDITIONAL** (fit gate failed); Odin accepted test-and-see |

Source files (verbatim copies, no tokens): [`../source/C4-OPS-STATUS.md`](../source/C4-OPS-STATUS.md), [`../source/C4-IMPLEMENTATION-CHECKLIST.md`](../source/C4-IMPLEMENTATION-CHECKLIST.md), [`../source/DEPLOY-TODAY-C4.md`](../source/DEPLOY-TODAY-C4.md), [`../unit/c4-sma50-r1.service`](../unit/c4-sma50-r1.service).

---

## 1) Live catalogue drip — FROZEN (proven)

The freeze means **no new catalogue market buys**. It is a reversible env flag, not a service deletion, so existing-ticket management keeps running.

| Item | Value |
|---|---|
| Service | `catalogue-btc-15m.service` — still **active** |
| Script | `/home/solveetcoagula/ftmo-catalogue/btc_15m_buy.py` |
| Mechanism | `FREEZE_NEW_BUYS=1` in the `catalogue-btc-15m.service` `Environment` + a gate in `btc_15m_buy.py` |
| Freeze installed | **8:07:44 AM ET** (start event logs `"freezeNewBuys":true`) |
| Slot proof | **8:30:04 AM ET** — `skip_freeze_new_buys` for slot `2026-10-07T08:30:00-04:00` |
| New buys | **blocked** — no `CATALOGUE_BTC_15M` buy at the 8:30 slot |
| Backup of script | `/home/solveetcoagula/ftmo-catalogue/btc_15m_buy.py.bak.freeze-20261007-0806et` |
| 22% hourly oldest-loser cut | **KEPT** (runs on :00 when margin ≥ 22%) |
| TP sweep / TP recovery | **KEPT** |
| Open catalogue buys | **not mass-closed** (left open; TP management continues) |
| Sheet updater | `btc-sheet-updater.service` **active**, unchanged |
| Account | MetaAPI `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` |

Journal excerpt (from the ops status; fields elided by the operator shown as `...`):

```
{"event":"start",...,"freezeNewBuys":true,"loggedAt":"2026-10-07T08:07:44..."}
{"event":"skip_freeze_new_buys","slot":"2026-10-07T08:30:00-04:00","freezeNewBuys":true,"marginPercent":9.42,"equity":91749.61,"loggedAt":"2026-10-07T08:30:04.840272-04:00"}
```

Checklist section A verification items, as reported:

1. Service still healthy — **yes** (active).
2. Next :00/:30 slot did not place a new `CATALOGUE_BTC_15M` buy — **yes** (8:30 slot skipped).
3. Open-position policy explicit — keep TP modify/recovery; **no mass close**.
4. Margin ≥ 22% hourly cut while frozen — **still runs**.
5. Sheet updater — **still writes** (unchanged).
6. Journalctl proof of skipped slot — **yes** (excerpt above).

The drip was **not** rewritten into C4 in place. C4 is a separate book (section 2).

---

## 2) Candidate 4 — NEW stopped book — ARMED

C4 is a new, separate book, not an edit of `btc_15m_buy.py` or `catalogue-btc-15m.service`.

| Item | Value |
|---|---|
| Path | `/home/solveetcoagula/ftmo-c4/` |
| Engine | `c4_sma50_r1.py` |
| Service | `c4-sma50-r1.service` — **enabled, active** |
| Order comment | `C4_SMA50_R1` |
| Account | MetaAPI `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` — **same account as the drip, intentional**; order comments segregate the books (`C4_SMA50_R1` vs `CATALOGUE_BTC_15M`) |
| Symbol | BTCUSD |
| Volume | 0.01 (full stop ≈ $412.91 ≈ $413 risk) |
| SL / TP | entry ± **412.91**, both hard and both required (R = 1); **emergency close if SL cannot be set** |
| Regime | prior **UTC daily close** vs **SMA50**, prior closed UTC day only (no look-ahead) |
| Regime feed | FTMO MetaAPI market data, **1h candles aggregated to UTC daily close** (same price source as traded); logged as `feed` |
| Entry clock | 00:00 UTC only; max **1** open position; no pyramid; no drip logic |
| First entry window | **2026-10-08 00:00 UTC = tonight 8:00 PM ET** |
| Kill switch | `touch /home/solveetcoagula/ftmo-c4/KILL`, or `C4_KILL=1` + restart, or `systemctl stop c4-sma50-r1` |
| Disarm | `C4_ARMED=0` in the unit + restart, or `touch /home/solveetcoagula/ftmo-c4/DISARM` |
| State file | `c4_state.json` (day-risk closed-PnL tracking; see deviation 4) |

Start log (from the ops status):

```
{"event":"start",...,"armed":true,"kill":false,...,"loggedAt":"2026-10-07T08:33:50..."}
{"event":"wait_slot","slot":"2026-10-08T00:00:00+00:00",...}
```

### Unit file snapshot

[`../unit/c4-sma50-r1.service`](../unit/c4-sma50-r1.service) is the verbatim snapshot taken from the live book path. It is kept here **for the record only** — do not install it from this repository.

Observation for the reviewer: the snapshot carries `Environment=C4_ARMED=0`, while the 8:33:50 AM ET start log reports `"armed":true` and the status header says ARMED. The attached sources do not state how the armed state was applied relative to the snapshot (e.g. unit edited after the snapshot, or an override). This record does not guess; confirm with Trading Ops if the exact arming mechanism matters.

---

## 3) Pre-flight (blocking list C.1–C.12) — 12/12 PASS

| # | Check | Result |
|---|---|---|
| 1 | MetaAPI London host reachable; account id correct; token not stale | **PASS** — FTMO account, equity ~91,750 |
| 2 | BTCUSD tradeable now (outside the daily break) | **PASS** — `SYMBOL_TRADE_MODE_FULL` |
| 3 | SMA50 from the same price source as traded; prior close only | **PASS** — 2026-10-06 UTC close **85506.23** > SMA50 **79893.16** → **long** |
| 4 | Market + SL + TP atomic, or modify-with-retry; never TP-only without SL | **PASS** — atomic path + modify-with-retry; emergency close if no SL |
| 5 | 412.91 survives broker digits (2dp) both sides | **PASS** |
| 6 | Short path tested (sell + SL above + TP below) | **PASS** — dry-run logged |
| 7 | Max-1 enforced; second signal while open is a hard skip | **PASS** |
| 8 | Drip freeze still holds while C4 arms | **PASS** — `FREEZE_NEW_BUYS=1` held |
| 9 | Kill switch documented and tested (< 60 s) | **PASS** — KILL file |
| 10 | Dry-run full lifecycle, or first live ticket at minimum volume with Ops watching fill + SL + TP | **PASS** — dry-run SL/TP **and** live min-size ticket (section 4) |
| 11 | Logging: entry, regime, SMA50, SL, TP, ticket, comment; alert on reject / partial / timeout / 504 | **PASS** — structured JSON logs; `alert=True` on reject / timeout / 504 |
| 12 | No collision with Asterdex / Griff (paused) comments, magic, ids | **PASS** — no Griff / Asterdex / drip comment collision |

---

## 4) Live minimum-size test — verified, then closed

| Field | Value |
|---|---|
| Ticket | **173729950** |
| Side | long |
| Open | 83524.2 |
| SL | 83112.08 |
| TP | 83937.9 |
| Volume | 0.01 |
| Result | **PASS** (`sl_ok` + `tp_ok`) — fill, SL and TP verified on the broker, then **closed** after verification |
| Remaining C4 positions | **none** |

Arithmetic note for the reviewer: the reported SL and TP are exactly symmetric at ±412.91 around **83524.99** (83524.99 − 412.91 = 83112.08; 83524.99 + 412.91 = 83937.90), while the reported open is 83524.2, i.e. 0.79 below that reference. The attached sources do not state which price the SL/TP were computed from; they report the ticket as PASS (`sl_ok` + `tp_ok`) on both sides. Recorded as-is.

---

## 5) Armed for

**ARMED for 2026-10-08 00:00 UTC (tonight, 8:00 PM ET).**

Expect **long** unless the Oct 7 UTC daily close flips vs SMA50 before entry. Morning research context: spot ~83.6k vs SMA50 ~80.3k (deploy brief) and pre-flight 3 confirmed 2026-10-06 close 85506.23 > SMA50 79893.16.

---

## 6) Deviations from the research rules

From the FINAL ops status, section 4:

1. **Same MetaAPI account as the drip** — intentional; comments segregate the books (`C4_SMA50_R1` vs `CATALOGUE_BTC_15M`).
2. **SMA50 from FTMO 1h aggregated to UTC daily** (not the Dukascopy / Coinbase research feed) — required by pre-flight 3 ("same price source you trade"); documented in logs as `feed`.
3. **MetaAPI historical 504s** on some candle chunks — the engine retries and merges overlapping windows; regime still computed (confirmed in pre-flight and live).
4. **Day-risk closed-PnL tracking starts empty** in `c4_state.json` — float from open C4 positions and the equity-floor buffer are active from day one.
5. **Research status remains CONDITIONAL** — Odin accepted test-and-see.

Risk rules carried from the brief (section B of the checklist): no new entries if this book's closed + float ≤ −2% equity on the CE(S)T day; no new entries within 3% of the FTMO 10% max-loss floor; same-minute double touch treated as a stop.

---

## 7) Parallel systems (unchanged)

| System | State |
|---|---|
| Drip freeze | **ON**; 22% cut + TP sweep **ON** |
| Griff engines | untouched (inactive) |
| Asterdex | untouched |
| Catalogue-B | not enabled |

---

## 8) Success / kill for the first 10 trading days

- **Keep:** no day worse than −2% from the C4 book; C4 cumulative not worse than −3%.
- **Kill:** any FTMO daily / max-loss near-miss attributable to C4, or 10 days with C4 net < −2%.

---

## 9) Authorization trail

| When (ET) | Who | What |
|---|---|---|
| ~8:05 AM | Odin | Approved: freeze the live catalogue drip **and** set up Candidate 4; test and see; absolute requirement of no order-execution or implementation issues |
| 8:07:44 AM | Trading Ops | Freeze installed on `catalogue-btc-15m.service` |
| 8:30:04 AM | Trading Ops | Slot proof `skip_freeze_new_buys` |
| ~8:33 AM | Trading Ops | C4 pre-flight 12/12 PASS, live min-size ticket 173729950 verified and closed, `c4-sma50-r1.service` armed; FINAL status written |
| ~8:46 AM | Odin via Trading Ops | Strategy Implementer to record the above in this repository as a **docs-only** PR; no live service, VM path, or trading-code change |
