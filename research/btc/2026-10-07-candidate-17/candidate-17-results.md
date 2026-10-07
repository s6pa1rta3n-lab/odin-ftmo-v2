# Candidate 17 Results — Pass Path Package (≤90d)

**Best path label: CONDITIONAL (multi-asset residual)** (`B_c15_0.75` + ≥$3,709/mo second instrument)

**One sentence:** CONDITIONAL multi-asset residual — BTC C15@0.75% $1291/mo legal DD 7.4% + need ≥$3,709/mo from US100/Gold in ≤2.6% shared-DD headroom; BTC-alone ≤90d windows 0/879.

**Measured:** 2026-10-07 11:55:27 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-17-pass-path.md`

## THE PASS PATH

**CONDITIONAL (multi-asset residual) — the measured way to clear ≤90d:** Run BTC **C15 H4 BB squeeze @0.75%** (HO **$1,291/mo**, max DD **7.4%** legal, leave-out OK, Fit OK) as the BTC sleeve. It alone prints **0/879** continuous ≤90d windows and **0/879** Challenge→reset→Verification sequential windows; Ext **$-1,823** (FAIL — do not deploy BTC sleeve until Ext fixed). To hit +$15k in 90d you still need **≥$3,709/mo** from a second instrument (US100 and/or Gold) under the remaining shared DD budget of **~2.6%** (10% − BTC 7.4%). Alt denser BTC sleeve: C15 @1.00% = $1,736/mo / DD 9.8% → gap **$3,264/mo** but only **~0.2%** DD headroom left (tighter). Workstreams A (dual C5+C15) and C (H4-BREAK-6 hard wrap) did not produce a legal ≤90d BTC-only pass.
## Workstream scoreboard

| Tag | Path | HO $/mo | Fit | Leave | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 reset | HO≤90d | Legal |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `B_c15_1.00` | **FAIL** | $1,736 | $465 | $3,835 | $-2,527 | -2.04% | 9.8% | 0/909 | 0/879 | 0/879 | 0/210 | YES |
| `B_c15_0.75` | **FAIL** | $1,291 | $523 | $3,005 | $-1,823 | -1.53% | 7.4% | 0/909 | 0/879 | 0/879 | 0/210 | YES |
| `C_h4b6_R15_0.50` | **FAIL** | $444 | $2,996 | $-431 | $419 | -1.01% | 8.2% | 0/947 | 0/917 | 0/917 | 0/210 | YES |
| `C_h4b6_R1_0.65` | **FAIL** | $435 | $7,889 | $-3,830 | $557 | -1.31% | 9.8% | 0/947 | 0/917 | 0/917 | 0/210 | YES |
| `C_h4b6_R1_0.50` | **FAIL** | $342 | $6,168 | $-2,850 | $419 | -1.02% | 7.6% | 0/947 | 0/917 | 0/917 | 0/210 | YES |
| `A_dual_0.50_0.50` | **FAIL** | $1,003 | $-8,786 | $2,705 | $-982 | -1.54% | 16.2% | 0/918 | 0/888 | 0/0 | 0/210 | NO |
| `A_dual_0.40_0.40` | **FAIL** | $814 | $-7,004 | $2,220 | $-792 | -1.23% | 13.1% | 0/918 | 0/888 | 0/0 | 0/210 | NO |
| `A_dual_0.35_0.35` | **FAIL** | $713 | $-6,069 | $1,958 | $-694 | -1.07% | 11.5% | 0/918 | 0/888 | 0/0 | 0/210 | NO |
| `C_h4b6_R15_0.75` | **FAIL** | $672 | $4,531 | $-721 | $602 | -1.51% | 12.0% | 0/947 | 0/917 | 0/917 | 0/210 | NO |
| `C_h4b6_R15_0.65` | **FAIL** | $587 | $3,819 | $-527 | $502 | -1.32% | 10.6% | 0/947 | 0/917 | 0/917 | 0/210 | NO |
| `C_h4b6_R1_0.75` | **FAIL** | $521 | $9,030 | $-4,395 | $612 | -1.52% | 11.2% | 0/947 | 0/917 | 0/917 | 0/210 | NO |

## Workstream A — Dual C5+C15

### `A_dual_0.50_0.50` — FAIL

- Risk: c5@0.50%+c15@0.50%
- Trades: 563; meta: {'signals_a': 449, 'signals_b': 114, 'taken_a': 449, 'taken_b': 114, 'skip_kill': 0, 'skip_lots': 0, 'skip_busy': 0, 'final_equity': 100016.1791840012, 'killed_days': 0, 'taken': 563}
- HO $9,784.46 (~$1,003/mo); Fit $-8,786.40; Leave ['2026-08', '2026-06'] → $2,704.73; Ext $-981.88
- Worst Prague day: 2025-02-17 -1.54%; fail-days=0; max DD 16.17%
- ≤60d 0/918; ≤90d 0/888; HO≤90d 0/210

### `A_dual_0.40_0.40` — FAIL

- Risk: c5@0.40%+c15@0.40%
- Trades: 563; meta: {'signals_a': 449, 'signals_b': 114, 'taken_a': 449, 'taken_b': 114, 'skip_kill': 0, 'skip_lots': 0, 'skip_busy': 0, 'final_equity': 100142.76659599946, 'killed_days': 0, 'taken': 563}
- HO $7,938.47 (~$814/mo); Fit $-7,003.56; Leave ['2026-08', '2026-06'] → $2,219.59; Ext $-792.14
- Worst Prague day: 2025-02-17 -1.23%; fail-days=0; max DD 13.09%
- ≤60d 0/918; ≤90d 0/888; HO≤90d 0/210

### `A_dual_0.35_0.35` — FAIL

- Risk: c5@0.35%+c15@0.35%
- Trades: 563; meta: {'signals_a': 449, 'signals_b': 114, 'taken_a': 449, 'taken_b': 114, 'skip_kill': 0, 'skip_lots': 0, 'skip_busy': 0, 'final_equity': 100193.16587899881, 'killed_days': 0, 'taken': 563}
- HO $6,956.10 (~$713/mo); Fit $-6,069.25; Leave ['2026-08', '2026-06'] → $1,957.66; Ext $-693.69
- Worst Prague day: 2025-02-17 -1.07%; fail-days=0; max DD 11.53%
- ≤60d 0/918; ≤90d 0/888; HO≤90d 0/210

## Workstream B — C15 ≤90d

### `B_c15_1.00` — FAIL

- Risk: c15@1.00%
- Trades: 114; meta: {'signals': 114, 'taken': 114, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 114876.35449099999, 'killed_days': 0}
- HO $16,938.22 (~$1,736/mo); Fit $464.84; Leave ['2026-06', '2026-08'] → $3,834.78; Ext $-2,526.71
- Worst Prague day: 2026-09-28 -2.04%; fail-days=0; max DD 9.80%
- ≤60d 0/909; ≤90d 0/879; HO≤90d 0/210

### `B_c15_0.75` — FAIL

- Risk: c15@0.75%
- Trades: 114; meta: {'signals': 114, 'taken': 114, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 111294.33854200004, 'killed_days': 0}
- HO $12,594.53 (~$1,291/mo); Fit $522.55; Leave ['2026-06', '2026-08'] → $3,005.28; Ext $-1,822.74
- Worst Prague day: 2026-09-28 -1.53%; fail-days=0; max DD 7.41%
- ≤60d 0/909; ≤90d 0/879; HO≤90d 0/210

## Workstream C — H4-BREAK-6 hard DD

### `C_h4b6_R15_0.50` — FAIL

- Risk: h4b6 R=1.5 @0.50%
- Trades: 303; meta: {'signals': 303, 'taken': 303, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 107751.60838549984, 'killed_days': 0}
- HO $4,336.58 (~$444/mo); Fit $2,995.80; Leave ['2026-08', '2026-03'] → $-430.59; Ext $419.22
- Worst Prague day: 2025-09-01 -1.01%; fail-days=0; max DD 8.22%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

### `C_h4b6_R1_0.65` — FAIL

- Risk: h4b6 R=1 @0.65%
- Trades: 370; meta: {'signals': 370, 'taken': 370, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 112694.346613, 'killed_days': 0}
- HO $4,248.33 (~$435/mo); Fit $7,889.11; Leave ['2026-08', '2026-03'] → $-3,829.91; Ext $556.91
- Worst Prague day: 2025-12-26 -1.31%; fail-days=0; max DD 9.76%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

### `C_h4b6_R1_0.50` — FAIL

- Risk: h4b6 R=1 @0.50%
- Trades: 370; meta: {'signals': 370, 'taken': 370, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 109923.79743300009, 'killed_days': 0}
- HO $3,336.23 (~$342/mo); Fit $6,168.50; Leave ['2026-08', '2026-03'] → $-2,849.68; Ext $419.07
- Worst Prague day: 2025-12-26 -1.02%; fail-days=0; max DD 7.61%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

### `C_h4b6_R15_0.75` — FAIL

- Risk: h4b6 R=1.5 @0.75%
- Trades: 303; meta: {'signals': 303, 'taken': 303, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 111686.009661, 'killed_days': 0}
- HO $6,553.32 (~$672/mo); Fit $4,530.98; Leave ['2026-08', '2026-03'] → $-721.04; Ext $601.71
- Worst Prague day: 2025-12-26 -1.51%; fail-days=0; max DD 12.02%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

### `C_h4b6_R15_0.65` — FAIL

- Risk: h4b6 R=1.5 @0.65%
- Trades: 303; meta: {'signals': 303, 'taken': 303, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 110047.91932825, 'killed_days': 0}
- HO $5,727.33 (~$587/mo); Fit $3,819.06; Leave ['2026-08', '2026-03'] → $-526.71; Ext $501.53
- Worst Prague day: 2025-12-26 -1.32%; fail-days=0; max DD 10.61%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

### `C_h4b6_R1_0.75` — FAIL

- Risk: h4b6 R=1 @0.75%
- Trades: 370; meta: {'signals': 370, 'taken': 370, 'skip_kill': 0, 'skip_lots': 0, 'final_equity': 114726.96604799996, 'killed_days': 0}
- HO $5,084.48 (~$521/mo); Fit $9,030.00; Leave ['2026-08', '2026-03'] → $-4,395.04; Ext $612.48
- Worst Prague day: 2025-09-09 -1.52%; fail-days=0; max DD 11.19%
- ≤60d 0/947; ≤90d 0/917; HO≤90d 0/210

## Residual / second-instrument math

Target pace for +$15k in 90d: **$5,000/mo**.

| BTC sleeve (legal DD) | HO $/mo | Max DD | DD budget left | Gap to $5k/mo | Ext |
|---|---:|---:|---:|---:|---:|
| **C15 @0.75% (PRIMARY residual)** | $1,291 | 7.4% | **2.6%** | **$3,709** | $-1,823 |
| C15 @1.00% (alt denser) | $1,736 | 9.8% | 0.2% | $3,264 | $-2,527 |
| H4-BREAK-6 R=1.5 @0.50% | $444 | 8.2% | 1.8% | $4,556 | +$419 |
| H4-BREAK-6 R=1 @0.65% | $435 | 9.8% | 0.2% | $4,565 | +$557 |

**Minimum second-instrument contribution (PRIMARY): ≥$3,709/mo** at combined max DD ≤10% (BTC already 7.4%).  
Next research action (not this PR): measure US100/Gold books that can deliver ≥$3,709/mo with max DD ≤2.6% standalone (or less when combined).

Dual A blew shared DD (11.5–16.2%) — correlated BTC books do not buy pace without illegal DD.  
C H4-BREAK-6 hard wrap: Ext≥0 at 0.50–0.65% but pace ≤$587/mo and 0 ≤90d windows.

## Cost model note

Unified on FTMO spread=15 × lots (commission 0, swap 0) for A/B/C. C5 originally used catalogue 0.065%+swap at vol 0.01; C17 dual/replay re-sizes C5 with % equity risk and spread=15 for shared-DD apples-to-apples.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
