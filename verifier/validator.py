"""Odin FTMO v2 Runtime Validator and Equity Watchdog.

Python 3.9-compatible profile validation and 1-second equity watchdog.
Enforces the 5 FTMO mathematical invariants and the 7-class module incompatibility
matrix (INC-01 through INC-07) with exact semantic parity to the OCaml formal verifier.
"""

import sys
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


INITIAL_BALANCE = 100000.0
CURRENT_EQUITY = 94939.28
ABSOLUTE_FLOOR = 90000.0
EMERGENCY_FLOOR = 90500.0
CIRCUIT_BREAKER_DAILY_LOSS_PCT = 0.045
FTMO_MAX_DAILY_LOSS_PCT = 0.05
MAX_COMPOSITE_RISK_PCT = 0.0130
MAX_FREE_MARGIN_PCT = 0.50
MAX_CRYPTO_LOTS = 0.50

INSTRUMENT_SPECS: Dict[str, Dict[str, Any]] = {
    "US100.cash": {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.0,
        "default_price": 19500.0,
        "default_atr": 40.0,
    },
    "US30.cash": {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.5,
        "default_price": 41000.0,
        "default_atr": 80.0,
    },
    "US500.cash": {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 0.3,
        "default_price": 5600.0,
        "default_atr": 15.0,
    },
    "GER40.cash": {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.0,
        "default_price": 18500.0,
        "default_atr": 45.0,
    },
    "UK100.cash": {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.5,
        "default_price": 8300.0,
        "default_atr": 25.0,
    },
    "EURUSD": {
        "asset_class": "forex",
        "leverage": 100.0,
        "contract_size": 100000.0,
        "tick_value": 10.0,
        "commission": 3.0,
        "spread": 0.2,
        "default_price": 1.09,
        "default_atr": 0.0050,
    },
    "GBPUSD": {
        "asset_class": "forex",
        "leverage": 100.0,
        "contract_size": 100000.0,
        "tick_value": 10.0,
        "commission": 3.0,
        "spread": 0.5,
        "default_price": 1.31,
        "default_atr": 0.0060,
    },
    "XAUUSD": {
        "asset_class": "commodity",
        "leverage": 30.0,
        "contract_size": 100.0,
        "tick_value": 1.0,
        "commission": 3.0,
        "spread": 2.5,
        "default_price": 2500.0,
        "default_atr": 15.0,
    },
    "BTCUSD": {
        "asset_class": "crypto",
        "leverage": 1.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 15.0,
        "default_price": 60000.0,
        "default_atr": 800.0,
    },
    "ETHUSD": {
        "asset_class": "crypto",
        "leverage": 1.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.0,
        "default_price": 2500.0,
        "default_atr": 45.0,
    },
}

LONDON_ENTRIES = {
    "blind_limit",
    "sweep_confirmation",
    "dynamic_buffer",
    "time_weighted",
    "order_flow_spread_gate",
    "multi_timeframe",
    "hybrid_sweep_time_spread",
}

OMNI_ENTRIES = {
    "stop_order_at_range",
    "close_confirmation",
    "volume_spike_gate",
    "retest_entry",
    "momentum_threshold",
    "dual_timeframe",
    "hybrid_retest_volume_spread",
}

SCALE_IN_PYRAMIDS = {
    "equal_split",
    "front_loaded",
    "inverse_pyramid",
    "adaptive_tranche",
    "momentum_confirmed",
}

HIGH_RISK_MODELS = {
    "aggressive_flat",
    "anti_martingale",
}

BACKLOADED_PYRAMIDS = {
    "inverse_pyramid",
    "adaptive_tranche",
}

COMPLEX_SCALE_IN_PYRAMIDS = {
    "adaptive_tranche",
    "momentum_confirmed",
}

VALID_ENGINES = {
    "london_reversal",
    "omni_breakout",
}

VALID_RISK_MODELS = {
    "conservative_ramp",
    "fixed_low",
    "aggressive_flat",
    "kelly_criterion",
    "anti_martingale",
    "volatility_scaled",
    "equity_curve",
}

VALID_ENTRY_MODES = LONDON_ENTRIES | OMNI_ENTRIES

VALID_PYRAMID_MODELS = {
    "no_pyramid",
    "equal_split",
    "front_loaded",
    "inverse_pyramid",
    "momentum_confirmed",
    "risk_free_runner",
    "adaptive_tranche",
}

VALID_EXIT_MODELS = {
    "fixed_sl_tp",
    "fixed_sl_trail",
    "atr_dynamic_trail",
    "breakeven_runner",
    "time_based",
    "chandelier",
    "multi_target_cascade",
}


def validate_schema(profile: Any) -> Tuple[bool, List[str]]:
    """Validate profile dictionary structure and dimension enums against formal schema."""
    errors: List[str] = []
    if not isinstance(profile, dict) or len(profile) == 0:
        return False, ["Schema validation error: Profile must be a non-empty JSON object"]

    required_keys = ["engine", "instrument", "dimensions", "parameters", "risk_bounds"]
    for k in required_keys:
        if k not in profile:
            errors.append(f"Schema validation error: Missing required top-level key: {k}")

    if errors:
        return False, errors

    engine = profile.get("engine")
    if engine not in VALID_ENGINES:
        errors.append(f"Schema validation error: Invalid engine '{engine}'")

    instrument = profile.get("instrument")
    if not isinstance(instrument, str) or len(instrument.strip()) == 0:
        errors.append("Schema validation error: Invalid or empty instrument")

    dimensions = profile.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("Schema validation error: 'dimensions' must be a dictionary")
    else:
        risk_model = dimensions.get("risk_model")
        if risk_model not in VALID_RISK_MODELS:
            errors.append(f"Schema validation error: Invalid risk_model '{risk_model}'")

        entry_mode = dimensions.get("entry_mode")
        if entry_mode not in VALID_ENTRY_MODES:
            errors.append(f"Schema validation error: Invalid entry_mode '{entry_mode}'")

        pyramid_model = dimensions.get("pyramid_model")
        if pyramid_model not in VALID_PYRAMID_MODELS:
            errors.append(f"Schema validation error: Invalid pyramid_model '{pyramid_model}'")

        exit_model = dimensions.get("exit_model")
        if exit_model not in VALID_EXIT_MODELS:
            errors.append(f"Schema validation error: Invalid exit_model '{exit_model}'")

        filters = dimensions.get("filters")
        if filters is not None and not isinstance(filters, list):
            errors.append("Schema validation error: 'filters' must be a list")

    if not isinstance(profile.get("parameters"), dict):
        errors.append("Schema validation error: 'parameters' must be a dictionary")

    if not isinstance(profile.get("risk_bounds"), dict):
        errors.append("Schema validation error: 'risk_bounds' must be a dictionary")

    return len(errors) == 0, errors


def get_spec(symbol: str) -> Dict[str, Any]:
    """Return instrument specification dictionary with safe fallback defaults."""
    clean_sym = symbol.strip()
    if clean_sym in INSTRUMENT_SPECS:
        return INSTRUMENT_SPECS[clean_sym]
    return {
        "asset_class": "index",
        "leverage": 50.0,
        "contract_size": 1.0,
        "tick_value": 1.0,
        "commission": 0.0,
        "spread": 1.5,
        "default_price": 19000.0,
        "default_atr": 40.0,
    }


def compute_lot_size(profile: Dict[str, Any], equity: float) -> float:
    """Compute position size in lots for a given equity level."""
    dims = profile.get("dimensions", {})
    params = profile.get("parameters", {})
    bounds = profile.get("risk_bounds", {})
    symbol = profile.get("instrument", "US100.cash")
    spec = get_spec(symbol)

    risk_model = dims.get("risk_model", "conservative_ramp")
    if risk_model == "conservative_ramp":
        if equity < 98000.0:
            base_risk = 0.0025
        elif equity < 102000.0:
            base_risk = 0.0050
        else:
            base_risk = 0.0075
    elif risk_model == "fixed_low":
        base_risk = 0.0035
    elif risk_model == "aggressive_flat":
        base_risk = 0.0075
    elif risk_model == "kelly_criterion":
        base_risk = 0.0075
    elif risk_model == "anti_martingale":
        base_risk = 0.0075
    elif risk_model == "volatility_scaled":
        base_risk = 0.0060
    elif risk_model == "equity_curve":
        base_risk = 0.0050
    else:
        base_risk = 0.0050

    max_risk_pct = float(bounds.get("max_risk_pct", 0.0075))
    eff_risk = min(base_risk, max_risk_pct)
    risk_dollars = equity * eff_risk

    try:
        sl_pts = float(params.get("sl_pts", 40.0))
    except (ValueError, TypeError):
        raise ValueError("Stop loss parameter sl_pts must be a valid float")

    if math.isnan(sl_pts) or sl_pts <= 0.0:
        raise ValueError(f"Stop loss parameter sl_pts must be positive (got {sl_pts})")

    raw_lots = risk_dollars / (sl_pts * spec["tick_value"])
    base_lots = params.get("base_lot_size")
    if base_lots is not None:
        raw_lots = max(float(base_lots), raw_lots)

    max_lots = float(bounds.get("max_lot_size", 15.0))
    capped = min(raw_lots, max_lots)
    rounded = round(capped, 2)
    return max(0.01, rounded)


def check_incompatibilities(profile: Dict[str, Any]) -> List[str]:
    """Evaluate INC-01 through INC-07 on a profile dictionary."""
    violations: List[str] = []
    engine = profile.get("engine", "")
    dims = profile.get("dimensions", {})
    params = profile.get("parameters", {})
    bounds = profile.get("risk_bounds", {})
    symbol = profile.get("instrument", "")

    entry_mode = dims.get("entry_mode", "")
    risk_model = dims.get("risk_model", "")
    pyramid_model = dims.get("pyramid_model", "")
    exit_model = dims.get("exit_model", "")
    filters = dims.get("filters", [])

    if engine == "london_reversal" and entry_mode not in LONDON_ENTRIES:
        violations.append(f"INC-01: London Reversal engine assigned Omni entry mode: {entry_mode}")

    if engine == "omni_breakout" and entry_mode not in OMNI_ENTRIES:
        violations.append(f"INC-01: Omni Breakout engine assigned London entry mode: {entry_mode}")

    if pyramid_model in SCALE_IN_PYRAMIDS and exit_model == "fixed_sl_tp":
        violations.append("INC-02: Scale-in pyramiding model requires trailing stop or breakeven exit, incompatible with static fixed_sl_tp")

    if risk_model in HIGH_RISK_MODELS and pyramid_model in BACKLOADED_PYRAMIDS:
        violations.append("INC-03: High-exposure risk model combined with back-loaded or adaptive pyramiding violates drawdown safety")

    if pyramid_model in COMPLEX_SCALE_IN_PYRAMIDS and exit_model == "time_based":
        violations.append("INC-04: Multi-tranche scale-in model is incompatible with 120-minute time_based exit")

    if entry_mode == "blind_limit" and len(filters) == 0:
        violations.append("INC-05: Blind limit entry requires at least one market context filter to prevent momentum flush stop-outs")

    sl_pts = float(params.get("sl_pts", 40.0))
    max_risk = float(bounds.get("max_risk_pct", 0.0075))
    if exit_model == "chandelier" and (sl_pts < 20.0 or risk_model == "aggressive_flat" or max_risk > 0.010):
        violations.append("INC-06: Chandelier wide stop exit (3x ATR) is incompatible with tight SL (<20 pts) or aggressive risk sizing")

    is_crypto = symbol in ("BTCUSD", "ETHUSD")
    if is_crypto:
        max_lot = float(bounds.get("max_lot_size", 15.0))
        if max_lot > MAX_CRYPTO_LOTS:
            violations.append("INC-07: Crypto instruments (1:1 leverage) require position size <= 0.50 lots to preserve margin ceiling")
        base_lots = params.get("base_lot_size")
        if base_lots is not None and float(base_lots) > MAX_CRYPTO_LOTS:
            violations.append("INC-07: Crypto base lot size exceeds 0.50 lots on 1:1 leverage account")

    return violations


def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Verify profile invariants and incompatibilities against FTMO constraints."""
    schema_ok, schema_errors = validate_schema(profile)
    if not schema_ok:
        report = {
            "verified": False,
            "profile_id": profile.get("profile_id", "unknown") if isinstance(profile, dict) else "unknown",
            "invariants": {
                "total_floor_preserved": False,
                "daily_loss_bounded": False,
                "composite_risk_valid": False,
                "adverse_gap_resilient": False,
                "margin_feasible": False,
                "compatibility_passed": False,
            },
            "worst_case_drawdown_pct": 1.0,
            "worst_case_equity": 0.0,
            "max_lot_size": 0.0,
            "violations": schema_errors,
        }
        return False, schema_errors, report

    violations = check_incompatibilities(profile)

    symbol = profile.get("instrument", "US100.cash")
    spec = get_spec(symbol)
    dims = profile.get("dimensions", {})
    params = profile.get("parameters", {})
    bounds = profile.get("risk_bounds", {})

    sl_val = params.get("sl_pts", 40.0)
    try:
        sl_pts = float(sl_val)
    except (ValueError, TypeError):
        sl_pts = 0.0

    valid_sl = not math.isnan(sl_pts) and sl_pts > 0.0
    if not valid_sl:
        violations.append(f"Invariant 1 Violation: Stop loss parameter sl_pts must be positive (got {sl_val})")
        violations.append(f"Invariant 2 Violation: Stop loss parameter sl_pts must be positive (got {sl_val})")

    base_lots = params.get("base_lot_size")
    max_lots = float(bounds.get("max_lot_size", 15.0))
    base_lot_exceeds_max = False
    if base_lots is not None:
        try:
            bl_val = float(base_lots)
            if bl_val > max_lots:
                base_lot_exceeds_max = True
                violations.append(
                    f"Invariant 1 Violation: Base lot size {bl_val:.2f} exceeds maximum lot size {max_lots:.2f}"
                )
        except (ValueError, TypeError):
            pass

    if valid_sl:
        try:
            initial_lots = compute_lot_size(profile, CURRENT_EQUITY)
        except ValueError:
            initial_lots = 0.0
    else:
        initial_lots = 0.0

    pyramid_model = dims.get("pyramid_model", "no_pyramid")
    max_tranches = int(params.get("max_tranches", 1))
    tranche_count = 1 if pyramid_model == "no_pyramid" else max(1, max_tranches)
    total_lots = initial_lots * tranche_count

    composite_risk = (total_lots * sl_pts * spec["tick_value"]) + (total_lots * spec["commission"])
    margin_to_floor = max(0.0, CURRENT_EQUITY - ABSOLUTE_FLOOR)
    max_composite_budget = min(0.015 * CURRENT_EQUITY, 0.25 * margin_to_floor)

    inv3_passed = valid_sl and composite_risk <= max_composite_budget and (composite_risk / CURRENT_EQUITY) <= MAX_COMPOSITE_RISK_PCT
    if not inv3_passed and valid_sl:
        violations.append(
            f"Invariant 3 Violation: Composite risk ${composite_risk:.2f} exceeds ceiling ${max_composite_budget:.2f} (1.30% limit)"
        )

    shock_sl = sl_pts + (1.5 * spec["default_atr"]) + (3.0 * spec["spread"])
    shock_loss = (total_lots * shock_sl * spec["tick_value"]) + (total_lots * spec["commission"])
    circuit_breaker_limit = CIRCUIT_BREAKER_DAILY_LOSS_PCT * CURRENT_EQUITY

    inv4_passed = valid_sl and shock_loss <= circuit_breaker_limit
    if not inv4_passed and valid_sl:
        violations.append(
            f"Invariant 4 Violation: Adverse gap shock loss ${shock_loss:.2f} exceeds daily circuit breaker limit ${circuit_breaker_limit:.2f}"
        )

    margin_req = (total_lots * spec["contract_size"] * spec["default_price"]) / spec["leverage"]
    max_margin = MAX_FREE_MARGIN_PCT * CURRENT_EQUITY
    crypto_lots_ok = spec["asset_class"] != "crypto" or total_lots <= MAX_CRYPTO_LOTS

    inv5_passed = valid_sl and margin_req <= max_margin and crypto_lots_ok
    if not inv5_passed and valid_sl:
        if not crypto_lots_ok:
            violations.append(f"Invariant 5 Violation: Crypto position size {total_lots:.2f} lots exceeds 0.50 lot cap")
        else:
            violations.append(f"Invariant 5 Violation: Margin required ${margin_req:.2f} exceeds 50% free margin ${max_margin:.2f}")

    single_trade_loss = (initial_lots * sl_pts * spec["tick_value"]) + (initial_lots * spec["commission"])
    max_daily_loss_pct = float(bounds.get("max_daily_loss_pct", 0.045))
    inv2_passed = (
        valid_sl
        and single_trade_loss <= circuit_breaker_limit
        and max_daily_loss_pct <= CIRCUIT_BREAKER_DAILY_LOSS_PCT
    )
    if not inv2_passed and valid_sl:
        violations.append(
            f"Invariant 2 Violation: Trade risk ${single_trade_loss:.2f} breaches 4.5% daily loss ceiling ${circuit_breaker_limit:.2f}"
        )

    sim_equity = CURRENT_EQUITY
    sim_watermark = CURRENT_EQUITY
    sim_daily_loss = 0.0
    min_equity_reached = CURRENT_EQUITY
    sim_floor_breached = False

    if valid_sl and not base_lot_exceeds_max:
        for _ in range(10):
            if sim_equity > EMERGENCY_FLOOR:
                try:
                    step_lots = compute_lot_size(profile, sim_equity)
                except ValueError:
                    sim_floor_breached = True
                    break
                step_loss = (step_lots * sl_pts * spec["tick_value"]) + (step_lots * spec["commission"])
                if sim_equity - step_loss < ABSOLUTE_FLOOR:
                    sim_floor_breached = True
                    min_equity_reached = min(min_equity_reached, sim_equity - step_loss)

                max_daily = CIRCUIT_BREAKER_DAILY_LOSS_PCT * sim_watermark

                if sim_daily_loss + step_loss >= max_daily:
                    loss_applied = min(step_loss, max(0.0, max_daily - sim_daily_loss))
                    sim_equity -= loss_applied
                    min_equity_reached = min(min_equity_reached, sim_equity)
                    sim_watermark = sim_equity
                    sim_daily_loss = 0.0
                else:
                    sim_equity -= step_loss
                    sim_daily_loss += step_loss
                    min_equity_reached = min(min_equity_reached, sim_equity)

                if sim_equity < ABSOLUTE_FLOOR:
                    sim_floor_breached = True
    else:
        sim_floor_breached = True

    inv1_passed = (
        valid_sl
        and not base_lot_exceeds_max
        and not sim_floor_breached
        and min_equity_reached >= ABSOLUTE_FLOOR
    )
    if not inv1_passed and valid_sl and not base_lot_exceeds_max:
        violations.append(
            f"Invariant 1 Violation: Simulated worst-case equity ${min_equity_reached:.2f} dropped below absolute floor ${ABSOLUTE_FLOOR:.2f}"
        )

    compatibility_passed = len(check_incompatibilities(profile)) == 0
    verified = (
        inv1_passed
        and inv2_passed
        and inv3_passed
        and inv4_passed
        and inv5_passed
        and compatibility_passed
        and len(violations) == 0
    )

    worst_case_drawdown_pct = (CURRENT_EQUITY - min_equity_reached) / CURRENT_EQUITY

    report = {
        "verified": verified,
        "profile_id": profile.get("profile_id", "unknown"),
        "invariants": {
            "total_floor_preserved": inv1_passed,
            "daily_loss_bounded": inv2_passed,
            "composite_risk_valid": inv3_passed,
            "adverse_gap_resilient": inv4_passed,
            "margin_feasible": inv5_passed,
            "compatibility_passed": compatibility_passed,
        },
        "worst_case_drawdown_pct": worst_case_drawdown_pct,
        "worst_case_equity": min_equity_reached,
        "max_lot_size": total_lots,
        "violations": violations,
    }

    return verified, violations, report


def validate_profile_file(profile_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Load JSON profile from file and perform full validation."""
    p = Path(profile_path)
    if not p.exists():
        return False, [f"Profile file not found: {profile_path}"], {}
    try:
        with open(p, "r") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Failed to parse JSON file {profile_path}: {e}"], {}
    return validate_profile(data)


def validate_profile_or_exit(profile_path: str) -> None:
    """Validate profile file; on failure, print report and terminate process with code 1."""
    verified, violations, report = validate_profile_file(profile_path)
    if verified:
        print(f"[VALIDATOR] SUCCESS: Profile {profile_path} verified against all FTMO constraints.")
    else:
        print(f"[VALIDATOR] FATAL: Profile {profile_path} rejected by formal verification rules:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)


class EquityWatchdog:
    """Continuous runtime equity watchdog checking daily circuit breaker and floor."""

    def __init__(
        self,
        daily_watermark: float = CURRENT_EQUITY,
        account_floor: float = ABSOLUTE_FLOOR,
        emergency_floor: float = EMERGENCY_FLOOR,
        circuit_breaker_pct: float = CIRCUIT_BREAKER_DAILY_LOSS_PCT,
        lockout_file: str = "daily_lockouts.json",
    ):
        self.daily_watermark = daily_watermark
        self.account_floor = account_floor
        self.emergency_floor = emergency_floor
        self.circuit_breaker_pct = circuit_breaker_pct
        self.lockout_file = Path(lockout_file)

    def check_equity(self, current_equity: float) -> Tuple[str, str]:
        """Evaluate current mark-to-market equity against safety boundaries.

        Returns (action, reason) where action is one of:
        - "NORMAL": Equity within safe operating parameters.
        - "CIRCUIT_BREAKER": Equity breached 4.5% daily drawdown; flatten and halt day.
        - "EMERGENCY_STOP": Equity breached $90,500.00 emergency stop; permanent shutdown.
        """
        if current_equity <= self.emergency_floor:
            reason = f"Equity ${current_equity:.2f} breached emergency floor ${self.emergency_floor:.2f}"
            self.record_lockout("EMERGENCY_STOP", reason, current_equity)
            return "EMERGENCY_STOP", reason

        max_loss = self.circuit_breaker_pct * self.daily_watermark
        cb_threshold = self.daily_watermark - max_loss
        if current_equity <= cb_threshold:
            drawdown_pct = (self.daily_watermark - current_equity) / self.daily_watermark
            reason = f"Daily drawdown {drawdown_pct:.2%} breached circuit breaker threshold {self.circuit_breaker_pct:.2%}"
            self.record_lockout("CIRCUIT_BREAKER", reason, current_equity)
            return "CIRCUIT_BREAKER", reason

        return "NORMAL", "Equity within risk bounds"

    def is_locked_out(self) -> bool:
        """Check if trading is halted for today in the lockout state file."""
        if not self.lockout_file.exists():
            return False
        try:
            with open(self.lockout_file, "r") as f:
                data = json.load(f)
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return bool(data.get("trading_halted_for_day", False) and data.get("lockout_date") == today_str)
        except Exception:
            return False

    def record_lockout(self, action: str, reason: str, equity: float) -> None:
        """Write lockout event record to disk for persistence across engine restarts."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        record = {
            "lockout_date": today_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "reason": reason,
            "equity_at_lockout": equity,
            "watermark": self.daily_watermark,
            "trading_halted_for_day": True,
        }
        try:
            with open(self.lockout_file, "w") as f:
                json.dump(record, f, indent=2)
        except Exception as e:
            sys.stderr.write(f"[WATCHDOG] Failed to write lockout file: {e}\n")

    def reset_daily_watermark(self, new_watermark: float) -> None:
        """Reset the daily starting equity watermark at 00:00 CE(S)T rollover."""
        self.daily_watermark = new_watermark


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validator.py --profile <profile_path.json>")
        sys.exit(2)

    arg = sys.argv[1]
    if arg == "--profile" and len(sys.argv) >= 3:
        prof_path = sys.argv[2]
        ok, viols, rep = validate_profile_file(prof_path)
        print(json.dumps(rep, indent=2))
        sys.exit(0 if ok else 1)
    else:
        ok, viols, rep = validate_profile_file(arg)
        print(json.dumps(rep, indent=2))
        sys.exit(0 if ok else 1)
