# FTMO Candidate 43 — XAG soft PRIMARY + JPN225 fixed low-risk satellite

Research-only. Locked a-priori — **not** a fishing grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.
**No US100 NR7.**

## Thesis (from C42)

C42 soft joint preserved **5/8** XAG HO-era ≤90d windows (unlike XAG+NR7 wipe) but shared soft DD was
**11.1% illegal** and leave-out worse (−$9.2k). Cut JPN to a **fixed** low-risk satellite so shared
max DD ≤10% while testing whether HO windows still survive and leave-out improves vs 43A (−$6,976).

## Soft governor

- **XAG only** uses soft ladder on shared peak DD: dd&lt;5% full; 5–8% mid; ≥8% floor.
- **JPN** is FIXED risk (no soft ladder) on satellite books.
- Prague −3% day kill both sleeves. One pos/sleeve; dual-open OK.

## Books

| Book | Contents |
|---|---|
| **43A** | XAG soft alone 2.50→1.25→0.75 |
| **43B** | JPN FIXED **0.50%** alone |
| **43C** | JOINT XAG soft + JPN FIXED **0.50%** |
| **43D** | JOINT XAG soft + JPN FIXED **0.25%** |
| **43E** | optional: XAG soft 2.00→1.00→0.60 + JPN 0.25% if C/D DD&gt;10% |

## ASSUMPTIONS

- XAG: contract **5000** / spread **0.025** / $3/lot (C19B/C21B)
- JPN225: contract **10** / spread **8.0 ASSUMPTION** / comm 0; JPY→USD via USDJPY mid
- Ext UNAVAILABLE OK (feeds end 2026-09-01)
