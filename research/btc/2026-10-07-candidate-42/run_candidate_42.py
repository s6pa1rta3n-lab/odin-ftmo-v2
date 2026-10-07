#!/usr/bin/env python3
"""Candidate 42: Joint XAG Donchian soft (C21B) + JPN225 Keltner55 soft (C31B). NO US100. NO Gold.

Locked a-priori (not a fishing grid):
  42A — XAG Donchian alone soft 2.50→1.25→0.75 (reconfirm C21B/C39A)
  42B — JPN225 Keltner55 alone soft 2.50→1.25→0.625 (reconfirm C31B)
  42C — joint ungoverened (XAG 2.50% + JPN 2.50% always)
  42D — joint + soft gov (verdict)

Thesis: XAG has 8 HO≤90d windows but leave-out FAIL; XAG+NR7 always wiped windows.
JPN Keltner may help leave-out without killing XAG windows.

Research only. No live / C4 / drip / FREEZE / MetaAPI. Do not package Gold.
Do NOT revive XAG+US100 NR7 stacks.
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
JPN_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/jpnidxjpy-m1-bid-2024-01-01-2026-09-02.csv"
)
USDJPY_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv"
)

XAG_SHA = "6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c"
JPN_SHA = "b7e9a85045eba935ead5812f13d461ba919f60d8220581671bfaf0b66ab82a6e"
USDJPY_SHA = "ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-42"
SPEC = OUT_DIR / "ftmo-candidate-42.md"
RESULTS = OUT_DIR / "candidate-42-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-42-summary.txt"
RESULTS_JSON = OUT_DIR / "candidate-42-results.json"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C42.md"
RUNNER = OUT_DIR / "run_candidate_42.py"

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

# XAG Donchian (C21B full tiers)
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

# JPN225 Keltner55 (exact C31)
JPN_CONTRACT = 10.0  # catalogue
JPN_SPREAD = 8.0  # ASSUMPTION — feed missing
JPN_COMM = 0.0
JPN_FULL = 0.025
JPN_MID = 0.0125
JPN_FLOOR = 0.00625
JPN_MAX_LOT = 200.0
JPN_TIME_DAY = 5
TP_MULT_JPN = 2.0
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
    ema = np.full(n, np.nan)
    if n < EMA_LEN:
        return ema
    ema[EMA_LEN - 1] = float(np.mean(closes[0:EMA_LEN]))
    alpha = 2.0 / (EMA_LEN + 1)
    for t in range(EMA_LEN, n):
        ema[t] = alpha * float(closes[t]) + (1.0 - alpha) * ema[t - 1]
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
    if symbol == "XAG":
        return XAG_FULL, XAG_MID, XAG_FLOOR
    return JPN_FULL, JPN_MID, JPN_FLOOR


def size_lots(symbol: str, equity: float, risk: float, stop_dist: float, fx: float = 1.0) -> float:
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    if symbol == "XAG":
        lots = round(equity * risk / (stop_dist * XAG_CONTRACT), 2)
        lots = min(lots, XAG_MAX_LOT)
    else:
        jpy_per_lot = stop_dist * JPN_CONTRACT
        usd_per_lot = jpy_per_lot / fx if fx > 0 else 0.0
        if usd_per_lot <= 0:
            return 0.0
        lots = round(equity * risk / usd_per_lot, 2)
        lots = min(lots, JPN_MAX_LOT)
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
    if symbol == "XAG":
        units = lots * XAG_CONTRACT
        return raw * units - XAG_SPREAD * units - XAG_COMM * lots
    units = lots * JPN_CONTRACT
    jpy = raw * units - JPN_SPREAD * units - JPN_COMM * lots
    return jpy / fx_exit


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


def extract_jpn_keltner(daily: pd.DataFrame, fx_mid: pd.Series) -> tuple[list[dict], dict]:
    """Exact C31 entry55 Keltner on daily (no sizing)."""
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
                target = entry + TP_MULT_JPN * sl
            else:
                stop = entry + sl
                target = entry - TP_MULT_JPN * sl
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
            if day_num > JPN_TIME_DAY:
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
                JPN_TIME_DAY,
            )
            if hit:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                fx_e = fx_asof(fx_mid, position["entry_ts"])
                fx_x = fx_asof(fx_mid, exit_ts)
                signals.append(
                    {
                        "symbol": "JPN225",
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
    busy_until: dict[str, pd.Timestamp | None] = {"XAG": None, "JPN225": None}

    # XAG (window sleeve) then JPN on same timestamp
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
        "42A": "xag-donchian-20d-2.50" + ("+softgov" if use_gov else ""),
        "42B": "jpn225-keltner55-2.50" + ("+softgov" if use_gov else ""),
        "42C": "xag+jpn-joint-ungov",
        "42D": "xag+jpn-joint+softgov",
    }
    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": chassis_map.get(book, book),
        "taken": len(trades),
        "use_gov": use_gov,
        "symbol": "JOINT" if book in ("42C", "42D") else ("XAG" if book == "42A" else "JPN225"),
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


def summarize(label, book, trades, day_pnl, day_start_eq, meta, use_gov, data_end):
    ho_net = slice_pnl(trades, HO_START, HO_END)
    fit_net = slice_pnl(trades, FIT_START, FIT_END)
    ext_available = data_end >= EXT_START
    if ext_available:
        ext_net = slice_pnl(trades, EXT_START, None)
        ext_status = "measured"
    else:
        ext_net = 0.0
        ext_status = "UNAVAILABLE (XAG/JPN feeds end 2026-09-01; no dukas-ext)"

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

    if book == "42A":
        full, mid, floor = XAG_FULL, XAG_MID, XAG_FLOOR
    elif book == "42B":
        full, mid, floor = JPN_FULL, JPN_MID, JPN_FLOOR
    else:
        full = XAG_FULL + JPN_FULL
        mid = XAG_MID + JPN_MID
        floor = XAG_FLOOR + JPN_FLOOR

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


def write_docs(summaries, measured, xag_end, jpn_end, xag_sha, jpn_sha, fx_sha):
    PACK.mkdir(parents=True, exist_ok=True)

    by_book = {s["book"]: s for s in summaries}
    # Verdict book is always 42D (joint soft). 42A/42B are diagnostics only.
    primary = by_book.get("42D") or summaries[-1]

    if primary["decision"] == "ACCEPT":
        lead = (
            f"**YES — XAG Donchian soft + JPN225 Keltner soft opens a deployable ~3mo path** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — XAG + JPN225 soft legal DD + windows, not ACCEPT** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo."
        )
    else:
        lead = (
            "**NO — XAG Donchian soft + JPN225 Keltner soft (no US100/Gold) does not open a deployable ~3mo path.** "
            "DD illegal, HO≤0, or zero ≤90d windows (or windows wiped)."
        )

    b42a = by_book.get("42A")
    b42d = by_book.get("42D")
    xag_survive = None
    windows_survived = None
    if b42a and b42d:
        windows_survived = b42d["n90_ho"] > 0 and b42a["n90_ho"] > 0
        # Also count any HO windows on joint even if 42A had them
        if b42a["n90_ho"] > 0:
            windows_survived = b42d["n90_ho"] > 0
        xag_survive = (
            f"42A HO≤90d={b42a['n90_ho']} → 42D joint HO≤90d={b42d['n90_ho']} "
            f"(seq HO {b42a['nseq_ho']}→{b42d['nseq_ho']}) | windows_survived={'Y' if windows_survived else 'N'}"
        )

    lines = []
    lines.append("# Candidate 42 Results — XAG Donchian soft + JPN225 Keltner55 soft (no US100 / no Gold)")
    lines.append("")
    lines.append(lead)
    lines.append("")
    if xag_survive:
        lines.append(f"**XAG window survival (42A→42D):** {xag_survive}")
        lines.append("")
    lines.append(f"**XAG data:** `{XAG_PATH}` sha256 `{xag_sha}` end `{xag_end}`")
    lines.append(f"**JPN225 data:** `{JPN_PATH}` sha256 `{jpn_sha}` end `{jpn_end}`")
    lines.append(f"**USDJPY FX:** `{USDJPY_PATH}` sha256 `{fx_sha}` (mid for JPY→USD)")
    lines.append(f"**Measured (ET):** {measured}")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |")
    lines.append("| XAG risks | **2.50% / 1.25% / 0.75%** (full C21B) |")
    lines.append("| JPN225 contract / spread / commission | **10** / **8.0 ASSUMPTION** / **0** (catalogue JP225.cash) |")
    lines.append("| JPN225 risks | **2.50% / 1.25% / 0.625%** (exact C31) |")
    lines.append("| JPY→USD | USDJPY M1 mid at entry (size) and exit (PnL) |")
    lines.append("| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |")
    lines.append("| Prague day kill | −3% both sleeves |")
    lines.append("| Max positions | one per sleeve (two simultaneous OK) |")
    lines.append("| US100 NR7 | **excluded** |")
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
    lines.append(
        "Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. US100 NR7 excluded. No deploy."
    )

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-42-results.md").write_text(RESULTS.read_text())

    summary_lines = [lead, ""]
    if xag_survive:
        summary_lines.append(f"XAG_WINDOW_SURVIVAL|{xag_survive}")
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
    (PACK / "candidate-42-summary.txt").write_text(SUMMARY_TXT.read_text())

    payload = {
        "candidate": 42,
        "measured": measured,
        "lead": lead,
        "primary": primary["book"],
        "decision": primary["decision"],
        "xag_window_survival": xag_survive,
        "windows_survived": windows_survived,
        "assumptions": {
            "xag_contract": XAG_CONTRACT,
            "xag_spread": XAG_SPREAD,
            "xag_commission": XAG_COMM,
            "xag_risks": [XAG_FULL, XAG_MID, XAG_FLOOR],
            "jpn_contract": JPN_CONTRACT,
            "jpn_spread": JPN_SPREAD,
            "jpn_commission": JPN_COMM,
            "jpn_risks": [JPN_FULL, JPN_MID, JPN_FLOOR],
            "fx": "USDJPY mid",
            "us100": "excluded",
            "gold": "not packaged",
            "note": "JPN spread 8.0 ASSUMPTION (C31); XAG costs ASSUMPTION C19B/C21B",
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
            "jpn_sha": jpn_sha,
            "jpn_end": str(jpn_end),
            "fx_sha": fx_sha,
        },
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (PACK / "candidate-42-results.json").write_text(RESULTS_JSON.read_text())

    prior = ROOT_STATUS.read_text() if ROOT_STATUS.exists() else ""

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.append(f"**Status: C42 XAG soft + JPN225 Keltner soft — {primary['decision']}** — {lead}")
    status.append("")
    status.append("_Prior:_ preserved below (C41 / C40 / …).")
    status.append("")
    status.append("## Candidate 42")
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
    if xag_survive:
        status.append(f"**XAG window survival:** {xag_survive}")
        status.append("")
    status.append("## Live")
    status.append(
        "Catalogue drip / C4 ops: **untouched**. Nothing from C42 arms without Odin approval. "
        "Gold not packaged. US100 NR7 excluded."
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
    pr.append("## Candidate 42 — XAG Donchian soft + JPN225 Keltner55 soft (no US100 / no Gold)")
    pr.append("")
    pr.append(lead)
    pr.append("")
    if xag_survive:
        pr.append(f"**XAG window survival (42A→42D):** {xag_survive}")
        pr.append("")
    pr.append(
        "Locked a-priori: XAG soft is the only sleeve with HO-era ≤90d windows (8) but leave-out FAIL. "
        "XAG+NR7 always wiped windows 8→0 (C35/C37/C39). Test joint with JPN225 Keltner55 (C31B) — "
        "no US100 NR7, no Gold — hoping windows survive and leave-out improves."
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
    pr.append("- XAG: contract **5000** / spread **0.025** / commission **$3/lot** (ASSUMPTION — C19B/C21B)")
    pr.append("- XAG risks **2.50% / 1.25% / 0.75%** (full C21B)")
    pr.append("- JPN225: contract **10** / spread **8.0 ASSUMPTION** / commission **0**; risks **2.50→1.25→0.625**")
    pr.append("- JPY→USD via USDJPY M1 mid")
    pr.append("- Soft gov: dd<5% full / 5–8% mid / ≥8% floor; Prague −3% kill both")
    pr.append("- One pos/sleeve; joint may hold both open")
    pr.append("- **US100 NR7 excluded**; Gold not packaged")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-42/`")
    pr.append("")
    pr.append("Research only. Live C4 + drip freeze + MetaAPI untouched. Do not package Gold. No deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C42.md").write_text(PR_BODY.read_text())

    shutil.copy2(SPEC, PACK / "ftmo-candidate-42.md")
    shutil.copy2(RUNNER, PACK / "run_candidate_42.py")

    print(lead)
    if xag_survive:
        print("  XAG survival:", xag_survive)
    for s in summaries:
        xc = s["explorer_xcheck"]
        print(
            f"  {s['book']}: {s['decision']} DD={s['max_dd']*100:.1f}% pace=${s['ho_pace']:.0f}/mo "
            f"90HO={s['n90_ho']} seqHO={s['nseq_ho']} leave={s['leave_net']:.0f} "
            f"xcheck_out={xc['outside_countable']} best={xc['best_outside_pct']}"
        )
    return primary, lead


def main():
    print("Loading XAG M1...")
    xag = load_m1(XAG_PATH, XAG_SHA)
    xag_end = xag.index[-1]
    xag_sha = XAG_SHA
    print(f"  XAG M1: {len(xag)} → {xag_end}")

    print("Loading JPN225 M1...")
    jpn = load_m1(JPN_PATH, JPN_SHA)
    jpn_end = jpn.index[-1]
    jpn_sha = JPN_SHA
    print(f"  JPN225 M1: {len(jpn)} → {jpn_end}")

    print("Loading USDJPY M1 for JPY→USD...")
    usdjpy = load_m1(USDJPY_PATH, USDJPY_SHA)
    fx_mid = build_fx_mid(usdjpy)
    fx_sha = USDJPY_SHA
    print(f"  USDJPY M1: {len(usdjpy)} mid points={len(fx_mid)}")

    xag_daily = build_daily(xag)
    jpn_daily = build_daily(jpn)
    print(f"  XAG D1: {len(xag_daily)} | JPN225 D1: {len(jpn_daily)}")

    print("Extracting XAG Donchian 20d signals...")
    xag_sigs, xag_funnel = extract_xag_donchian(xag_daily)
    print(f"  XAG Donchian signals={len(xag_sigs)} funnel={xag_funnel}")

    print("Extracting JPN225 Keltner55 signals...")
    jpn_sigs, jpn_funnel = extract_jpn_keltner(jpn_daily, fx_mid)
    print(f"  JPN225 Keltner signals={len(jpn_sigs)} funnel={jpn_funnel}")

    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    summaries = []
    data_end = max(xag_end, jpn_end)

    print("Running 42A XAG Donchian soft...")
    t, dp, ds, meta = replay_signals(xag_sigs, "42A", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize("42A XAG Donchian @2.50% soft", "42A", t, dp, ds, meta, True, data_end)
    )
    print(
        f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo "
        f"DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}"
    )

    print("Running 42B JPN225 Keltner soft...")
    t, dp, ds, meta = replay_signals(jpn_sigs, "42B", use_gov=True, allow_simultaneous=False)
    summaries.append(
        summarize("42B JPN225 Keltner55 @2.50% soft", "42B", t, dp, ds, meta, True, data_end)
    )
    print(
        f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo "
        f"DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}"
    )

    joint_sigs = xag_sigs + jpn_sigs

    print("Running 42C joint ungoverened...")
    t, dp, ds, meta = replay_signals(joint_sigs, "42C", use_gov=False, allow_simultaneous=True)
    summaries.append(
        summarize("42C joint ungoverened", "42C", t, dp, ds, meta, False, data_end)
    )
    print(
        f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo "
        f"DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}"
    )

    print("Running 42D joint soft gov (verdict)...")
    t, dp, ds, meta = replay_signals(joint_sigs, "42D", use_gov=True, allow_simultaneous=True)
    summaries.append(
        summarize("42D joint + soft gov (verdict)", "42D", t, dp, ds, meta, True, data_end)
    )
    print(
        f"  → {summaries[-1]['decision']} pace=${summaries[-1]['ho_pace']:.0f}/mo "
        f"DD={summaries[-1]['max_dd']*100:.1f}% 90HO={summaries[-1]['n90_ho']} leave={summaries[-1]['leave_net']:.0f}"
    )

    write_docs(summaries, measured, xag_end, jpn_end, xag_sha, jpn_sha, fx_sha)
    print("DONE pack", PACK)


if __name__ == "__main__":
    main()
