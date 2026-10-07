## Candidate 21 — Soft DD governor on BTC H4-BREAK-6 channel (research)

**CONDITIONAL (not deployable) — soft DD governor does NOT open a 1–3mo ACCEPT path.** BTC H4 channel soft (1.00→0.50→0.25): max DD **9.6%** legal, HO ~**$310/mo** (sticky was $0), Ext **−$2.6k**, leave-out fail, ≤90d **77/917** but **HO-era 0** (Fit 2024 only) → same Fit-window trap as C20. XAG Donchian soft (2.50→1.25→0.75): DD **9.4%** legal, HO ~**$847/mo**, ≤90d **48/838** with **8 HO-era**, but leave-out remaining HO **negative** → CONDITIONAL, not ACCEPT. Vs C20 sticky: soft restores HO trading; still no deployable pass.

Locked a-priori soft governor (<5% full / 5–8% mid / ≥8% floor; never sticky-block).
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Gov | HO $/mo | Max DD | ≤90d (HO-era) | Ext | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---|---:|---|---|
| 21B XAG Donchian 2.50% TP1R | OFF | 867 | 12.4% | 77/838 (0) | N/A | −7270 | NO | REJECT |
| 21B XAG soft 2.50→1.25→0.75 | SOFT | 847 | 9.4% | 48/838 (8) | N/A | −6976 | YES | CONDITIONAL |
| 21A BTC H4-BREAK-6 channel @1.00% | OFF | 2070 | 13.8% | 129/917 (0) | −3270 | −13567 | NO | REJECT |
| 21A BTC soft 1.00→0.50→0.25 | SOFT | 310 | 9.6% | 77/917 (0) | −2586 | −4467 | YES | CONDITIONAL |

### Soft vs C20 sticky
Soft restores HO trading (BTC $310 vs sticky $0; XAG $847 vs $0) and keeps DD legal. BTC HO-era windows still **0**. XAG gets 8 HO-era continuous windows but leave-out fails. **Not ACCEPT. Do not deploy.**

### Files
- `research/btc/2026-10-07-candidate-21/`
- `run_candidate_21.py`, `ftmo-candidate-21.md`, `candidate-21-results.md`, `STATUS.md`

### Live
Research only — do not deploy. C4/drip untouched.
