"""Smoke test: runs a single London Reversal backtest on the existing US100 data."""

import sys
sys.path.insert(0, "/Users/solveetcoagula/Desktop/google_cloud/backtester")

from engine import (
    BacktestEngine,
    BacktestProfile,
    CandleDataLoader,
    EngineType,
    ExitModel,
    PyramidModel,
    RiskModel,
)
from datetime import datetime, timezone

DATA_DIR = "/Users/solveetcoagula/Desktop/google_cloud/data/raw"

profile = BacktestProfile(
    engine=EngineType.LONDON_REVERSAL,
    risk_model=RiskModel.FIXED_LOW,
    entry_mode="blind_limit",
    pyramid_model=PyramidModel.NO_PYRAMID,
    exit_model=ExitModel.FIXED_SL_TP,
    filters=[],
    instrument="usatechidxusd",
)

loader = CandleDataLoader(DATA_DIR)
start = datetime(2026, 6, 1, tzinfo=timezone.utc)
end = datetime(2026, 9, 1, tzinfo=timezone.utc)

print(f"Loading candles for {profile.instrument} from {start} to {end}...")
candles = loader.load(profile.instrument, start, end)
print(f"Loaded {len(candles)} candles")

if not candles:
    print("No candles loaded. Check data path and symbol matching.")
    sys.exit(1)

print(f"First candle: {candles[0].timestamp} | Last candle: {candles[-1].timestamp}")

engine = BacktestEngine(
    profile=profile,
    candles=candles,
    starting_equity=100000.0,
    tick_value=1.0,
    commission_per_lot=0.0,
)

print("\nRunning backtest...")
metrics = engine.run()

print(f"\n{'='*60}")
print(f"BACKTEST RESULTS: {profile.profile_id()}")
print(f"{'='*60}")
print(f"Total Trades:       {metrics.total_trades}")
print(f"Win Rate:           {metrics.win_rate:.1%}")
print(f"Total PnL:          ${metrics.total_pnl:,.2f}")
print(f"Sharpe Ratio:       {metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown:       {metrics.max_drawdown_pct:.2%} (${metrics.max_drawdown:,.2f})")
print(f"Profit Factor:      {metrics.profit_factor:.2f}")
print(f"Avg Win:            ${metrics.avg_win:,.2f}")
print(f"Avg Loss:           ${metrics.avg_loss:,.2f}")
print(f"Avg R:R:            {metrics.avg_rr:.2f}")
print(f"Max Consec Losses:  {metrics.max_consecutive_losses}")
print(f"Tournament Score:   {metrics.tournament_score():.4f}")
print(f"Ending Equity:      ${metrics.ending_equity:,.2f}")
