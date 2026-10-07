#!/usr/bin/env python3
"""Candidate 29: Locked residual joint — C15 BTC H4 BB squeeze + C21B XAG Donchian soft.

Locked a-priori (not a fishing grid):
  29A — BTC-only @ 0.40% / 0.20% / 0.10% soft
  29B — XAG-only @ 1.25% / 0.625% / 0.375% soft
  29C — joint shared equity (one DD peak); BTC 0.40 soft + XAG 1.25 soft

Research only. No live / C4 / drip / FREEZE / MetaAPI. Do not package Gold.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

BTC_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_EXT = Path(
    "/workspace/btc-strategies/dukas-ext/btcusd-m1-bid-2026-09-01-2026-10-07T11-34.csv"
)
XAG_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv"
)
XAG_SHA = "6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-29"
SPEC = OUT_DIR / "ftmo-candidate-29.md"
RESULTS = OUT_DIR / "candidate-29-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-29-summary.txt"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C29.md"
RUNNER = OUT_DIR / "run_candidate_29.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
DAILY_KILL = -0.03
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

GOV_SOFT = 0.05
GOV_HARD = 0.08

# BTC C15 chassis
BTC_SPREAD = 15.0
BTC_MAX_LOT = 50.0
ATR_MULT_BTC = 1.0
R_MULT_BTC = 2.0
BB_PERIOD = 20
BB_K = 2.0
BW_LOOKBACK = 100
BW_PCT = 10.0
BTC_FULL = 0.0040
BTC_MID = 0.0020
BTC_FLOOR = 0.0010

# XAG C21B chassis
XAG_CONTRACT = 5000.0
XAG_SPREAD = 0.025
XAG_COMM = 3.0
XAG_MAX_LOT = 100.0
DONCH_N = 20
ATR_MULT_XAG = 2.0
R_MULT_XAG = 1.0
MAX_HOLD_DAYS = 10
XAG_FULL = 0.0125
XAG_MID = 0.00625
XAG_FLOOR = 0.00375

HO_START = pd.Timestamp("2025-11-08 00:00:00+00:00")
HO_END = pd.Timestamp("2026-09-01 23:59:59+00:00")
EXT_START = pd.Timestamp("2026-09-02 00:00:00+00:00")
FIT_START = pd.Timestamp("2024-01-01 00:00:00+00:00")
FIT_END = pd.Timestamp("2025-11-07 23:59:59+00:00")


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
    book: str
    risk_used: float
    gov_state: str
    symbol: str


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prague_day(ts: pd.Timestamp) -> date:
    return ts.tz_convert(PRAGUE).date()


def prague_month(ts: pd.Timestamp) -> str:
    d = ts.tz_convert(PRAGUE).date()
    return f"{d.year:04d}-{d.month:02d}"


def load_btc_m1() -> pd.DataFrame:
    frames = []
    for path in (BTC_MAIN, BTC_EXT):
        if not path.exists():
            raise SystemExit(f"BTC data MISSING: {path}")
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
    return m1[~(flat & unchanged)]


def load_xag_m1() -> pd.DataFrame:
    if not XAG_MAIN.exists():
        raise SystemExit(f"XAG data MISSING: {XAG_MAIN}")
    got = sha256_of(XAG_MAIN)
    if got != XAG_SHA:
        raise SystemExit(f"XAG sha mismatch: got {got}")
    df = pd.read_csv(XAG_MAIN)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    m1 = df[["open", "high", "low", "close"]].astype(float)
    flat = (
        (m1["open"] == m1["high"])
        & (m1["high"] == m1["low"])
        & (m1["low"] == m1["close"])
    )
    unchanged = m1["close"].eq(m1["close"].shift(1))
    return m1[~(flat & unchanged)]


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
    bars = m1.resample("1D", label="left", closed="left", origin=ORIGIN).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return bars.dropna(subset=["open", "high", "low", "close"])


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


def bollinger_bw(close: np.ndarray, period: int = BB_PERIOD, k: float = BB_K):
    n = len(close)
    middle = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    bw = np.full(n, np.nan)
    csum = np.cumsum(close)
    csum2 = np.cumsum(close * close)
    for i in range(period - 1, n):
        prev = csum[i - period] if i >= period else 0.0
        prev2 = csum2[i - period] if i >= period else 0.0
        mean = (csum[i] - prev) / period
        mean_sq = (csum2[i] - prev2) / period
        var = mean_sq - mean * mean
        if var < 0:
            var = 0.0
        std = float(np.sqrt(var))
        mid = float(mean)
        up = mid + k * std
        lo = mid - k * std
        middle[i] = mid
        upper[i] = up
        lower[i] = lo
        if mid > 0:
            bw[i] = (up - lo) / mid
    return middle, upper, lower, bw


def squeeze_flags(bw: np.ndarray, lookback: int = BW_LOOKBACK, pct: float = BW_PCT):
    n = len(bw)
    flag = np.zeros(n, dtype=bool)
    p10 = np.full(n, np.nan)
    for t in range(lookback - 1, n):
        window = bw[t - lookback + 1 : t + 1]
        if not np.all(np.isfinite(window)):
            continue
        thr = float(np.percentile(window, pct))
        p10[t] = thr
        flag[t] = bool(bw[t] <= thr)
    return flag, p10


def soft_gov_risk(equity: float, peak: float, full: float, mid: float, floor: float):
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return floor, "floor"
    if dd >= GOV_SOFT:
        return mid, "mid"
    return full, "full"


def size_lots_btc(equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / stop_dist, 2)
    lots = min(lots, BTC_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_btc(side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    return raw * lots - BTC_SPREAD * lots


def size_lots_xag(equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / (stop_dist * XAG_CONTRACT), 2)
    lots = min(lots, XAG_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_xag(side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    units = lots * XAG_CONTRACT
    return raw * units - XAG_SPREAD * units - XAG_COMM * lots


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float) -> float:
    if symbol == "BTC":
        return size_lots_btc(equity, risk, stop_dist)
    return size_lots_xag(equity, risk, stop_dist)


def pnl_sym(symbol: str, side: str, entry: float, exit_px: float, lots: float) -> float:
    if symbol == "BTC":
        return pnl_btc(side, entry, exit_px, lots)
    return pnl_xag(side, entry, exit_px, lots)


def resolve_daily_bar(side: str, o, h, l, c, stop, target, day_num: int):
    if side == "long":
        if o <= stop:
            return float(o), "SL_OPEN", "open"
        if l <= stop and h >= target:
            return float(stop), "SL_BOTH", "close"
        if l <= stop:
            return float(stop), "SL", "close"
        if h >= target:
            return float(target), "TP", "close"
    else:
        if o >= stop:
            return float(o), "SL_OPEN", "open"
        if h >= stop and l <= target:
            return float(stop), "SL_BOTH", "close"
        if h >= stop:
            return float(stop), "SL", "close"
        if l <= target:
            return float(target), "TP", "close"
    if day_num == MAX_HOLD_DAYS:
        return float(c), "TIME", "close"
    return None


def extract_btc_squeeze_signals(m1: pd.DataFrame, h4: pd.DataFrame) -> list[dict]:
    """Exact C15 chassis: H4 BB squeeze breakout → M1 SL/TP R=2 (no sizing)."""
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14(high, low, close)
    _middle, upper, lower, bw = bollinger_bw(close)
    sq_flag, p10 = squeeze_flags(bw)

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)

    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    signals: list[dict] = []
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
        if entry_i >= n_m1:
            continue
        if entry_i <= in_trade_until:
            continue

        entry_ts = m1_index[entry_i]
        entry_px = float(m1_open[entry_i])
        stop_dist = ATR_MULT_BTC * float(atr[t])
        if stop_dist <= 0:
            continue
        target_dist = R_MULT_BTC * stop_dist

        if side == "long":
            stop = entry_px - stop_dist
            target = entry_px + target_dist
            if entry_px <= stop:
                continue
        else:
            stop = entry_px + stop_dist
            target = entry_px - target_dist
            if entry_px >= stop:
                continue

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

        if exit_i is None:
            in_trade_until = n_m1 - 1
            continue

        signals.append(
            {
                "symbol": "BTC",
                "side": side,
                "entry_ts": entry_ts,
                "entry": entry_px,
                "exit_ts": m1_index[exit_i],
                "exit": float(exit_px),
                "reason": reason,
                "stop_dist": stop_dist,
            }
        )
        in_trade_until = exit_i

    return signals


def extract_xag_donchian_signals(daily: pd.DataFrame) -> list[dict]:
    """Exact C21B Donchian 20d dual TP1R TIME10 (no sizing)."""
    opens = daily["open"].to_numpy(dtype=float)
    highs = daily["high"].to_numpy(dtype=float)
    lows = daily["low"].to_numpy(dtype=float)
    closes = daily["close"].to_numpy(dtype=float)
    index = daily.index
    atr = atr14(highs, lows, closes)
    n = len(daily)
    signals: list[dict] = []
    pending = None
    pos = None

    for i in range(n):
        if pending is not None and pos is None:
            entry = float(opens[i])
            entry_ts = pd.Timestamp(index[i])
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.tz_localize("UTC")
            sl_dist = ATR_MULT_XAG * float(pending["atr"])
            if sl_dist > 0:
                side = pending["side"]
                if side == "long":
                    stop = entry - sl_dist
                    target = entry + R_MULT_XAG * sl_dist
                else:
                    stop = entry + sl_dist
                    target = entry - R_MULT_XAG * sl_dist
                pos = {
                    "side": side,
                    "entry": entry,
                    "entry_ts": entry_ts,
                    "entry_i": i,
                    "stop": stop,
                    "target": target,
                    "sl_dist": sl_dist,
                }
            pending = None

        if pos is not None:
            day_num = i - pos["entry_i"] + 1
            hit = resolve_daily_bar(
                pos["side"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                pos["stop"],
                pos["target"],
                day_num,
            )
            if hit is not None:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                signals.append(
                    {
                        "symbol": "XAG",
                        "side": pos["side"],
                        "entry_ts": pos["entry_ts"],
                        "entry": pos["entry"],
                        "exit_ts": exit_ts,
                        "exit": float(fill),
                        "reason": reason,
                        "stop_dist": pos["sl_dist"],
                    }
                )
                pos = None

        if pos is None and pending is None and i >= DONCH_N:
            if np.isfinite(atr[i]) and atr[i] > 0:
                hh = float(highs[i - DONCH_N : i].max())
                ll = float(lows[i - DONCH_N : i].min())
                c = float(closes[i])
                if c > hh:
                    pending = {"side": "long", "atr": float(atr[i])}
                elif c < ll:
                    pending = {"side": "short", "atr": float(atr[i])}

    return signals


def risk_tiers_for(symbol: str):
    if symbol == "BTC":
        return BTC_FULL, BTC_MID, BTC_FLOOR
    return XAG_FULL, XAG_MID, XAG_FLOOR


def replay_signals(
    signals: list[dict],
    book: str,
    use_gov: bool,
    allow_simultaneous: bool = False,
):
    """Replay precomputed signals with soft gov + Prague kill.

    If allow_simultaneous: one busy_until per symbol (joint 29C).
    Else: global one-at-a-time (single-sleeve books; signals already non-overlap).
    """
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel: dict[str, int] = defaultdict(int)
    busy_until: dict[str, pd.Timestamp | None] = {"BTC": None, "XAG": None}

    ordered = sorted(signals, key=lambda s: s["entry_ts"])

    for sig in ordered:
        sym = sig["symbol"]
        if allow_simultaneous:
            bu = busy_until[sym]
            if bu is not None and sig["entry_ts"] < bu:
                funnel["skip_overlap"] += 1
                continue
        else:
            # single sleeve: signals already non-overlapping; no skip needed
            pass

        pd_entry = prague_day(sig["entry_ts"])
        if pd_entry in killed_days:
            funnel["skip_kill"] += 1
            continue
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            funnel["skip_kill"] += 1
            continue

        full, mid, floor = risk_tiers_for(sym)
        if use_gov:
            risk, gstate = soft_gov_risk(equity, peak, full, mid, floor)
            funnel[f"gov_{gstate}"] += 1
        else:
            risk, gstate = full, "n/a"

        lots = size_lots(sym, equity, risk, sig["stop_dist"])
        if lots < MIN_LOT:
            funnel["skip_lots"] += 1
            continue

        pnl = pnl_sym(sym, sig["side"], sig["entry"], sig["exit"], lots)
        equity += pnl
        if equity > peak:
            peak = equity
        pd_exit = prague_day(sig["exit_ts"])
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
        day_pnl[pd_exit] += pnl
        if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
            killed_days.add(pd_exit)

        trades.append(
            Trade(
                side=sig["side"],
                entry_ts=sig["entry_ts"],
                entry=sig["entry"],
                exit_ts=sig["exit_ts"],
                exit=sig["exit"],
                reason=sig["reason"],
                lots=lots,
                stop_dist=sig["stop_dist"],
                pnl=pnl,
                equity_after=equity,
                book=book,
                risk_used=risk,
                gov_state=gstate,
                symbol=sym,
            )
        )
        busy_until[sym] = sig["exit_ts"]
        funnel["taken"] += 1
        funnel[f"taken_{sym}"] += 1

    chassis = {
        "29A": "btc-h4-bb-squeeze-0.40" + ("+softgov" if use_gov else ""),
        "29B": "xag-donchian-20d-1.25" + ("+softgov" if use_gov else ""),
        "29C": "btc0.40+xag1.25-joint" + ("+softgov" if use_gov else ""),
    }.get(book, book)

    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis,
        "taken": len(trades),
        "use_gov": use_gov,
        "symbol": "JOINT" if book == "29C" else ("BTC" if book == "29A" else "XAG"),
        "n_signals_in": len(signals),
        "btc_full": BTC_FULL,
        "xag_full": XAG_FULL,
        "max_dd_path": (1.0 - (min((tr.equity_after for tr in trades), default=START_EQUITY) / peak))
        if trades
        else 0.0,
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


def worst_day_pct(day_pnl, day_start_eq):
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


def slice_pnl(trades, start, end=None):
    total = 0.0
    for tr in trades:
        if tr.exit_ts < start:
            continue
        if end is not None and tr.exit_ts > end:
            continue
        total += tr.pnl
    return total


def leave_out_two_best_ho(trades):
    months: dict[str, float] = defaultdict(float)
    for tr in trades:
        if tr.exit_ts < HO_START or tr.exit_ts > HO_END:
            continue
        months[prague_month(tr.exit_ts)] += tr.pnl
    if not months:
        return [], 0.0
    ranked = sorted(months.items(), key=lambda kv: kv[1], reverse=True)
    drop = [m for m, _ in ranked[:2]]
    leave = sum(v for m, v in months.items() if m not in drop)
    return drop, leave


def count_pass_windows(trades, day_pnl, day_start_eq, window_days: int):
    if not trades:
        return 0, 0, []
    exits = [(tr.exit_ts, tr.equity_after) for tr in trades]
    all_days = sorted(set(day_start_eq.keys()) | {prague_day(t) for t, _ in exits})
    if not all_days:
        return 0, 0, []
    first_day, last_day = all_days[0], all_days[-1]
    end_limit = last_day - timedelta(days=window_days - 1)
    if end_limit < first_day:
        return 0, 0, []
    passes = []
    n_windows = 0
    exit_pdays = [prague_day(ts) for ts, _ in exits]
    exit_eqs = [eq for _, eq in exits]
    cur = first_day
    while cur <= end_limit:
        ws, we = cur, cur + timedelta(days=window_days - 1)
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
        max_eq, min_eq = max(window_eqs), min(window_eqs)
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
        if hit_10 and hit_15 and floor_ok and not day_fail:
            passes.append(
                {
                    "start": ws.isoformat(),
                    "end": we.isoformat(),
                    "start_eq": start_eq,
                    "max_mult": max_eq / start_eq,
                    "min_mult": min_eq / start_eq,
                    "worst_day": worst_day_in,
                }
            )
        cur += timedelta(days=1)
    return len(passes), n_windows, passes[:15]


def count_sequential_reset(trades: list[Trade], use_gov: bool, window_days: int = 90):
    """Re-size each template trade with soft gov; Challenge then Verification reset."""
    if not trades:
        return 0, 0, []
    first = prague_day(trades[0].entry_ts)
    last = prague_day(trades[-1].exit_ts)
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

        def run_stage(start_eq, stage_start_day, need_mult, hard_end):
            eq = start_eq
            peak = start_eq
            day_pnl_l: dict[date, float] = defaultdict(float)
            day_start_l: dict[date, float] = {}
            killed: set[date] = set()
            done_day = None
            for tr in trades:
                pd_e = prague_day(tr.entry_ts)
                if pd_e < stage_start_day:
                    continue
                if pd_e > hard_end:
                    break
                if done_day is not None:
                    break
                if pd_e in killed:
                    continue
                if pd_e not in day_start_l:
                    day_start_l[pd_e] = eq
                if day_pnl_l[pd_e] / day_start_l[pd_e] <= DAILY_KILL:
                    killed.add(pd_e)
                    continue
                full, mid, floor = risk_tiers_for(tr.symbol)
                if use_gov:
                    risk, _ = soft_gov_risk(eq, peak, full, mid, floor)
                else:
                    risk = full
                lots = size_lots(tr.symbol, eq, risk, tr.stop_dist)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_sym(tr.symbol, tr.side, tr.entry, tr.exit, lots)
                eq += pnl
                if eq > peak:
                    peak = eq
                pd_x = prague_day(tr.exit_ts)
                if pd_x > hard_end:
                    return None, eq, True
                if pd_x not in day_start_l:
                    day_start_l[pd_x] = eq - pnl
                day_pnl_l[pd_x] += pnl
                if day_pnl_l[pd_x] / day_start_l[pd_x] <= DAY_FAIL:
                    return None, eq, True
                if day_pnl_l[pd_x] / day_start_l[pd_x] <= DAILY_KILL:
                    killed.add(pd_x)
                if eq < start_eq * FLOOR_MULT:
                    return None, eq, True
                if eq >= start_eq * need_mult:
                    done_day = pd_x
                    break
            return done_day, eq, False

        chall_done, _, breached = run_stage(START_EQUITY, ws, CHALLENGE_MULT, we)
        if breached or chall_done is None:
            cur += timedelta(days=1)
            continue
        ver_start = chall_done + timedelta(days=1)
        if ver_start > we:
            cur += timedelta(days=1)
            continue
        ver_done, _, breached2 = run_stage(START_EQUITY, ver_start, 1.05, we)
        if breached2 or ver_done is None:
            cur += timedelta(days=1)
            continue
        total_days = (ver_done - ws).days + 1
        if total_days <= window_days:
            passes.append(
                {
                    "start": ws.isoformat(),
                    "challenge_done": chall_done.isoformat(),
                    "verification_done": ver_done.isoformat(),
                    "total_days": total_days,
                }
            )
        cur += timedelta(days=1)
    return len(passes), n_win, passes[:15]


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end, ext_available_flag):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    if ext_available_flag:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext)"

    leave_drop, leave_net = leave_out_two_best_ho(trades)
    max_dd = max_realized_dd(trades)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail = days_at_or_below(day_pnl, day_start_eq, DAY_FAIL)

    ho_days = (HO_END.normalize() - HO_START).days + 1
    ho_mo = ho_days / 30.44
    ho_pace = ho_net / ho_mo if ho_mo > 0 else 0.0

    n60, w60, _ = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)
    nseq, wseq, pseq = count_sequential_reset(trades, use_gov, 90)

    wins = sum(1 for tr in trades if tr.pnl > 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")
    reasons: dict[str, int] = defaultdict(int)
    gov_counts: dict[str, int] = defaultdict(int)
    by_sym: dict[str, int] = defaultdict(int)
    for tr in trades:
        reasons[tr.reason] += 1
        gov_counts[tr.gov_state] += 1
        by_sym[tr.symbol] += 1

    ho_cut = date(2025, 11, 8)
    n90_ho = sum(1 for p in p90 if date.fromisoformat(p["start"]) >= ho_cut)
    nseq_ho = sum(1 for p in pseq if date.fromisoformat(p["start"]) >= ho_cut)
    has_90 = n90 >= 1 or nseq >= 1
    has_90_ho = n90_ho >= 1 or nseq_ho >= 1

    legal = max_dd <= 0.10 + 1e-12 and n_fail == 0 and worst_pct > DAY_FAIL
    leave_ok = leave_net > 0
    ext_ok = (not ext_available_flag) or (ext_net >= 0)
    ho_ok = ho_net > 0

    if not legal or not has_90:
        decision = "REJECT"
    elif legal and has_90_ho and ho_ok and leave_ok and ext_ok:
        if ext_available_flag and ext_net >= 0:
            decision = "ACCEPT"
        elif not ext_available_flag:
            decision = "CONDITIONAL"
        else:
            decision = "CONDITIONAL"
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available_flag and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    # representative full risk for display
    if book == "29A":
        full, mid, floor = BTC_FULL, BTC_MID, BTC_FLOOR
    elif book == "29B":
        full, mid, floor = XAG_FULL, XAG_MID, XAG_FLOOR
    else:
        full, mid, floor = BTC_FULL + XAG_FULL, BTC_MID + XAG_MID, BTC_FLOOR + XAG_FLOOR

    return {
        "label": label,
        "book": book,
        "symbol": meta.get("symbol", book),
        "use_gov": use_gov,
        "full_risk": full,
        "mid_risk": mid,
        "floor_risk": floor,
        "n_trades": len(trades),
        "wins": wins,
        "wr": wins / len(trades) if trades else 0.0,
        "longs": longs,
        "shorts": shorts,
        "reasons": dict(reasons),
        "gov_counts": dict(gov_counts),
        "by_sym": dict(by_sym),
        "ho_net": ho_net,
        "ho_pace": ho_pace,
        "fit_net": fit_net,
        "leave_drop": leave_drop,
        "leave_net": leave_net,
        "leave_ok": leave_ok,
        "ext_net": ext_net,
        "ext_status": ext_status,
        "ext_available": ext_available_flag,
        "max_dd": max_dd,
        "worst_day": worst_d.isoformat() if worst_d else None,
        "worst_pct": worst_pct,
        "n_fail_days": n_fail,
        "legal": legal,
        "n60": n60,
        "w60": w60,
        "n90": n90,
        "w90": w90,
        "p90": p90,
        "n90_ho": n90_ho,
        "nseq": nseq,
        "wseq": wseq,
        "pseq": pseq,
        "nseq_ho": nseq_ho,
        "has_90": has_90,
        "has_90_ho": has_90_ho,
        "decision": decision,
        "final_equity": trades[-1].equity_after if trades else START_EQUITY,
        "peak_equity": meta.get("peak_equity", START_EQUITY),
        "meta": meta,
    }


def write_docs(summaries, measured, btc_end, xag_end, btc_sha, xag_sha):
    PACK.mkdir(parents=True, exist_ok=True)

    # Primary = 29C verdict book
    joint = next((s for s in summaries if s["book"] == "29C"), summaries[-1])
    primary = joint
    clears_residual = (
        joint["decision"] == "ACCEPT"
        or (
            joint["legal"]
            and joint["has_90_ho"]
            and joint["ho_ok"] if "ho_ok" in joint else joint["ho_net"] > 0
            and joint["leave_ok"]
            and joint["ext_ok"] if "ext_ok" in joint else (
                (not joint["ext_available"]) or joint["ext_net"] >= 0
            )
        )
    )
    # simpler residual clear: ACCEPT, or CONDITIONAL with legal+HO windows+positive pace covering C17 gap
    residual_cleared = joint["decision"] == "ACCEPT"
    residual_partial = (
        joint["legal"]
        and joint["has_90_ho"]
        and joint["ho_net"] > 0
        and joint["decision"] in ("ACCEPT", "CONDITIONAL")
    )

    if joint["decision"] == "ACCEPT":
        lead = (
            f"**YES — joint C15 BTC + C21B XAG soft clears a deployable ~3mo path** via 29C: "
            f"max DD {joint['max_dd']*100:.1f}%, ≤90d {joint['n90']}/{joint['w90']} "
            f"(HO-era {joint['n90_ho']}), seq {joint['nseq']}/{joint['wseq']} "
            f"(HO-era {joint['nseq_ho']}), HO ~${joint['ho_pace']:,.0f}/mo. "
            f"Clears C17 residual thesis."
        )
    elif residual_partial:
        lead = (
            f"**CONDITIONAL — joint legal DD + HO-era windows, not ACCEPT** via 29C: "
            f"max DD {joint['max_dd']*100:.1f}%, ≤90d {joint['n90']}/{joint['w90']} "
            f"(HO-era {joint['n90_ho']}), seq HO-era {joint['nseq_ho']}, "
            f"HO ~${joint['ho_pace']:,.0f}/mo, leave-out ${joint['leave_net']:+,.0f}, "
            f"Ext {joint['ext_net']:+,.0f} ({joint['ext_status']}). "
            f"Does NOT fully clear C17 residual to ACCEPT."
        )
    else:
        lead = (
            "**NO — joint C15 BTC + C21B XAG soft does not clear C17 residual / deployable ~3mo path.** "
            f"29C: DD {joint['max_dd']*100:.1f}% legal={joint['legal']}, "
            f"HO ~${joint['ho_pace']:,.0f}/mo, ≤90d HO-era {joint['n90_ho']}, "
            f"leave-out ${joint['leave_net']:+,.0f}."
        )

    lines = []
    lines.append("# Candidate 29 Results — C15 BTC + C21B XAG soft joint residual stack")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**Measured:** {measured}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**BTC data:** `{BTC_MAIN}` + dukas-ext sha256 main `{btc_sha}` end `{btc_end}`")
    lines.append(f"**XAG data:** `{XAG_MAIN}` sha256 `{xag_sha}` end `{xag_end}`")
    lines.append("")
    lines.append("## C17 residual check")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| C17 BTC@0.75% solo pace | ~$1,291/mo DD 7.4% |")
    lines.append("| C17 residual gap | ≥~$3,709/mo in ~2.6% DD headroom |")
    lines.append(f"| 29C joint HO pace | ${joint['ho_pace']:,.0f}/mo |")
    lines.append(f"| 29C max DD (shared) | {joint['max_dd']*100:.2f}% |")
    lines.append(f"| 29C ≤90d HO-era | {joint['n90_ho']} cont / {joint['nseq_ho']} seq |")
    lines.append(f"| Clears C17 residual to ACCEPT? | {'YES' if residual_cleared else 'NO'} |")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step |")
    lines.append("| Challenge / Verification | +10% / +5% |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |")
    lines.append("| BTC risk shares | **0.40% / 0.20% / 0.10%** |")
    lines.append("| XAG risk shares | **1.25% / 0.625% / 0.375%** |")
    lines.append("| BTC costs | spread **15**, commission **0**, contract **1** |")
    lines.append("| XAG costs | contract **5000**, spread **0.025**, commission **$3/lot** (**ASSUMPTION**) |")
    lines.append("| Shared equity | one book, one peak DD |")
    lines.append("| Max positions | one per sleeve (two simultaneous OK) |")
    lines.append("| Gold packaging | Forbidden |")
    lines.append("")

    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |"
    )
    lines.append("|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---|---|")
    for s in summaries:
        gov = "SOFT" if s["use_gov"] else "OFF"
        if s["book"] == "29C":
            rc = "BTC 0.40/0.20/0.10 + XAG 1.25/0.625/0.375"
        else:
            rc = f"{s['full_risk']*100:.2f}/{s['mid_risk']*100:.2f}/{s['floor_risk']*100:.2f}%"
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        lines.append(
            f"| {s['book']} {s['label']} | {s['symbol']} | {gov} | {rc} | {s['ho_pace']:,.0f} | "
            f"{s['leave_net']:+,.0f} | {ext_cell} | "
            f"{s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    lines.append("")

    for s in summaries:
        lines.append(f"## {s['book']} — {s['label']} (gov={'SOFT' if s['use_gov'] else 'OFF'})")
        lines.append("")
        lines.append(f"**Decision: {s['decision']}**")
        lines.append("")
        lines.append(f"- Chassis: `{s['meta'].get('chassis', s['book'])}`")
        lines.append(
            f"- Trades: n={s['n_trades']} L/S={s['longs']}/{s['shorts']} WR={s['wr']*100:.1f}% "
            f"reasons={s['reasons']} gov={s['gov_counts']} by_sym={s['by_sym']}"
        )
        lines.append(
            f"- HO ${s['ho_net']:,.2f} (~${s['ho_pace']:,.2f}/mo); Fit ${s['fit_net']:,.2f}; "
            f"Leave-out ${s['leave_net']:,.2f} (drop {s['leave_drop']}); Ext {s['ext_status']} "
            + ("" if not s["ext_available"] else f"${s['ext_net']:,.2f}")
        )
        lines.append(
            f"- Max DD {s['max_dd']*100:.2f}%; peak eq ${s['peak_equity']:,.2f}; "
            f"worst Prague day {s['worst_day']} {s['worst_pct']*100:.2f}%; "
            f"fail-days={s['n_fail_days']}; Legal={'YES' if s['legal'] else 'NO'}"
        )
        lines.append(
            f"- Windows: ≤60d {s['n60']}/{s['w60']}; ≤90d cont {s['n90']}/{s['w90']} "
            f"(HO-era starts {s['n90_ho']}); seq90 reset {s['nseq']}/{s['wseq']} "
            f"(HO-era {s['nseq_ho']})"
        )
        lines.append(f"- Final equity ${s['final_equity']:,.2f}")
        if s["p90"]:
            lines.append("")
            lines.append("### ≤90d continuous pass sample")
            lines.append("| Start | End | Era | Start eq | Max mult | Min mult | Worst day |")
            lines.append("|---|---|---|---:|---:|---:|---:|")
            for p in s["p90"][:12]:
                era = "HO+" if date.fromisoformat(p["start"]) >= date(2025, 11, 8) else "Fit"
                lines.append(
                    f"| {p['start']} | {p['end']} | {era} | ${p['start_eq']:,.0f} | "
                    f"{p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']*100:.2f}% |"
                )
        if s["pseq"]:
            lines.append("")
            lines.append("### seq90 reset pass sample")
            lines.append("| Start | Era | Challenge done | Verification done | Total days |")
            lines.append("|---|---|---|---|---:|")
            for p in s["pseq"][:12]:
                era = "HO+" if date.fromisoformat(p["start"]) >= date(2025, 11, 8) else "Fit"
                lines.append(
                    f"| {p['start']} | {era} | {p['challenge_done']} | {p['verification_done']} | {p['total_days']} |"
                )
        lines.append("")
        lines.append(f"Meta: `{json.dumps(s['meta'], default=str)}`")
        lines.append("")

    lines.append("## Live")
    lines.append("")
    lines.append("Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.")
    lines.append("Gold not packaged. Do not deploy.")
    lines.append("")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-29-results.md").write_text(RESULTS.read_text())
    if SPEC.exists():
        (PACK / "ftmo-candidate-29.md").write_text(SPEC.read_text())

    SUMMARY_TXT.write_text(
        f"{lead}\n"
        + "\n".join(
            f"{s['book']}|{s['symbol']}|gov={s['use_gov']}|{s['decision']}|pace=${s['ho_pace']:.0f}/mo|"
            f"DD={s['max_dd']*100:.1f}%|90d={s['n90']}/{s['w90']}(HO={s['n90_ho']})|"
            f"seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']})|legal={s['legal']}|"
            f"leave={s['leave_net']:.0f}|ext={s['ext_net'] if s['ext_available'] else 'N/A'}"
            for s in summaries
        )
        + "\n"
    )
    (PACK / "candidate-29-summary.txt").write_text(SUMMARY_TXT.read_text())

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C29 BTC+XAG residual joint — {primary['decision']}** — {lead}")
    status.append("")
    status.append("## Candidate 29")
    status.append("")
    status.append(
        "| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |"
    )
    status.append("|---|---|---|---:|---:|---:|---:|---|---:|---|---|")
    for s in summaries:
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        status.append(
            f"| {s['book']} | {s['symbol']} | {'SOFT' if s['use_gov'] else 'OFF'} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{ext_cell} | {s['leave_net']:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    status.append("## Live")
    status.append(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C29 arms without Odin approval. Gold not packaged."
    )
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pr.append("## Candidate 29 — Locked residual stack: C15 BTC + C21B XAG soft joint")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append(
        "Locked a-priori: C15 H4 BB squeeze @0.40→0.20→0.10 + C21B XAG Donchian @1.25→0.625→0.375; "
        "shared equity soft gov; one pos/sleeve; Prague −3% kill both."
    )
    pr.append("Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.")
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Leave-out | Ext | Legal | Decision |")
    pr.append("|---|---|---|---:|---:|---:|---:|---:|---|---|---|")
    for s in summaries:
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        pr.append(
            f"| {s['book']} {s['label']} | {s['symbol']} | {'SOFT' if s['use_gov'] else 'OFF'} | "
            f"{s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {s['leave_net']:+,.0f} | {ext_cell} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pr.append("")
    pr.append("### ASSUMPTIONS")
    pr.append("- BTC: spread 15, commission 0, contract 1")
    pr.append("- XAG: contract 5000, spread 0.025, commission $3/lot (ASSUMPTION)")
    pr.append("- Soft gov: &lt;5% full / 5–8% mid / ≥8% floor; never sticky-block")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-29/`")
    pr.append("- `run_candidate_29.py`, `ftmo-candidate-29.md`, `candidate-29-results.md`, `STATUS.md`")
    pr.append("")
    pr.append("### Live")
    pr.append("Research only — do not deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C29.md").write_text(PR_BODY.read_text())

    shutil.copy2(RUNNER, PACK / "run_candidate_29.py")

    dump = []
    for s in summaries:
        row = {k: v for k, v in s.items() if k not in ("p60",)}
        dump.append(row)
    (PACK / "candidate-29-results.json").write_text(json.dumps(dump, indent=2, default=str))
    (OUT_DIR / "candidate-29-results.json").write_text(json.dumps(dump, indent=2, default=str))

    return lead, primary, residual_cleared


def main():
    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("Loading BTC M1 (main+ext)...")
    btc = load_btc_m1()
    btc_end = btc.index[-1]
    btc_sha = sha256_of(BTC_MAIN)
    print(f"  BTC M1: {len(btc)} → {btc_end}")
    btc_h4 = build_h4(btc)
    print(f"  BTC H4: {len(btc_h4)}")

    print("Loading XAG M1...")
    xag = load_xag_m1()
    xag_end = xag.index[-1]
    print(f"  XAG M1: {len(xag)} → {xag_end}")
    xag_daily = build_daily(xag)
    print(f"  XAG D1: {len(xag_daily)}")

    print("Extracting BTC C15 squeeze signals...")
    btc_sigs = extract_btc_squeeze_signals(btc, btc_h4)
    print(f"  BTC signals: {len(btc_sigs)}")

    print("Extracting XAG C21B Donchian signals...")
    xag_sigs = extract_xag_donchian_signals(xag_daily)
    print(f"  XAG signals: {len(xag_sigs)}")

    summaries = []

    # 29A BTC-only soft
    print("Running 29A BTC-only soft 0.40→0.20→0.10...")
    trades, day_pnl, day_start, meta = replay_signals(
        btc_sigs, "29A", use_gov=True, allow_simultaneous=False
    )
    print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
    s = summarize(
        "soft 0.40→0.20→0.10",
        "29A",
        trades,
        day_pnl,
        day_start,
        meta,
        True,
        btc_end,
        ext_available_flag=True,
    )
    print(
        f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
        f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
        f"legal={s['legal']}"
    )
    summaries.append(s)

    # 29B XAG-only soft
    print("Running 29B XAG-only soft 1.25→0.625→0.375...")
    trades, day_pnl, day_start, meta = replay_signals(
        xag_sigs, "29B", use_gov=True, allow_simultaneous=False
    )
    print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
    s = summarize(
        "soft 1.25→0.625→0.375",
        "29B",
        trades,
        day_pnl,
        day_start,
        meta,
        True,
        xag_end,
        ext_available_flag=False,
    )
    print(
        f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
        f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
        f"legal={s['legal']}"
    )
    summaries.append(s)

    # 29C joint soft
    print("Running 29C JOINT soft BTC0.40+XAG1.25...")
    trades, day_pnl, day_start, meta = replay_signals(
        btc_sigs + xag_sigs, "29C", use_gov=True, allow_simultaneous=True
    )
    print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
    # Joint Ext available via BTC dukas-ext (XAG silent in Ext)
    s = summarize(
        "soft joint BTC0.40+XAG1.25",
        "29C",
        trades,
        day_pnl,
        day_start,
        meta,
        True,
        btc_end,
        ext_available_flag=True,
    )
    print(
        f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
        f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
        f"legal={s['legal']}"
    )
    summaries.append(s)

    lead, primary, cleared = write_docs(
        summaries, measured, btc_end, xag_end, btc_sha, XAG_SHA
    )
    print("\n" + lead)
    print(f"Wrote {RESULTS}")
    print(f"Pack {PACK}")
    print(f"Clears C17 residual ACCEPT: {cleared}")


if __name__ == "__main__":
    main()
