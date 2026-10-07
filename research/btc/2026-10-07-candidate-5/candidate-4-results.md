# Candidate 4 Results — Small Fixed-Risk Daily Regime R=1 (max 1)

**Decision: CONDITIONAL**

**One sentence:** CONDITIONAL Candidate 4: HO/ext/worst-day OK but fit $-8,949.23.

**Measured:** 2026-10-07 07:45:46 EDT
**Live engines:** not modified.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-4.md`

## Rules used

- SMA50 exclusive dual; stop=target=**412.91** (R=1); max 1; 00:00 UTC entry
- One-stop risk ≈ **$412.91** at vol 0.01; costs 0.065% + swap est.
- Data: merged Dukas M1 2024-01-01 00:00:00+00:00 → 2026-10-07 11:34:00+00:00

## Gate checklist

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout full > 0 and > buy-only | YES | HO $7,158.94; buy-only $-8,258.20 |
| 2 Extension full ≥ 0 | YES | $786.15 |
| 3 Leave-out two best HO months > 0 | YES | removed ['2025-11', '2026-04']; left $2,251.35 |
| 4 Worst day ≥ −2000 HO & ext | YES | HO ('2025-12-30', Decimal('-825.82')); ext ('2026-09-06', Decimal('-825.82')) |
| 5 Fit full ≥ −5000 | NO | $-8,949.23 |
| 6 Holdout months ≥50% green | YES | 8/11 (72.7%) |

**Remaining gate / next:** Remaining: fit $-8,949.23. No live changes.

## Slices (exclusive dual)

### Holdout (2025-11-08 → 2026-09-01 UTC entries)

- Regime days L/S/F: 110/172/0; skip no-bar/in-trade: 14/6

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 103 | 53.4% | 2,877.78 | 2,776.33 | 2,774.50 |
| Short | 159 | 53.5% | 4,542.01 | 4,386.03 | 4,384.44 |
| Combined | 262 | 53.4% | 7,419.79 | 7,162.35 | 7,158.94 |

- Worst ET day raw: **2025-12-30** → **$-825.82**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **8/11** (72.7%)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2025-11 | 18 | 2,455.08 |
| 2025-12 | 25 | 384.00 |
| 2026-01 | 31 | -2,940.14 |
| 2026-02 | 23 | 1,218.17 |
| 2026-03 | 31 | -1,266.74 |
| 2026-04 | 26 | 2,452.51 |
| 2026-05 | 25 | 2,039.23 |
| 2026-06 | 28 | 1,628.71 |
| 2026-07 | 26 | -848.49 |
| 2026-08 | 28 | 1,624.72 |
| 2026-09 | 1 | 411.89 |

### Leave-out (removed ['2025-11', '2026-04'])

| Trades left | Net full $ | Worst raw |
|---:|---:|---|
| 218 | **2,251.35** | 2025-12-30 -825.82 |

### Extension (2026-09-02 → 2026-10-07)

- Regime days L/S/F: 36/0/0; skip no-bar/in-trade: 0/2

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 34 | 52.9% | 823.43 | 787.49 | 786.15 |
| Short | 0 | n/a | 0.00 | 0.00 | 0.00 |
| Combined | 34 | 52.9% | 823.43 | 787.49 | 786.15 |

- Worst ET day raw: **2026-09-06** → **$-825.82**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **1/2** (50.0%)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2026-09 | 27 | -442.44 |
| 2026-10 | 7 | 1,228.59 |

### Fit (2024-01-01 → 2025-11-07)

- Regime days L/S/F: 367/239/0; skip no-bar/in-trade: 21/7

| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |
|---|---:|---:|---:|---:|---:|
| Long | 351 | 48.7% | -3,743.45 | -4,148.96 | -4,151.95 |
| Short | 227 | 47.6% | -4,555.59 | -4,796.26 | -4,797.28 |
| Combined | 578 | 48.3% | -8,299.04 | -8,945.21 | -8,949.23 |

- Worst ET day raw: **2024-06-10** → **$-827.01**; days < −$2,000: **0**; open-at-end: 0
- Months ≥0: **8/22** (36.4%)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2024-02 | 8 | -831.71 |
| 2024-03 | 31 | 2,863.09 |
| 2024-04 | 28 | -1,675.51 |
| 2024-05 | 30 | -25.44 |
| 2024-06 | 25 | -436.90 |
| 2024-07 | 25 | 392.78 |
| 2024-08 | 30 | -1,675.48 |
| 2024-09 | 29 | -2,926.25 |
| 2024-10 | 30 | 1,618.40 |
| 2024-11 | 30 | 1,617.88 |
| 2024-12 | 30 | -38.35 |
| 2025-01 | 31 | -2,930.53 |
| 2025-02 | 27 | -1,281.79 |
| 2025-03 | 29 | -4,578.07 |
| 2025-04 | 26 | 1,622.58 |
| 2025-05 | 27 | -449.26 |
| 2025-06 | 28 | -3,348.09 |
| 2025-07 | 26 | -865.62 |
| 2025-08 | 31 | 1,192.46 |
| 2025-09 | 28 | -2,518.71 |
| 2025-10 | 23 | 3,681.89 |
| 2025-11 | 6 | 1,643.41 |

## Diagnostics — long-only / short-only under SMA50 (same stop/R)

| Slice | Long-only full $ | Short-only full $ |
|---|---:|---:|
| Holdout | 2,774.50 (n=103, wr=53.4%) | 4,384.44 (n=159, wr=53.5%) |
| Holdout+ext | 3,560.64 | 4,384.44 |

## Assumptions / limitations

1. Real Dukas M1 only; missing midnights skipped.
2. Catalogue $ at vol 0.01; leave-out by ET exit month.
3. No live engine changes.

## User summary (≤15 lines)

1. **CONDITIONAL** — SMA50 exclusive dual, stop=target **$412.91** (R=1), max 1.
2. Holdout full **$7,158.94** (L/S 103/159, 53.4% wins) vs buy-only **$-8,258.20**.
3. Extension **$786.15**; fit **$-8,949.23**.
4. Leave-out removed **['2025-11', '2026-04']** → **$2,251.35**.
5. Worst HO **2025-12-30 $-825.82**; ext **2026-09-06 $-825.82**.
6. Months green **8/11 (72.7%)**; HO long-only **$2,774.50** / short-only **$4,384.44**.
7. CONDITIONAL Candidate 4: HO/ext/worst-day OK but fit $-8,949.23.
8. Live engines untouched.
