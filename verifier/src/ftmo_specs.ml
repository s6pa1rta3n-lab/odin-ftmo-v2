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

let initial_account_balance = 100000.0
let current_account_equity = 94939.28
let absolute_total_loss_floor = 90000.0
let emergency_liquidation_floor = 90500.0
let ftmo_max_daily_loss_pct = 0.05
let circuit_breaker_daily_loss_pct = 0.045
let max_composite_risk_ceiling_pct = 0.0130
let max_free_margin_consumption_pct = 0.50
let max_crypto_position_lots = 0.50

let known_instruments = [
  {
    symbol = "US100.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.0;
    default_price = 19500.0;
    default_atr = 40.0;
  };
  {
    symbol = "US30.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.5;
    default_price = 41000.0;
    default_atr = 80.0;
  };
  {
    symbol = "US500.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 0.3;
    default_price = 5600.0;
    default_atr = 15.0;
  };
  {
    symbol = "GER40.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.0;
    default_price = 18500.0;
    default_atr = 45.0;
  };
  {
    symbol = "UK100.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.5;
    default_price = 8300.0;
    default_atr = 25.0;
  };
  {
    symbol = "JPN225.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 0.01;
    commission_per_lot = 0.0;
    typical_spread = 10.0;
    default_price = 37000.0;
    default_atr = 120.0;
  };
  {
    symbol = "FRA40.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.5;
    default_price = 7600.0;
    default_atr = 25.0;
  };
  {
    symbol = "AUS200.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 2.0;
    default_price = 8100.0;
    default_atr = 25.0;
  };
  {
    symbol = "EU50.cash";
    asset_class = Index;
    leverage = 50.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 2.0;
    default_price = 4900.0;
    default_atr = 20.0;
  };
  {
    symbol = "EURUSD";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 10.0;
    commission_per_lot = 3.0;
    typical_spread = 0.2;
    default_price = 1.09;
    default_atr = 0.0050;
  };
  {
    symbol = "GBPUSD";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 10.0;
    commission_per_lot = 3.0;
    typical_spread = 0.5;
    default_price = 1.31;
    default_atr = 0.0060;
  };
  {
    symbol = "USDJPY";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 6.67;
    commission_per_lot = 3.0;
    typical_spread = 0.3;
    default_price = 145.0;
    default_atr = 0.80;
  };
  {
    symbol = "AUDUSD";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 10.0;
    commission_per_lot = 3.0;
    typical_spread = 0.4;
    default_price = 0.67;
    default_atr = 0.0040;
  };
  {
    symbol = "USDCAD";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 7.40;
    commission_per_lot = 3.0;
    typical_spread = 0.5;
    default_price = 1.35;
    default_atr = 0.0050;
  };
  {
    symbol = "USDCHF";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 11.20;
    commission_per_lot = 3.0;
    typical_spread = 0.6;
    default_price = 0.85;
    default_atr = 0.0045;
  };
  {
    symbol = "NZDUSD";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 10.0;
    commission_per_lot = 3.0;
    typical_spread = 0.6;
    default_price = 0.62;
    default_atr = 0.0045;
  };
  {
    symbol = "EURGBP";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 12.50;
    commission_per_lot = 3.0;
    typical_spread = 0.5;
    default_price = 0.84;
    default_atr = 0.0035;
  };
  {
    symbol = "EURJPY";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 6.67;
    commission_per_lot = 3.0;
    typical_spread = 0.8;
    default_price = 158.0;
    default_atr = 0.90;
  };
  {
    symbol = "GBPJPY";
    asset_class = Forex;
    leverage = 100.0;
    contract_size = 100000.0;
    tick_value = 6.67;
    commission_per_lot = 3.0;
    typical_spread = 1.5;
    default_price = 190.0;
    default_atr = 1.10;
  };
  {
    symbol = "XAUUSD";
    asset_class = Commodity;
    leverage = 30.0;
    contract_size = 100.0;
    tick_value = 1.0;
    commission_per_lot = 3.0;
    typical_spread = 2.5;
    default_price = 2500.0;
    default_atr = 15.0;
  };
  {
    symbol = "XAGUSD";
    asset_class = Commodity;
    leverage = 30.0;
    contract_size = 5000.0;
    tick_value = 50.0;
    commission_per_lot = 3.0;
    typical_spread = 0.03;
    default_price = 29.0;
    default_atr = 0.40;
  };
  {
    symbol = "BTCUSD";
    asset_class = Crypto;
    leverage = 1.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 15.0;
    default_price = 60000.0;
    default_atr = 800.0;
  };
  {
    symbol = "ETHUSD";
    asset_class = Crypto;
    leverage = 1.0;
    contract_size = 1.0;
    tick_value = 1.0;
    commission_per_lot = 0.0;
    typical_spread = 1.0;
    default_price = 2500.0;
    default_atr = 45.0;
  };
]

let get_instrument_spec symbol =
  let clean_sym = String.trim symbol in
  List.find_opt (fun inst -> String.equal inst.symbol clean_sym) known_instruments

let max_composite_risk_dollars equity =
  let pct_limit = 0.015 *. equity in
  let floor_margin_limit = 0.25 *. (equity -. absolute_total_loss_floor) in
  Float.min pct_limit (Float.max 0.0 floor_margin_limit)
