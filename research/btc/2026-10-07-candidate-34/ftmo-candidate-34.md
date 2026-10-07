# FTMO Candidate 34 — Joint US100 NR7 @1% + USA30 Keltner55 @2.50% (Explorer USA30 fallback)

Research-only. Locked a-priori — **not** a fishing grid. **Do not retune C31.**
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis (from Strategy Explorer near-miss)

C31 **US100 NR7@1% + JPN225 Keltner55@2.50%** was DD-legal with HO ~$2.9k/mo but **0** ≤90d HO windows (Explorer outside best +14.85%, TIME-zero 0). Explorer originally suggested **USA30 Keltner** as fallback for the Gold-Keltner replacement. Measure **US100 NR7@1% + USA30 Keltner55@2.50%** joint.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd: dd&lt;5% → full sleeve risks; 5–8% → half; ≥8% → quarter; never sticky-block.
3. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
4. Max **one position per sleeve** (two max simultaneous if both signal).

## Risk shares at full tier (a-priori)

| Sleeve | Full | Mid (half) | Floor (quarter) |
|---|---:|---:|---:|
| US100 NR7 | **1.00%** | **0.50%** | **0.25%** |
| USA30 Keltner55 | **2.50%** | **1.25%** | **0.625%** |

## Books (diagnostics + verdict)

| Book | Contents |
|---|---|
| **34A** | US100 NR7 alone @1% (soft gov still applied as sleeve-only) |
| **34B** | USA30 Keltner alone @2.50% soft |
| **34C** | Joint ungoverened (full risks always) — diagnostic |
| **34D** | Joint + soft gov — **verdict book** |

## Chassis (exact reuse — no retune)

### Sleeve A — US100 NR7 @1.00% (exact C31A / Explorer)

- Spec: `/workspace/strategy-explorer/us100-nr7-preregister-2026-10-07.md`
- Daily NR7; next-day break of NR high/low; stop opposite NR side; TP 2R; TIME day5
- Costs: spread **1**, commission **0**, contract **1**, tick **1**
- Data: `usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha `5d833b20…d3af`

### Sleeve B — USA30 Keltner55 (entry55 mirror)

- Spec mechanics: `/workspace/gold-strategy/entry55-preregister-2026-10-07.md` (swap symbol/data/costs/risk only)
- Daily Mid=EMA20; ATR14; Upper/Lower = Mid ± 1.5×ATR; close cross; next open; stop 2×ATR; TP 2R; TIME day5; both sides
- Risk **2.50%** locked a-priori
- Data: `usa30idxusd-m1-bid-2024-01-01-2026-09-02.csv` sha `968d27f1…746a`
- Costs (C22): contractSize **1**, commission **0**; spread **ASSUMPTION 2.5** pts
- USD-quoted — **no JPY conversion**

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | N/A (index feeds end 2026-09-01) |

## Gates

- **ACCEPT**: max DD ≤10%, worst Prague day &gt; −5% (0 days ≤−5%), HO net &gt;0, leave-out remaining HO &gt;0, Ext≥0 or N/A, AND ≥1 ≤90d Challenge+Ver window with start in HO or Ext.
- **CONDITIONAL**: legal DD + HO/Ext-era windows but leave-out/Ext weak.
- **REJECT** otherwise. No retune after results.

Also report Explorer 30-triplet outside + TIME-zero countable for cross-check (not substitute for HO ≤90d gate).
