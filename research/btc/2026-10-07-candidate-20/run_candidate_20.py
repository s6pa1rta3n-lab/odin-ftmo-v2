#!/usr/bin/env python3
"""Candidate 20: Drawdown governor on window-capable entry books.

Locked a-priori:
  20A — XAG C19B Donchian 20d dual @2.50% TP1R ± governor (2.50 / 1.00 / block@8%)
  20B — BTC H4-BREAK-6 channel-exit @1.00% ± governor (1.00 / 0.40 / block@8%)
  20C — BTC H4-BREAK-6 C17 R=1.5 @0.75% ± governor (0.75 / 0.30 / block@8%)

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
PACK = OUT_DIR / "2026-10-07-candidate-20"
SPEC = OUT_DIR / "ftmo-candidate-20.md"
RESULTS = OUT_DIR / "candidate-20-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-20-summary.txt"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C20.md"
RUNNER = OUT_DIR / "run_candidate_20.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
DAILY_KILL = -0.03
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

# Governor thresholds (locked)
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
XAG_CUT = 0.010

# BTC costs / H4B6
BTC_SPREAD = 15.0
BTC_MAX_LOT = 50.0
H4_LOOKBACK = 6
H4_EXIT_LB = 3
H4_ATR_MULT = 1.5
BTC_CH_FULL = 0.010
BTC_CH_CUT = 0.004
BTC_R15_FULL = 0.0075
BTC_R15_CUT = 0.0030
R15_TARGET = 1.5

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
    gov_state: str  # full / cut / (n/a for ungoverened)


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


def gov_risk(equity: float, peak: float, full: float, cut: float) -> tuple[float | None, str]:
    """Return (risk_or_None_if_blocked, state). Recovery requires dd < soft after hard block."""
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return None, "block"
    if dd >= GOV_SOFT:
        return cut, "cut"
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


def run_xag_donchian(daily: pd.DataFrame, full_risk: float, cut_risk: float, use_gov: bool):
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
    blocked_until_recover = False  # sticky until dd < soft after hard block

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
                    # Governor
                    if use_gov:
                        dd = 1.0 - equity / peak if peak > 0 else 0.0
                        if blocked_until_recover:
                            if dd < GOV_SOFT:
                                blocked_until_recover = False
                            else:
                                funnel["gov_block"] += 1
                                pending = None
                        if pending is not None:
                            if dd >= GOV_HARD:
                                blocked_until_recover = True
                                funnel["gov_block"] += 1
                                pending = None
                            elif dd >= GOV_SOFT:
                                risk, gstate = cut_risk, "cut"
                                funnel["gov_cut"] += 1
                            else:
                                risk, gstate = full_risk, "full"
                                funnel["gov_full"] += 1
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
                # sticky block check after close
                if use_gov:
                    dd_now = 1.0 - equity / peak if peak > 0 else 0.0
                    if dd_now >= GOV_HARD:
                        blocked_until_recover = True
                    elif blocked_until_recover and dd_now < GOV_SOFT:
                        blocked_until_recover = False
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
                        book="20A",
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
        "chassis": "xag-donchian-20d-dual-1r" + ("+gov" if use_gov else ""),
        "taken": len(trades),
        "use_gov": use_gov,
        "full_risk": full_risk,
        "cut_risk": cut_risk,
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
    cut_risk: float,
    use_gov: bool,
    book_tag: str,
):
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    blocked_until_recover = False
    meta = {
        "signals": len(signals),
        "taken": 0,
        "skip_kill": 0,
        "skip_lots": 0,
        "gov_block": 0,
        "gov_cut": 0,
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
            dd = 1.0 - equity / peak if peak > 0 else 0.0
            if blocked_until_recover:
                if dd < GOV_SOFT:
                    blocked_until_recover = False
                else:
                    meta["gov_block"] += 1
                    continue
            if dd >= GOV_HARD:
                blocked_until_recover = True
                meta["gov_block"] += 1
                continue
            if dd >= GOV_SOFT:
                risk, gstate = cut_risk, "cut"
                meta["gov_cut"] += 1
            else:
                risk, gstate = full_risk, "full"
                meta["gov_full"] += 1
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
        if use_gov:
            dd_now = 1.0 - equity / peak if peak > 0 else 0.0
            if dd_now >= GOV_HARD:
                blocked_until_recover = True
            elif blocked_until_recover and dd_now < GOV_SOFT:
                blocked_until_recover = False
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
    meta["cut_risk"] = cut_risk
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
    cut_risk: float,
    use_gov: bool,
    instrument: str,
    window_days: int = 90,
):
    """Challenge +10% then RESET to 100k for Verification +5%, applying governor if use_gov."""
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
            blocked = False
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
                    dd = 1.0 - eq / peak if peak > 0 else 0.0
                    if blocked:
                        if dd < GOV_SOFT:
                            blocked = False
                        else:
                            continue
                    if dd >= GOV_HARD:
                        blocked = True
                        continue
                    risk = cut_risk if dd >= GOV_SOFT else full_risk
                else:
                    risk = full_risk
                lots = size_fn(eq, risk, tr.stop_dist)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_fn(tr.side, tr.entry, tr.exit, lots)
                eq += pnl
                if eq > peak:
                    peak = eq
                if use_gov:
                    dd_now = 1.0 - eq / peak if peak > 0 else 0.0
                    if dd_now >= GOV_HARD:
                        blocked = True
                    elif blocked and dd_now < GOV_SOFT:
                        blocked = False
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
    cut_risk,
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
        trades, full_risk, cut_risk, use_gov, instrument, 90
    )

    wins = sum(1 for tr in trades if tr.pnl > 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")
    reasons: dict[str, int] = defaultdict(int)
    gov_counts: dict[str, int] = defaultdict(int)
    for tr in trades:
        reasons[tr.reason] += 1
        gov_counts[tr.gov_state] += 1

    legal = max_dd <= 0.10 + 1e-12 and n_fail == 0 and worst_pct > DAY_FAIL
    leave_ok = leave_net > 0
    ext_ok = ext_available and ext_net >= 0
    ho_ok = ho_net > 0
    has_90 = n90 >= 1 or nseq >= 1

    # Gates per C20 mandate
    if legal and has_90 and leave_ok and ho_ok and (ext_ok or not ext_available):
        # Ext N/A is OK per mandate ("Ext N/A OK if feed ends")
        if leave_ok and (ext_ok or not ext_available):
            if leave_ok and ho_ok:
                if ext_available and not ext_ok:
                    decision = "CONDITIONAL"
                elif not leave_ok:
                    decision = "CONDITIONAL"
                else:
                    # Ext unavailable: CONDITIONAL if windows+legal; ACCEPT only if Ext≥0 measured
                    decision = "ACCEPT" if ext_ok else "CONDITIONAL"
            else:
                decision = "CONDITIONAL"
        else:
            decision = "CONDITIONAL"
    elif legal and has_90:
        decision = "CONDITIONAL"
    elif (not legal) and has_90:
        decision = "REJECT"  # windows but illegal DD (or governor failed to save DD)
    elif legal and not has_90:
        decision = "REJECT"  # governor killed windows / never had them
    else:
        decision = "REJECT"

    # Refine: mandate says CONDITIONAL if legal DD + ≥1 ≤90d but leave-out/Ext weak
    if legal and has_90 and (not leave_ok or (ext_available and ext_net < 0) or not ext_available):
        decision = "CONDITIONAL"
    if legal and has_90 and leave_ok and ext_ok:
        decision = "ACCEPT"
    if not legal or not has_90:
        if legal and not has_90:
            decision = "REJECT"
        elif not legal:
            decision = "REJECT"

    return {
        "label": label,
        "book": book,
        "instrument": instrument,
        "use_gov": use_gov,
        "full_risk": full_risk,
        "cut_risk": cut_risk,
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
        "nseq": nseq,
        "wseq": wseq,
        "pseq": pseq,
        "has_90": has_90,
        "decision": decision,
        "final_equity": trades[-1].equity_after if trades else START_EQUITY,
        "meta": meta,
    }


def write_docs(summaries, measured, xag_end, btc_end, xag_sha):
    PACK.mkdir(parents=True, exist_ok=True)

    # Pick best LEGAL ≤90d path
    legal_with_90 = [s for s in summaries if s["legal"] and s["has_90"]]
    if legal_with_90:
        # Prefer ACCEPT, then CONDITIONAL; among them prefer more windows then higher HO pace
        legal_with_90.sort(
            key=lambda s: (
                0 if s["decision"] == "ACCEPT" else 1,
                -(s["n90"] + s["nseq"]),
                -s["ho_pace"],
            )
        )
        primary = legal_with_90[0]
        opens = True
    else:
        # fallback: best by decision priority
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
            f"**YES — DD governor opens a measured 1–3mo pass path** via {primary['book']} "
            f"({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']}, seq {primary['nseq']}/{primary['wseq']}, "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif opens and primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — DD governor yields legal DD + ≤90d windows** via {primary['book']} "
            f"({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']}, seq {primary['nseq']}/{primary['wseq']}, "
            f"HO ~${primary['ho_pace']:,.0f}/mo — leave-out/Ext weak (document)."
        )
    else:
        lead = (
            "**NO — DD governor does not open a 1–3mo pass path.** "
            "Either windows die under the governor, or DD stays illegal."
        )

    lines = []
    lines.append("# Candidate 20 Results — Drawdown governor")
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
    lines.append("| Governor soft / hard | **5%** cut / **8%** block until dd<5% |")
    lines.append("| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B parity) |")
    lines.append("| BTC spread / commission | **15** price units / **0** |")
    lines.append("| Gold packaging | Forbidden |")
    lines.append("")
    lines.append("## Scoreboard — ungoverened vs governed")
    lines.append("")
    lines.append(
        "| Book | Gov | Full/Cut | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 | Legal | Decision |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for s in summaries:
        gov = "YES" if s["use_gov"] else "NO"
        rc = f"{s['full_risk']*100:.2f}%/{s['cut_risk']*100:.2f}%"
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        leave_cell = f"{s['leave_net']:+,.0f}"
        lines.append(
            f"| {s['book']} {s['label']} | {gov} | {rc} | {s['ho_pace']:,.0f} | "
            f"{s['fit_net']:+,.0f} | {leave_cell} | {ext_cell} | "
            f"{s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | "
            f"{s['n60']}/{s['w60']} | {s['n90']}/{s['w90']} | {s['nseq']}/{s['wseq']} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    lines.append("")

    for s in summaries:
        lines.append(f"## {s['book']} — {s['label']} (gov={'ON' if s['use_gov'] else 'OFF'})")
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
            f"- Windows: ≤60d {s['n60']}/{s['w60']}; ≤90d cont {s['n90']}/{s['w90']}; "
            f"seq90 reset {s['nseq']}/{s['wseq']}"
        )
        lines.append(f"- Final equity ${s['final_equity']:,.2f}")
        if s["p90"]:
            lines.append("")
            lines.append("### ≤90d continuous pass sample")
            lines.append("| Start | End | Start eq | Max mult | Min mult | Worst day |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for p in s["p90"][:12]:
                lines.append(
                    f"| {p['start']} | {p['end']} | ${p['start_eq']:,.0f} | "
                    f"{p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']*100:.2f}% |"
                )
        if s["pseq"]:
            lines.append("")
            lines.append("### seq90 reset pass sample")
            lines.append("| Start | Challenge done | Verification done | Total days |")
            lines.append("|---|---|---|---:|")
            for p in s["pseq"][:12]:
                lines.append(
                    f"| {p['start']} | {p['challenge_done']} | {p['verification_done']} | {p['total_days']} |"
                )
        lines.append("")
        lines.append(f"Meta: `{json.dumps(s['meta'], default=str)}`")
        lines.append("")

    lines.append("## Ungoverened → governed delta (critical)")
    lines.append("")
    lines.append("| Pair | Ungov DD | Gov DD | Ungov ≤90d | Gov ≤90d | Ungov seq | Gov seq | Ungov HO$/mo | Gov HO$/mo |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    pairs = [
        ("20A XAG Donchian", "20A"),
        ("20B BTC channel", "20B"),
        ("20C BTC R15 C17", "20C"),
    ]
    for pname, prefix in pairs:
        off = next((x for x in summaries if x["book"] == prefix and not x["use_gov"]), None)
        on = next((x for x in summaries if x["book"] == prefix and x["use_gov"]), None)
        if off and on:
            lines.append(
                f"| {pname} | {off['max_dd']*100:.1f}% | {on['max_dd']*100:.1f}% | "
                f"{off['n90']}/{off['w90']} | {on['n90']}/{on['w90']} | "
                f"{off['nseq']}/{off['wseq']} | {on['nseq']}/{on['wseq']} | "
                f"{off['ho_pace']:,.0f} | {on['ho_pace']:,.0f} |"
            )
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.")
    lines.append("Gold not packaged. Do not deploy.")
    lines.append("")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-20-results.md").write_text(RESULTS.read_text())

    # Ensure spec in pack
    if SPEC.exists():
        (PACK / "ftmo-candidate-20.md").write_text(SPEC.read_text())

    SUMMARY_TXT.write_text(
        f"{lead}\n"
        + "\n".join(
            f"{s['book']}|gov={s['use_gov']}|{s['decision']}|pace=${s['ho_pace']:.0f}/mo|"
            f"DD={s['max_dd']*100:.1f}%|90d={s['n90']}/{s['w90']}|seq={s['nseq']}/{s['wseq']}|"
            f"legal={s['legal']}"
            for s in summaries
        )
        + "\n"
    )
    (PACK / "candidate-20-summary.txt").write_text(SUMMARY_TXT.read_text())

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C20 DD governor — {primary['decision']}** — {lead}")
    status.append("")
    status.append("## Candidate 20")
    status.append("")
    status.append(
        "| Book | Gov | HO $/mo | Max DD | ≤90d | seq90 | Ext | Legal | Decision |"
    )
    status.append("|---|---|---:|---:|---:|---:|---|---|---|")
    for s in summaries:
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        status.append(
            f"| {s['book']} | {'ON' if s['use_gov'] else 'OFF'} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} | {s['nseq']}/{s['wseq']} | "
            f"{ext_cell} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    status.append("## Live")
    status.append("Catalogue drip / C4 ops: **untouched**. Nothing from C20 arms without Odin approval.")
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pr.append("## Candidate 20 — Drawdown governor on window-capable books (research)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append("Locked a-priori governor (5% cut / 8% block). Not a post-hoc grid.")
    pr.append("Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.")
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Gov | HO $/mo | Max DD | ≤90d | seq90 | Legal | Decision |")
    pr.append("|---|---|---:|---:|---:|---:|---|---|")
    for s in summaries:
        pr.append(
            f"| {s['book']} {s['label']} | {'ON' if s['use_gov'] else 'OFF'} | "
            f"{s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} | "
            f"{s['nseq']}/{s['wseq']} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-20/`")
    pr.append("- `run_candidate_20.py`, `ftmo-candidate-20.md`, `candidate-20-results.md`, `STATUS.md`")
    pr.append("")
    pr.append("### Live")
    pr.append("Research only — do not deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C20.md").write_text(PR_BODY.read_text())

    shutil.copy2(RUNNER, PACK / "run_candidate_20.py")

    dump = []
    for s in summaries:
        row = {k: v for k, v in s.items() if k not in ("p60",)}
        dump.append(row)
    (PACK / "candidate-20-results.json").write_text(json.dumps(dump, indent=2, default=str))

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

    summaries = []

    # 20A XAG ungoverened / governed
    for use_gov, tag in [(False, "ungov 2.50%"), (True, "gov 2.50→1.00 block@8%")]:
        print(f"Running 20A XAG Donchian {tag}...")
        trades, day_pnl, day_start, meta = run_xag_donchian(
            xag_daily, XAG_FULL, XAG_CUT, use_gov
        )
        print(
            f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}"
        )
        s = summarize(
            tag, "20A", trades, day_pnl, day_start, meta,
            XAG_FULL, XAG_CUT, use_gov, "xag", xag_end, xag_ext,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} legal={s['legal']}"
        )
        summaries.append(s)

    print("Building BTC H4B6 channel signals...")
    sig_ch = h4b6_channel_signals(btc, btc_h4)
    print(f"  channel signals: {len(sig_ch)}")
    print("Building BTC H4B6 R15 signals...")
    sig_r15 = h4b6_r15_signals(btc, btc_h4)
    print(f"  R15 signals: {len(sig_r15)}")

    # 20B BTC channel
    for use_gov, tag in [(False, "ungov ch@1.00%"), (True, "gov ch 1.00→0.40 block@8%")]:
        print(f"Running 20B BTC channel {tag}...")
        trades, day_pnl, day_start, meta = replay_btc_signals(
            sig_ch, BTC_CH_FULL, BTC_CH_CUT, use_gov, "20B"
        )
        meta["chassis"] = "btc-h4-break6-channel" + ("+gov" if use_gov else "")
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} meta={meta}")
        s = summarize(
            tag, "20B", trades, day_pnl, day_start, meta,
            BTC_CH_FULL, BTC_CH_CUT, use_gov, "btc", btc_end, btc_ext,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} legal={s['legal']}"
        )
        summaries.append(s)

    # 20C BTC R15 C17
    for use_gov, tag in [(False, "ungov R15@0.75%"), (True, "gov R15 0.75→0.30 block@8%")]:
        print(f"Running 20C BTC R15 {tag}...")
        trades, day_pnl, day_start, meta = replay_btc_signals(
            sig_r15, BTC_R15_FULL, BTC_R15_CUT, use_gov, "20C"
        )
        meta["chassis"] = "btc-h4-break6-r15-c17" + ("+gov" if use_gov else "")
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f}")
        s = summarize(
            tag, "20C", trades, day_pnl, day_start, meta,
            BTC_R15_FULL, BTC_R15_CUT, use_gov, "btc", btc_end, btc_ext,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} legal={s['legal']}"
        )
        summaries.append(s)

    lead, primary, opens = write_docs(summaries, measured, xag_end, btc_end, XAG_SHA)
    print("\n" + lead)
    print(f"Wrote {RESULTS}")
    print(f"Pack {PACK}")


if __name__ == "__main__":
    main()
