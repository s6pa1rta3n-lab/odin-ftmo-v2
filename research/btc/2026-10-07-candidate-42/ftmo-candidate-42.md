# FTMO Candidate 42 — XAG Donchian soft + JPN225 Keltner55 soft (no US100 / no Gold)

Research-only. Locked a-priori joint — **not** a fishing grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.
**Do NOT revive XAG+US100 NR7 stacks.**

## Thesis

XAG soft (C21B) is the only sleeve left with HO-era ≤90d windows (**8**) but leave-out FAIL (−$7k).
XAG+NR7 always wiped windows 8→0 (C35/C37/C39). JPN225 Keltner from C31B was ~$484/mo @ 9.3% DD soft,
0 HO windows alone. Joint **without NR7** may (a) keep some XAG HO windows and (b) help leave-out.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd: dd&lt;5% → full; 5–8% → mid; ≥8% → floor; never sticky-block.
3. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
4. Max **one position per sleeve** (two max simultaneous if both signal).

## Risk shares at full tier (a-priori)

| Sleeve | Full | Mid | Floor |
|---|---:|---:|---:|
| XAG Donchian 20d (C21B) | **2.50%** | **1.25%** | **0.75%** |
| JPN225 Keltner55 (C31B) | **2.50%** | **1.25%** | **0.625%** |

## Books

| Book | Description |
|---|---|
| **42A** | XAG soft alone (reconfirm C21B / C39A) |
| **42B** | JPN225 Keltner55 soft alone (reconfirm C31B) |
| **42C** | joint ungoverened |
| **42D** | joint + soft gov (**verdict**) |

## Primary gate

Does joint preserve any HO-era ≤90d windows from XAG (`windows_survived`)?
Also leave-out, max DD ≤10%, worst day &gt; −5%, Ext if available, pace $/mo.

## Explicit exclusions

- No US100 NR7
- No Gold primary
- No live C4 / drip / MetaAPI / deploy
