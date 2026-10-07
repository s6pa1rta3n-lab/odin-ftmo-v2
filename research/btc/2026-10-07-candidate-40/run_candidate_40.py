#!/usr/bin/env python3
"""Candidate 40: GER40 Keltner55 (entry55 mirror) + soft DD governor.

Locked a-priori (not a fishing grid):
  40A — GER40 Keltner55 @2.50% OFF
  40B — GER40 Keltner55 soft 2.50→1.25→0.75 (verdict)

Research only. No live / C4 / drip / FREEZE / MetaAPI. Do not package Gold.
Do not conflict with C38/C39 files.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import shutil

import numpy as np
import pandas as pd

PRAGUE = ZoneInfo("Europe/Prague")
ET = ZoneInfo("America/New_York")

GER40_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv"
)
GER40_SHA = "f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-40"
SPEC = OUT_DIR / "ftmo-candidate-40.md"
RESULTS = OUT_DIR / "candidate-40-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-40-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-40-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C40.md"
RUNNER = OUT_DIR / "run_candidate_40.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 1000.0
CONTRACT = 1.0  # catalogue GER40.cash
SPREAD = 2.0  # ASSUMPTION C22
COMMISSION = 0.0  # catalogue
# ASSUMPTION: GER40 EUR PnL treated 1:1 as USD for research

DAILY_KILL = -0.03
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

GOV_SOFT = 0.05
GOV_HARD = 0.08

FULL = 0.025
MID = 0.0125
FLOOR = 0.0075

TIME_DAY = 5
TP_MULT = 2.0
EMA_LEN = 20
KELTNER_MULT = 1.5
ATR_STOP_MULT = 2.0

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


def load_m1(path: Path, expected_sha: str) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"data MISSING: {path}")
    got = sha256_of(path)
    if got != expected_sha:
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


def build_ema20(closes: np.ndarray) -> np.ndarray:
    n = len(closes)
    ema = np.full(n, np.nan, dtype=float)
    if n < EMA_LEN:
        return ema
    ema[EMA_LEN - 1] = float(np.mean(closes[0:EMA_LEN]))
    alpha = 2.0 / 21.0
    for t in range(EMA_LEN, n):
        ema[t] = ema[t - 1] + alpha * (float(closes[t]) - ema[t - 1])
    return ema


def soft_gov_risk(equity: float, peak: float, full: float, mid: float, floor: float):
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return floor, "floor"
    if dd >= GOV_SOFT:
        return mid, "mid"
    return full, "full"


def size_lots(equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / (stop_dist * CONTRACT), 2)
    lots = min(lots, MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_index(side: str, entry: float, exit_px: float, lots: float) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    return raw * lots * CONTRACT - SPREAD * lots - COMMISSION * lots


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
    if day_num == TIME_DAY:
        return float(c), "TIME", "close"
    return None


def extract_keltner(daily: pd.DataFrame, symbol: str) -> tuple[list[dict], dict]:
    """Exact entry55 Keltner on daily (no sizing)."""
    opens, highs, lows, closes = [daily[c].to_numpy(float) for c in ("open", "high", "low", "close")]
    index = daily.index
    n = len(daily)
    mid = build_ema20(closes)
    atr = atr14(highs, lows, closes)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for t in range(n):
        if np.isfinite(mid[t]) and np.isfinite(atr[t]) and atr[t] > 0:
            upper[t] = mid[t] + KELTNER_MULT * atr[t]
            lower[t] = mid[t] - KELTNER_MULT * atr[t]

    signals: list[dict] = []
    pending = None
    position = None
    funnel: dict[str, int] = defaultdict(int)

    for i in range(n):
        if pending is not None:
            entry = float(opens[i])
            entry_ts = pd.Timestamp(index[i])
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.tz_localize("UTC")
            sl = ATR_STOP_MULT * float(pending["atr"])
            side = pending["side"]
            if side == "long":
                stop = entry - sl
                target = entry + TP_MULT * sl
            else:
                stop = entry + sl
                target = entry - TP_MULT * sl
            position = {
                "side": side,
                "entry": entry,
                "entry_ts": entry_ts,
                "entry_i": i,
                "stop": float(stop),
                "target": float(target),
                "sl_dist": float(sl),
            }
            pending = None

        if position is not None:
            day_num = i - position["entry_i"] + 1
            if day_num > TIME_DAY:
                raise RuntimeError("Keltner past day5")
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
            if hit:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                signals.append(
                    {
                        "symbol": symbol,
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

        kind = "no_signal"
        sig = None
        if i < 1:
            kind = "no_signal"
        elif not (
            np.isfinite(upper[i])
            and np.isfinite(lower[i])
            and np.isfinite(upper[i - 1])
            and np.isfinite(lower[i - 1])
        ):
            if i < 14 or (not np.isfinite(atr[i])) or not (float(atr[i]) > 0):
                kind = "atr"
            else:
                kind = "bands"
        else:
            long_sig = float(closes[i]) > float(upper[i]) and float(closes[i - 1]) <= float(upper[i - 1])
            short_sig = float(closes[i]) < float(lower[i]) and float(closes[i - 1]) >= float(lower[i - 1])
            if long_sig and short_sig:
                kind = "both_sides"
            elif not long_sig and not short_sig:
                kind = "no_signal"
            else:
                sig = {"side": "long" if long_sig else "short", "atr": float(atr[i])}
                kind = "signal"
                funnel["long" if long_sig else "short"] += 1

        if position is None:
            if kind == "signal":
                if i + 1 >= n:
                    funnel["no_next"] += 1
                else:
                    pending = sig
                    funnel["signals"] += 1
            else:
                funnel[kind] += 1
        elif kind == "signal":
            funnel["ignored"] += 1
        else:
            funnel[kind] += 1

    return signals, dict(funnel)


def replay_signals(signals: list[dict], book: str, use_gov: bool):
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel: dict[str, int] = defaultdict(int)
    busy_until: pd.Timestamp | None = None

    ordered = sorted(signals, key=lambda s: s["entry_ts"])

    for sig in ordered:
        if busy_until is not None and sig["entry_ts"] < busy_until:
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

        if use_gov:
            risk, gstate = soft_gov_risk(equity, peak, FULL, MID, FLOOR)
            funnel[f"gov_{gstate}"] += 1
        else:
            risk, gstate = FULL, "n/a"

        lots = size_lots(equity, risk, sig["stop_dist"])
        if lots < MIN_LOT:
            funnel["skip_lots"] += 1
            continue

        pnl = pnl_index(sig["side"], sig["entry"], sig["exit"], lots)
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
                symbol="GER40",
            )
        )
        busy_until = sig["exit_ts"]
        funnel["taken"] += 1

    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": "ger40-keltner55-2.50" + ("+softgov" if use_gov else ""),
        "taken": len(trades),
        "use_gov": use_gov,
        "full_risk": FULL,
        "mid_risk": MID,
        "floor_risk": FLOOR,
        "spread": SPREAD,
        "symbol": "GER40",
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
                if use_gov:
                    risk, _ = soft_gov_risk(eq, peak, FULL, MID, FLOOR)
                else:
                    risk = FULL
                lots = size_lots(eq, risk, tr.stop_dist)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_index(tr.side, tr.entry, tr.exit, lots)
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
            "countable": 0,
            "outside": 0,
            "best_outside_pct": None,
            "best_outside_months": None,
            "dd": 0.0,
            "final": START_EQUITY,
            "windows": [],
        }
    rows = []
    for seq, tr in enumerate(trades):
        rows.append(
            {
                "exit_ts": tr.exit_ts,
                "pnl_raw": tr.pnl,
                "reason": tr.reason,
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


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    ext_available = data_end >= EXT_START
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (GER40 feed ends 2026-09-01; no dukas-ext)"

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
    for tr in trades:
        reasons[tr.reason] += 1
        gov_counts[tr.gov_state] += 1

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

    return {
        "label": label,
        "book": book,
        "symbol": "GER40",
        "use_gov": use_gov,
        "full_risk": FULL,
        "mid_risk": MID,
        "floor_risk": FLOOR,
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
        "peak_equity": meta.get("peak_equity", START_EQUITY),
        "meta": meta,
        "explorer_xcheck": xcheck,
    }


def write_docs(summaries, measured, ger_end, ger_sha, sig_funnel):
    PACK.mkdir(parents=True, exist_ok=True)

    legal_with_90 = [s for s in summaries if s["legal"] and s["has_90"]]
    ho_ok_books = [s for s in legal_with_90 if s.get("has_90_ho")]
    # Verdict book is 40B; prefer it when ranking
    if ho_ok_books:
        ho_ok_books.sort(
            key=lambda s: (
                0 if s["book"] == "40B" else 1,
                0 if s["decision"] == "ACCEPT" else 1,
                -(s["n90_ho"] + s["nseq_ho"]),
                -s["ho_pace"],
            )
        )
        primary = ho_ok_books[0]
    elif legal_with_90:
        legal_with_90.sort(
            key=lambda s: (0 if s["book"] == "40B" else 1, -(s["n90"] + s["nseq"]), -s["ho_pace"])
        )
        primary = legal_with_90[0]
    else:
        # Prefer 40B as the stated verdict book for lead wording
        soft = [s for s in summaries if s["book"] == "40B"]
        primary = soft[0] if soft else summaries[-1]

    opens = primary["decision"] == "ACCEPT"
    if opens:
        lead = (
            f"**YES — GER40 Keltner55 opens a deployable ~3mo path** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — GER40 Keltner55 legal DD + windows, not ACCEPT** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo."
        )
    else:
        lead = (
            "**NO — GER40 Keltner55 does not open a deployable ~3mo path.** "
            "DD illegal, HO≤0, or zero ≤90d windows."
        )

    lines = []
    lines.append("# Candidate 40 Results — GER40 Keltner55 (entry55) + soft DD governor")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**GER40 data:** `{GER40_PATH}` sha256 `{ger_sha}` end `{ger_end}`")
    lines.append(f"**Signal funnel:** `{sig_funnel}`")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| GER40.cash contractSize | **1** (catalogue) |")
    lines.append("| GER40.cash commission | **0** (catalogue) |")
    lines.append("| GER40 spread | **2.0** pts (**ASSUMPTION** — feed missing; C22) |")
    lines.append("| GER40 EUR→USD | **1:1** (**ASSUMPTION** — research) |")
    lines.append("| Soft gov | dd<5% full; 5–8% half; ≥8% quarter; never sticky-block |")
    lines.append("| Prague day kill | −3% |")
    lines.append("| Chassis | entry55: EMA20 Mid ±1.5 ATR14; stop 2×ATR; TP 2R; TIME day5 |")
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|---:|---|---|---|")
    for s in summaries:
        xc = s["explorer_xcheck"]
        gov = "SOFT 2.50→1.25→0.75" if s["use_gov"] else "2.50% OFF"
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        lines.append(
            f"| {s['book']} | {gov} | {s['ho_pace']:,.0f} | "
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
        lines.append(f"- reasons={s['reasons']} gov={s['gov_counts']}")
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
    lines.append("Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-40-results.md").write_text(RESULTS.read_text())

    summary_lines = [lead, ""]
    for s in summaries:
        xc = s["explorer_xcheck"]
        summary_lines.append(
            f"{s['book']}|GER40|gov={s['use_gov']}|{s['decision']}|"
            f"pace=${s['ho_pace']:.0f}/mo|DD={s['max_dd']*100:.1f}%|"
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']})|"
            f"seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']})|"
            f"legal={s['legal']}|leave={s['leave_net']:.0f}|"
            f"xcheck_out={xc['outside_countable']}/{xc['countable']} best={xc['best_outside_pct']}"
        )
    SUMMARY_TXT.write_text("\n".join(summary_lines) + "\n")
    (PACK / "candidate-40-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 40,
        "symbol": "GER40",
        "chassis": "keltner55-entry55",
        "measured": measured,
        "lead": lead,
        "primary": primary["book"],
        "decision": primary["decision"],
        "assumptions": {
            "contract": CONTRACT,
            "spread": SPREAD,
            "commission": COMMISSION,
            "eur_usd": "1:1 ASSUMPTION",
            "soft_gov": "2.50→1.25→0.75",
        },
        "signal_funnel": sig_funnel,
        "books": [
            {
                k: (v if not isinstance(v, (np.floating, np.integer)) else float(v))
                for k, v in s.items()
                if k != "meta"
            }
            | {"meta": s["meta"]}
            for s in summaries
        ],
        "data": {"ger40_sha": ger_sha, "ger40_end": str(ger_end)},
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (PACK / "candidate-40-results.json").write_text(RESULTS_JSON.read_text())

    # STATUS: C40 on top; preserve C39 (if present) then C38 then earlier
    status = []
    sa = status.append
    sa("# BTC FTMO research baseline (2026-10-07)")
    sa("")
    sa(f"**Status: C40 GER40 Keltner55 — {primary['decision']}** — {lead}")
    sa("")
    sa("_Prior:_ preserved below (C39 / C38 / …).")
    sa("")
    sa("## Candidate 40")
    sa("")
    sa(
        "| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |"
    )
    sa("|---|---|---:|---:|---:|---:|---|---:|---|---|")
    for s in summaries:
        gov = "SOFT 2.50→1.25→0.75" if s["use_gov"] else "2.50% OFF"
        ext = "N/A" if not s["ext_available"] else f"{s['ext_net']:,.0f}"
        sa(
            f"| {s['book']} | {gov} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {ext} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    sa("")

    prior_root = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""
    # Also pull from packs if missing in root
    for cand in (39, 38, 37, 36, 35, 34, 33):
        marker = f"## Candidate {cand}"
        if marker not in prior_root:
            pack_st = OUT_DIR / f"2026-10-07-candidate-{cand}" / "STATUS.md"
            if pack_st.exists():
                prior_root = prior_root + "\n" + pack_st.read_text()
        if marker not in prior_root:
            continue
        chunk_start = prior_root.find(marker)
        rest = prior_root[chunk_start + len(marker) :]
        next_marks = []
        for m in re.finditer(r"(?m)^## (?:Candidate \d+|Live)\b", rest):
            next_marks.append(m.start())
        chunk_end = chunk_start + len(marker) + (next_marks[0] if next_marks else len(rest))
        sa(prior_root[chunk_start:chunk_end].rstrip())
        sa("")

    sa("## Live")
    sa(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C40 arms without Odin approval. Gold not packaged."
    )
    sa("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pa = pr.append
    pa("## Candidate 40 — GER40 Keltner55 (entry55 mirror) + soft DD governor")
    pa("")
    pa(
        "Research only. Broad Odin mandate. Fresh single-book GER40 Keltner "
        "(C22 Donchian REJECT; C26 three-close REJECT; C31 used JPN225 Keltner in a joint). "
        "**No deploy.** Live C4 untouched."
    )
    pa("")
    pa(f"**Primary verdict: `{primary['decision']}`** via {primary['book']}")
    pa("")
    pa(lead)
    pa("")
    pa("### Scoreboard")
    pa("")
    pa("| Book | Decision | HO $/mo | Max DD | ≤90d HO | seq HO | Leave-out | Explorer out |")
    pa("|---|---|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        xc = s["explorer_xcheck"]
        pa(
            f"| {s['book']} | {s['decision']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90_ho']} | {s['nseq_ho']} | {s['leave_net']:,.0f} | {xc['outside_countable']} |"
        )
    pa("")
    pa("### ASSUMPTIONS")
    pa("- GER40.cash: contractSize=1, commission=0 (catalogue); spread **2.0 ASSUMPTION** (C22)")
    pa("- EUR→USD **1:1 ASSUMPTION** (research)")
    pa("- Soft gov: dd<5% full / 5–8% half / ≥8% quarter; Prague −3% kill; never sticky")
    pa("- Chassis: entry55 Mid=EMA20 ±1.5×ATR14; stop 2×ATR; TP 2R; TIME day5; risk 2.50%")
    pa("")
    pa("### Paths")
    pa("- Spec: `research/btc/2026-10-07-candidate-40/ftmo-candidate-40.md`")
    pa("- Runner: `research/btc/2026-10-07-candidate-40/run_candidate_40.py`")
    pa("- Results: `research/btc/2026-10-07-candidate-40/candidate-40-results.md`")
    pa("")
    pa("Research only. Live C4 + drip freeze + MetaAPI untouched. Do not package Gold. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C40.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-40.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_40.py")

    print(lead)
    for s in summaries:
        xc = s["explorer_xcheck"]
        print(
            f"  {s['book']}: {s['decision']} DD={s['max_dd']*100:.1f}% pace=${s['ho_pace']:.0f}/mo "
            f"90HO={s['n90_ho']} seqHO={s['nseq_ho']} xcheck_out={xc['outside_countable']} "
            f"best={xc['best_outside_pct']}"
        )
    return primary, lead


def main():
    print("Loading GER40 M1...")
    ger = load_m1(GER40_PATH, GER40_SHA)
    ger_end = ger.index[-1]
    ger_sha = GER40_SHA
    print(f"  GER40 M1: {len(ger)} → {ger_end}")

    daily = build_daily(ger)
    print(f"  GER40 D1: {len(daily)}")

    print("Extracting GER40 Keltner55 signals (entry55)...")
    sigs, funnel = extract_keltner(daily, "GER40")
    print(f"  signals={len(sigs)} funnel={funnel}")

    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    summaries = []

    print("Running 40A GER40 Keltner @2.50% OFF...")
    t, dp, ds, meta = replay_signals(sigs, "40A", use_gov=False)
    summaries.append(
        summarize("40A GER40 Keltner55 @2.50% OFF", "40A", t, dp, ds, meta, False, ger_end)
    )

    print("Running 40B GER40 Keltner soft gov (verdict)...")
    t, dp, ds, meta = replay_signals(sigs, "40B", use_gov=True)
    summaries.append(
        summarize("40B GER40 Keltner55 + soft gov (verdict)", "40B", t, dp, ds, meta, True, ger_end)
    )

    write_docs(summaries, measured, ger_end, ger_sha, funnel)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
