# Candidate 38 — USA30 Wilder Parabolic SAR results

- Measured: 2026-10-07 12:44 EDT
- Data sha256: `968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a`
- Spec sha256: `37bb07b24568436a86848d14ee49e05d3c46c4dd9cd2b12365c66802c8a56c0b`
- Gold entry30 preregister sha256: `29638946222b3801dde3c02f6b9831fb89975630768888200310266f99ed5c43` (mechanics source; not retuned)
- BTC SAR preregister present: `/workspace/strategy-explorer/btc-sar-preregister-2026-10-07.md` (mirror lane; BTC @0.50% FAIL not re-run)
- Data end: 2026-09-01 23:59:00+00:00
- Live C4 / drip / FREEZE: **untouched**
- Costs ASSUMPTION (C22 USA30): contractSize=1, commission=0, spread=2.5 pts
- Worst Prague day uses **floating** mark (BTC SAR construction; USA30 units=lots×1)

## Lead
**REJECT — USA30 Wilder SAR does not open a ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows. Best book 38B+soft: legal=False DD=11.36% HO=$-557/mo 90d=0/884 outside=0.

## Summary table

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 38A@2.50% | 2.50% | -1,618 | 20.7% | 0/884 (0) | 0/872 (0) | 0 | -22,269 | NO | REJECT |
| 38B+soft | SOFT 2.50→1.25→0.75 | -557 | 11.4% | 0/884 (0) | 0/872 (0) | 0 | -7,322 | NO | REJECT |
| sens@2.60% | 2.60% sens | -1,679 | 21.4% | 0/884 (0) | 0/872 (0) | 0 | -23,096 | NO | REJECT |

## 38A USA30 SAR @2.50% (primary)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $91,462.50 |
| Max DD | 20.7110% |
| Worst Prague day (floating) | 2025-04-09 (-6.6185%) |
| Worst Prague day (closed-only) | 2024-11-24 (-2.4562%) |
| Floating flagged days | 2 |
| Trades / WR | 76 / 38.2% |
| Long / Short | 38 / 38 |
| Exit mix | {'REVERSE': 71, 'SL_OPEN': 5} |
| Fit net / pace | $7,305 / $328/mo |
| HO net / pace | $-15,843 / $-1,618/mo |
| Leave-out (drop ['2026-04', '2026-07']) | $-22,269 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/914 |
| ≤90d continuous | 0/884 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/872 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 38A@2.50%

None.

## 38B USA30 SAR + soft DD governor

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $89,229.90 |
| Max DD | 11.3594% |
| Worst Prague day (floating) | 2025-04-09 (-6.5908%) |
| Worst Prague day (closed-only) | 2024-11-24 (-2.4614%) |
| Floating flagged days | 1 |
| Trades / WR | 76 / 38.2% |
| Long / Short | 38 / 38 |
| Exit mix | {'REVERSE': 71, 'SL_OPEN': 5} |
| Gov states | {'full': 23, 'mid': 33, 'floor': 20} |
| Killed Prague days | 0 |
| Soft funnel | {'gov_full': 23, 'gov_mid': 33, 'gov_floor': 21} |
| Fit net / pace | $-5,319 / $-239/mo |
| HO net / pace | $-5,451 / $-557/mo |
| Leave-out (drop ['2026-04', '2026-07']) | $-7,322 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/914 |
| ≤90d continuous | 0/884 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/872 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 38B+soft

None.

## Sensitivity @2.60% (NOT verdict)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, floating day&gt;−5%) | False |
| Final equity | $91,117.70 |
| Max DD | 21.4261% |
| Worst Prague day (floating) | 2025-04-09 (-6.8749%) |
| Worst Prague day (closed-only) | 2024-11-24 (-2.5575%) |
| Floating flagged days | 2 |
| Trades / WR | 76 / 38.2% |
| Long / Short | 38 / 38 |
| Exit mix | {'REVERSE': 71, 'SL_OPEN': 5} |
| Fit net / pace | $7,553 / $340/mo |
| HO net / pace | $-16,436 / $-1,679/mo |
| Leave-out (drop ['2026-04', '2026-07']) | $-23,096 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/914 |
| ≤90d continuous | 0/884 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/872 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — sens@2.60%

None.

## Funnel (SAR generation)

```
{
  "seed_long": true,
  "reversals": 77,
  "continued": 754,
  "skipped_nonpositive_stop": 0
}
```

## Does USA30 Wilder SAR open a ~3mo path?

**No cleared ACCEPT.** Official primary verdict **REJECT**; soft-gov **REJECT**. Keep iterating under broad mandate; do not retune this locked rule.

Nothing live.
