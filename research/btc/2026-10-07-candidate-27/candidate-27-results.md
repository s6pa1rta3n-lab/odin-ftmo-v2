# Candidate 27 — XAGUSD Wilder Parabolic SAR results

- Measured: 2026-10-07 12:26 EDT
- Data sha256: `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c`
- Spec sha256: `89623265cb63d101f0eed063b4dbb88f953fd2a6fa18042b914d9e3b2f375838`
- Gold entry30 preregister sha256: `29638946222b3801dde3c02f6b9831fb89975630768888200310266f99ed5c43` (mechanics source; not retuned)
- BTC SAR preregister present: `/workspace/strategy-explorer/btc-sar-preregister-2026-10-07.md` (mirror lane; BTC @0.50% FAIL not re-run)
- Data end: 2026-09-01 23:59:00+00:00
- Live C4 / drip / FREEZE: **untouched**
- Costs ASSUMPTION (C19/C24): contractSize=5000, spread=0.025, commission=$3/lot
- Worst Prague day uses **floating** mark (BTC SAR construction; XAG units=lots×5000)

## Lead
**REJECT — XAG Wilder SAR does not open a ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows. Best book 27A@2.50%: legal=False DD=21.08% HO=$2,052/mo 90d=21/863 outside=0.

## Summary table

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 27A@2.50% | 2.50% | 2,052 | 21.1% | 21/863 (0) | 25/863 (10) | 0 | 2,899 | NO | REJECT |
| 27B+soft | SOFT 2.50→1.25→0.75 | 757 | 12.8% | 0/863 (0) | 25/863 (10) | 0 | 658 | NO | REJECT |
| sens@2.60% | 2.60% sens | 2,173 | 21.9% | 38/863 (0) | 25/863 (10) | 0 | 3,063 | NO | REJECT |

## 27A XAG SAR @2.50% (primary)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $117,380.28 |
| Max DD | 21.0793% |
| Worst Prague day (floating) | 2026-01-30 (-11.4880%) |
| Worst Prague day (closed-only) | 2024-02-14 (-2.5097%) |
| Floating flagged days | 4 |
| Trades / WR | 73 / 45.2% |
| Long / Short | 37 / 36 |
| Exit mix | {'REVERSE': 73} |
| Fit net / pace | $-1,884 / $-85/mo |
| HO net / pace | $20,084 / $2,052/mo |
| Leave-out (drop ['2025-12', '2026-02']) | $2,899 |
| Ext | UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 1/893 |
| ≤90d continuous | 21/863 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 25/863 (HO-era 10) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 27A@2.50%

None.

### ≤90d continuous pass sample — 27A@2.50%

| start | end | max_mult | min_mult | worst_day |
|---|---|---:|---:|---:|
| 2024-04-03 | 2024-07-01 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-04 | 2024-07-02 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-05 | 2024-07-03 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-06 | 2024-07-04 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-07 | 2024-07-05 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-08 | 2024-07-06 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-09 | 2024-07-07 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-10 | 2024-07-08 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-11 | 2024-07-09 | 1.1587 | 1.0695 | -4.01% |
| 2024-04-12 | 2024-07-10 | 1.1587 | 1.0695 | -4.01% |

## 27B XAG SAR + soft DD governor

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $98,709.55 |
| Max DD | 12.8008% |
| Worst Prague day (floating) | 2026-01-30 (-4.6919%) |
| Worst Prague day (closed-only) | 2024-02-14 (-2.5097%) |
| Floating flagged days | 0 |
| Trades / WR | 73 / 45.2% |
| Long / Short | 37 / 36 |
| Exit mix | {'REVERSE': 73} |
| Gov states | {'full': 22, 'mid': 16, 'floor': 35} |
| Killed Prague days | 0 |
| Soft funnel | {'gov_full': 22, 'gov_mid': 17, 'gov_floor': 35} |
| Fit net / pace | $-7,994 / $-359/mo |
| HO net / pace | $7,406 / $757/mo |
| Leave-out (drop ['2026-02', '2025-12']) | $658 |
| Ext | UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/893 |
| ≤90d continuous | 0/863 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 25/863 (HO-era 10) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 27B+soft

None.

## Sensitivity @2.60% (NOT verdict)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $117,891.92 |
| Max DD | 21.9350% |
| Worst Prague day (floating) | 2026-01-30 (-11.4565%) |
| Worst Prague day (closed-only) | 2024-02-14 (-2.6335%) |
| Floating flagged days | 5 |
| Trades / WR | 73 / 45.2% |
| Long / Short | 37 / 36 |
| Exit mix | {'REVERSE': 73} |
| Fit net / pace | $-2,502 / $-112/mo |
| HO net / pace | $21,272 / $2,173/mo |
| Leave-out (drop ['2025-12', '2026-02']) | $3,063 |
| Ext | UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 1/893 |
| ≤90d continuous | 38/863 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 25/863 (HO-era 10) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — sens@2.60%

None.

### ≤90d continuous pass sample — sens@2.60%

| start | end | max_mult | min_mult | worst_day |
|---|---|---:|---:|---:|
| 2024-03-06 | 2024-06-03 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-07 | 2024-06-04 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-08 | 2024-06-05 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-09 | 2024-06-06 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-10 | 2024-06-07 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-11 | 2024-06-08 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-12 | 2024-06-09 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-13 | 2024-06-10 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-14 | 2024-06-11 | 1.1580 | 1.0139 | -4.11% |
| 2024-03-15 | 2024-06-12 | 1.1580 | 1.0139 | -4.11% |

## Funnel (SAR generation)

```
{
  "seed_long": false,
  "reversals": 74,
  "continued": 757,
  "skipped_nonpositive_stop": 0
}
```

## Does XAG Wilder SAR open a ~3mo path?

**No cleared ACCEPT.** Official primary verdict **REJECT**; soft-gov **REJECT**. Keep iterating under broad mandate; do not retune this locked rule.

Nothing live.
