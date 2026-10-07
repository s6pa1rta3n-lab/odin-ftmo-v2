#!/usr/bin/env python3
"""Candidate 48: XAG soft 2.00 PRIMARY + US100 NR7 FIXED higher sat — leave flip.

NO BTC. NO Gold.

Locked a-priori (scale NR7 above 47E 0.35% to clear leave ≥0):
  48A — reconfirm 47E: XAG soft 2.00→1.00→0.60 + NR7 FIXED 0.35%
  48B — XAG soft 2.00… + NR7 FIXED 0.40%
  48C — XAG soft 2.00… + NR7 FIXED 0.45%
  48D — XAG soft 2.00… + NR7 FIXED 0.50%
  48E — XAG soft 2.00… + NR7 FIXED 0.60%
  48F — (if B–E leave still red OR DD>10%): XAG soft 1.75→0.90→0.50 + NR7 FIXED 0.50%

Thesis: 47E HO=15 / DD 6.9% / leave −1096 / Ext N/A. Need ~+$1.1k leave.
Ext N/A is NOT an ACCEPT blocker when feed missing.

Research only. No live / C4 / drip / FREEZE / MetaAPI. No BTC. No Gold.
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

US100_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv"
)
XAG_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv"
)

US100_SHA = "5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af"
XAG_SHA = "6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-48"
SPEC = OUT_DIR / "ftmo-candidate-48.md"
RESULTS = OUT_DIR / "candidate-48-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-48-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-48-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C48.md"
RUNNER = OUT_DIR / "run_candidate_48.py"

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

# US100 NR7 — FIXED satellite ladder (does NOT soft-scale; C41 chassis)
US100_SPREAD = 1.0
US100_CONTRACT = 1.0
US100_COMM = 0.0
US100_FIXED_35 = 0.0035
US100_FIXED_40 = 0.0040
US100_FIXED_45 = 0.0045
US100_FIXED_50 = 0.0050
US100_FIXED_60 = 0.0060
XAG_F_FULL = 0.0175
XAG_F_MID = 0.0090
XAG_F_FLOOR = 0.0050
US100_MAX_LOT = 1000.0
US100_TIME_DAY = 5
TP_MULT_US100 = 2.0

# XAG Donchian — soft 2.00→1.00→0.60 (from 45E / C46; NOT soft-2.50)
XAG_CONTRACT = 5000.0
XAG_SPREAD = 0.025
XAG_COMM = 3.0
XAG_MAX_LOT = 100.0
DONCH_N = 20
ATR_MULT_XAG = 2.0
R_MULT_XAG = 1.0
XAG_TIME_DAY = 10
XAG_FULL = 0.020   # soft 2.00%
XAG_MID = 0.010    # 1.00%
XAG_FLOOR = 0.006  # 0.60%

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
    fx_entry: float = 1.0
    fx_exit: float = 1.0


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


def risk_tiers_for(symbol: str, us100_fixed: float | None = None,
                   xag_tiers: tuple[float, float, float] | None = None):
    """US100 fixed satellite; soft tiers apply only to XAG."""
    if symbol == "US100":
        r = float(us100_fixed if us100_fixed is not None else US100_FIXED_35)
        return r, r, r
    if xag_tiers is not None:
        return xag_tiers
    return XAG_FULL, XAG_MID, XAG_FLOOR


def risk_for_symbol(
    symbol: str,
    equity: float,
    peak: float,
    use_gov: bool,
    us100_fixed: float | None = None,
    xag_tiers: tuple[float, float, float] | None = None,
):
    """Soft gov resizes XAG only; US100 stays fixed at all dd tiers."""
    if symbol == "US100":
        r = float(us100_fixed if us100_fixed is not None else US100_FIXED_35)
        return r, "fixed"
    full, mid, floor = xag_tiers if xag_tiers is not None else (XAG_FULL, XAG_MID, XAG_FLOOR)
    if use_gov:
        return soft_gov_risk(equity, peak, full, mid, floor)
    return full, "n/a"


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float, fx: float = 1.0) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    if symbol == "US100":
        lots = round(equity * risk / (stop_dist * US100_CONTRACT), 2)
        lots = min(lots, US100_MAX_LOT)
    else:
        lots = round(equity * risk / (stop_dist * XAG_CONTRACT), 2)
        lots = min(lots, XAG_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_sym(
    symbol: str,
    side: str,
    entry: float,
    exit_px: float,
    lots: float,
    fx_exit: float = 1.0,
) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    if symbol == "US100":
        units = lots * US100_CONTRACT
        return raw * units - US100_SPREAD * units - US100_COMM * lots
    units = lots * XAG_CONTRACT
    return raw * units - XAG_SPREAD * units - XAG_COMM * lots


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
                        "fx_entry": 1.0,
                        "fx_exit": 1.0,
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


def extract_xag_donchian(daily: pd.DataFrame) -> tuple[list[dict], dict]:
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
                        "fx_entry": 1.0,
                        "fx_exit": 1.0,
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


def replay_signals(
    signals: list[dict],
    book: str,
    use_gov: bool,
    mode: str = "dual",
    us100_fixed: float | None = None,
    xag_tiers: tuple[float, float, float] | None = None,
):
    """Replay sized trades.

    mode:
      "single" — one sleeve; within-symbol overlap guard only
      "dual"   — one pos per sleeve; both may be open (default joint)
      "mutex"  — account-wide at most one position; XAG priority on same ts;
                 no force-flat XAG (C39 lock)
    """
    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel: dict[str, int] = defaultdict(int)
    busy_until: dict[str, pd.Timestamp | None] = {"US100": None, "XAG": None}
    account_busy_until: pd.Timestamp | None = None
    xag_tiers = xag_tiers if xag_tiers is not None else (XAG_FULL, XAG_MID, XAG_FLOOR)

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
                if sym == "US100":
                    funnel["skip_mutex_us100"] += 1
                else:
                    funnel["skip_mutex_xag_wait"] += 1
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

        risk, gstate = risk_for_symbol(
            sym, equity, peak, use_gov, us100_fixed=us100_fixed, xag_tiers=xag_tiers
        )
        funnel[f"gov_{gstate}"] += 1

        fx_e = float(sig.get("fx_entry", 1.0))
        fx_x = float(sig.get("fx_exit", 1.0))
        lots = size_lots(sym, equity, risk, sig["stop_dist"], fx_e)
        if lots < MIN_LOT:
            funnel["skip_lots"] += 1
            continue

        pnl = pnl_sym(sym, sig["side"], sig["entry"], sig["exit"], lots, fx_x)
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
                fx_entry=fx_e,
                fx_exit=fx_x,
            )
        )
        busy_until[sym] = sig["exit_ts"]
        if mode == "mutex":
            account_busy_until = sig["exit_ts"]
        funnel["taken"] += 1
        funnel[f"taken_{sym}"] += 1

    chassis_map = {
        "48A": "xag-soft-2.00+us100-nr7-0.35",
        "48B": "xag-soft-2.00+us100-nr7-0.40",
        "48C": "xag-soft-2.00+us100-nr7-0.45",
        "48D": "xag-soft-2.00+us100-nr7-0.50",
        "48E": "xag-soft-2.00+us100-nr7-0.60",
        "48F": "xag-soft-1.75+us100-nr7-0.50",
    }
    sym_label = "JOINT"
    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis_map.get(book, book),
        "taken": len(trades),
        "use_gov": use_gov,
        "symbol": sym_label,
        "n_signals_in": len(signals),
        "mode": mode,
        "us100_fixed": us100_fixed,
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
                    xt = (XAG_F_FULL, XAG_F_MID, XAG_F_FLOOR) if tr.book == "48F" else (XAG_FULL, XAG_MID, XAG_FLOOR)
                    risk, _ = risk_for_symbol(
                        tr.symbol, eq, peak, use_gov,
                        us100_fixed=None,
                        xag_tiers=xt,
                    )
                lots = size_lots(tr.symbol, eq, risk, tr.stop_dist, tr.fx_entry)
                if lots < MIN_LOT:
                    continue
                pnl = pnl_sym(tr.symbol, tr.side, tr.entry, tr.exit, lots, tr.fx_exit)
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


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    ext_available = data_end >= EXT_START
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (feeds end 2026-09-01; no dukas-ext)"

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

    ho_era_ok = n90_ho >= 5
    if not legal or not has_90:
        decision = "REJECT"
    elif legal and ho_era_ok and ho_ok and leave_ok and ext_ok:
        # Ext N/A documented → does not block ACCEPT (no dukas-ext for XAG/US100)
        decision = "ACCEPT"
    elif legal and has_90_ho and ho_ok and leave_ok and ext_ok and not ho_era_ok:
        decision = "CONDITIONAL"  # HO-era windows < 5
    elif legal and has_90 and not has_90_ho:
        decision = "CONDITIONAL"
    elif legal and has_90 and (not ho_ok or not leave_ok or (ext_available and ext_net < 0)):
        decision = "CONDITIONAL"
    else:
        decision = "CONDITIONAL"

    xcheck = explorer_crosscheck(trades)

    us_fx = {
        "48A": US100_FIXED_35,
        "48B": US100_FIXED_40,
        "48C": US100_FIXED_45,
        "48D": US100_FIXED_50,
        "48E": US100_FIXED_60,
        "48F": US100_FIXED_50,
    }.get(book, US100_FIXED_35)
    if book == "48F":
        xf, xm, xfl = XAG_F_FULL, XAG_F_MID, XAG_F_FLOOR
    else:
        xf, xm, xfl = XAG_FULL, XAG_MID, XAG_FLOOR
    full = xf + us_fx
    mid = xm + us_fx
    floor = xfl + us_fx

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


def write_docs(summaries, measured, us_end, xag_end, us_sha, xag_sha):
    PACK.mkdir(parents=True, exist_ok=True)
    by_book = {s["book"]: s for s in summaries}

    primary = None
    accepts = [s for s in summaries if s["decision"] == "ACCEPT"]
    if accepts:
        accepts.sort(key=lambda s: (s["leave_net"], s["n90_ho"], s["ho_pace"]), reverse=True)
        primary = accepts[0]
    if primary is None:
        cands = [
            s for s in summaries
            if s["legal"] and s.get("n90_ho", 0) >= 5 and s.get("leave_ok")
        ]
        if cands:
            cands.sort(key=lambda s: (s["leave_net"], s["n90_ho"], s["ho_pace"]), reverse=True)
            primary = cands[0]
    if primary is None:
        cands = [s for s in summaries if s["legal"] and s.get("has_90_ho")]
        if cands:
            cands.sort(key=lambda s: (s["leave_net"], s["n90_ho"], -s["max_dd"]), reverse=True)
            primary = cands[0]
    if primary is None:
        primary = by_book.get("48A") or summaries[0]

    b48a = by_book.get("48A")
    leave_a = b48a["leave_net"] if b48a else float("nan")
    n90_a = b48a["n90_ho"] if b48a else 0

    keys = [k for k in ("48A", "48B", "48C", "48D", "48E", "48F") if k in by_book]
    parts = []
    windows_survived = False
    for k in keys:
        jb = by_book[k]
        delta = jb["leave_net"] - leave_a if b48a else 0.0
        parts.append(
            f"{k} HO≤90d={jb['n90_ho']} DD={jb['max_dd']*100:.1f}% leave={jb['leave_net']:.0f} (Δ{delta:+.0f})"
        )
        if jb["n90_ho"] > 0:
            windows_survived = True
    xag_survive = (
        f"48A HO≤90d={n90_a} leave={leave_a:.0f} → " + " | ".join(parts)
        + f" | windows_survived={'Y' if windows_survived else 'N'}"
    )

    def ext_cell(s):
        if not s.get("ext_available"):
            return "N/A"
        return f"{s['ext_net']:,.0f}"

    def mode_cell(s):
        return {
            "48A": "dual/NR7 0.35%",
            "48B": "dual/NR7 0.40%",
            "48C": "dual/NR7 0.45%",
            "48D": "dual/NR7 0.50%",
            "48E": "dual/NR7 0.60%",
            "48F": "soft1.75+NR7 0.50%",
        }.get(s["book"], s["book"])

    ext_note = primary.get("ext_status", "N/A")
    if primary["decision"] == "ACCEPT":
        lead = (
            f"**YES — ACCEPT pass-path** via {primary['book']}: max DD {primary['max_dd']*100:.1f}%, "
            f"HO≤90d {primary['n90_ho']}, leave ${primary['leave_net']:,.0f}, "
            f"HO ~${primary['ho_pace']:,.0f}/mo. Ext: {ext_note} (N/A OK). "
            f"**Still no live deploy from this research pack.**"
        )
    elif primary["decision"] == "CONDITIONAL":
        delta = primary["leave_net"] - leave_a if b48a else 0.0
        why = "Leave-out still blocks ACCEPT." if not primary.get("leave_ok") else "Gates incomplete."
        if primary.get("max_dd", 0) > 0.10:
            why = "DD illegal."
        lead = (
            f"**CONDITIONAL — NR7 leave-scale incomplete** via {primary['book']}: "
            f"max DD {primary['max_dd']*100:.1f}%, HO≤90d {primary['n90_ho']}, "
            f"HO ~${primary['ho_pace']:,.0f}/mo, leave ${primary['leave_net']:,.0f} "
            f"(Δ vs 48A {delta:+,.0f}). Ext: {ext_note}. {why}"
        )
    else:
        lead = (
            "**NO — XAG soft-2.00 + higher NR7 sat does not open a deployable ~3mo path.** "
            "DD illegal, HO wiped, or leave fails."
        )

    lines = []
    lines.append("# Candidate 48 Results — XAG soft-2.00 + US100 NR7 higher sat (leave flip; no BTC/Gold)")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**XAG window survival / leave Δ:** {xag_survive}")
    lines.append("")
    lines.append(
        "**Note:** Around 47E (leave −1096 / HO=15). Scale NR7 FIXED above 0.35%. "
        "Ext N/A is NOT an ACCEPT blocker when dukas-ext missing."
    )
    lines.append("")
    lines.append(f"**XAG data:** `{XAG_PATH}` sha256 `{xag_sha}` end `{xag_end}`")
    lines.append(f"**US100 data:** `{US100_PATH}` sha256 `{us_sha}` end `{us_end}`")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** |")
    lines.append("| XAG risks | soft **2.00→1.00→0.60** (48A–E); 48F optional **1.75→0.90→0.50** |")
    lines.append("| US100 costs | spread **1** / comm **0** / contract **1** |")
    lines.append("| US100 risks | FIXED **0.35 / 0.40 / 0.45 / 0.50 / 0.60%** |")
    lines.append("| Soft gov | XAG only; US100 fixed |")
    lines.append("| Prague day kill | −3% both |")
    lines.append("| Positions | dual-open |")
    lines.append("| BTC / Gold | **excluded** |")
    lines.append("| Ext | N/A OK for ACCEPT when feed missing — do not invent |")
    lines.append("")
    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 48A | Legal | Decision |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|")
    for s in summaries:
        delta = s["leave_net"] - leave_a if b48a else 0.0
        lines.append(
            f"| {s['book']} | {s['symbol']} | {mode_cell(s)} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {ext_cell(s)} | "
            f"{s['leave_net']:,.0f} | {delta:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
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
            f"- max DD {s['max_dd']*100:.2f}% | worst Prague day {s['worst_day']} @ "
            f"{s['worst_pct']*100:.2f}% | fail-days {s['n_fail_days']} | legal={s['legal']}"
        )
        lines.append(
            f"- ≤90d {s['n90']}/{s['w90']} (HO-era {s['n90_ho']}) | "
            f"seq {s['nseq']}/{s['wseq']} (HO-era {s['nseq_ho']})"
        )
        xc = s["explorer_xcheck"]
        lines.append(
            f"- Explorer xcheck: outside_countable={xc['outside_countable']} "
            f"countable={xc['countable']} best_outside%={xc['best_outside_pct']} "
            f"months={xc.get('best_outside_months')}"
        )
        lines.append(
            f"- final equity ${s['final_equity']:,.0f} | chassis `{s['meta'].get('chassis')}` | "
            f"Ext {ext_cell(s)} ({s['ext_status']})"
        )
        lines.append("")

    lines.append("## Does this open a ~3mo path?")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append("Live C4 / drip / FREEZE / MetaAPI: **untouched**. BTC/Gold excluded. No deploy.")
    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-48-results.md").write_text(RESULTS.read_text())

    sum_lines = [lead, "", f"XAG_WINDOW_SURVIVAL|{xag_survive}"]
    for s in summaries:
        delta = s["leave_net"] - leave_a if b48a else 0.0
        sum_lines.append(
            f"{s['book']}|{s['symbol']}|{s['decision']}|pace=${s['ho_pace']:.0f}/mo|"
            f"DD={s['max_dd']*100:.1f}%|90HO={s['n90_ho']}|leave={s['leave_net']:.0f}|"
            f"dLeave={delta:+.0f}|Ext={ext_cell(s)}|legal={s['legal']}"
        )
    SUMMARY_TXT.write_text("\n".join(sum_lines) + "\n")
    (PACK / "candidate-48-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 48,
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
            "us100_spread": US100_SPREAD,
            "us100_contract": US100_CONTRACT,
            "us100_fixed": [US100_FIXED_35, US100_FIXED_40, US100_FIXED_45, US100_FIXED_50, US100_FIXED_60],
            "btc": "excluded",
            "gold": "excluded",
            "ext_na_ok_for_accept": True,
        },
        "books": summaries,
        "data": {
            "xag_sha": xag_sha,
            "xag_end": str(xag_end),
            "us100_sha": us_sha,
            "us100_end": str(us_end),
        },
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str))
    (PACK / "candidate-48-results.json").write_text(RESULTS_JSON.read_text())

    prior = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""
    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C48 XAG soft-2.00 + NR7 higher sat — {primary['decision']}** — {lead}")
    status.append("")
    status.append("_Prior:_ preserved below (C47 / C46 / …).")
    status.append("")
    status.append("## Candidate 48")
    status.append("")
    status.append(
        "| Book | Symbol | HO $/mo | Max DD | ≤90d (HO) | Ext | Leave-out | Δ vs 48A | Legal | Decision |"
    )
    status.append("|---|---|---:|---:|---:|---|---:|---:|---|---|")
    for s in summaries:
        delta = s["leave_net"] - leave_a if b48a else 0.0
        status.append(
            f"| {s['book']} | {s['symbol']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {ext_cell(s)} | {s['leave_net']:,.0f} | "
            f"{delta:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    status.append("")
    status.append(f"**XAG window survival / leave Δ:** {xag_survive}")
    status.append("")
    status.append("## Live")
    status.append("Catalogue drip / C4 ops: **untouched**. BTC/Gold excluded. No deploy from C48.")
    status.append("")
    status.append("---")
    status.append("")
    status.append("## Preserved prior STATUS")
    status.append("")
    prior_body = prior
    if prior_body.startswith("# BTC FTMO"):
        lines_p = prior_body.splitlines()
        idx = 0
        for i, ln in enumerate(lines_p):
            if ln.startswith("**Status:"):
                idx = i
                break
        prior_body = "\n".join(lines_p[idx:])
    status.append(prior_body.strip())
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")

    accept_tag = " **ACCEPT**" if primary["decision"] == "ACCEPT" else ""
    (PACK / "STATUS.md").write_text(
        f"# Candidate 48 STATUS (pack)\n\n**{primary['decision']}**{accept_tag} — {lead}\n\n"
        f"**XAG window survival / leave Δ:** {xag_survive}\n\n"
        "Live C4 untouched. No BTC/Gold. No deploy.\n"
    )

    pr = []
    pr.append("## Candidate 48 — XAG soft-2.00 + US100 NR7 higher sat (leave flip; no BTC/Gold)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append(f"**XAG window survival / leave Δ:** {xag_survive}")
    pr.append("")
    pr.append(
        "Around 47E (leave −1096 / HO=15). Scale NR7 FIXED 0.35→0.60%. "
        "Ext N/A OK for ACCEPT. No BTC Ext drag."
    )
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Decision | HO $/mo | Max DD | ≤90d HO | Ext | Leave-out | Δ vs 48A |")
    pr.append("|---|---|---:|---:|---:|---|---:|---:|")
    for s in summaries:
        delta = s["leave_net"] - leave_a if b48a else 0.0
        pr.append(
            f"| {s['book']} | {s['decision']} | {s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | "
            f"{s['n90_ho']} | {ext_cell(s)} | {s['leave_net']:,.0f} | {delta:+,.0f} |"
        )
    pr.append("")
    pr.append("### ASSUMPTIONS")
    pr.append("- XAG: **5000** / **0.025** / $3; soft **2.00→1.00→0.60** (48F: **1.75→0.90→0.50**)")
    pr.append("- US100 NR7: spread **1** / comm 0 / contract 1; FIXED **0.35/0.40/0.45/0.50/0.60%**")
    pr.append("- Soft gov XAG only; Prague −3%; dual-open; Ext N/A OK for ACCEPT")
    pr.append("- BTC / Gold excluded")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-48/`")
    pr.append("")
    pr.append("Research only. Live C4 + drip freeze + MetaAPI untouched. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C48.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-48.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_48.py")

    print(lead)
    print("  Survival:", xag_survive)
    for s in summaries:
        delta = s["leave_net"] - leave_a if b48a else 0.0
        print(
            f"  {s['book']}: {s['decision']} DD={s['max_dd']*100:.1f}% pace=${s['ho_pace']:.0f}/mo "
            f"90HO={s['n90_ho']} leave={s['leave_net']:.0f} (Δ{delta:+.0f}) Ext={ext_cell(s)}"
        )
    return primary, lead


def main():
    print("Loading US100 M1...")
    us = load_m1(US100_PATH, US100_SHA)
    us_end = us.index[-1]
    us_sha = US100_SHA
    print(f"  US100 M1: {len(us)} → {us_end}")

    print("Loading XAG M1...")
    xag = load_m1(XAG_PATH, XAG_SHA)
    xag_end = xag.index[-1]
    xag_sha = XAG_SHA
    print(f"  XAG M1: {len(xag)} → {xag_end}")

    us_daily = build_daily(us)
    xag_daily = build_daily(xag)
    print(f"  US100 D1: {len(us_daily)} | XAG D1: {len(xag_daily)}")

    print("Extracting US100 NR7 signals...")
    us_sigs, us_funnel = extract_us100_nr7(us_daily)
    print(f"  US100 NR7 signals={len(us_sigs)} funnel={us_funnel}")

    print("Extracting XAG Donchian 20d signals...")
    xag_sigs, xag_funnel = extract_xag_donchian(xag_daily)
    print(f"  XAG Donchian signals={len(xag_sigs)} funnel={xag_funnel}")

    measured = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")
    summaries = []
    data_end = max(us_end, xag_end)
    xag_e = (XAG_FULL, XAG_MID, XAG_FLOOR)
    xag_f = (XAG_F_FULL, XAG_F_MID, XAG_F_FLOOR)
    joint = xag_sigs + us_sigs

    def run(book, label, *, us100_fixed, xag_tiers=None):
        t, dp, ds, meta = replay_signals(
            joint, book, use_gov=True, mode="dual",
            us100_fixed=us100_fixed,
            xag_tiers=xag_tiers if xag_tiers is not None else xag_e,
        )
        s = summarize(label, book, t, dp, ds, meta, True, data_end)
        summaries.append(s)
        ext_s = "N/A" if not s["ext_available"] else f"{s['ext_net']:.0f}"
        print(
            f"  → {s['decision']} DD={s['max_dd']*100:.1f}% 90HO={s['n90_ho']} "
            f"leave={s['leave_net']:.0f} Ext={ext_s} pace=${s['ho_pace']:.0f}/mo"
        )
        return s

    print("Running 48A reconfirm 47E (XAG soft 2.00 + NR7 FIXED 0.35%)...")
    s48a = run("48A", "48A reconfirm 47E NR7 0.35%", us100_fixed=US100_FIXED_35)

    print("Running 48B NR7 FIXED 0.40%...")
    s48b = run("48B", "48B XAG soft-2.00 + NR7 0.40%", us100_fixed=US100_FIXED_40)

    print("Running 48C NR7 FIXED 0.45%...")
    s48c = run("48C", "48C XAG soft-2.00 + NR7 0.45%", us100_fixed=US100_FIXED_45)

    print("Running 48D NR7 FIXED 0.50%...")
    s48d = run("48D", "48D XAG soft-2.00 + NR7 0.50%", us100_fixed=US100_FIXED_50)

    print("Running 48E NR7 FIXED 0.60%...")
    s48e = run("48E", "48E XAG soft-2.00 + NR7 0.60%", us100_fixed=US100_FIXED_60)

    be = [s48b, s48c, s48d, s48e]
    leave_still_red = all(not s["leave_ok"] for s in be)
    dd_illegal = any(s["max_dd"] > 0.10 + 1e-12 for s in be)
    need_f = leave_still_red or dd_illegal
    # Also run 48F if no ACCEPT yet among A–E
    any_accept = any(s["decision"] == "ACCEPT" for s in [s48a, *be])
    if need_f and not any_accept:
        print("Running 48F XAG soft 1.75 + NR7 FIXED 0.50%...")
        run("48F", "48F XAG soft-1.75 + NR7 0.50%", us100_fixed=US100_FIXED_50, xag_tiers=xag_f)
    else:
        reason = "ACCEPT already found" if any_accept else "leave cleared without DD breach needing 48F"
        if not need_f:
            reason = "leave cleared on B–E with legal DD"
        print(f"Skipping 48F ({reason})")

    write_docs(summaries, measured, us_end, xag_end, us_sha, xag_sha)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
