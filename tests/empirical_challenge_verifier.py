"""Adversarial stress harness for OCaml verifier and Python runtime validator.

Generates adversarial profiles violating FTMO constraints, architectural incompatibilities,
and malformed parameters, testing whether both verification layers reject 100% of cases.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_base_valid_profile() -> Dict[str, Any]:
    """Return a baseline canonical valid profile for mutation."""
    return {
        "profile_id": "london_reversal|conservative_ramp|sweep_confirmation|no_pyramid|fixed_sl_trail|spread_gate|US100.cash",
        "engine": "london_reversal",
        "instrument": "US100.cash",
        "version": "1.0.0",
        "dimensions": {
            "risk_model": "conservative_ramp",
            "entry_mode": "sweep_confirmation",
            "pyramid_model": "no_pyramid",
            "exit_model": "fixed_sl_trail",
            "filters": ["spread_gate"],
        },
        "parameters": {
            "sl_pts": 40.0,
            "tp_pts": 20.0,
            "buffer_pts": 0.0,
            "trail_trigger_pts": 15.0,
            "trail_dist_pts": 15.0,
            "max_spread_pts": 3.0,
            "max_tranches": 1,
            "cooldown_seconds": 60.0,
            "base_lot_size": 2.0,
        },
        "risk_bounds": {
            "max_risk_pct": 0.0075,
            "max_daily_loss_pct": 0.045,
            "account_floor": 90000.0,
            "max_lot_size": 15.0,
        },
    }


def generate_adversarial_profiles() -> List[Tuple[str, str, Any]]:
    """Generate categorized adversarial test cases.

    Returns list of (case_id, description, profile_dict_or_raw_string).
    """
    cases = []

    p1 = get_base_valid_profile()
    p1["profile_id"] = "adv_floor_breach"
    p1["parameters"]["base_lot_size"] = 80.0
    p1["risk_bounds"]["max_risk_pct"] = 0.50
    cases.append(("ADV-01-FLOOR", "Extreme lot size triggering simulated floor breach", p1))

    p2 = get_base_valid_profile()
    p2["profile_id"] = "adv_daily_loss_breach_pct"
    p2["risk_bounds"]["max_daily_loss_pct"] = 0.08
    cases.append(("ADV-02-DAILY-PCT", "max_daily_loss_pct set to 8% (exceeds 4.5% limit)", p2))

    p3 = get_base_valid_profile()
    p3["profile_id"] = "adv_daily_loss_trade_risk"
    p3["parameters"]["sl_pts"] = 250.0
    p3["parameters"]["base_lot_size"] = 20.0
    cases.append(("ADV-03-TRADE-RISK", "Single trade risk breaches daily 4.5% ceiling", p3))

    p4 = get_base_valid_profile()
    p4["profile_id"] = "adv_inc01_london_omni"
    p4["dimensions"]["entry_mode"] = "volume_spike_gate"
    cases.append(("ADV-04-INC01-LONDON", "INC-01: London engine assigned Omni breakout entry", p4))

    p5 = get_base_valid_profile()
    p5["profile_id"] = "adv_inc01_omni_london"
    p5["engine"] = "omni_breakout"
    p5["dimensions"]["entry_mode"] = "sweep_confirmation"
    cases.append(("ADV-05-INC01-OMNI", "INC-01: Omni engine assigned London reversal entry", p5))

    p6 = get_base_valid_profile()
    p6["profile_id"] = "adv_inc02_scale_in_fixed"
    p6["dimensions"]["pyramid_model"] = "equal_split"
    p6["dimensions"]["exit_model"] = "fixed_sl_tp"
    cases.append(("ADV-06-INC02", "INC-02: Scale-in pyramiding with static fixed SL/TP", p6))

    p7 = get_base_valid_profile()
    p7["profile_id"] = "adv_inc03_high_risk_backloaded"
    p7["dimensions"]["risk_model"] = "aggressive_flat"
    p7["dimensions"]["pyramid_model"] = "inverse_pyramid"
    cases.append(("ADV-07-INC03", "INC-03: High risk model with backloaded pyramiding", p7))

    p8 = get_base_valid_profile()
    p8["profile_id"] = "adv_inc04_scale_in_time"
    p8["dimensions"]["pyramid_model"] = "adaptive_tranche"
    p8["dimensions"]["exit_model"] = "time_based"
    cases.append(("ADV-08-INC04", "INC-04: Adaptive tranche scale-in with time-based exit", p8))

    p9 = get_base_valid_profile()
    p9["profile_id"] = "adv_inc05_blind_no_filter"
    p9["dimensions"]["entry_mode"] = "blind_limit"
    p9["dimensions"]["filters"] = []
    cases.append(("ADV-09-INC05", "INC-05: Blind limit entry without market context filters", p9))

    p10 = get_base_valid_profile()
    p10["profile_id"] = "adv_inc06_chandelier_tight"
    p10["dimensions"]["exit_model"] = "chandelier"
    p10["parameters"]["sl_pts"] = 10.0
    cases.append(("ADV-10-INC06", "INC-06: Chandelier wide stop exit with tight 10pt SL", p10))

    p11 = get_base_valid_profile()
    p11["profile_id"] = "adv_inc07_crypto_max_lots"
    p11["instrument"] = "BTCUSD"
    p11["risk_bounds"]["max_lot_size"] = 2.0
    cases.append(("ADV-11-INC07-MAX", "INC-07: Crypto position size max_lot_size > 0.50 lots", p11))

    p12 = get_base_valid_profile()
    p12["profile_id"] = "adv_inc07_crypto_base_lots"
    p12["instrument"] = "ETHUSD"
    p12["parameters"]["base_lot_size"] = 1.0
    cases.append(("ADV-12-INC07-BASE", "INC-07: Crypto base lot size > 0.50 lots", p12))

    p13 = get_base_valid_profile()
    p13["profile_id"] = "adv_excessive_margin"
    p13["parameters"]["base_lot_size"] = 250.0
    p13["risk_bounds"]["max_lot_size"] = 250.0
    cases.append(("ADV-13-MARGIN", "Margin requirement exceeds 50% free margin ceiling", p13))

    p14 = get_base_valid_profile()
    p14["profile_id"] = "adv_negative_sl"
    p14["parameters"]["sl_pts"] = -40.0
    cases.append(("ADV-14-NEG-SL", "Negative stop loss parameter (-40.0 pts)", p14))

    p15 = get_base_valid_profile()
    p15["profile_id"] = "adv_zero_sl"
    p15["parameters"]["sl_pts"] = 0.0
    cases.append(("ADV-15-ZERO-SL", "Zero stop loss parameter (0.0 pts)", p15))

    cases.append(("ADV-16-NAN", "NaN value in sl_pts parameter",
                  '{"profile_id":"adv_nan","engine":"london_reversal","instrument":"US100.cash","dimensions":{"risk_model":"conservative_ramp","entry_mode":"sweep_confirmation","pyramid_model":"no_pyramid","exit_model":"fixed_sl_trail","filters":[]},"parameters":{"sl_pts":NaN},"risk_bounds":{}}'))

    cases.append(("ADV-17-CORRUPT-JSON", "Corrupt non-JSON payload", "{corrupt: true, invalid_json: [}"))

    cases.append(("ADV-18-EMPTY-JSON", "Empty JSON dictionary", "{}"))

    return cases


def run_ocaml_verifier(verifier_bin: Path, profile_file: Path) -> Tuple[bool, int, str]:
    """Execute OCaml formal verifier binary on profile path.

    Returns (is_verified, returncode, output_str).
    """
    cmd = [str(verifier_bin), str(profile_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout.strip()
    if res.returncode == 0:
        try:
            parsed = json.loads(out)
            return bool(parsed.get("verified", False)), res.returncode, out
        except Exception:
            return True, res.returncode, out
    return False, res.returncode, (out + " " + res.stderr.strip()).strip()


def run_python_validator(validator_py: Path, profile_file: Path) -> Tuple[bool, int, str]:
    """Execute Python runtime validator on profile path.

    Returns (is_verified, returncode, output_str).
    """
    cmd = [sys.executable, str(validator_py), str(profile_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout.strip()
    if res.returncode == 0:
        try:
            parsed = json.loads(out)
            return bool(parsed.get("verified", False)), res.returncode, out
        except Exception:
            return True, res.returncode, out
    return False, res.returncode, (out + " " + res.stderr.strip()).strip()


def run_all_stress_tests() -> Dict[str, Any]:
    """Execute stress test suite across both verifiers and return detailed results."""
    project_root = Path(__file__).resolve().parent.parent
    ocaml_bin = project_root / "verifier" / "bin" / "main.exe"
    validator_py = project_root / "verifier" / "validator.py"

    assert ocaml_bin.exists(), f"OCaml binary missing at {ocaml_bin}"
    assert validator_py.exists(), f"Python validator missing at {validator_py}"

    cases = generate_adversarial_profiles()
    results = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for case_id, desc, profile_data in cases:
            file_path = tmp_path / f"{case_id}.json"
            if isinstance(profile_data, str):
                file_path.write_text(profile_data, encoding="utf-8")
            else:
                file_path.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")

            ocaml_ver, ocaml_rc, ocaml_msg = run_ocaml_verifier(ocaml_bin, file_path)
            py_ver, py_rc, py_msg = run_python_validator(validator_py, file_path)

            ocaml_rejected = (not ocaml_ver) or (ocaml_rc != 0)
            py_rejected = (not py_ver) or (py_rc != 0)

            both_rejected = ocaml_rejected and py_rejected

            results.append({
                "case_id": case_id,
                "description": desc,
                "ocaml_verified": ocaml_ver,
                "ocaml_exit_code": ocaml_rc,
                "ocaml_rejected": ocaml_rejected,
                "py_verified": py_ver,
                "py_exit_code": py_rc,
                "py_rejected": py_rejected,
                "both_rejected": both_rejected,
            })

    total = len(results)
    rejected_both = sum(1 for r in results if r["both_rejected"])
    rejection_rate = (rejected_both / total) * 100.0

    return {
        "total_cases": total,
        "rejected_both": rejected_both,
        "rejection_rate_pct": rejection_rate,
        "cases": results,
    }


if __name__ == "__main__":
    summary = run_all_stress_tests()
    print(f"Total adversarial cases: {summary['total_cases']}")
    print(f"Rejected by BOTH verifiers: {summary['rejected_both']} / {summary['total_cases']}")
    print(f"Empirical Rejection Rate: {summary['rejection_rate_pct']:.2f}%")
    for c in summary["cases"]:
        status = "PASSED (REJECTED)" if c["both_rejected"] else "FAILED (ACCEPTED)"
        print(f"  [{c['case_id']}] {status} | OCaml RC: {c['ocaml_exit_code']} | Py RC: {c['py_exit_code']} | {c['description']}")
    if summary["rejection_rate_pct"] < 100.0:
        sys.exit(1)
    sys.exit(0)
