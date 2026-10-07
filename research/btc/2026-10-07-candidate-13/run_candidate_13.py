#!/usr/bin/env python3
"""Candidate 13: London Opening Range Breakout (ORB) Exclusive Dual.

Hard stop = opposite side of 07:00–08:00 UTC range; R=1.5; 0.75% risk;
Prague −3% kill. Research only. No live VM / MetaAPI / C4 / drip / FREEZE.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
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
OUT = Path("/workspace/btc-strategies/candidate-13-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-13.md")
PACK = Path("/workspace/btc-strategies/2026-10-07-candidate-13")
ROOT_STATUS = Path("/workspace/btc-strategies/STATUS.md")
PR_BODY = Path("/workspace/btc-strategies/GITHUB-PR-BODY-C13.md")

START_EQUITY = 100_000.0
RISK = 0.0075  # 0.75% locked
R_MULT = 1.5
MIN_LOT = 0.01
MAX_LOT = 50.0
SPREAD = 15.0  # FTMO typical_spread; commission 0; swap 0
DAILY_KILL = -0.03
MIN_OR_BARS = 45  # a priori thin-data guard for London hour
OR_HOUR = 7  # 07:00–07:59 UTC

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
    pnl: float
    equity_after: float
    or_range: float


def load_m1_merged() -> pd.DataFrame:
    frames = []
    for path in (DUKAS_MAIN, DUKAS_EXT):
        if not path.exists():
            raise FileNotFoundError(f"Missing Dukas M1: {path}")
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").sort_index()
        frames.append(df[["open", "high", "low", "close"]].astype(float))
    m1 = pd.concat(frames)
    m1 = m1[~m1.index.duplicated(keep="last")].sort_index()
    flat = (
        (m1["open"] == m1["high"])
        & (m1["high"] == m1["low"])
        & (m1["low"] == m1["close"])
    )
    unchanged = m1["close"].eq(m1["close"].shift(1))
    m1 = m1[~(flat & unchanged)]
    return m1


def prague_day(ts: pd.Timestamp) -> date:
    return ts.tz_convert(PRAGUE).date()


def prague_month(ts: pd.Timestamp) -> str:
    d = ts.tz_convert(PRAGUE).date()
    return f"{d.year:04d}-{d.month:02d}"


def et_month(ts: pd.Timestamp) -> str:
    d = ts.tz_convert(ET).date()
    return f"{d.year:04d}-{d.month:02d}"


def atr14(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Simple 14-bar ATR (not Wilder) — used only by H1 z-score fallback."""
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


def manage_exit(
    side: str,
    entry_i: int,
    stop: float,
    target: float,
    m1_open: np.ndarray,
    m1_high: np.ndarray,
    m1_low: np.ndarray,
    n_m1: int,
):
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
        exit_px = op if gap_tp else target
        reason = "gap-target" if gap_tp else "target"
        break
    return exit_i, exit_px, reason


def run_backtest_orb(m1: pd.DataFrame, risk: float = RISK):
    """London ORB exclusive dual — primary C13 chassis."""
    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_close = m1["close"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)

    hours = m1_index.hour
    utc_dates = m1_index.date

    # Pre-group indices by UTC date
    by_date: dict[date, list[int]] = defaultdict(list)
    for i in range(n_m1):
        by_date[utc_dates[i]].append(i)

    equity = START_EQUITY
    trades: list[Trade] = []
    in_trade_until = -1
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()

    signals = 0
    taken = 0
    skip_kill = 0
    skip_lots = 0
    skip_stop = 0
    skip_in_trade = 0
    skip_thin = 0
    skip_range = 0
    skip_no_break = 0
    or_days = 0

    sorted_dates = sorted(by_date.keys())

    for d in sorted_dates:
        idxs = by_date[d]
        or_idxs = [i for i in idxs if hours[i] == OR_HOUR]
        if len(or_idxs) < MIN_OR_BARS:
            skip_thin += 1
            continue
        or_high = float(np.max(m1_high[or_idxs]))
        or_low = float(np.min(m1_low[or_idxs]))
        or_range = or_high - or_low
        if or_range <= 0:
            skip_range += 1
            continue
        or_days += 1

        # Break watch: hour >= 8 same UTC day
        watch = [i for i in idxs if hours[i] >= 8]
        if not watch:
            skip_no_break += 1
            continue

        side = None
        confirm_i = None
        for i in watch:
            if i <= in_trade_until:
                continue
            c = float(m1_close[i])
            if c > or_high:
                side = "long"
                confirm_i = i
                break
            if c < or_low:
                side = "short"
                confirm_i = i
                break

        if side is None or confirm_i is None:
            skip_no_break += 1
            continue

        signals += 1
        entry_i = confirm_i + 1
        if entry_i >= n_m1:
            continue
        # Entry must still be same UTC day (a priori: no overnight gap-in from next day)
        if utc_dates[entry_i] != d:
            continue
        if entry_i <= in_trade_until:
            skip_in_trade += 1
            continue

        entry_ts = m1_index[entry_i]
        entry_px = float(m1_open[entry_i])
        pd_entry = prague_day(entry_ts)

        if pd_entry in killed_days:
            skip_kill += 1
            continue
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            skip_kill += 1
            continue

        if side == "long":
            stop = or_low
            stop_dist = entry_px - stop
            if stop_dist <= 0 or entry_px <= stop:
                skip_stop += 1
                continue
            target = entry_px + R_MULT * stop_dist
        else:
            stop = or_high
            stop_dist = stop - entry_px
            if stop_dist <= 0 or entry_px >= stop:
                skip_stop += 1
                continue
            target = entry_px - R_MULT * stop_dist

        lots = round(equity * risk / stop_dist, 2)
        lots = min(lots, MAX_LOT)
        if lots < MIN_LOT:
            skip_lots += 1
            continue

        exit_i, exit_px, reason = manage_exit(
            side, entry_i, stop, target, m1_open, m1_high, m1_low, n_m1
        )
        if exit_i is None:
            in_trade_until = n_m1 - 1
            continue

        raw = (exit_px - entry_px) if side == "long" else (entry_px - exit_px)
        pnl = raw * lots - SPREAD * lots
        equity += pnl
        taken += 1
        exit_ts = m1_index[exit_i]
        pd_exit = prague_day(exit_ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
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
                or_range=or_range,
            )
        )
        in_trade_until = exit_i

    meta = {
        "chassis": "london-orb",
        "signals": signals,
        "taken": taken,
        "skip_kill": skip_kill,
        "skip_lots": skip_lots,
        "skip_stop": skip_stop,
        "skip_in_trade": skip_in_trade,
        "skip_thin": skip_thin,
        "skip_range": skip_range,
        "skip_no_break": skip_no_break,
        "or_days": or_days,
        "final_equity": equity,
        "killed_days": len(killed_days),
    }
    return trades, day_pnl, day_start_eq, meta


def build_h1(m1: pd.DataFrame) -> pd.DataFrame:
    origin = pd.Timestamp("2024-01-01 00:00:00+00:00")
    bars = m1.resample("1h", label="left", closed="left", origin=origin).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    last_m1 = m1.index[-1]
    bin_end_inclusive = bars.index[-1] + pd.Timedelta(hours=1) - pd.Timedelta(minutes=1)
    if last_m1 < bin_end_inclusive:
        bars = bars.iloc[:-1]
    return bars


def run_backtest_zscore_fallback(m1: pd.DataFrame, risk: float = RISK):
    """A-priori fallback ONLY if ORB path broken: H1 z-score fade, no SMA50 regime."""
    h1 = build_h1(m1)
    open_ = h1["open"].to_numpy()
    high = h1["high"].to_numpy()
    low = h1["low"].to_numpy()
    close = h1["close"].to_numpy()
    atr = atr14(high, low, close)

    # 48-bar SMA + stdev for z
    n = len(close)
    sma48 = np.full(n, np.nan)
    std48 = np.full(n, np.nan)
    for i in range(47, n):
        window = close[i - 47 : i + 1]
        sma48[i] = float(np.mean(window))
        std48[i] = float(np.std(window, ddof=0))
        if std48[i] <= 0:
            std48[i] = np.nan

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)
    ends = h1.index + pd.Timedelta(hours=1)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    equity = START_EQUITY
    trades: list[Trade] = []
    in_trade_until = -1
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    signals = 0
    taken = 0
    skip_kill = 0
    skip_lots = 0
    skip_stop = 0
    skip_in_trade = 0
    skip_atr = 0

    for t in range(n):
        if not np.isfinite(sma48[t]) or not np.isfinite(std48[t]) or not np.isfinite(atr[t]):
            continue
        if atr[t] <= 0:
            skip_atr += 1
            continue
        z = (close[t] - sma48[t]) / std48[t]
        if z >= 2.0:
            side = "short"  # fade
        elif z <= -2.0:
            side = "long"
        else:
            continue
        signals += 1

        entry_i = int(end_locs[t])
        if entry_i >= n_m1:
            continue
        if entry_i <= in_trade_until:
            skip_in_trade += 1
            continue

        entry_ts = m1_index[entry_i]
        entry_px = float(m1_open[entry_i])
        pd_entry = prague_day(entry_ts)
        if pd_entry in killed_days:
            skip_kill += 1
            continue
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            skip_kill += 1
            continue

        stop_dist = 1.0 * float(atr[t])
        target_dist = R_MULT * stop_dist
        if side == "long":
            stop = entry_px - stop_dist
            target = entry_px + target_dist
            if entry_px <= stop:
                skip_stop += 1
                continue
        else:
            stop = entry_px + stop_dist
            target = entry_px - target_dist
            if entry_px >= stop:
                skip_stop += 1
                continue

        lots = round(equity * risk / stop_dist, 2)
        lots = min(lots, MAX_LOT)
        if lots < MIN_LOT:
            skip_lots += 1
            continue

        exit_i, exit_px, reason = manage_exit(
            side, entry_i, stop, target, m1_open, m1_high, m1_low, n_m1
        )
        if exit_i is None:
            in_trade_until = n_m1 - 1
            continue

        raw = (exit_px - entry_px) if side == "long" else (entry_px - exit_px)
        pnl = raw * lots - SPREAD * lots
        equity += pnl
        taken += 1
        exit_ts = m1_index[exit_i]
        pd_exit = prague_day(exit_ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
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
                or_range=0.0,
            )
        )
        in_trade_until = exit_i

    meta = {
        "chassis": "h1-zscore-fallback",
        "signals": signals,
        "taken": taken,
        "skip_kill": skip_kill,
        "skip_lots": skip_lots,
        "skip_stop": skip_stop,
        "skip_in_trade": skip_in_trade,
        "skip_atr": skip_atr,
        "final_equity": equity,
        "killed_days": len(killed_days),
    }
    return trades, day_pnl, day_start_eq, meta


def max_realized_dd(trades: list[Trade]) -> float:
    peak = START_EQUITY
    max_dd = 0.0
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


def monthly_table_et(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[str, int, float]]:
    by_m: dict[str, list] = defaultdict(lambda: [0, 0.0])
    for tr in trades:
        if tr.exit_ts < start or tr.exit_ts >= end:
            continue
        m = et_month(tr.exit_ts)
        by_m[m][0] += 1
        by_m[m][1] += tr.pnl
    return [(m, by_m[m][0], by_m[m][1]) for m in sorted(by_m)]


def count_60d_pass_windows(
    trades: list[Trade],
    day_pnl: dict,
    day_start_eq: dict,
) -> tuple[int, int, list[dict]]:
    if not trades:
        return 0, 0, []

    exits = [(tr.exit_ts, tr.equity_after) for tr in trades]
    all_days = sorted(set(day_start_eq.keys()) | {prague_day(t) for t, _ in exits})
    if not all_days:
        return 0, 0, []

    first_day = all_days[0]
    last_day = all_days[-1]
    passes = []
    n_windows = 0
    cur = first_day
    end_limit = last_day - timedelta(days=WINDOW_DAYS - 1)

    exit_pdays = [prague_day(ts) for ts, _ in exits]
    exit_eqs = [eq for _, eq in exits]

    while cur <= end_limit:
        ws = cur
        we = cur + timedelta(days=WINDOW_DAYS - 1)
        n_windows += 1

        start_eq = START_EQUITY
        for i, pd_ in enumerate(exit_pdays):
            if pd_ < ws:
                start_eq = exit_eqs[i]
            else:
                break

        window_eqs = [exit_eqs[i] for i, pd_ in enumerate(exit_pdays) if ws <= pd_ <= we]
        if not window_eqs:
            cur += timedelta(days=1)
            continue

        max_eq = max(window_eqs)
        min_eq = min(window_eqs)
        hit_10 = max_eq >= start_eq * CHALLENGE_MULT
        hit_15 = max_eq >= start_eq * BOTH_MULT
        floor_ok = min_eq > start_eq * FLOOR_MULT

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

    return len(passes), n_windows, passes[:20]


def one_stop_dollars(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    vals = [tr.lots * tr.stop_dist for tr in trades]
    return float(np.mean(vals))


def worst_day_dollars(day_pnl) -> tuple[date | None, float]:
    if not day_pnl:
        return None, 0.0
    d = min(day_pnl.items(), key=lambda x: x[1])
    return d[0], d[1]


def summarize_run(label: str, trades, day_pnl, day_start_eq, meta, risk: float) -> dict:
    ho_end = pd.Timestamp("2026-09-01 23:59:59+00:00")
    ho_net = slice_pnl(trades, HO_START, ho_end)
    ext_net = slice_pnl(trades, EXT_START, None)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    full_net = meta["final_equity"] - START_EQUITY

    # Leave-out two best HO Prague months (C13 gate text)
    by_m: dict[str, float] = defaultdict(float)
    for tr in trades:
        if HO_START <= tr.exit_ts <= ho_end:
            by_m[prague_month(tr.exit_ts)] += tr.pnl
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

    wins = sum(1 for tr in trades if tr.pnl > 0)
    losses = sum(1 for tr in trades if tr.pnl <= 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")
    reasons: dict[str, int] = defaultdict(int)
    for tr in trades:
        reasons[tr.reason] += 1

    months = monthly_table_et(trades, HO_START, pd.Timestamp("2026-09-02 00:00:00+00:00"))
    full_months = monthly_table_et(
        trades, FIT_START, pd.Timestamp("2026-10-08 00:00:00+00:00")
    )

    mean_or = float(np.mean([tr.or_range for tr in trades])) if trades else 0.0

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

    return {
        "label": label,
        "risk": risk,
        "decision": decision,
        "a_pass": a_pass,
        "b_pass": b_pass,
        "gates": {
            "g1_ho": (g1, ho_net),
            "g2_ext": (g2, ext_net),
            "g3_leave": (g3, leave_net, leave_drop),
            "g4_day": (g4, worst_d, worst_pct, n_fail_days),
            "g5_dd": (g5, max_dd),
            "g6_fit": (g6, fit_net),
            "g7_60d": (g7, n_pass, n_win),
            "g8_pace": (g8, ho_pace),
            "g9_stop": (g9, mean_stop_usd, worst_day_usd),
        },
        "meta": meta,
        "full_net": full_net,
        "wins": wins,
        "losses": losses,
        "longs": longs,
        "shorts": shorts,
        "reasons": dict(reasons),
        "months_ho": months,
        "months_full": full_months,
        "pass_sample": pass_sample,
        "n_trades": len(trades),
        "final_equity": meta["final_equity"],
        "worst_day_d": worst_day_d,
        "worst_day_usd": worst_day_usd,
        "mean_stop_usd": mean_stop_usd,
        "max_dd": max_dd,
        "ho_pace": ho_pace,
        "n_pass": n_pass,
        "n_win": n_win,
        "ho_net": ho_net,
        "ext_net": ext_net,
        "fit_net": fit_net,
        "leave_net": leave_net,
        "leave_drop": leave_drop,
        "worst_d": worst_d,
        "worst_pct": worst_pct,
        "n_fail_days": n_fail_days,
        "mean_or": mean_or,
    }


def binding_and_next(s: dict) -> tuple[str, str]:
    fails = []
    g = s["gates"]
    reason_tags = []
    if not g["g1_ho"][0] or not g["g2_ext"][0] or not g["g3_leave"][0] or not g["g6_fit"][0]:
        reason_tags.append("EDGE")
    if not g["g4_day"][0] or not g["g5_dd"][0] or not g["g9_stop"][0]:
        reason_tags.append("DD")
    if not g["g7_60d"][0] or (not g["g8_pace"][0] and g["g7_60d"][0] is False):
        reason_tags.append("PACE")
    if not g["g1_ho"][0]:
        fails.append("HO edge")
    if not g["g2_ext"][0]:
        fails.append("extension")
    if not g["g3_leave"][0]:
        fails.append("leave-out")
    if not g["g4_day"][0]:
        fails.append("−5% day")
    if not g["g5_dd"][0]:
        fails.append(f"max DD {s['max_dd']*100:.1f}%")
    if not g["g6_fit"][0]:
        fails.append("fit")
    if not g["g7_60d"][0]:
        fails.append("0 ≤60d windows")
    if not g["g8_pace"][0]:
        fails.append(f"pace ${s['ho_pace']:,.0f}/mo")
    if not g["g9_stop"][0]:
        fails.append("stop/worst-day/DD dollars")

    tag = "/".join(dict.fromkeys(reason_tags)) if reason_tags else "narrow"

    if s["decision"] == "ACCEPT":
        binding = "none (ACCEPT)"
        nxt = (
            "C13 cleared Gate A+B as a ≤60d research vehicle. Still research-only — "
            "no deploy without Odin approval. Live C4/drip untouched."
        )
        return binding, nxt, tag

    binding = f"{tag}: " + (", ".join(fails) if fails else "narrow near-miss")

    months_to_15k = (15_000 / s["ho_pace"]) if s["ho_pace"] > 0 else float("inf")
    if s["decision"] == "CONDITIONAL":
        nxt = (
            f"Gate A passed; Gate B failed (PACE). Honest multi-month estimate at locked risk: "
            f"~{months_to_15k:.1f} months to +$15k at HO pace ${s['ho_pace']:,.0f}/mo — "
            f"**not** a ≤60d vehicle. Do not fake ≤60d hope. "
            f"≤60d BTC-only still blocked on pace at legal DD."
        )
    elif s["ho_net"] <= 0 or not s["a_pass"]:
        nxt = (
            "London ORB chassis failed Gate A (edge and/or DD) at locked risk. "
            "Together with C5–C12, BTC-only Challenge+Verification in ≤60 days at FTMO "
            "5%/10% DD remains **blocked** — robust edges too slow; session/HF books "
            "lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify "
            "beyond BTC-only. Do not deploy C13."
        )
    else:
        nxt = (
            "Near-miss documented. ≤60d BTC-only still looks blocked at legal DD. "
            "Honest path: multi-month C5/C10 or non-BTC diversification."
        )
    return binding, nxt, tag


def main():
    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("Loading M1...")
    m1 = load_m1_merged()
    print(f"  M1 bars: {len(m1)}  {m1.index[0]} → {m1.index[-1]}")

    # Probe ORB path: can we form ranges?
    hours = m1.index.hour
    sample_or = int(np.sum(hours == OR_HOUR))
    print(f"  M1 bars in hour=07 UTC: {sample_or}")
    use_fallback = sample_or < 1000  # path broken if almost no London-hour bars
    chassis_name = "h1-zscore-fallback" if use_fallback else "london-orb"
    if use_fallback:
        print("ORB path appears broken — using a-priori H1 z-score fallback.")
        runner = run_backtest_zscore_fallback
    else:
        print("ORB path OK — running London ORB exclusive dual.")
        runner = run_backtest_orb

    summaries = {}
    for risk, label in [(0.0075, "0.75% locked"), (0.005, "0.50%"), (0.01, "1.00%")]:
        print(f"Running C13 @ risk={risk*100:.2f}% ({chassis_name}) ...")
        trades, day_pnl, day_start_eq, meta = runner(m1, risk)
        print(
            f"  trades={len(trades)} final_eq={meta['final_equity']:.2f} "
            f"signals={meta['signals']} chassis={meta.get('chassis')}"
        )
        summaries[risk] = summarize_run(label, trades, day_pnl, day_start_eq, meta, risk)

    s = summaries[0.0075]
    binding, nxt, tag = binding_and_next(s)

    legal = (
        s["max_dd"] <= 0.10
        and s["n_fail_days"] == 0
        and s["worst_pct"] > DAY_FAIL
    )

    lines = []
    lines.append("# Candidate 13 Results — London Opening Range Breakout (ORB)")
    lines.append("")
    lines.append(f"**Decision: {s['decision']}**")
    lines.append("")
    one = (
        f"{s['decision']} C13 as ≤60d vehicle: London ORB dual R=1.5 @0.75% "
        f"(chassis={s['meta'].get('chassis')}); "
        f"HO {s['ho_net']:+,.0f} (~${s['ho_pace']:,.0f}/mo); "
        f"fit {s['fit_net']:+,.0f}; max DD {s['max_dd']*100:.1f}%; "
        f"60d windows {s['n_pass']}/{s['n_win']}; "
        f"binding: {binding}."
    )
    lines.append(f"**One sentence:** {one}")
    lines.append("")
    lines.append(f"**Measured:** {measured}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**Spec:** `{SPEC}`")
    lines.append(f"**Chassis used:** `{s['meta'].get('chassis')}`" + (" (fallback)" if use_fallback else " (primary ORB)"))
    lines.append("")
    lines.append("## Locked rules (a priori)")
    lines.append("")
    lines.append("| Step | Rule |")
    lines.append("|---|---|")
    if use_fallback:
        lines.append("| Bars | Dukas M1 → H1 UTC; z-score on 48-bar close vs SMA |")
        lines.append("| Entry | Fade |z|≥2 toward mean; next H1 open; max 1; **no SMA50 regime** |")
        lines.append("| Stop | 1.0 × H1 ATR(14) |")
        lines.append("| Target | 1.5 × stop (R=1.5) |")
    else:
        lines.append("| OR | First London hour 07:00–07:59 UTC; ≥45 M1 bars |")
        lines.append("| Break | M1 close beyond OR high/low after 08:00 UTC; first wins |")
        lines.append("| Entry | Next M1 open after confirm; max 1; same UTC day |")
        lines.append("| Stop | **Opposite side of OR** (not mid) — a priori |")
        lines.append("| Target | 1.5 × stop_dist (R=1.5) |")
    lines.append("| Risk | 0.75% equity / stop (also 0.50%, 1.00%) |")
    lines.append("| Kill | Prague-day realized ≤ −3% day-start → no new entries |")
    lines.append("| Cost | FTMO spread=15 × lots; commission 0; swap 0 (C7/C11 parity) |")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step (ASSUMPTION) |")
    lines.append("| Challenge / Verification | +10% / +5% (1.10 / 1.155 window) |")
    lines.append("| Pace bar | ≤60 calendar days both steps |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Stop rule | Opposite OR side always (not mid) |")
    lines.append("| R multiple | **1.5** a priori |")
    lines.append("| Data | Merged Dukas M1 bid main+ext |")
    lines.append("| Cost | spread=15 (not C4 0.065%/side) |")
    lines.append("")
    lines.append("## Gate A — robustness @ 0.75% risk")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    g = s["gates"]
    lines.append(f"| 1 Holdout >0 | {'YES' if g['g1_ho'][0] else 'NO'} | HO ${s['ho_net']:,.2f} |")
    lines.append(f"| 2 Extension ≥ 0 | {'YES' if g['g2_ext'][0] else 'NO'} | Ext ${s['ext_net']:,.2f} |")
    lines.append(
        f"| 3 Leave-out two best HO Prague months > 0 | {'YES' if g['g3_leave'][0] else 'NO'} | "
        f"removed {s['leave_drop']}; left ${s['leave_net']:,.2f} |"
    )
    lines.append(
        f"| 4 Worst Prague day ≥ −5%; 0 fail-days | {'YES' if g['g4_day'][0] else 'NO'} | "
        f"worst {s['worst_d']} {s['worst_pct']*100:.2f}%; fail-days={s['n_fail_days']} |"
    )
    lines.append(f"| 5 Max realized DD ≤ 10% | {'YES' if g['g5_dd'][0] else 'NO'} | DD {s['max_dd']*100:.2f}% |")
    lines.append(f"| 6 Fit ≥ −$10k | {'YES' if g['g6_fit'][0] else 'NO'} | Fit ${s['fit_net']:,.2f} |")
    lines.append("")
    lines.append(f"**Gate A all pass?** {'YES' if s['a_pass'] else 'NO'}")
    lines.append("")
    wr = s["wins"] / s["n_trades"] * 100 if s["n_trades"] else 0.0
    lines.append(
        f"- Trades full L/S: {s['longs']}/{s['shorts']}; n={s['n_trades']}; "
        f"WR {wr:.1f}% ({s['wins']}/{s['losses']})"
    )
    lines.append(f"- Exit reasons: {s['reasons']}")
    lines.append(f"- Pace @0.75%: **${s['ho_pace']:,.2f}/mo** over HO calendar")
    if not use_fallback:
        lines.append(
            f"- OR days formed: {s['meta'].get('or_days')}; mean OR range on trades: ${s['mean_or']:,.1f}"
        )
    lines.append(
        f"- Meta: signals={s['meta']['signals']} taken={s['meta']['taken']} "
        f"skip_in_trade={s['meta'].get('skip_in_trade')} skip_kill={s['meta']['skip_kill']} "
        f"skip_lots={s['meta']['skip_lots']} skip_thin={s['meta'].get('skip_thin')} "
        f"skip_no_break={s['meta'].get('skip_no_break')} killed_days={s['meta']['killed_days']}"
    )
    lines.append("")
    lines.append("### HO monthly P&L @0.75% (ET exit month)")
    lines.append("")
    lines.append("| ET exit month | Trades | Net $ |")
    lines.append("|---|---:|---:|")
    for m, n, pnl in s["months_ho"]:
        lines.append(f"| {m} | {n} | {pnl:,.2f} |")
    lines.append("")
    lines.append("## Gate B — ≤60-day vehicle @ 0.75% risk")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    lines.append(
        f"| 7 ≥1 clean 60d window | {'YES' if g['g7_60d'][0] else 'NO'} | "
        f"**{s['n_pass']} / {s['n_win']}** windows |"
    )
    lines.append(
        f"| 8 Pace ≥$7.5k/mo OR Gate 7 | {'YES' if g['g8_pace'][0] else 'NO'} | "
        f"HO pace ${s['ho_pace']:,.2f}/mo |"
    )
    lines.append(
        f"| 9 Stop+worst day ≤$5k; DD≤10% | {'YES' if g['g9_stop'][0] else 'NO'} | "
        f"mean stop ${s['mean_stop_usd']:,.2f}; worst day ${s['worst_day_usd']:,.2f}; "
        f"DD {s['max_dd']*100:.1f}% |"
    )
    lines.append("")
    lines.append(f"**Gate B all pass?** {'YES' if s['b_pass'] else 'NO'}")
    lines.append("")
    lines.append(f"- Final equity: ${s['final_equity']:,.2f} (net ${s['full_net']:,.2f})")
    lines.append(f"- Binding constraint: **{binding}**")
    lines.append(f"- DD-legal @0.75%? **{'YES' if legal else 'NO'}**")
    lines.append("")
    lines.append("### 60-day pass windows (sample)")
    lines.append("")
    if s["pass_sample"]:
        lines.append("| Start | End | Start eq | Max mult | Min mult | Worst day |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for p in s["pass_sample"]:
            lines.append(
                f"| {p['start']} | {p['end']} | ${p['start_eq']:,.0f} | "
                f"{p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']*100:.2f}% |"
            )
    else:
        lines.append("_None._")
    lines.append("")
    lines.append("## Risk table (0.50% / 0.75% / 1.00%)")
    lines.append("")
    lines.append(
        "| Risk | HO net | HO $/mo | Fit | Leave-out | Ext | Max DD | Worst day % | "
        "60d passes | Legal | Decision@risk |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for risk in (0.005, 0.0075, 0.01):
        r = summaries[risk]
        r_legal = (
            r["max_dd"] <= 0.10
            and r["n_fail_days"] == 0
            and r["worst_pct"] > DAY_FAIL
        )
        lines.append(
            f"| {risk*100:.2f}% | ${r['ho_net']:,.0f} | ${r['ho_pace']:,.0f} | "
            f"${r['fit_net']:,.0f} | ${r['leave_net']:,.0f} | ${r['ext_net']:,.0f} | "
            f"{r['max_dd']*100:.1f}% | {r['worst_pct']*100:.2f}% | "
            f"{r['n_pass']}/{r['n_win']} | {'YES' if r_legal else 'NO'} | {r['decision']} |"
        )
    lines.append("")
    lines.append("## vs prior candidates")
    lines.append("")
    lines.append("| Book | Chassis | $/mo (ref) | ≤60d @ legal-ish | Notes |")
    lines.append("|---|---|---:|---|---|")
    lines.append("| C5 | SMA50 daily + filters R=1 @0.01 | ~$450 | 0 | research ACCEPT; too slow |")
    lines.append("| C7 | H4-BREAK dual R=1 | ~$508 | 0; DD 17% | REJECT |")
    lines.append("| C11 | H1 mom dual R=2 @0.75% | negative | 0; DD ~60% | REJECT |")
    lines.append("| C12 | C5 stack N=3 | ~$448 | 0/850 | REJECT + structural |")
    lines.append(
        f"| **C13** | **London ORB R=1.5 @0.75%** | **${s['ho_pace']:,.0f}** | "
        f"**{s['n_pass']}/{s['n_win']}** | **{s['decision']}** |"
    )
    lines.append("")
    lines.append("## Full-sample monthly P&L @0.75% (ET exit month)")
    lines.append("")
    lines.append("| ET exit month | Trades | Net $ |")
    lines.append("|---|---:|---:|")
    for m, n, pnl in s["months_full"]:
        lines.append(f"| {m} | {n} | {pnl:,.2f} |")
    lines.append("")
    lines.append("## Research-next")
    lines.append("")
    lines.append(nxt)
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.")
    lines.append("")

    text = "\n".join(lines)
    OUT.write_text(text)
    print(f"Wrote {OUT}")

    PACK.mkdir(parents=True, exist_ok=True)
    runner_src = Path("/workspace/btc-strategies/run_candidate_13.py").read_text()
    (PACK / "ftmo-candidate-13.md").write_text(SPEC.read_text())
    (PACK / "candidate-13-results.md").write_text(text)
    (PACK / "run_candidate_13.py").write_text(runner_src)

    still_blocked = s["decision"] != "ACCEPT"
    blocked_line = (
        "≤60d BTC-only still **blocked** at FTMO 5%/10% after C13."
        if still_blocked
        else "C13 opened a measured ≤60d path — still research-only."
    )

    status = f"""# BTC FTMO research baseline (2026-10-07)

**Status: C13 {s['decision']}** — London ORB exclusive dual R=1.5 @0.75% (chassis={s['meta'].get('chassis')}). HO ${s['ho_net']:,.0f} (~${s['ho_pace']:,.0f}/mo); fit ${s['fit_net']:,.0f}; leave-out ${s['leave_net']:,.0f}; ext ${s['ext_net']:,.0f}; max DD {s['max_dd']*100:.1f}%; 60d windows {s['n_pass']}/{s['n_win']}. Binding: {binding}. {blocked_line} C4 still armed/ops path. Do not deploy C5–C13.

## Candidate 13 (new measurement)
London ORB (07:00–08:00 UTC) exclusive dual + opposite-side stop + R=1.5 + 0.75% risk + −3% Prague kill. Cost: spread=15 (C7/C11 parity). No SMA50.

| Cfg | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | ${summaries[0.005]['ho_pace']:,.0f} | ${summaries[0.005]['fit_net']:,.0f} | ${summaries[0.005]['leave_net']:,.0f} | ${summaries[0.005]['ext_net']:,.0f} | {summaries[0.005]['worst_pct']*100:.2f}% | {summaries[0.005]['max_dd']*100:.1f}% | {summaries[0.005]['n_pass']}/{summaries[0.005]['n_win']} | {'YES' if summaries[0.005]['max_dd']<=0.10 and summaries[0.005]['n_fail_days']==0 else 'NO'} |
| 0.75% | ${s['ho_pace']:,.0f} | ${s['fit_net']:,.0f} | ${s['leave_net']:,.0f} | ${s['ext_net']:,.0f} | {s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | {s['n_pass']}/{s['n_win']} | {'YES' if legal else 'NO'} |
| 1.00% | ${summaries[0.01]['ho_pace']:,.0f} | ${summaries[0.01]['fit_net']:,.0f} | ${summaries[0.01]['leave_net']:,.0f} | ${summaries[0.01]['ext_net']:,.0f} | {summaries[0.01]['worst_pct']*100:.2f}% | {summaries[0.01]['max_dd']*100:.1f}% | {summaries[0.01]['n_pass']}/{summaries[0.01]['n_win']} | {'YES' if summaries[0.01]['max_dd']<=0.10 and summaries[0.01]['n_fail_days']==0 else 'NO'} |

**{s['decision']}** as ≤60d vehicle. Binding: {binding}.

Research-next: {nxt}

## Prior
- C12 REJECT + structural (0/850; stack ≠ pace)
- C11 REJECT (H1 mom EDGE+DD)
- C10 CONDITIONAL (R-trail; PACE+DD)
- C9 CONDITIONAL; C8 REJECT; C7 REJECT; C6 REJECT
- C5 research ACCEPT @0.01; too slow
- C4 armed/ops path; fit fail

## Live
Live catalogue drip / C4 ops: do not touch from research. Nothing arms from this folder.
"""
    ROOT_STATUS.write_text(status)
    (PACK / "STATUS.md").write_text(status)
    (PACK / "README.md").write_text(
        f"# 2026-10-07 Candidate 13\n\nDecision: **{s['decision']}**\n\n"
        f"Chassis: `{s['meta'].get('chassis')}`\n\n"
        f"See `candidate-13-results.md` and `ftmo-candidate-13.md`.\n"
    )

    pr_body = f"""## Candidate 13 — London Opening Range Breakout (ORB) Exclusive Dual (research)

**Decision: {s['decision']}**

London ORB (07:00–08:00 UTC) exclusive dual + opposite-side stop (not mid) + R=1.5 TP + 0.75% equity risk + −3% Prague-day kill.
Cost model: FTMO spread=15 (HF parity with C7/C11). Not C4/C5 %. **No SMA50** in entry/regime.
Chassis measured: `{s['meta'].get('chassis')}`.

### Headline
- HO net: ${s['ho_net']:,.2f} (~${s['ho_pace']:,.0f}/mo)
- Fit / Leave-out / Ext: ${s['fit_net']:,.2f} / ${s['leave_net']:,.2f} / ${s['ext_net']:,.2f}
- Max DD: {s['max_dd']*100:.2f}%
- Worst Prague day: {s['worst_pct']*100:.2f}%
- ≤60d clean windows @0.75%: **{s['n_pass']}/{s['n_win']}**
- Binding: {binding}
- {blocked_line}

### Risk table
| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | ${summaries[0.005]['ho_pace']:,.0f} | ${summaries[0.005]['fit_net']:,.0f} | ${summaries[0.005]['leave_net']:,.0f} | ${summaries[0.005]['ext_net']:,.0f} | {summaries[0.005]['worst_pct']*100:.2f}% | {summaries[0.005]['max_dd']*100:.1f}% | {summaries[0.005]['n_pass']}/{summaries[0.005]['n_win']} | {'YES' if summaries[0.005]['max_dd']<=0.10 and summaries[0.005]['n_fail_days']==0 else 'NO'} |
| 0.75% | ${s['ho_pace']:,.0f} | ${s['fit_net']:,.0f} | ${s['leave_net']:,.0f} | ${s['ext_net']:,.0f} | {s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | {s['n_pass']}/{s['n_win']} | {'YES' if legal else 'NO'} |
| 1.00% | ${summaries[0.01]['ho_pace']:,.0f} | ${summaries[0.01]['fit_net']:,.0f} | ${summaries[0.01]['leave_net']:,.0f} | ${summaries[0.01]['ext_net']:,.0f} | {summaries[0.01]['worst_pct']*100:.2f}% | {summaries[0.01]['max_dd']*100:.1f}% | {summaries[0.01]['n_pass']}/{summaries[0.01]['n_win']} | {'YES' if summaries[0.01]['max_dd']<=0.10 and summaries[0.01]['n_fail_days']==0 else 'NO'} |

### Research-next
{nxt}

### Live
Research only — C4 / drip / FREEZE / MetaAPI / live VM untouched.

Files under `research/btc/2026-10-07-candidate-13/`.
"""
    PR_BODY.write_text(pr_body)
    (PACK / "GITHUB-PR-BODY.md").write_text(pr_body)

    # Compact summary for parent
    summary_path = Path("/workspace/btc-strategies/candidate-13-summary.txt")
    summary_path.write_text(
        f"DECISION={s['decision']}\n"
        f"CHASSIS={s['meta'].get('chassis')}\n"
        f"HO_PACE={s['ho_pace']:.2f}\n"
        f"HO_NET={s['ho_net']:.2f}\n"
        f"FIT={s['fit_net']:.2f}\n"
        f"LEAVE={s['leave_net']:.2f}\n"
        f"EXT={s['ext_net']:.2f}\n"
        f"WORST_DAY={s['worst_pct']*100:.2f}%\n"
        f"MAX_DD={s['max_dd']*100:.2f}%\n"
        f"WINDOWS={s['n_pass']}/{s['n_win']}\n"
        f"LEGAL={legal}\n"
        f"BINDING={binding}\n"
        f"TAG={tag}\n"
    )

    print("DECISION:", s["decision"])
    print("HO pace:", s["ho_pace"])
    print("60d:", s["n_pass"], "/", s["n_win"])
    print("DD:", s["max_dd"])
    print("Binding:", binding)
    print("Chassis:", s["meta"].get("chassis"))


if __name__ == "__main__":
    main()
