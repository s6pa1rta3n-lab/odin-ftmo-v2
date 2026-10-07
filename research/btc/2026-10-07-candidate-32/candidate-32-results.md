# Candidate 32 — USA30 three-close momentum results

- Measured: 2026-10-07 12:36 EDT
- Data sha256: `968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a`
- Spec sha256: `0a5e1db0c2bbdf6c74bba0db5f5368f7abd4288aa8bb4104b2b7f529b74b61cf`
- Gold entry5 preregister sha256: `6a76bfa6867839b761ff7bf86be104fd533d600925faf306a587a8b37fb48282` (mechanics source; not retuned)
- Data end: 2026-09-01 23:59:00+00:00
- Live C4 / drip / FREEZE: **untouched**
- Costs ASSUMPTION (C22 USA30): contractSize=1, commission=0, spread=2.5 pts, USD

## Lead
**REJECT — USA30 three-close does not open a ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows. Best book 32A@2.50%: legal=False DD=22.42% HO=$405/mo 90d=0/866 outside=0.

## Summary table

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 32A@2.50% | 2.50% | 405 | 22.4% | 0/866 (0) | 0/868 (0) | 0 | 26 | NO | REJECT |
| 32B+soft | SOFT 2.50→1.25→0.75 | 138 | 12.3% | 0/866 (0) | 0/868 (0) | 0 | 72 | NO | REJECT |
| sens@2.60% | 2.60% sens | 417 | 23.2% | 0/866 (0) | 0/868 (0) | 0 | 20 | NO | REJECT |

## 32A USA30 three-close @2.50% (primary)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $84,869.71 |
| Max DD | 22.4211% |
| Worst Prague day | 2025-03-30 (-2.5132%) |
| Trades / WR | 82 / 45.1% |
| Long / Short | 49 / 33 |
| Exit mix | {'SL': 17, 'TIME': 63, 'TP': 1, 'SL_OPEN': 1} |
| Fit net / pace | $-19,099 / $-859/mo |
| HO net / pace | $3,968 / $405/mo |
| Leave-out (drop ['2026-08', '2026-07']) | $26 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/896 |
| ≤90d continuous | 0/866 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/868 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 32A@2.50%

None.

## 32B USA30 three-close + soft DD governor

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $90,087.62 |
| Max DD | 12.3218% |
| Worst Prague day | 2024-02-14 (-2.5120%) |
| Trades / WR | 82 / 45.1% |
| Long / Short | 49 / 33 |
| Exit mix | {'SL': 17, 'TIME': 63, 'TP': 1, 'SL_OPEN': 1} |
| Gov states | {'full': 5, 'mid': 19, 'floor': 58} |
| Killed Prague days | 0 |
| Soft funnel | {'gov_full': 5, 'gov_mid': 19, 'gov_floor': 58} |
| Fit net / pace | $-11,264 / $-506/mo |
| HO net / pace | $1,352 / $138/mo |
| Leave-out (drop ['2026-08', '2026-07']) | $72 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/896 |
| ≤90d continuous | 0/866 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/868 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — 32B+soft

None.

## Sensitivity @2.60% (NOT verdict)

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $84,296.47 |
| Max DD | 23.2177% |
| Worst Prague day | 2024-01-20 (-2.6133%) |
| Trades / WR | 82 / 45.1% |
| Long / Short | 49 / 33 |
| Exit mix | {'SL': 17, 'TIME': 63, 'TP': 1, 'SL_OPEN': 1} |
| Fit net / pace | $-19,790 / $-890/mo |
| HO net / pace | $4,087 / $417/mo |
| Leave-out (drop ['2026-08', '2026-07']) | $20 |
| Ext | UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/896 |
| ≤90d continuous | 0/866 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/868 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows — sens@2.60%

None.

## Funnel (signal generation)

```
{
  "signals": 83,
  "no_next_bar": 0,
  "atr_not_positive": 2,
  "ignored_in_position": 105,
  "no_signal": 449
}
```

## Does USA30 three-close open a ~3mo path?

**No cleared ACCEPT.** Official primary verdict **REJECT**; soft-gov **REJECT**. Keep iterating under broad mandate; do not retune this locked rule.

Nothing live.
