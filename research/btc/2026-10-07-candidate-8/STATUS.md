# BTC FTMO research baseline (2026-10-07)

**Status: C8 REJECT as ≤60-day FTMO vehicle** — binding constraint = **edge** (higher R kills WR). C5 still research ACCEPT @ 0.01 (slow); C6/C7 REJECT; C4 still armed/ops path. Do not deploy C5–C8.

## Candidate 8 (new measurement)
Filtered SMA50 dual + catalogue stop 412.91 + **R=2** (diag R=3). Cost model: C4/C5 0.065%+swap.

**REJECT:** HO @0.01 **−$6,770** (~−$694/mo); WR 30.1% (needs >33% for R=2); leave-out −$8,811; fit −$10,253; @1% risk 60d windows **0/252**; max DD 19.07%. R=3 diag also negative HO. vs C1: filters+smaller stop did not rescue higher R.

## Candidate 7
H4 dual R=1 → REJECT (~$508/mo; 0/896 windows; DD 17%).

## Candidate 6
C5 Fast-Scale → REJECT (≤60d needs illegal size).

## Candidate 5
SMA50 + slope E + ATR&lt;P75 R=1 → research ACCEPT @ 0.01; too slow for ≤60d.

## Candidate 4
SMA50 exclusive dual R=1. Fit fail; still the armed ops candidate.

## Live
Live catalogue drip / C4 ops: do not touch from research. Nothing arms from this folder.
