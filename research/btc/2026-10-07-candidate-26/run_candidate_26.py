#!/usr/bin/env python3
"""Candidate 26: GER40 three-close momentum (Gold entry5 port) + soft DD governor.

Research only. Broad Odin mandate. Explorer suggested GER40 three-close near-miss.
Mirror entry5 mechanics on GER40 — C22 was GER40 Donchian; C24 was XAG three-close.
26A @2.50% primary; 26B soft gov a-priori; 2.60% sensitivity NOT verdict.
No live VM / MetaAPI / C4 / drip / FREEZE. Do not package Gold.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import calendar
import hashlib
import heapq
import importlib.util
import json
import shutil
import sys
import types

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

GER40_FEED = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv"
)
EXPECTED_SHA = "f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d"
ENTRY5_PREREG = Path("/workspace/gold-strategy/entry5-preregister-2026-10-03.md")
ENTRY5_PREREG_SHA = "6a76bfa6867839b761ff7bf86be104fd533d600925faf306a587a8b37fb48282"
SPEC_PATH = Path("/workspace/btc-strategies/ftmo-candidate-26.md")

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-26"
RESULTS = OUT_DIR / "candidate-26-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-26-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-26-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C26.md"
RUNNER = OUT_DIR / "run_candidate_26.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 100.0
CONTRACT_SIZE = 1.0  # FTMO GER40.cash catalogue
SPREAD = 2.0  # ASSUMPTION — C22; feed missing
COMMISSION_PER_LOT = 0.0  # catalogue

RISK_OFFICIAL = 0.025
RISK_SENSITIVITY = 0.026
RISK_MID = 0.0125
RISK_FLOOR = 0.0075
GOV_SOFT = 0.05
GOV_HARD = 0.08
DAILY_KILL = -0.03  # Prague day kill — no new entries

TIME_DAY = 5
TP_MULT = 2.0
ATR_MULT = 2.0

DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90

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
    atr: float
    signal_ts: pd.Timestamp
    risk_used: float = 0.025
    gov_state: str = "n/a"


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


def _install_metaapi_stub() -> None:
    if "metaapi_cloud_sdk" in sys.modules:
        return

    class MetaApi:
        def __init__(self, *a, **k):
            pass

    class SynchronizationListener:
        def __init__(self, *a, **k):
            pass

    class TimeoutException(Exception):
        pass

    sdk = types.ModuleType("metaapi_cloud_sdk")
    sdk.MetaApi = MetaApi
    clients = types.ModuleType("metaapi_cloud_sdk.clients")
    metaapi = types.ModuleType("metaapi_cloud_sdk.clients.metaapi")
    syn = types.ModuleType("metaapi_cloud_sdk.clients.metaapi.synchronization_listener")
    syn.SynchronizationListener = SynchronizationListener
    timeout_mod = types.ModuleType("metaapi_cloud_sdk.clients.timeout_exception")
    timeout_mod.TimeoutException = TimeoutException
    sdk.clients = clients
    clients.metaapi = metaapi
    metaapi.synchronization_listener = syn
    clients.timeout_exception = timeout_mod
    sys.modules["metaapi_cloud_sdk"] = sdk
    sys.modules["metaapi_cloud_sdk.clients"] = clients
    sys.modules["metaapi_cloud_sdk.clients.metaapi"] = metaapi
    sys.modules["metaapi_cloud_sdk.clients.metaapi.synchronization_listener"] = syn
    sys.modules["metaapi_cloud_sdk.clients.timeout_exception"] = timeout_mod


def load_harness():
    _install_metaapi_stub()
    sys.path.insert(0, "/workspace/odin-ftmo-v2")
    _HARNESS_PATH = Path("/workspace/strategy-explorer/pr36/backtest_2026_10_02_live_rules.py")
    _spec = importlib.util.spec_from_file_location("backtest_2026_10_02_live_rules", _HARNESS_PATH)
    H = importlib.util.module_from_spec(_spec)
    sys.modules["backtest_2026_10_02_live_rules"] = H
    _spec.loader.exec_module(H)
    from griff_engine_live import compute_atr_14, compute_true_range

    assert compute_atr_14.__globals__["compute_true_range"] is compute_true_range
    return H, compute_atr_14


def resolve_bar(direction, o, h, l, c, stop, target, day_num):
    """Same priority as entry5 / Donchian resolve_bar; TIME at day 5."""
    if direction == "BUY":
        if o <= stop:
            return (float(o), "SL_OPEN", "open")
        if l <= stop and h >= target:
            return (float(stop), "SL_BOTH", "close")
        if l <= stop:
            return (float(stop), "SL", "close")
        if h >= target:
            return (float(target), "TP", "close")
    else:
        if o >= stop:
            return (float(o), "SL_OPEN", "open")
        if h >= stop and l <= target:
            return (float(stop), "SL_BOTH", "close")
        if h >= stop:
            return (float(stop), "SL", "close")
        if l <= target:
            return (float(target), "TP", "close")
    if day_num == TIME_DAY:
        return (float(c), "TIME", "close")
    return None


def soft_gov_risk(equity: float, peak: float, full: float, mid: float, floor: float):
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return floor, "floor"
    if dd >= GOV_SOFT:
        return mid, "mid"
    return full, "full"


def _atr_as_of(compute_atr_14, highs, lows, closes, i: int) -> float:
    window = [
        {"high": float(highs[j]), "low": float(lows[j]), "close": float(closes[j])}
        for j in range(i - 14, i + 1)
    ]
    return float(compute_atr_14(window))


def generate(daily: pd.DataFrame, compute_atr_14) -> dict:
    opens = daily["open"].to_numpy(float)
    highs = daily["high"].to_numpy(float)
    lows = daily["low"].to_numpy(float)
    closes = daily["close"].to_numpy(float)
    index = daily.index
    n = len(daily)
    trades, unfinished = [], []
    funnel = {
        "signals": 0,
        "no_next_bar": 0,
        "atr_not_positive": 0,
        "ignored_in_position": 0,
        "no_signal": 0,
    }
    pending = position = None

    def evaluate(i: int):
        if i < 3:
            return None, "no_signal"
        c0, c1, c2, c3 = (
            float(closes[i]),
            float(closes[i - 1]),
            float(closes[i - 2]),
            float(closes[i - 3]),
        )
        if c0 > c1 > c2 > c3:
            direction = "BUY"
        elif c0 < c1 < c2 < c3:
            direction = "SELL"
        else:
            return None, "no_signal"
        if i < 14:
            return None, "atr"
        atr = _atr_as_of(compute_atr_14, highs, lows, closes, i)
        if not atr > 0.0:
            return None, "atr"
        return {
            "direction": direction,
            "atr": atr,
            "signal_i": i,
            "signal_close": c0,
        }, "signal"

    for i in range(n):
        if pending is not None:
            if position is not None:
                raise RuntimeError("pending while in position")
            entry = float(opens[i])
            sl_dist = ATR_MULT * float(pending["atr"])
            if pending["direction"] == "BUY":
                stop = entry - sl_dist
                target = entry + TP_MULT * sl_dist
            else:
                stop = entry + sl_dist
                target = entry - TP_MULT * sl_dist
            position = {
                "direction": pending["direction"],
                "entry_time": pd.Timestamp(index[i]),
                "entry": entry,
                "sl_initial": float(stop),
                "tp": float(target),
                "sl_dist": float(sl_dist),
                "atr": float(pending["atr"]),
                "entry_i": i,
                "signal_i": int(pending["signal_i"]),
                "signal_bar_time": pd.Timestamp(index[pending["signal_i"]]),
                "signal_close": float(pending["signal_close"]),
            }
            pending = None

        if position is not None:
            day_num = i - position["entry_i"] + 1
            if day_num > TIME_DAY:
                raise RuntimeError("held past day 5")
            hit = resolve_bar(
                position["direction"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                position["sl_initial"],
                position["tp"],
                day_num,
            )
            if hit is not None:
                fill, reason, when = hit
                exit_time = (
                    pd.Timestamp(index[i])
                    if when == "open"
                    else pd.Timestamp(index[i]) + pd.Timedelta(days=1)
                )
                if exit_time <= position["entry_time"]:
                    raise RuntimeError("bad exit clock")
                trades.append(
                    {
                        **position,
                        "exit_time": exit_time,
                        "exit": float(fill),
                        "exit_reason": reason,
                        "bars_held": int(day_num),
                        "exit_bar_i": int(i),
                    }
                )
                position = None

        if position is None:
            sig, kind = evaluate(i)
            if kind == "no_signal":
                funnel["no_signal"] += 1
            elif kind == "atr":
                funnel["atr_not_positive"] += 1
            elif i + 1 >= n:
                funnel["no_next_bar"] += 1
            else:
                pending = sig
                funnel["signals"] += 1
        else:
            sig, kind = evaluate(i)
            if kind == "signal":
                funnel["ignored_in_position"] += 1

    if position is not None:
        unfinished.append(
            {
                "direction": position["direction"],
                "entry_time": str(position["entry_time"]),
                "bars_seen": int(n - position["entry_i"]),
            }
        )
    if pending is not None:
        raise RuntimeError("pending left")
    return {"trades": trades, "unfinished": unfinished, "funnel": funnel}


def size_lots(equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / (stop_dist * CONTRACT_SIZE), 2)
    lots = min(lots, MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_index(side: str, entry: float, exit_px: float, lots: float) -> float:
    """ASSUMPTION: GER40 EUR PnL treated 1:1 USD; spread in index points × lots."""
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    return raw * lots * CONTRACT_SIZE - SPREAD * lots - COMMISSION_PER_LOT * lots


def book_raw(trades, *, risk: float, zero_time: bool, FTMO_TZ, book_tag: str):
    """Size and cost trades at fixed risk. Equity updates after exits at/before entry."""
    ordered = sorted(trades, key=lambda t: t["entry_time"])
    equity = START_EQUITY
    open_exits, rows = [], []
    skipped = 0
    for seq, tr in enumerate(ordered):
        while open_exits and open_exits[0][0] <= tr["entry_time"]:
            _, _, pnl = heapq.heappop(open_exits)
            equity += pnl
        lots = size_lots(equity, risk, tr["sl_dist"])
        if lots < MIN_LOT:
            skipped += 1
            continue
        side = "long" if tr["direction"] == "BUY" else "short"
        if zero_time and tr["exit_reason"] == "TIME":
            pnl = 0.0
        else:
            pnl = pnl_index(side, tr["entry"], tr["exit"], lots)
        rows.append(
            {
                **tr,
                "seq": seq,
                "lots": lots,
                "equity_at_entry": equity,
                "pnl": pnl,
                "risk": risk,
                "gov_state": "n/a",
                "side_label": side,
            }
        )
        heapq.heappush(open_exits, (tr["exit_time"], seq, pnl))
    while open_exits:
        _, _, pnl = heapq.heappop(open_exits)
        equity += pnl

    return _finalize_book(rows, skipped, equity, FTMO_TZ, book_tag, risk)


def book_soft_gov(trades, *, zero_time: bool, FTMO_TZ, book_tag: str):
    """Soft DD governor sizing + Prague day kill −3%. Never sticky-block."""
    ordered = sorted(trades, key=lambda t: t["entry_time"])
    equity = START_EQUITY
    peak = START_EQUITY
    open_exits, rows = [], []
    skipped = 0
    killed_days: set[date] = set()
    day_pnl_live: dict[date, float] = defaultdict(float)
    day_start_live: dict[date, float] = {}
    funnel_gov = defaultdict(int)

    for seq, tr in enumerate(ordered):
        while open_exits and open_exits[0][0] <= tr["entry_time"]:
            _, _, pnl, xt = heapq.heappop(open_exits)
            equity += pnl
            if equity > peak:
                peak = equity
            pd_x = prague_day(xt)
            if pd_x not in day_start_live:
                day_start_live[pd_x] = equity - pnl
            day_pnl_live[pd_x] += pnl
            if day_start_live[pd_x] > 0 and day_pnl_live[pd_x] / day_start_live[pd_x] <= DAILY_KILL:
                killed_days.add(pd_x)

        et = pd.Timestamp(tr["entry_time"])
        if et.tzinfo is None:
            et = et.tz_localize("UTC")
        pd_e = prague_day(et)

        if pd_e in killed_days:
            funnel_gov["skip_kill"] += 1
            skipped += 1
            continue
        if pd_e not in day_start_live:
            day_start_live[pd_e] = equity
        if day_start_live[pd_e] > 0 and day_pnl_live[pd_e] / day_start_live[pd_e] <= DAILY_KILL:
            killed_days.add(pd_e)
            funnel_gov["skip_kill"] += 1
            skipped += 1
            continue

        risk, gstate = soft_gov_risk(equity, peak, RISK_OFFICIAL, RISK_MID, RISK_FLOOR)
        funnel_gov[f"gov_{gstate}"] += 1
        lots = size_lots(equity, risk, tr["sl_dist"])
        if lots < MIN_LOT:
            funnel_gov["skip_lots"] += 1
            skipped += 1
            continue
        side = "long" if tr["direction"] == "BUY" else "short"
        if zero_time and tr["exit_reason"] == "TIME":
            pnl = 0.0
        else:
            pnl = pnl_index(side, tr["entry"], tr["exit"], lots)
        rows.append(
            {
                **tr,
                "seq": seq,
                "lots": lots,
                "equity_at_entry": equity,
                "pnl": pnl,
                "risk": risk,
                "gov_state": gstate,
                "side_label": side,
            }
        )
        xt = pd.Timestamp(tr["exit_time"])
        if xt.tzinfo is None:
            xt = xt.tz_localize("UTC")
        heapq.heappush(open_exits, (tr["exit_time"], seq, pnl, xt))

    while open_exits:
        _, _, pnl, xt = heapq.heappop(open_exits)
        equity += pnl
        if equity > peak:
            peak = equity

    booked = _finalize_book(rows, skipped, equity, FTMO_TZ, book_tag, RISK_OFFICIAL)
    booked["funnel_gov"] = dict(funnel_gov)
    booked["killed_days"] = len(killed_days)
    return booked


def _finalize_book(rows, skipped, equity, FTMO_TZ, book_tag, risk):
    df = pd.DataFrame(rows)
    if df.empty:
        return {
            "df": df,
            "skipped": skipped,
            "final": equity,
            "months": {},
            "daily": {},
            "max_dd": 0.0,
            "worst_day": None,
            "trade_objs": [],
            "day_pnl": {},
            "day_start_eq": {},
            "funnel_gov": {},
            "killed_days": 0,
        }
    df = df.sort_values(["exit_time", "seq"], kind="mergesort").reset_index(drop=True)
    df["equity_after"] = START_EQUITY + df["pnl"].cumsum()
    eq = df["equity_after"].to_numpy(float)
    peak = np.maximum.accumulate(np.concatenate([[START_EQUITY], eq]))[1:]
    df["dd"] = (eq - peak) / peak
    exit_local = pd.DatetimeIndex(df["exit_time"]).tz_convert(FTMO_TZ)
    df["ftmo_day"] = exit_local.date
    df["month"] = exit_local.strftime("%Y-%m")
    daily = df.groupby("ftmo_day", sort=True)["pnl"].sum()
    daily_eq_end = START_EQUITY + daily.cumsum()
    daily_eq_start = daily_eq_end.shift(1).fillna(START_EQUITY)
    daily_ratio = daily / daily_eq_start
    daily_rows = {
        d: {
            "pnl": float(daily.loc[d]),
            "eq_start": float(daily_eq_start.loc[d]),
            "ratio": float(daily_ratio.loc[d]),
            "month": f"{d.year}-{d.month:02d}",
        }
        for d in daily.index
    }
    worst_key = min(daily_rows, key=lambda d: daily_rows[d]["ratio"]) if daily_rows else None
    worst_day = {"date": str(worst_key), **daily_rows[worst_key]} if worst_key is not None else None
    pnl_by_month = df.groupby("month")["pnl"].sum()
    eq_cursor = START_EQUITY
    months = {}
    for ym in COMPLETE:
        eq_start = eq_cursor
        pnl = float(pnl_by_month[ym]) if ym in pnl_by_month.index else 0.0
        eq_cursor = eq_start + pnl
        months[ym] = {"equity_start": eq_start, "equity_end": eq_cursor, "pnl": pnl}

    trade_objs: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    for _, r in df.iterrows():
        side = r["side_label"]
        et = pd.Timestamp(r["entry_time"])
        xt = pd.Timestamp(r["exit_time"])
        if et.tzinfo is None:
            et = et.tz_localize("UTC")
        if xt.tzinfo is None:
            xt = xt.tz_localize("UTC")
        tr = Trade(
            side=side,
            entry_ts=et,
            entry=float(r["entry"]),
            exit_ts=xt,
            exit=float(r["exit"]),
            reason=str(r["exit_reason"]),
            lots=float(r["lots"]),
            stop_dist=float(r["sl_dist"]),
            pnl=float(r["pnl"]),
            equity_after=float(r["equity_after"]),
            book=book_tag,
            atr=float(r["atr"]),
            signal_ts=pd.Timestamp(r["signal_bar_time"]),
            risk_used=float(r["risk"]),
            gov_state=str(r["gov_state"]),
        )
        trade_objs.append(tr)
        pd_x = prague_day(xt)
        if pd_x not in day_start_eq:
            day_start_eq[pd_x] = float(r["equity_after"]) - float(r["pnl"])
        day_pnl[pd_x] += float(r["pnl"])

    return {
        "df": df,
        "skipped": skipped,
        "final": float(df["equity_after"].iloc[-1]),
        "months": months,
        "daily": daily_rows,
        "max_dd": float(df["dd"].min()),
        "worst_day": worst_day,
        "trade_objs": trade_objs,
        "day_pnl": dict(day_pnl),
        "day_start_eq": day_start_eq,
        "funnel_gov": {},
        "killed_days": 0,
    }


def score_windows(booked):
    df = booked["df"]
    months = booked["months"]
    daily_rows = booked["daily"]
    windows = []
    for i in range(len(COMPLETE) - 2):
        trip = COMPLETE[i : i + 3]
        start_eq = months[trip[0]]["equity_start"]
        inside = df[df["month"].isin(trip)] if len(df) else df
        days = [daily_rows[d] for d in daily_rows if daily_rows[d]["month"] in trip]
        reached_110 = reached_1155 = False
        min_eq = max_eq = None
        terminal_eq = start_eq
        for _, r in inside.iterrows():
            ea = float(r["equity_after"])
            terminal_eq = ea
            if min_eq is None or ea < min_eq:
                min_eq = ea
            if max_eq is None or ea > max_eq:
                max_eq = ea
            if (not reached_110) and ea >= start_eq * 1.10:
                reached_110 = True
            if (not reached_1155) and ea >= start_eq * 1.155:
                reached_1155 = True
        if len(inside) == 0:
            terminal_eq = max_eq = min_eq = start_eq
        floor_fail = min_eq is not None and min_eq <= start_eq * 0.90
        day_fail = any(d["ratio"] <= -0.05 for d in days)
        worst_day = min((d["ratio"] for d in days), default=0.0)
        max_dd = 0.0
        if len(inside):
            eqs = inside["equity_after"].to_numpy(float)
            pk = np.maximum.accumulate(np.concatenate([[start_eq], eqs]))[1:]
            max_dd = float(((eqs - pk) / pk).min())
        passed = reached_110 and reached_1155 and (not floor_fail) and (not day_fail)
        inter = set(trip) & STREAK
        if not inter:
            overlap = "outside"
        elif inter == set(trip):
            overlap = "inside_streak"
        else:
            overlap = "partial_overlap"
        y, m = map(int, trip[2].split("-"))
        end_day = calendar.monthrange(y, m)[1]
        windows.append(
            {
                "months": trip,
                "start": f"{trip[0]}-01",
                "end": f"{trip[2]}-{end_day:02d}",
                "overlap": overlap,
                "n_exits": int(len(inside)),
                "reached_110": reached_110,
                "reached_1155": reached_1155,
                "floor_fail": floor_fail,
                "day_fail": day_fail,
                "passed": passed,
                "terminal_return_pct": (terminal_eq / start_eq - 1.0) * 100.0,
                "max_return_pct": (max_eq / start_eq - 1.0) * 100.0 if max_eq is not None else 0.0,
                "max_dd_pct": max_dd * 100.0,
                "worst_day_pct": worst_day * 100.0,
            }
        )
    return windows


def max_realized_dd(trades: list[Trade]) -> float:
    max_dd = 0.0
    peak = START_EQUITY
    for tr in trades:
        if tr.equity_after > peak:
            peak = tr.equity_after
        dd = (peak - tr.equity_after) / peak if peak > 0 else 0.0
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
                if use_gov and pd_e in killed:
                    continue
                if pd_e not in day_start_l:
                    day_start_l[pd_e] = eq
                if use_gov and day_start_l[pd_e] > 0 and day_pnl_l[pd_e] / day_start_l[pd_e] <= DAILY_KILL:
                    killed.add(pd_e)
                    continue
                if use_gov:
                    risk, _ = soft_gov_risk(eq, peak, RISK_OFFICIAL, RISK_MID, RISK_FLOOR)
                else:
                    risk = tr.risk_used if tr.risk_used > 0 else RISK_OFFICIAL
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
                if use_gov and day_pnl_l[pd_x] / day_start_l[pd_x] <= DAILY_KILL:
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


def explorer_summary(real, zeroed, win_real, win_zero):
    zero_pass_keys = {(w["start"], w["end"]) for w in win_zero if w["passed"]}
    countable = []
    for w in win_real:
        if w["passed"] and (w["start"], w["end"]) in zero_pass_keys:
            wz = next(x for x in win_zero if x["start"] == w["start"] and x["end"] == w["end"])
            countable.append({"real": w, "time_zeroed": wz})
    price_passes = [w for w in win_real if w["passed"]]
    countable_outside = [c for c in countable if not (set(c["real"]["months"]) & STREAK)]
    return {
        "price_passes": len(price_passes),
        "countable": len(countable),
        "countable_outside": len(countable_outside),
        "countable_windows": countable,
        "price_windows": price_passes,
        "zeroed_passes": sum(1 for w in win_zero if w["passed"]),
        "zeroed_final": zeroed["final"],
        "zeroed_max_dd": zeroed["max_dd"],
        "zeroed_worst": zeroed["worst_day"],
    }


def summarize_our_gates(label, booked, data_end, explorer, use_gov: bool):
    trades = booked["trade_objs"]
    day_pnl = booked["day_pnl"]
    day_start_eq = booked["day_start_eq"]

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
    fit_days = (FIT_END.normalize() - FIT_START).days + 1
    fit_mo = fit_days / 30.44
    fit_pace = fit_net / fit_mo if fit_mo > 0 else 0.0

    n60, w60, p60 = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)
    nseq, wseq, pseq = count_sequential_reset(trades, use_gov, 90)

    ho_cut = date(2025, 11, 8)
    n90_ho = sum(1 for p in p90 if date.fromisoformat(p["start"]) >= ho_cut)
    nseq_ho = sum(1 for p in pseq if date.fromisoformat(p["start"]) >= ho_cut)
    has_90 = n90 >= 1 or nseq >= 1
    has_90_ho = n90_ho >= 1 or nseq_ho >= 1

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
    ext_ok = (not ext_available) or (ext_net >= 0)
    ho_ok = ho_net > 0

    # ACCEPT gates same as C22–C25: HO ≤90d is the gate (Explorer outside is cross-check only)
    if not legal or not has_90:
        decision = "REJECT"
    elif legal and has_90_ho and ho_ok and leave_ok and ext_ok:
        if ext_available and ext_net >= 0:
            decision = "ACCEPT"
        elif not ext_available:
            decision = "CONDITIONAL"  # Ext N/A honesty / C22 precedent
        else:
            decision = "CONDITIONAL"
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    return {
        "label": label,
        "use_gov": use_gov,
        "decision": decision,
        "legal": legal,
        "ho_net": ho_net,
        "ho_pace": ho_pace,
        "fit_net": fit_net,
        "fit_pace": fit_pace,
        "leave_net": leave_net,
        "leave_drop": leave_drop,
        "ext_net": ext_net,
        "ext_status": ext_status,
        "ext_available": ext_available,
        "max_dd": max_dd,
        "worst_day": str(worst_d) if worst_d else None,
        "worst_pct": worst_pct,
        "n_fail_days": n_fail,
        "n_trades": len(trades),
        "wins": wins,
        "wr": wins / len(trades) if trades else 0.0,
        "longs": longs,
        "shorts": shorts,
        "reasons": dict(reasons),
        "gov_counts": dict(gov_counts),
        "final_equity": booked["final"],
        "skipped": booked["skipped"],
        "killed_days": booked.get("killed_days", 0),
        "funnel_gov": booked.get("funnel_gov", {}),
        "n60": n60,
        "w60": w60,
        "p60": p60,
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
        "explorer_countable": explorer["countable"],
        "explorer_countable_outside": explorer["countable_outside"],
        "explorer_price_passes": explorer["price_passes"],
    }


def write_outputs(book_a, book_b, sens, gen, data_sha, spec_sha, entry5_sha, data_end):
    PACK.mkdir(parents=True, exist_ok=True)
    books = [book_a, book_b]
    primary = book_a if book_a["decision"] != "REJECT" or book_b["decision"] == "REJECT" else book_b
    # Prefer ACCEPT > CONDITIONAL > REJECT; among ties prefer soft if better HO windows
    ranked = sorted(
        books,
        key=lambda s: (
            0 if s["decision"] == "ACCEPT" else (1 if s["decision"] == "CONDITIONAL" else 2),
            -(s["n90_ho"] + s["nseq_ho"]),
            -s["ho_pace"],
            0 if s["use_gov"] else 1,
        ),
    )
    primary = ranked[0]

    lines = []
    a = lines.append
    a("# Candidate 26 — GER40 three-close momentum results")
    a("")
    a(f"- Measured: {datetime.now(ET).strftime('%Y-%m-%d %H:%M %Z')}")
    a(f"- Data sha256: `{data_sha}`")
    a(f"- Spec sha256: `{spec_sha}`")
    a(f"- Gold entry5 preregister sha256: `{entry5_sha}` (mechanics source; not retuned)")
    a(f"- Data end: {data_end}")
    a("- Live C4 / drip / FREEZE: **untouched**")
    a(
        "- Costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.0 pts, "
        "EUR→USD 1:1"
    )
    a("")
    a("## Lead")
    opens = primary["decision"] == "ACCEPT"
    if opens:
        a(
            f"**ACCEPT — GER40 three-close opens a ~3mo path on measurement** via "
            f"{primary['label']} (DD {primary['max_dd']*100:.2f}%, HO ~${primary['ho_pace']:,.0f}/mo, "
            f"≤90d HO-era {primary['n90_ho']}, Explorer outside {primary['explorer_countable_outside']})."
        )
    elif primary["decision"] == "CONDITIONAL":
        a(
            f"**CONDITIONAL — GER40 three-close legal DD + windows, not ACCEPT** via "
            f"{primary['label']} (DD {primary['max_dd']*100:.2f}%, HO ~${primary['ho_pace']:,.0f}/mo, "
            f"≤90d {primary['n90']}/{primary['w90']} HO-era {primary['n90_ho']}, "
            f"leave-out ${primary['leave_net']:,.0f}, Ext {primary['ext_status']})."
        )
    else:
        a(
            f"**REJECT — GER40 three-close does not open a ~3mo path.** "
            f"DD illegal, HO≤0, or zero ≤90d windows. "
            f"Best book {primary['label']}: legal={primary['legal']} "
            f"DD={primary['max_dd']*100:.2f}% HO=${primary['ho_pace']:,.0f}/mo "
            f"90d={primary['n90']}/{primary['w90']} outside={primary['explorer_countable_outside']}."
        )
    a("")
    a("## Summary table")
    a("")
    a(
        "| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | "
        "Explorer out | Leave-out | Legal | Decision |"
    )
    a("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for s in [book_a, book_b, sens]:
        gov = "SOFT 2.50→1.25→0.75" if s["use_gov"] else f"{s.get('_risk_label', '2.50%')}"
        tag = s["label"]
        a(
            f"| {tag} | {gov} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{s['explorer_countable_outside']} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    a("")

    for s, title in [
        (book_a, "26A GER40 three-close @2.50% (primary)"),
        (book_b, "26B GER40 three-close + soft DD governor"),
        (sens, "Sensitivity @2.60% (NOT verdict)"),
    ]:
        a(f"## {title}")
        a("")
        a("| Metric | Value |")
        a("|---|---|")
        a(f"| Decision | **{s['decision']}** |")
        a(f"| Legal (DD≤10%, no day≤−5%) | {s['legal']} |")
        a(f"| Final equity | ${s['final_equity']:,.2f} |")
        a(f"| Max DD | {s['max_dd']*100:.4f}% |")
        a(f"| Worst Prague day | {s['worst_day']} ({s['worst_pct']*100:.4f}%) |")
        a(f"| Trades / WR | {s['n_trades']} / {s['wr']*100:.1f}% |")
        a(f"| Long / Short | {s['longs']} / {s['shorts']} |")
        a(f"| Exit mix | {s['reasons']} |")
        if s["use_gov"]:
            a(f"| Gov states | {s['gov_counts']} |")
            a(f"| Killed Prague days | {s['killed_days']} |")
            a(f"| Soft funnel | {s['funnel_gov']} |")
        a(f"| Fit net / pace | ${s['fit_net']:,.0f} / ${s['fit_pace']:,.0f}/mo |")
        a(f"| HO net / pace | ${s['ho_net']:,.0f} / ${s['ho_pace']:,.0f}/mo |")
        a(f"| Leave-out (drop {s['leave_drop']}) | ${s['leave_net']:,.0f} |")
        a(f"| Ext | {s['ext_status']} (${s['ext_net']:,.0f}) |")
        a(f"| ≤60d continuous | {s['n60']}/{s['w60']} |")
        a(f"| ≤90d continuous | {s['n90']}/{s['w90']} (HO-era starts {s['n90_ho']}) |")
        a(f"| seq90 Challenge→Verify reset | {s['nseq']}/{s['wseq']} (HO-era {s['nseq_ho']}) |")
        a(
            f"| Explorer countable (real ∩ TIME-zero) | "
            f"{s['explorer_countable']}/30 (outside streak {s['explorer_countable_outside']}) |"
        )
        a(f"| Explorer price-path passes | {s['explorer_price_passes']}/30 |")
        a("")
        cw = s.get("_countable_windows", [])
        a(f"### Explorer countable windows — {s['label']}")
        a("")
        if not cw:
            a("None.")
        else:
            a("| start | end | overlap | terminal % | max % | max DD % | worst day % |")
            a("|---|---|---|---:|---:|---:|---:|")
            for c in cw:
                w = c["real"]
                a(
                    f"| {w['start']} | {w['end']} | {w['overlap']} | "
                    f"{w['terminal_return_pct']:.4f} | {w['max_return_pct']:.4f} | "
                    f"{w['max_dd_pct']:.4f} | {w['worst_day_pct']:.4f} |"
                )
        a("")
        if s["p90"]:
            a(f"### ≤90d continuous pass sample — {s['label']}")
            a("")
            a("| start | end | max_mult | min_mult | worst_day |")
            a("|---|---|---:|---:|---:|")
            for p in s["p90"][:10]:
                a(
                    f"| {p['start']} | {p['end']} | {p['max_mult']:.4f} | "
                    f"{p['min_mult']:.4f} | {p['worst_day']*100:.2f}% |"
                )
            a("")

    a("## Funnel (signal generation)")
    a("")
    a(f"```\n{json.dumps(gen['funnel'], indent=2)}\n```")
    a("")
    a("## Does GER40 three-close open a ~3mo path?")
    a("")
    if opens:
        a("**Yes on measurement gates** — still research-only; nothing arms without Odin yes.")
    else:
        a(
            f"**No cleared ACCEPT.** Official primary verdict **{book_a['decision']}**; "
            f"soft-gov **{book_b['decision']}**. "
            "Keep iterating under broad mandate; do not retune this locked rule."
        )
    a("")
    a("Nothing live.")

    RESULTS.write_text("\n".join(lines) + "\n")

    SUMMARY_TXT.write_text(
        f"C26 GER40 three-close → primary={primary['decision']} via {primary['label']} | "
        f"26A={book_a['decision']} DD={book_a['max_dd']*100:.2f}% HO=${book_a['ho_pace']:,.0f}/mo "
        f"90d={book_a['n90']}/{book_a['w90']}(HO={book_a['n90_ho']}) out={book_a['explorer_countable_outside']} "
        f"leave=${book_a['leave_net']:,.0f} legal={book_a['legal']} | "
        f"26B soft={book_b['decision']} DD={book_b['max_dd']*100:.2f}% HO=${book_b['ho_pace']:,.0f}/mo "
        f"90d={book_b['n90']}/{book_b['w90']}(HO={book_b['n90_ho']}) out={book_b['explorer_countable_outside']} "
        f"leave=${book_b['leave_net']:,.0f} legal={book_b['legal']} | "
        f"sens@2.60%={sens['decision']} DD={sens['max_dd']*100:.2f}%\n"
        f"Live C4 untouched. Research only.\n"
    )

    def scrub(d):
        return {k: v for k, v in d.items() if not k.startswith("_")}

    payload = {
        "candidate": 26,
        "label": "GER40 three-close momentum (Gold entry5 port) + soft DD governor",
        "not_live": True,
        "data_sha256": data_sha,
        "spec_sha256": spec_sha,
        "entry5_preregister_sha256": entry5_sha,
        "costs_assumption": {
            "contract_size": CONTRACT_SIZE,
            "spread": SPREAD,
            "commission_per_lot": COMMISSION_PER_LOT,
            "eur_usd": "1:1 ASSUMPTION",
            "note": "C22 ASSUMPTIONS reused",
        },
        "funnel": gen["funnel"],
        "unfinished": len(gen["unfinished"]),
        "n_raw_trades": len(gen["trades"]),
        "book_26A": scrub(book_a),
        "book_26B_soft": scrub(book_b),
        "sensitivity_2_60": scrub(sens),
        "primary": primary["label"],
        "primary_decision": primary["decision"],
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")

    # STATUS
    lead = (
        f"**YES — GER40 three-close opens a deployable ~3mo path** via {primary['label']}."
        if opens
        else (
            f"**CONDITIONAL — GER40 three-close legal DD + windows, not ACCEPT** via {primary['label']}."
            if primary["decision"] == "CONDITIONAL"
            else "**NO — GER40 three-close does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows."
        )
    )
    status = []
    sa = status.append
    sa("# BTC FTMO research baseline (2026-10-07)")
    sa("")
    sa(f"**Status: C26 GER40 three-close — {primary['decision']}** — {lead}")
    sa("")
    sa("## Candidate 26")
    sa("")
    sa(
        "| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | "
        "Explorer out | Leave-out | Legal | Decision |"
    )
    sa("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for s, risk_lbl in [
        (book_a, "2.50% OFF"),
        (book_b, "SOFT 2.50→1.25→0.75"),
        (sens, "2.60% sens (NOT verdict)"),
    ]:
        sa(
            f"| {s['label']} | {risk_lbl} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{s['explorer_countable_outside']} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    sa("")
    sa("## Live")
    sa(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C26 arms without Odin approval. Gold not packaged."
    )
    sa("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")

    # PR body
    pr = []
    pa = pr.append
    pa("## Candidate 26 — GER40 three-close momentum (Gold entry5 port)")
    pa("")
    pa("Research only. Broad Odin mandate. Explorer near-miss lane. **No deploy.** Live C4 untouched.")
    pa("")
    pa(f"**Primary verdict: `{primary['decision']}`** via {primary['label']}")
    pa("")
    pa(
        "| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | "
        "Explorer out | Leave-out | Legal | Decision |"
    )
    pa("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for s, risk_lbl in [
        (book_a, "2.50% OFF"),
        (book_b, "SOFT"),
        (sens, "2.60% sens"),
    ]:
        pa(
            f"| {s['label']} | {risk_lbl} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{s['explorer_countable_outside']} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pa("")
    pa("### Lead")
    pa(lead)
    pa("")
    pa("### Mechanics")
    pa("- Mirror of Gold entry5: three strict consecutive daily closes → next open; SL 2×ATR14; TP 2R; day-5 TIME")
    pa("- 26A risk locked **2.50%**; 26B soft gov 2.50→1.25→0.75 + Prague day kill −3% (a-priori)")
    pa("- 2.60% sensitivity readout only — not verdict")
    pa("- GER40 costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.0 pts, EUR→USD 1:1")
    pa("- ACCEPT gates = C22–C25 (HO ≤90d is gate; Explorer outside is cross-check)")
    pa("")
    pa("### Paths")
    pa("- Spec: `research/btc/2026-10-07-candidate-26/ftmo-candidate-26.md`")
    pa("- Runner: `research/btc/2026-10-07-candidate-26/run_candidate_26.py`")
    pa("- Results: `research/btc/2026-10-07-candidate-26/candidate-26-results.md`")
    pa("")
    pa("Nothing live. Do not arm without Odin yes.")
    PR_BODY.write_text("\n".join(pr) + "\n")

    for src in [SPEC_PATH, RUNNER, RESULTS, SUMMARY_TXT, RESULTS_JSON, ROOT_STATUS, PR_BODY]:
        if src.exists():
            shutil.copy2(src, PACK / src.name)
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())
    (PACK / "GITHUB-PR-BODY-C26.md").write_text(PR_BODY.read_text())


def main() -> None:
    data_sha = sha256_of(GER40_FEED)
    if data_sha != EXPECTED_SHA:
        raise SystemExit(f"ABORT GER40 sha mismatch: got {data_sha} expected {EXPECTED_SHA}")
    entry5_sha = sha256_of(ENTRY5_PREREG)
    if entry5_sha != ENTRY5_PREREG_SHA:
        raise SystemExit(f"ABORT entry5 prereg sha mismatch: {entry5_sha}")
    if not SPEC_PATH.exists():
        raise SystemExit(f"ABORT missing spec {SPEC_PATH}")
    spec_sha = sha256_of(SPEC_PATH)

    print("loading harness + GER40…", flush=True)
    H, compute_atr_14 = load_harness()
    FTMO_TZ = H.FTMO_TZ
    m1 = H.load_m1(GER40_FEED)
    daily = H.resample(m1, "1D")
    data_end = m1.index[-1]
    print(f"m1={len(m1)} daily={len(daily)} data_end={data_end}", flush=True)

    print("generating three-close trades…", flush=True)
    gen = generate(daily, compute_atr_14)
    raw_trades = gen["trades"]
    print(
        f"raw trades={len(raw_trades)} unfinished={len(gen['unfinished'])} funnel={gen['funnel']}",
        flush=True,
    )

    print("booking 26A @ 2.50% (official)…", flush=True)
    real_a = book_raw(raw_trades, risk=RISK_OFFICIAL, zero_time=False, FTMO_TZ=FTMO_TZ, book_tag="26A@2.50%")
    zero_a = book_raw(raw_trades, risk=RISK_OFFICIAL, zero_time=True, FTMO_TZ=FTMO_TZ, book_tag="26A@2.50%z")
    exp_a = explorer_summary(real_a, zero_a, score_windows(real_a), score_windows(zero_a))
    book_a = summarize_our_gates("26A@2.50%", real_a, data_end, exp_a, use_gov=False)
    book_a["_countable_windows"] = exp_a["countable_windows"]
    book_a["_risk_label"] = "2.50%"
    print(
        f"  26A → {book_a['decision']} DD={book_a['max_dd']*100:.2f}% HO={book_a['ho_pace']:.0f} "
        f"90d={book_a['n90']}/{book_a['w90']}(HO={book_a['n90_ho']}) out={book_a['explorer_countable_outside']}",
        flush=True,
    )

    print("booking 26B soft gov…", flush=True)
    real_b = book_soft_gov(raw_trades, zero_time=False, FTMO_TZ=FTMO_TZ, book_tag="26B+soft")
    zero_b = book_soft_gov(raw_trades, zero_time=True, FTMO_TZ=FTMO_TZ, book_tag="26B+softz")
    exp_b = explorer_summary(real_b, zero_b, score_windows(real_b), score_windows(zero_b))
    book_b = summarize_our_gates("26B+soft", real_b, data_end, exp_b, use_gov=True)
    book_b["_countable_windows"] = exp_b["countable_windows"]
    book_b["_risk_label"] = "SOFT"
    print(
        f"  26B → {book_b['decision']} DD={book_b['max_dd']*100:.2f}% HO={book_b['ho_pace']:.0f} "
        f"90d={book_b['n90']}/{book_b['w90']}(HO={book_b['n90_ho']}) out={book_b['explorer_countable_outside']}",
        flush=True,
    )

    print("booking sensitivity @ 2.60% (NOT verdict)…", flush=True)
    real_s = book_raw(
        raw_trades, risk=RISK_SENSITIVITY, zero_time=False, FTMO_TZ=FTMO_TZ, book_tag="sens@2.60%"
    )
    zero_s = book_raw(
        raw_trades, risk=RISK_SENSITIVITY, zero_time=True, FTMO_TZ=FTMO_TZ, book_tag="sens@2.60%z"
    )
    exp_s = explorer_summary(real_s, zero_s, score_windows(real_s), score_windows(zero_s))
    sens = summarize_our_gates("sens@2.60%", real_s, data_end, exp_s, use_gov=False)
    sens["_countable_windows"] = exp_s["countable_windows"]
    sens["_risk_label"] = "2.60% sens"
    print(
        f"  sens → {sens['decision']} DD={sens['max_dd']*100:.2f}% out={sens['explorer_countable_outside']}",
        flush=True,
    )

    write_outputs(book_a, book_b, sens, gen, data_sha, spec_sha, entry5_sha, data_end)
    print("wrote", RESULTS, PACK, flush=True)
    print(SUMMARY_TXT.read_text(), flush=True)


if __name__ == "__main__":
    main()
