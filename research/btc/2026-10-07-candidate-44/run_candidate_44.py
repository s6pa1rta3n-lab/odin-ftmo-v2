#!/usr/bin/env python3
"""Candidate 44: XAG Donchian soft PRIMARY + BTC C15 FIXED low-risk satellite.

Locked a-priori (not a fishing grid):
  44A — XAG soft alone 2.50→1.25→0.75 (reconfirm)
  44B — BTC C15 FIXED 0.20% alone
  44C — JOINT dual-open: XAG soft + BTC FIXED 0.40%
  44D — JOINT dual-open: XAG soft + BTC FIXED 0.20%
  44E — only if C/D wipe HO windows to 0: MUTEX XAG priority + BTC FIXED 0.40%

Thesis: C43 kept 8 HO windows at legal DD with calm fixed satellite but leave-out FAIL.
BTC C15 alone had leave-out +$2.9k (C41B). Fixed tiny BTC (not soft) may help leave-out
without wiping windows (C29 soft dual wiped).

Research only. No live / C4 / drip / FREEZE / MetaAPI. No Gold. No US100 NR7. No JPN.
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

XAG_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_EXT = Path(
    "/workspace/btc-strategies/dukas-ext/btcusd-m1-bid-2026-09-01-2026-10-07T11-34.csv"
)

XAG_SHA = "6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c"
BTC_MAIN_SHA = "437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-44"
SPEC = OUT_DIR / "ftmo-candidate-44.md"
RESULTS = OUT_DIR / "candidate-44-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-44-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-44-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C44.md"
RUNNER = OUT_DIR / "run_candidate_44.py"

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

# XAG Donchian (C21B)
XAG_CONTRACT = 5000.0
XAG_SPREAD = 0.025
XAG_COMM = 3.0
XAG_MAX_LOT = 100.0
DONCH_N = 20
ATR_MULT_XAG = 2.0
R_MULT_XAG = 1.0
XAG_TIME_DAY = 10
XAG_FULL = 0.025
XAG_MID = 0.0125
XAG_FLOOR = 0.0075

# BTC C15
BTC_SPREAD = 15.0
BTC_MAX_LOT = 50.0
ATR_MULT_BTC = 1.0
R_MULT_BTC = 2.0
BB_PERIOD = 20
BB_K = 2.0
BW_LOOKBACK = 100
BW_PCT = 10.0
BTC_FIXED_40 = 0.0040
BTC_FIXED_20 = 0.0020

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
    if symbol == "XAG":
        return XAG_FULL, XAG_MID, XAG_FLOOR
    return BTC_FIXED_40, BTC_FIXED_40, BTC_FIXED_40


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    if symbol == "XAG":
        lots = round(equity * risk / (stop_dist * XAG_CONTRACT), 2)
        lots = min(lots, XAG_MAX_LOT)
    else:
        lots = round(equity * risk / stop_dist, 2)
        lots = min(lots, BTC_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_sym(symbol: str, side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    if symbol == "XAG":
        units = lots * XAG_CONTRACT
        return raw * units - XAG_SPREAD * units - XAG_COMM * lots
    return raw * lots - BTC_SPREAD * lots


def extract_xag_donchian(daily: pd.DataFrame) -> tuple[list[dict], dict]:
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
    funnel = defaultdict(int)

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
                funnel["signals"] += 1
            else:
                funnel["skip_atr"] += 1
            pending = None

        if pos is not None:
            day_num = i - pos["entry_i"] + 1
            if day_num > XAG_TIME_DAY:
                raise RuntimeError("XAG past day10")
            hit = resolve_daily_bar(
                pos["side"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                pos["stop"],
                pos["target"],
                day_num,
                XAG_TIME_DAY,
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
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                funnel["atr"] += 1
            else:
                hh = float(highs[i - DONCH_N : i].max())
                ll = float(lows[i - DONCH_N : i].min())
                c = float(closes[i])
                if c > hh:
                    pending = {"side": "long", "atr": float(atr[i])}
                    funnel["long"] += 1
                elif c < ll:
                    pending = {"side": "short", "atr": float(atr[i])}
                    funnel["short"] += 1
                else:
                    funnel["no_break"] += 1
        elif pos is not None and i >= DONCH_N:
            hh = float(highs[i - DONCH_N : i].max())
            ll = float(lows[i - DONCH_N : i].min())
            c = float(closes[i])
            if c > hh or c < ll:
                funnel["ignored_in_pos"] += 1

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
    btc_fixed: float | None = None,
    mode: str = "dual",  # dual | single | mutex
):
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel: dict[str, int] = defaultdict(int)
    busy_until: dict[str, pd.Timestamp | None] = {"XAG": None, "BTC": None}
    account_busy_until: pd.Timestamp | None = None

    def sort_key(s):
        pri = 0 if s["symbol"] == "XAG" else 1
        return (s["entry_ts"], pri)

    ordered = sorted(signals, key=sort_key)

    for sig in ordered:
        sym = sig["symbol"]
        bu = busy_until.get(sym)
        if bu is not None and sig["entry_ts"] < bu:
            funnel["skip_overlap"] += 1
            continue

        if mode == "mutex":
            if account_busy_until is not None and sig["entry_ts"] < account_busy_until:
                funnel["skip_mutex_btc" if sym == "BTC" else "skip_mutex_xag_wait"] += 1
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

        if sym == "BTC" and btc_fixed is not None:
            risk, gstate = float(btc_fixed), "fixed"
            funnel["gov_fixed"] += 1
        else:
            full, mid, floor = risk_tiers_for(sym)
            if use_gov and sym == "XAG":
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
        if mode == "mutex":
            account_busy_until = sig["exit_ts"]
        funnel["taken"] += 1
        funnel[f"taken_{sym}"] += 1

    chassis_map = {
        "44A": "xag-donchian-20d-2.50+softgov",
        "44B": "btc-h4-bb-squeeze-fixed-0.20",
        "44C": "xag-soft+btc-fixed-0.40",
        "44D": "xag-soft+btc-fixed-0.20",
        "44E": "xag-soft+btc-fixed-0.40-MUTEX",
    }
    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis_map.get(book, book),
        "taken": len(trades),
        "use_gov": use_gov,
        "btc_fixed": btc_fixed,
        "mode": mode,
        "symbol": "JOINT" if book in ("44C", "44D", "44E") else ("XAG" if book == "44A" else "BTC"),
        "n_signals_in": len(signals),
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
                if tr.gov_state == "fixed":
                    risk = float(tr.risk_used)
                else:
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
        return {"windows": [], "final": START_EQUITY, "dd": 0.0, "max_dd_abs": 0.0}
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
    return {"windows": windows, "final": equity, "dd": -max_dd, "max_dd_abs": max_dd}


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


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end, ext_flag=None):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    if ext_flag is None:
        ext_available = data_end >= EXT_START
    else:
        ext_available = bool(ext_flag)
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE or XAG-silent (note BTC dukas-ext may still move joint Ext)"

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
        decision = "ACCEPT" if (not ext_available or ext_net >= 0) else "CONDITIONAL"
        if not ext_available:
            decision = "CONDITIONAL"
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    xcheck = explorer_crosscheck(trades)

    if book == "44A":
        full, mid, floor = XAG_FULL, XAG_MID, XAG_FLOOR
    elif book == "44B":
        full = mid = floor = BTC_FIXED_20
    elif book == "44C" or book == "44E":
        full = XAG_FULL + BTC_FIXED_40
        mid = XAG_MID + BTC_FIXED_40
        floor = XAG_FLOOR + BTC_FIXED_40
    elif book == "44D":
        full = XAG_FULL + BTC_FIXED_20
        mid = XAG_MID + BTC_FIXED_20
        floor = XAG_FLOOR + BTC_FIXED_20
    else:
        full, mid, floor = XAG_FULL, XAG_MID, XAG_FLOOR

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


def write_docs(summaries, measured, xag_end, btc_end, xag_sha, btc_sha):
    PACK.mkdir(parents=True, exist_ok=True)
    by_book = {s["book"]: s for s in summaries}

    # Prefer legal joint with HO windows + best leave: 44D, 44C, 44E
    primary = None
    for key in ("44D", "44C", "44E"):
        s = by_book.get(key)
        if s and s["legal"] and s.get("has_90_ho") and s.get("leave_ok"):
            primary = s
            break
    if primary is None:
        cands = [by_book[k] for k in ("44D", "44C", "44E") if k in by_book and by_book[k]["legal"] and by_book[k].get("has_90_ho")]
        if cands:
            cands.sort(key=lambda s: (s["leave_net"], -s["max_dd"]), reverse=True)
            primary = cands[0]
    if primary is None:
        for key in ("44D", "44C", "44E", "44A"):
            if key in by_book:
                primary = by_book[key]
                break
    if primary is None:
        primary = summaries[-1]

    b44a = by_book.get("44A")
    leave_a = b44a["leave_net"] if b44a else float("nan")

    if primary["decision"] == "ACCEPT":
        lead = (
            f"**YES — XAG soft + BTC fixed satellite opens a deployable ~3mo path** via "
            f"{primary['book']}: max DD {primary['max_dd']*100:.1f}%, HO≤90d {primary['n90_ho']}, "
            f"leave ${primary['leave_net']:,.0f}, HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        delta = primary["leave_net"] - leave_a if b44a else 0.0
        lead = (
            f"**CONDITIONAL — XAG soft + BTC fixed satellite legal/windows, not ACCEPT** via "
            f"{primary['book']}: max DD {primary['max_dd']*100:.1f}%, HO≤90d {primary['n90_ho']}, "
            f"HO ~${primary['ho_pace']:,.0f}/mo, leave ${primary['leave_net']:,.0f} "
            f"(Δ vs 44A {delta:+,.0f}). Leave-out still blocks ACCEPT."
        )
    else:
        lead = (
            "**NO — XAG soft + BTC fixed satellite does not open a deployable ~3mo path.** "
            "DD illegal, HO windows wiped, or otherwise fails gates."
        )

    joint_keys = [k for k in ("44C", "44D", "44E") if k in by_book]
    xag_survive = None
    windows_survived = None
    if b44a and joint_keys:
        parts = []
        best_joint = None
        for k in joint_keys:
            jb = by_book[k]
            delta = jb["leave_net"] - b44a["leave_net"]
            parts.append(
                f"{k} HO≤90d={jb['n90_ho']} DD={jb['max_dd']*100:.1f}% leave={jb['leave_net']:.0f} (Δ{delta:+.0f})"
            )
            if best_joint is None or (jb["n90_ho"], jb["leave_net"]) > (best_joint["n90_ho"], best_joint["leave_net"]):
                best_joint = jb
        windows_survived = bool(b44a["n90_ho"] > 0 and best_joint and best_joint["n90_ho"] > 0)
        xag_survive = (
            f"44A HO≤90d={b44a['n90_ho']} leave={b44a['leave_net']:.0f} → "
            + " | ".join(parts)
            + f" | windows_survived={'Y' if windows_survived else 'N'}"
        )

    lines = []
    lines.append("# Candidate 44 Results — XAG soft PRIMARY + BTC C15 fixed satellite (no NR7 / no Gold / no JPN)")
    lines.append("")
    lines.append(lead)
    lines.append("")
    if xag_survive:
        lines.append(f"**XAG window survival / leave Δ:** {xag_survive}")
        lines.append("")
    lines.append(f"**XAG data:** `{XAG_PATH}` sha256 `{xag_sha}` end `{xag_end}`")
    lines.append(f"**BTC data:** `{BTC_MAIN}` + dukas-ext sha256 main `{btc_sha}` end `{btc_end}`")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |")
    lines.append("| XAG risks | **2.50% / 1.25% / 0.75%** soft |")
    lines.append("| BTC costs | spread **15** / comm 0 (C15 model) |")
    lines.append("| BTC risks | **FIXED 0.40% (44C/E) or 0.20% (44B/D)** — no soft ladder |")
    lines.append("| Soft gov | XAG only; BTC fixed |")
    lines.append("| Prague day kill | −3% both |")
    lines.append("| Positions | dual-open (44C/D); MUTEX XAG priority (44E only if needed) |")
    lines.append("| US100 / Gold / JPN | excluded |")
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 44A | Legal | Decision |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|")
    for s in summaries:
        mode = s["meta"].get("mode", "")
        btcf = s["meta"].get("btc_fixed")
        mode_s = mode if mode else ("soft" if s["use_gov"] else "fixed")
        if btcf:
            mode_s = f"{mode_s}/{btcf*100:.2f}%"
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        delta = s["leave_net"] - leave_a if b44a else 0.0
        lines.append(
            f"| {s['book']} | {s['symbol']} | {mode_s} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {ext} | {s['leave_net']:,.0f} | "
            f"{delta:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
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
            f"best_outside%={xc['best_outside_pct']} months={xc['best_outside_months']}"
        )
        lines.append(f"- final equity ${s['final_equity']:,.0f} | chassis `{s['meta'].get('chassis')}`")
        lines.append("")

    lines.append("## Does this open a ~3mo path?")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append("Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold/NR7/JPN excluded. No deploy.")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-44-results.md").write_text(RESULTS.read_text())

    summary_lines = [lead, ""]
    if xag_survive:
        summary_lines.append(f"XAG_WINDOW_SURVIVAL|{xag_survive}")
    for s in summaries:
        delta = s["leave_net"] - leave_a if b44a else 0.0
        summary_lines.append(
            f"{s['book']}|{s['symbol']}|{s['decision']}|"
            f"pace=${s['ho_pace']:.0f}/mo|DD={s['max_dd']*100:.1f}%|"
            f"90HO={s['n90_ho']}|leave={s['leave_net']:.0f}|dLeave={delta:+.0f}|legal={s['legal']}"
        )
    SUMMARY_TXT.write_text("\n".join(summary_lines) + "\n")
    (PACK / "candidate-44-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 44,
        "measured": measured,
        "lead": lead,
        "primary": primary["book"],
        "decision": primary["decision"],
        "xag_window_survival": xag_survive,
        "windows_survived": windows_survived,
        "leave_a": leave_a,
        "assumptions": {
            "xag_contract": XAG_CONTRACT,
            "xag_spread": XAG_SPREAD,
            "xag_commission": XAG_COMM,
            "xag_risks": [XAG_FULL, XAG_MID, XAG_FLOOR],
            "btc_spread": BTC_SPREAD,
            "btc_fixed": [BTC_FIXED_40, BTC_FIXED_20],
            "us100": "excluded",
            "gold": "not packaged",
            "jpn": "excluded",
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
            "xag_sha": xag_sha,
            "xag_end": str(xag_end),
            "btc_sha": btc_sha,
            "btc_end": str(btc_end),
        },
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (PACK / "candidate-44-results.json").write_text(RESULTS_JSON.read_text())

    prior = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""
    status = [
        "# BTC FTMO research baseline (2026-10-07)",
        "",
        f"**Status: C44 XAG soft + BTC fixed satellite — {primary['decision']}** — {lead}",
        "",
        "_Prior:_ preserved below (C43 / C42 / …).",
        "",
        "## Candidate 44",
        "",
        "| Book | Symbol | HO $/mo | Max DD | ≤90d (HO) | Ext | Leave-out | Δ vs 44A | Legal | Decision |",
        "|---|---|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for s in summaries:
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        delta = s["leave_net"] - leave_a if b44a else 0.0
        status.append(
            f"| {s['book']} | {s['symbol']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {ext} | {s['leave_net']:,.0f} | "
            f"{delta:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    if xag_survive:
        status.append(f"**XAG window survival / leave Δ:** {xag_survive}")
        status.append("")
    status.append("## Live")
    status.append(
        "Catalogue drip / C4 ops: **untouched**. Gold/NR7/JPN excluded. No deploy from C44."
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
    # short pack STATUS
    (PACK / "STATUS.md").write_text(
        "\n".join(
            [
                "# Candidate 44 STATUS (pack)",
                "",
                f"**{primary['decision']}** — {lead}",
                "",
                f"**XAG window survival / leave Δ:** {xag_survive}",
                "",
                "Live C4 untouched. No Gold/NR7/JPN. No deploy.",
                "",
            ]
        )
    )

    pr = [
        "## Candidate 44 — XAG soft PRIMARY + BTC C15 fixed satellite (no NR7 / no Gold / no JPN)",
        "",
        lead,
        "",
    ]
    if xag_survive:
        pr.append(f"**XAG window survival / leave Δ:** {xag_survive}")
        pr.append("")
    pr.append(
        "Locked a-priori from C43: calm fixed satellite kept all 8 XAG HO windows at legal DD but leave-out FAIL. "
        "BTC C15 alone had leave-out +$2.9k (C41B). C44 uses FIXED tiny BTC (0.40%/0.20%) — not soft dual (C29 wiped)."
    )
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Decision | HO $/mo | Max DD | ≤90d HO | Leave-out | Δ vs 44A |")
    pr.append("|---|---|---:|---:|---:|---:|---:|")
    for s in summaries:
        delta = s["leave_net"] - leave_a if b44a else 0.0
        pr.append(
            f"| {s['book']} | {s['decision']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90_ho']} | {s['leave_net']:,.0f} | {delta:+,.0f} |"
        )
    pr.append("")
    pr.append("### ASSUMPTIONS")
    pr.append("- XAG: contract **5000** / spread **0.025** / $3/lot; soft **2.50→1.25→0.75**")
    pr.append("- BTC: spread **15** / comm 0; **FIXED** 0.40% (44C/E) or 0.20% (44B/D)")
    pr.append("- Soft gov on XAG only; Prague −3% kill; dual-open (MUTEX only if 44E)")
    pr.append("- US100 NR7 / Gold / JPN excluded")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-44/`")
    pr.append("")
    pr.append("Research only. Live C4 + drip freeze + MetaAPI untouched. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C44.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-44.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_44.py")

    print(lead)
    if xag_survive:
        print("  Survival:", xag_survive)
    for s in summaries:
        delta = s["leave_net"] - leave_a if b44a else 0.0
        print(
            f"  {s['book']}: {s['decision']} DD={s['max_dd']*100:.1f}% pace=${s['ho_pace']:.0f}/mo "
            f"90HO={s['n90_ho']} leave={s['leave_net']:.0f} (Δ{delta:+.0f})"
        )
    return primary, lead


def main():
    print("Loading XAG M1...")
    xag = load_m1(XAG_PATH, XAG_SHA)
    xag_end = xag.index[-1]
    print(f"  XAG M1: {len(xag)} → {xag_end}")

    print("Loading BTC M1 (main+ext)...")
    btc = load_btc_m1()
    btc_end = btc.index[-1]
    btc_sha = sha256_of(BTC_MAIN)
    if btc_sha != BTC_MAIN_SHA:
        print(f"  WARN BTC sha changed: {btc_sha}")
    print(f"  BTC M1: {len(btc)} → {btc_end}")

    xag_daily = build_daily(xag)
    btc_h4 = build_h4(btc)
    print(f"  XAG D1: {len(xag_daily)} | BTC H4: {len(btc_h4)}")

    print("Extracting XAG Donchian...")
    xag_sigs, xag_funnel = extract_xag_donchian(xag_daily)
    print(f"  XAG signals={len(xag_sigs)} funnel={xag_funnel}")

    print("Extracting BTC C15 squeeze...")
    btc_sigs = extract_btc_squeeze_signals(btc, btc_h4)
    print(f"  BTC signals={len(btc_sigs)}")

    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    summaries = []
    joint = xag_sigs + btc_sigs

    print("Running 44A XAG soft...")
    t, dp, ds, meta = replay_signals(xag_sigs, "44A", use_gov=True, mode="single")
    summaries.append(summarize("44A XAG soft", "44A", t, dp, ds, meta, True, xag_end, ext_flag=False))
    print(f"  → {summaries[-1]['decision']} DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}")

    print("Running 44B BTC FIXED 0.20%...")
    t, dp, ds, meta = replay_signals(btc_sigs, "44B", use_gov=False, btc_fixed=BTC_FIXED_20, mode="single")
    summaries.append(summarize("44B BTC C15 FIXED 0.20%", "44B", t, dp, ds, meta, False, btc_end, ext_flag=True))
    print(f"  → {summaries[-1]['decision']} DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}")

    print("Running 44C JOINT XAG soft + BTC FIXED 0.40%...")
    t, dp, ds, meta = replay_signals(joint, "44C", use_gov=True, btc_fixed=BTC_FIXED_40, mode="dual")
    summaries.append(summarize("44C joint XAG soft + BTC 0.40%", "44C", t, dp, ds, meta, True, btc_end, ext_flag=True))
    s44c = summaries[-1]
    print(f"  → {s44c['decision']} DD={s44c['max_dd']*100:.1f}% 90HO={s44c['n90_ho']} leave={s44c['leave_net']:.0f}")

    print("Running 44D JOINT XAG soft + BTC FIXED 0.20%...")
    t, dp, ds, meta = replay_signals(joint, "44D", use_gov=True, btc_fixed=BTC_FIXED_20, mode="dual")
    summaries.append(summarize("44D joint XAG soft + BTC 0.20%", "44D", t, dp, ds, meta, True, btc_end, ext_flag=True))
    s44d = summaries[-1]
    print(f"  → {s44d['decision']} DD={s44d['max_dd']*100:.1f}% 90HO={s44d['n90_ho']} leave={s44d['leave_net']:.0f}")

    wiped = (s44c["n90_ho"] == 0) and (s44d["n90_ho"] == 0)
    if wiped:
        print("Running 44E MUTEX XAG priority + BTC FIXED 0.40% (C/D wiped HO windows)...")
        t, dp, ds, meta = replay_signals(joint, "44E", use_gov=True, btc_fixed=BTC_FIXED_40, mode="mutex")
        summaries.append(summarize("44E MUTEX XAG soft + BTC 0.40%", "44E", t, dp, ds, meta, True, btc_end, ext_flag=True))
        print(f"  → {summaries[-1]['decision']} DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}")
    else:
        print("Skipping 44E (44C or 44D kept HO windows)")

    write_docs(summaries, measured, xag_end, btc_end, XAG_SHA, btc_sha)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
