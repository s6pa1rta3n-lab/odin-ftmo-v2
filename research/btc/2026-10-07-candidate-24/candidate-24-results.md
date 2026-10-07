# Candidate 24 — XAG three-close momentum results

- Measured: 2026-10-07 12:16 EDT
- Data sha256: `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c`
- Spec sha256: `f4b5e61fbce1cecbf6ef83d9110ca378a074ee03dbe8b080f2d03d69ebc6a336`
- Gold entry5 preregister sha256: `6a76bfa6867839b761ff7bf86be104fd533d600925faf306a587a8b37fb48282` (mechanics source; not retuned)
- Data end: 2026-09-01 23:59:00+00:00
- Live C4 / drip / FREEZE: **untouched**
- Costs ASSUMPTION: contract 5000, spread 0.025, commission $3/lot (C19 parity)

## Lead
**REJECT — XAG three-close does not open a ~3mo path.** legal=False DD=10.89% HO=$1,648/mo 90d=0/859 outside=0.

## Official book @ 2.50%

| Metric | Value |
|---|---|
| Decision | **REJECT** |
| Legal (DD≤10%, no day≤−5%) | False |
| Final equity | $116,030.72 |
| Max DD | 10.8924% |
| Worst Prague day | 2026-06-14 (-2.6912%) |
| Trades / WR | 89 / 51.7% |
| Long / Short | 59 / 30 |
| Exit mix | {'SL': 15, 'TIME': 69, 'TP': 4, 'SL_OPEN': 1} |
| Fit net / pace | $-102 / $-5/mo |
| HO net / pace | $16,132 / $1,648/mo |
| Leave-out (drop ['2026-01', '2025-12']) | $4,419 |
| Ext | UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) ($0) |
| ≤60d continuous | 0/889 |
| ≤90d continuous | 0/859 (HO-era starts 0) |
| seq90 Challenge→Verify reset | 0/861 (HO-era 0) |
| Explorer countable (real ∩ TIME-zero) | 0/30 (outside streak 0) |
| Explorer price-path passes | 0/30 |

### Explorer countable windows @ 2.50%

None.

## Sensitivity readout @ 2.60% (NOT official verdict)

| Metric | Value |
|---|---|
| Decision (informational) | REJECT |
| Legal | False |
| Final equity | $116,717.00 |
| Max DD | 11.2568% |
| Worst day | 2026-06-14 (-2.9708%) |
| HO pace | $1,718/mo |
| Leave-out | $4,491 |
| ≤90d (HO-era) | 0/859 (0) |
| seq90 (HO-era) | 0/861 (0) |
| Explorer countable / outside | 0/30 / 0 |

## Funnel

```
{
  "signals": 89,
  "no_next_bar": 0,
  "atr_not_positive": 1,
  "ignored_in_position": 79,
  "no_signal": 417
}
```

## Does XAG three-close open a ~3mo path?

**No cleared ACCEPT.** Official verdict **REJECT**. Keep iterating under broad mandate; do not retune this locked rule.

Nothing live.
