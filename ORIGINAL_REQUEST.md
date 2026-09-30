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

## Follow-up — 2026-09-15T14:38:58Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Investigate and definitively solve the "ghost exit" bug on the Odin FTMO v2 trading system. A LONG position on US100.cash was automatically closed exactly 11 seconds after entry via an API market order, but the active Python trading engines did not log any closing action and the user did not manually close it. The team must find the true root cause of this execution and provide a proven resolution.

Working directory: /Users/solveetcoagula/Desktop/google_cloud
Integrity mode: benchmark

## Requirements

### R1. Forensic Root Cause Analysis
Determine exactly what process, script, or cloud mechanism issued the `DEAL_ENTRY_OUT` market order with `ORDER_REASON_EXPERT` at 07:57:15 UTC. Analyze the local mirrored codebase (`MetaApiWrapper.py`, `london_reversal_engine_live.py`, `omni_breakout_engine.py`) and use `gcloud compute ssh` to inspect the VM (`matt-berserker`).

### R2. State Leakage & Concurrency Check
Investigate if there is any state leakage between the Omni Breakout Engine and the London Reversal Engine. Specifically, check if the Omni engine (or any other background process) read the London engine's position and executed a hidden exit, trailing stop, or flatten command that bypassed standard logging.

### R3. Implement Resolution
Once the root cause is mathematically proven, implement the code fix in the trading engines to strictly isolate state by `client_id` or fix the offending logic to prevent cross-talk and unauthorized exits.

## Acceptance Criteria

### Root Cause Verification
- [ ] The root cause explicitly explains how the `positionId` and `comment` string were perfectly carried over to the exit order.
- [ ] The root cause explicitly explains why the Python engines did not output any `PLACING MARKET` or `FLATTENING` logs during the exact second of the exit.

### Fix Verification
- [ ] The engines are refactored to strictly isolate their state management so they never read or modify each other's active trades.
- [ ] Mandatory build process documentation is updated on the GitHub tracking issue (#1) detailing the bug and resolution.

## Follow-up — 2026-09-16T14:58:09Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval.
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Small, focused team

This is a single self-contained fix; keep it small and focused. Fix the MetaApi WebSocket connection stability issues in the `omni_breakout_engine.py` trading script. The script currently suffers from `TimeoutError` and "account is not connected to broker yet" errors that drop the streaming connection and force it into a degraded REST fallback mode.

Working directory: /Users/solveetcoagula/Desktop/google_cloud
Integrity mode: benchmark

## Requirements

### R1. MetaApi Connection Hardening
Analyze the MT5 connection lifecycle in `omni_breakout_engine.py`. The `MetaApiWrapper` is currently experiencing `TimeoutError` on the streaming subscription and falling back to REST mode because the WebSocket upgrade drops or the region settings are mismatched.

### R2. Reconnection & Config Fix
Implement robust reconnection logic, proper `waitSynchronized` handling, and verify/fix the MetaApi region or SDK settings if they are misconfigured for the FTMO broker (the log explicitly mentions SDK region option warnings).

### R3. Deployment & Parity
Deploy the patched engine to the remote VM (`matt-berserker`), restart the `ftmo_hft_omni.service`, and ensure 100% SHA256 parity between the local repository and the VM.

## Acceptance Criteria

### Execution & Telemetry
- [ ] `tail -n 100 /home/solveetcoagula/odin_ftmo/omni_breakout.log` on the VM shows `WebSocket upgrade was successful`.
- [ ] The log shows a continuous stream of live `synchronization` price ticks.
- [ ] The log contains absolutely zero `TimeoutError`, `processingError`, or REST fallback warnings.

### Parity
- [ ] The SHA256 checksum of the local `omni_breakout_engine.py` perfectly matches the checksum of the remote VM file.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*

## Follow-up — 2026-09-16T20:42:57Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Build a new automated trading engine based on "Griff's" strategy (1-hour time frame, no indicators, price-action inside bar breakout, ATR-based position sizing and trailing stops) to trade on a deployed 100k free trial FTMO account via MetaAPI (ID: `45a2565b-4f53-4bd5-8c58-667b3660430f`). Ensure existing 'omni_breakout' and 'london' engines (and their cron jobs) on the VM are permanently disabled, avoid previous deployment issues, and enforce mandatory GitHub build process documentation.

Working directory: /Users/solveetcoagula/Desktop/google_cloud
Integrity mode: development

## Requirements

### R1. Remote Cleanup
SSH into the `matt-berserker` VM and permanently disable the `ftmo_hft_omni` and london-related systemd services, plus any associated cron jobs.

### R2. Live Engine Implementation & Execution
Build `griff_engine_live.py` utilizing Griff's 1-hour inside-bar, ATR-sized breakout strategy (14-period ATR). Position sizing must strictly risk 1% of the current account equity. The team must start the engine and verify it successfully executes live trades on the provided FTMO account.

### R3. Infrastructure, Credentials & Resilience
Utilize the newly hardened, fault-tolerant `MetaApiWrapper.py` (which includes RPC/REST timeout fallbacks) to connect to MetaAPI (ID: `45a2565b-4f53-4bd5-8c58-667b3660430f`). 
If MetaAPI syncing or verification is required, use these credentials:
- Login: `1514655871`
- Master Password: `B4w63?c*3H!e`
- Server: `FTMO-Demo`
This is required to prevent disconnection errors. All `gcloud` commands must be prefixed with `CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity`.

### R4. Mandatory Build Documentation
Strictly follow the `mandatory-build-process-documentation` skill. Initialize a GitHub repo under `s6pa1rta3n-lab` and document all deployment blockers, fixes, and design decisions as real-time sub-issues.

## Acceptance Criteria

### VM Cleanup
- [ ] `systemctl is-active` returns `inactive` for both the omni and london engines on `matt-berserker`.
- [ ] `systemctl is-enabled` returns `disabled` for both services.

### Engine Execution & Live Verification
- [ ] `griff_engine_live.py` successfully connects to MetaAPI (ID: `45a2565b-4f53-4bd5-8c58-667b3660430f`).
- [ ] The engine logs the correct starting FTMO balance (~$100,000) on startup without raising a `TimeoutException`.
- [ ] The engine parses the 1H timeframe correctly and calculates position sizes strictly at 1% risk based on the 14-period ATR.
- [ ] A live trade is successfully routed, executed, and confirmed on the FTMO Demo account by the engine.

### Documentation
- [ ] A new GitHub repository is created under `s6pa1rta3n-lab` with a parent tracking issue.
- [ ] At least one sub-issue (documenting the VM cleanup or a design decision) is correctly linked to the parent tracking issue via `sub_issue_write` using the `id` field.


## 2026-09-21T02:22:25Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Requested team: The full multi-agent teamwork swarm

Investigate and determine the objective root cause of persistent MetaAPI websocket 503 connection errors, request timeouts, and historical candle fetch failures occurring on the GCP VM `matt-berserker` running the Griff Trading Engine. The investigation must be purely empirical with no prior assumptions.

Working directory: `~/teamwork_projects/metaapi_503_rca`
Integrity mode: development

## Requirements

### R1. Analyze System Logs
Gather and analyze raw system logs (`journalctl`), process metrics, and network traffic from `matt-berserker` (zone: us-central1-a, project: project-45c3b27c-b597-4704-a50) to identify the exact onset, frequency, and pattern of the 503 errors across both `griff_engine` and `griff_engine_btc` services. ALWAYS prefix gcloud commands with `CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity`.

### R2. Determine Locus of Failure
Determine conclusively whether the root cause originates from the client side (e.g., rate limiting, aggressive polling, local network configuration, IP blocking) or the server side (e.g., MetaAPI London server outage, broker disconnection). 

### R3. Active Diagnostics Permitted
You may write and run active network diagnostic scripts (e.g., `ping`, `curl`, `tcpdump`) on the VM. You may also temporarily modify the trading engine source code to add verbose debug logging if necessary, provided you revert any changes after the investigation.

### R4. Formal RCA Deliverable
Produce a formal Root Cause Analysis (RCA) document containing detailed evidence, log timelines, diagnostic outputs, and actionable remediation steps.

### R5. Mandatory GitHub Documentation
You MUST strictly follow the `mandatory-build-process-documentation` protocol. Document every blocker, unexpected error, failed approach, diagnostic discovery, and significant decision encountered during the investigation as a GitHub sub-issue in real-time under the `s6pa1rta3n-lab` organization tracking issue. 

## Acceptance Criteria

### Verification Rubric (Agent-as-Judge)
- [ ] An independent reviewer agent can confirm the RCA document contains concrete timestamped log evidence from the VM rather than speculative theories.
- [ ] An independent reviewer agent can confirm the RCA explicitly rules out at least two alternative hypotheses using empirical evidence (e.g., ruling out local network failure via external ping tests).
- [ ] The RCA document includes the exact HTTP/WebSocket response headers or TCP connection states captured during a failure event.
- [ ] Any temporary code modifications made for debugging have been successfully reverted, leaving the trading engine in its original state.
- [ ] An independent reviewer agent can confirm that diagnostic steps, errors, and blockers were successfully logged to GitHub issues using the `issue_write` and `sub_issue_write` tools in real-time.

## 2026-09-21T02:57:53Z

USER INSTRUCTION: The priority is to make sure that we never miss a trading opportunity. Hiding problems (like suppressing 503 logs) won't be helpful if it masks a failure that causes us to miss a trade. Please ensure the RCA remediation prioritizes absolute reliability, potentially recommending a full shard migration (e.g. new-york or singapore) rather than just silencing the logs.
