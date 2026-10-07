# BTC FTMO research baseline (2026-10-07)

**Status: C21 soft DD governor — CONDITIONAL** — **CONDITIONAL (not deployable) — soft DD governor does NOT open a 1–3mo ACCEPT path.** BTC H4 channel soft (1.00→0.50→0.25): max DD **9.6%** legal, HO ~**$310/mo** (sticky was $0), Ext **−$2.6k**, leave-out fail, ≤90d **77/917** but **HO-era 0** (Fit 2024 only) → same Fit-window trap as C20. XAG Donchian soft (2.50→1.25→0.75): DD **9.4%** legal, HO ~**$847/mo**, ≤90d **48/838** with **8 HO-era**, but leave-out remaining HO **negative** → CONDITIONAL, not ACCEPT. Vs C20 sticky: soft restores HO trading; still no deployable pass.

## Candidate 21

| Book | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---|---:|---|---|
| 21B XAG Donchian | OFF | 867 | 12.4% | 77/838 (0) | 60/838 (0) | N/A | −7270 | NO | REJECT |
| 21B XAG Donchian | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | −6976 | YES | CONDITIONAL |
| 21A BTC H4 channel | OFF | 2070 | 13.8% | 129/917 (0) | 13/917 (0) | −3270 | −13567 | NO | REJECT |
| 21A BTC H4 channel | SOFT | 310 | 9.6% | 77/917 (0) | 13/917 (0) | −2586 | −4467 | YES | CONDITIONAL |

## Soft vs C20 sticky

| Book | Soft HO$/mo | Sticky HO$/mo | Soft DD | Sticky DD | Soft ≤90d (HO) | Sticky ≤90d |
|---|---:|---:|---:|---:|---:|---:|
| BTC H4 channel | 310 | 0 | 9.6% | 8.0% | 77/917 (0) | 77/916 |
| XAG Donchian | 847 | 0 | 9.4% | 8.5% | 48/838 (8) | 0/827 |

## Live
Catalogue drip / C4 ops: **untouched**. Nothing from C21 arms without Odin approval. Gold not packaged.
