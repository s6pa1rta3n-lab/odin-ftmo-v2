## Candidate 20 — Drawdown governor on window-capable books (research)

**CONDITIONAL (thin) — BTC H4-BREAK-6 channel + governor is the only legal ≤90d path:** max DD **8.0%**, ≤90d cont **77/916**, seq **13/536**. BUT **HO net = $0** and **Ext = $0** — governor sticky-blocked after Fit; all counted windows sit in Fit (2024). XAG Donchian+gov kills every window. C17 R15+gov: legal DD, still 0 windows. **Not ACCEPT. Not deployable as a live 1–3mo start.**

Locked a-priori governor (5% soft cut / 8% hard block until dd<5%). Not a post-hoc grid.
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Ungoverened vs governed

| Book | Gov | HO $/mo | Max DD | ≤90d | seq90 | Legal | Decision |
|---|---|---:|---:|---:|---:|---|---|
| 20A XAG Donchian 2.50% TP1R | OFF | 867 | 12.4% | 77/838 | 60/838 | NO | REJECT |
| 20A XAG Donchian | ON | 0 | 8.5% | 0/827 | 0/322 | YES | REJECT |
| 20B BTC H4-BREAK-6 channel @1.00% | OFF | 2070 | 13.8% | 129/917 | 13/917 | NO | REJECT |
| 20B BTC channel | ON | 0 | 8.0% | 77/916 | 13/536 | YES | CONDITIONAL |
| 20C BTC H4-BREAK-6 R15 @0.75% (C17) | OFF | 669 | 12.0% | 0/917 | 0/917 | NO | REJECT |
| 20C BTC R15 | ON | 0 | 8.2% | 0/917 | 0/155 | YES | REJECT |

### Takeaway
Governor **does** pull illegal window-capable books under 10% DD. Only BTC channel keeps countable ≤90d windows after governing — but sticky block zeros HO/Ext, so windows are Fit-era only. **Not ACCEPT. Do not deploy.**

### Files
- `research/btc/2026-10-07-candidate-20/`
- `run_candidate_20.py`, `ftmo-candidate-20.md`, `candidate-20-results.md`, `STATUS.md`

### Live
Research only — do not deploy. C4/drip untouched.
