#!/usr/bin/env python3
"""Candidate 38: USA30 Wilder Parabolic SAR (Gold entry30 / Explorer BTC-SAR port) + soft DD governor.

Research only. Broad Odin mandate. Explorer suggested USA30 Wilder SAR near-miss.
Mirror entry30 / btc-sar mechanics on USA30 — AF 0.02/0.02/0.20; reverse-only.
38A @2.50% primary; 38B soft gov a-priori; 2.60% sensitivity NOT verdict.
No live VM / MetaAPI / C4 / drip / FREEZE. Do not package Gold.
Do not re-run Explorer BTC SAR @0.50% FAIL.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import calendar
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import types

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

USA30_FEED = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usa30idxusd-m1-bid-2024-01-01-2026-09-02.csv"
)
EXPECTED_SHA = "968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a"
ENTRY30_PREREG = Path("/workspace/gold-strategy/entry30-preregister-2026-10-03.md")
ENTRY30_PREREG_SHA = "29638946222b3801dde3c02f6b9831fb89975630768888200310266f99ed5c43"
BTC_SAR_PREREG = Path("/workspace/strategy-explorer/btc-sar-preregister-2026-10-07.md")
SPEC_PATH = Path("/workspace/btc-strategies/ftmo-candidate-38.md")

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-38"
RESULTS = OUT_DIR / "candidate-38-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-38-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-38-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C38.md"
RUNNER = OUT_DIR / "run_candidate_38.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 100.0
CONTRACT_SIZE = 1.0  # FTMO US30.cash catalogue (C22)
SPREAD = 2.5  # ASSUMPTION — C22 USA30; feed missing
COMMISSION_PER_LOT = 0.0  # catalogue
TICK_VALUE = 1.0

AF_START, AF_STEP, AF_MAX = 0.02, 0.02, 0.20

RISK_OFFICIAL = 0.025
RISK_SENSITIVITY = 0.026
RISK_MID = 0.0125
RISK_FLOOR = 0.0075
GOV_SOFT = 0.05
GOV_HARD = 0.08
DAILY_KILL = -0.03

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
    units: float = 0.0
    include_exit_bar: bool = True


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
    return H


def soft_gov_risk(equity: float, peak: float, full: float, mid: float, floor: float):
    if peak <= 0:
        return full, "full"
    dd = 1.0 - equity / peak
    if dd >= GOV_HARD:
        return floor, "floor"
    if dd >= GOV_SOFT:
        return mid, "mid"
    return full, "full"


def generate_reversals(daily: pd.DataFrame) -> dict:
    """Wilder SAR reverse stream — mirror entry30 / btc_sar_2026_10_07.generate."""
    opens = daily["open"].to_numpy(float)
    highs = daily["high"].to_numpy(float)
    lows = daily["low"].to_numpy(float)
    closes = daily["close"].to_numpy(float)
    index = daily.index
    n = len(daily)
    if closes[1] >= closes[0]:
        trend_long, sar, ep = True, float(lows[0]), float(highs[1])
    else:
        trend_long, sar, ep = False, float(highs[0]), float(lows[1])
    af = AF_START
    reversals = []
    funnel = {
        "seed_long": trend_long,
        "reversals": 0,
        "continued": 0,
        "skipped_nonpositive_stop": 0,
    }
    for t in range(1, n - 1):
        raw = sar + af * (ep - sar)
        if trend_long:
            next_sar = min(raw, float(lows[t]), float(lows[t - 1]))
        else:
            next_sar = max(raw, float(highs[t]), float(highs[t - 1]))
        bar = t + 1
        o, h, l = float(opens[bar]), float(highs[bar]), float(lows[bar])
        reverse = (trend_long and l <= next_sar) or ((not trend_long) and h >= next_sar)
        if not reverse:
            if trend_long and h > ep:
                ep, af = h, min(af + AF_STEP, AF_MAX)
            elif (not trend_long) and l < ep:
                ep, af = l, min(af + AF_STEP, AF_MAX)
            sar = next_sar
            funnel["continued"] += 1
            continue
        funnel["reversals"] += 1
        old_ep = ep
        fill = float(next_sar)
        fill_is_open = False
        if trend_long and o < next_sar:
            fill, fill_is_open = o, True
        elif (not trend_long) and o > next_sar:
            fill, fill_is_open = o, True
        if fill_is_open:
            fill_when, fill_time, exit_reason = "open", pd.Timestamp(index[bar]), "SL_OPEN"
        else:
            fill_when, fill_time, exit_reason = (
                "sar",
                pd.Timestamp(index[bar]) + pd.Timedelta(days=1),
                "REVERSE",
            )
        new_long = not trend_long
        new_ep = h if new_long else l
        new_sar = float(old_ep)
        new_dir = "BUY" if new_long else "SELL"
        sl_dist = abs(fill - new_sar)
        trend_long, ep, sar, af = new_long, new_ep, new_sar, AF_START
        if not sl_dist > 0:
            funnel["skipped_nonpositive_stop"] += 1
            reversals.append(
                {
                    "fill": fill,
                    "fill_time": fill_time,
                    "fill_is_open": fill_is_open,
                    "exit_reason": exit_reason,
                    "new_dir": new_dir,
                    "new_sar": new_sar,
                    "sl_dist": 0.0,
                    "openable": False,
                    "bar_i": int(bar),
                    "fill_when": fill_when,
                }
            )
            continue
        reversals.append(
            {
                "fill": fill,
                "fill_time": fill_time,
                "fill_is_open": fill_is_open,
                "exit_reason": exit_reason,
                "new_dir": new_dir,
                "new_sar": new_sar,
                "sl_dist": float(sl_dist),
                "openable": True,
                "bar_i": int(bar),
                "fill_when": fill_when,
            }
        )
    unfinished = {
        "trend_long": trend_long,
        "sar": float(sar),
        "ep": float(ep),
        "af": float(af),
        "last_bar": int(n - 1),
        "last_ts": pd.Timestamp(index[n - 1]),
    }
    return {"reversals": reversals, "funnel": funnel, "unfinished": unfinished}


def size_lots(equity: float, risk: float, stop_dist: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    lots = round(equity * risk / (stop_dist * CONTRACT_SIZE * TICK_VALUE), 2)
    lots = min(lots, MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_usa30(side: str, entry: float, exit_px: float, lots: float) -> float:
    """ASSUMPTION: USA30 USD PnL; spread in index points × lots (C22 ASSUMPTION 2.5)."""
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    return raw * lots * CONTRACT_SIZE - SPREAD * lots - COMMISSION_PER_LOT * lots


def book_reversals(
    reversals,
    unfinished_meta,
    *,
    risk: float | None,
    soft: bool,
    FTMO_TZ,
    book_tag: str,
):
    """Walk SAR reverses; soft mode may stay flat after a close (kill / lots / risk)."""
    equity = START_EQUITY
    peak = START_EQUITY
    position = None
    rows = []
    skipped = 0
    killed_days: set[date] = set()
    day_pnl_live: dict[date, float] = defaultdict(float)
    day_start_live: dict[date, float] = {}
    funnel_gov = defaultdict(int)
    opens = closes = 0

    def note_exit_pnl(pnl: float, xt: pd.Timestamp):
        nonlocal equity, peak
        equity += pnl
        if equity > peak:
            peak = equity
        pd_x = prague_day(xt)
        if pd_x not in day_start_live:
            day_start_live[pd_x] = equity - pnl
        day_pnl_live[pd_x] += pnl
        if day_start_live[pd_x] > 0 and day_pnl_live[pd_x] / day_start_live[pd_x] <= DAILY_KILL:
            killed_days.add(pd_x)

    for seq, rev in enumerate(reversals):
        fill = float(rev["fill"])
        fill_time = pd.Timestamp(rev["fill_time"])
        if fill_time.tzinfo is None:
            fill_time = fill_time.tz_localize("UTC")
        exit_reason = rev["exit_reason"]
        fill_is_open = bool(rev["fill_is_open"])

        if position is not None:
            et = fill_time
            if et <= position["entry_time"]:
                et = position["entry_time"] + pd.Timedelta(seconds=1)
            side = position["side"]
            pnl = pnl_usa30(side, position["entry"], fill, position["lots"])
            note_exit_pnl(pnl, et)
            rows.append(
                {
                    "seq": seq,
                    "direction": "BUY" if side == "long" else "SELL",
                    "side_label": side,
                    "entry_time": position["entry_time"],
                    "entry": position["entry"],
                    "exit_time": et,
                    "exit": fill,
                    "exit_reason": exit_reason,
                    "lots": position["lots"],
                    "units": position["units"],
                    "sl_dist": position["sl_dist"],
                    "sl_initial": position["sl_initial"],
                    "equity_at_entry": position["equity_at_entry"],
                    "pnl": pnl,
                    "risk": position["risk"],
                    "gov_state": position["gov_state"],
                    "include_exit_bar": not fill_is_open,
                    "signal_bar_time": position["entry_time"],
                    "atr": 0.0,
                }
            )
            closes += 1
            position = None

        if not rev["openable"]:
            skipped += 1
            funnel_gov["skip_nonpos_stop"] += 1
            continue

        pd_e = prague_day(fill_time)
        if soft:
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
            r_used, gstate = soft_gov_risk(equity, peak, RISK_OFFICIAL, RISK_MID, RISK_FLOOR)
            funnel_gov[f"gov_{gstate}"] += 1
        else:
            r_used, gstate = float(risk), "n/a"

        lots = size_lots(equity, r_used, rev["sl_dist"])
        if lots < MIN_LOT:
            funnel_gov["skip_lots"] += 1
            skipped += 1
            continue
        side = "long" if rev["new_dir"] == "BUY" else "short"
        units = lots * CONTRACT_SIZE
        position = {
            "side": side,
            "entry_time": fill_time,
            "entry": fill,
            "sl_initial": float(rev["new_sar"]),
            "sl_dist": float(rev["sl_dist"]),
            "lots": lots,
            "units": units,
            "equity_at_entry": equity,
            "risk": r_used,
            "gov_state": gstate,
        }
        opens += 1

    unfinished_pos = None
    if position is not None:
        unfinished_pos = {
            "direction": "BUY" if position["side"] == "long" else "SELL",
            "entry_time": str(position["entry_time"]),
            "entry": position["entry"],
            "lots": position["lots"],
            "units": position["units"],
            "sl_initial": position["sl_initial"],
        }

    booked = _finalize_book(
        rows,
        skipped,
        equity,
        FTMO_TZ,
        book_tag,
        RISK_OFFICIAL if soft else float(risk),
    )
    booked["funnel_gov"] = dict(funnel_gov)
    booked["killed_days"] = len(killed_days)
    booked["opens"] = opens
    booked["closes"] = closes
    booked["unfinished_pos"] = unfinished_pos
    booked["unfinished_meta"] = unfinished_meta
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
            "opens": 0,
            "closes": 0,
            "unfinished_pos": None,
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
            atr=0.0,
            signal_ts=et,
            risk_used=float(r["risk"]),
            gov_state=str(r["gov_state"]),
            units=float(r["units"]),
            include_exit_bar=bool(r["include_exit_bar"]),
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


def prague_midnight_utc(d: date):
    return pd.Timestamp(datetime(d.year, d.month, d.day, tzinfo=PRAGUE)).tz_convert("UTC")


def floating_audit(m1: pd.DataFrame, trades: list[Trade], unfinished_pos):
    """Match BTC SAR floating Prague day: adverse M1 extreme vs midnight/entry ref + realized."""
    prague_idx = m1.index.tz_convert(PRAGUE)
    codes, uniques = pd.factorize(prague_idx.floor("D"), sort=False)
    codes = np.asarray(codes, dtype=np.int64)
    n = len(m1)
    cuts = np.flatnonzero(np.diff(codes)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [n]))
    uniq_dates = [pd.Timestamp(ts).date() for ts in uniques]
    midnights = [prague_midnight_utc(d) for d in uniq_dates]
    opens = m1["open"].to_numpy(float)
    lows = m1["low"].to_numpy(float)
    highs = m1["high"].to_numpy(float)
    closes = m1["close"].to_numpy(float)
    index = m1.index
    after_last = index[-1] + pd.Timedelta(minutes=1)

    def hold_end(tr: Trade):
        et = tr.exit_ts
        if not tr.include_exit_bar:
            return et
        i = int(index.searchsorted(et))
        return pd.Timestamp(index[i + 1]) if i + 1 < len(index) else after_last

    def ref_mid(mu):
        pos = int(index.searchsorted(mu))
        if pos < len(index) and index[pos] == mu:
            return float(opens[pos])
        return float(closes[pos - 1]) if pos > 0 else None

    intervals = []
    for tr in trades:
        intervals.append(
            {
                "entry_time": tr.entry_ts,
                "hold_end": hold_end(tr),
                "entry": float(tr.entry),
                "units": float(tr.units),
                "direction": "BUY" if tr.side == "long" else "SELL",
            }
        )
    if unfinished_pos:
        intervals.append(
            {
                "entry_time": pd.Timestamp(unfinished_pos["entry_time"]),
                "hold_end": after_last,
                "entry": float(unfinished_pos["entry"]),
                "units": float(unfinished_pos["units"]),
                "direction": unfinished_pos["direction"],
            }
        )

    exits_by_day: dict[date, list[Trade]] = {}
    for tr in trades:
        exits_by_day.setdefault(prague_day(tr.exit_ts), []).append(tr)

    equity = START_EQUITY
    flagged = []
    day_float_ratio: dict[date, float] = {}
    worst_ratio = worst_day = None
    for di, d in enumerate(uniq_dates):
        s, e = int(starts[di]), int(ends[di])
        mu = midnights[di]
        next_mu = prague_midnight_utc(date.fromordinal(d.toordinal() + 1))
        day_exits = exits_by_day.get(d, [])
        realized = float(sum(tr.pnl for tr in day_exits))
        float_add = 0.0
        position_open = False
        for pos in intervals:
            if not (pos["entry_time"] < next_mu and pos["hold_end"] > mu):
                continue
            position_open = True
            ref = ref_mid(mu) if pos["entry_time"] <= mu < pos["hold_end"] else float(pos["entry"])
            if ref is None:
                continue
            lo = int(index.searchsorted(pos["entry_time"] if pos["entry_time"] > mu else mu, side="left"))
            hi = int(index.searchsorted(pos["hold_end"] if pos["hold_end"] < next_mu else next_mu, side="left"))
            lo, hi = max(lo, s), min(hi, e)
            if lo < hi:
                if pos["direction"] == "BUY":
                    float_add += pos["units"] * (float(lows[lo:hi].min()) - ref)
                else:
                    float_add += pos["units"] * (ref - float(highs[lo:hi].max()))
        floating = realized + float_add if position_open else realized
        if position_open or day_exits:
            ratio = floating / equity if equity else float("inf")
            day_float_ratio[d] = ratio
            if ratio <= -0.05:
                flagged.append({"day": str(d), "ratio": ratio})
            if worst_ratio is None or ratio < worst_ratio:
                worst_ratio, worst_day = ratio, str(d)
        equity += realized
    return {
        "flagged": len(flagged),
        "flagged_rows": flagged,
        "worst_ratio": worst_ratio,
        "worst_day": worst_day,
        "day_float_ratio": day_float_ratio,
        "final_equity_replay": equity,
    }


def score_windows(booked, floating=None):
    df = booked["df"]
    months = booked["months"]
    daily_rows = booked["daily"]
    flagged_m: dict[str, list] = {}
    if floating:
        for row in floating["flagged_rows"]:
            d = date.fromisoformat(row["day"])
            flagged_m.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(row)
    windows = []
    for i in range(len(COMPLETE) - 2):
        trip = COMPLETE[i : i + 3]
        start_eq = months[trip[0]]["equity_start"] if trip[0] in months else START_EQUITY
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
        closed_day_fail = any(d["ratio"] <= -0.05 for d in days)
        if floating is not None:
            hits = []
            for m in trip:
                hits.extend(flagged_m.get(m, []))
            day_fail = len(hits) > 0
            float_ratios = []
            for m in trip:
                y, mo = map(int, m.split("-"))
                for d, ratio in floating["day_float_ratio"].items():
                    if d.year == y and d.month == mo:
                        float_ratios.append(ratio)
            worst_day = min(float_ratios) if float_ratios else min((d["ratio"] for d in days), default=0.0)
        else:
            day_fail = closed_day_fail
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
                "closed_day_fail": closed_day_fail,
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


def count_pass_windows(trades, day_pnl, day_start_eq, window_days: int, float_ratios=None):
    """≤Nd continuous Challenge+Verify path. Day fail uses floating ratios when provided."""
    if not trades:
        return 0, 0, []
    exits = [(tr.exit_ts, tr.equity_after) for tr in trades]
    all_days = sorted(set(day_start_eq.keys()) | {prague_day(t) for t, _ in exits})
    if float_ratios:
        all_days = sorted(set(all_days) | set(float_ratios.keys()))
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
            if float_ratios is not None and d in float_ratios:
                pct = float_ratios[d]
            elif d in day_pnl and d in day_start_eq and day_start_eq[d] > 0:
                pct = day_pnl[d] / day_start_eq[d]
            else:
                d += timedelta(days=1)
                continue
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
                pnl = pnl_usa30(tr.side, tr.entry, tr.exit, lots)
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


def explorer_summary(win_real, win_zero):
    """SAR has no TIME exits — real == zeroed; still intersect for countable."""
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
    }


def summarize_our_gates(label, booked, data_end, explorer, use_gov: bool, floating):
    trades = booked["trade_objs"]
    day_pnl = booked["day_pnl"]
    day_start_eq = booked["day_start_eq"]
    float_ratios = floating["day_float_ratio"] if floating else None

    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    ext_available = data_end >= EXT_START
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (USA30 feed ends 2026-09-01; no dukas-ext)"

    leave_drop, leave_net = leave_out_two_best_ho(trades)
    max_dd = max_realized_dd(trades)
    closed_worst_d, closed_worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail_closed = days_at_or_below(day_pnl, day_start_eq, DAY_FAIL)

    if floating and floating["worst_ratio"] is not None:
        worst_d = floating["worst_day"]
        worst_pct = float(floating["worst_ratio"])
        n_fail = int(floating["flagged"])
    else:
        worst_d, worst_pct = closed_worst_d, closed_worst_pct
        n_fail = n_fail_closed

    ho_days = (HO_END.normalize() - HO_START).days + 1
    ho_mo = ho_days / 30.44
    ho_pace = ho_net / ho_mo if ho_mo > 0 else 0.0
    fit_days = (FIT_END.normalize() - FIT_START).days + 1
    fit_mo = fit_days / 30.44
    fit_pace = fit_net / fit_mo if fit_mo > 0 else 0.0

    n60, w60, p60 = count_pass_windows(trades, day_pnl, day_start_eq, 60, float_ratios)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90, float_ratios)
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

    if not legal or not has_90:
        decision = "REJECT"
    elif legal and has_90_ho and ho_ok and leave_ok and ext_ok:
        if ext_available and ext_net >= 0:
            decision = "ACCEPT"
        elif not ext_available:
            decision = "CONDITIONAL"
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
        "worst_day_closed": str(closed_worst_d) if closed_worst_d else None,
        "worst_pct_closed": closed_worst_pct,
        "n_fail_days": n_fail,
        "n_fail_days_closed": n_fail_closed,
        "floating_flagged": floating["flagged"] if floating else 0,
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


def write_outputs(book_a, book_b, sens, gen, data_sha, spec_sha, entry30_sha, data_end):
    PACK.mkdir(parents=True, exist_ok=True)
    books = [book_a, book_b]
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
    a("# Candidate 38 — USA30 Wilder Parabolic SAR results")
    a("")
    a(f"- Measured: {datetime.now(ET).strftime('%Y-%m-%d %H:%M %Z')}")
    a(f"- Data sha256: `{data_sha}`")
    a(f"- Spec sha256: `{spec_sha}`")
    a(f"- Gold entry30 preregister sha256: `{entry30_sha}` (mechanics source; not retuned)")
    a(f"- BTC SAR preregister present: `{BTC_SAR_PREREG}` (mirror lane; BTC @0.50% FAIL not re-run)")
    a(f"- Data end: {data_end}")
    a("- Live C4 / drip / FREEZE: **untouched**")
    a(
        "- Costs ASSUMPTION (C22 USA30): contractSize=1, commission=0, spread=2.5 pts"
    )
    a("- Worst Prague day uses **floating** mark (BTC SAR construction; USA30 units=lots×1)")
    a("")
    a("## Lead")
    opens = primary["decision"] == "ACCEPT"
    if opens:
        a(
            f"**ACCEPT — USA30 Wilder SAR opens a ~3mo path on measurement** via "
            f"{primary['label']} (DD {primary['max_dd']*100:.2f}%, HO ~${primary['ho_pace']:,.0f}/mo, "
            f"≤90d HO-era {primary['n90_ho']}, Explorer outside {primary['explorer_countable_outside']})."
        )
    elif primary["decision"] == "CONDITIONAL":
        a(
            f"**CONDITIONAL — USA30 Wilder SAR legal DD + windows, not ACCEPT** via "
            f"{primary['label']} (DD {primary['max_dd']*100:.2f}%, HO ~${primary['ho_pace']:,.0f}/mo, "
            f"≤90d {primary['n90']}/{primary['w90']} HO-era {primary['n90_ho']}, "
            f"leave-out ${primary['leave_net']:,.0f}, Ext {primary['ext_status']})."
        )
    else:
        a(
            f"**REJECT — USA30 Wilder SAR does not open a ~3mo path.** "
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
        a(
            f"| {s['label']} | {gov} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{s['explorer_countable_outside']} | {s['leave_net']:,.0f} | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    a("")

    for s, title in [
        (book_a, "38A USA30 SAR @2.50% (primary)"),
        (book_b, "38B USA30 SAR + soft DD governor"),
        (sens, "Sensitivity @2.60% (NOT verdict)"),
    ]:
        a(f"## {title}")
        a("")
        a("| Metric | Value |")
        a("|---|---|")
        a(f"| Decision | **{s['decision']}** |")
        a(f"| Legal (DD≤10%, floating day&gt;−5%) | {s['legal']} |")
        a(f"| Final equity | ${s['final_equity']:,.2f} |")
        a(f"| Max DD | {s['max_dd']*100:.4f}% |")
        a(
            f"| Worst Prague day (floating) | {s['worst_day']} ({s['worst_pct']*100:.4f}%) |"
        )
        a(
            f"| Worst Prague day (closed-only) | {s['worst_day_closed']} "
            f"({s['worst_pct_closed']*100:.4f}%) |"
        )
        a(f"| Floating flagged days | {s['floating_flagged']} |")
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

    a("## Funnel (SAR generation)")
    a("")
    a(f"```\n{json.dumps(gen['funnel'], indent=2)}\n```")
    a("")
    a("## Does USA30 Wilder SAR open a ~3mo path?")
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
        f"C38 USA30 Wilder SAR → primary={primary['decision']} via {primary['label']} | "
        f"38A={book_a['decision']} DD={book_a['max_dd']*100:.2f}% HO=${book_a['ho_pace']:,.0f}/mo "
        f"90d={book_a['n90']}/{book_a['w90']}(HO={book_a['n90_ho']}) out={book_a['explorer_countable_outside']} "
        f"leave=${book_a['leave_net']:,.0f} legal={book_a['legal']} | "
        f"38B soft={book_b['decision']} DD={book_b['max_dd']*100:.2f}% HO=${book_b['ho_pace']:,.0f}/mo "
        f"90d={book_b['n90']}/{book_b['w90']}(HO={book_b['n90_ho']}) out={book_b['explorer_countable_outside']} "
        f"leave=${book_b['leave_net']:,.0f} legal={book_b['legal']} | "
        f"sens@2.60%={sens['decision']} DD={sens['max_dd']*100:.2f}%\n"
        f"Live C4 untouched. Research only.\n"
    )

    def scrub(d):
        return {k: v for k, v in d.items() if not k.startswith("_")}

    payload = {
        "candidate": 38,
        "label": "USA30 Wilder Parabolic SAR (Gold entry30 / BTC-SAR port) + soft DD governor",
        "not_live": True,
        "data_sha256": data_sha,
        "spec_sha256": spec_sha,
        "entry30_preregister_sha256": entry30_sha,
        "af": {"start": AF_START, "step": AF_STEP, "max": AF_MAX},
        "costs_assumption": {
            "contract_size": CONTRACT_SIZE,
            "spread": SPREAD,
            "commission_per_lot": COMMISSION_PER_LOT,
            "tick_value": TICK_VALUE,
            "note": "C22 USA30 ASSUMPTIONS reused (spread 2.5) — LABEL ASSUMPTIONS",
        },
        "funnel": gen["funnel"],
        "n_reversals": len(gen["reversals"]),
        "book_38A": scrub(book_a),
        "book_38B_soft": scrub(book_b),
        "sensitivity_2_60": scrub(sens),
        "primary": primary["label"],
        "primary_decision": primary["decision"],
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")

    lead = (
        f"**YES — USA30 Wilder SAR opens a deployable ~3mo path** via {primary['label']}."
        if opens
        else (
            f"**CONDITIONAL — USA30 Wilder SAR legal DD + windows, not ACCEPT** via {primary['label']}."
            if primary["decision"] == "CONDITIONAL"
            else "**NO — USA30 Wilder SAR does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows."
        )
    )
    status = []
    sa = status.append
    sa("# BTC FTMO research baseline (2026-10-07)")
    sa("")
    sa(f"**Status: C38 USA30 Wilder SAR — {primary['decision']}** — {lead}")
    sa("")
    sa("_Prior:_ preserved below (C37 / C36 / C35 / …).")
    sa("")
    sa("## Candidate 38")
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

    # Preserve C37 / C36 / earlier sections from root or pack STATUS files
    prior_root = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""
    for cand in (37, 36, 35, 34, 33):
        marker = f"## Candidate {cand}"
        if marker not in prior_root:
            pack_st = OUT_DIR / f"2026-10-07-candidate-{cand}" / "STATUS.md"
            if pack_st.exists():
                prior_root = prior_root + "\n" + pack_st.read_text()
        if marker not in prior_root:
            continue
        chunk_start = prior_root.find(marker)
        rest = prior_root[chunk_start + len(marker):]
        # end at next ## Candidate N or ## Live or EOF
        next_marks = []
        for m in re.finditer(r"(?m)^## (?:Candidate \d+|Live)\b", rest):
            next_marks.append(m.start())
        chunk_end = chunk_start + len(marker) + (next_marks[0] if next_marks else len(rest))
        # if next is Live immediately after this section's table, stop before Live
        sa(prior_root[chunk_start:chunk_end].rstrip())
        sa("")

    sa("## Live")
    sa(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C38 arms without Odin approval. Gold not packaged."
    )
    sa("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")

    pr = []
    pa = pr.append
    pa("## Candidate 38 — USA30 Wilder Parabolic SAR (entry30 / BTC-SAR port)")
    pa("")
    pa("Research only. Broad Odin mandate. Fresh index SAR lane (C27 XAG SAR REJECT; Explorer BTC SAR FAIL). **No deploy.** Live C4 untouched.")
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
    pa("- Mirror of Gold entry30 / Explorer BTC-SAR: AF 0.02/0.02/0.20; reverse-only; both sides")
    pa("- Stop distance = abs(fill − new SAR); no ATR / TP / TIME")
    pa("- 38A risk locked **2.50%** (index lane C22/C32; not BTC 0.50%, not Gold 2.60% retune)")
    pa("- 38B soft gov 2.50→1.25→0.75 + Prague day kill −3% (a-priori)")
    pa("- 2.60% sensitivity readout only — not verdict")
    pa("- USA30 costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.5 pts, USD")
    pa("- Floating Prague day mark for legal/Explorer (BTC SAR construction)")
    pa("- ACCEPT gates = C22–C26 (HO ≤90d is gate; Explorer outside is cross-check)")
    pa("")
    pa("### Paths")
    pa("- Spec: `research/btc/2026-10-07-candidate-38/ftmo-candidate-38.md`")
    pa("- Runner: `research/btc/2026-10-07-candidate-38/run_candidate_38.py`")
    pa("- Results: `research/btc/2026-10-07-candidate-38/candidate-38-results.md`")
    pa("")
    pa("Nothing live. Do not arm without Odin yes.")
    PR_BODY.write_text("\n".join(pr) + "\n")

    for src in [SPEC_PATH, RUNNER, RESULTS, SUMMARY_TXT, RESULTS_JSON, ROOT_STATUS, PR_BODY]:
        if src.exists():
            shutil.copy2(src, PACK / src.name)
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())
    (PACK / "GITHUB-PR-BODY-C38.md").write_text(PR_BODY.read_text())


def main() -> None:
    data_sha = sha256_of(USA30_FEED)
    if data_sha != EXPECTED_SHA:
        raise SystemExit(f"ABORT USA30 sha mismatch: got {data_sha} expected {EXPECTED_SHA}")
    entry30_sha = sha256_of(ENTRY30_PREREG)
    if entry30_sha != ENTRY30_PREREG_SHA:
        raise SystemExit(f"ABORT entry30 prereg sha mismatch: {entry30_sha}")
    if not SPEC_PATH.exists():
        raise SystemExit(f"ABORT missing spec {SPEC_PATH}")
    spec_sha = sha256_of(SPEC_PATH)

    print("loading harness + USA30…", flush=True)
    H = load_harness()
    FTMO_TZ = H.FTMO_TZ
    m1 = H.load_m1(USA30_FEED)
    daily = H.resample(m1, "1D")
    data_end = m1.index[-1]
    print(f"m1={len(m1)} daily={len(daily)} data_end={data_end}", flush=True)

    print("generating Wilder SAR reversals…", flush=True)
    gen = generate_reversals(daily)
    revs = gen["reversals"]
    print(
        f"reversals={len(revs)} openable={sum(1 for r in revs if r['openable'])} funnel={gen['funnel']}",
        flush=True,
    )

    print("booking 38A @ 2.50% (official)…", flush=True)
    real_a = book_reversals(
        revs, gen["unfinished"], risk=RISK_OFFICIAL, soft=False, FTMO_TZ=FTMO_TZ, book_tag="38A@2.50%"
    )
    float_a = floating_audit(m1, real_a["trade_objs"], real_a.get("unfinished_pos"))
    # SAR has no TIME exits — zeroed book identical; re-book for Explorer intersect honesty
    zero_a = book_reversals(
        revs, gen["unfinished"], risk=RISK_OFFICIAL, soft=False, FTMO_TZ=FTMO_TZ, book_tag="38A@2.50%z"
    )
    float_az = floating_audit(m1, zero_a["trade_objs"], zero_a.get("unfinished_pos"))
    win_a = score_windows(real_a, float_a)
    win_az = score_windows(zero_a, float_az)
    exp_a = explorer_summary(win_a, win_az)
    book_a = summarize_our_gates("38A@2.50%", real_a, data_end, exp_a, use_gov=False, floating=float_a)
    book_a["_countable_windows"] = exp_a["countable_windows"]
    book_a["_risk_label"] = "2.50%"
    print(
        f"  38A → {book_a['decision']} DD={book_a['max_dd']*100:.2f}% HO={book_a['ho_pace']:.0f} "
        f"90d={book_a['n90']}/{book_a['w90']}(HO={book_a['n90_ho']}) out={book_a['explorer_countable_outside']} "
        f"float_worst={book_a['worst_pct']*100:.2f}% flagged={book_a['floating_flagged']}",
        flush=True,
    )

    print("booking 38B soft gov…", flush=True)
    real_b = book_reversals(
        revs, gen["unfinished"], risk=None, soft=True, FTMO_TZ=FTMO_TZ, book_tag="38B+soft"
    )
    float_b = floating_audit(m1, real_b["trade_objs"], real_b.get("unfinished_pos"))
    zero_b = book_reversals(
        revs, gen["unfinished"], risk=None, soft=True, FTMO_TZ=FTMO_TZ, book_tag="38B+softz"
    )
    float_bz = floating_audit(m1, zero_b["trade_objs"], zero_b.get("unfinished_pos"))
    win_b = score_windows(real_b, float_b)
    win_bz = score_windows(zero_b, float_bz)
    exp_b = explorer_summary(win_b, win_bz)
    book_b = summarize_our_gates("38B+soft", real_b, data_end, exp_b, use_gov=True, floating=float_b)
    book_b["_countable_windows"] = exp_b["countable_windows"]
    book_b["_risk_label"] = "SOFT"
    print(
        f"  38B → {book_b['decision']} DD={book_b['max_dd']*100:.2f}% HO={book_b['ho_pace']:.0f} "
        f"90d={book_b['n90']}/{book_b['w90']}(HO={book_b['n90_ho']}) out={book_b['explorer_countable_outside']} "
        f"float_worst={book_b['worst_pct']*100:.2f}% flagged={book_b['floating_flagged']}",
        flush=True,
    )

    print("booking sensitivity @ 2.60% (NOT verdict)…", flush=True)
    real_s = book_reversals(
        revs, gen["unfinished"], risk=RISK_SENSITIVITY, soft=False, FTMO_TZ=FTMO_TZ, book_tag="sens@2.60%"
    )
    float_s = floating_audit(m1, real_s["trade_objs"], real_s.get("unfinished_pos"))
    zero_s = book_reversals(
        revs, gen["unfinished"], risk=RISK_SENSITIVITY, soft=False, FTMO_TZ=FTMO_TZ, book_tag="sens@2.60%z"
    )
    float_sz = floating_audit(m1, zero_s["trade_objs"], zero_s.get("unfinished_pos"))
    win_s = score_windows(real_s, float_s)
    win_sz = score_windows(zero_s, float_sz)
    exp_s = explorer_summary(win_s, win_sz)
    sens = summarize_our_gates("sens@2.60%", real_s, data_end, exp_s, use_gov=False, floating=float_s)
    sens["_countable_windows"] = exp_s["countable_windows"]
    sens["_risk_label"] = "2.60% sens"
    print(
        f"  sens → {sens['decision']} DD={sens['max_dd']*100:.2f}% out={sens['explorer_countable_outside']} "
        f"float_worst={sens['worst_pct']*100:.2f}%",
        flush=True,
    )

    write_outputs(book_a, book_b, sens, gen, data_sha, spec_sha, entry30_sha, data_end)
    print("wrote", RESULTS, PACK, flush=True)
    print(SUMMARY_TXT.read_text(), flush=True)


if __name__ == "__main__":
    main()
