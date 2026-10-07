# BTC FTMO research baseline (2026-10-07)

**Status: C40 GER40 Keltner55 — REJECT** — **NO — GER40 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

_Prior:_ preserved below (C39 / C38 / C37 / …).

## Candidate 40

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---|---:|---|---|
| 40A | 2.50% OFF | -724 | 13.8% | 0/857 (0) | 0/857 (0) | N/A | -11,033 | NO | REJECT |
| 40B | SOFT 2.50→1.25→0.75 | -399 | 9.8% | 0/857 (0) | 0/857 (0) | N/A | -4,879 | YES | REJECT |

## Candidate 39

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 39A | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | CONDITIONAL |
| 39B | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | REJECT |
| 39C | JOINT-MUTEX | SOFT | 2,554 | 8.0% | 100/838 (0) | 60/838 (0) | N/A | 6,131 | YES | REJECT |

**XAG window survival:** 39A HO≤90d=8 → 39C mutex HO≤90d=0 (seq HO 0→0) | windows_survived=N

## Candidate 38

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 38A@2.50% | 2.50% OFF | -1,618 | 20.7% | 0/884 (0) | 0/872 (0) | 0 | -22,269 | NO | REJECT |
| 38B+soft | SOFT 2.50→1.25→0.75 | -557 | 11.4% | 0/884 (0) | 0/872 (0) | 0 | -7,322 | NO | REJECT |
| sens@2.60% | 2.60% sens (NOT verdict) | -1,679 | 21.4% | 0/884 (0) | 0/872 (0) | 0 | -23,096 | NO | REJECT |

## Candidate 37

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 37A | XAG | SOFT-XAG | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | CONDITIONAL |
| 37B | US100 | FIXED0.25 | 385 | 0.3% | 0/732 (0) | 0/732 (0) | N/A | 2,142 | YES | REJECT |
| 37C | JOINT | SOFT-XAG+FIX | 1,186 | 7.7% | 100/838 (0) | 60/838 (0) | N/A | -6,569 | YES | REJECT |

**XAG window survival:** 37A HO≤90d=8 → 37C joint HO≤90d=0 (seq HO 0→0) | windows_survived=N

**Leave-out vs 37A:** 37A leave-out $-6,976 → 37C leave-out $-6,569 (delta $407)

## Candidate 36

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 36A | AUS200 | OFF | -630 | 27.1% | 0/844 (0) | 0/844 (0) | N/A | -12,189 | NO | REJECT |
| 36B | AUS200 | SOFT | -208 | 14.0% | 0/844 (0) | 0/844 (0) | N/A | -4,061 | NO | REJECT |

## Candidate 35

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 35A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | REJECT |
| 35B | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | CONDITIONAL |
| 35C | JOINT | OFF | 3,372 | 7.1% | 120/838 (0) | 68/838 (0) | N/A | 8,793 | YES | CONDITIONAL |
| 35D | JOINT | SOFT | 3,011 | 6.6% | 107/838 (0) | 68/838 (0) | N/A | 5,783 | YES | CONDITIONAL |

**XAG window survival:** 35B HO≤90d=8 → 35D joint HO≤90d=0 (seq HO 0→0)

## Candidate 34

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 34A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | REJECT |
| 34B | USA30 | SOFT | -272 | 9.2% | 0/836 (0) | 0/836 (0) | N/A | -3,856 | YES | REJECT |
| 34C | JOINT | OFF | 972 | 8.9% | 0/836 (0) | 0/836 (0) | N/A | -2,658 | YES | REJECT |
| 34D | JOINT | SOFT | 675 | 7.4% | 0/836 (0) | 0/836 (0) | N/A | -1,517 | YES | REJECT |

## Candidate 33

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|
| 33A | AUDUSD | OFF | -237 | 30.8% | 0/841 (0) | 0/840 (0) | N/A | -5,438 | NO | REJECT |
| 33A | AUDUSD | SOFT | -77 | 16.3% | 0/841 (0) | 0/840 (0) | N/A | -1,887 | NO | REJECT |
| 33B | USDCAD | OFF | 421 | 24.8% | 0/850 (0) | 0/850 (0) | N/A | -6,460 | NO | REJECT |
| 33B | USDCAD | SOFT | 139 | 13.3% | 0/850 (0) | 0/850 (0) | N/A | -1,939 | NO | REJECT |
| 33C | JOINT | OFF | 312 | 20.9% | 0/840 (0) | 0/840 (0) | N/A | -2,338 | NO | REJECT |
| 33C | JOINT | SOFT | 101 | 11.4% | 0/840 (0) | 0/840 (0) | N/A | -749 | NO | REJECT |

## Live
Catalogue drip / C4 ops: **untouched**. Nothing from C40 arms without Odin approval. Gold not packaged.
