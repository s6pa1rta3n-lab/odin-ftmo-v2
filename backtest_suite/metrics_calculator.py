import pandas as pd
import numpy as np
import os

def calculate_and_report_metrics(trades_list, start_balance=100000.0, risk_per_trade=1000.0, output_csv="trades.csv"):
    if not trades_list:
        print("No trades executed.")
        return

    df = pd.DataFrame(trades_list)
    if 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'])
        df.set_index('datetime', inplace=True)
    
    df['cum_pnl'] = df['pnl'].cumsum()
    df['equity'] = start_balance + df['cum_pnl']

    total_trades = len(df)
    winning_trades = df[df['pnl'] > 0]
    losing_trades = df[df['pnl'] <= 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    
    avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
    avg_loss = abs(losing_trades['pnl'].mean()) if not losing_trades.empty else 0
    avg_rr = (avg_win / avg_loss) if avg_loss > 0 else float('inf')

    # Max Drawdown Calculation
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = df['equity'] - df['peak']
    df['drawdown_pct'] = (df['drawdown'] / df['peak']) * 100
    max_drawdown = df['drawdown'].min()
    max_drawdown_pct = df['drawdown_pct'].min()

    # Days to +10% target
    target_profit = start_balance * 0.10
    reached_target_idx = df[df['cum_pnl'] >= target_profit].index
    
    if len(reached_target_idx) > 0:
        first_date = df.index[0]
        target_date = reached_target_idx[0]
        days_to_target = (target_date - first_date).days
    else:
        days_to_target = "Did not reach +10% target"

    print("="*40)
    print("        FTMO METRICS REPORT         ")
    print("="*40)
    print(f"Total Trades : {total_trades}")
    print(f"Win Rate     : {win_rate:.2f}%")
    print(f"Average Win  : ${avg_win:.2f}")
    print(f"Average Loss : ${avg_loss:.2f}")
    print(f"Average R:R  : {avg_rr:.2f}")
    print(f"Max Drawdown : ${abs(max_drawdown):.2f} ({abs(max_drawdown_pct):.2f}%)")
    print(f"Total PnL    : ${df['cum_pnl'].iloc[-1]:.2f}")
    print(f"Final Equity : ${df['equity'].iloc[-1]:.2f}")
    print(f"Days to 10%  : {days_to_target}")
    print("="*40)

    # Save to CSV
    df.to_csv(output_csv)
    print(f"Trade log saved to {output_csv}")
    return df
