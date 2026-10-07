# Candidate 5 Results — SMA50 Slope + Elevated-Vol Skip (R=1)

**Decision: ACCEPT**

**One sentence:** ACCEPT Candidate 5: E+V75 clears all gates (HO $4,790.18, leave-out $707.31, ext $385.76, fit $-3,213.88, months 7/11 (63.6%)).

**Clearly better than C4?** YES — Clears all 6 gates including fit; C4 failed fit.

**Measured:** 2026-10-07 08:49:27 EDT
**Live engines:** not modified.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-5.md`

## Rules used

- SMA50 exclusive dual; stop=target=**412.91** (R=1); max 1; 00:00 UTC entry
- Filter E: SMA50 slope rising for long / falling for short (lookback 10 series days)
- Filter V75: prior ATR(14) < P75 of prior 100d ATR (≥50 non-null)
- One-stop risk ≈ **$412.91** at vol 0.01; costs 0.065% + swap est.
- Data: merged Dukas M1 2024-01-01 00:00:00+00:00 → 2026-10-07 11:34:00+00:00

## Gate checklist

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout full > 0 and > buy-only | YES | HO $4,790.18; buy-only $-8,258.20 |
| 2 Extension full ≥ 0 | YES | $385.76 |
| 3 Leave-out two best HO months > 0 | YES | removed ['2026-04', '2025-12']; left $707.31 |
| 4 Worst day ≥ −2000 HO & ext | YES | HO ('2025-12-30', Decimal('-825.82')); ext ('2026-09-13', Decimal('-825.82')) |
| 5 Fit full ≥ −5000 | YES | $-3,213.88 |
| 6 Holdout months ≥50% green | YES | 7/11 (63.6%) |

**Remaining gate / next:** Research ACCEPT only — no live deploy without separate approval.

## Comparison vs C4 / C4b-E

| Variant | Fit full | HO full | Ext full | Leave-out | HO months | Worst HO | Gates passed |
|---|---:|---:|---:|---:|---|---:|---:|
| C4 baseline | -8,949.23 | 7,158.94 | 786.15 | 2,251.35 | 8/11 | -825.82 | 5/6 |
| C4b-E (prior) | -6,693.22 | 7,229.50 | 786.15 | 2,320.09 | 7/11 | -825.82 | 5/6 |
| C5 E+V75 (this) | -3,213.88 | 4,790.18 | 385.76 | 707.31 | 7/11 (63.6%) | -825.82 | 6/6 |
| Diagnostic E-only | -6,693.22 | 7,229.50 | 786.15 | 2,320.09 | 7/11 | -825.82 | (diag) |

- Better bits: fit Δ $5,735.35, HO still + ($4,790.18)
- Worse bits: HO lower than C4 by $2,368.76, ext lower ($385.76 vs C4 $786.15), leave-out lower ($707.31 vs C4 $2,251.35)

## Slices (C5 primary)

### Holdout (2025-11-08 → 2026-09-01 UTC entries)

- Regime days L/S/F: 110/172/0; skip no-bar/in-trade: 7/1; filter skips: 102 (slope≈63, vol≈39)

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 61 | 54.1% | 2,064.55 | 2,004.25 | 2,004.25 |
| Short | 111 | 53.2% | 2,890.37 | 2,786.46 | 2,785.92 |
| Combined | 172 | 53.5% | 4,954.92 | 4,790.71 | 4,790.18 |

- Worst ET day raw: **2025-12-30** → **$-825.82**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **7/11** (63.6%)

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

### Leave-out (removed ['2026-04', '2025-12'])

| Trades left | Net full $ | Worst raw |
|---:|---:|---|
| 128 | **707.31** | 2026-01-18 -825.82 |

### Extension (2026-09-02 → 2026-10-07)

- Regime days L/S/F: 36/0/0; skip no-bar/in-trade: 0/1; filter skips: 12 (slope≈0, vol≈12)

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 23 | 52.2% | 410.52 | 386.40 | 385.76 |
| Short | 0 | n/a | 0.00 | 0.00 | 0.00 |
| Combined | 23 | 52.2% | 410.52 | 386.40 | 385.76 |

- Worst ET day raw: **2026-09-13** → **$-825.82**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **1/2** (50.0%)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2026-09 | 17 | -431.02 |
| 2026-10 | 6 | 816.78 |

### Fit (2024-01-01 → 2025-11-07)

- Regime days L/S/F: 367/239/0; skip no-bar/in-trade: 10/4; filter skips: 333 (slope≈177, vol≈156)

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 167 | 49.7% | -426.98 | -631.13 | -633.69 |
| Short | 92 | 46.7% | -2,487.05 | -2,580.19 | -2,580.19 |
| Combined | 259 | 48.6% | -2,914.03 | -3,211.31 | -3,213.88 |

- Worst ET day raw: **2024-06-10** → **$-827.01**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **6/18** (33.3%)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2024-04 | 3 | 410.38 |
| 2024-05 | 16 | -838.85 |
| 2024-06 | 12 | -12.46 |
| 2024-07 | 13 | 1,228.83 |
| 2024-08 | 4 | 822.67 |
| 2024-09 | 14 | -10.86 |
| 2024-10 | 28 | 2,445.79 |
| 2024-11 | 10 | 816.33 |
| 2025-01 | 9 | -1,250.45 |
| 2025-02 | 12 | -24.16 |
| 2025-03 | 13 | -3,730.55 |
| 2025-04 | 18 | 2,457.60 |
| 2025-05 | 27 | -449.26 |
| 2025-06 | 25 | -2,931.20 |
| 2025-07 | 25 | -1,277.15 |
| 2025-08 | 16 | -24.28 |
| 2025-09 | 13 | -431.75 |
| 2025-10 | 1 | -414.51 |

## Diagnostic — E-only (no V75; not a new candidate)

- Fit $-6,693.22; HO $7,229.50; ext $786.15; leave-out removed ['2025-11', '2026-04'] → $2,320.09
- Filter skips fit/HO: 177/63

## Assumptions / limitations

1. Real Dukas M1 only; missing midnights skipped.
2. Slope lookback 10 and V75 locked a priori (not fit-tuned).
3. Catalogue $ at vol 0.01; leave-out by ET exit month.
4. No live engine changes.

## User summary (≤15 lines)

1. **ACCEPT** — SMA50 exclusive dual R=1 + E slope + ATR < P75(100d).
2. Holdout full **$4,790.18** (L/S 61/111, 53.5% wins) vs buy-only **$-8,258.20**.
3. Extension **$385.76**; fit **$-3,213.88**.
4. Leave-out removed **['2026-04', '2025-12']** → **$707.31**.
5. Worst HO **2025-12-30 $-825.82**; ext **2026-09-13 $-825.82**.
6. Months green **7/11 (63.6%)**.
7. vs C4: clearly better? **YES** — Clears all 6 gates including fit; C4 failed fit.
8. ACCEPT Candidate 5: E+V75 clears all gates (HO $4,790.18, leave-out $707.31, ext $385.76, fit $-3,213.88, months 7/11 (63.6%)).
9. Live engines untouched.
