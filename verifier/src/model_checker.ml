open Types
open Ftmo_specs

let parse_profile json =
  let profile_id =
    match Json.get_string "profile_id" json with
    | Some s -> s
    | None -> "unknown_profile"
  in

  let engine =
    match Json.get_string "engine" json with
    | Some s ->
        (match engine_type_of_string s with
        | Some e -> Ok e
        | None -> Error ("Invalid engine type: " ^ s))
    | None -> Error "Missing required field: engine"
  in

  let instrument =
    match Json.get_string "instrument" json with
    | Some s -> Ok s
    | None -> Error "Missing required field: instrument"
  in

  let version =
    match Json.get_string "version" json with
    | Some s -> s
    | None -> "1.0.0"
  in

  let dimensions_obj = Json.get_field "dimensions" json in
  let parameters_obj = Json.get_field "parameters" json in
  let risk_bounds_obj = Json.get_field "risk_bounds" json in

  match (engine, instrument, dimensions_obj, parameters_obj, risk_bounds_obj) with
  | (Ok eng, Ok inst, Some dims, Some params, Some bounds) ->
      let risk_model_res =
        match Json.get_string "risk_model" dims with
        | Some s ->
            (match risk_model_of_string s with
            | Some rm -> Ok rm
            | None -> Error ("Invalid risk_model: " ^ s))
        | None -> Error "Missing required field: dimensions.risk_model"
      in
      let entry_mode_res =
        match Json.get_string "entry_mode" dims with
        | Some s ->
            (match entry_mode_of_string s with
            | Some em -> Ok em
            | None -> Error ("Invalid entry_mode: " ^ s))
        | None -> Error "Missing required field: dimensions.entry_mode"
      in
      let pyramid_model_res =
        match Json.get_string "pyramid_model" dims with
        | Some s ->
            (match pyramid_model_of_string s with
            | Some pm -> Ok pm
            | None -> Error ("Invalid pyramid_model: " ^ s))
        | None -> Error "Missing required field: dimensions.pyramid_model"
      in
      let exit_model_res =
        match Json.get_string "exit_model" dims with
        | Some s ->
            (match exit_model_of_string s with
            | Some xm -> Ok xm
            | None -> Error ("Invalid exit_model: " ^ s))
        | None -> Error "Missing required field: dimensions.exit_model"
      in
      let filters_res =
        match Json.get_list "filters" dims with
        | Some flist ->
            let parsed_filters =
              List.filter_map
                (function
                  | Json.JString s -> market_filter_of_string s
                  | _ -> None)
                flist
            in
            Ok parsed_filters
        | None -> Ok []
      in

      let sl_pts = Option.value (Json.get_float "sl_pts" params) ~default:40.0 in
      let tp_pts = Option.value (Json.get_float "tp_pts" params) ~default:20.0 in
      let buffer_pts = Option.value (Json.get_float "buffer_pts" params) ~default:0.0 in
      let trail_trigger_pts = Option.value (Json.get_float "trail_trigger_pts" params) ~default:0.0 in
      let trail_dist_pts = Option.value (Json.get_float "trail_dist_pts" params) ~default:0.0 in
      let max_spread_pts = Option.value (Json.get_float "max_spread_pts" params) ~default:3.0 in
      let max_tranches = Option.value (Json.get_int "max_tranches" params) ~default:1 in
      let cooldown_seconds = Option.value (Json.get_float "cooldown_seconds" params) ~default:60.0 in
      let base_lot_size = Json.get_float "base_lot_size" params in

      let max_risk_pct = Option.value (Json.get_float "max_risk_pct" bounds) ~default:0.0075 in
      let max_daily_loss_pct = Option.value (Json.get_float "max_daily_loss_pct" bounds) ~default:0.045 in
      let account_floor = Option.value (Json.get_float "account_floor" bounds) ~default:90000.0 in
      let max_lot_size = Option.value (Json.get_float "max_lot_size" bounds) ~default:15.0 in

      (match (risk_model_res, entry_mode_res, pyramid_model_res, exit_model_res, filters_res) with
      | (Ok rm, Ok em, Ok pm, Ok xm, Ok flts) ->
          Ok
            {
              profile_id;
              engine = eng;
              instrument = inst;
              version;
              risk_model = rm;
              entry_mode = em;
              pyramid_model = pm;
              exit_model = xm;
              filters = flts;
              parameters =
                {
                  sl_pts;
                  tp_pts;
                  buffer_pts;
                  trail_trigger_pts;
                  trail_dist_pts;
                  max_spread_pts;
                  max_tranches;
                  cooldown_seconds;
                  base_lot_size;
                };
              risk_bounds =
                {
                  max_risk_pct;
                  max_daily_loss_pct;
                  account_floor;
                  max_lot_size;
                };
            }
      | (Error err, _, _, _, _)
      | (_, Error err, _, _, _)
      | (_, _, Error err, _, _)
      | (_, _, _, Error err, _)
      | (_, _, _, _, Error err) -> Error err)
  | (Error err, _, _, _, _)
  | (_, Error err, _, _, _) -> Error err
  | _ -> Error "Missing one or more required objects: dimensions, parameters, risk_bounds"

let check_incompatibilities profile =
  let violations = ref [] in
  let add v = violations := v :: !violations in

  if profile.engine = LondonReversal && not (is_london_entry profile.entry_mode) then
    add ("INC-01: London Reversal engine assigned Omni entry mode: " ^ string_of_entry_mode profile.entry_mode);

  if profile.engine = OmniBreakout && not (is_omni_entry profile.entry_mode) then
    add ("INC-01: Omni Breakout engine assigned London entry mode: " ^ string_of_entry_mode profile.entry_mode);

  let is_scale_in_pyramid = function
    | EqualSplit | FrontLoaded | InversePyramid | AdaptiveTranche | MomentumConfirmed -> true
    | NoPyramid | RiskFreeRunner -> false
  in

  if is_scale_in_pyramid profile.pyramid_model && profile.exit_model = FixedSlTp then
    add "INC-02: Scale-in pyramiding model requires trailing stop or breakeven exit, incompatible with static fixed_sl_tp";

  let is_high_risk = function
    | AggressiveFlat | AntiMartingale -> true
    | _ -> false
  in
  let is_backloaded_or_adaptive = function
    | InversePyramid | AdaptiveTranche -> true
    | _ -> false
  in

  if is_high_risk profile.risk_model && is_backloaded_or_adaptive profile.pyramid_model then
    add "INC-03: High-exposure risk model combined with back-loaded or adaptive pyramiding violates drawdown safety";

  let is_complex_scale_in = function
    | AdaptiveTranche | MomentumConfirmed -> true
    | _ -> false
  in

  if is_complex_scale_in profile.pyramid_model && profile.exit_model = TimeBased then
    add "INC-04: Multi-tranche scale-in model is incompatible with 120-minute time_based exit";

  if profile.entry_mode = BlindLimit && profile.filters = [] then
    add "INC-05: Blind limit entry requires at least one market context filter to prevent momentum flush stop-outs";

  if profile.exit_model = Chandelier
     && (profile.parameters.sl_pts < 20.0
        || profile.risk_model = AggressiveFlat
        || profile.risk_bounds.max_risk_pct > 0.010) then
    add "INC-06: Chandelier wide stop exit (3x ATR) is incompatible with tight SL (<20 pts) or aggressive risk sizing";

  let is_crypto = String.equal profile.instrument "BTCUSD" || String.equal profile.instrument "ETHUSD" in
  if is_crypto then begin
    if profile.risk_bounds.max_lot_size > max_crypto_position_lots then
      add "INC-07: Crypto instruments (1:1 leverage) require position size <= 0.50 lots to preserve margin ceiling";
    match profile.parameters.base_lot_size with
    | Some lots when lots > max_crypto_position_lots ->
        add "INC-07: Crypto base lot size exceeds 0.50 lots on 1:1 leverage account"
    | _ -> ()
  end;

  List.rev !violations

let compute_lot_size profile spec current_equity =
  let base_risk_pct =
    match profile.risk_model with
    | ConservativeRamp ->
        if current_equity < 98000.0 then 0.0025
        else if current_equity < 102000.0 then 0.0050
        else 0.0075
    | FixedLow -> 0.0035
    | AggressiveFlat -> 0.0075
    | KellyCriterion -> 0.0075
    | AntiMartingale -> 0.0075
    | VolatilityScaled -> 0.0060
    | EquityCurve -> 0.0050
  in
  let effective_risk_pct = Float.min base_risk_pct profile.risk_bounds.max_risk_pct in
  let risk_dollars = current_equity *. effective_risk_pct in
  let sl = profile.parameters.sl_pts in
  if sl <= 0.0 then 0.0
  else
    let calculated_lots = risk_dollars /. (sl *. spec.tick_value) in
    let lot_with_base =
      match profile.parameters.base_lot_size with
      | Some bl -> Float.max bl calculated_lots
      | None -> calculated_lots
    in
    let capped_lots = Float.min lot_with_base profile.risk_bounds.max_lot_size in
    let rounded_lots = Float.round (capped_lots *. 100.0) /. 100.0 in
    Float.max 0.01 rounded_lots

let verify_profile profile =
  let violations = ref (check_incompatibilities profile) in
  let add_v v = violations := v :: !violations in

  let spec =
    match get_instrument_spec profile.instrument with
    | Some s -> s
    | None ->
        {
          symbol = profile.instrument;
          asset_class = Index;
          leverage = 50.0;
          contract_size = 1.0;
          tick_value = 1.0;
          commission_per_lot = 0.0;
          typical_spread = 1.5;
          default_price = 19000.0;
          default_atr = 40.0;
        }
  in

  let valid_sl = profile.parameters.sl_pts > 0.0 in
  if not valid_sl then begin
    add_v (Printf.sprintf "Invariant 1 Violation: Stop loss parameter sl_pts must be positive (got %.2f)" profile.parameters.sl_pts);
    add_v (Printf.sprintf "Invariant 2 Violation: Stop loss parameter sl_pts must be positive (got %.2f)" profile.parameters.sl_pts);
  end;

  let base_lot_exceeds_max =
    match profile.parameters.base_lot_size with
    | Some bl -> bl > profile.risk_bounds.max_lot_size
    | None -> false
  in
  if base_lot_exceeds_max then
    add_v (Printf.sprintf "Invariant 1 Violation: Base lot size %.2f exceeds maximum lot size %.2f"
             (Option.value profile.parameters.base_lot_size ~default:0.0)
             profile.risk_bounds.max_lot_size);

  let initial_lots = compute_lot_size profile spec current_account_equity in

  let max_tranches_count =
    if profile.pyramid_model = NoPyramid then 1
    else Float.to_int (Float.max 1.0 (float_of_int profile.parameters.max_tranches))
  in

  let total_position_lots = initial_lots *. float_of_int max_tranches_count in

  let composite_risk_dollars =
    let sl = profile.parameters.sl_pts in
    (total_position_lots *. sl *. spec.tick_value)
    +. (total_position_lots *. spec.commission_per_lot)
  in

  let max_composite_budget = max_composite_risk_dollars current_account_equity in

  let inv3_passed =
    valid_sl
    && composite_risk_dollars <= max_composite_budget
    && (composite_risk_dollars /. current_account_equity) <= max_composite_risk_ceiling_pct
  in

  if not inv3_passed && valid_sl then
    add_v (Printf.sprintf "Invariant 3 Violation: Composite risk $%.2f exceeds ceiling $%.2f (1.30%% limit)"
             composite_risk_dollars max_composite_budget);

  let shock_effective_sl =
    profile.parameters.sl_pts
    +. (1.5 *. spec.default_atr)
    +. (3.0 *. spec.typical_spread)
  in
  let shock_loss_dollars =
    (total_position_lots *. shock_effective_sl *. spec.tick_value)
    +. (total_position_lots *. spec.commission_per_lot)
  in
  let circuit_breaker_limit = circuit_breaker_daily_loss_pct *. current_account_equity in

  let inv4_passed = valid_sl && shock_loss_dollars <= circuit_breaker_limit in

  if not inv4_passed && valid_sl then
    add_v (Printf.sprintf "Invariant 4 Violation: Adverse gap shock loss $%.2f exceeds daily circuit breaker limit $%.2f"
             shock_loss_dollars circuit_breaker_limit);

  let margin_required =
    (total_position_lots *. spec.contract_size *. spec.default_price) /. spec.leverage
  in
  let max_margin_allowed = max_free_margin_consumption_pct *. current_account_equity in

  let crypto_lots_ok =
    if spec.asset_class = Crypto then
      total_position_lots <= max_crypto_position_lots
    else
      true
  in

  let inv5_passed = valid_sl && margin_required <= max_margin_allowed && crypto_lots_ok in

  if not inv5_passed && valid_sl then begin
    if not crypto_lots_ok then
      add_v (Printf.sprintf "Invariant 5 Violation: Crypto position size %.2f lots exceeds 0.50 lot cap" total_position_lots)
    else
      add_v (Printf.sprintf "Invariant 5 Violation: Margin required $%.2f exceeds 50%% free margin $%.2f"
               margin_required max_margin_allowed)
  end;

  let single_trade_normal_loss =
    (initial_lots *. profile.parameters.sl_pts *. spec.tick_value)
    +. (initial_lots *. spec.commission_per_lot)
  in

  let inv2_passed =
    valid_sl
    && single_trade_normal_loss <= circuit_breaker_limit
    && profile.risk_bounds.max_daily_loss_pct <= circuit_breaker_daily_loss_pct
  in

  if not inv2_passed && valid_sl then
    add_v (Printf.sprintf "Invariant 2 Violation: Trade risk $%.2f breaches 4.5%% daily loss ceiling $%.2f"
             single_trade_normal_loss circuit_breaker_limit);

  let sim_equity = ref current_account_equity in
  let sim_watermark = ref current_account_equity in
  let sim_daily_loss = ref 0.0 in
  let min_equity_reached = ref current_account_equity in
  let sim_floor_breached = ref false in

  for _ = 1 to 10 do
    if !sim_equity > emergency_liquidation_floor && valid_sl && not base_lot_exceeds_max then begin
      let lots = compute_lot_size profile spec !sim_equity in
      let step_loss =
        (lots *. profile.parameters.sl_pts *. spec.tick_value)
        +. (lots *. spec.commission_per_lot)
      in
      if !sim_equity -. step_loss < absolute_total_loss_floor then begin
        sim_floor_breached := true;
        min_equity_reached := Float.min !min_equity_reached (!sim_equity -. step_loss)
      end;
      let max_daily_allowance = circuit_breaker_daily_loss_pct *. !sim_watermark in

      if !sim_daily_loss +. step_loss >= max_daily_allowance then begin
        let loss_applied = Float.min step_loss (max_daily_allowance -. !sim_daily_loss) in
        sim_equity := !sim_equity -. loss_applied;
        min_equity_reached := Float.min !min_equity_reached !sim_equity;
        sim_watermark := !sim_equity;
        sim_daily_loss := 0.0
      end else begin
        sim_equity := !sim_equity -. step_loss;
        sim_daily_loss := !sim_daily_loss +. step_loss;
        min_equity_reached := Float.min !min_equity_reached !sim_equity
      end;

      if !sim_equity < absolute_total_loss_floor then
        sim_floor_breached := true
    end
  done;

  let inv1_passed =
    valid_sl
    && not base_lot_exceeds_max
    && not !sim_floor_breached
    && !min_equity_reached >= absolute_total_loss_floor
  in

  if not inv1_passed && valid_sl && not base_lot_exceeds_max then
    add_v (Printf.sprintf "Invariant 1 Violation: Simulated worst-case equity $%.2f dropped below absolute floor $%.2f"
             !min_equity_reached absolute_total_loss_floor);

  let compatibility_passed = (check_incompatibilities profile = []) in
  let all_invariants_passed =
    inv1_passed && inv2_passed && inv3_passed && inv4_passed && inv5_passed && compatibility_passed && (!violations = [])
  in

  let worst_case_drawdown_pct =
    (current_account_equity -. !min_equity_reached) /. current_account_equity
  in

  {
    verified = all_invariants_passed;
    profile_id = profile.profile_id;
    invariants =
      {
        total_floor_preserved = inv1_passed;
        daily_loss_bounded = inv2_passed;
        composite_risk_valid = inv3_passed;
        adverse_gap_resilient = inv4_passed;
        margin_feasible = inv5_passed;
        compatibility_passed;
      };
    worst_case_drawdown_pct;
    worst_case_equity = !min_equity_reached;
    max_lot_size = total_position_lots;
    violations = List.rev !violations;
  }

let json_of_report report =
  let inv_fields =
    [
      ("total_floor_preserved", Json.JBool report.invariants.total_floor_preserved);
      ("daily_loss_bounded", Json.JBool report.invariants.daily_loss_bounded);
      ("composite_risk_valid", Json.JBool report.invariants.composite_risk_valid);
      ("adverse_gap_resilient", Json.JBool report.invariants.adverse_gap_resilient);
      ("margin_feasible", Json.JBool report.invariants.margin_feasible);
      ("compatibility_passed", Json.JBool report.invariants.compatibility_passed);
    ]
  in
  let violation_items = List.map (fun v -> Json.JString v) report.violations in
  Json.JAssoc
    [
      ("verified", Json.JBool report.verified);
      ("profile_id", Json.JString report.profile_id);
      ("invariants", Json.JAssoc inv_fields);
      ("worst_case_drawdown_pct", Json.JFloat report.worst_case_drawdown_pct);
      ("worst_case_equity", Json.JFloat report.worst_case_equity);
      ("max_lot_size", Json.JFloat report.max_lot_size);
      ("violations", Json.JList violation_items);
    ]
