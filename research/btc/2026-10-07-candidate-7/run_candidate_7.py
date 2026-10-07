#!/usr/bin/env python3
"""Candidate 7: H4-BREAK Dual R=1 + SMA50 regime + 0.75% risk + daily kill.

Research only. No live VM / MetaAPI / C4 / drip / FREEZE touches.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

DUKAS_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv"
)
DUKAS_EXT = Path(
    "/workspace/btc-strategies/dukas-ext/btcusd-m1-bid-2026-09-01-2026-10-07T11-34.csv"
)
OUT = Path("/workspace/btc-strategies/candidate-7-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-7.md")

START_EQUITY = 100_000.0
RISK = 0.0075  # 0.75%
LOOKBACK = 6
ATR_MULT = 1.0
MIN_LOT = 0.01
MAX_LOT = 50.0
SPREAD = 15.0  # FTMO typical_spread; commission 0; swap 0
DAILY_KILL = -0.03  # -3% realized day -> no new entries
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

HO_START = pd.Timestamp("2025-11-08 00:00:00+00:00")
HO_END = pd.Timestamp("2026-09-01 00:00:00+00:00")
EXT_START = pd.Timestamp("2026-09-02 00:00:00+00:00")
FIT_START = pd.Timestamp("2024-01-01 00:00:00+00:00")
FIT_END = pd.Timestamp("2025-11-07 23:59:59+00:00")

WINDOW_DAYS = 60
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
DAY_FAIL = -0.05


@dataclass
class Trade:
    side: str
    entry_ts: pd.Timestamp
    entry: float
    exit_ts: pd.Timestamp
    exit: float
    reason: str
    lots: float
    stop_dist: float
    pnl: float  # after spread
    equity_after: float


def load_m1_merged() -> pd.DataFrame:
    frames = []
    for path in (DUKAS_MAIN, DUKAS_EXT):
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").sort_index()
        frames.append(df[["open", "high", "low", "close"]].astype(float))
    m1 = pd.concat(frames)
    m1 = m1[~m1.index.duplicated(keep="last")].sort_index()
    # Flat-row clean (same spirit as harness): drop OHLC-equal unchanged vs prior
    flat = (
        (m1["open"] == m1["high"])
        & (m1["high"] == m1["low"])
        & (m1["low"] == m1["close"])
    )
    unchanged = m1["close"].eq(m1["close"].shift(1))
    m1 = m1[~(flat & unchanged)]
    return m1


def build_h4(m1: pd.DataFrame) -> pd.DataFrame:
    bars = m1.resample("4h", label="left", closed="left", origin=ORIGIN).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    last_m1 = m1.index[-1]
    bin_end_inclusive = bars.index[-1] + pd.Timedelta(hours=4) - pd.Timedelta(minutes=1)
    if last_m1 < bin_end_inclusive:
        bars = bars.iloc[:-1]
    return bars


def build_daily(m1: pd.DataFrame) -> pd.DataFrame:
    d = m1.resample("1D", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return d.dropna()


def atr14(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    n = len(close)
    atr = np.full(n, np.nan)
    trs = np.zeros(n)
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        trs[i] = max(hl, hc, lc)
    csum = np.cumsum(trs)
    for i in range(14, n):
        atr[i] = round(float(csum[i] - csum[i - 14]) / 14.0, 4)
    return atr


def prior_extreme(values: np.ndarray, n: int, how: str) -> np.ndarray:
    out = np.full(len(values), np.nan)
    if len(values) <= n:
        return out
    window = np.lib.stride_tricks.sliding_window_view(values, n)
    stats = window.max(axis=1) if how == "max" else window.min(axis=1)
    out[n:] = stats[: len(values) - n]
    return out


def sma50_daily(daily: pd.DataFrame) -> pd.Series:
    return daily["close"].rolling(50, min_periods=50).mean()


def prague_day(ts: pd.Timestamp) -> date:
    return ts.tz_convert(PRAGUE).date()


def et_month(ts: pd.Timestamp) -> str:
    d = ts.tz_convert(ET).date()
    return f"{d.year:04d}-{d.month:02d}"


def run_backtest(m1: pd.DataFrame, h4: pd.DataFrame, daily: pd.DataFrame, risk: float = RISK):
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14(high, low, close)
    prior_hi = prior_extreme(high, LOOKBACK, "max")
    prior_lo = prior_extreme(low, LOOKBACK, "min")

    sma = sma50_daily(daily)
    # Map each H4 bar's calendar UTC date -> prior day's close vs SMA50
    daily_closes = daily["close"]
    daily_index = daily.index  # midnight UTC

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)

    # First M1 at or after each H4 bar end
    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    equity = START_EQUITY
    trades: list[Trade] = []
    in_trade_until = -1  # m1 index exclusive / last exit index
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    signals = 0
    taken = 0
    skip_regime = 0
    skip_kill = 0
    skip_lots = 0
    skip_stop = 0
    skip_in_trade = 0

    # Track equity path after each exit for windows
    equity_marks: list[tuple[pd.Timestamp, float, date]] = []  # exit_ts, equity, prague_day

    for t in range(len(h4)):
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        if not np.isfinite(prior_hi[t]) or not np.isfinite(prior_lo[t]):
            continue

        long_sig = close[t] > prior_hi[t]
        short_sig = close[t] < prior_lo[t]
        if long_sig and short_sig:
            continue
        if not long_sig and not short_sig:
            continue
        signals += 1

        # Regime from prior completed UTC day
        bar_day = h4.index[t].normalize()
        # prior day = bar_day - 1 day in daily index
        prior_day = bar_day - pd.Timedelta(days=1)
        # find last daily bar strictly before bar_day
        pos = daily_index.searchsorted(bar_day, side="left") - 1
        if pos < 0:
            skip_regime += 1
            continue
        d_ts = daily_index[pos]
        sma_v = sma.iloc[pos]
        if pd.isna(sma_v):
            skip_regime += 1
            continue
        d_close = float(daily_closes.iloc[pos])
        if d_close > float(sma_v):
            regime = "long"
        elif d_close < float(sma_v):
            regime = "short"
        else:
            skip_regime += 1
            continue

        side = "long" if long_sig else "short"
        if side != regime:
            skip_regime += 1
            continue

        entry_i = int(end_locs[t])
        if entry_i >= n_m1:
            continue
        if entry_i <= in_trade_until:
            skip_in_trade += 1
            continue

        entry_ts = m1_index[entry_i]
        entry_px = float(m1_open[entry_i])
        pd_entry = prague_day(entry_ts)

        # Daily kill check
        if pd_entry in killed_days:
            skip_kill += 1
            continue
        # Initialize day start equity if needed
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            skip_kill += 1
            continue

        stop_dist = ATR_MULT * float(atr[t])
        if stop_dist <= 0:
            continue
        if side == "long":
            stop = entry_px - stop_dist
            target = entry_px + stop_dist
            if entry_px <= stop:
                skip_stop += 1
                continue
        else:
            stop = entry_px + stop_dist
            target = entry_px - stop_dist
            if entry_px >= stop:
                skip_stop += 1
                continue

        lots = round(equity * risk / stop_dist, 2)
        lots = min(lots, MAX_LOT)
        if lots < MIN_LOT:
            skip_lots += 1
            continue

        # Walk M1 for exit
        exit_i = None
        exit_px = None
        reason = None
        for j in range(entry_i, n_m1):
            hi = float(m1_high[j])
            lo = float(m1_low[j])
            op = float(m1_open[j])
            if side == "long":
                hit_sl = lo <= stop
                hit_tp = hi >= target
                gap_sl = op <= stop
                gap_tp = op >= target
            else:
                hit_sl = hi >= stop
                hit_tp = lo <= target
                gap_sl = op >= stop
                gap_tp = op <= target
            if not hit_sl and not hit_tp:
                continue
            if hit_sl and hit_tp:
                # conservative: stop
                if gap_sl and not gap_tp:
                    exit_i, exit_px, reason = j, op, "gap-stop"
                elif gap_tp and not gap_sl:
                    exit_i, exit_px, reason = j, target, "gap-target"
                else:
                    exit_i, exit_px, reason = j, stop, "both-stop"
                break
            if hit_sl:
                exit_i = j
                exit_px = op if gap_sl else stop
                reason = "gap-stop" if gap_sl else "stop"
                break
            exit_i = j
            exit_px = target
            reason = "target"
            break

        if exit_i is None:
            # open eod — exclude from official path
            in_trade_until = n_m1 - 1
            continue

        raw = (exit_px - entry_px) if side == "long" else (entry_px - exit_px)
        pnl = raw * lots - SPREAD * lots
        equity += pnl
        taken += 1
        exit_ts = m1_index[exit_i]
        pd_exit = prague_day(exit_ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl  # before this exit
        day_pnl[pd_exit] += pnl
        if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
            killed_days.add(pd_exit)

        trades.append(
            Trade(
                side=side,
                entry_ts=entry_ts,
                entry=entry_px,
                exit_ts=exit_ts,
                exit=exit_px,
                reason=reason,
                lots=lots,
                stop_dist=stop_dist,
                pnl=pnl,
                equity_after=equity,
            )
        )
        equity_marks.append((exit_ts, equity, pd_exit))
        in_trade_until = exit_i

    meta = {
        "signals": signals,
        "taken": taken,
        "skip_regime": skip_regime,
        "skip_kill": skip_kill,
        "skip_lots": skip_lots,
        "skip_stop": skip_stop,
        "skip_in_trade": skip_in_trade,
        "final_equity": equity,
        "killed_days": len(killed_days),
    }
    return trades, day_pnl, day_start_eq, equity_marks, meta


def max_realized_dd(trades: list[Trade]) -> float:
    peak = START_EQUITY
    max_dd = 0.0
    eq = START_EQUITY
    for tr in trades:
        eq = tr.equity_after
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def worst_day_pct(day_pnl, day_start_eq) -> tuple[date | None, float]:
    worst_d, worst_p = None, 0.0
    for d, pnl in day_pnl.items():
        start = day_start_eq.get(d, START_EQUITY)
        if start <= 0:
            continue
        pct = pnl / start
        if pct < worst_p:
            worst_p = pct
            worst_d = d
    return worst_d, worst_p


def days_at_or_below(day_pnl, day_start_eq, thresh: float) -> int:
    n = 0
    for d, pnl in day_pnl.items():
        start = day_start_eq.get(d, START_EQUITY)
        if start > 0 and pnl / start <= thresh:
            n += 1
    return n


def slice_pnl(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp | None) -> float:
    s = 0.0
    for tr in trades:
        if tr.exit_ts < start:
            continue
        if end is not None and tr.exit_ts > end:
            continue
        s += tr.pnl
    return s


def leave_out_two_best_ho(trades: list[Trade]) -> tuple[float, list[str]]:
    by_m: dict[str, float] = defaultdict(float)
    for tr in trades:
        if tr.exit_ts < HO_START or tr.exit_ts >= HO_END:
            continue
        by_m[et_month(tr.exit_ts)] += tr.pnl
    if len(by_m) < 2:
        return slice_pnl(trades, HO_START, HO_END - pd.Timedelta(seconds=1)), []
    ranked = sorted(by_m.items(), key=lambda x: -x[1])
    drop = [ranked[0][0], ranked[1][0]]
    left = sum(v for k, v in by_m.items() if k not in drop)
    return left, drop


def monthly_table(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[str, int, float]]:
    by_m: dict[str, list] = defaultdict(lambda: [0, 0.0])
    for tr in trades:
        if tr.exit_ts < start or tr.exit_ts >= end:
            continue
        m = et_month(tr.exit_ts)
        by_m[m][0] += 1
        by_m[m][1] += tr.pnl
    return [(m, by_m[m][0], by_m[m][1]) for m in sorted(by_m)]


def build_equity_series(trades: list[Trade]) -> list[tuple[pd.Timestamp, float]]:
    out = [(FIT_START, START_EQUITY)]
    eq = START_EQUITY
    for tr in trades:
        eq = tr.equity_after
        out.append((tr.exit_ts, eq))
    return out


def count_60d_pass_windows(
    trades: list[Trade],
    day_pnl: dict,
    day_start_eq: dict,
) -> tuple[int, int, list[dict]]:
    """Rolling 60 calendar-day windows starting each Prague day with trades path.

    Pass: hit 1.10 and 1.155 of window-start equity on some exit inside window,
    never <= 0.90 of start, no Prague day in window with day pnl/start <= -5%.
    """
    if not trades:
        return 0, 0, []

    # Build list of (exit_ts, equity_after)
    exits = [(tr.exit_ts, tr.equity_after) for tr in trades]
    # All Prague days that appear in day_start_eq or have exits
    all_days = sorted(set(day_start_eq.keys()) | {prague_day(t) for t, _ in exits})
    if not all_days:
        return 0, 0, []

    first_day = all_days[0]
    last_day = all_days[-1]
    # Also need continuous calendar for window starts
    # Equity at window start = equity after last exit strictly before window start midnight Prague
    # Approximate: equity before any exit whose prague day is inside [ws, ws+60)

    passes = []
    n_windows = 0
    # Start every 7 days to keep compute reasonable but still dense; ALSO every day is better
    # Use every Prague calendar day from first trade day to last-60
    cur = first_day
    end_limit = last_day - timedelta(days=WINDOW_DAYS - 1)
    while cur <= end_limit:
        ws = cur
        we = cur + timedelta(days=WINDOW_DAYS - 1)  # inclusive 60 calendar days
        n_windows += 1

        # Window-start equity: equity after last exit with prague_day < ws; else START
        start_eq = START_EQUITY
        for ts, eq in exits:
            if prague_day(ts) < ws:
                start_eq = eq
            else:
                break

        # Exits inside window
        window_exits = [(ts, eq) for ts, eq in exits if ws <= prague_day(ts) <= we]
        if not window_exits:
            cur += timedelta(days=1)
            continue

        max_eq = max(eq for _, eq in window_exits)
        min_eq = min(eq for _, eq in window_exits)
        hit_10 = max_eq >= start_eq * CHALLENGE_MULT
        hit_15 = max_eq >= start_eq * BOTH_MULT
        floor_ok = min_eq > start_eq * FLOOR_MULT

        # Day fails inside window
        day_fail = False
        worst_day_in = 0.0
        d = ws
        while d <= we:
            if d in day_pnl and d in day_start_eq and day_start_eq[d] > 0:
                pct = day_pnl[d] / day_start_eq[d]
                if pct < worst_day_in:
                    worst_day_in = pct
                if pct <= DAY_FAIL:
                    day_fail = True
                    break
            d += timedelta(days=1)

        ok = hit_10 and hit_15 and floor_ok and not day_fail
        if ok:
            passes.append(
                {
                    "start": ws.isoformat(),
                    "end": we.isoformat(),
                    "start_eq": start_eq,
                    "max_mult": max_eq / start_eq if start_eq else 0,
                    "min_mult": min_eq / start_eq if start_eq else 0,
                    "worst_day": worst_day_in,
                }
            )
        cur += timedelta(days=1)

    return len(passes), n_windows, passes[:15]  # sample of passes


def one_stop_dollars(trades: list[Trade]) -> float:
    """Typical planned stop $ = risk * equity_at_entry ≈ mean(lots * stop_dist)."""
    if not trades:
        return 0.0
    vals = [tr.lots * tr.stop_dist for tr in trades]
    return float(np.mean(vals))


def worst_day_dollars(day_pnl) -> tuple[date | None, float]:
    if not day_pnl:
        return None, 0.0
    d = min(day_pnl.items(), key=lambda x: x[1])
    return d[0], d[1]


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def main():
    print("Loading M1...")
    m1 = load_m1_merged()
    print(f"  M1 bars: {len(m1)}  {m1.index[0]} → {m1.index[-1]}")
    h4 = build_h4(m1)
    print(f"  H4 bars: {len(h4)}  {h4.index[0]} → {h4.index[-1]}")
    daily = build_daily(m1)
    print(f"  Daily bars: {len(daily)}")

    print(f"Running C7 @ risk={RISK*100:.2f}% ...")
    trades, day_pnl, day_start_eq, equity_marks, meta = run_backtest(m1, h4, daily, RISK)

    ho_net = slice_pnl(trades, HO_START, HO_END - pd.Timedelta(seconds=1))
    # HO inclusive of exits on 2026-09-01 before EXT
    ho_net = slice_pnl(trades, HO_START, pd.Timestamp("2026-09-01 23:59:59+00:00"))
    ext_net = slice_pnl(trades, EXT_START, None)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    full_net = meta["final_equity"] - START_EQUITY

    leave_net, leave_drop = leave_out_two_best_ho(trades)
    # recompute leave-out on HO months properly
    by_m: dict[str, float] = defaultdict(float)
    for tr in trades:
        if HO_START <= tr.exit_ts <= pd.Timestamp("2026-09-01 23:59:59+00:00"):
            by_m[et_month(tr.exit_ts)] += tr.pnl
    if len(by_m) >= 2:
        ranked = sorted(by_m.items(), key=lambda x: -x[1])
        leave_drop = [ranked[0][0], ranked[1][0]]
        leave_net = sum(v for k, v in by_m.items() if k not in leave_drop)
    else:
        leave_drop = []
        leave_net = ho_net

    max_dd = max_realized_dd(trades)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail_days = days_at_or_below(day_pnl, day_start_eq, DAY_FAIL)
    worst_day_d, worst_day_usd = worst_day_dollars(day_pnl)
    mean_stop_usd = one_stop_dollars(trades)

    ho_days = (HO_END.date() - HO_START.date()).days
    ho_mo = ho_days / 30.44
    ho_pace = ho_net / ho_mo if ho_mo > 0 else 0.0

    n_pass, n_win, pass_sample = count_60d_pass_windows(trades, day_pnl, day_start_eq)

    # Gate checks
    g1 = ho_net > 0
    g2 = ext_net >= 0
    g3 = leave_net > 0
    g4 = n_fail_days == 0 and worst_pct > DAY_FAIL
    g5 = max_dd <= 0.10
    g6 = fit_net >= -10_000
    g7 = n_pass >= 1
    g8 = ho_pace >= 7500 or g7
    g9 = mean_stop_usd <= 5000 and abs(worst_day_usd) <= 5000 and max_dd <= 0.10

    a_pass = all([g1, g2, g3, g4, g5, g6])
    b_pass = all([g7, g8, g9])

    if a_pass and b_pass:
        decision = "ACCEPT"
    elif a_pass and not b_pass:
        decision = "CONDITIONAL"
    else:
        decision = "REJECT"

    # Optional ablation at 0.50% risk (diagnostic only)
    print("Running diagnostic ablation @ 0.50% risk...")
    trades50, day_pnl50, day_start50, _, meta50 = run_backtest(m1, h4, daily, 0.005)
    ho50 = slice_pnl(trades50, HO_START, pd.Timestamp("2026-09-01 23:59:59+00:00"))
    max_dd50 = max_realized_dd(trades50)
    n_pass50, n_win50, _ = count_60d_pass_windows(trades50, day_pnl50, day_start50)
    worst_d50, worst_pct50 = worst_day_pct(day_pnl50, day_start50)

    # Monthly HO table
    months = monthly_table(trades, HO_START, pd.Timestamp("2026-09-02 00:00:00+00:00"))

    # Size / risk table (scale RISK multiplier)
    scale_rows = []
    for risk_pct in [0.0025, 0.005, 0.0075, 0.01, 0.015]:
        # Linear scale from base 0.75% run for pace/worst-day estimate
        scale = risk_pct / RISK
        pace = ho_pace * scale
        wd = worst_day_usd * scale
        stop_u = mean_stop_usd * scale
        dd_proxy = max_dd  # DD% roughly scale-invariant for fixed fractional risk... actually
        # For fractional risk, DD% is similar; dollar DD scales. Report dollar worst day.
        days_both = (15000 / pace * 30.44) if pace > 0 else float("inf")
        daily_ok = abs(wd) <= 5000 and stop_u <= 5000
        scale_rows.append((risk_pct, pace, wd, stop_u, days_both, daily_ok))

    # Wins / losses
    wins = sum(1 for tr in trades if tr.pnl > 0)
    losses = sum(1 for tr in trades if tr.pnl <= 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")

    lines = []
    lines.append("# Candidate 7 Results — H4-BREAK Dual R=1 + SMA50 Regime + 0.75% Risk + Daily Kill")
    lines.append("")
    lines.append(f"**Decision: {decision}**")
    lines.append("")
    one = (
        f"{decision} C7 as ≤60-day FTMO vehicle: "
        f"HO {fmt_money(ho_net)} (~{fmt_money(ho_pace)}/mo); "
        f"60d pass windows {n_pass}/{n_win}; "
        f"max DD {max_dd*100:.2f}%; worst day {worst_pct*100:.2f}%."
    )
    lines.append(f"**One sentence:** {one}")
    lines.append("")
    lines.append(f"**Measured:** {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE untouched.")
    lines.append(f"**Spec:** `{SPEC}`")
    lines.append("")
    lines.append("## ASSUMPTIONS (labeled)")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step (ASSUMPTION) |")
    lines.append("| Challenge / Verification | +10% / +5% |")
    lines.append("| Pace bar | ≤60 calendar days both steps |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Risk per trade | 0.75% equity / stop_dist |")
    lines.append("| Stop / Target | 1.0× H4 ATR(14) / R=1 |")
    lines.append("| Cost model | FTMO spread=15 × lots; commission 0; swap 0 |")
    lines.append("| Data | Merged Dukas M1 bid main+ext |")
    lines.append("")
    lines.append("## Rules used")
    lines.append("")
    lines.append("- H4 6-bar high/low break; exclusive dual via prior-day SMA50 regime")
    lines.append("- Hard R=1 TP (no channel exit); stop = 1.0× ATR14 H4")
    lines.append("- Size round(equity×0.0075/stop_dist, 2); max 1 position")
    lines.append("- Prague-day realized kill at −3%; same-minute double touch → stop")
    lines.append("")
    lines.append("## Run meta")
    lines.append("")
    lines.append(f"- Signals: {meta['signals']}; taken: {meta['taken']}; long/short: {longs}/{shorts}")
    lines.append(f"- Wins/losses: {wins}/{losses}")
    lines.append(
        f"- Skips: regime={meta['skip_regime']} kill={meta['skip_kill']} "
        f"lots={meta['skip_lots']} stop={meta['skip_stop']} in_trade={meta['skip_in_trade']}"
    )
    lines.append(f"- Killed Prague days: {meta['killed_days']}")
    lines.append(f"- Final equity: {fmt_money(meta['final_equity'])} (net {fmt_money(full_net)})")
    lines.append(f"- Mean planned stop $: {fmt_money(mean_stop_usd)}")
    lines.append("")
    lines.append("## Gate A — robustness")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    lines.append(f"| 1 Holdout net > 0 | {'YES' if g1 else 'NO'} | HO {fmt_money(ho_net)} |")
    lines.append(f"| 2 Extension net ≥ 0 | {'YES' if g2 else 'NO'} | Ext {fmt_money(ext_net)} |")
    lines.append(
        f"| 3 Leave-out two best HO months > 0 | {'YES' if g3 else 'NO'} | "
        f"removed {leave_drop}; left {fmt_money(leave_net)} |"
    )
    lines.append(
        f"| 4 Worst Prague day > −5%; 0 days ≤ −5% | {'YES' if g4 else 'NO'} | "
        f"worst {worst_d} {worst_pct*100:.2f}%; fail-days={n_fail_days} |"
    )
    lines.append(f"| 5 Max realized DD ≤ 10% | {'YES' if g5 else 'NO'} | {max_dd*100:.2f}% |")
    lines.append(f"| 6 Fit net ≥ −$10,000 | {'YES' if g6 else 'NO'} | Fit {fmt_money(fit_net)} |")
    lines.append("")
    lines.append(f"**Gate A all pass?** {'YES' if a_pass else 'NO'}")
    lines.append("")
    lines.append("## Gate B — ≤60-day fast vehicle")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    lines.append(
        f"| 7 ≥1 clean 60d window (1.10 then 1.155, floor, no −5% day) | "
        f"{'YES' if g7 else 'NO'} | {n_pass} / {n_win} windows |"
    )
    lines.append(
        f"| 8 Pace ≥$7.5k/mo OR Gate 7 | {'YES' if g8 else 'NO'} | "
        f"HO pace {fmt_money(ho_pace)}/mo |"
    )
    lines.append(
        f"| 9 Stop + worst day ≤ $5k; DD ≤10% | {'YES' if g9 else 'NO'} | "
        f"stop~{fmt_money(mean_stop_usd)}; worst day {fmt_money(worst_day_usd)}; "
        f"DD {max_dd*100:.2f}% |"
    )
    lines.append("")
    lines.append(f"**Gate B all pass?** {'YES' if b_pass else 'NO'}")
    lines.append("")
    lines.append("## 60-day pass windows (sample)")
    lines.append("")
    if pass_sample:
        lines.append("| start | end | start_eq | max_mult | min_mult | worst_day |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for p in pass_sample:
            lines.append(
                f"| {p['start']} | {p['end']} | {p['start_eq']:.2f} | "
                f"{p['max_mult']:.4f} | {p['min_mult']:.4f} | {p['worst_day']*100:.2f}% |"
            )
    else:
        lines.append("_None._")
    lines.append("")
    lines.append("## HO monthly P&L (ET exit month)")
    lines.append("")
    lines.append("| ET exit month | Trades | Net $ |")
    lines.append("|---|---:|---:|")
    for m, n, pnl in months:
        lines.append(f"| {m} | {n} | {pnl:,.2f} |")
    lines.append("")
    lines.append("## Risk scale table (linear $ from 0.75% base run)")
    lines.append("")
    lines.append("| Risk% | HO $/mo | Worst day $ | Mean stop $ | Est days both +$15k | Daily $ OK |")
    lines.append("|---:|---:|---:|---:|---:|:---:|")
    for risk_pct, pace, wd, stop_u, days_both, daily_ok in scale_rows:
        db = f"{days_both:.1f}" if days_both != float("inf") else "inf"
        lines.append(
            f"| {risk_pct*100:.2f} | {pace:,.2f} | {wd:,.2f} | {stop_u:,.2f} | {db} | "
            f"{'Y' if daily_ok else 'N'} |"
        )
    lines.append("")
    lines.append("## Diagnostic ablation — 0.50% risk (not a new candidate)")
    lines.append("")
    lines.append(f"- Trades: {meta50['taken']}; final equity {fmt_money(meta50['final_equity'])}")
    lines.append(f"- HO net: {fmt_money(ho50)}; max DD {max_dd50*100:.2f}%")
    lines.append(f"- Worst day: {worst_d50} {worst_pct50*100:.2f}%")
    lines.append(f"- 60d pass windows: {n_pass50} / {n_win50}")
    lines.append("")
    lines.append("## Comparison vs C5 / C6")
    lines.append("")
    lines.append("| | C5 @ 0.01 | C6 max DD-safe | C7 @ 0.75% |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| HO $/mo | ~491 | ~2,973 | {ho_pace:,.2f} |")
    lines.append(f"| ≤60d both | NO | NO (~154d) | {'YES' if g7 else 'NO'} ({n_pass} windows) |")
    lines.append(f"| Max DD | low @0.01 | scaled | {max_dd*100:.2f}% |")
    lines.append(f"| Structure | daily SMA R=1 | scale C5 | H4 break dual R=1 |")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"**{decision}** — C7 is research-only. Not deployable live from this folder.")
    if decision == "REJECT":
        lines.append(
            "Near-miss notes: see Gate A/B failures above. "
            "If HO positive but no 60d windows, frequency/edge still insufficient at DD-legal risk."
        )
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.")
    lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")
    print(f"Decision: {decision}")
    print(f"HO net={ho_net:.2f} pace={ho_pace:.2f}/mo  ext={ext_net:.2f} fit={fit_net:.2f}")
    print(f"maxDD={max_dd*100:.2f}% worstDay={worst_pct*100:.2f}% stop~{mean_stop_usd:.2f}")
    print(f"60d passes={n_pass}/{n_win}")


if __name__ == "__main__":
    main()
