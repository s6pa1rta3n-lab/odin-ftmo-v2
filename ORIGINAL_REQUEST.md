# Original User Request

## Initial Request — 2026-08-31T22:22:39-04:00

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Scan live global markets (Crypto, Forex, Commodities, Indices) for high-probability, highly asymmetric "explosive" swing trade setups. Once a setup is identified, deploy a Python script on the existing trading VM to execute a 0.01 micro-lot trade on the FTMO account to track the setup with zero risk.

Working directory: `/home/solveetcoagula/odin_ftmo/` (on the remote VM)
Integrity mode: development

## Requirements

### R1. Market Scanning & Analysis
The team must scan current market conditions across major asset classes to identify at least one highly asymmetric setup poised for explosive directional movement. The thesis, entry, stop loss, and take profit must be clearly defined. The team may use any approach (technical, fundamental, or a combination) they deem best.

### R2. Context & Infrastructure Integration
The team must execute all work on the remote GCP VM (`matt-berserker`). You must connect to the VM using `gcloud compute ssh matt-berserker --zone=us-central1-a --project=project-45c3b27c-b597-4704-a50 --account=reemanos8422@gmail.com`. You must utilize the existing MetaApi credentials located at `/home/solveetcoagula/odin_ftmo/config_us100.json`.

### R3. Micro-Lot Execution Script
The team must write and deploy an isolated Python script on the VM that executes the identified setup. You should reference the existing US Open and London Reversal scripts in the directory for execution logic and credential handling. 
**CRITICAL LIMITATION**: The script MUST hardcode the execution volume to a `0.01` micro-lot to ensure this is purely a zero-risk tracking trade.

## Acceptance Criteria

### Execution & Verification
- [ ] A written thesis is provided detailing the chosen asset, the technical/fundamental setup, and the exact entry/SL/TP parameters.
- [ ] A Python script is deployed on the VM that successfully connects to MetaApi using the existing config.
- [ ] The script successfully places a live 0.01 micro-lot trade (or pending order) on the FTMO account, and the agent verifies the order ID was created on the broker.

## Follow-up — 2026-09-09T18:12:56Z

Rebuild two automated FTMO prop trading engines into config-driven, modular systems. Each engine has 5 design dimensions x 7 options per dimension. Backtest all profile combinations across multiple instruments and time windows. Deploy the empirical winners to a live MetaApi trading account. This is a production system managing real capital under strict drawdown constraints.

Working directory: /Users/solveetcoagula/Desktop/google_cloud
Integrity mode: benchmark

## Critical Context

### Account State
- FTMO Verification account at $94,939.28 (5.06% drawdown from $100K start)
- Absolute floor: $90,000 (10% max loss). Remaining margin: $4,939
- Profit target: $110,000 (need 15.87% return)
- Daily loss limit: 5% of equity (mark-to-market, split-second breach = violation)
- Deadline: ~30 days

### Existing Infrastructure (Already Built)
The following components are complete and tested. Do NOT rebuild them — extend and use them:

1. **Backtesting engine** (`backtester/engine.py`) — 850-line Python module implementing all 5 design dimensions for both engines. Smoke-tested on US100 data. Handles candle loading, ATR calculation, range detection, 7 risk sizing models, 7 entry modes per engine, 7 pyramiding models, 7 exit models, 7+ market filters, position tracking, and tournament scoring.

2. **Tournament runner** (`backtester/tournament.py`) — Generates all profile combinations, runs backtests in parallel (ProcessPoolExecutor), supports multi-window testing (6-month, 1-year, 2.5-year), outputs CSV/JSON ranked results.

3. **Dukascopy downloader** (`data/downloaders/dukascopy.py`) — Downloads 1-minute OHLCV data from Dukascopy for forex/commodities. Async with retry logic.

4. **MetaApi data puller** (`data/downloaders/metaapi_pull.py`) — Pulls 1-minute candles from MetaApi REST API for indices/crypto. Supports resumption.

5. **FTMO asset specs** (`data/ftmo_asset_specs.json`) — Commission structures, tick values, contract sizes, and trading rules for 25 instruments across 4 asset classes.

6. **GitHub repo** — `s6pa1rta3n-lab/odin-ftmo-v2` with parent tracking issue #1 and 11 design decision sub-issues already documented.

### Existing Trading Engines (To Be Refactored)
- **London Reversal Engine** (`london_reversal_engine_live.py`, 305 lines) — Asian session range fade strategy. Currently uses blind limit orders at range extremes with fixed 40pt SL / 20pt TP. Single instrument (US100.cash). Runs 07:00-13:00 UTC.
- **Omni Breakout Engine** (`omni_breakout_engine.py`, 791 lines) — US Open Range breakout. Has tranche state machine, VIX filter, trailing stops, EOD liquidation, hive mind state sync. Runs 14:00-20:00 UTC.
- Both engines use `MetaApiWrapper` for order execution via MetaApi cloud SDK.

### VM Access
Commands on the trading VM must be run via:
```
gcloud compute ssh matt-berserker --zone=us-central1-a --project=project-45c3b27c-b597-4704-a50 --account=reemanos8422@gmail.com --command="<CMD>"
```
Working directory on VM: `/home/solveetcoagula/odin_ftmo/`

### Mandatory Build Process Documentation
**All agents MUST document blockers, errors, debugging cycles, and design decisions as GitHub sub-issues on parent issue #1** in repo `s6pa1rta3n-lab/odin-ftmo-v2`, using `issue_write` (method: "create", owner: "s6pa1rta3n-lab", repo: "odin-ftmo-v2") then `sub_issue_write` (method: "add") to link. Use the issue **ID** (not number) as `sub_issue_id`. Labels: `["build-log", "blocker"]` for errors, `["build-log", "decision"]` for design decisions.

Sub-issue template:
```
## What Was Attempted
{description}
## What Failed
{description}
## Root Cause
{analysis}
## Resolution
- **Status**: {Resolved / Workaround / Unresolved}
- **Fix**: {description}
- **Lessons**: {takeaways}
---
*Parent: #1*
```

## Requirements

### R1. Data Pipeline Execution
Download 2.5 years of 1-minute OHLCV data for all target instruments using the existing download scripts. Validate downloaded data for gaps, duplicates, and timestamp continuity.

Target instruments:
- **Indices** (MetaApi): US100.cash, US30.cash, US500.cash, GER40.cash, UK100.cash, JPN225.cash, FRA40.cash, AUS200.cash, EU50.cash
- **Forex** (Dukascopy): EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, EURGBP, EURJPY, GBPJPY
- **Commodities** (Dukascopy): XAUUSD, XAGUSD
- **Crypto** (MetaApi): BTCUSD, ETHUSD

Date range: 2024-01-01 to 2026-09-09. Output: CSV files in `data/raw/`.

### R2. Engine Refactors
Refactor both trading engines from hardcoded parameters to config-driven architecture. Each engine must support runtime profile switching across 5 dimensions:

1. **Risk Sizing** (7 models): Conservative Ramp, Fixed Low, Aggressive Flat, Kelly Criterion, Anti-Martingale, Volatility-Scaled, Equity Curve
2. **Entry Modes** (7 per engine): London has range-fade variants; Omni has breakout variants. See `backtester/engine.py` for the full taxonomy.
3. **Pyramiding** (7 models): No Pyramid, Equal Split, Front-Loaded, Inverse Pyramid, Momentum-Confirmed, Risk-Free Runner, Adaptive Tranche
4. **Exit Models** (7 models): Fixed SL/TP, Fixed SL + Trail, ATR Dynamic Trail, Breakeven Runner, Time-Based, Chandelier, Multi-Target Cascade
5. **Market Filters** (7 per engine, independently toggleable)

Each engine loads a JSON profile at startup and dispatches to the correct module for each dimension. The MetaApiWrapper, order execution, account connection, and data collection code must be preserved.

### R3. Formal Verification Pipeline
Build a three-layer config validation pipeline: JSON profiles -> OCaml formal verifier -> Python runtime validator.

The OCaml verifier must prove that no profile combination can violate FTMO constraints (5% daily loss, 10% total loss). It must reject incompatible module combinations and model worst-case drawdown under adversarial market conditions.

A Haskell QuickCheck fuzzer must property-test the OCaml model with 10,000+ random profiles.

The formal verification components run locally (not on the VM). The Python validator runs at engine startup on the VM.

### R4. Backtesting Tournament
Run the existing tournament runner (`backtester/tournament.py`) across all profile combinations for both engines, all instruments, and three time windows (6-month, 1-year, 2.5-year).

Tournament scoring: Sharpe (40%), Max Drawdown (30%), Profit Factor (20%), Trade Count (10%).

Output: Ranked CSV/JSON results. Top 10 profiles per engine for paper trading.

### R5. Paper Trade and Deployment
Paper trade the top 10 London Reversal profiles for 48 hours on the live MetaApi account in observation-only mode. Deploy the winner. Repeat for Omni Breakout.

After both engines are deployed, run cross-engine correlation analysis to verify the two engines don't amplify each other's losses.

Deployment target: systemd services on the `matt-berserker` VM.

## Acceptance Criteria

### Code Quality
- [ ] Both refactored engines load JSON profiles and dispatch to correct modules for all 5 dimensions
- [ ] All 7 entry modes for each engine produce trades in backtesting (no dead code paths)
- [ ] All 7 risk sizing models produce different lot sizes given the same equity/SL
- [ ] All 7 exit models produce different exit behavior in backtesting
- [ ] Unit tests pass for every module (risk sizing, entry, pyramiding, exit, filters)
- [ ] MetaApiWrapper integration is preserved — existing order execution flow unchanged

### Formal Verification
- [ ] OCaml verifier compiles and passes `dune test`
- [ ] No profile combination passes the verifier AND violates FTMO constraints in backtesting
- [ ] Haskell QuickCheck runs 10,000 random profiles with zero property violations
- [ ] Python validator catches all profiles rejected by the OCaml verifier

### Backtesting Tournament
- [ ] Tournament runs to completion for at least US100.cash across all three time windows
- [ ] Top 10 profiles have positive Sharpe ratio across all three time windows
- [ ] Top 10 profiles have max drawdown below 8% (leaving 2% safety margin from FTMO's 10% limit)
- [ ] Results CSV/JSON files are written to `backtester/results/`

### Deployment
- [ ] Paper trade logs show signal generation for at least 5 trading sessions
- [ ] Deployed engines start without errors from systemd service files
- [ ] No FTMO constraint violations during paper trading or live deployment

### Mandatory Documentation
- [ ] Every blocker encountered is documented as a GitHub sub-issue on #1 with the required template
- [ ] Every design decision is documented as a GitHub sub-issue on #1

### Red-Team Audit
- [ ] An independent auditor agent verifies that no test assertions were weakened, commented out, or bypassed
- [ ] The auditor confirms that the OCaml verifier uses real constraint checking (not mocked proofs)
- [ ] The auditor confirms that backtest results are reproducible (same profile + same data = same metrics)
- [ ] The auditor confirms that the deployed engines enforce authorization (MetaApi token validation, account ID matching)

## Follow-up — 2026-09-09T19:15:34Z

Updated requirement from the user: Paper trading (R5) must run for a minimum of **72 hours (3 days)**, not 48 hours as originally specified. This applies to both London Reversal and Omni Breakout top 10 profiles. Do NOT deploy any winning profile to live trading until it has completed at least 72 hours of paper trading with passing metrics. Relay this constraint to the orchestrator and any M5 workers.
