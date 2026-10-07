# Draft PR — research docs only

**Title:** `research: BTC Candidate 5 ACCEPT (SMA50 slope + ATR P75) — 2026-10-07`

**Base:** `main`  
**Head:** `research/btc-candidate-5-2026-10-07`  
**Repo:** `s6pa1rta3n-lab/odin-ftmo-v2`  
**Draft:** yes  
**Scope:** markdown + research runner under `research/btc/2026-10-07-candidate-5/` only — **no live engine / drip / C4 service changes**

---

## Summary

Research-only Candidate 5 vs C4 gates. **Decision: ACCEPT** (not deployed).

**Thesis:** Keep C4’s SMA50 exclusive dual R=1, add SMA50 slope confirmation (C4b-E), and skip only elevated volatility (prior ATR ≥ 75th percentile of prior 100d ATR) — milder than C4b-A’s median gate that killed leave-out/ext.

## Gate table vs C4

| Gate | C4 | C5 |
|---|---|---|
| Holdout full | $7,158.94 YES | $4,790.18 YES |
| Extension full | $786.15 YES | $385.76 YES |
| Leave-out (drop 2 best HO months) | $2,251.35 YES | $707.31 YES |
| Worst ET day HO & ext | −825.82 YES | −825.82 YES |
| Fit full ≥ −$5,000 | **−$8,949.23 NO** | **−$3,213.88 YES** |
| HO months ≥50% green | 8/11 YES | 7/11 YES |
| **Gates passed** | **5/6** | **6/6 ACCEPT** |

**Clearly better than C4?** YES on gates (fit repaired). HO/ext/leave-out dollars are lower but still pass.

## Paths

- Pack: `research/btc/2026-10-07-candidate-5/`
- Spec: `…/ftmo-candidate-5.md`
- Results: `…/candidate-5-results.md`
- Runner: `…/run_candidate_5.py`
- Box originals: `/workspace/btc-strategies/` (same filenames)

## Explicit non-goals

- No MetaAPI / live VM / systemd / freeze-rearm / catalogue drip edits
- No C4 service file changes
- Deploy requires separate Odin/Ops approval after this research ACCEPT

## Checklist for Ops

- [ ] Read `README.md` + gate table
- [ ] Confirm C4 stays running as-is
- [ ] Do **not** arm C5 from this PR
- [ ] Optional: re-run `python3 run_candidate_5.py` on box with Dukas merge if regenerating numbers
