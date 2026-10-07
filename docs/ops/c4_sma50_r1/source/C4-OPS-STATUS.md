# C4 Ops Status — FINAL — 2026-10-07

**Operator:** Trading Ops (Grok Bot executor)  
**Odin approval:** ~8:05 AM ET freeze drip + set up C4  
**Addendum:** watched min-size live fill+SL+TP before nightly arm  
**Completed:** ~8:33 AM ET

---

## 1) Freeze drip — PROVEN

| Item | Value |
|---|---|
| Time freeze installed | **8:07:44 AM ET** |
| Slot proof | **8:30:04 AM ET** `skip_freeze_new_buys` for slot `2026-10-07T08:30:00-04:00` |
| Mechanism | `FREEZE_NEW_BUYS=1` in `catalogue-btc-15m.service` Environment + gate in `btc_15m_buy.py` |
| Backup | `/home/solveetcoagula/ftmo-catalogue/btc_15m_buy.py.bak.freeze-20261007-0806et` |
| Service | still **active** |
| New buys | **blocked** (no `CATALOGUE_BTC_15M` buy at 8:30) |
| 22% hourly oldest-loser cut | **KEPT** (runs on :00 when margin≥22%) |
| TP sweep / TP recovery | **KEPT** |
| Sheet updater | `btc-sheet-updater.service` **active** (unchanged) |
| Open catalogue buys | **not mass-closed** |

Journal excerpt:
```
{"event":"start",...,"freezeNewBuys":true,"loggedAt":"2026-10-07T08:07:44..."}
{"event":"skip_freeze_new_buys","slot":"2026-10-07T08:30:00-04:00","freezeNewBuys":true,"marginPercent":9.42,"equity":91749.61,"loggedAt":"2026-10-07T08:30:04.840272-04:00"}
```

---

## 2) Candidate 4 — NEW book — ARMED

| Item | Value |
|---|---|
| Path | `/home/solveetcoagula/ftmo-c4/` |
| Engine | `c4_sma50_r1.py` |
| Service | **`c4-sma50-r1.service`** (enabled, active) |
| Comment | `C4_SMA50_R1` |
| Account | MetaAPI `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` (same as drip — documented) |
| Volume | 0.01 (~$412.91 stop ≈ $413 risk) |
| SL/TP | ±412.91 hard, both required; emergency close if SL cannot be set |
| Regime feed | FTMO MetaAPI market-data **1h → UTC daily close** vs SMA50 (prior closed UTC day only) |
| First entry window | **tonight 2026-10-08 00:00 UTC = 8:00 PM ET** |
| Kill switch | touch `/home/solveetcoagula/ftmo-c4/KILL` or `C4_KILL=1` + restart; or `systemctl stop c4-sma50-r1` |
| Disarm | `C4_ARMED=0` in unit + restart, or touch `DISARM` |

Start log:
```
{"event":"start",...,"armed":true,"kill":false,...,"loggedAt":"2026-10-07T08:33:50..."}
{"event":"wait_slot","slot":"2026-10-08T00:00:00+00:00",...}
```

---

## 3) Pre-flight (1–12) — ALL PASS

1. PASS — MetaAPI London + account (FTMO, equity ~91750)
2. PASS — BTCUSD tradable (`SYMBOL_TRADE_MODE_FULL`)
3. PASS — SMA50 prior UTC close (2026-10-06 close 85506.23 > SMA50 79893.16 → **long**)
4. PASS — Atomic market+SL+TP + modify-with-retry; emergency close if no SL
5. PASS — 412.91 rounds 2dp both sides
6. PASS — Short path dry-run logged
7. PASS — Max-1 hard skip
8. PASS — Drip freeze holds (`FREEZE_NEW_BUYS=1`) while C4 arms
9. PASS — Kill switch <60s (KILL file)
10. PASS — Dry-run SL/TP + **live min-size** (see below)
11. PASS — Structured JSON logs + `alert=True` on reject/timeout/504
12. PASS — No Griff/Asterdex/drip comment collision

### Live min-size test
| Field | Value |
|---|---|
| Ticket | **173729950** |
| Side | long |
| Open | 83524.2 |
| SL | 83112.08 |
| TP | 83937.9 |
| Volume | 0.01 |
| Result | **PASS** (sl_ok + tp_ok) then **closed** after verify |
| Remaining C4 | none |

---

## 4) Deviations from research rules

1. **Same MetaAPI account as drip** — intentional; comments segregate books (`C4_SMA50_R1` vs `CATALOGUE_BTC_15M`).
2. **SMA50 from FTMO 1h aggregated to UTC daily** (not Dukas/Coinbase research feed) — required “same price source you trade”; documented in logs as `feed`.
3. **MetaAPI historical 504s** on some candle chunks — engine retries/merges overlapping windows; regime still computed (preflight + live confirmed).
4. **Day-risk closed PnL tracking** starts empty in `c4_state.json` (float from open C4 + equity floor buffer active from day one).
5. Research status remains **CONDITIONAL** — Odin accepted test-and-see.

---

## 5) Armed-for

**ARMED for 2026-10-08 00:00 UTC (tonight 8:00 PM ET).**  
Expect **long** unless Oct 7 UTC daily close flips vs SMA50 before entry.

---

## 6) Parallel systems

- Drip freeze: **ON**; cut + TP sweep: **ON**
- Griff engines: untouched (inactive)
- Asterdex: untouched
- Catalogue-B: not enabled
