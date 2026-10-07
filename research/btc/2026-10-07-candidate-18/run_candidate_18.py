#!/usr/bin/env python3
"""Candidate 18: ETHUSD denser-pace hunt (multi-crypto FTMO research under BTC Strategies).

Two locked a-priori books only — not a fishing grid.
  18A — ETH H4 Bollinger squeeze (port of BTC C15)
  18B — ETH 20-day Donchian dual @ 2.60% risk (Gold Donchian structure)

Research only. No live VM / MetaAPI / C4 / drip / FREEZE.
Do not package Gold as primary. Do not invent US100.
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

ETH_MAIN = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/ethusd-m1-bid-2024-01-01-2026-09-02.csv"
)
EXPECTED_SHA = "bc3bf16554976b31350b5449503da50f24565c08b73bf12d035c0df21215d770"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-18"
SPEC = OUT_DIR / "ftmo-candidate-18.md"
RESULTS = OUT_DIR / "candidate-18-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-18-summary.txt"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C18.md"
RUNNER = OUT_DIR / "run_candidate_18.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 50.0
# FTMO ETHUSD catalogue: contractSize=10. Spread missing from feed → ASSUMPTION.
CONTRACT_SIZE = 10.0
SPREAD = 1.50  # ASSUMPTION price units (C15 HF analog; BTC uses 15 on contract 1)
COMMISSION_PER_LOT = 0.0  # ASSUMPTION — C15 HF / Gold-style without inventing % commission path
DAILY_KILL = -0.03  # Prague −3% kill (18A); also used as soft kill
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

# C15 BB params
BB_PERIOD = 20
BB_K = 2.0
BW_LOOKBACK = 100
BW_PCT = 10.0
ATR_MULT_A = 1.0
R_MULT_A = 2.0

# Donchian params
DONCH_N = 20
ATR_MULT_B = 2.0
R_MULT_B = 3.0  # target = 3R where R = stop = 2×ATR → target dist = 3 * 2ATR = 6ATR? 
# Gold: sl_dist = 2*ATR; target = entry ± 3.0 * sl_dist → 3R. Yes.
RISK_B = 0.026
MAX_HOLD_DAYS = 10  # Gold harness TIME exit

HO_START = pd.Timestamp("2025-11-08 00:00:00+00:00")
HO_END = pd.Timestamp("2026-09-01 23:59:59+00:00")
EXT_START = pd.Timestamp("2026-09-02 00:00:00+00:00")
FIT_START = pd.Timestamp("2024-01-01 00:00:00+00:00")
FIT_END = pd.Timestamp("2025-11-07 23:59:59+00:00")

# BTC C15 residual reference (from C17)
C15_HO_PACE = 1291.0
C15_DD = 0.074
RESIDUAL_TARGET = 3709.0


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


def et_month(ts: pd.Timestamp) -> str:
    d = ts.tz_convert(ET).date()
    return f"{d.year:04d}-{d.month:02d}"


def load_eth_m1() -> pd.DataFrame:
    if not ETH_MAIN.exists():
        raise SystemExit(f"ETH data MISSING: {ETH_MAIN}")
    got = sha256_of(ETH_MAIN)
    if got != EXPECTED_SHA:
        raise SystemExit(f"ETH sha mismatch: got {got} expected {EXPECTED_SHA}")
    df = pd.read_csv(ETH_MAIN)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    m1 = df[["open", "high", "low", "close"]].astype(float)
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
    # UTC daily, left-labeled — clean, no lookahead. Gold harness uses similar M1→D1.
    bars = m1.resample("1D", label="left", closed="left", origin=ORIGIN).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    # Drop incomplete last calendar day if M1 ends mid-day (last day is complete through 23:59)
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
        atr[i] = round(float(csum[i] - csum[i - 14]) / 14.0, 6)
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


def size_lots(equity: float, risk: float, stop_dist: float) -> float:
    """lots = round(risk_dollars / (stop_dist * contract_size), 2)."""
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / (stop_dist * CONTRACT_SIZE), 2)
    lots = min(lots, MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_dollars(side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    units = lots * CONTRACT_SIZE
    return raw * units - SPREAD * units - COMMISSION_PER_LOT * lots


def run_18a(m1: pd.DataFrame, h4: pd.DataFrame, risk: float):
    high = h4["high"].to_numpy()
    low = h4["low"].to_numpy()
    close = h4["close"].to_numpy()
    atr = atr14(high, low, close)
    _mid, upper, lower, bw = bollinger_bw(close)
    sq_flag, p10 = squeeze_flags(bw)

    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_index = m1.index
    n_m1 = len(m1)
    ends = h4.index + pd.Timedelta(hours=4)
    end_locs = np.asarray(m1_index.searchsorted(ends, side="left"), dtype=np.int64)

    equity = START_EQUITY
    trades: list[Trade] = []
    in_trade_until = -1
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    signals = taken = 0
    skip = defaultdict(int)

    for t in range(1, len(h4)):
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            skip["atr"] += 1
            continue
        if not np.isfinite(upper[t]) or not np.isfinite(lower[t]) or not np.isfinite(bw[t]):
            skip["bb"] += 1
            continue
        if not np.isfinite(p10[t - 1]):
            skip["bb"] += 1
            continue
        if not sq_flag[t - 1]:
            continue
        if close[t] > upper[t]:
            side = "long"
        elif close[t] < lower[t]:
            side = "short"
        else:
            continue
        signals += 1

        entry_i = int(end_locs[t])
        if entry_i >= n_m1:
            continue
        if entry_i <= in_trade_until:
            skip["in_trade"] += 1
            continue

        entry_ts = m1_index[entry_i]
        entry_px = float(m1_open[entry_i])
        pd_entry = prague_day(entry_ts)
        if pd_entry in killed_days:
            skip["kill"] += 1
            continue
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if day_pnl[pd_entry] / day_start_eq[pd_entry] <= DAILY_KILL:
            killed_days.add(pd_entry)
            skip["kill"] += 1
            continue

        stop_dist = ATR_MULT_A * float(atr[t])
        if stop_dist <= 0:
            skip["atr"] += 1
            continue
        target_dist = R_MULT_A * stop_dist
        if side == "long":
            stop = entry_px - stop_dist
            target = entry_px + target_dist
            if entry_px <= stop:
                skip["stop"] += 1
                continue
        else:
            stop = entry_px + stop_dist
            target = entry_px - target_dist
            if entry_px >= stop:
                skip["stop"] += 1
                continue

        lots = size_lots(equity, risk, stop_dist)
        if lots < MIN_LOT:
            skip["lots"] += 1
            continue

        exit_i = exit_px = reason = None
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

        pnl = pnl_dollars(side, entry_px, float(exit_px), lots)
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
                exit=float(exit_px),
                reason=reason,
                lots=lots,
                stop_dist=stop_dist,
                pnl=pnl,
                equity_after=equity,
                book="18A",
            )
        )
        in_trade_until = exit_i

    meta = {
        "signals": signals,
        "taken": taken,
        "skip": dict(skip),
        "final_equity": equity,
        "killed_days": len(killed_days),
        "n_h4": len(h4),
        "n_squeeze": int(sq_flag.sum()),
        "chassis": "eth-h4-bb-squeeze",
    }
    return trades, day_pnl, day_start_eq, meta


def resolve_daily_bar(side: str, o, h, l, c, stop, target, day_num: int):
    """Gold Donchian daily exit walk."""
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


def run_18b(daily: pd.DataFrame, risk: float = RISK_B):
    opens = daily["open"].to_numpy(dtype=float)
    highs = daily["high"].to_numpy(dtype=float)
    lows = daily["low"].to_numpy(dtype=float)
    closes = daily["close"].to_numpy(dtype=float)
    index = daily.index
    atr = atr14(highs, lows, closes)
    n = len(daily)

    equity = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    pending = None
    position = None
    funnel = defaultdict(int)
    unfinished = 0

    for i in range(n):
        # Fill pending at today's open
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
                    sl_dist = ATR_MULT_B * float(pending["atr"])
                    lots = size_lots(equity, risk, sl_dist)
                    if lots < MIN_LOT or sl_dist <= 0:
                        funnel["skip_lots"] += 1
                        pending = None
                    else:
                        side = pending["side"]
                        if side == "long":
                            stop = entry - sl_dist
                            target = entry + R_MULT_B * sl_dist
                        else:
                            stop = entry + sl_dist
                            target = entry - R_MULT_B * sl_dist
                        position = {
                            "side": side,
                            "entry": entry,
                            "entry_ts": entry_ts,
                            "entry_i": i,
                            "stop": stop,
                            "target": target,
                            "sl_dist": sl_dist,
                            "lots": lots,
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
                if when == "open":
                    exit_ts = bar_ts
                else:
                    # close ≈ next day open info-time like Gold (+1D)
                    exit_ts = bar_ts + pd.Timedelta(days=1)
                pnl = pnl_dollars(position["side"], position["entry"], float(fill), position["lots"])
                equity += pnl
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
                        book="18B",
                    )
                )
                position = None

        # New signal only if flat
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
        "killed_days": len(killed_days),
        "n_daily": n,
        "unfinished": unfinished,
        "chassis": "eth-donchian-20d-dual",
        "taken": len(trades),
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


def count_sequential_reset(trades: list[Trade], risk: float, window_days: int = 90):
    """Challenge +10% then RESET to 100k for Verification +5%, total ≤ window_days."""
    if not trades:
        return 0, 0, []
    # Build signal-like list from trades (already sized path — re-simulate from raw R)
    # Use stored entry/exit/stop_dist/side; re-size at each stage equity.
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
                lots = size_lots(eq, risk, tr.stop_dist)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_dollars(tr.side, tr.entry, tr.exit, lots)
                eq += pnl
                pd_x = prague_day(tr.exit_ts)
                if pd_x > hard_end:
                    return None, eq, True  # exit outside
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
        # Verification resets to 100k, starts day after challenge done
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


def summarize(label, book, trades, day_pnl, day_start_eq, meta, risk, data_end):
    # Ext availability
    ext_available = data_end >= EXT_START
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (ETH feed ends 2026-09-01; no dukas-ext)"

    leave_drop, leave_net = leave_out_two_best_ho(trades)
    max_dd = max_realized_dd(trades)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail = days_at_or_below(day_pnl, day_start_eq, DAY_FAIL)

    ho_days = (HO_END.normalize() - HO_START).days + 1
    ho_mo = ho_days / 30.44
    ho_pace = ho_net / ho_mo if ho_mo > 0 else 0.0

    n60, w60, p60 = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)
    nseq, wseq, pseq = count_sequential_reset(trades, risk, 90)

    wins = sum(1 for tr in trades if tr.pnl > 0)
    losses = sum(1 for tr in trades if tr.pnl <= 0)
    longs = sum(1 for tr in trades if tr.side == "long")
    shorts = sum(1 for tr in trades if tr.side == "short")
    reasons: dict[str, int] = defaultdict(int)
    for tr in trades:
        reasons[tr.reason] += 1

    legal = max_dd <= 0.10 and n_fail == 0 and worst_pct > DAY_FAIL
    leave_ok = leave_net > 0
    # Ext gate: if unavailable, do not count as Ext≥0 pass for ACCEPT
    ext_ok = ext_available and ext_net >= 0
    ho_ok = ho_net > 0
    fit_ok = fit_net >= -10_000

    # ACCEPT: ≥1 legal ≤90d both-stages window + Ext≥0 + leave-out OK + legal DD
    has_90 = n90 >= 1 or nseq >= 1
    if legal and has_90 and ext_ok and leave_ok and ho_ok:
        decision = "ACCEPT"
    elif legal and ho_pace >= 3000 and leave_ok and ho_ok:
        decision = "CONDITIONAL"  # Ext weak/unavailable labeled
    elif legal and ho_ok and leave_ok:
        decision = "NEAR-MISS"
    else:
        decision = "REJECT"

    residual_needed = None
    dd_headroom = None
    if legal:
        residual_needed = max(0.0, RESIDUAL_TARGET - ho_pace) if book.startswith("18") else None
        # if ETH is residual sleeve beside C15: need 3709 - wait, residual IS what we need FROM eth
        # Joint: C15@0.75 provides 1291; ETH provides ho_pace; still need max(0, 5000 - 1291 - eth)
        # Task: "if 18A or 18B is legal, what $/mo remains needed beside BTC C15@0.75%"
        still_need = max(0.0, (C15_HO_PACE + RESIDUAL_TARGET) - C15_HO_PACE - ho_pace)
        # = max(0, 5000 - 1291 - eth) = max(0, 3709 - eth)
        still_need = max(0.0, RESIDUAL_TARGET - ho_pace)
        residual_needed = still_need
        dd_headroom = max(0.0, 0.10 - max_dd)
        # shared with C15: headroom after both = 0.10 - C15_DD - eth_dd (rough, uncorrelated ASSUMPTION)
        joint_dd_left = max(0.0, 0.10 - C15_DD - max_dd)

    return {
        "label": label,
        "book": book,
        "risk": risk,
        "decision": decision,
        "legal": legal,
        "ho_net": ho_net,
        "ho_pace": ho_pace,
        "fit_net": fit_net,
        "leave_net": leave_net,
        "leave_drop": leave_drop,
        "ext_net": ext_net,
        "ext_status": ext_status,
        "ext_ok": ext_ok,
        "leave_ok": leave_ok,
        "ho_ok": ho_ok,
        "fit_ok": fit_ok,
        "max_dd": max_dd,
        "worst_d": worst_d,
        "worst_pct": worst_pct,
        "n_fail": n_fail,
        "n60": n60,
        "w60": w60,
        "p60": p60,
        "n90": n90,
        "w90": w90,
        "p90": p90,
        "nseq": nseq,
        "wseq": wseq,
        "pseq": pseq,
        "n_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "longs": longs,
        "shorts": shorts,
        "reasons": dict(reasons),
        "final_equity": meta["final_equity"],
        "full_net": meta["final_equity"] - START_EQUITY,
        "meta": meta,
        "residual_needed": residual_needed,
        "dd_headroom": dd_headroom if legal else None,
        "joint_dd_left_vs_c15": (max(0.0, 0.10 - C15_DD - max_dd) if legal else None),
    }


def fmt_money(x):
    return f"${x:,.0f}"


def write_docs(summaries, measured, data_end, eth_sha):
    PACK.mkdir(parents=True, exist_ok=True)

    # Pick primary headline: best legal by pace, else best overall
    legal_ones = [s for s in summaries if s["legal"]]
    if legal_ones:
        primary = max(legal_ones, key=lambda s: s["ho_pace"])
    else:
        primary = max(summaries, key=lambda s: s["ho_pace"])

    opens_path = any(s["decision"] == "ACCEPT" for s in summaries)
    conditional = any(s["decision"] == "CONDITIONAL" for s in summaries)

    if opens_path:
        lead = (
            f"**YES — ETH opens a measured 1–3mo pass path** via {primary['book']} "
            f"({primary['decision']})."
        )
    elif conditional:
        lead = (
            f"**CONDITIONAL — ETH shows legal high pace** via {primary['book']} "
            f"(~${primary['ho_pace']:,.0f}/mo) but Ext {primary['ext_status']}."
        )
    elif primary["legal"] and primary["ho_pace"] > 0:
        lead = (
            f"**NO cleared ACCEPT — ETH {primary['book']} is DD-legal at "
            f"~${primary['ho_pace']:,.0f}/mo but too slow / no ≤90d windows "
            f"(Ext {primary['ext_status']})."
        )
    else:
        lead = (
            "**NO — ETH Candidate 18 does not open a 1–3mo pass path** on the two locked books."
        )

    # Results md
    lines = []
    lines.append("# Candidate 18 Results — ETHUSD denser-pace hunt")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**Measured:** {measured}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**ETH data:** `{ETH_MAIN}` sha256 `{eth_sha}`")
    lines.append(f"**Data range:** 2024-01-01 → {data_end} (no ETH dukas-ext)")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step |")
    lines.append("| Challenge / Verification | +10% / +5% (1.10 then 1.155 continuous; seq reset 1.10 then 1.05) |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| ETH contract_size | **10** (FTMO catalogue) |")
    lines.append("| ETH spread | **1.50** price units × units (ASSUMPTION — feed has no typical_spread; C15 HF analog; BTC uses 15 @ contract 1) |")
    lines.append("| Commission / swap | **0** / **0** (ASSUMPTION — C15 HF parity; catalogue percent commission not applied) |")
    lines.append("| Ext | UNAVAILABLE if feed ends before 2026-09-02 |")
    lines.append("| Books | Two locked a-priori only — not a grid |")
    lines.append("| Gold packaging | Forbidden (Gold Strategy veto) |")
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 | Legal | Decision |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for s in summaries:
        ext_cell = (
            f"{s['ext_net']:+,.0f}"
            if s["ext_status"].startswith("measured")
            else "N/A"
        )
        lines.append(
            f"| {s['book']} {s['label']} | {s['risk']*100:.2f}% | "
            f"{s['ho_pace']:,.0f} | {s['fit_net']:+,.0f} | {s['leave_net']:+,.0f} | "
            f"{ext_cell} | {s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | "
            f"{s['n60']}/{s['w60']} | {s['n90']}/{s['w90']} | {s['nseq']}/{s['wseq']} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    lines.append("")

    for s in summaries:
        lines.append(f"## {s['book']} — {s['label']}")
        lines.append("")
        lines.append(f"**Decision: {s['decision']}**")
        lines.append("")
        lines.append(f"- Chassis: `{s['meta'].get('chassis')}`")
        lines.append(
            f"- Trades: n={s['n_trades']} L/S={s['longs']}/{s['shorts']} "
            f"WR={s['wins']/s['n_trades']*100 if s['n_trades'] else 0:.1f}% "
            f"reasons={s['reasons']}"
        )
        lines.append(
            f"- HO ${s['ho_net']:,.2f} (~${s['ho_pace']:,.2f}/mo); "
            f"Fit ${s['fit_net']:,.2f}; Leave-out ${s['leave_net']:,.2f} "
            f"(drop {s['leave_drop']}); Ext {s['ext_status']} "
            f"{'' if not s['ext_status'].startswith('measured') else f'(${s['ext_net']:,.2f})'}"
        )
        lines.append(
            f"- Max DD {s['max_dd']*100:.2f}%; worst Prague day {s['worst_d']} "
            f"{s['worst_pct']*100:.2f}%; fail-days={s['n_fail']}; Legal={'YES' if s['legal'] else 'NO'}"
        )
        lines.append(
            f"- Windows: ≤60d {s['n60']}/{s['w60']}; ≤90d cont {s['n90']}/{s['w90']}; "
            f"seq90 reset {s['nseq']}/{s['wseq']}"
        )
        lines.append(f"- Final equity ${s['final_equity']:,.2f} (net ${s['full_net']:,.2f})")
        if s["legal"]:
            lines.append(
                f"- **Joint residual vs BTC C15@0.75% ($1,291/mo, DD 7.4%):** "
                f"still need **${s['residual_needed']:,.0f}/mo** from ETH "
                f"(or other) to hit ~$5k/mo combined; ETH alone DD headroom "
                f"{s['dd_headroom']*100:.1f}%; rough joint leftover after stacking "
                f"C15+ETH DDs (uncorrelated ASSUMPTION) = {s['joint_dd_left_vs_c15']*100:.1f}%"
            )
        if s["p90"]:
            lines.append("")
            lines.append("### ≤90d continuous pass sample")
            lines.append("| Start | End | Start eq | Max mult | Min mult | Worst day |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for p in s["p90"]:
                lines.append(
                    f"| {p['start']} | {p['end']} | ${p['start_eq']:,.0f} | "
                    f"{p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']*100:.2f}% |"
                )
        if s["pseq"]:
            lines.append("")
            lines.append("### seq90 reset pass sample")
            lines.append("| Start | Challenge done | Verification done | Total days |")
            lines.append("|---|---|---|---:|")
            for p in s["pseq"]:
                lines.append(
                    f"| {p['start']} | {p['challenge_done']} | {p['verification_done']} | {p['total_days']} |"
                )
        lines.append("")
        lines.append(f"Meta: `{json.dumps(s['meta'], default=str)[:500]}`")
        lines.append("")

    lines.append("## Joint residual (mandate math)")
    lines.append("")
    lines.append(
        "BTC C15@0.75% contributes ~$1,291/mo at 7.4% DD. Need ~$5,000/mo for +$15k/90d → "
        "residual ≥$3,709/mo from a second book inside leftover ~2.6% DD."
    )
    lines.append("")
    for s in summaries:
        if s["legal"]:
            fills = s["ho_pace"] >= RESIDUAL_TARGET
            lines.append(
                f"- {s['book']}@{s['risk']*100:.2f}%: ${s['ho_pace']:,.0f}/mo, "
                f"DD {s['max_dd']*100:.1f}%, still-need ${s['residual_needed']:,.0f}/mo, "
                f"{'FILLS residual alone' if fills else 'does NOT fill residual alone'}."
            )
        else:
            lines.append(
                f"- {s['book']}@{s['risk']*100:.2f}%: illegal or unusable for residual "
                f"(DD {s['max_dd']*100:.1f}%, pace ${s['ho_pace']:,.0f}/mo)."
            )
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.")
    lines.append("Gold not packaged as primary. US100 not invented.")
    lines.append("")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-18-results.md").write_text(RESULTS.read_text())

    # Spec
    spec = []
    spec.append("# FTMO Candidate 18 — ETHUSD denser-pace hunt")
    spec.append("")
    spec.append("Research-only multi-crypto book under BTC Strategies lane.")
    spec.append("Two locked a-priori ETH books. Not a fishing grid. No deploy.")
    spec.append("")
    spec.append("## Book 18A — ETH H4 BB squeeze (BTC C15 port)")
    spec.append("")
    spec.append("- H4 Bollinger(20, 2σ); squeeze = bw ≤ P10 of prior 100 bw")
    spec.append("- Break: prior bar in squeeze AND close outside band")
    spec.append("- Stop 1×ATR14; target R=2; max 1 pos")
    spec.append("- Risk 0.75% (also 0.50%, 1.00%); Prague −3% day kill")
    spec.append("- Cost: C15 HF analog — spread 1.50 × units, commission 0, contract_size 10")
    spec.append("")
    spec.append("## Book 18B — ETH 20-day Donchian dual @ 2.60%")
    spec.append("")
    spec.append("- Daily UTC bars from M1; 20-day channel (prior bars only)")
    spec.append("- Both sides; entry next open; stop 2×ATR; target 3R; TIME day-10")
    spec.append("- Risk **2.60%**; Prague day DD/worst-day rules")
    spec.append("- Cost: Gold daily formula with ETH contract_size 10, spread 1.50, commission 0")
    spec.append("")
    spec.append("## Periods")
    spec.append("")
    spec.append("| Slice | Range |")
    spec.append("|---|---|")
    spec.append("| Fit | 2024-01-01 → 2025-11-07 |")
    spec.append("| HO | 2025-11-08 → 2026-09-01 |")
    spec.append("| Ext | 2026-09-02 → data end (UNAVAILABLE on this feed) |")
    spec.append("")
    spec.append("## Gates")
    spec.append("")
    spec.append("- ACCEPT: ≥1 legal ≤90d both-stages window + Ext≥0 + leave-out OK")
    spec.append("- CONDITIONAL: legal DD + HO pace ≥$3,000/mo (label Ext)")
    spec.append("")
    SPEC.write_text("\n".join(spec) + "\n")
    (PACK / "ftmo-candidate-18.md").write_text(SPEC.read_text())

    # Summary one-liner
    SUMMARY_TXT.write_text(
        f"{lead}\n"
        + "\n".join(
            f"{s['book']}@{s['risk']*100:.2f}% {s['decision']} pace=${s['ho_pace']:.0f}/mo "
            f"DD={s['max_dd']*100:.1f}% 90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} "
            f"legal={s['legal']}"
            for s in summaries
        )
        + "\n"
    )
    (PACK / "candidate-18-summary.txt").write_text(SUMMARY_TXT.read_text())

    # STATUS
    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C18 ETH denser-pace — {primary['decision']}** — {lead}")
    status.append("")
    status.append("## Candidate 18 (ETHUSD)")
    status.append("")
    status.append(
        "| Book | Risk | HO $/mo | Max DD | ≤90d | seq90 | Ext | Legal | Decision |"
    )
    status.append("|---|---:|---:|---:|---:|---:|---|---|---|")
    for s in summaries:
        ext_cell = (
            f"{s['ext_net']:+,.0f}"
            if s["ext_status"].startswith("measured")
            else "N/A"
        )
        status.append(
            f"| {s['book']} | {s['risk']*100:.2f}% | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} | {s['nseq']}/{s['wseq']} | "
            f"{ext_cell} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    status.append("## Prior residual (C17)")
    status.append(
        "BTC C15@0.75% $1,291/mo DD 7.4% → need ≥$3,709/mo residual. "
        "US100 best legal ~$432/mo cannot fill. Gold not packaged as primary."
    )
    status.append("")
    status.append("## Live")
    status.append("Catalogue drip / C4 ops: **untouched**. Nothing from C18 arms without Odin approval.")
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    # PR body
    pr = []
    pr.append("## Candidate 18 — ETHUSD denser-pace hunt (research)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append("Two locked a-priori ETH books under BTC Strategies multi-crypto lane.")
    pr.append("Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged as primary.")
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Risk | HO $/mo | Max DD | ≤90d | seq90 | Legal | Decision |")
    pr.append("|---|---:|---:|---:|---:|---:|---|---|")
    for s in summaries:
        pr.append(
            f"| {s['book']} {s['label']} | {s['risk']*100:.2f}% | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} | {s['nseq']}/{s['wseq']} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-18/`")
    pr.append("- `run_candidate_18.py`, `ftmo-candidate-18.md`, `candidate-18-results.md`, `STATUS.md`")
    pr.append("")
    pr.append("### Live")
    pr.append("Research only — do not deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C18.md").write_text(PR_BODY.read_text())

    # Copy runner
    shutil.copy2(RUNNER, PACK / "run_candidate_18.py")

    # JSON dump for audit
    dump = []
    for s in summaries:
        dump.append({k: (v.isoformat() if isinstance(v, date) else v) for k, v in s.items() if k not in ("p60", "meta")})
        dump[-1]["p90"] = s["p90"]
        dump[-1]["pseq"] = s["pseq"]
        dump[-1]["meta"] = s["meta"]
    (PACK / "candidate-18-results.json").write_text(json.dumps(dump, indent=2, default=str))

    return lead, primary, opens_path, conditional


def main():
    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("Loading ETH M1...")
    m1 = load_eth_m1()
    eth_sha = EXPECTED_SHA
    data_end = m1.index[-1]
    print(f"  M1 bars: {len(m1)}  {m1.index[0]} → {data_end}")

    h4 = build_h4(m1)
    print(f"  H4 bars: {len(h4)}  {h4.index[0]} → {h4.index[-1]}")
    daily = build_daily(m1)
    print(f"  D1 bars: {len(daily)}  {daily.index[0]} → {daily.index[-1]}")

    summaries = []

    # 18A at three risks
    for risk, label in [(0.0075, "0.75% locked"), (0.005, "0.50%"), (0.01, "1.00%")]:
        print(f"Running 18A @ {risk*100:.2f}% ...")
        trades, day_pnl, day_start, meta = run_18a(m1, h4, risk)
        print(
            f"  trades={len(trades)} final_eq={meta['final_equity']:.2f} "
            f"signals={meta['signals']} squeeze={meta['n_squeeze']}"
        )
        s = summarize(label, "18A", trades, day_pnl, day_start, meta, risk, data_end)
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} legal={s['legal']}"
        )
        summaries.append(s)

    # 18B locked 2.60%
    print("Running 18B Donchian @ 2.60% ...")
    trades, day_pnl, day_start, meta = run_18b(daily, RISK_B)
    print(
        f"  trades={len(trades)} final_eq={meta['final_equity']:.2f} "
        f"funnel={meta['funnel']}"
    )
    s = summarize("2.60% locked", "18B", trades, day_pnl, day_start, meta, RISK_B, data_end)
    print(
        f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
        f"90d={s['n90']}/{s['w90']} seq={s['nseq']}/{s['wseq']} legal={s['legal']}"
    )
    summaries.append(s)

    lead, primary, opens, cond = write_docs(summaries, measured, data_end, eth_sha)
    print("\n" + lead)
    print(f"Wrote {RESULTS}")
    print(f"Pack {PACK}")


if __name__ == "__main__":
    main()
