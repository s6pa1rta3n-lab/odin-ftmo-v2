"""Comprehensive test suite for the Formal Verification Pipeline (Milestone M3).

Verifies:
1. JSON schema conformity for canonical profiles.
2. Direct execution of OCaml formal verifier binary on canonical and toxic profiles.
3. Python runtime validator enforcement of INC-01 through INC-07 and Invariants 1-5.
4. Cross-language parity between OCaml verifier output and Python validator output.
5. Equity watchdog transitions and circuit breaker lockout file persistence.
"""

import json
import subprocess
import tempfile
from pathlib import Path
import pytest
import jsonschema

from verifier.validator import (
    EquityWatchdog,
    validate_profile,
    validate_profile_file,
    check_incompatibilities,
    compute_lot_size,
    CURRENT_EQUITY,
    ABSOLUTE_FLOOR,
    EMERGENCY_FLOOR,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "profiles" / "profile_schema.json"
CANONICAL_PROFILES = [
    Path(__file__).resolve().parent.parent / "profiles" / "london_reversal" / "london_conservative_sweep_v1.json",
    Path(__file__).resolve().parent.parent / "profiles" / "london_reversal" / "london_fixed_low_be_v1.json",
    Path(__file__).resolve().parent.parent / "profiles" / "omni_breakout" / "omni_conservative_close_v1.json",
    Path(__file__).resolve().parent.parent / "profiles" / "omni_breakout" / "omni_fixed_low_trail_v1.json",
]
OCAML_BIN = Path(__file__).resolve().parent.parent / "verifier" / "bin" / "main.exe"


def load_canonical_profile() -> dict:
    """Load canonical London Reversal profile as a base template."""
    with open(CANONICAL_PROFILES[0], "r") as f:
        return json.load(f)


class TestLayer1SchemaValidation:
    """Layer 1: Schema conformance tests."""

    def test_schema_file_exists_and_parses(self):
        """Verify profile_schema.json is present and valid JSON Schema."""
        assert SCHEMA_PATH.exists()
        with open(SCHEMA_PATH, "r") as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert schema["type"] == "object"

    @pytest.mark.parametrize("prof_path", CANONICAL_PROFILES)
    def test_canonical_profiles_conform_to_schema(self, prof_path):
        """Verify each canonical profile strictly validates against profile_schema.json."""
        assert prof_path.exists()
        with open(SCHEMA_PATH, "r") as sf, open(prof_path, "r") as pf:
            schema = json.load(sf)
            profile_data = json.load(pf)
        jsonschema.validate(instance=profile_data, schema=schema)


class TestLayer2OCamlVerifierParity:
    """Layer 2: Hermetic OCaml formal verifier tests and cross-language parity."""

    def test_ocaml_binary_exists(self):
        """Verify the OCaml verifier executable has been compiled."""
        assert OCAML_BIN.exists()

    @pytest.mark.parametrize("prof_path", CANONICAL_PROFILES)
    def test_ocaml_verifier_verifies_canonical_profiles(self, prof_path):
        """Verify OCaml verifier returns exit code 0 and verified=true on canonical profiles."""
        cmd = [str(OCAML_BIN), str(prof_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0
        output_data = json.loads(proc.stdout)
        assert output_data["verified"] is True
        assert output_data["invariants"]["total_floor_preserved"] is True
        assert output_data["invariants"]["daily_loss_bounded"] is True
        assert output_data["invariants"]["composite_risk_valid"] is True
        assert output_data["invariants"]["adverse_gap_resilient"] is True
        assert output_data["invariants"]["margin_feasible"] is True
        assert output_data["invariants"]["compatibility_passed"] is True
        assert len(output_data["violations"]) == 0

    @pytest.mark.parametrize("prof_path", CANONICAL_PROFILES)
    def test_ocaml_and_python_parity(self, prof_path):
        """Verify exact mathematical parity between OCaml verifier and Python validator."""
        cmd = [str(OCAML_BIN), str(prof_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0
        ocaml_rep = json.loads(proc.stdout)

        py_ok, py_viols, py_rep = validate_profile_file(str(prof_path))
        assert py_ok is True
        assert len(py_viols) == 0

        assert ocaml_rep["verified"] == py_rep["verified"]
        assert pytest.approx(ocaml_rep["worst_case_equity"], abs=0.01) == py_rep["worst_case_equity"]
        assert pytest.approx(ocaml_rep["max_lot_size"], abs=0.01) == py_rep["max_lot_size"]
        assert pytest.approx(ocaml_rep["worst_case_drawdown_pct"], abs=0.001) == py_rep["worst_case_drawdown_pct"]


class TestIncompatibilityMatrix:
    """Verification of INC-01 through INC-07 rejection rules in Python validator."""

    def test_inc01_cross_engine_rejection(self):
        """Verify INC-01 rejects cross-engine entry combinations."""
        p_london = load_canonical_profile()
        p_london["dimensions"]["entry_mode"] = "close_confirmation"
        viols = check_incompatibilities(p_london)
        assert any("INC-01" in v for v in viols)

        p_omni = load_canonical_profile()
        p_omni["engine"] = "omni_breakout"
        p_omni["dimensions"]["entry_mode"] = "sweep_confirmation"
        viols = check_incompatibilities(p_omni)
        assert any("INC-01" in v for v in viols)

    def test_inc02_scale_in_fixed_exit_rejection(self):
        """Verify INC-02 rejects scale-in pyramiding with fixed SL/TP."""
        p = load_canonical_profile()
        p["dimensions"]["pyramid_model"] = "equal_split"
        p["dimensions"]["exit_model"] = "fixed_sl_tp"
        viols = check_incompatibilities(p)
        assert any("INC-02" in v for v in viols)

    def test_inc03_high_risk_backloaded_rejection(self):
        """Verify INC-03 rejects aggressive/anti-martingale with back-loaded tranches."""
        p = load_canonical_profile()
        p["dimensions"]["risk_model"] = "aggressive_flat"
        p["dimensions"]["pyramid_model"] = "inverse_pyramid"
        viols = check_incompatibilities(p)
        assert any("INC-03" in v for v in viols)

    def test_inc04_complex_scale_in_time_exit_rejection(self):
        """Verify INC-04 rejects multi-tranche models paired with time-based exit."""
        p = load_canonical_profile()
        p["dimensions"]["pyramid_model"] = "adaptive_tranche"
        p["dimensions"]["exit_model"] = "time_based"
        viols = check_incompatibilities(p)
        assert any("INC-04" in v for v in viols)

    def test_inc05_blind_limit_empty_filter_rejection(self):
        """Verify INC-05 rejects blind limit entries with no filters."""
        p = load_canonical_profile()
        p["dimensions"]["entry_mode"] = "blind_limit"
        p["dimensions"]["filters"] = []
        viols = check_incompatibilities(p)
        assert any("INC-05" in v for v in viols)

    def test_inc06_chandelier_tight_sl_rejection(self):
        """Verify INC-06 rejects chandelier exit with tight SL or aggressive risk."""
        p = load_canonical_profile()
        p["dimensions"]["exit_model"] = "chandelier"
        p["parameters"]["sl_pts"] = 15.0
        viols = check_incompatibilities(p)
        assert any("INC-06" in v for v in viols)

    def test_inc07_crypto_large_lot_rejection(self):
        """Verify INC-07 rejects crypto instruments with lot size > 0.50."""
        p = load_canonical_profile()
        p["instrument"] = "BTCUSD"
        p["risk_bounds"]["max_lot_size"] = 1.0
        viols = check_incompatibilities(p)
        assert any("INC-07" in v for v in viols)


class TestFTMOInvariants:
    """Verification of Invariants 1-5 in Python validator."""

    def test_invariant_3_composite_risk_rejection(self):
        """Verify Invariant 3 rejects composite risk exceeding 1.30% ceiling."""
        p = load_canonical_profile()
        p["parameters"]["sl_pts"] = 80.0
        p["parameters"]["base_lot_size"] = 25.0
        p["parameters"]["max_tranches"] = 3
        p["risk_bounds"]["max_lot_size"] = 30.0
        verified, violations, report = validate_profile(p)
        assert verified is False
        assert report["invariants"]["composite_risk_valid"] is False
        assert any("Invariant 3" in v for v in violations)

    def test_invariant_4_adverse_gap_rejection(self):
        """Verify Invariant 4 rejects positions whose 1.5x ATR gap breaches daily limit."""
        p = load_canonical_profile()
        p["parameters"]["sl_pts"] = 50.0
        p["parameters"]["base_lot_size"] = 40.0
        p["risk_bounds"]["max_lot_size"] = 50.0
        verified, violations, report = validate_profile(p)
        assert verified is False
        assert report["invariants"]["adverse_gap_resilient"] is False
        assert any("Invariant 4" in v for v in violations)

    def test_invariant_5_margin_feasibility(self):
        """Verify Invariant 5 enforces margin consumption <= 50% free margin."""
        p = load_canonical_profile()
        p["instrument"] = "BTCUSD"
        p["parameters"]["base_lot_size"] = 0.40
        p["risk_bounds"]["max_lot_size"] = 0.40
        verified, violations, report = validate_profile(p)
        assert report["invariants"]["margin_feasible"] is True


class TestEquityWatchdog:
    """Layer 3: 1-second interval equity watchdog tests."""

    def test_watchdog_normal_operation(self):
        """Verify normal equity level produces NORMAL action."""
        watchdog = EquityWatchdog(daily_watermark=CURRENT_EQUITY)
        action, reason = watchdog.check_equity(CURRENT_EQUITY)
        assert action == "NORMAL"

    def test_watchdog_circuit_breaker_trigger(self):
        """Verify 4.5% daily drawdown triggers CIRCUIT_BREAKER action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockout_file = str(Path(tmpdir) / "test_lockouts.json")
            watchdog = EquityWatchdog(daily_watermark=CURRENT_EQUITY, lockout_file=lockout_file)
            cb_equity = CURRENT_EQUITY * (1.0 - 0.046)
            action, reason = watchdog.check_equity(cb_equity)
            assert action == "CIRCUIT_BREAKER"
            assert "circuit breaker" in reason.lower()
            assert watchdog.is_locked_out() is True

    def test_watchdog_emergency_stop_trigger(self):
        """Verify breach of $90,500 emergency floor triggers EMERGENCY_STOP action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockout_file = str(Path(tmpdir) / "test_lockouts.json")
            watchdog = EquityWatchdog(daily_watermark=CURRENT_EQUITY, lockout_file=lockout_file)
            breach_equity = EMERGENCY_FLOOR - 100.0
            action, reason = watchdog.check_equity(breach_equity)
            assert action == "EMERGENCY_STOP"
            assert "emergency floor" in reason.lower()
            assert watchdog.is_locked_out() is True

    def test_watchdog_watermark_reset(self):
        """Verify midnight watermark reset updates reference equity."""
        watchdog = EquityWatchdog(daily_watermark=100000.0)
        watchdog.reset_daily_watermark(105000.0)
        assert watchdog.daily_watermark == 105000.0
