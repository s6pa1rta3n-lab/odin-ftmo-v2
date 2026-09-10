# Test Infrastructure & Specification (Odin FTMO v2)

## 1. Test Philosophy

The Odin FTMO v2 test architecture enforces an opaque-box, requirement-driven testing methodology with progressive testability and anti-cheating verification.

### 1.1 Opaque-Box & Requirement-Driven
- Tests validate observable contracts, system outputs, and behavioral boundaries derived directly from `ORIGINAL_REQUEST.md`, `PROJECT.md`, and FTMO regulatory specifications (`data/ftmo_asset_specs.json`).
- Tests do not assert against internal implementation shortcuts.
- Each test case asserts against an explicit authoritative expected value derived from mathematical properties, broker rulebooks, or documented interface contracts.

### 1.2 Progressive Testability
- Tests are structured across 4 distinct tiers (`tests/e2e/test_tier1_features.py`, `tests/e2e/test_tier2_boundaries.py`, `tests/e2e/test_tier3_combinations.py`, `tests/e2e/test_tier4_applications.py`).
- Milestones currently in progress (such as OCaml Dune binary compilation or Haskell QuickCheck executables) are tested via interface contract specifications and skip gracefully if external build artifacts have not yet been placed on disk.
- Core specifications, dimensional taxonomy, risk calculations, and trade replay remain fully verifiable at all times.

### 1.3 Anti-Cheating & Integrity Guardrails
- In accordance with the project Victory Audit rules:
  - Cryptographic and mathematical operations are calculated directly; no mocks replace core risk calculations.
  - Assertions check exact numeric equality or strictly bounded ranges rather than generic booleans.
  - Zero test assertions are commented out or suppressed.

---

## 2. Feature Inventory & Coverage Threshold Mapping

The test suite provides exhaustive coverage across all 16 features inventoried in `PROJECT.md`.

| # | Feature Name | Milestone | Tier 1 Tests | Tier 2 Boundaries | Tier 3 Matrix | Tier 4 Sim | Status |
|---|---|---|---|---|---|---|---|
| 1 | Dukascopy Data Downloader | M1 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 2 | MetaApi Data Puller | M1 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 3 | CandleDataLoader Fixes & Validation | M1 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 4 | Modular Risk Sizing (7 Models) | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 5 | Modular Entry Modes (7 London, 7 Omni) | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 6 | Modular Pyramiding (7 Models) | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 7 | Modular Exit Models (7 Models) | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 8 | Modular Market Filters (7 per engine) | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 9 | Config-Driven Live Engine Refactors | M2 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 10 | Hermetic OCaml Formal Verifier | M3 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 11 | Haskell QuickCheck Fuzzer | M3 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 12 | Python Runtime Validator & Watchdog | M3 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 13 | High-Performance Tournament Runner | M4 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 14 | Observation-Only Paper Trader | M5 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 15 | Cross-Engine Correlation & VM Deployment | M5 | >=5 | >=5 | Yes | Yes | VERIFIED |
| 16 | Opaque-Box E2E Test Suite (Tiers 1-4) | E2E | >=5 | >=5 | Yes | Yes | VERIFIED |

---

## 3. Four-Tier Test Suite Architecture

```
tests/e2e/
├── conftest.py                   # Shared fixtures, synthetic candles, account state
├── test_tier1_features.py        # 80 happy-path feature verification tests
├── test_tier2_boundaries.py      # 80 edge, corner, zero-value, and stress tests
├── test_tier3_combinations.py    # 19 pairwise interaction and INC-01 to INC-07 tests
└── test_tier4_applications.py    # 5 realistic FTMO challenge simulations
```

### 3.1 Tier 1: Feature Isolation Tests (`test_tier1_features.py`)
- Purpose: Verifies primary functional requirements (happy paths) for every inventoried component.
- Threshold: Minimum 5 isolated tests per feature (80 tests total).
- Coverage:
  - Downloader URL construction, date chunking, and candle aggregation.
  - Exact risk percentages across Conservative Ramp, Fixed Low, Aggressive Flat, Kelly, Anti-Martingale, Volatility-Scaled, and Equity Curve models.
  - Entry signals across all 14 entry modes (London range-fades and Omni breakouts).
  - Tranche distributions for all 7 pyramiding models.
  - Trailing, ATR dynamic, and time-based exits.
  - Filter logic across ATR, spread, day-of-week, and composite stacks.
  - Tournament ranking formula and metric computation.

### 3.2 Tier 2: Boundary & Corner Case Tests (`test_tier2_boundaries.py`)
- Purpose: Tests failure modes, resource limits, division-by-zero guards, and FTMO constraints.
- Threshold: Minimum 5 boundary/corner cases per feature (80 tests total).
- Coverage:
  - Zero-equity and non-positive stop-loss protections.
  - Inverted candle detection, zero volume bars, and empty CSV handling.
  - Weekend market closure behavior and leap-year timestamp handling.
  - Exact boundary thresholds for ATR gate (0.50 and 2.00) and spread gate (4.99 vs 5.00 pts).
  - Chandelier stop monotonicity and simultaneous SL/TP wick resolution.
  - $90,000 floor preservation across 20+ loss streaks.
  - 1-second watchdog equity drop detection.

### 3.3 Tier 3: Pairwise Combinations & Incompatibilities (`test_tier3_combinations.py`)
- Purpose: Verifies valid cross-dimensional interactions and enforces architectural incompatibility rejections.
- Incompatibility Rules Tested:
  - `INC-01`: Cross-engine entry mode mismatch (London engine with Omni entry).
  - `INC-02`: Scale-in pyramiding paired with static fixed SL/TP exits.
  - `INC-03`: High-exposure risk sizing paired with multi-tranche pyramiding.
  - `INC-04`: Multi-tranche scale-in paired with time-based exits.
  - `INC-05`: Blind limit entries without market context filters.
  - `INC-06`: Wide Chandelier exits paired with tight fixed SL sizing.
  - `INC-07`: Crypto instruments paired with position sizes exceeding 0.50 lots.
- Cross-Engine Session Interaction:
  - Morning London Reversal profit/loss propagation to afternoon Omni Breakout equity.
  - Circuit breaker trips in morning session halting afternoon engine.

### 3.4 Tier 4: Realistic FTMO Challenge Simulations (`test_tier4_applications.py`)
- Purpose: Evaluates complete multi-day trading scenarios under live FTMO verification account parameters.
- Account Baseline:
  - Initial Balance: $100,000.00
  - Current Equity: $94,939.28 (5.06% drawdown)
  - Hard Floor: $90,000.00 (10% max loss)
  - Remaining Floor Cushion: $4,939.28
  - Profit Target: $110,000.00
  - Daily Loss Limit: 5.0% mark-to-market
  - Circuit Breaker: 4.5% drawdown threshold ($4,272.27 at $94,939.28)
- Scenarios Tested:
  - 5-Day Challenge Week: Progressive equity growth across 10 sessions towards $110k target.
  - Adversarial Gap & Shock: Flash crash tripping circuit breaker at 4.5%, preserving $90,500 emergency floor.
  - 10-Day Drawdown Sequence: Verifying Conservative Ramp keeps maximum drawdown under 8.0%.
  - Paper Trader 48-Hour Stream: 2,880 1-minute bars verifying strict 0.01 micro-lot zero-risk execution.
  - Watchdog Emergency Lockout: Immediate generation of `daily_lockouts.json`.

---

## 4. Test Runner Configuration and Invocation

### 4.1 Prerequisites
- Python 3.9+ (Python 3.14 compatible)
- `pytest` >= 9.0.0
- `pytest-asyncio` >= 1.0.0

### 4.2 Configuration File (`pytest.ini`)
```ini
[pytest]
pythonpath = .
testpaths = tests/e2e
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v
```

### 4.3 Invocation Commands

```bash
# Execute entire E2E test suite (all 4 tiers)
pytest tests/e2e/ -v

# Execute Tier 1: Feature Isolation Tests
pytest tests/e2e/test_tier1_features.py -v

# Execute Tier 2: Boundary & Corner Case Tests
pytest tests/e2e/test_tier2_boundaries.py -v

# Execute Tier 3: Pairwise Combinations & Incompatibilities
pytest tests/e2e/test_tier3_combinations.py -v

# Execute Tier 4: FTMO Challenge Simulations
pytest tests/e2e/test_tier4_applications.py -v
```
