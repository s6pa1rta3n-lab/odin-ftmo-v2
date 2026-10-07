# Candidate 26 — GER40 three-close momentum results

- Measured: 2026-10-07 12:22 EDT
- Data sha256: `f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d`
- Spec sha256: `cc292d122c22b9dca72e82944f00a803f8fd4eb10fbdc98f47d53184f3851447`
- Gold entry5 preregister sha256: `6a76bfa6867839b761ff7bf86be104fd533d600925faf306a587a8b37fb48282` (mechanics source; not retuned)
- Data end: 2026-09-01 23:59:00+00:00
- Live C4 / drip / FREEZE: **untouched**
- Costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.0 pts, EUR→USD 1:1

## Lead
**REJECT — GER40 three-close does not open a ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows. Best book 26B+soft: legal=False DD=10.45% HO=$-261/mo 90d=0/858 outside=0.

## Summary table

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 26A@2.50% | 2.50% | -603 | 13.0% | 0/858 (0) | 0/864 (0) | 0 | -19,002 | NO | REJECT |
| 26B+soft | SOFT 2.50→1.25→0.75 | -261 | 10.4% | 0/858 (0) | 0/864 (0) | 0 | -6,354 | NO | REJECT |
| sens@2.60% | 2.60% sens | -633 | 13.6% | 0/858 (0) | 0/864 (0) | 0 | -19,831 | NO | REJECT |

## 26A GER40 three-close @2.50% (primary)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $99,853.02 |
| Max DD | 13.0404% |
| Worst Prague day | 2024-03-09 (-2.5217%) |
| Trades / WR | 99 / 48.5% |
| Long / Short | 61 / 38 |
| Exit mix | {'TIME': 72, 'SL': 23, 'TP': 4} |
| Fit net / pace | $5,761 / $259/mo |
| HO net / pace | $-5,908 / $-603/mo |
| Leave-out (drop ['2026-01', '2026-04']) | $-19,002 |
| Ext | UNAVAILABLE (GER40 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/888 |
| ≤90d continuous | 0/858 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/864 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 26A@2.50%

None.

## 26B GER40 three-close + soft DD governor

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $98,311.11 |
| Max DD | 10.4464% |
| Worst Prague day | 2024-03-09 (-2.5217%) |
| Trades / WR | 99 / 48.5% |
| Long / Short | 61 / 38 |
| Exit mix | {'TIME': 72, 'SL': 23, 'TP': 4} |
| Gov states | {'full': 34, 'mid': 21, 'floor': 44} |
| Killed Prague days | 0 |
| Soft funnel | {'gov_full': 34, 'gov_mid': 21, 'gov_floor': 44} |
| Fit net / pace | $865 / $39/mo |
| HO net / pace | $-2,554 / $-261/mo |
| Leave-out (drop ['2026-01', '2026-04']) | $-6,354 |
| Ext | UNAVAILABLE (GER40 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/888 |
| ≤90d continuous | 0/858 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/864 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 26B+soft

None.

## Sensitivity @2.60% (NOT verdict)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $99,726.81 |
| Max DD | 13.5643% |
| Worst Prague day | 2024-03-09 (-2.6224%) |
| Trades / WR | 99 / 48.5% |
| Long / Short | 61 / 38 |
| Exit mix | {'TIME': 72, 'SL': 23, 'TP': 4} |
| Fit net / pace | $5,927 / $266/mo |
| HO net / pace | $-6,200 / $-633/mo |
| Leave-out (drop ['2026-01', '2026-04']) | $-19,831 |
| Ext | UNAVAILABLE (GER40 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/888 |
| ≤90d continuous | 0/858 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/864 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — sens@2.60%

None.

## Funnel (signal generation)

```
{
  "signals": 99,
  "no_next_bar": 1,
  "atr_not_positive": 3,
  "ignored_in_position": 104,
  "no_signal": 369
}
```

## Does GER40 three-close open a ~3mo path?

**No cleared ACCEPT.** Official primary verdict **REJECT**; soft-gov **REJECT**. Keep iterating under broad mandate; do not retune this locked rule.

Nothing live.
