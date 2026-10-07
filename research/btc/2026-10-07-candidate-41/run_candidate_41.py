#!/usr/bin/env python3
"""Candidate 41: Joint US100 NR7 @1% soft + BTC C15 H4 BB squeeze @0.75% soft (no XAG).

Locked a-priori (not a fishing grid):
  41A — US100 NR7 alone soft 1.00→0.50→0.25
  41B — BTC C15 alone soft 0.75→0.40→0.20
  41C — joint ungoverened (US100 1% + BTC 0.75% always)
  41D — joint + soft gov (verdict)

Research only. No live / C4 / drip / FREEZE / MetaAPI. Do not package Gold.
Do NOT include XAG (C35/C37/C39 stack family closed).
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

PRAGUE = ZoneInfo("Europe/Prague")
ET = ZoneInfo("America/New_York")

US100_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_EXT = Path(
    "/workspace/btc-strategies/dukas-ext/btcusd-m1-bid-2026-09-01-2026-10-07T11-34.csv"
)

US100_SHA = "5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af"
BTC_MAIN_SHA = "437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-41"
SPEC = OUT_DIR / "ftmo-candidate-41.md"
RESULTS = OUT_DIR / "candidate-41-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-41-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-41-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C41.md"
RUNNER = OUT_DIR / "run_candidate_41.py"

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

# US100 NR7
US100_SPREAD = 1.0
US100_CONTRACT = 1.0
US100_COMM = 0.0
US100_FULL = 0.01
US100_MID = 0.005
US100_FLOOR = 0.0025
US100_MAX_LOT = 1000.0
US100_TIME_DAY = 5
TP_MULT_US100 = 2.0

# BTC C15 H4 BB squeeze
BTC_SPREAD = 15.0
BTC_MAX_LOT = 50.0
ATR_MULT_BTC = 1.0
R_MULT_BTC = 2.0
BB_PERIOD = 20
BB_K = 2.0
BW_LOOKBACK = 100
BW_PCT = 10.0
BTC_FULL = 0.0075
BTC_MID = 0.0040
BTC_FLOOR = 0.0020

HO_START = pd.Timestamp("2025-11-08 00:00:00+00:00")
HO_END = pd.Timestamp("2026-09-01 23:59:59+00:00")
EXT_START = pd.Timestamp("2026-09-02 00:00:00+00:00")
FIT_START = pd.Timestamp("2024-01-01 00:00:00+00:00")
FIT_END = pd.Timestamp("2025-11-07 23:59:59+00:00")

COMPLETE = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)] + [
    f"2026-{m:02d}" for m in range(1, 9)
]
STREAK = {f"2025-{m:02d}" for m in range(8, 13)} | {"2026-01", "2026-02"}


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


def load_m1(path: Path, expected_sha: str | None = None) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"data MISSING: {path}")
    got = sha256_of(path)
    if expected_sha and got != expected_sha:
        raise SystemExit(f"sha mismatch {path.name}: got {got}")
    df = pd.read_csv(path)
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


def build_daily(m1: pd.DataFrame) -> pd.DataFrame:
    bars = m1.resample("1D", label="left", closed="left", origin=ORIGIN).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return bars.dropna(subset=["open", "high", "low", "close"])


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


def resolve_daily_bar(side: str, o, h, l, c, stop, target, day_num: int, time_day: int):
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
    if day_num == time_day:
        return float(c), "TIME", "close"
    return None


def risk_tiers_for(symbol: str):
    if symbol == "US100":
        return US100_FULL, US100_MID, US100_FLOOR
    return BTC_FULL, BTC_MID, BTC_FLOOR


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    if symbol == "US100":
        lots = round(equity * risk / (stop_dist * US100_CONTRACT), 2)
        lots = min(lots, US100_MAX_LOT)
    else:
        lots = round(equity * risk / stop_dist, 2)
        lots = min(lots, BTC_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_sym(symbol: str, side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    if symbol == "US100":
        units = lots * US100_CONTRACT
        return raw * units - US100_SPREAD * units - US100_COMM * lots
    return raw * lots - BTC_SPREAD * lots


def extract_us100_nr7(daily: pd.DataFrame) -> tuple[list[dict], dict]:
    """Exact Explorer US100 NR7 (no sizing). TIME day5, TP 2R."""
    opens, highs, lows, closes = [daily[c].to_numpy(float) for c in ("open", "high", "low", "close")]
    index = daily.index
    n = len(daily)
    ranges = highs - lows
    signals: list[dict] = []
    pending = None
    position = None
    funnel = defaultdict(int)

    for i in range(n):
        if pending is not None and i == pending["expire_i"]:
            if position is not None:
                funnel["ignored"] += 1
                pending = None
            else:
                nh, nl = pending["nr_high"], pending["nr_low"]
                long_ok = float(highs[i]) >= nh
                short_ok = float(lows[i]) <= nl
                if long_ok and short_ok:
                    funnel["both_skip"] += 1
                    pending = None
                elif not long_ok and not short_ok:
                    funnel["no_break"] += 1
                    pending = None
                else:
                    o = float(opens[i])
                    if long_ok:
                        fill = o if o >= nh else nh
                        stop = nl
                        side = "long"
                    else:
                        fill = o if o <= nl else nl
                        stop = nh
                        side = "short"
                    sl_dist = abs(fill - stop)
                    if (
                        not sl_dist > 0
                        or (side == "long" and fill <= stop)
                        or (side == "short" and fill >= stop)
                    ):
                        funnel["stop_through"] += 1
                        pending = None
                    else:
                        target = fill + TP_MULT_US100 * sl_dist if side == "long" else fill - TP_MULT_US100 * sl_dist
                        entry_ts = pd.Timestamp(index[i])
                        if entry_ts.tzinfo is None:
                            entry_ts = entry_ts.tz_localize("UTC")
                        position = {
                            "side": side,
                            "entry": float(fill),
                            "entry_ts": entry_ts,
                            "entry_i": i,
                            "stop": float(stop),
                            "target": float(target),
                            "sl_dist": float(sl_dist),
                        }
                        funnel["signals"] += 1
                        pending = None
        elif pending is not None and i > pending["expire_i"]:
            pending = None

        if position is not None:
            day_num = i - position["entry_i"] + 1
            if day_num > US100_TIME_DAY:
                raise RuntimeError("NR7 past day5")
            hit = resolve_daily_bar(
                position["side"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                position["stop"],
                position["target"],
                day_num,
                US100_TIME_DAY,
            )
            if hit:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                signals.append(
                    {
                        "symbol": "US100",
                        "side": position["side"],
                        "entry_ts": position["entry_ts"],
                        "entry": position["entry"],
                        "exit_ts": exit_ts,
                        "exit": float(fill),
                        "reason": reason,
                        "stop_dist": position["sl_dist"],
                    }
                )
                position = None

        if i >= 6 and ranges[i] > 0:
            prior = ranges[i - 6 : i]
            if float(ranges[i]) < float(prior.min()):
                funnel["nr7"] += 1
                if position is None and pending is None:
                    if i + 1 >= n:
                        funnel["no_next"] += 1
                    else:
                        pending = {
                            "nr_high": float(highs[i]),
                            "nr_low": float(lows[i]),
                            "expire_i": i + 1,
                        }
                else:
                    funnel["ignored"] += 1

    return signals, dict(funnel)


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


def replay_signals(
    signals: list[dict],
    book: str,
    use_gov: bool,
    allow_simultaneous: bool = False,
):
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel: dict[str, int] = defaultdict(int)
    busy_until: dict[str, pd.Timestamp | None] = {"US100": None, "BTC": None}

    # On same timestamp: US100 then BTC (pace sleeve after NR7)
    def sort_key(s):
        pri = 0 if s["symbol"] == "US100" else 1
        return (s["entry_ts"], pri)

    ordered = sorted(signals, key=sort_key)

    for sig in ordered:
        sym = sig["symbol"]
        bu = busy_until.get(sym)
        if bu is not None and sig["entry_ts"] < bu:
            funnel["skip_overlap"] += 1
            continue

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

    chassis_map = {
        "41A": "us100-nr7-1.00" + ("+softgov" if use_gov else ""),
        "41B": "btc-h4-bb-squeeze-0.75" + ("+softgov" if use_gov else ""),
        "41C": "us100nr7+btc-joint-ungov",
        "41D": "us100nr7+btc-joint+softgov",
    }
    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis_map.get(book, book),
        "taken": len(trades),
        "use_gov": use_gov,
        "symbol": "JOINT" if book in ("41C", "41D") else ("US100" if book == "41A" else "BTC"),
        "n_signals_in": len(signals),
        "allow_simultaneous": allow_simultaneous,
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


def explorer_triplet_score(trades: list[Trade], zero_time: bool = False):
    if not trades:
        return {
            "windows": [],
            "final": START_EQUITY,
            "dd": 0.0,
            "max_dd_abs": 0.0,
        }
    rows = []
    for seq, tr in enumerate(trades):
        rows.append(
            {
                "exit_ts": tr.exit_ts,
                "entry_ts": tr.entry_ts,
                "pnl_raw": tr.pnl,
                "reason": tr.reason,
                "symbol": tr.symbol,
                "seq": seq,
            }
        )

    equity = START_EQUITY
    peak = START_EQUITY
    max_dd = 0.0
    booked = []
    for r in sorted(rows, key=lambda x: (x["exit_ts"], x["seq"])):
        pnl = 0.0 if (zero_time and r["reason"] == "TIME") else r["pnl_raw"]
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
        booked.append({**r, "pnl": pnl, "equity_after": equity})

    months_eq = {}
    eq_cursor = START_EQUITY
    by_m: dict[str, float] = defaultdict(float)
    for b in booked:
        by_m[prague_month(b["exit_ts"])] += b["pnl"]
    for ym in COMPLETE:
        eq_start = eq_cursor
        pnl = float(by_m.get(ym, 0.0))
        eq_cursor = eq_start + pnl
        months_eq[ym] = {"equity_start": eq_start, "equity_end": eq_cursor}

    windows = []
    for i in range(len(COMPLETE) - 2):
        trip = COMPLETE[i : i + 3]
        start_eq = months_eq[trip[0]]["equity_start"]
        inside = [b for b in booked if prague_month(b["exit_ts"]) in trip]
        reached_110 = reached_1155 = False
        min_eq = max_eq = None
        for b in inside:
            ea = float(b["equity_after"])
            min_eq = ea if min_eq is None or ea < min_eq else min_eq
            max_eq = ea if max_eq is None or ea > max_eq else max_eq
            if (not reached_110) and ea >= start_eq * 1.10:
                reached_110 = True
            if (not reached_1155) and ea >= start_eq * 1.155:
                reached_1155 = True
        floor = min_eq is not None and min_eq <= start_eq * 0.90
        inter = set(trip) & STREAK
        ov = (
            "outside"
            if not inter
            else ("inside_streak" if inter == set(trip) else "partial_overlap")
        )
        passed = bool(reached_110 and reached_1155 and not floor)
        windows.append(
            {
                "months": trip,
                "overlap": ov,
                "passed": passed,
                "max_return_pct": ((max_eq / start_eq - 1) * 100) if max_eq is not None else 0.0,
            }
        )
    return {
        "windows": windows,
        "final": equity,
        "dd": -max_dd,
        "max_dd_abs": max_dd,
    }


def explorer_crosscheck(trades: list[Trade]):
    real = explorer_triplet_score(trades, zero_time=False)
    zero = explorer_triplet_score(trades, zero_time=True)
    real_pass = {tuple(w["months"]) for w in real["windows"] if w["passed"]}
    tz_pass = {tuple(w["months"]) for w in zero["windows"] if w["passed"]}
    countable = sorted(real_pass & tz_pass)
    outside = [list(m) for m in countable if set(m).isdisjoint(STREAK)]
    outside_real = [w for w in real["windows"] if w["overlap"] == "outside"]
    best = max(outside_real, key=lambda w: w["max_return_pct"]) if outside_real else None
    return {
        "countable": len(countable),
        "outside_countable": len(outside),
        "outside_windows": outside,
        "best_outside_pct": (best or {}).get("max_return_pct"),
        "best_outside_months": (best or {}).get("months"),
        "full_sample_dd": real["dd"],
        "final_equity": real["final"],
    }


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end, ext_available_flag=None):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    if ext_available_flag is None:
        ext_available = data_end >= EXT_START
    else:
        ext_available = bool(ext_available_flag)
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (US100 feed ends 2026-09-01; no dukas-ext)"

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
    ext_ok = (not ext_available) or (ext_net >= 0)
    ho_ok = ho_net > 0

    if not legal or not has_90:
        decision = "REJECT"
    elif legal and has_90_ho and ho_ok and leave_ok and ext_ok:
        if ext_available and ext_net >= 0:
            decision = "ACCEPT"
        else:
            decision = "CONDITIONAL"
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    xcheck = explorer_crosscheck(trades)

    if book == "41A":
        full, mid, floor = US100_FULL, US100_MID, US100_FLOOR
    elif book == "41B":
        full, mid, floor = BTC_FULL, BTC_MID, BTC_FLOOR
    else:
        full = US100_FULL + BTC_FULL
        mid = US100_MID + BTC_MID
        floor = US100_FLOOR + BTC_FLOOR

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
        "ext_available": ext_available,
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
        "explorer_xcheck": xcheck,
    }


def write_docs(summaries, measured, us_end, btc_end, us_sha, btc_sha):
    PACK.mkdir(parents=True, exist_ok=True)

    by_book = {s["book"]: s for s in summaries}
    primary = by_book.get("41D") or summaries[-1]
    legal_with_90 = [s for s in summaries if s["legal"] and s["has_90"]]
    ho_ok_books = [s for s in legal_with_90 if s.get("has_90_ho")]
    if primary["decision"] == "REJECT" and ho_ok_books:
        ho_ok_books.sort(
            key=lambda s: (
                0 if s["decision"] == "ACCEPT" else 1,
                -(s["n90_ho"] + s["nseq_ho"]),
                -s["ho_pace"],
            )
        )
        primary = ho_ok_books[0]
    elif primary["decision"] == "REJECT" and legal_with_90:
        legal_with_90.sort(key=lambda s: (-(s["n90"] + s["nseq"]), -s["ho_pace"]))
        primary = legal_with_90[0]

    opens = primary["decision"] == "ACCEPT"
    if opens:
        lead = (
            f"**YES — US100 NR7 + BTC C15 soft opens a deployable ~3mo path** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — US100 NR7 + BTC C15 soft legal DD + windows, not ACCEPT** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo."
        )
    else:
        lead = (
            "**NO — US100 NR7 + BTC C15 soft joint (no XAG) does not open a deployable ~3mo path.** "
            "DD illegal, HO≤0, or zero ≤90d windows."
        )

    b41a = by_book.get("41A")
    b41b = by_book.get("41B")
    b41d = by_book.get("41D")
    window_note = None
    if b41a and b41b and b41d:
        window_note = (
            f"41A HO≤90d={b41a['n90_ho']} | 41B HO≤90d={b41b['n90_ho']} → "
            f"41D joint HO≤90d={b41d['n90_ho']} "
            f"(seq HO {b41a['nseq_ho']}+{b41b['nseq_ho']}→{b41d['nseq_ho']})"
        )

    lines = []
    lines.append("# Candidate 41 Results — US100 NR7 @1% + BTC C15 H4 BB squeeze soft (no XAG)")
    lines.append("")
    lines.append(lead)
    lines.append("")
    if window_note:
        lines.append(f"**Window creation (alone→joint):** {window_note}")
        lines.append("")
    lines.append(f"**US100 data:** `{US100_PATH}` sha256 `{us_sha}` end `{us_end}`")
    lines.append(f"**BTC data:** `{BTC_MAIN}` + dukas-ext sha256 main `{btc_sha}` end `{btc_end}`")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |")
    lines.append("| BTC costs | spread **15** / comm 0 / contract 1 (C15 model) |")
    lines.append("| US100 risks | **1.00% / 0.50% / 0.25%** |")
    lines.append("| BTC risks | **0.75% / 0.40% / 0.20%** (exact C15 full) |")
    lines.append("| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |")
    lines.append("| Prague day kill | −3% both sleeves |")
    lines.append("| Max positions | one per sleeve (two simultaneous OK) |")
    lines.append("| XAG | **excluded** (C35/C37/C39 closed) |")
    lines.append("| Gold | not packaged |")
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|")
    for s in summaries:
        xc = s["explorer_xcheck"]
        gov = "SOFT" if s["use_gov"] else "OFF"
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        lines.append(
            f"| {s['book']} | {s['symbol']} | {gov} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {ext} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | "
            f"{xc['outside_countable']}/{xc['countable']} best={xc['best_outside_pct']} | "
            f"{s['decision']} |"
        )
    lines.append("")
    for s in summaries:
        lines.append(f"### {s['book']} — {s['label']}")
        lines.append("")
        lines.append(f"- trades={s['n_trades']} WR={s['wr']*100:.1f}% L/S={s['longs']}/{s['shorts']}")
        lines.append(f"- reasons={s['reasons']} gov={s['gov_counts']} by_sym={s['by_sym']}")
        lines.append(
            f"- HO net ${s['ho_net']:,.0f} (~${s['ho_pace']:,.0f}/mo) | Fit ${s['fit_net']:,.0f} | "
            f"leave-out drop {s['leave_drop']} → ${s['leave_net']:,.0f}"
        )
        lines.append(
            f"- max DD {s['max_dd']*100:.2f}% | worst Prague day {s['worst_day']} @ {s['worst_pct']*100:.2f}% | "
            f"fail-days {s['n_fail_days']} | legal={s['legal']}"
        )
        lines.append(
            f"- ≤90d {s['n90']}/{s['w90']} (HO-era {s['n90_ho']}) | seq {s['nseq']}/{s['wseq']} (HO-era {s['nseq_ho']})"
        )
        xc = s["explorer_xcheck"]
        lines.append(
            f"- Explorer xcheck: outside_countable={xc['outside_countable']} countable={xc['countable']} "
            f"best_outside%={xc['best_outside_pct']} months={xc['best_outside_months']} "
            f"dd={xc['full_sample_dd']}"
        )
        if s["p90"]:
            lines.append(f"- sample ≤90d starts: {[p['start'] for p in s['p90'][:5]]}")
        if s["pseq"]:
            lines.append(f"- sample seq starts: {[p['start'] for p in s['pseq'][:5]]}")
        lines.append(f"- final equity ${s['final_equity']:,.0f} | chassis `{s['meta'].get('chassis')}`")
        lines.append("")

    lines.append("## Does this open a ~3mo path?")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append("Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. XAG excluded. No deploy.")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-41-results.md").write_text(RESULTS.read_text())

    summary_lines = [lead, ""]
    if window_note:
        summary_lines.append(f"WINDOW_CREATION|{window_note}")
    for s in summaries:
        xc = s["explorer_xcheck"]
        summary_lines.append(
            f"{s['book']}|{s['symbol']}|gov={s['use_gov']}|{s['decision']}|"
            f"pace=${s['ho_pace']:.0f}/mo|DD={s['max_dd']*100:.1f}%|"
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']})|"
            f"seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']})|"
            f"legal={s['legal']}|leave={s['leave_net']:.0f}|"
            f"xcheck_out={xc['outside_countable']}/{xc['countable']} best={xc['best_outside_pct']}"
        )
    SUMMARY_TXT.write_text("\n".join(summary_lines) + "\n")
    (PACK / "candidate-41-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 41,
        "measured": measured,
        "lead": lead,
        "primary": primary["book"],
        "decision": primary["decision"],
        "window_creation": window_note,
        "assumptions": {
            "us100_spread": US100_SPREAD,
            "us100_risks": [US100_FULL, US100_MID, US100_FLOOR],
            "btc_spread": BTC_SPREAD,
            "btc_risks": [BTC_FULL, BTC_MID, BTC_FLOOR],
            "xag": "excluded",
            "gold": "not packaged",
            "note": "C15 BTC full 0.75% soft ladder + Explorer US100 NR7 1% soft; no XAG",
        },
        "books": [
            {
                k: (v if not isinstance(v, (np.floating, np.integer)) else float(v))
                for k, v in s.items()
                if k != "meta"
            }
            | {"meta": s["meta"]}
            for s in summaries
        ],
        "data": {
            "us100_sha": us_sha,
            "us100_end": str(us_end),
            "btc_sha": btc_sha,
            "btc_end": str(btc_end),
        },
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (PACK / "candidate-41-results.json").write_text(RESULTS_JSON.read_text())

    prior = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C41 US100 NR7 + BTC C15 soft — {primary['decision']}** — {lead}")
    status.append("")
    status.append("_Prior:_ preserved below (C40 / C39 / …).")
    status.append("")
    status.append("## Candidate 41")
    status.append("")
    status.append(
        "| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |"
    )
    status.append("|---|---|---|---:|---:|---:|---:|---|---:|---|---|")
    for s in summaries:
        gov = "SOFT" if s["use_gov"] else "OFF"
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        status.append(
            f"| {s['book']} | {s['symbol']} | {gov} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {ext} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    if window_note:
        status.append(f"**Window creation:** {window_note}")
        status.append("")
    status.append("## Live")
    status.append(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C41 arms without Odin approval. "
        "Gold not packaged. XAG excluded."
    )
    status.append("")

    if prior:
        status.append("---")
        status.append("")
        status.append("## Preserved prior STATUS")
        status.append("")
        prior_lines = prior.splitlines()
        if prior_lines and prior_lines[0].startswith("# BTC"):
            prior_lines = prior_lines[1:]
            while prior_lines and prior_lines[0].strip() == "":
                prior_lines = prior_lines[1:]
        status.extend(prior_lines)
        status.append("")

    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pr.append("## Candidate 41 — US100 NR7 @1% + BTC C15 H4 BB squeeze soft (no XAG)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    if window_note:
        pr.append(f"**Window creation (alone→joint):** {window_note}")
        pr.append("")
    pr.append(
        "Locked a-priori: XAG+NR7 stacks (C35/C37/C39) cannot keep HO ≤90d windows. "
        "Pivot to pace sleeves without XAG — US100 NR7 (~$1.9k/mo, 0 HO windows) + "
        "BTC C15 BB squeeze (~$1.3k/mo @0.75%). Shared soft joint may create HO windows neither has alone."
    )
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Decision | HO $/mo | Max DD | ≤90d HO | seq HO | Leave-out | Explorer out |")
    pr.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        xc = s["explorer_xcheck"]
        pr.append(
            f"| {s['book']} | {s['decision']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90_ho']} | {s['nseq_ho']} | {s['leave_net']:,.0f} | {xc['outside_countable']} |"
        )
    pr.append("")
    pr.append("### ASSUMPTIONS")
    pr.append("- US100: spread 1 / comm 0 / contract 1; risks **1.00→0.50→0.25**")
    pr.append("- BTC: spread **15** / comm 0; risks **0.75→0.40→0.20** (exact C15)")
    pr.append("- Soft gov: dd<5% full / 5–8% mid / ≥8% floor; Prague −3% kill both")
    pr.append("- One pos/sleeve; joint may hold both open")
    pr.append("- **XAG excluded**; Gold not packaged")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-41/`")
    pr.append("")
    pr.append("Research only. Live C4 + drip freeze + MetaAPI untouched. Do not package Gold. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C41.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-41.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_41.py")

    print(lead)
    if window_note:
        print("  Window creation:", window_note)
    for s in summaries:
        xc = s["explorer_xcheck"]
        print(
            f"  {s['book']}: {s['decision']} DD={s['max_dd']*100:.1f}% pace=${s['ho_pace']:.0f}/mo "
            f"90HO={s['n90_ho']} seqHO={s['nseq_ho']} xcheck_out={xc['outside_countable']} "
            f"best={xc['best_outside_pct']}"
        )
    return primary, lead


def main():
    print("Loading US100 M1...")
    us = load_m1(US100_PATH, US100_SHA)
    us_end = us.index[-1]
    us_sha = US100_SHA
    print(f"  US100 M1: {len(us)} → {us_end}")

    print("Loading BTC M1 (main+ext)...")
    btc = load_btc_m1()
    btc_end = btc.index[-1]
    btc_sha = sha256_of(BTC_MAIN)
    if btc_sha != BTC_MAIN_SHA:
        print(f"  WARN BTC sha changed: {btc_sha} (expected {BTC_MAIN_SHA})")
    print(f"  BTC M1: {len(btc)} → {btc_end}")

    us_daily = build_daily(us)
    btc_h4 = build_h4(btc)
    print(f"  US100 D1: {len(us_daily)} | BTC H4: {len(btc_h4)}")

    print("Extracting US100 NR7 signals...")
    us_sigs, us_funnel = extract_us100_nr7(us_daily)
    print(f"  US100 NR7 signals={len(us_sigs)} funnel={us_funnel}")

    print("Extracting BTC C15 squeeze signals...")
    btc_sigs = extract_btc_squeeze_signals(btc, btc_h4)
    print(f"  BTC squeeze signals={len(btc_sigs)}")

    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    summaries = []

    print("Running 41A US100 NR7 soft...")
    t, dp, ds, meta = replay_signals(us_sigs, "41A", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize(
            "41A US100 NR7 @1% soft",
            "41A",
            t,
            dp,
            ds,
            meta,
            True,
            us_end,
            ext_available_flag=False,
        )
    )
    print(f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']}")

    print("Running 41B BTC C15 soft...")
    t, dp, ds, meta = replay_signals(btc_sigs, "41B", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize(
            "41B BTC C15 @0.75% soft",
            "41B",
            t,
            dp,
            ds,
            meta,
            True,
            btc_end,
            ext_available_flag=True,
        )
    )
    print(f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']}")

    joint_sigs = us_sigs + btc_sigs

    print("Running 41C joint ungoverened...")
    t, dp, ds, meta = replay_signals(joint_sigs, "41C", use_gov=False, allow_simultaneous=True)
    summaries.append(
        summarize(
            "41C joint ungoverened",
            "41C",
            t,
            dp,
            ds,
            meta,
            False,
            btc_end,
            ext_available_flag=True,
        )
    )
    print(f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']}")

    print("Running 41D joint soft gov (verdict)...")
    t, dp, ds, meta = replay_signals(joint_sigs, "41D", use_gov=True, allow_simultaneous=True)
    summaries.append(
        summarize(
            "41D joint + soft gov (verdict)",
            "41D",
            t,
            dp,
            ds,
            meta,
            True,
            btc_end,
            ext_available_flag=True,
        )
    )
    print(f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']}")

    write_docs(summaries, measured, us_end, btc_end, us_sha, btc_sha)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
