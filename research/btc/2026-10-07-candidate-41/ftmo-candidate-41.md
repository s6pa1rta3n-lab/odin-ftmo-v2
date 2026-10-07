# FTMO Candidate 41 — US100 NR7 @1% + BTC C15 H4 BB squeeze soft joint (no XAG)

Research-only. Locked a-priori joint — **not** a fishing grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.
**Do not include XAG** (C35/C37/C39 stack family closed).

## Thesis

XAG+NR7 stacks (C35 dual-open, C37 tiny satellite, C39 mutex) cannot keep HO ≤90d windows —
XAG's 8 HO windows die whenever a second sleeve shares the equity path.

Pivot to **pace sleeves without XAG**:
- **US100 NR7** (~$1.9k/mo legal DD, 0 HO windows alone — exact Explorer/C31/C35A)
- **BTC C15 H4 BB squeeze** (best BTC DD-legal ~$1.3k/mo @0.75%, Ext weak — exact C15)

Shared soft joint may create HO ≤90d windows neither sleeve has alone.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd: dd&lt;5% → full; 5–8% → mid; ≥8% → floor; never sticky-block.
3. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
4. Max **one position per sleeve** (two max simultaneous if both signal — dual-open allowed).

## Risk shares at full tier (a-priori)

| Sleeve | Full | Mid | Floor |
|---|---:|---:|---:|
| US100 NR7 | **1.00%** | **0.50%** | **0.25%** |
| BTC H4 BB squeeze (C15) | **0.75%** | **0.40%** | **0.20%** |

## Sleeve specs

### Sleeve A — US100 NR7 (exact Explorer / C31 / C35A)
- Daily NR7 (range &lt; prior 6 days min); next-day break of NR high/low; stop = opposite NR extreme; TP 2R; TIME day5
- Costs: spread 1, commission 0, contract 1
- Data: usatechidxusd M1 Dukascopy

### Sleeve B — BTC H4 BB squeeze (exact C15)
- Spec `ftmo-candidate-15.md` / `run_candidate_15.py`
- H4 Bollinger(20,2σ) bandwidth ≤ P10 of prior 100 bw; break = prior bar in squeeze + close outside band
- Stop 1.0×ATR(14) H4; TP R=2; M1 path SL/TP; same-minute both → stop
- Costs: spread 15, commission 0, contract 1
- Data: btcusd M1 main + dukas-ext

## Books

| Book | Description |
|---|---|
| **41A** | US100 soft alone |
| **41B** | BTC C15 soft alone |
| **41C** | joint ungoverened (always full tiers) |
| **41D** | joint + soft gov (**verdict**) |

## ACCEPT gates

Standard HO ≤90d windows in HO/Ext eras. CONDITIONAL if legal DD + windows but leave-out/Ext weak.
No retune. No XAG. No Gold primary. No deploy.

## Deliverables

- `ftmo-candidate-41.md`, `run_candidate_41.py`, results/summary/json
- Pack `2026-10-07-candidate-41/`
- STATUS append; `GITHUB-PR-BODY-C41.md`
- PR `research/btc/2026-10-07-candidate-41/` on `s6pa1rta3n-lab/odin-ftmo-v2`
