# Candidate 4 — `C4_SMA50_R1` (BTCUSD, SMA50 regime, R = 1)

Operations record for the Candidate 4 book and the parallel freeze of the live catalogue drip, both completed live by Trading Ops on 2026-10-07 (Odin approved ~8:05 AM ET; live work done ~8:33 AM ET).

**This tree is documentation only.** It records what already runs on matt-berserker. Nothing in this repository installs, enables, restarts, or edits `c4-sma50-r1.service` or `catalogue-btc-15m.service`, and nothing here changes trading-code behaviour. The engine source `c4_sma50_r1.py` lives only on the VM at `/home/solveetcoagula/ftmo-c4/` and was not part of the attached material, so it is **not** mirrored here.

| Document | What it is |
| --- | --- |
| [evidence/2026-10-07-drip-freeze-and-c4-arm.md](evidence/2026-10-07-drip-freeze-and-c4-arm.md) | FINAL record: drip freeze proof, C4 book facts, pre-flight 12/12, live min-size ticket, armed-for, deviations, authorization trail |
| [unit/c4-sma50-r1.service](unit/c4-sma50-r1.service) | Verbatim snapshot of the live unit file from the book path (for the record; do not install from here) |
| [source/C4-OPS-STATUS.md](source/C4-OPS-STATUS.md) | Trading Ops FINAL status (~8:33 AM ET), verbatim |
| [source/C4-IMPLEMENTATION-CHECKLIST.md](source/C4-IMPLEMENTATION-CHECKLIST.md) | Blocking pre-flight / implementation checklist, verbatim |
| [source/DEPLOY-TODAY-C4.md](source/DEPLOY-TODAY-C4.md) | Deploy-today brief (CONDITIONAL research status), verbatim |

## Quick facts

| Item | Value |
|---|---|
| Book path | `/home/solveetcoagula/ftmo-c4/` |
| Engine | `c4_sma50_r1.py` |
| Service | `c4-sma50-r1.service` (enabled, active) |
| Order comment | `C4_SMA50_R1` |
| Account | MetaAPI `a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf` (shared with the catalogue drip by design; comments segregate books) |
| Symbol / volume | BTCUSD / 0.01 |
| SL / TP | entry ± 412.91, both hard, both required; emergency close if SL cannot be set |
| Regime | prior UTC daily close vs SMA50, from FTMO MetaAPI 1h → UTC daily |
| Entry | 00:00 UTC only; max 1 open position |
| Kill | `touch /home/solveetcoagula/ftmo-c4/KILL`, or `C4_KILL=1` + restart, or `systemctl stop c4-sma50-r1` |
| Disarm | `C4_ARMED=0` in the unit + restart, or `touch /home/solveetcoagula/ftmo-c4/DISARM` |
| First armed entry | 2026-10-08 00:00 UTC (2026-10-07 8:00 PM ET) |

## Parallel: live catalogue drip

| Item | Value |
|---|---|
| Service | `catalogue-btc-15m.service` (still active) |
| Freeze | `FREEZE_NEW_BUYS=1` in the unit `Environment` + gate in `btc_15m_buy.py`, installed 8:07:44 AM ET |
| Proof | `skip_freeze_new_buys` at 8:30:04 AM ET for slot `2026-10-07T08:30:00-04:00` |
| Kept running | TP sweep / TP recovery; 22% hourly oldest-loser cut; `btc-sheet-updater.service` |
| Open catalogue positions | not mass-closed |

The drip was not rewritten into C4; C4 is a separate book.
