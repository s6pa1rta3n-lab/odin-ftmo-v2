# FTMO BTC — Candidate 6 Spec

**Name:** C5 Fast-Scale Probe (pace vs FTMO DD wall)  
**Status:** Research measurement only — live engines / C4 / drip untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Odin pace bar (updated):** BOTH FTMO steps (Challenge +10% then Verification +5%) inside **≤60 calendar days** on a **~$100k 2-step** account (ASSUMPTION — catalogue does not encode challenge size; labeled $100k).

**Scoreboard so far:**  
- C1–C3 → REJECT / CONDITIONAL (see prior specs)  
- C4 SMA50 exclusive dual R=1 → CONDITIONAL (fit fail)  
- C5 E+V75 → research ACCEPT on 6 gates, **REJECT as pass-speed** (~$480/mo at 0.01)  
- **C6 (this):** same C5 edge, ask whether **size alone** can hit ≤60-day pace without breaking 5% daily / 10% max DD

---

## One-line thesis

Do **not** invent a new filter edge. Take the only BTC book that cleared all six research gates (C5), measure the volume required for Challenge (~+$10,000) + Verification (~+$5,000) inside ≤60 calendar days from holdout-like pace, and **brutally** check whether that size keeps one-stop and historical worst-day inside FTMO daily 5% / max 10%. If the DD wall is hit before the pace bar, **REJECT** as a fast FTMO vehicle — that is still a useful result.

## Why this path (one primary — not a fishing trip)

| Option | Verdict a priori |
|---|---|
| 1. New HF (H4/H1) | Survey H4-BREAK-6 had some 3-month window hits but max realized DD ~14.8%, a floating −6.9% day, and most holdout windows failed 1.10/1.155 — not a clean ≤60-day vehicle without re-tuning. C3 4H Donchian already REJECT on HO. |
| **2. Scale C5 (chosen)** | Honest: dollars scale ~linear with volume; DD does too. Measure the wall on real Dukas C5 trades. |
| 3. Other survey $/mo | Asia/PDHL/etc. 0/30 three-month passes; slower or riskier than claiming a 60-day pass. |

## Direction / timeframe / rules

**Identical to Candidate 5** (no rule change):

- SMA50 exclusive dual; stop=target=**412.91** (R=1); max 1; 00:00 UTC entry  
- Filter E: SMA50 slope (lookback 10)  
- Filter V75: prior ATR(14) < P75 of prior 100d ATR (≥50 non-null)  
- Costs: commission **0.065%**/side; swap est. **|−30%|/360** per UTC midnight held (same as C4/C5)

## Risk / size ASSUMPTIONS

| Assumption | Value | Label |
|---|---|---|
| Account | **$100,000** 2-step | ASSUMPTION (not in BTCUSD catalogue symbol feed) |
| Challenge target | +10% ≈ **+$10,000** | ASSUMPTION |
| Verification target | +5% ≈ **+$5,000** | ASSUMPTION |
| Daily DD limit | **5%** ≈ **−$5,000** from day-start (research uses scaled historical worst ET day raw) | ASSUMPTION / FTMO-standard reading |
| Max DD limit | **10%** ≈ **−$10,000** from initial (research flags if scaled fit net or scaled HO peak-to-trough proxy exceeds) | ASSUMPTION |
| Baseline volume | **0.01** (catalogue min; one stop ≈ **$412.91**) | measured |
| Proposed size | Whatever volume makes HO-like pace ≥ **~$7,500/month** after costs (so +$10k then +$5k plausible in ≤60 days), **or** the max volume that keeps worst-day ≥ −$5,000 — report both | measured |
| Pace bar for ACCEPT as “fast vehicle” | At stated volume: estimated calendar days to +$10k then +$5k from HO monthly pace ≤ **60 total**, **and** scaled worst HO/ext day ≥ −$5,000, **and** one full stop $ ≤ $5,000, **and** no obvious max-DD blow from scaled slice nets | required |

Rough arithmetic Odin bar: ~$7.5k+/month after costs at stated size.

## Gates

### A. Robustness (same 6 as C5) at volume **0.01**

1. Holdout after costs **> 0** and **> buy-only −$8,258.20**  
2. Extension after costs **≥ 0**  
3. Leave-out two best holdout months → remaining **> 0**  
4. Worst ET day raw ≥ **−$2,000** on HO and ext (research budget at 0.01)  
5. Fit after costs ≥ **−$5,000**  
6. Holdout months with trades: **≥50%** green  

### B. Fast-vehicle gates (new — decide ACCEPT/CONDITIONAL/REJECT for “fast FTMO”)

7. **Pace:** At proposed volume, HO-implied months-to-+$10k + months-to-+$5k (calendar days) ≤ **60**  
8. **Daily DD:** Scaled HO & ext worst ET day raw ≥ **−$5,000**; one catalogue stop at that volume ≤ **$5,000**  
9. **Max DD honesty:** Scaled fit net and/or HO running drawdown proxy must not clearly exceed **−$10,000** at that volume (report numbers; fail if violated)

**ACCEPT as fast vehicle** only if A and B all pass.  
**CONDITIONAL** if A passes but B is borderline / assumption-sensitive.  
**REJECT as fast vehicle** if B fails (even if A still holds at 0.01) — expected outcome if scale hits DD before pace.

## Slices (same as C5)

| Slice | UTC entry midnights |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout | 2025-11-08 → 2026-09-01 |
| Extension | 2026-09-02 → last available |

## Deliverables

- Runner: `/workspace/btc-strategies/run_candidate_6.py`  
- Results: `/workspace/btc-strategies/candidate-6-results.md`  
- Pack: `/workspace/btc-strategies/2026-10-07-candidate-6/`

## Live

**Do not touch** live VM, MetaAPI, FREEZE_NEW_BUYS, C4 under `/home/solveetcoagula/ftmo-c4/`, or drip.
