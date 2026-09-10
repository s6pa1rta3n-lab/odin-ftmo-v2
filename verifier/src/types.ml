type engine_type =
  | LondonReversal
  | OmniBreakout

type risk_model =
  | ConservativeRamp
  | FixedLow
  | AggressiveFlat
  | KellyCriterion
  | AntiMartingale
  | VolatilityScaled
  | EquityCurve

type entry_mode =
  | BlindLimit
  | SweepConfirmation
  | DynamicBuffer
  | TimeWeighted
  | OrderFlowSpreadGate
  | MultiTimeframe
  | HybridSweepTimeSpread
  | StopOrderAtRange
  | CloseConfirmation
  | VolumeSpikeGate
  | RetestEntry
  | MomentumThreshold
  | DualTimeframe
  | HybridRetestVolumeSpread

type pyramid_model =
  | NoPyramid
  | EqualSplit
  | FrontLoaded
  | InversePyramid
  | MomentumConfirmed
  | RiskFreeRunner
  | AdaptiveTranche

type exit_model =
  | FixedSlTp
  | FixedSlTrail
  | AtrDynamicTrail
  | BreakevenRunner
  | TimeBased
  | Chandelier
  | MultiTargetCascade

type market_filter =
  | AtrGate
  | VixRegime
  | SpreadGate
  | NewsBlackout
  | PreSessionMomentum
  | VolatilityPercentile
  | DayOfWeek
  | OrbWidthGate
  | PreOpenTrend
  | LondonSessionResult

type profile_parameters = {
  sl_pts: float;
  tp_pts: float;
  buffer_pts: float;
  trail_trigger_pts: float;
  trail_dist_pts: float;
  max_spread_pts: float;
  max_tranches: int;
  cooldown_seconds: float;
  base_lot_size: float option;
}

type risk_bounds = {
  max_risk_pct: float;
  max_daily_loss_pct: float;
  account_floor: float;
  max_lot_size: float;
}

type profile = {
  profile_id: string;
  engine: engine_type;
  instrument: string;
  version: string;
  risk_model: risk_model;
  entry_mode: entry_mode;
  pyramid_model: pyramid_model;
  exit_model: exit_model;
  filters: market_filter list;
  parameters: profile_parameters;
  risk_bounds: risk_bounds;
}

type invariant_status = {
  total_floor_preserved: bool;
  daily_loss_bounded: bool;
  composite_risk_valid: bool;
  adverse_gap_resilient: bool;
  margin_feasible: bool;
  compatibility_passed: bool;
}

type verification_report = {
  verified: bool;
  profile_id: string;
  invariants: invariant_status;
  worst_case_drawdown_pct: float;
  worst_case_equity: float;
  max_lot_size: float;
  violations: string list;
}

let engine_type_of_string = function
  | "london_reversal" -> Some LondonReversal
  | "omni_breakout" -> Some OmniBreakout
  | _ -> None

let string_of_engine_type = function
  | LondonReversal -> "london_reversal"
  | OmniBreakout -> "omni_breakout"

let risk_model_of_string = function
  | "conservative_ramp" -> Some ConservativeRamp
  | "fixed_low" -> Some FixedLow
  | "aggressive_flat" -> Some AggressiveFlat
  | "kelly_criterion" -> Some KellyCriterion
  | "anti_martingale" -> Some AntiMartingale
  | "volatility_scaled" -> Some VolatilityScaled
  | "equity_curve" -> Some EquityCurve
  | _ -> None

let string_of_risk_model = function
  | ConservativeRamp -> "conservative_ramp"
  | FixedLow -> "fixed_low"
  | AggressiveFlat -> "aggressive_flat"
  | KellyCriterion -> "kelly_criterion"
  | AntiMartingale -> "anti_martingale"
  | VolatilityScaled -> "volatility_scaled"
  | EquityCurve -> "equity_curve"

let entry_mode_of_string = function
  | "blind_limit" -> Some BlindLimit
  | "sweep_confirmation" -> Some SweepConfirmation
  | "dynamic_buffer" -> Some DynamicBuffer
  | "time_weighted" -> Some TimeWeighted
  | "order_flow_spread_gate" -> Some OrderFlowSpreadGate
  | "multi_timeframe" -> Some MultiTimeframe
  | "hybrid_sweep_time_spread" -> Some HybridSweepTimeSpread
  | "stop_order_at_range" -> Some StopOrderAtRange
  | "close_confirmation" -> Some CloseConfirmation
  | "volume_spike_gate" -> Some VolumeSpikeGate
  | "retest_entry" -> Some RetestEntry
  | "momentum_threshold" -> Some MomentumThreshold
  | "dual_timeframe" -> Some DualTimeframe
  | "hybrid_retest_volume_spread" -> Some HybridRetestVolumeSpread
  | _ -> None

let string_of_entry_mode = function
  | BlindLimit -> "blind_limit"
  | SweepConfirmation -> "sweep_confirmation"
  | DynamicBuffer -> "dynamic_buffer"
  | TimeWeighted -> "time_weighted"
  | OrderFlowSpreadGate -> "order_flow_spread_gate"
  | MultiTimeframe -> "multi_timeframe"
  | HybridSweepTimeSpread -> "hybrid_sweep_time_spread"
  | StopOrderAtRange -> "stop_order_at_range"
  | CloseConfirmation -> "close_confirmation"
  | VolumeSpikeGate -> "volume_spike_gate"
  | RetestEntry -> "retest_entry"
  | MomentumThreshold -> "momentum_threshold"
  | DualTimeframe -> "dual_timeframe"
  | HybridRetestVolumeSpread -> "hybrid_retest_volume_spread"

let is_london_entry = function
  | BlindLimit
  | SweepConfirmation
  | DynamicBuffer
  | TimeWeighted
  | OrderFlowSpreadGate
  | MultiTimeframe
  | HybridSweepTimeSpread -> true
  | _ -> false

let is_omni_entry = function
  | StopOrderAtRange
  | CloseConfirmation
  | VolumeSpikeGate
  | RetestEntry
  | MomentumThreshold
  | DualTimeframe
  | HybridRetestVolumeSpread -> true
  | _ -> false

let pyramid_model_of_string = function
  | "no_pyramid" -> Some NoPyramid
  | "equal_split" -> Some EqualSplit
  | "front_loaded" -> Some FrontLoaded
  | "inverse_pyramid" -> Some InversePyramid
  | "momentum_confirmed" -> Some MomentumConfirmed
  | "risk_free_runner" -> Some RiskFreeRunner
  | "adaptive_tranche" -> Some AdaptiveTranche
  | _ -> None

let string_of_pyramid_model = function
  | NoPyramid -> "no_pyramid"
  | EqualSplit -> "equal_split"
  | FrontLoaded -> "front_loaded"
  | InversePyramid -> "inverse_pyramid"
  | MomentumConfirmed -> "momentum_confirmed"
  | RiskFreeRunner -> "risk_free_runner"
  | AdaptiveTranche -> "adaptive_tranche"

let exit_model_of_string = function
  | "fixed_sl_tp" -> Some FixedSlTp
  | "fixed_sl_trail" -> Some FixedSlTrail
  | "atr_dynamic_trail" -> Some AtrDynamicTrail
  | "breakeven_runner" -> Some BreakevenRunner
  | "time_based" -> Some TimeBased
  | "chandelier" -> Some Chandelier
  | "multi_target_cascade" -> Some MultiTargetCascade
  | _ -> None

let string_of_exit_model = function
  | FixedSlTp -> "fixed_sl_tp"
  | FixedSlTrail -> "fixed_sl_trail"
  | AtrDynamicTrail -> "atr_dynamic_trail"
  | BreakevenRunner -> "breakeven_runner"
  | TimeBased -> "time_based"
  | Chandelier -> "chandelier"
  | MultiTargetCascade -> "multi_target_cascade"

let market_filter_of_string = function
  | "atr_gate" -> Some AtrGate
  | "vix_regime" -> Some VixRegime
  | "spread_gate" -> Some SpreadGate
  | "news_blackout" -> Some NewsBlackout
  | "pre_session_momentum" -> Some PreSessionMomentum
  | "volatility_percentile" -> Some VolatilityPercentile
  | "day_of_week" -> Some DayOfWeek
  | "orb_width_gate" -> Some OrbWidthGate
  | "pre_open_trend" -> Some PreOpenTrend
  | "london_session_result" -> Some LondonSessionResult
  | _ -> None

let string_of_market_filter = function
  | AtrGate -> "atr_gate"
  | VixRegime -> "vix_regime"
  | SpreadGate -> "spread_gate"
  | NewsBlackout -> "news_blackout"
  | PreSessionMomentum -> "pre_session_momentum"
  | VolatilityPercentile -> "volatility_percentile"
  | DayOfWeek -> "day_of_week"
  | OrbWidthGate -> "orb_width_gate"
  | PreOpenTrend -> "pre_open_trend"
  | LondonSessionResult -> "london_session_result"
