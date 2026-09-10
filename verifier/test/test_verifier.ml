open Types
open Model_checker

let assert_true name cond =
  if not cond then begin
    Printf.eprintf "FAIL: %s\n" name;
    exit 1
  end else
    Printf.printf "PASS: %s\n" name

let assert_false name cond =
  assert_true name (not cond)

let has_substring str sub =
  try
    let _ = Str.search_forward (Str.regexp_string sub) str 0 in
    true
  with Not_found -> false

let make_base_profile () =
  {
    profile_id = "test_profile_valid";
    engine = LondonReversal;
    instrument = "US100.cash";
    version = "1.0.0";
    risk_model = ConservativeRamp;
    entry_mode = SweepConfirmation;
    pyramid_model = NoPyramid;
    exit_model = FixedSlTrail;
    filters = [AtrGate; SpreadGate];
    parameters =
      {
        sl_pts = 40.0;
        tp_pts = 20.0;
        buffer_pts = 0.0;
        trail_trigger_pts = 15.0;
        trail_dist_pts = 15.0;
        max_spread_pts = 3.0;
        max_tranches = 1;
        cooldown_seconds = 60.0;
        base_lot_size = Some 5.0;
      };
    risk_bounds =
      {
        max_risk_pct = 0.0075;
        max_daily_loss_pct = 0.045;
        account_floor = 90000.0;
        max_lot_size = 15.0;
      };
  }

let test_json_parser () =
  let sample = "{\"name\": \"test\", \"value\": 42.5, \"flag\": true, \"items\": [1, 2, 3], \"nested\": {\"k\": \"v\"}}" in
  let parsed = Json.from_string sample in
  assert_true "json_get_string" (Json.get_string "name" parsed = Some "test");
  assert_true "json_get_float" (Json.get_float "value" parsed = Some 42.5);
  assert_true "json_get_bool" (Json.get_bool "flag" parsed = Some true);
  let items = Json.get_list "items" parsed in
  assert_true "json_get_list" (Option.is_some items && List.length (Option.get items) = 3);
  let serialized = Json.to_string parsed in
  assert_true "json_roundtrip" (String.length serialized > 0)

let test_valid_profile_passes () =
  let p = make_base_profile () in
  let report = verify_profile p in
  assert_true "valid_profile_verified" report.verified;
  assert_true "valid_floor_preserved" report.invariants.total_floor_preserved;
  assert_true "valid_daily_loss_bounded" report.invariants.daily_loss_bounded;
  assert_true "valid_composite_risk" report.invariants.composite_risk_valid;
  assert_true "valid_gap_resilient" report.invariants.adverse_gap_resilient;
  assert_true "valid_margin_feasible" report.invariants.margin_feasible;
  assert_true "valid_compatibility" report.invariants.compatibility_passed;
  assert_true "no_violations" (report.violations = [])

let test_inc01_cross_engine () =
  let p_london_bad = { (make_base_profile ()) with entry_mode = CloseConfirmation } in
  let report1 = verify_profile p_london_bad in
  assert_false "inc01_london_rejected" report1.verified;
  assert_true "inc01_london_violation"
    (List.exists (fun v -> has_substring v "INC-01") report1.violations);

  let p_omni_bad = { (make_base_profile ()) with engine = OmniBreakout; entry_mode = SweepConfirmation } in
  let report2 = verify_profile p_omni_bad in
  assert_false "inc01_omni_rejected" report2.verified;
  assert_true "inc01_omni_violation"
    (List.exists (fun v -> has_substring v "INC-01") report2.violations)

let test_inc02_scale_in_fixed_exit () =
  let p_bad = { (make_base_profile ()) with pyramid_model = EqualSplit; exit_model = FixedSlTp } in
  let report = verify_profile p_bad in
  assert_false "inc02_rejected" report.verified;
  assert_true "inc02_violation"
    (List.exists (fun v -> has_substring v "INC-02") report.violations)

let test_inc03_high_risk_pyramid () =
  let p_bad1 = { (make_base_profile ()) with risk_model = AggressiveFlat; pyramid_model = InversePyramid } in
  let report1 = verify_profile p_bad1 in
  assert_false "inc03_aggressive_inverse_rejected" report1.verified;
  assert_true "inc03_violation1"
    (List.exists (fun v -> has_substring v "INC-03") report1.violations);

  let p_bad2 = { (make_base_profile ()) with risk_model = AntiMartingale; pyramid_model = AdaptiveTranche } in
  let report2 = verify_profile p_bad2 in
  assert_false "inc03_antimartingale_adaptive_rejected" report2.verified;
  assert_true "inc03_violation2"
    (List.exists (fun v -> has_substring v "INC-03") report2.violations)

let test_inc04_scale_in_time_based () =
  let p_bad = { (make_base_profile ()) with pyramid_model = AdaptiveTranche; exit_model = TimeBased } in
  let report = verify_profile p_bad in
  assert_false "inc04_rejected" report.verified;
  assert_true "inc04_violation"
    (List.exists (fun v -> has_substring v "INC-04") report.violations)

let test_inc05_blind_limit_empty_filters () =
  let p_bad = { (make_base_profile ()) with entry_mode = BlindLimit; filters = [] } in
  let report = verify_profile p_bad in
  assert_false "inc05_rejected" report.verified;
  assert_true "inc05_violation"
    (List.exists (fun v -> has_substring v "INC-05") report.violations)

let test_inc06_chandelier_tight_sl () =
  let p_bad =
    {
      (make_base_profile ()) with
      exit_model = Chandelier;
      parameters = { (make_base_profile ()).parameters with sl_pts = 10.0 };
    }
  in
  let report = verify_profile p_bad in
  assert_false "inc06_rejected" report.verified;
  assert_true "inc06_violation"
    (List.exists (fun v -> has_substring v "INC-06") report.violations)

let test_inc07_crypto_large_lot () =
  let p_bad =
    {
      (make_base_profile ()) with
      instrument = "BTCUSD";
      parameters = { (make_base_profile ()).parameters with base_lot_size = Some 1.0 };
      risk_bounds = { (make_base_profile ()).risk_bounds with max_lot_size = 1.0 };
    }
  in
  let report = verify_profile p_bad in
  assert_false "inc07_rejected" report.verified;
  assert_true "inc07_violation"
    (List.exists (fun v -> has_substring v "INC-07") report.violations)

let test_invariant_3_composite_risk () =
  let p_huge_risk =
    {
      (make_base_profile ()) with
      parameters =
        {
          (make_base_profile ()).parameters with
          sl_pts = 80.0;
          base_lot_size = Some 20.0;
          max_tranches = 3;
        };
      risk_bounds = { (make_base_profile ()).risk_bounds with max_lot_size = 30.0 };
    }
  in
  let report = verify_profile p_huge_risk in
  assert_false "inv3_rejected" report.verified;
  assert_false "inv3_flag_false" report.invariants.composite_risk_valid;
  assert_true "inv3_violation_message"
    (List.exists (fun v -> has_substring v "Invariant 3") report.violations)

let test_invariant_4_adverse_gap () =
  let p_gap_risk =
    {
      (make_base_profile ()) with
      pyramid_model = EqualSplit;
      exit_model = FixedSlTrail;
      parameters =
        {
          (make_base_profile ()).parameters with
          sl_pts = 50.0;
          base_lot_size = Some 40.0;
          max_tranches = 1;
        };
      risk_bounds = { (make_base_profile ()).risk_bounds with max_lot_size = 50.0 };
    }
  in
  let report = verify_profile p_gap_risk in
  assert_false "inv4_rejected" report.verified;
  assert_false "inv4_flag_false" report.invariants.adverse_gap_resilient;
  assert_true "inv4_violation_message"
    (List.exists (fun v -> has_substring v "Invariant 4") report.violations)

let test_canonical_profiles_from_disk () =
  let paths =
    [
      "../profiles/london_reversal/london_conservative_sweep_v1.json";
      "../profiles/london_reversal/london_fixed_low_be_v1.json";
      "../profiles/omni_breakout/omni_conservative_close_v1.json";
      "../profiles/omni_breakout/omni_fixed_low_trail_v1.json";
    ]
  in
  List.iter
    (fun p ->
      if Sys.file_exists p then begin
        let json_ast = Json.from_file p in
        match parse_profile json_ast with
        | Ok prof ->
            let report = verify_profile prof in
            assert_true ("disk_profile_verified: " ^ p) report.verified
        | Error err ->
            Printf.eprintf "Failed to parse %s: %s\n" p err;
            exit 1
      end)
    paths

let test_non_positive_sl_rejection () =
  let p_zero_sl =
    {
      (make_base_profile ()) with
      parameters = { (make_base_profile ()).parameters with sl_pts = 0.0 };
    }
  in
  let report_zero = verify_profile p_zero_sl in
  assert_false "zero_sl_rejected" report_zero.verified;
  assert_false "zero_sl_inv1_failed" report_zero.invariants.total_floor_preserved;
  assert_false "zero_sl_inv2_failed" report_zero.invariants.daily_loss_bounded;
  assert_true "zero_sl_violation"
    (List.exists (fun v -> has_substring v "sl_pts must be positive") report_zero.violations);

  let p_neg_sl =
    {
      (make_base_profile ()) with
      parameters = { (make_base_profile ()).parameters with sl_pts = -40.0 };
    }
  in
  let report_neg = verify_profile p_neg_sl in
  assert_false "neg_sl_rejected" report_neg.verified;
  assert_false "neg_sl_inv1_failed" report_neg.invariants.total_floor_preserved;
  assert_false "neg_sl_inv2_failed" report_neg.invariants.daily_loss_bounded;
  assert_true "neg_sl_violation"
    (List.exists (fun v -> has_substring v "sl_pts must be positive") report_neg.violations)

let test_extreme_lot_size_rejection () =
  let p_base_exceeds =
    {
      (make_base_profile ()) with
      parameters = { (make_base_profile ()).parameters with base_lot_size = Some 80.0 };
      risk_bounds = { (make_base_profile ()).risk_bounds with max_lot_size = 15.0 };
    }
  in
  let report_exceeds = verify_profile p_base_exceeds in
  assert_false "base_lot_exceeds_max_rejected" report_exceeds.verified;
  assert_false "base_lot_exceeds_inv1_failed" report_exceeds.invariants.total_floor_preserved;
  assert_true "base_lot_exceeds_violation"
    (List.exists (fun v -> has_substring v "Base lot size") report_exceeds.violations);

  let p_floor_breach =
    {
      (make_base_profile ()) with
      parameters = { (make_base_profile ()).parameters with base_lot_size = Some 80.0; sl_pts = 40.0 };
      risk_bounds = { (make_base_profile ()).risk_bounds with max_lot_size = 80.0; max_risk_pct = 0.50 };
    }
  in
  let report_breach = verify_profile p_floor_breach in
  assert_false "extreme_lot_floor_breach_rejected" report_breach.verified;
  assert_false "extreme_lot_floor_breach_inv1_failed" report_breach.invariants.total_floor_preserved;
  assert_true "extreme_lot_floor_breach_violation"
    (List.exists (fun v -> has_substring v "Invariant 1") report_breach.violations)

let () =
  Printf.printf "Running OCaml Formal Verifier Test Suite...\n";
  test_json_parser ();
  test_valid_profile_passes ();
  test_inc01_cross_engine ();
  test_inc02_scale_in_fixed_exit ();
  test_inc03_high_risk_pyramid ();
  test_inc04_scale_in_time_based ();
  test_inc05_blind_limit_empty_filters ();
  test_inc06_chandelier_tight_sl ();
  test_inc07_crypto_large_lot ();
  test_invariant_3_composite_risk ();
  test_invariant_4_adverse_gap ();
  test_canonical_profiles_from_disk ();
  test_non_positive_sl_rejection ();
  test_extreme_lot_size_rejection ();
  Printf.printf "All OCaml Formal Verifier tests passed successfully!\n"
