(** Domain types and conversion signatures for Odin FTMO formal verifier. *)

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

(** Parses an engine type string into an engine_type option. *)
val engine_type_of_string : string -> engine_type option

(** Converts an engine_type variant to its lowercase string representation. *)
val string_of_engine_type : engine_type -> string

(** Parses a risk model string into a risk_model option. *)
val risk_model_of_string : string -> risk_model option

(** Converts a risk_model variant to its lowercase string representation. *)
val string_of_risk_model : risk_model -> string

(** Parses an entry mode string into an entry_mode option. *)
val entry_mode_of_string : string -> entry_mode option

(** Converts an entry_mode variant to its lowercase string representation. *)
val string_of_entry_mode : entry_mode -> string

(** Returns true if the entry mode belongs to the London Reversal engine. *)
val is_london_entry : entry_mode -> bool

(** Returns true if the entry mode belongs to the Omni Breakout engine. *)
val is_omni_entry : entry_mode -> bool

(** Parses a pyramiding model string into a pyramid_model option. *)
val pyramid_model_of_string : string -> pyramid_model option

(** Converts a pyramid_model variant to its lowercase string representation. *)
val string_of_pyramid_model : pyramid_model -> string

(** Parses an exit model string into an exit_model option. *)
val exit_model_of_string : string -> exit_model option

(** Converts an exit_model variant to its lowercase string representation. *)
val string_of_exit_model : exit_model -> string

(** Parses a market filter string into a market_filter option. *)
val market_filter_of_string : string -> market_filter option

(** Converts a market_filter variant to its lowercase string representation. *)
val string_of_market_filter : market_filter -> string
