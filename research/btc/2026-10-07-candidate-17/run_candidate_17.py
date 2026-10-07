#!/usr/bin/env python3
"""Candidate 17: Pass-path search — dual C5+C15, C15@90d, H4-BREAK-6 hard-DD.

Research only. No live VM / MetaAPI / C4 / drip / FREEZE.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
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
OUT = Path("/workspace/btc-strategies/candidate-17-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-17-pass-path.md")
PACK = Path("/workspace/btc-strategies/2026-10-07-candidate-17")
ROOT_STATUS = Path("/workspace/btc-strategies/STATUS.md")
PR_BODY = Path("/workspace/btc-strategies/GITHUB-PR-BODY-C17.md")
SUMMARY_TXT = Path("/workspace/btc-strategies/candidate-17-summary.txt")

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 50.0
SPREAD = 15.0
DAILY_KILL = -0.03
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

HO_START = pd.Timestamp("2025-11-08 00:00:00+00:00")
HO_END = pd.Timestamp("2026-09-01 23:59:59+00:00")
EXT_START = pd.Timestamp("2026-09-02 00:00:00+00:00")
FIT_START = pd.Timestamp("2024-01-01 00:00:00+00:00")
FIT_END = pd.Timestamp("2025-11-07 23:59:59+00:00")

CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
DAY_FAIL = -0.05

# C5 locked
C5_STOP = 412.91
C5_TARGET = 412.91
C5_SLOPE_LB = 10
C5_ATR_WIN = 100
C5_ATR_PCT = 0.75

# C15 locked
C15_ATR_MULT = 1.0
C15_R = 2.0
C15_BB_PERIOD = 20
C15_BB_K = 2.0
C15_BW_LB = 100
C15_BW_PCT = 10.0

# C H4-BREAK-6 hard wrap
C_LOOKBACK = 6
C_ATR_MULT = 1.5  # original stop was 1.5 ATR


@dataclass
class Signal:
    book: str
    side: str
    entry_i: int
    entry_ts: pd.Timestamp
    entry: float
    exit_i: int
    exit_ts: pd.Timestamp
    exit: float
    reason: str
    stop_dist: float


@dataclass
class Trade:
    book: str
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


def prague_day(ts: pd.Timestamp) -> date:
    return ts.tz_convert(PRAGUE).date()


def et_month(ts: pd.Timestamp) -> str:
    t = ts.tz_convert(ET)
    return f"{t.year:04d}-{t.month:02d}"


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
    bars = m1.resample("1D", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return bars.dropna(subset=["open", "high", "low", "close"])


def atr14(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Simple rolling ATR14 (C15 parity: mean of last 14 TRs, rounded 4dp)."""
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


def atr14_simple(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Simple (non-Wilder) ATR14 used by original H4-BREAK-6."""
    n = len(close)
    atr = np.full(n, np.nan)
    trs = np.zeros(n)
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        trs[i] = max(hl, hc, lc)
    for i in range(14, n):
        atr[i] = round(float(np.mean(trs[i - 13 : i + 1])), 4)
    return atr


def bollinger_bw(close: np.ndarray, period: int = C15_BB_PERIOD, k: float = C15_BB_K):
    n = len(close)
    middle = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    bw = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = close[i - period + 1 : i + 1]
        m = float(np.mean(window))
        s = float(np.std(window, ddof=0))
        middle[i] = m
        upper[i] = m + k * s
        lower[i] = m - k * s
        if m != 0:
            bw[i] = (upper[i] - lower[i]) / m
    return middle, upper, lower, bw


def squeeze_flags(bw: np.ndarray, lookback: int = C15_BW_LB, pct: float = C15_BW_PCT):
    n = len(bw)
    sq = np.zeros(n, dtype=bool)
    p10 = np.full(n, np.nan)
    for i in range(lookback - 1, n):
        window = bw[i - lookback + 1 : i + 1]
        if np.any(~np.isfinite(window)):
            continue
        thr = float(np.percentile(window, pct))
        p10[i] = thr
        sq[i] = bool(np.isfinite(bw[i]) and bw[i] <= thr)
    return sq, p10


def scan_m1_exit(
    m1_open, m1_high, m1_low, m1_index, entry_i, side, stop, target
) -> tuple[int, float, str] | None:
    n_m1 = len(m1_index)
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
                return j, op, "gap-stop"
            if gap_tp and not gap_sl:
                return j, target, "gap-target"
            return j, stop, "both-stop"
        if hit_sl:
            return j, (op if gap_sl else stop), ("gap-stop" if gap_sl else "stop")
        return j, (op if gap_tp else target), ("gap-target" if gap_tp else "target")
    return None


# ---------- C15 signal templates ----------
def c15_signals(m1: pd.DataFrame, h4: pd.DataFrame) -> list[Signal]:
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14(high, low, close)
    middle, upper, lower, bw = bollinger_bw(close)
    sq_flag, p10 = squeeze_flags(bw)

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)
    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    signals: list[Signal] = []
    in_trade_until = -1
    for t in range(1, len(h4)):
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        if not np.isfinite(upper[t]) or not np.isfinite(lower[t]) or not np.isfinite(bw[t]):
            continue
        if not np.isfinite(p10[t - 1]):
            continue
        if not sq_flag[t - 1]:
            continue
        if close[t] > upper[t]:
            side = "long"
        elif close[t] < lower[t]:
            side = "short"
        else:
            continue
        entry_i = int(end_locs[t])
        if entry_i >= n_m1 or entry_i <= in_trade_until:
            continue
        entry_px = float(m1_open[entry_i])
        stop_dist = C15_ATR_MULT * float(atr[t])
        if stop_dist <= 0:
            continue
        target_dist = C15_R * stop_dist
        if side == "long":
            stop, target = entry_px - stop_dist, entry_px + target_dist
            if entry_px <= stop:
                continue
        else:
            stop, target = entry_px + stop_dist, entry_px - target_dist
            if entry_px >= stop:
                continue
        ex = scan_m1_exit(m1_open, m1_high, m1_low, m1_index, entry_i, side, stop, target)
        if ex is None:
            in_trade_until = n_m1 - 1
            continue
        exit_i, exit_px, reason = ex
        signals.append(
            Signal(
                book="c15",
                side=side,
                entry_i=entry_i,
                entry_ts=m1_index[entry_i],
                entry=entry_px,
                exit_i=exit_i,
                exit_ts=m1_index[exit_i],
                exit=exit_px,
                reason=reason,
                stop_dist=stop_dist,
            )
        )
        in_trade_until = exit_i
    return signals


# ---------- C5 signal templates (spread=15 cost model; % risk sized at replay) ----------
def c5_signals(m1: pd.DataFrame, daily: pd.DataFrame) -> list[Signal]:
    d_close = daily["close"]
    d_high = daily["high"].to_numpy()
    d_low = daily["low"].to_numpy()
    d_cls = daily["close"].to_numpy()
    sma50 = d_close.rolling(50, min_periods=50).mean()
    atr = atr14(d_high, d_low, d_cls)  # Wilder-style on daily

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)

    days = list(daily.index)
    day_pos = {d: i for i, d in enumerate(days)}

    signals: list[Signal] = []
    in_trade_until = -1

    # Entry days: UTC midnights that exist in M1
    # Walk from first usable day after SMA50 warmup
    for di, day_ts in enumerate(days):
        if di < 50:
            continue
        # signal uses PRIOR day close vs SMA50
        if di < 1:
            continue
        prior = days[di - 1]
        prior_i = di - 1
        pc = float(d_close.loc[prior])
        ps = sma50.loc[prior]
        if not np.isfinite(ps):
            continue
        if pc > float(ps):
            side = "long"
        elif pc < float(ps):
            side = "short"
        else:
            continue

        # Slope E: SMA50 rising/falling over 10 series days
        if prior_i < C5_SLOPE_LB:
            continue
        ago = days[prior_i - C5_SLOPE_LB]
        s_ago = sma50.loc[ago]
        if not np.isfinite(s_ago):
            continue
        if side == "long" and not (float(ps) > float(s_ago)):
            continue
        if side == "short" and not (float(ps) < float(s_ago)):
            continue

        # V75: prior ATR < P75 of prior 100d ATR
        if prior_i < C5_ATR_WIN - 1:
            continue
        atr_p = atr[prior_i]
        if not np.isfinite(atr_p):
            continue
        window = atr[prior_i - (C5_ATR_WIN - 1) : prior_i + 1]
        vals = window[np.isfinite(window)]
        if len(vals) < 50:
            continue
        thr = float(np.percentile(vals, C5_ATR_PCT * 100))
        if atr_p >= thr:
            continue

        # Entry at this day's UTC midnight open (first M1 at/after day start)
        entry_i = int(m1_index.searchsorted(day_ts, side="left"))
        if entry_i >= n_m1:
            continue
        # Require exact-ish midnight bar (same calendar day UTC)
        if m1_index[entry_i].floor("D") != day_ts:
            # missing midnight — skip like C5
            continue
        if entry_i <= in_trade_until:
            continue

        entry_px = float(m1_open[entry_i])
        stop_dist = C5_STOP
        if side == "long":
            stop, target = entry_px - C5_STOP, entry_px + C5_TARGET
            if entry_px <= stop:
                continue
        else:
            stop, target = entry_px + C5_STOP, entry_px - C5_TARGET
            if entry_px >= stop:
                continue
        ex = scan_m1_exit(m1_open, m1_high, m1_low, m1_index, entry_i, side, stop, target)
        if ex is None:
            in_trade_until = n_m1 - 1
            continue
        exit_i, exit_px, reason = ex
        signals.append(
            Signal(
                book="c5",
                side=side,
                entry_i=entry_i,
                entry_ts=m1_index[entry_i],
                entry=entry_px,
                exit_i=exit_i,
                exit_ts=m1_index[exit_i],
                exit=exit_px,
                reason=reason,
                stop_dist=stop_dist,
            )
        )
        in_trade_until = exit_i
    return signals


# ---------- H4-BREAK-6 hard-DD (Workstream C) ----------
def h4_break6_signals(
    m1: pd.DataFrame, h4: pd.DataFrame, r_mult: float
) -> list[Signal]:
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14_simple(high, low, close)

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)
    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    signals: list[Signal] = []
    in_trade_until = -1
    for t in range(C_LOOKBACK, len(h4)):
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        prior_high = float(np.max(high[t - C_LOOKBACK : t]))
        if close[t] <= prior_high:
            continue
        # long only
        side = "long"
        entry_i = int(end_locs[t])
        if entry_i >= n_m1 or entry_i <= in_trade_until:
            continue
        entry_px = float(m1_open[entry_i])
        stop_dist = C_ATR_MULT * float(atr[t])
        if stop_dist <= 0:
            continue
        target_dist = r_mult * stop_dist
        stop = entry_px - stop_dist
        target = entry_px + target_dist
        if entry_px <= stop:
            continue
        ex = scan_m1_exit(m1_open, m1_high, m1_low, m1_index, entry_i, side, stop, target)
        if ex is None:
            in_trade_until = n_m1 - 1
            continue
        exit_i, exit_px, reason = ex
        signals.append(
            Signal(
                book="h4b6",
                side=side,
                entry_i=entry_i,
                entry_ts=m1_index[entry_i],
                entry=entry_px,
                exit_i=exit_i,
                exit_ts=m1_index[exit_i],
                exit=exit_px,
                reason=reason,
                stop_dist=stop_dist,
            )
        )
        in_trade_until = exit_i
    return signals


# ---------- Replay engines ----------
def replay_single(
    signals: list[Signal], risk: float
) -> tuple[list[Trade], dict, dict, dict]:
    equity = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    meta = {"signals": len(signals), "taken": 0, "skip_kill": 0, "skip_lots": 0}

    for sig in signals:
        pd_entry = prague_day(sig.entry_ts)
        if pd_entry in killed_days:
            meta["skip_kill"] += 1
            continue
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            meta["skip_kill"] += 1
            continue

        lots = round(equity * risk / sig.stop_dist, 2)
        lots = min(lots, MAX_LOT)
        if lots < MIN_LOT:
            meta["skip_lots"] += 1
            continue

        raw = (sig.exit - sig.entry) if sig.side == "long" else (sig.entry - sig.exit)
        pnl = raw * lots - SPREAD * lots
        equity += pnl
        meta["taken"] += 1
        pd_exit = prague_day(sig.exit_ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
        day_pnl[pd_exit] += pnl
        if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
            killed_days.add(pd_exit)
        trades.append(
            Trade(
                book=sig.book,
                side=sig.side,
                entry_ts=sig.entry_ts,
                entry=sig.entry,
                exit_ts=sig.exit_ts,
                exit=sig.exit,
                reason=sig.reason,
                lots=lots,
                stop_dist=sig.stop_dist,
                pnl=pnl,
                equity_after=equity,
            )
        )
    meta["final_equity"] = equity
    meta["killed_days"] = len(killed_days)
    return trades, day_pnl, day_start_eq, meta


def replay_dual(
    sigs_a: list[Signal],
    sigs_b: list[Signal],
    risk_a: float,
    risk_b: float,
    book_a: str = "c5",
    book_b: str = "c15",
) -> tuple[list[Trade], dict, dict, dict]:
    """Two independent books, shared equity + Prague kill. Max 1 pos per book."""
    equity = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    meta = {
        "signals_a": len(sigs_a),
        "signals_b": len(sigs_b),
        "taken_a": 0,
        "taken_b": 0,
        "skip_kill": 0,
        "skip_lots": 0,
        "skip_busy": 0,
    }

    # Merge entries chronologically; track open exit index per book
    entries = sorted(
        [(s.entry_i, s.entry_ts, "a", s) for s in sigs_a]
        + [(s.entry_i, s.entry_ts, "b", s) for s in sigs_b],
        key=lambda x: (x[0], 0 if x[2] == "a" else 1),
    )
    open_until = {"a": -1, "b": -1}
    risk = {"a": risk_a, "b": risk_b}

    # Pending exits to apply when we pass their exit_i (handled at entry time by checking
    # that we only open if entry_i > open_until[book]). Equity updates happen at exit
    # chronologically — so we must process events as entry+exit timeline.

    # Better: build event list of (time_i, kind, payload)
    events = []
    for s in sigs_a:
        events.append((s.entry_i, 0, "entry", "a", s))  # entries before exits same bar
        events.append((s.exit_i, 1, "exit", "a", s))
    for s in sigs_b:
        events.append((s.entry_i, 0, "entry", "b", s))
        events.append((s.exit_i, 1, "exit", "b", s))
    events.sort(key=lambda x: (x[0], x[1], 0 if x[3] == "a" else 1))

    open_sig: dict[str, Signal | None] = {"a": None, "b": None}
    open_lots: dict[str, float] = {"a": 0.0, "b": 0.0}
    # Map signal id -> whether taken (object identity)
    taken_ids: set[int] = set()

    for ei, _prio, kind, book, sig in events:
        if kind == "entry":
            if open_sig[book] is not None:
                meta["skip_busy"] += 1
                continue
            # Within-book exclusivity already in signal templates; dual may still race
            pd_entry = prague_day(sig.entry_ts)
            if pd_entry in killed_days:
                meta["skip_kill"] += 1
                continue
            if pd_entry not in day_start_eq:
                day_start_eq[pd_entry] = equity
            if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
                killed_days.add(pd_entry)
                meta["skip_kill"] += 1
                continue
            lots = round(equity * risk[book] / sig.stop_dist, 2)
            lots = min(lots, MAX_LOT)
            if lots < MIN_LOT:
                meta["skip_lots"] += 1
                continue
            open_sig[book] = sig
            open_lots[book] = lots
            taken_ids.add(id(sig))
            meta[f"taken_{book}"] += 1
        else:  # exit
            if open_sig[book] is None or id(open_sig[book]) != id(sig):
                continue  # never opened (killed/busy)
            lots = open_lots[book]
            raw = (sig.exit - sig.entry) if sig.side == "long" else (sig.entry - sig.exit)
            pnl = raw * lots - SPREAD * lots
            equity += pnl
            pd_exit = prague_day(sig.exit_ts)
            if pd_exit not in day_start_eq:
                day_start_eq[pd_exit] = equity - pnl
            day_pnl[pd_exit] += pnl
            if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
                killed_days.add(pd_exit)
            trades.append(
                Trade(
                    book=sig.book,
                    side=sig.side,
                    entry_ts=sig.entry_ts,
                    entry=sig.entry,
                    exit_ts=sig.exit_ts,
                    exit=sig.exit,
                    reason=sig.reason,
                    lots=lots,
                    stop_dist=sig.stop_dist,
                    pnl=pnl,
                    equity_after=equity,
                )
            )
            open_sig[book] = None
            open_lots[book] = 0.0

    meta["final_equity"] = equity
    meta["killed_days"] = len(killed_days)
    meta["taken"] = meta["taken_a"] + meta["taken_b"]
    # Sort trades by exit for DD path consistency
    trades.sort(key=lambda t: (t.exit_ts, t.book))
    # Recompute equity_after in exit order for DD
    eq = START_EQUITY
    # Need chronological exit rebuild — trades already sorted by exit
    # But pnl already applied in event order which equals exit order for each;
    # dual concurrent means exit order may differ from event application order.
    # Rebuild equity_after from sorted exits using stored pnl:
    eq = START_EQUITY
    for tr in trades:
        eq += tr.pnl
        tr.equity_after = eq
    meta["final_equity"] = eq
    return trades, day_pnl, day_start_eq, meta


# ---------- Metrics ----------
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


def worst_day_pct(day_pnl, day_start_eq):
    worst_d, worst_p = None, 0.0
    for d, pnl in day_pnl.items():
        start = day_start_eq.get(d, START_EQUITY)
        if start <= 0:
            continue
        pct = pnl / start
        if pct < worst_p:
            worst_p, worst_d = pct, d
    return worst_d, worst_p


def slice_pnl(trades, start, end=None):
    s = 0.0
    for tr in trades:
        if tr.exit_ts < start:
            continue
        if end is not None and tr.exit_ts > end:
            continue
        s += tr.pnl
    return s


def leave_out_two_best_ho(trades):
    by_m: dict[str, float] = defaultdict(float)
    for tr in trades:
        if HO_START <= tr.exit_ts <= HO_END:
            by_m[et_month(tr.exit_ts)] += tr.pnl
    if len(by_m) < 2:
        return [], slice_pnl(trades, HO_START, HO_END)
    top2 = [m for m, _ in sorted(by_m.items(), key=lambda kv: kv[1], reverse=True)[:2]]
    left = 0.0
    for tr in trades:
        if HO_START <= tr.exit_ts <= HO_END and et_month(tr.exit_ts) not in top2:
            left += tr.pnl
    return top2, left



def count_sequential_reset_passes(
    signals: list[Signal],
    risk: float,
    window_days: int = 90,
    start_filter: date | None = None,
    end_filter: date | None = None,
) -> tuple[int, int, list[dict]]:
    """True FTMO 2-step proxy: Challenge +10% on path, then RESET to 100k for Verification +5%,
    total calendar ≤ window_days. Per-stage floor 0.90 and no −5% Prague day.
    Single-book only (signal list already exclusive).
    """
    if not signals:
        return 0, 0, []

    # Precompute entry/exit prague days
    entries = signals
    first = prague_day(entries[0].entry_ts)
    last = prague_day(entries[-1].exit_ts)
    if start_filter:
        first = max(first, start_filter)
    if end_filter:
        last = min(last, end_filter)
    end_limit = last - timedelta(days=window_days - 1)
    if end_limit < first:
        return 0, 0, []

    n_win = 0
    passes = []
    cur = first
    while cur <= end_limit:
        ws = cur
        we = cur + timedelta(days=window_days - 1)
        n_win += 1

        # --- Challenge stage ---
        eq = START_EQUITY
        peak = eq
        day_pnl: dict[date, float] = defaultdict(float)
        day_start: dict[date, float] = {}
        killed: set[date] = set()
        chall_done = None
        chall_days = None
        breached = False
        i0 = 0
        # skip signals that exit before ws
        while i0 < len(entries) and prague_day(entries[i0].exit_ts) < ws:
            i0 += 1

        j = i0
        while j < len(entries):
            sig = entries[j]
            pd_e = prague_day(sig.entry_ts)
            if pd_e > we:
                break
            if pd_e < ws:
                j += 1
                continue
            if chall_done is not None:
                break
            if pd_e in killed:
                j += 1
                continue
            if pd_e not in day_start:
                day_start[pd_e] = eq
            if day_pnl[pd_e] / day_start[pd_e] <= DAILY_KILL:
                killed.add(pd_e)
                j += 1
                continue
            lots = round(eq * risk / sig.stop_dist, 2)
            lots = min(lots, MAX_LOT)
            if lots < MIN_LOT:
                j += 1
                continue
            raw = (sig.exit - sig.entry) if sig.side == "long" else (sig.entry - sig.exit)
            pnl = raw * lots - SPREAD * lots
            eq += pnl
            pd_x = prague_day(sig.exit_ts)
            if pd_x > we:
                # exit outside window — abandon
                breached = True
                break
            if pd_x not in day_start:
                day_start[pd_x] = eq - pnl
            day_pnl[pd_x] += pnl
            if day_pnl[pd_x] / day_start[pd_x] <= DAY_FAIL:
                breached = True
                break
            if day_pnl[pd_x] / day_start[pd_x] <= DAILY_KILL:
                killed.add(pd_x)
            if eq > peak:
                peak = eq
            if eq <= START_EQUITY * FLOOR_MULT:
                breached = True
                break
            if eq >= START_EQUITY * CHALLENGE_MULT:
                chall_done = pd_x
                chall_days = (pd_x - ws).days + 1
                j += 1
                break
            j += 1

        if breached or chall_done is None:
            cur += timedelta(days=1)
            continue

        # --- Verification stage (RESET) ---
        eq = START_EQUITY
        day_pnl = defaultdict(float)
        day_start = {}
        killed = set()
        ver_done = None
        ver_days = None
        while j < len(entries):
            sig = entries[j]
            pd_e = prague_day(sig.entry_ts)
            if pd_e > we:
                break
            if pd_e < chall_done:  # should not happen
                j += 1
                continue
            # verification entries on/after chall_done
            if pd_e in killed:
                j += 1
                continue
            if pd_e not in day_start:
                day_start[pd_e] = eq
            if day_pnl[pd_e] / day_start[pd_e] <= DAILY_KILL:
                killed.add(pd_e)
                j += 1
                continue
            lots = round(eq * risk / sig.stop_dist, 2)
            lots = min(lots, MAX_LOT)
            if lots < MIN_LOT:
                j += 1
                continue
            raw = (sig.exit - sig.entry) if sig.side == "long" else (sig.entry - sig.exit)
            pnl = raw * lots - SPREAD * lots
            eq += pnl
            pd_x = prague_day(sig.exit_ts)
            if pd_x > we:
                break
            if pd_x not in day_start:
                day_start[pd_x] = eq - pnl
            day_pnl[pd_x] += pnl
            if day_pnl[pd_x] / day_start[pd_x] <= DAY_FAIL:
                breached = True
                break
            if day_pnl[pd_x] / day_start[pd_x] <= DAILY_KILL:
                killed.add(pd_x)
            if eq <= START_EQUITY * FLOOR_MULT:
                breached = True
                break
            if eq >= START_EQUITY * 1.05:  # Verification +5%
                ver_done = pd_x
                ver_days = (pd_x - chall_done).days + 1
                break
            j += 1

        if not breached and ver_done is not None and chall_days is not None and ver_days is not None:
            total = (ver_done - ws).days + 1
            if total <= window_days:
                passes.append(
                    {
                        "start": ws.isoformat(),
                        "chall_done": chall_done.isoformat(),
                        "ver_done": ver_done.isoformat(),
                        "chall_days": chall_days,
                        "ver_days": ver_days,
                        "total_days": total,
                    }
                )
        cur += timedelta(days=1)

    return len(passes), n_win, passes[:15]


def count_pass_windows(
    trades: list[Trade],
    day_pnl: dict,
    day_start_eq: dict,
    window_days: int,
    start_filter: date | None = None,
    end_filter: date | None = None,
) -> tuple[int, int, list[dict], list[int]]:
    """Return n_pass, n_windows, sample passes, days-to-both list for passes."""
    if not trades:
        return 0, 0, [], []

    exits = [(tr.exit_ts, tr.equity_after) for tr in trades]
    all_days = sorted(set(day_start_eq.keys()) | {prague_day(t) for t, _ in exits})
    if not all_days:
        return 0, 0, [], []

    first_day = all_days[0]
    last_day = all_days[-1]
    if start_filter:
        first_day = max(first_day, start_filter)
    if end_filter:
        last_day = min(last_day, end_filter)

    passes = []
    days_to_both: list[int] = []
    n_windows = 0
    cur = first_day
    end_limit = last_day - timedelta(days=window_days - 1)
    if end_limit < cur:
        return 0, 0, [], []

    exit_pdays = [prague_day(ts) for ts, _ in exits]
    exit_eqs = [eq for _, eq in exits]
    exit_dates_only = exit_pdays

    while cur <= end_limit:
        ws = cur
        we = cur + timedelta(days=window_days - 1)
        n_windows += 1

        start_eq = START_EQUITY
        for i, pd_ in enumerate(exit_pdays):
            if pd_ < ws:
                start_eq = exit_eqs[i]
            else:
                break

        # Collect exits in window with timestamps for days-to-both
        window_items = [
            (exits[i][0], exit_eqs[i], exit_pdays[i])
            for i in range(len(exits))
            if ws <= exit_pdays[i] <= we
        ]
        if not window_items:
            cur += timedelta(days=1)
            continue

        window_eqs = [eq for _, eq, _ in window_items]
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
            # days from ws to first exit that hits BOTH_MULT
            dtb = None
            for ts, eq, pd_ in window_items:
                if eq >= start_eq * BOTH_MULT:
                    dtb = (pd_ - ws).days + 1
                    break
            if dtb is not None:
                days_to_both.append(dtb)
            passes.append(
                {
                    "start": ws.isoformat(),
                    "end": we.isoformat(),
                    "start_eq": start_eq,
                    "max_mult": max_eq / start_eq if start_eq else 0,
                    "min_mult": min_eq / start_eq if start_eq else 0,
                    "worst_day": worst_day_in,
                    "days_to_both": dtb,
                }
            )
        cur += timedelta(days=1)

    return len(passes), n_windows, passes[:15], days_to_both


def ho_calendar_months(trades) -> float:
    """HO length in months for pace."""
    return (HO_END - HO_START).days / 30.4375


def summarize(label, trades, day_pnl, day_start_eq, meta, risk_note: str) -> dict:
    ho_net = slice_pnl(trades, HO_START, HO_END)
    ext_net = slice_pnl(trades, EXT_START, None)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    full_net = (trades[-1].equity_after - START_EQUITY) if trades else 0.0
    mos = ho_calendar_months(trades)
    ho_pace = ho_net / mos if mos > 0 else 0.0
    dd = max_realized_dd(trades)
    wd, wp = worst_day_pct(day_pnl, day_start_eq)
    top2, leave = leave_out_two_best_ho(trades)

    n60, w60, s60, d60 = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, s90, d90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)

    # HO-only 90d windows
    ho_start_d = HO_START.tz_convert(PRAGUE).date()
    ho_end_d = HO_END.tz_convert(PRAGUE).date()
    n90_ho, w90_ho, s90_ho, d90_ho = count_pass_windows(
        trades, day_pnl, day_start_eq, 90, start_filter=ho_start_d, end_filter=ho_end_d
    )

    fail_days = sum(
        1
        for d, pnl in day_pnl.items()
        if day_start_eq.get(d, START_EQUITY) > 0
        and pnl / day_start_eq[d] <= DAY_FAIL
    )

    return {
        "label": label,
        "risk_note": risk_note,
        "n_trades": len(trades),
        "ho_net": ho_net,
        "ext_net": ext_net,
        "fit_net": fit_net,
        "full_net": full_net,
        "ho_pace": ho_pace,
        "dd": dd,
        "worst_day": wd,
        "worst_pct": wp,
        "leave_top2": top2,
        "leave_net": leave,
        "fail_days": fail_days,
        "n60": n60,
        "w60": w60,
        "s60": s60,
        "n90": n90,
        "w90": w90,
        "s90": s90,
        "d90": d90,
        "n90_ho": n90_ho,
        "w90_ho": w90_ho,
        "s90_ho": s90_ho,
        "d90_ho": d90_ho,
        "meta": meta,
        "legal_dd": dd <= 0.10 and wp >= -0.05 and fail_days == 0,
        "g_ho": ho_net > 0,
        "g_ext": ext_net >= 0,
        "g_leave": leave > 0,
        "g_fit": fit_net >= -10_000,
    }


def path_label(s: dict) -> str:
    """ACCEPT / CONDITIONAL / FAIL."""
    legal = s["legal_dd"] and s["g_ho"] and s["g_leave"] and s["g_fit"]
    # ≥10% of HO 90d windows OR any full-sample 90d with legal
    ho_frac = (s["n90_ho"] / s["w90_ho"]) if s["w90_ho"] else 0.0
    full_pass = s["n90"] >= 1
    pace_ok = s["ho_pace"] >= 5000  # ~$5k/mo needed for $15k/90d

    if legal and s["g_ext"] and (full_pass or ho_frac >= 0.10 or pace_ok):
        if full_pass or ho_frac >= 0.10:
            return "ACCEPT"
        return "CONDITIONAL"  # pace theoretical but no window
    if legal and (full_pass or ho_frac >= 0.10):
        return "CONDITIONAL"  # Ext fail or weak
    if legal and pace_ok and not s["g_ext"]:
        return "CONDITIONAL"
    return "FAIL"


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def main():
    PACK.mkdir(parents=True, exist_ok=True)
    print("Loading M1…")
    m1 = load_m1_merged()
    print(f"  m1={len(m1)} {m1.index[0]} → {m1.index[-1]}")
    h4 = build_h4(m1)
    daily = build_daily(m1)
    print(f"  h4={len(h4)} daily={len(daily)}")

    print("Building C15 signals…")
    sig_c15 = c15_signals(m1, h4)
    print(f"  C15 templates: {len(sig_c15)}")
    print("Building C5 signals…")
    sig_c5 = c5_signals(m1, daily)
    print(f"  C5 templates: {len(sig_c5)}")
    print("Building H4-BREAK-6 R=1 / R=1.5 signals…")
    sig_h4_r1 = h4_break6_signals(m1, h4, r_mult=1.0)
    sig_h4_r15 = h4_break6_signals(m1, h4, r_mult=1.5)
    print(f"  H4B6 R=1: {len(sig_h4_r1)}; R=1.5: {len(sig_h4_r15)}")

    results: dict[str, dict] = {}

    # ===== Workstream B: C15 alone @90d =====
    print("\n=== Workstream B: C15 @ 0.75% / 1.00% ===")
    for risk, tag in [(0.0075, "B_c15_0.75"), (0.01, "B_c15_1.00")]:
        trades, day_pnl, day_start_eq, meta = replay_single(sig_c15, risk)
        s = summarize(tag, trades, day_pnl, day_start_eq, meta, f"c15@{risk*100:.2f}%")
        nseq, wseq, sseq = count_sequential_reset_passes(sig_c15, risk, 90)
        s["nseq90"] = nseq
        s["wseq90"] = wseq
        s["sseq90"] = sseq
        # If sequential reset finds passes and legal → upgrade path
        if s["legal_dd"] and s["g_ho"] and s["g_leave"] and s["g_fit"] and nseq >= 1:
            if s["g_ext"]:
                s["path"] = "ACCEPT"
            else:
                s["path"] = "CONDITIONAL"
        else:
            s["path"] = path_label(s)
        results[tag] = s
        print(
            f"  {tag}: HO ${s['ho_pace']:.0f}/mo DD {s['dd']*100:.1f}% "
            f"90d {s['n90']}/{s['w90']} seq90 {nseq}/{wseq} HO90 {s['n90_ho']}/{s['w90_ho']} "
            f"Ext ${s['ext_net']:.0f} → {s['path']}"
        )

    # ===== Workstream A: Dual C5+C15 =====
    print("\n=== Workstream A: Dual C5+C15 ===")
    for ra, rb, tag in [
        (0.0040, 0.0040, "A_dual_0.40_0.40"),
        (0.0050, 0.0050, "A_dual_0.50_0.50"),
        (0.0035, 0.0035, "A_dual_0.35_0.35"),
    ]:
        trades, day_pnl, day_start_eq, meta = replay_dual(sig_c5, sig_c15, ra, rb)
        s = summarize(
            tag, trades, day_pnl, day_start_eq, meta, f"c5@{ra*100:.2f}%+c15@{rb*100:.2f}%"
        )
        s["nseq90"] = 0
        s["wseq90"] = 0
        s["sseq90"] = []
        s["path"] = path_label(s)
        results[tag] = s
        print(
            f"  {tag}: trades={s['n_trades']} HO ${s['ho_pace']:.0f}/mo DD {s['dd']*100:.1f}% "
            f"90d {s['n90']}/{s['w90']} HO90 {s['n90_ho']}/{s['w90_ho']} "
            f"Ext ${s['ext_net']:.0f} → {s['path']}"
        )

    # ===== Workstream C: H4-BREAK-6 hard DD =====
    print("\n=== Workstream C: H4-BREAK-6 hard wrap ===")
    for sigs, risk, rlab, tag in [
        (sig_h4_r1, 0.0075, "R=1", "C_h4b6_R1_0.75"),
        (sig_h4_r15, 0.0075, "R=1.5", "C_h4b6_R15_0.75"),
        (sig_h4_r1, 0.005, "R=1", "C_h4b6_R1_0.50"),
        (sig_h4_r15, 0.005, "R=1.5", "C_h4b6_R15_0.50"),
        (sig_h4_r1, 0.0065, "R=1", "C_h4b6_R1_0.65"),
        (sig_h4_r15, 0.0065, "R=1.5", "C_h4b6_R15_0.65"),
    ]:
        trades, day_pnl, day_start_eq, meta = replay_single(sigs, risk)
        s = summarize(
            tag, trades, day_pnl, day_start_eq, meta, f"h4b6 {rlab} @{risk*100:.2f}%"
        )
        nseq, wseq, sseq = count_sequential_reset_passes(sigs, risk, 90)
        s["nseq90"] = nseq
        s["wseq90"] = wseq
        s["sseq90"] = sseq
        if s["legal_dd"] and s["g_ho"] and s["g_leave"] and s["g_fit"] and nseq >= 1:
            s["path"] = "ACCEPT" if s["g_ext"] else "CONDITIONAL"
        else:
            s["path"] = path_label(s)
        results[tag] = s
        print(
            f"  {tag}: HO ${s['ho_pace']:.0f}/mo DD {s['dd']*100:.1f}% "
            f"90d {s['n90']}/{s['w90']} seq90 {nseq}/{wseq} Ext ${s['ext_net']:.0f} → {s['path']}"
        )

    # Pick best path
    rank = {"ACCEPT": 0, "CONDITIONAL": 1, "FAIL": 2}
    ordered = sorted(
        results.items(),
        key=lambda kv: (
            rank.get(kv[1]["path"], 9),
            0 if kv[1]["legal_dd"] else 1,
            -kv[1].get("nseq90", 0),
            -kv[1]["n90_ho"],
            -kv[1]["n90"],
            -kv[1]["ho_pace"],
            kv[1]["dd"],
        ),
    )
    best_tag, best = ordered[0]

    # Residual math if no ACCEPT/CONDITIONAL with windows
    need_mo = 15_000 / 3.0  # $5k/mo for 90d → $15k
    best_legal = None
    for tag, s in ordered:
        if s["legal_dd"] and s["g_ho"]:
            best_legal = (tag, s)
            break
    if best_legal is None:
        best_legal = (best_tag, best)

    bl_tag, bl = best_legal
    gap = max(0.0, need_mo - bl["ho_pace"])
    residual = {
        "best_legal_tag": bl_tag,
        "best_legal_pace": bl["ho_pace"],
        "need_mo": need_mo,
        "gap_mo": gap,
        "second_instrument_mo": gap,  # dollars/mo needed from US100/Gold etc.
        "shared_dd_budget_left": max(0.0, 0.10 - bl["dd"]),
    }

    # Write results markdown
    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = []
    lines.append("# Candidate 17 Results — Pass Path Package (≤90d)")
    lines.append("")
    lines.append(f"**Best path label: {best['path']}** (`{best_tag}`)")
    lines.append("")
    lines.append(
        f"**One sentence:** {best['path']} — {best_tag}: HO ${best['ho_pace']:,.0f}/mo; "
        f"DD {best['dd']*100:.1f}%; ≤90d {best['n90']}/{best['w90']} "
        f"(HO-only {best['n90_ho']}/{best['w90_ho']}); Ext ${best['ext_net']:,.0f}."
    )
    lines.append("")
    lines.append(f"**Measured:** {now}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**Spec:** `{SPEC}`")
    lines.append("")
    lines.append("## THE PASS PATH")
    lines.append("")
    if best["path"] in ("ACCEPT", "CONDITIONAL") and (
        best["n90"] >= 1 or best["n90_ho"] >= 1 or best["ho_pace"] >= need_mo
    ):
        med = (
            float(np.median(best["d90"]))
            if best["d90"]
            else (float(np.median(best["d90_ho"])) if best["d90_ho"] else None)
        )
        lines.append(
            f"**{best['path']}:** `{best_tag}` ({best['risk_note']}). "
            f"Holdout pace **${best['ho_pace']:,.0f}/mo**, max DD **{best['dd']*100:.1f}%**, "
            f"worst day **{best['worst_pct']*100:.2f}%**, "
            f"≤90d both-stage windows **{best['n90']}/{best['w90']}** "
            f"(HO-only **{best['n90_ho']}/{best['w90_ho']}**)"
            + (f", median days-to-+15.5% **{med:.0f}**" if med else "")
            + f". Ext **${best['ext_net']:,.0f}** "
            + ("(PASS Ext)." if best["g_ext"] else "(FAIL Ext — do not deploy until Ext fixed).")
        )
    else:
        lines.append(
            f"**Closest measured path:** `{bl_tag}` ({bl['risk_note']}). "
            f"HO pace **${bl['ho_pace']:,.0f}/mo** vs **${need_mo:,.0f}/mo** needed for +$15k in 90d "
            f"(gap **${gap:,.0f}/mo**). Max DD **{bl['dd']*100:.1f}%** "
            f"(budget left **{residual['shared_dd_budget_left']*100:.1f}%** for a second instrument). "
            f"**Minimum second-instrument contribution: +${gap:,.0f}/mo** at shared DD ≤10% "
            f"to close the ≤90d pass. ≤90d windows on this BTC book: "
            f"{bl['n90']}/{bl['w90']} (HO {bl['n90_ho']}/{bl['w90_ho']})."
        )
    lines.append("")
    lines.append("## Workstream scoreboard")
    lines.append("")
    lines.append(
        "| Tag | Path | HO $/mo | Fit | Leave | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 reset | HO≤90d | Legal |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for tag, s in ordered:
        lines.append(
            f"| `{tag}` | **{s['path']}** | ${s['ho_pace']:,.0f} | ${s['fit_net']:,.0f} | "
            f"${s['leave_net']:,.0f} | ${s['ext_net']:,.0f} | {s['worst_pct']*100:.2f}% | "
            f"{s['dd']*100:.1f}% | {s['n60']}/{s['w60']} | {s['n90']}/{s['w90']} | "
            f"{s.get('nseq90',0)}/{s.get('wseq90',0)} | "
            f"{s['n90_ho']}/{s['w90_ho']} | {'YES' if s['legal_dd'] else 'NO'} |"
        )
    lines.append("")

    # Detail sections
    for ws_name, prefix in [
        ("Workstream A — Dual C5+C15", "A_"),
        ("Workstream B — C15 ≤90d", "B_"),
        ("Workstream C — H4-BREAK-6 hard DD", "C_"),
    ]:
        lines.append(f"## {ws_name}")
        lines.append("")
        for tag, s in ordered:
            if not tag.startswith(prefix):
                continue
            lines.append(f"### `{tag}` — {s['path']}")
            lines.append("")
            lines.append(f"- Risk: {s['risk_note']}")
            lines.append(f"- Trades: {s['n_trades']}; meta: {s['meta']}")
            lines.append(
                f"- HO ${s['ho_net']:,.2f} (~${s['ho_pace']:,.0f}/mo); Fit ${s['fit_net']:,.2f}; "
                f"Leave {s['leave_top2']} → ${s['leave_net']:,.2f}; Ext ${s['ext_net']:,.2f}"
            )
            lines.append(
                f"- Worst Prague day: {s['worst_day']} {s['worst_pct']*100:.2f}%; "
                f"fail-days={s['fail_days']}; max DD {s['dd']*100:.2f}%"
            )
            lines.append(
                f"- ≤60d {s['n60']}/{s['w60']}; ≤90d {s['n90']}/{s['w90']}; "
                f"HO≤90d {s['n90_ho']}/{s['w90_ho']}"
            )
            if s["d90"]:
                lines.append(
                    f"- Days-to-+15.5% (full-sample passes): "
                    f"median {np.median(s['d90']):.0f}, "
                    f"min {min(s['d90'])}, max {max(s['d90'])}"
                )
            if s["s90"]:
                lines.append("- Sample ≤90d passes:")
                for p in s["s90"][:5]:
                    lines.append(
                        f"  - {p['start']}→{p['end']}: max×{p['max_mult']:.3f} "
                        f"min×{p['min_mult']:.3f} worst_day={p['worst_day']*100:.2f}% "
                        f"days_to_both={p['days_to_both']}"
                    )
            lines.append("")

    lines.append("## Residual / second-instrument math")
    lines.append("")
    lines.append(
        f"Target pace for +$15k in 90d: **${need_mo:,.0f}/mo**. "
        f"Best legal BTC book `{bl_tag}`: **${bl['ho_pace']:,.0f}/mo**. "
        f"Gap: **${gap:,.0f}/mo** must come from a second instrument "
        f"(e.g. US100 / Gold) while shared max DD stays ≤10% "
        f"(BTC already uses {bl['dd']*100:.1f}%, budget left {residual['shared_dd_budget_left']*100:.1f}%)."
    )
    lines.append("")
    lines.append("## Cost model note")
    lines.append("")
    lines.append(
        "Unified on FTMO spread=15 × lots (commission 0, swap 0) for A/B/C. "
        "C5 originally used catalogue 0.065%+swap at vol 0.01; C17 dual/replay "
        "re-sizes C5 with % equity risk and spread=15 for shared-DD apples-to-apples."
    )
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    (PACK / "candidate-17-results.md").write_text("\n".join(lines), encoding="utf-8")
    SPEC_TXT = SPEC.read_text(encoding="utf-8")
    (PACK / "ftmo-candidate-17-pass-path.md").write_text(SPEC_TXT, encoding="utf-8")

    # STATUS
    status = f"""# BTC FTMO research baseline (2026-10-07)

**Status: C17 PASS-PATH SEARCH COMPLETE — mandate 1–3 months (≤90d)** — Measured dual-book / C15@90d / H4-BREAK-6 hard-DD package. Best label: **{best['path']}** (`{best_tag}`). Live C4 untouched.

## THE PASS PATH
{lines[lines.index('## THE PASS PATH')+2]}

## Workstream snapshot
| WS | Best tag | Path | HO $/mo | DD | ≤90d | Ext |
|---|---|---|---:|---:|---:|---:|
| A dual | see results | — | — | — | — | — |
| B C15 | `B_c15_0.75` / `B_c15_1.00` | {results['B_c15_0.75']['path']} / {results['B_c15_1.00']['path']} | ${results['B_c15_0.75']['ho_pace']:,.0f} / ${results['B_c15_1.00']['ho_pace']:,.0f} | {results['B_c15_0.75']['dd']*100:.1f}% / {results['B_c15_1.00']['dd']*100:.1f}% | {results['B_c15_0.75']['n90']}/{results['B_c15_0.75']['w90']} | ${results['B_c15_0.75']['ext_net']:,.0f} |
| C H4B6 | best among C_* | — | — | — | — | — |

Full table: `candidate-17-results.md`. Pack: `2026-10-07-candidate-17/`.

## Residual (if no ACCEPT)
Need ~${need_mo:,.0f}/mo for +$15k/90d. Best legal BTC `{bl_tag}` @ ${bl['ho_pace']:,.0f}/mo → **second instrument must add ≥${gap:,.0f}/mo** within shared 10% DD (BTC DD {bl['dd']*100:.1f}%, budget left {residual['shared_dd_budget_left']*100:.1f}%).

## Live
Catalogue drip / C4 ops: **untouched**. Nothing from C17 arms without separate Odin approval.
"""
    # Fill A/C rows properly
    a_best = min(
        ((t, s) for t, s in results.items() if t.startswith("A_")),
        key=lambda kv: (rank.get(kv[1]["path"], 9), -kv[1]["n90"], -kv[1]["ho_pace"]),
    )
    c_best = min(
        ((t, s) for t, s in results.items() if t.startswith("C_")),
        key=lambda kv: (rank.get(kv[1]["path"], 9), -kv[1]["n90"], -kv[1]["ho_pace"]),
    )
    status = f"""# BTC FTMO research baseline (2026-10-07)

**Status: C17 PASS-PATH SEARCH COMPLETE — mandate 1–3 months (≤90d)** — Dual-book / C15@90d / H4-BREAK-6 hard-DD measured. Best: **{best['path']}** (`{best_tag}`). Live C4 untouched.

## THE PASS PATH
{lines[lines.index('## THE PASS PATH')+2]}

## Workstream snapshot
| WS | Best tag | Path | HO $/mo | DD | ≤90d | Ext |
|---|---|---|---:|---:|---:|---:|
| A dual | `{a_best[0]}` | {a_best[1]['path']} | ${a_best[1]['ho_pace']:,.0f} | {a_best[1]['dd']*100:.1f}% | {a_best[1]['n90']}/{a_best[1]['w90']} | ${a_best[1]['ext_net']:,.0f} |
| B C15 | `B_c15_1.00` | {results['B_c15_1.00']['path']} | ${results['B_c15_1.00']['ho_pace']:,.0f} | {results['B_c15_1.00']['dd']*100:.1f}% | {results['B_c15_1.00']['n90']}/{results['B_c15_1.00']['w90']} | ${results['B_c15_1.00']['ext_net']:,.0f} |
| C H4B6 | `{c_best[0]}` | {c_best[1]['path']} | ${c_best[1]['ho_pace']:,.0f} | {c_best[1]['dd']*100:.1f}% | {c_best[1]['n90']}/{c_best[1]['w90']} | ${c_best[1]['ext_net']:,.0f} |

Full table: `candidate-17-results.md`. Pack: `2026-10-07-candidate-17/`.

## Residual (quantified way if BTC-alone short)
Need ~${need_mo:,.0f}/mo for +$15k/90d. Best legal BTC `{bl_tag}` @ ${bl['ho_pace']:,.0f}/mo → **second instrument must add ≥${gap:,.0f}/mo** within shared 10% DD (BTC DD {bl['dd']*100:.1f}%, budget left {residual['shared_dd_budget_left']*100:.1f}%).

## Live
Catalogue drip / C4 ops: **untouched**. Nothing from C17 arms without separate Odin approval.
"""
    ROOT_STATUS.write_text(status, encoding="utf-8")
    (PACK / "STATUS.md").write_text(status, encoding="utf-8")

    pr = f"""## Candidate 17 — Pass Path Package (≤90d Challenge+Verification)

Research-only. Live C4 / drip / MetaAPI / VM **untouched**.

### THE PASS PATH
{lines[lines.index('## THE PASS PATH')+2]}

### Workstreams
| WS | Best | Path | HO $/mo | DD | ≤90d | Ext |
|---|---|---|---:|---:|---:|---:|
| A dual C5+C15 | `{a_best[0]}` | {a_best[1]['path']} | ${a_best[1]['ho_pace']:,.0f} | {a_best[1]['dd']*100:.1f}% | {a_best[1]['n90']}/{a_best[1]['w90']} | ${a_best[1]['ext_net']:,.0f} |
| B C15@90d | `B_c15_1.00` | {results['B_c15_1.00']['path']} | ${results['B_c15_1.00']['ho_pace']:,.0f} | {results['B_c15_1.00']['dd']*100:.1f}% | {results['B_c15_1.00']['n90']}/{results['B_c15_1.00']['w90']} | ${results['B_c15_1.00']['ext_net']:,.0f} |
| C H4-BREAK-6 hard | `{c_best[0]}` | {c_best[1]['path']} | ${c_best[1]['ho_pace']:,.0f} | {c_best[1]['dd']*100:.1f}% | {c_best[1]['n90']}/{c_best[1]['w90']} | ${c_best[1]['ext_net']:,.0f} |

### Residual
Need ${need_mo:,.0f}/mo for +$15k/90d. Best legal BTC `{bl_tag}` @ ${bl['ho_pace']:,.0f}/mo → second instrument ≥**${gap:,.0f}/mo** (DD budget left {residual['shared_dd_budget_left']*100:.1f}%).

### Files
- `research/btc/2026-10-07-candidate-17/`
- `run_candidate_17.py`, `ftmo-candidate-17-pass-path.md`, `candidate-17-results.md`, `STATUS.md`
"""
    PR_BODY.write_text(pr, encoding="utf-8")
    (PACK / "GITHUB-PR-BODY-C17.md").write_text(pr, encoding="utf-8")

    SUMMARY_TXT.write_text(
        f"BEST={best_tag}\nPATH={best['path']}\nHO_PACE={best['ho_pace']:.2f}\n"
        f"DD={best['dd']:.4f}\nN90={best['n90']}/{best['w90']}\n"
        f"N90_HO={best['n90_ho']}/{best['w90_ho']}\nEXT={best['ext_net']:.2f}\n"
        f"GAP_MO={gap:.2f}\nBL={bl_tag}\n",
        encoding="utf-8",
    )
    # Copy runner into pack
    import shutil

    shutil.copy2(__file__, PACK / "run_candidate_17.py")

    print("\n=== BEST ===")
    print(f"{best_tag} → {best['path']}")
    print(f"HO pace ${best['ho_pace']:.0f}/mo DD {best['dd']*100:.1f}%")
    print(f"90d {best['n90']}/{best['w90']} HO90 {best['n90_ho']}/{best['w90_ho']}")
    print(f"Ext ${best['ext_net']:.0f}")
    print(f"Residual gap ${gap:.0f}/mo from second instrument")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
