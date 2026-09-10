(** FTMO account specifications, asset properties, and risk limit constants. *)

type asset_class =
  | Index
  | Forex
  | Commodity
  | Crypto

type instrument_spec = {
  symbol: string;
  asset_class: asset_class;
  leverage: float;
  contract_size: float;
  tick_value: float;
  commission_per_lot: float;
  typical_spread: float;
  default_price: float;
  default_atr: float;
}

val initial_account_balance : float
val current_account_equity : float
val absolute_total_loss_floor : float
val emergency_liquidation_floor : float
val ftmo_max_daily_loss_pct : float
val circuit_breaker_daily_loss_pct : float
val max_composite_risk_ceiling_pct : float
val max_free_margin_consumption_pct : float
val max_crypto_position_lots : float

(** Retrieves the specification for a known FTMO trading instrument. *)
val get_instrument_spec : string -> instrument_spec option

(** Calculates maximum composite risk budget allowed in dollars for a given equity level. *)
val max_composite_risk_dollars : float -> float
