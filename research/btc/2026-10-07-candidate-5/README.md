# Candidate 5 research pack — 2026-10-07

**Decision: ACCEPT** (research only — do **not** deploy / re-arm / touch live VM)

## One-line thesis

SMA50 exclusive dual R=1 + slope confirm (rising long / falling short) + skip elevated vol (ATR ≥ P75 of prior 100d) — clear fit ≥ −$5k without C4b-A’s leave-out/ext kill.

## Clearly better than C4?

**YES** — clears all **6/6** gates; C4 was 5/6 (failed fit −$8,949). Tradeoff: HO/ext/leave-out dollars are lower than C4 but still pass.

## Gate table

| Gate | C4 | C5 |
|---|---|---|
| 1 Holdout >0 & > buy-only | YES $7,158.94 | YES $4,790.18 |
| 2 Extension ≥0 | YES $786.15 | YES $385.76 |
| 3 Leave-out two best >0 | YES $2,251.35 | YES $707.31 |
| 4 Worst day ≥ −2000 | YES −825.82 | YES −825.82 |
| 5 Fit ≥ −5000 | **NO** −8,949.23 | **YES** −3,213.88 |
| 6 HO months ≥50% green | YES 8/11 | YES 7/11 |

## Files in this folder

| File | Role |
|---|---|
| `ftmo-candidate-5.md` | Spec + labeled ASSUMPTIONS |
| `candidate-5-results.md` | Full measurement + gate checklist |
| `run_candidate_5.py` | Reproducible runner (research only) |
| `STATUS.md` | Baseline pointer |
| `candidate-4-results.md` / `candidate-4b-fit-fix.md` | Prior context |
| `GITHUB-PR-BODY.md` | Draft PR title/body for Ops |

## Source paths on box

- Spec: `/workspace/btc-strategies/ftmo-candidate-5.md`
- Results: `/workspace/btc-strategies/candidate-5-results.md`
- Runner: `/workspace/btc-strategies/run_candidate_5.py`
- This pack: `/workspace/btc-strategies/2026-10-07-candidate-5/`

## Ops notes

- C4 live path stays as-is (`FREEZE_NEW_BUYS` / nightly arm). This pack does **not** change engines.
- Nothing goes live until Odin/Ops explicitly approve a separate deploy.
- Diagnostic E-only inside results matches C4b-E (fit −$6,693) — V75 is what cleared fit.

Measured: 2026-10-07 ~08:49 ET.

## GitHub

Draft PR: https://github.com/s6pa1rta3n-lab/odin-ftmo-v2/pull/37
Branch: `research/btc-candidate-5-2026-10-07`
