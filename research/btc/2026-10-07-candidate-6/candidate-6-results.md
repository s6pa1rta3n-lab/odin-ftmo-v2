# Candidate 6 Results — C5 Fast-Scale Probe (pace vs DD wall)

**Decision: REJECT** (as fast FTMO vehicle)

**One sentence:** REJECT C6 as fast FTMO vehicle: C5 edge cannot hit Challenge+Verification in ≤60 calendar days without blowing 5% daily / 10% max DD on real Dukas HO.

**Measured:** 2026-10-07 08:58:33 EDT
**Live engines:** not modified. C4/drip/FREEZE untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-6.md`

## ASSUMPTIONS (labeled)

| Item | Value |
|---|---|
| Account | $100,000.00 2-step (ASSUMPTION) |
| Challenge | +10% ≈ +$10,000.00 |
| Verification | +5% ≈ +$5,000.00 |
| Pace bar | ≤60 calendar days for BOTH steps (~$7,500.00/mo HO-like) |
| Daily DD | 5% ≈ −$5,000.00 |
| Max DD | 10% ≈ −$10,000.00 (fit-net scale used as honesty proxy) |
| Base edge | C5 rules; stop=target=412.91; vol base 0.01 |
| HO window | 2025-11-08 → 2026-09-01 UTC (297 calendar days) |

## Rules used

- Identical to C5: SMA50 exclusive dual R=1 + slope E + ATR < P75(100d)
- No new filters; only volume scaling of measured C5 trade dollars
- Data: merged Dukas M1 (same as C5)

## Gate A — robustness at vol 0.01 (C5 re-measure)

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout full > 0 and > buy-only | YES | HO $4,790.18; buy-only $-8,258.20 |
| 2 Extension full ≥ 0 | YES | $385.76 |
| 3 Leave-out two best HO months > 0 | YES | removed ['2026-04', '2025-12']; left $707.31 |
| 4 Worst day ≥ −2000 HO & ext | YES | HO ('2025-12-30', Decimal('-825.82')); ext ('2026-09-13', Decimal('-825.82')) |
| 5 Fit full ≥ −5000 | YES | $-3,213.88 |
| 6 Holdout months ≥50% green | YES | 7/11 (63.6%) |

**Gate A all pass?** YES

## Pace at 0.01

- HO net full: **$4,790.18** over **297** calendar days
- HO monthly pace: **$490.95/month**
- Days to Challenge +$10k (linear HO pace): **620.02**
- Days to both +$15k: **930.03**

## Scaling wall (the point of C6)

- One stop $ at 0.01: **$412.91**
- Worst HO ET day raw at 0.01: **$-825.82** (2025-12-30)
- Worst ext ET day raw at 0.01: **$-825.82** (2026-09-13)
- Binding worst-day for scale: **$-825.82**

- **Max vol by daily DD** (worst-day × scale ≥ −$5,000): **0.06**
- **Max vol by one-stop ≤ $5,000:** **0.12**
- **Max vol by fit-net ≥ −$10,000 (proxy):** **0.03**
- **Max DD-safe vol (min of daily + one-stop):** **0.06**

- At max DD-safe vol **0.06**:
  - HO pace ≈ **$2,972.52/month**
  - Est. days to Challenge: **102.40**
  - Est. days to both steps: **153.61** (>60 NO — fails Odin bar)

- **Vol needed for ~$7,500.00/mo:** **0.15** (scale ×15.28)
  - Worst day at that size: **$-12,615.57** (limit −$5,000.00) → **VIOLATES 5% daily**
  - One stop at that size: **$6,307.78** → **VIOLATES 5% daily (single stop)**
  - Fit net scaled: **$-49,096.51** (limit −$10,000.00) → **VIOLATES 10% max-DD proxy**
  - Est. days Challenge / Verification / both: **40.59 / 20.29 / 60.88**

## Gate B — fast vehicle

| Gate | Pass? | Detail |
|---|---|---|
| 7 Pace ≤60d both at a DD-legal size | NO | max safe both-days=153.61 |
| 8 Daily DD OK at pace-needed vol | NO | needed vol 0.15 |
| 9 Max-DD proxy OK at pace-needed vol | NO | scaled fit -49,096.51 |

## Scale table (linear $ with volume)

| Vol | HO $/mo | HO net (×) | Worst day $ | One stop $ | Fit net (×) | Days to +$10k | Days both +$15k | Daily OK | Fit≤10k | Both≤60d |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|
| 0.01 | 490.95 | 4,790.18 | -825.82 | 412.91 | -3,213.88 | 620.02 | 930.03 | Y | Y | N |
| 0.02 | 981.91 | 9,580.36 | -1,651.64 | 825.82 | -6,427.75 | 310.01 | 465.01 | Y | Y | N |
| 0.03 | 1,472.86 | 14,370.54 | -2,477.46 | 1,238.73 | -9,641.63 | 206.67 | 310.01 | Y | Y | N |
| 0.04 | 1,963.81 | 19,160.72 | -3,303.28 | 1,651.64 | -12,855.51 | 155.00 | 232.51 | Y | N | N |
| 0.05 | 2,454.77 | 23,950.89 | -4,129.10 | 2,064.55 | -16,069.39 | 124.00 | 186.01 | Y | N | N |
| 0.06 | 2,945.72 | 28,741.07 | -4,954.92 | 2,477.46 | -19,283.26 | 103.34 | 155.00 | Y | N | N |
| 0.08 | 3,927.62 | 38,321.43 | -6,606.56 | 3,303.28 | -25,711.02 | 77.50 | 116.25 | N | N | N |
| 0.10 | 4,909.53 | 47,901.79 | -8,258.20 | 4,129.10 | -32,138.77 | 62.00 | 93.00 | N | N | N |
| 0.15 | 7,364.30 | 71,852.68 | -12,387.30 | 6,193.65 | -48,208.16 | 41.33 | 62.00 | N | N | N |
| 0.20 | 9,819.06 | 95,803.58 | -16,516.40 | 8,258.20 | -64,277.54 | 31.00 | 46.50 | N | N | Y |

## Comparison vs C5

| | C5 @ 0.01 | C6 @ max DD-safe | C6 @ pace-needed |
|---|---:|---:|---:|
| Volume | 0.01 | 0.06 | 0.15 |
| HO $/mo | 490.95 | 2,972.52 | 7,500.00 |
| Days both steps | 930.03 | 153.61 | 60.88 |
| Worst day $ | -825.82 | -5,000.00 | -12,615.57 |

## HO monthly P&L at 0.01 (same as C5)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2025-11 | 1 | 411.74 |
| 2025-12 | 20 | 1,628.55 |
| 2026-01 | 12 | -839.64 |
| 2026-02 | 15 | 399.41 |
| 2026-03 | 25 | -1,261.09 |
| 2026-04 | 24 | 2,454.33 |
| 2026-05 | 20 | -20.49 |
| 2026-06 | 24 | 806.34 |
| 2026-07 | 12 | -10.34 |
| 2026-08 | 18 | 809.50 |
| 2026-09 | 1 | 411.89 |

## Why not H4-BREAK-6 / other HF as this candidate

Prior survey BTC-H4-BREAK-6 (1% risk, channel exit) reached final equity ~$152k and 4/30 floating-inclusive 3-month windows, but max realized DD ~14.8% (>10%), one floating day −6.9%, and most holdout-era windows failed 1.10/1.155. C3 4H Donchian already REJECT on HO. Scaling C5 is the cleaner single question for Odin’s ≤60-day bar.

## Decision

**REJECT** as a fast FTMO Challenge+Verification vehicle (≤60 calendar days).

REJECT C6 as fast FTMO vehicle: C5 edge cannot hit Challenge+Verification in ≤60 calendar days without blowing 5% daily / 10% max DD on real Dukas HO.

**Deployable-as-research-next?** **NO** for fast pass. C5 remains the robustness ACCEPT at 0.01; C4 stays live path. Need a structurally higher-$/month edge (or multi-symbol book) before a ≤60-day BTC claim.

## Assumptions / limitations

1. Linear volume scaling of realized C5 trade dollars (catalogue point value).
2. Pace uses average HO $/month — lumpy months mean calendar pass time is optimistic.
3. Max-DD check uses scaled fit *net* as a blunt proxy, not full peak-to-trough MTM.
4. FTMO daily is Prague equity incl. floating; research uses ET exit-day raw.
5. Account $100k ASSUMPTION.
6. No live engine / VM / C4 / drip changes.

## User summary (≤15 lines)

1. **REJECT** — C5 scaled cannot clear ≤60-day both-steps without FTMO DD breach.
2. HO @ 0.01: **$4,790.18** ≈ **$490.95/mo** over 297d.
3. Need ~**0.15** lots for ~$7.5k/mo → worst day **$-12,615.57** (limit $5k).
4. Max DD-safe vol ≈ **0.06** → both-steps ~**153.61** days (>60).
5. Gate A (robustness @ 0.01) still matches C5 ACCEPT; Gate B (fast) fails.
6. Not deployable for fast pass; live untouched.
