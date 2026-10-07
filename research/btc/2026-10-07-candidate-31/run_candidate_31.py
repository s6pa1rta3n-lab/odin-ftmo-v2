#!/usr/bin/env python3
"""Candidate 31: Joint US100 NR7 @1% + JPN225 Keltner55 @2.50% (Explorer re-chassis).

Locked a-priori (not a fishing grid):
  31A — US100 NR7 alone @1.00% soft 1.00→0.50→0.25
  31B — JPN225 Keltner alone @2.50% soft 2.50→1.25→0.625
  31C — joint ungoverened (full risks always)
  31D — joint + soft gov (verdict)

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

PRAGUE = ZoneInfo("Europe/Prague")

US100_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv"
)
JPN_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/jpnidxjpy-m1-bid-2024-01-01-2026-09-02.csv"
)
USDJPY_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv"
)
USA30_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usa30idxusd-m1-bid-2024-01-01-2026-09-02.csv"
)

US100_SHA = "5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af"
JPN_SHA = "b7e9a85045eba935ead5812f13d461ba919f60d8220581671bfaf0b66ab82a6e"
USDJPY_SHA = "ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca"
USA30_SHA = "968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-31"
SPEC = OUT_DIR / "ftmo-candidate-31.md"
RESULTS = OUT_DIR / "candidate-31-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-31-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-31-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C31.md"
RUNNER = OUT_DIR / "run_candidate_31.py"

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

# JPN225 Keltner (catalogue JP225.cash)
JPN_CONTRACT = 10.0  # catalogue
JPN_SPREAD = 8.0  # ASSUMPTION — feed missing
JPN_COMM = 0.0  # catalogue
JPN_FULL = 0.025
JPN_MID = 0.0125
JPN_FLOOR = 0.00625
JPN_MAX_LOT = 200.0  # catalogue maxTradeVolume

# USA30 fallback (if JPN blocked)
USA30_CONTRACT = 1.0
USA30_SPREAD = 2.5  # ASSUMPTION from C22
USA30_COMM = 0.0
USA30_MAX_LOT = 1000.0

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

# Runtime: which index sleeve ran
INDEX_SYMBOL = "JPN225"  # or USA30
INDEX_CONTRACT = JPN_CONTRACT
INDEX_SPREAD = JPN_SPREAD
INDEX_COMM = JPN_COMM
INDEX_MAX_LOT = JPN_MAX_LOT
USE_FX = True  # JPY→USD


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


def build_fx_mid(usdjpy_m1: pd.DataFrame) -> pd.Series:
    mid = (usdjpy_m1["high"] + usdjpy_m1["low"]) / 2.0
    return mid.sort_index()


def fx_asof(fx_mid: pd.Series, ts: pd.Timestamp) -> float:
    if fx_mid is None or len(fx_mid) == 0:
        return 1.0
    i = int(fx_mid.index.searchsorted(ts, side="right")) - 1
    if i < 0:
        i = 0
    v = float(fx_mid.iloc[i])
    if not np.isfinite(v) or v <= 0:
        raise SystemExit(f"bad USDJPY mid at {ts}: {v}")
    return v


def risk_tiers_for(symbol: str):
    if symbol == "US100":
        return US100_FULL, US100_MID, US100_FLOOR
    return JPN_FULL, JPN_MID, JPN_FLOOR


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float, fx: float) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    if symbol == "US100":
        lots = round(equity * risk / (stop_dist * US100_CONTRACT), 2)
        lots = min(lots, US100_MAX_LOT)
    else:
        # JPY risk per lot = stop_dist * contract; USD = that / fx
        jpy_per_lot = stop_dist * INDEX_CONTRACT
        usd_per_lot = jpy_per_lot / fx if USE_FX else jpy_per_lot
        if usd_per_lot <= 0:
            return 0.0
        lots = round(equity * risk / usd_per_lot, 2)
        lots = min(lots, INDEX_MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_sym(
    symbol: str,
    side: str,
    entry: float,
    exit_px: float,
    lots: float,
    fx_exit: float,
) -> float:
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    if symbol == "US100":
        units = lots * US100_CONTRACT
        return raw * units - US100_SPREAD * units - US100_COMM * lots
    units = lots * INDEX_CONTRACT
    jpy = raw * units - INDEX_SPREAD * units - INDEX_COMM * lots
    if USE_FX:
        return jpy / fx_exit
    return jpy  # USA30 USD path: treat as USD 1:1


def extract_us100_nr7(daily: pd.DataFrame) -> list[dict]:
    """Exact Explorer US100 NR7 (no sizing)."""
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
                        target = fill + TP_MULT * sl_dist if side == "long" else fill - TP_MULT * sl_dist
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
            if day_num > TIME_DAY:
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


def extract_keltner(daily: pd.DataFrame, symbol: str, fx_mid: pd.Series | None) -> list[dict]:
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
    funnel = defaultdict(int)

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
                fx_e = fx_asof(fx_mid, position["entry_ts"]) if fx_mid is not None else 1.0
                fx_x = fx_asof(fx_mid, exit_ts) if fx_mid is not None else 1.0
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
                        "fx_entry": fx_e,
                        "fx_exit": fx_x,
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
    busy_until: dict[str, pd.Timestamp | None] = {"US100": None, INDEX_SYMBOL: None}

    # JPN then US100 on same timestamp (Gold-then-US100 pattern)
    def sort_key(s):
        pri = 0 if s["symbol"] != "US100" else 1
        return (s["entry_ts"], pri)

    ordered = sorted(signals, key=sort_key)

    for sig in ordered:
        sym = sig["symbol"]
        if allow_simultaneous:
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
        funnel["taken"] += 1
        funnel[f"taken_{sym}"] += 1

    chassis_map = {
        "31A": f"us100-nr7-1.00" + ("+softgov" if use_gov else ""),
        "31B": f"{INDEX_SYMBOL.lower()}-keltner55-2.50" + ("+softgov" if use_gov else ""),
        "31C": f"us100nr7+{INDEX_SYMBOL.lower()}-joint-ungov",
        "31D": f"us100nr7+{INDEX_SYMBOL.lower()}-joint+softgov",
    }
    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis_map.get(book, book),
        "taken": len(trades),
        "use_gov": use_gov,
        "symbol": "JOINT" if book in ("31C", "31D") else ("US100" if book == "31A" else INDEX_SYMBOL),
        "n_signals_in": len(signals),
        "index_symbol": INDEX_SYMBOL,
        "use_fx": USE_FX,
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
    """Explorer 30 Prague month-triplet outside + TIME-zero countable cross-check."""
    if not trades:
        return {
            "countable": 0,
            "outside": 0,
            "best_outside_pct": None,
            "best_outside_months": None,
            "dd": 0.0,
            "final": START_EQUITY,
        }
    rows = []
    for seq, tr in enumerate(trades):
        pnl = 0.0 if (zero_time and tr.reason == "TIME") else tr.pnl
        # For TIME-zero we need to rebuild equity path — recompute from raw template
        rows.append(
            {
                "exit_ts": tr.exit_ts,
                "entry_ts": tr.entry_ts,
                "pnl_raw": tr.pnl,
                "reason": tr.reason,
                "symbol": tr.symbol,
                "side": tr.side,
                "entry": tr.entry,
                "exit": tr.exit,
                "lots": tr.lots,
                "stop_dist": tr.stop_dist,
                "fx_entry": tr.fx_entry,
                "fx_exit": tr.fx_exit,
                "risk_used": tr.risk_used,
                "seq": seq,
            }
        )

    # Rebuild with TIME-zero if needed using stored lots (same size path as real book)
    equity = START_EQUITY
    peak = START_EQUITY
    max_dd = 0.0
    booked = []
    for r in sorted(rows, key=lambda x: (x["exit_ts"], x["seq"])):
        pnl = 0.0 if (zero_time and r["reason"] == "TIME") else r["pnl_raw"]
        # Note: TIME-zero Explorer zeros TIME PnL but keeps costs in the zero —
        # Explorer sets entire TIME pnl to 0 including costs. Match that.
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
        "dd": -max_dd,  # signed like Explorer
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
        ext_status = "UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext)"

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

    if book == "31A":
        full, mid, floor = US100_FULL, US100_MID, US100_FLOOR
    elif book == "31B":
        full, mid, floor = JPN_FULL, JPN_MID, JPN_FLOOR
    else:
        full = US100_FULL + JPN_FULL
        mid = US100_MID + JPN_MID
        floor = US100_FLOOR + JPN_FLOOR

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


def write_docs(summaries, measured, us_end, idx_end, us_sha, idx_sha, fx_sha):
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
    elif legal_with_90:
        legal_with_90.sort(key=lambda s: (-(s["n90"] + s["nseq"]), -s["ho_pace"]))
        primary = legal_with_90[0]
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

    opens = primary["decision"] == "ACCEPT"
    if opens:
        lead = (
            f"**YES — US100 NR7 + {INDEX_SYMBOL} Keltner55 opens a deployable ~3mo path** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — US100 NR7 + {INDEX_SYMBOL} Keltner55 legal DD + windows, not ACCEPT** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo."
        )
    else:
        lead = (
            f"**NO — US100 NR7 + {INDEX_SYMBOL} Keltner55 does not open a deployable ~3mo path.** "
            f"DD illegal, HO≤0, or zero ≤90d windows."
        )

    lines = []
    lines.append(f"# Candidate 31 Results — US100 NR7 + {INDEX_SYMBOL} Keltner55 (Explorer re-chassis)")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**Index sleeve ran:** `{INDEX_SYMBOL}` (USE_FX={USE_FX})")
    lines.append(f"**US100 data:** `{US100_PATH}` sha256 `{us_sha}` end `{us_end}`")
    lines.append(f"**Index data end:** `{idx_end}` sha `{idx_sha}`")
    if USE_FX:
        lines.append(f"**USDJPY FX:** `{USDJPY_PATH}` sha256 `{fx_sha}` (mid for JPY→USD)")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| JP225.cash contractSize | **10** (catalogue) |")
    lines.append("| JP225.cash commission | **0** (catalogue) |")
    lines.append("| JP225.cash spread | **8.0** pts (**ASSUMPTION** — feed missing) |")
    lines.append("| JPY→USD | USDJPY M1 mid at entry (size) and exit (PnL) |")
    lines.append("| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |")
    lines.append("| Soft gov | dd<5% full; 5–8% half; ≥8% quarter; never sticky-block |")
    lines.append("| Prague day kill | −3% both sleeves |")
    lines.append("| Max positions | one per sleeve (two simultaneous OK) |")
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
    lines.append("Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-31-results.md").write_text(RESULTS.read_text())

    summary_lines = [lead, ""]
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
    (PACK / "candidate-31-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 31,
        "index_symbol": INDEX_SYMBOL,
        "use_fx": USE_FX,
        "measured": measured,
        "lead": lead,
        "primary": primary["book"],
        "decision": primary["decision"],
        "assumptions": {
            "jpn_contract": INDEX_CONTRACT,
            "jpn_spread": INDEX_SPREAD,
            "jpn_commission": INDEX_COMM,
            "us100_spread": US100_SPREAD,
            "fx": "USDJPY mid" if USE_FX else "N/A (USA30 USD)",
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
            "index_sha": idx_sha,
            "index_end": str(idx_end),
            "fx_sha": fx_sha,
        },
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (PACK / "candidate-31-results.json").write_text(RESULTS_JSON.read_text())

    # STATUS: append C31; preserve C30 if pack exists
    c30_note = ""
    c30_pack_status = OUT_DIR / "2026-10-07-candidate-30" / "STATUS.md"
    if c30_pack_status.exists():
        c30_note = c30_pack_status.read_text().strip() + "\n\n---\n\n"

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C31 US100 NR7 + {INDEX_SYMBOL} Keltner55 — {primary['decision']}** — {lead}")
    status.append("")
    if c30_note:
        status.append("## Prior: Candidate 30 (preserved)")
        status.append("")
        # pull the C30 table lines only
        for line in c30_pack_status.read_text().splitlines():
            if line.startswith("# BTC"):
                continue
            if line.startswith("**Status: C30"):
                status.append(line)
            elif line.startswith("|") or line.startswith("## Candidate 30") or line.startswith("## Live"):
                if line.startswith("## Live"):
                    break
                status.append(line)
        status.append("")
    status.append("## Candidate 31")
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
    status.append("## Live")
    status.append(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C31 arms without Odin approval. Gold not packaged."
    )
    status.append("")
    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(ROOT_STATUS.read_text())

    pr = []
    pr.append(f"## Candidate 31 — US100 NR7 @1% + {INDEX_SYMBOL} Keltner55 @2.50% (Explorer re-chassis)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append(
        "Locked a-priori re-chassis of Explorer joint US100-NR7 + Gold-Keltner55: keep US100 NR7, "
        f"replace Gold with {INDEX_SYMBOL} Keltner55 (entry55 params), soft gov on shared equity."
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
    pr.append(f"- Index sleeve: **{INDEX_SYMBOL}** (JPN225 preferred; USA30 only if JPN blocked)")
    pr.append("- JP225.cash: contractSize=10, commission=0 (catalogue); spread **8.0 ASSUMPTION**")
    pr.append("- JPY→USD via USDJPY M1 mid" if USE_FX else "- USA30 USD path (no FX)")
    pr.append("- Soft gov: dd<5% full / 5–8% half / ≥8% quarter; Prague −3% kill both")
    pr.append("- One pos/sleeve; joint may hold both open")
    pr.append("")
    pr.append("Research only. Live C4 + drip freeze + MetaAPI untouched. Do not package Gold. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C31.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-31.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_31.py")

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
    global INDEX_SYMBOL, INDEX_CONTRACT, INDEX_SPREAD, INDEX_COMM, INDEX_MAX_LOT, USE_FX

    print("Loading US100 M1...")
    us = load_m1(US100_PATH, US100_SHA)
    us_end = us.index[-1]
    us_sha = US100_SHA
    print(f"  US100 M1: {len(us)} → {us_end}")

    print("Loading JPN225 M1...")
    try:
        jpn = load_m1(JPN_PATH, JPN_SHA)
        print(f"  JPN225 M1: {len(jpn)} → {jpn.index[-1]}")
        print("Loading USDJPY M1 for JPY→USD...")
        usdjpy = load_m1(USDJPY_PATH, USDJPY_SHA)
        fx_mid = build_fx_mid(usdjpy)
        fx_sha = USDJPY_SHA
        print(f"  USDJPY M1: {len(usdjpy)} mid points={len(fx_mid)}")
        INDEX_SYMBOL = "JPN225"
        INDEX_CONTRACT = JPN_CONTRACT
        INDEX_SPREAD = JPN_SPREAD
        INDEX_COMM = JPN_COMM
        INDEX_MAX_LOT = JPN_MAX_LOT
        USE_FX = True
        idx_daily = build_daily(jpn)
        idx_end = jpn.index[-1]
        idx_sha = JPN_SHA
        idx_m1 = jpn
    except SystemExit as e:
        print(f"JPN225/FX blocked ({e}); falling back to USA30 Keltner55 @2.50%")
        usa = load_m1(USA30_PATH, USA30_SHA)
        INDEX_SYMBOL = "USA30"
        INDEX_CONTRACT = USA30_CONTRACT
        INDEX_SPREAD = USA30_SPREAD
        INDEX_COMM = USA30_COMM
        INDEX_MAX_LOT = USA30_MAX_LOT
        USE_FX = False
        fx_mid = None
        fx_sha = "N/A"
        idx_daily = build_daily(usa)
        idx_end = usa.index[-1]
        idx_sha = USA30_SHA
        idx_m1 = usa

    us_daily = build_daily(us)
    print(f"  US100 D1: {len(us_daily)} | Index D1: {len(idx_daily)} symbol={INDEX_SYMBOL}")

    print("Extracting US100 NR7 signals...")
    us_sigs, us_funnel = extract_us100_nr7(us_daily)
    print(f"  US100 NR7 signals={len(us_sigs)} funnel={us_funnel}")

    print(f"Extracting {INDEX_SYMBOL} Keltner55 signals...")
    idx_sigs, idx_funnel = extract_keltner(idx_daily, INDEX_SYMBOL, fx_mid)
    print(f"  {INDEX_SYMBOL} Keltner signals={len(idx_sigs)} funnel={idx_funnel}")

    measured = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")
    summaries = []
    data_end = max(us_end, idx_end)

    # 31A US100 alone soft
    print("Running 31A US100 NR7 soft...")
    t, dp, ds, meta = replay_signals(us_sigs, "31A", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize("31A US100 NR7 @1% soft", "31A", t, dp, ds, meta, True, data_end)
    )

    # 31B index alone soft
    print(f"Running 31B {INDEX_SYMBOL} Keltner soft...")
    t, dp, ds, meta = replay_signals(idx_sigs, "31B", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize(f"31B {INDEX_SYMBOL} Keltner55 @2.50% soft", "31B", t, dp, ds, meta, True, data_end)
    )

    joint_sigs = us_sigs + idx_sigs

    # 31C joint ungov
    print("Running 31C joint ungoverened...")
    t, dp, ds, meta = replay_signals(joint_sigs, "31C", use_gov=False, allow_simultaneous=True)
    summaries.append(
        summarize("31C joint ungoverened", "31C", t, dp, ds, meta, False, data_end)
    )

    # 31D joint soft (verdict)
    print("Running 31D joint soft gov...")
    t, dp, ds, meta = replay_signals(joint_sigs, "31D", use_gov=True, allow_simultaneous=True)
    summaries.append(
        summarize("31D joint + soft gov (verdict)", "31D", t, dp, ds, meta, True, data_end)
    )

    write_docs(summaries, measured, us_end, idx_end, us_sha, idx_sha, fx_sha)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
