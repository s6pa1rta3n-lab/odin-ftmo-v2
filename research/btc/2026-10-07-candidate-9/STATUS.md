# BTC FTMO research baseline (2026-10-07)

**Status: C9 CONDITIONAL** — Gate A PASS (trail runner); Gate B FAIL on **DD** (1% → 65/252 ≤60d windows but DD 18.5%; 0.5% DD OK but 0 windows). C8 REJECT (edge). C5 still research ACCEPT @ 0.01 (slow). C6/C7 REJECT. C4 still armed/ops path. Do not deploy C5–C9.

## Candidate 9 (new measurement)
C5 entry + BE at +1R + ATR(14)×k=1.0 trail + emergency +5R. Cost: C4/C5 0.065%+swap.

**CONDITIONAL:** HO @0.01 **+$6,444** (~$660/mo); fit **−$830**; leave-out +$286; ext +$1,625; WR 11.6% (19× +5R winners). @1% risk: 65/252 ≤60d windows but max DD **18.5%**. @0.5%: DD 7.4%, **0/252** windows. ATR≫stop → trail never left BE (exits: init-stop / BE / +5R only).

## Candidate 8
Hard R=2 → REJECT (HO −$6.8k; edge).

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
