#!/usr/bin/env python3
"""Candidate 21: Soft DD governor on BTC H4-BREAK-6 channel (+ XAG mirror).

Locked a-priori soft governor (never sticky-block; only cut risk):
  21A — BTC H4-BREAK-6 channel @1.00% / 0.50% / 0.25% (dd <5% / 5–8% / ≥8%)
  21B — XAG Donchian 20d dual @2.50% / 1.25% / 0.75% (same dd thresholds)

Also report ungoverened baselines for delta vs C20 sticky.
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

XAG_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv"
)
XAG_SHA = "6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c"
BTC_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv"
)
BTC_EXT = Path(
    "/workspace/btc-strategies/dukas-ext/btcusd-m1-bid-2026-09-01-2026-10-07T11-34.csv"
)

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-21"
SPEC = OUT_DIR / "ftmo-candidate-21.md"
RESULTS = OUT_DIR / "candidate-21-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-21-summary.txt"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C21.md"
RUNNER = OUT_DIR / "run_candidate_21.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
DAILY_KILL = -0.03
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

# Soft governor thresholds (locked — never block)
GOV_SOFT = 0.05
GOV_HARD = 0.08

# XAG costs (C19B ASSUMPTIONS)
XAG_CONTRACT = 5000.0
XAG_SPREAD = 0.025
XAG_COMM = 3.0
XAG_MAX_LOT = 100.0
DONCH_N = 20
ATR_MULT_XAG = 2.0
R_MULT_XAG = 1.0
MAX_HOLD_DAYS = 10
XAG_FULL = 0.025
XAG_MID = 0.0125
XAG_FLOOR = 0.0075

# BTC costs / H4B6 channel (C20B parity)
BTC_SPREAD = 15.0
BTC_MAX_LOT = 50.0
H4_LOOKBACK = 6
H4_EXIT_LB = 3
H4_ATR_MULT = 1.5
BTC_CH_FULL = 0.010
BTC_CH_MID = 0.005
BTC_CH_FLOOR = 0.0025

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
    gov_state: str  # full / mid / floor / (n/a for ungoverened)


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


def load_btc_m1() -> pd.DataFrame:
    frames = []
    for path in (BTC_MAIN, BTC_EXT):
        if not path.exists():
            if path == BTC_EXT:
                continue
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


def atr14_simple(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
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


def atr14_xag(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
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
        atr[i] = round(float(csum[i] - csum[i - 14]) / 14.0, 6)
    return atr


def soft_gov_risk(equity: float, peak: float, full: float, mid: float, floor: float) -> tuple[float, str]:
    """Soft governor: never block. full / mid / floor by dd band."""
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return floor, "floor"
    if dd >= GOV_SOFT:
        return mid, "mid"
    return full, "full"


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


def run_xag_donchian(daily: pd.DataFrame, full_risk: float, mid_risk: float, floor_risk: float, use_gov: bool):
    opens = daily["open"].to_numpy(dtype=float)
    highs = daily["high"].to_numpy(dtype=float)
    lows = daily["low"].to_numpy(dtype=float)
    closes = daily["close"].to_numpy(dtype=float)
    index = daily.index
    atr = atr14_xag(highs, lows, closes)
    n = len(daily)

    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    pending = None
    position = None
    funnel = defaultdict(int)
    unfinished = 0

    for i in range(n):
        if pending is not None:
            if position is not None:
                raise RuntimeError("pending while in position")
            entry = float(opens[i])
            entry_ts = pd.Timestamp(index[i])
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.tz_localize("UTC")
            pd_entry = prague_day(entry_ts)

            if pd_entry in killed_days:
                funnel["skip_kill"] += 1
                pending = None
            else:
                if pd_entry not in day_start_eq:
                    day_start_eq[pd_entry] = equity
                if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
                    killed_days.add(pd_entry)
                    funnel["skip_kill"] += 1
                    pending = None
                else:
                    # Soft governor (never block)
                    if use_gov:
                        risk, gstate = soft_gov_risk(
                            equity, peak, full_risk, mid_risk, floor_risk
                        )
                        funnel[f"gov_{gstate}"] += 1
                    else:
                        risk, gstate = full_risk, "n/a"

                    if pending is not None:
                        sl_dist = ATR_MULT_XAG * float(pending["atr"])
                        lots = size_lots_xag(equity, risk, sl_dist)
                        if lots < MIN_LOT or sl_dist <= 0:
                            funnel["skip_lots"] += 1
                            pending = None
                        else:
                            side = pending["side"]
                            if side == "long":
                                stop = entry - sl_dist
                                target = entry + R_MULT_XAG * sl_dist
                            else:
                                stop = entry + sl_dist
                                target = entry - R_MULT_XAG * sl_dist
                            position = {
                                "side": side,
                                "entry": entry,
                                "entry_ts": entry_ts,
                                "entry_i": i,
                                "stop": stop,
                                "target": target,
                                "sl_dist": sl_dist,
                                "lots": lots,
                                "risk_used": risk,
                                "gov_state": gstate,
                            }
                            pending = None

        if position is not None:
            day_num = i - position["entry_i"] + 1
            if day_num > MAX_HOLD_DAYS:
                raise RuntimeError("held past max days")
            hit = resolve_daily_bar(
                position["side"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                position["stop"],
                position["target"],
                day_num,
            )
            if hit is not None:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                pnl = pnl_xag(position["side"], position["entry"], float(fill), position["lots"])
                equity += pnl
                if equity > peak:
                    peak = equity
                pd_exit = prague_day(exit_ts)
                if pd_exit not in day_start_eq:
                    day_start_eq[pd_exit] = equity - pnl
                day_pnl[pd_exit] += pnl
                if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
                    killed_days.add(pd_exit)
                trades.append(
                    Trade(
                        side=position["side"],
                        entry_ts=position["entry_ts"],
                        entry=position["entry"],
                        exit_ts=exit_ts,
                        exit=float(fill),
                        reason=reason,
                        lots=position["lots"],
                        stop_dist=position["sl_dist"],
                        pnl=pnl,
                        equity_after=equity,
                        book="21B",
                        risk_used=position["risk_used"],
                        gov_state=position["gov_state"],
                    )
                )
                position = None

        if position is None and pending is None and i >= DONCH_N:
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                funnel["atr"] += 1
            else:
                hh = float(highs[i - DONCH_N : i].max())
                ll = float(lows[i - DONCH_N : i].min())
                c = float(closes[i])
                if c > hh:
                    side = "long"
                elif c < ll:
                    side = "short"
                else:
                    funnel["no_break"] += 1
                    side = None
                if side is not None:
                    if i + 1 >= n:
                        funnel["no_next"] += 1
                    else:
                        pending = {"side": side, "atr": float(atr[i]), "signal_i": i}
                        funnel["signals"] += 1
        elif position is not None and i >= DONCH_N:
            hh = float(highs[i - DONCH_N : i].max())
            ll = float(lows[i - DONCH_N : i].min())
            c = float(closes[i])
            if c > hh or c < ll:
                funnel["ignored_in_pos"] += 1

    if position is not None:
        unfinished = 1
    if pending is not None:
        funnel["pending_end"] += 1

    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "n_daily": n,
        "unfinished": unfinished,
        "chassis": "xag-donchian-20d-dual-1r" + ("+softgov" if use_gov else ""),
        "taken": len(trades),
        "use_gov": use_gov,
        "full_risk": full_risk,
        "mid_risk": mid_risk,
        "floor_risk": floor_risk,
    }
    return trades, day_pnl, day_start_eq, meta


def prior_window(values: np.ndarray, n: int, how: str) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=np.float64)
    if len(values) <= n:
        return out
    window = np.lib.stride_tricks.sliding_window_view(values, n)
    stats = window.max(axis=1) if how == "max" else window.min(axis=1)
    out[n:] = stats[: len(values) - n]
    return out


def h4b6_channel_signals(m1: pd.DataFrame, h4: pd.DataFrame) -> list[Signal]:
    """Original window-capable H4-BREAK-6: channel exit on prior 3-bar low."""
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14_simple(high, low, close)
    prior_high = prior_window(high, H4_LOOKBACK, "max")
    prior_low3 = prior_window(low, H4_EXIT_LB, "min")

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)
    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    signals: list[Signal] = []
    i = H4_LOOKBACK
    while i < len(h4):
        if not np.isfinite(atr[i]) or atr[i] <= 0 or not np.isfinite(prior_high[i]):
            i += 1
            continue
        if close[i] <= prior_high[i]:
            i += 1
            continue
        entry_i = int(end_locs[i])
        if entry_i >= n_m1:
            break
        entry_px = float(m1_open[entry_i])
        stop_dist = H4_ATR_MULT * float(atr[i])
        if stop_dist <= 0:
            i += 1
            continue
        stop = entry_px - stop_dist
        if entry_px <= stop:
            i += 1
            continue

        # Find exit: stop from entry bar, else channel close < prior 3 low
        channel_i = None
        channel_u = None
        for u in range(i + 1, len(h4)):
            if not np.isfinite(prior_low3[u]):
                continue
            if close[u] < prior_low3[u]:
                channel_i = int(end_locs[u])
                channel_u = u
                break

        # Scan m1 from entry for stop
        exit_i = None
        exit_px = None
        reason = None
        scan_end = channel_i if channel_i is not None else n_m1
        for j in range(entry_i, min(scan_end, n_m1)):
            lo = float(m1_low[j])
            op = float(m1_open[j])
            if lo <= stop:
                if op <= stop:
                    exit_i, exit_px, reason = j, op, "gap-stop"
                else:
                    exit_i, exit_px, reason = j, stop, "stop"
                break
        if exit_i is None and channel_i is not None and channel_i < n_m1:
            # channel fill at open of channel end
            # but stop may have hit on channel bar before open? already scanned to channel_i
            exit_i = channel_i
            exit_px = float(m1_open[exit_i])
            reason = "channel"
        if exit_i is None:
            i += 1
            continue

        signals.append(
            Signal(
                book="h4b6-ch",
                side="long",
                entry_i=entry_i,
                entry_ts=m1_index[entry_i],
                entry=entry_px,
                exit_i=exit_i,
                exit_ts=m1_index[exit_i],
                exit=float(exit_px),
                reason=reason,
                stop_dist=stop_dist,
            )
        )
        # advance to exit bar's H4 index
        exit_bar = int(h4.index.searchsorted(m1_index[exit_i], side="right") - 1)
        i = max(exit_bar, i) + 1 if exit_bar >= 0 else i + 1
    return signals


def scan_m1_exit_r(m1_open, m1_high, m1_low, m1_index, entry_i, side, stop, target):
    n_m1 = len(m1_index)
    for j in range(entry_i, n_m1):
        hi = float(m1_high[j])
        lo = float(m1_low[j])
        op = float(m1_open[j])
        hit_sl = lo <= stop
        hit_tp = hi >= target
        gap_sl = op <= stop
        gap_tp = op >= target
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


def h4b6_r15_signals(m1: pd.DataFrame, h4: pd.DataFrame) -> list[Signal]:
    """C17 harden: 6-bar break, 1.5 ATR stop, R=1.5 target (no channel)."""
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
    for t in range(H4_LOOKBACK, len(h4)):
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        prior_high = float(np.max(high[t - H4_LOOKBACK : t]))
        if close[t] <= prior_high:
            continue
        entry_i = int(end_locs[t])
        if entry_i >= n_m1 or entry_i <= in_trade_until:
            continue
        entry_px = float(m1_open[entry_i])
        stop_dist = H4_ATR_MULT * float(atr[t])
        if stop_dist <= 0:
            continue
        stop = entry_px - stop_dist
        target = entry_px + R15_TARGET * stop_dist
        if entry_px <= stop:
            continue
        ex = scan_m1_exit_r(m1_open, m1_high, m1_low, m1_index, entry_i, "long", stop, target)
        if ex is None:
            in_trade_until = n_m1 - 1
            continue
        exit_i, exit_px, reason = ex
        signals.append(
            Signal(
                book="h4b6-r15",
                side="long",
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


def replay_btc_signals(
    signals: list[Signal],
    full_risk: float,
    mid_risk: float,
    floor_risk: float,
    use_gov: bool,
    book_tag: str,
):
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    meta = {
        "signals": len(signals),
        "taken": 0,
        "skip_kill": 0,
        "skip_lots": 0,
        "gov_floor": 0,
        "gov_mid": 0,
        "gov_full": 0,
    }

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

        if use_gov:
            risk, gstate = soft_gov_risk(equity, peak, full_risk, mid_risk, floor_risk)
            meta[f"gov_{gstate}"] += 1
        else:
            risk, gstate = full_risk, "n/a"

        lots = size_lots_btc(equity, risk, sig.stop_dist)
        if lots < MIN_LOT:
            meta["skip_lots"] += 1
            continue

        pnl = pnl_btc(sig.side, sig.entry, sig.exit, lots)
        equity += pnl
        if equity > peak:
            peak = equity
        meta["taken"] += 1
        pd_exit = prague_day(sig.exit_ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
        day_pnl[pd_exit] += pnl
        if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
            killed_days.add(pd_exit)
        trades.append(
            Trade(
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
                book=book_tag,
                risk_used=risk,
                gov_state=gstate,
            )
        )
    meta["final_equity"] = equity
    meta["peak_equity"] = peak
    meta["killed_days"] = len(killed_days)
    meta["use_gov"] = use_gov
    meta["full_risk"] = full_risk
    meta["mid_risk"] = mid_risk
    meta["floor_risk"] = floor_risk
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
            worst_p, worst_d = pct, d
    return worst_d, worst_p


def days_at_or_below(day_pnl, day_start_eq, thresh: float) -> int:
    n = 0
    for d, pnl in day_pnl.items():
        start = day_start_eq.get(d, START_EQUITY)
        if start > 0 and pnl / start <= thresh:
            n += 1
    return n


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
            by_m[prague_month(tr.exit_ts)] += tr.pnl
    if len(by_m) < 2:
        return [], slice_pnl(trades, HO_START, HO_END)
    top2 = [m for m, _ in sorted(by_m.items(), key=lambda kv: kv[1], reverse=True)[:2]]
    left = sum(
        tr.pnl
        for tr in trades
        if HO_START <= tr.exit_ts <= HO_END and prague_month(tr.exit_ts) not in top2
    )
    return top2, left


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


def count_sequential_reset(
    trades: list[Trade],
    full_risk: float,
    mid_risk: float,
    floor_risk: float,
    use_gov: bool,
    instrument: str,
    window_days: int = 90,
):
    """Challenge +10% then RESET to 100k for Verification +5%, applying soft governor if use_gov."""
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

    def size_fn(eq, risk, stop_dist):
        if instrument == "xag":
            return size_lots_xag(eq, risk, stop_dist)
        return size_lots_btc(eq, risk, stop_dist)

    def pnl_fn(side, entry, exit_px, lots):
        if instrument == "xag":
            return pnl_xag(side, entry, exit_px, lots)
        return pnl_btc(side, entry, exit_px, lots)

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
                if use_gov:
                    risk, _ = soft_gov_risk(eq, peak, full_risk, mid_risk, floor_risk)
                else:
                    risk = full_risk
                lots = size_fn(eq, risk, tr.stop_dist)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_fn(tr.side, tr.entry, tr.exit, lots)
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


def summarize(
    label,
    book,
    trades,
    day_pnl,
    day_start_eq,
    meta,
    full_risk,
    mid_risk,
    floor_risk,
    use_gov,
    instrument,
    data_end,
    ext_available: bool,
):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext)" if instrument == "xag" else "UNAVAILABLE"

    leave_drop, leave_net = leave_out_two_best_ho(trades)
    max_dd = max_realized_dd(trades)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail = days_at_or_below(day_pnl, day_start_eq, DAY_FAIL)

    ho_days = (HO_END.normalize() - HO_START).days + 1
    ho_mo = ho_days / 30.44
    ho_pace = ho_net / ho_mo if ho_mo > 0 else 0.0

    n60, w60, p60 = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)
    nseq, wseq, pseq = count_sequential_reset(
        trades, full_risk, mid_risk, floor_risk, use_gov, instrument, 90
    )

    wins = sum(1 for tr in trades if tr.pnl > 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")
    reasons: dict[str, int] = defaultdict(int)
    gov_counts: dict[str, int] = defaultdict(int)
    for tr in trades:
        reasons[tr.reason] += 1
        gov_counts[tr.gov_state] += 1

    # HO-era / Ext-era window starts (C21 gate: Fit-only = not ACCEPT)
    ho_cut = date(2025, 11, 8)
    n90_ho = sum(1 for p in p90 if date.fromisoformat(p["start"]) >= ho_cut)
    nseq_ho = sum(1 for p in pseq if date.fromisoformat(p["start"]) >= ho_cut)
    has_90 = n90 >= 1 or nseq >= 1
    has_90_ho = n90_ho >= 1 or nseq_ho >= 1

    legal = max_dd <= 0.10 + 1e-12 and n_fail == 0 and worst_pct > DAY_FAIL
    leave_ok = leave_net > 0
    ext_ok = (not ext_available) or (ext_net >= 0)
    ho_ok = ho_net > 0

    # C21 gates
    if not legal or not has_90:
        decision = "REJECT"
    elif has_90_ho and ho_ok and leave_ok and ext_ok and (ext_available or instrument == "xag"):
        # Ext N/A for XAG is OK; BTC needs Ext≥0 when available
        if ext_available and ext_net >= 0 and ho_ok and leave_ok:
            decision = "ACCEPT"
        elif not ext_available and ho_ok and leave_ok:
            # XAG Ext N/A: CONDITIONAL (cannot confirm Ext) unless we treat N/A as pass
            decision = "CONDITIONAL"  # Ext N/A → not full ACCEPT per honesty
        else:
            decision = "CONDITIONAL"
    elif has_90 and not has_90_ho:
        # Fit-era windows only → CONDITIONAL thin / not ACCEPT
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    # Harden ACCEPT: require HO>0, leave-out>0, Ext≥0 measured (or XAG N/A stays CONDITIONAL),
    # and ≥1 HO/Ext-era ≤90d window
    if (
        legal
        and has_90_ho
        and ho_ok
        and leave_ok
        and ext_available
        and ext_net >= 0
    ):
        decision = "ACCEPT"
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"  # Fit-only windows
    elif not legal or not has_90:
        decision = "REJECT"

    return {
        "label": label,
        "book": book,
        "instrument": instrument,
        "use_gov": use_gov,
        "full_risk": full_risk,
        "mid_risk": mid_risk,
        "floor_risk": floor_risk,
        "n_trades": len(trades),
        "wins": wins,
        "wr": wins / len(trades) if trades else 0.0,
        "longs": longs,
        "shorts": shorts,
        "reasons": dict(reasons),
        "gov_counts": dict(gov_counts),
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
        "meta": meta,
    }


def write_docs(summaries, measured, xag_end, btc_end, xag_sha, sticky_ref: dict | None):
    PACK.mkdir(parents=True, exist_ok=True)

    legal_with_90 = [s for s in summaries if s["legal"] and s["has_90"]]
    ho_ok_books = [s for s in legal_with_90 if s.get("has_90_ho")]
    if ho_ok_books:
        ho_ok_books.sort(
            key=lambda s: (
                0 if s["decision"] == "ACCEPT" else 1,
                -(s["n90_ho"] + s["nseq_ho"]),
                -s["ho_pace"],
            )
        )
        primary = ho_ok_books[0]
        opens = primary["decision"] == "ACCEPT"
    elif legal_with_90:
        legal_with_90.sort(
            key=lambda s: (-(s["n90"] + s["nseq"]), -s["ho_pace"])
        )
        primary = legal_with_90[0]
        opens = False
    else:
        primary = max(
            summaries,
            key=lambda s: (
                2 if s["decision"] == "ACCEPT" else (1 if s["decision"] == "CONDITIONAL" else 0),
                1 if s["legal"] else 0,
                s["n90"] + s["nseq"],
                s["ho_pace"],
            ),
        )
        opens = False

    if opens and primary["decision"] == "ACCEPT":
        lead = (
            f"**YES — soft DD governor opens a deployable 1–3mo path** via {primary['book']} "
            f"({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — soft governor legal DD + windows, but not ACCEPT** via {primary['book']} "
            f"({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo. "
            f"Fit-only windows and/or HO/Ext weak → not deployable."
        )
    else:
        lead = (
            "**NO — soft DD governor does not open a deployable 1–3mo path.** "
            "DD still illegal, HO≤0, or zero ≤90d windows."
        )

    lines = []
    lines.append("# Candidate 21 Results — Soft DD governor")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**Measured:** {measured}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**XAG data:** `{XAG_MAIN}` sha256 `{xag_sha}` end `{xag_end}`")
    lines.append(f"**BTC data:** `{BTC_MAIN}` (+ dukas-ext if present) end `{btc_end}`")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step |")
    lines.append("| Challenge / Verification | +10% / +5% |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |")
    lines.append("| BTC 21A risks | **1.00% / 0.50% / 0.25%** |")
    lines.append("| XAG 21B risks | **2.50% / 1.25% / 0.75%** |")
    lines.append("| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B parity) |")
    lines.append("| BTC spread / commission | **15** price units / **0** |")
    lines.append("| Gold packaging | Forbidden |")
    lines.append("")

    lines.append("## Scoreboard vs C20 sticky")
    lines.append("")
    lines.append(
        "| Book | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for s in summaries:
        gov = "SOFT" if s["use_gov"] else "OFF"
        rc = f"{s['full_risk']*100:.2f}/{s['mid_risk']*100:.2f}/{s['floor_risk']*100:.2f}%"
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        lines.append(
            f"| {s['book']} {s['label']} | {gov} | {rc} | {s['ho_pace']:,.0f} | "
            f"{s['leave_net']:+,.0f} | {ext_cell} | "
            f"{s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    if sticky_ref:
        lines.append("")
        lines.append("### C20 sticky reference (from prior run)")
        lines.append("")
        lines.append("| Book | Sticky HO $/mo | Sticky DD | Sticky ≤90d | Sticky seq | Note |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for k, v in sticky_ref.items():
            lines.append(
                f"| {k} | {v['ho_pace']:,.0f} | {v['max_dd']*100:.1f}% | "
                f"{v['n90']}/{v['w90']} | {v['nseq']}/{v['wseq']} | {v['note']} |"
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
            f"reasons={s['reasons']} gov_entry_states={s['gov_counts']}"
        )
        lines.append(
            f"- HO ${s['ho_net']:,.2f} (~${s['ho_pace']:,.2f}/mo); Fit ${s['fit_net']:,.2f}; "
            f"Leave-out ${s['leave_net']:,.2f} (drop {s['leave_drop']}); Ext {s['ext_status']} "
            + ("" if not s["ext_available"] else f"${s['ext_net']:,.2f}")
        )
        lines.append(
            f"- Max DD {s['max_dd']*100:.2f}%; worst Prague day {s['worst_day']} "
            f"{s['worst_pct']*100:.2f}%; fail-days={s['n_fail_days']}; Legal={'YES' if s['legal'] else 'NO'}"
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

    lines.append("## Soft vs sticky delta (critical)")
    lines.append("")
    lines.append(
        "| Pair | Soft HO$/mo | Sticky HO$/mo | Soft DD | Sticky DD | Soft ≤90d (HO) | Sticky ≤90d |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    soft_btc = next((x for x in summaries if x["book"] == "21A" and x["use_gov"]), None)
    soft_xag = next((x for x in summaries if x["book"] == "21B" and x["use_gov"]), None)
    if soft_btc and sticky_ref and "20B sticky" in sticky_ref:
        st = sticky_ref["20B sticky"]
        lines.append(
            f"| BTC H4 channel | {soft_btc['ho_pace']:,.0f} | {st['ho_pace']:,.0f} | "
            f"{soft_btc['max_dd']*100:.1f}% | {st['max_dd']*100:.1f}% | "
            f"{soft_btc['n90']}/{soft_btc['w90']} ({soft_btc['n90_ho']}) | "
            f"{st['n90']}/{st['w90']} |"
        )
    if soft_xag and sticky_ref and "20A sticky" in sticky_ref:
        st = sticky_ref["20A sticky"]
        lines.append(
            f"| XAG Donchian | {soft_xag['ho_pace']:,.0f} | {st['ho_pace']:,.0f} | "
            f"{soft_xag['max_dd']*100:.1f}% | {st['max_dd']*100:.1f}% | "
            f"{soft_xag['n90']}/{soft_xag['w90']} ({soft_xag['n90_ho']}) | "
            f"{st['n90']}/{st['w90']} |"
        )
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.")
    lines.append("Gold not packaged. Do not deploy.")
    lines.append("")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-21-results.md").write_text(RESULTS.read_text())

    if SPEC.exists():
        (PACK / "ftmo-candidate-21.md").write_text(SPEC.read_text())

    SUMMARY_TXT.write_text(
        f"{lead}\n"
        + "\n".join(
            f"{s['book']}|gov={s['use_gov']}|{s['decision']}|pace=${s['ho_pace']:.0f}/mo|"
            f"DD={s['max_dd']*100:.1f}%|90d={s['n90']}/{s['w90']}(HO={s['n90_ho']})|"
            f"seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']})|legal={s['legal']}"
            for s in summaries
        )
        + "\n"
    )
    (PACK / "candidate-21-summary.txt").write_text(SUMMARY_TXT.read_text())

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C21 soft DD governor — {primary['decision']}** — {lead}")
    status.append("")
    status.append("## Candidate 21")
    status.append("")
    status.append(
        "| Book | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Legal | Decision |"
    )
    status.append("|---|---|---:|---:|---:|---:|---|---|---|")
    for s in summaries:
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        status.append(
            f"| {s['book']} | {'SOFT' if s['use_gov'] else 'OFF'} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{ext_cell} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    status.append("## Live")
    status.append("Catalogue drip / C4 ops: **untouched**. Nothing from C21 arms without Odin approval.")
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pr.append("## Candidate 21 — Soft DD governor on BTC H4-BREAK-6 channel (research)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append("Locked a-priori soft governor (<5% full / 5–8% mid / ≥8% floor; never sticky-block).")
    pr.append("Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.")
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |")
    pr.append("|---|---|---:|---:|---:|---:|---|---|")
    for s in summaries:
        pr.append(
            f"| {s['book']} {s['label']} | {'SOFT' if s['use_gov'] else 'OFF'} | "
            f"{s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-21/`")
    pr.append("- `run_candidate_21.py`, `ftmo-candidate-21.md`, `candidate-21-results.md`, `STATUS.md`")
    pr.append("")
    pr.append("### Live")
    pr.append("Research only — do not deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C21.md").write_text(PR_BODY.read_text())

    shutil.copy2(RUNNER, PACK / "run_candidate_21.py")

    dump = []
    for s in summaries:
        row = {k: v for k, v in s.items() if k not in ("p60",)}
        dump.append(row)
    (PACK / "candidate-21-results.json").write_text(json.dumps(dump, indent=2, default=str))

    return lead, primary, opens


def main():
    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("Loading XAG M1...")
    xag = load_xag_m1()
    xag_end = xag.index[-1]
    print(f"  XAG M1: {len(xag)}  → {xag_end}")
    xag_daily = build_daily(xag)
    print(f"  XAG D1: {len(xag_daily)}")

    print("Loading BTC M1...")
    btc = load_btc_m1()
    btc_end = btc.index[-1]
    print(f"  BTC M1: {len(btc)}  → {btc_end}")
    btc_h4 = build_h4(btc)
    print(f"  BTC H4: {len(btc_h4)}")

    xag_ext = xag_end >= EXT_START
    btc_ext = btc_end >= EXT_START

    # C20 sticky reference (from candidate-20-summary / results — locked numbers)
    sticky_ref = {
        "20A sticky": {
            "ho_pace": 0.0,
            "max_dd": 0.085,
            "n90": 0,
            "w90": 827,
            "nseq": 0,
            "wseq": 322,
            "note": "sticky killed all windows",
        },
        "20B sticky": {
            "ho_pace": 0.0,
            "max_dd": 0.080,
            "n90": 77,
            "w90": 916,
            "nseq": 13,
            "wseq": 536,
            "note": "Fit-era only; HO=$0 Ext=$0",
        },
    }

    summaries = []

    # 21B XAG ungoverened / soft-gov (mirror)
    for use_gov, tag in [
        (False, "ungov 2.50%"),
        (True, "soft 2.50→1.25→0.75"),
    ]:
        print(f"Running 21B XAG Donchian {tag}...")
        trades, day_pnl, day_start, meta = run_xag_donchian(
            xag_daily, XAG_FULL, XAG_MID, XAG_FLOOR, use_gov
        )
        print(
            f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}"
        )
        s = summarize(
            tag, "21B", trades, day_pnl, day_start, meta,
            XAG_FULL, XAG_MID, XAG_FLOOR, use_gov, "xag", xag_end, xag_ext,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
            f"legal={s['legal']}"
        )
        summaries.append(s)

    print("Building BTC H4B6 channel signals...")
    sig_ch = h4b6_channel_signals(btc, btc_h4)
    print(f"  channel signals: {len(sig_ch)}")

    # 21A BTC channel ungoverened / soft-gov
    for use_gov, tag in [
        (False, "ungov ch@1.00%"),
        (True, "soft ch 1.00→0.50→0.25"),
    ]:
        print(f"Running 21A BTC channel {tag}...")
        trades, day_pnl, day_start, meta = replay_btc_signals(
            sig_ch, BTC_CH_FULL, BTC_CH_MID, BTC_CH_FLOOR, use_gov, "21A"
        )
        meta["chassis"] = "btc-h4-break6-channel" + ("+softgov" if use_gov else "")
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} meta={meta}")
        s = summarize(
            tag, "21A", trades, day_pnl, day_start, meta,
            BTC_CH_FULL, BTC_CH_MID, BTC_CH_FLOOR, use_gov, "btc", btc_end, btc_ext,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
            f"legal={s['legal']}"
        )
        summaries.append(s)

    lead, primary, opens = write_docs(
        summaries, measured, xag_end, btc_end, XAG_SHA, sticky_ref
    )
    print("\n" + lead)
    print(f"Wrote {RESULTS}")
    print(f"Pack {PACK}")


if __name__ == "__main__":
    main()
