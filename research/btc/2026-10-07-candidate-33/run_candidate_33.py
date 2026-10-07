#!/usr/bin/env python3
"""Candidate 33: FX residual majors Donchian + soft DD governor (AUDUSD / USDCAD).

Locked a-priori:
  33A — AUDUSD 20d Donchian dual @2.50% / soft 2.50→1.25→0.75
  33B — USDCAD 20d Donchian dual @2.50% / soft 2.50→1.25→0.75
  33C — joint equal 1/2 soft-gov risk share on shared equity (one DD peak)

Research only. No live / C4 / drip / FREEZE / MetaAPI. Do not package Gold.
C25 was EUR/GBP/JPY REJECT — fresh pairs only. Do not conflict with C31 names.
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

AUD_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/audusd-m1-bid-2024-01-01-2026-09-02.csv"
)
CAD_PATH = Path(
    "/workspace/strategy-explorer/pr36/dukascopy-raw/usdcad-m1-bid-2024-01-01-2026-09-02.csv"
)
AUD_SHA = "5c472bbb005ce6e06b5a844efb5185332e06c9b9011c7cf9555fec2c89af1e4a"
CAD_SHA = "c50c676b4c9010ac7aa9f9ad719f984ad7ed63085796787232b332b42046a8a1"

OUT_DIR = Path("/workspace/btc-strategies")
PACK = OUT_DIR / "2026-10-07-candidate-33"
SPEC = OUT_DIR / "ftmo-candidate-33.md"
RESULTS = OUT_DIR / "candidate-33-results.md"
SUMMARY_TXT = OUT_DIR / "candidate-33-summary.txt"
ROOT_STATUS = OUT_DIR / "STATUS.md"
PR_BODY = OUT_DIR / "GITHUB-PR-BODY-C33.md"
RUNNER = OUT_DIR / "run_candidate_33.py"

START_EQUITY = 100_000.0
MIN_LOT = 0.01
MAX_LOT = 100.0  # FTMO maxTradeVolume for FX majors
CONTRACT = 100_000.0  # catalogue both
COMMISSION = 5.0  # catalogue flat_USD $/lot
# ASSUMPTION spreads (feed missing) — industry mid per C33 lock
AUD_SPREAD = 0.00015
CAD_SPREAD = 0.00020
SYMBOL_SPREAD = {"AUDUSD": AUD_SPREAD, "USDCAD": CAD_SPREAD}
SYMBOL_CONTRACT = {"AUDUSD": CONTRACT, "USDCAD": CONTRACT, "JOINT": CONTRACT}
# profitCurrency: AUDUSD → USD; USDCAD → CAD (convert at exit mid)
CAD_PROFIT = {"AUDUSD": False, "USDCAD": True}

DAILY_KILL = -0.03
DAY_FAIL = -0.05
CHALLENGE_MULT = 1.10
BOTH_MULT = 1.155
FLOOR_MULT = 0.90
ORIGIN = pd.Timestamp("2024-01-01 00:00:00+00:00")

GOV_SOFT = 0.05
GOV_HARD = 0.08

DONCH_N = 20
ATR_MULT = 2.0
R_MULT = 1.0
MAX_HOLD_DAYS = 10

FULL = 0.025
MID = 0.0125
FLOOR = 0.0075
# 33C a-priori: equal 1/2 share of soft tiers on shared equity / one DD peak
JOINT_FULL = FULL / 2.0   # =1.25%
JOINT_MID = MID / 2.0     # =0.625%
JOINT_FLOOR = FLOOR / 2.0  # =0.375%

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
        # 6 dp for FX pip-scale ATR
        atr[i] = round(float(csum[i] - csum[i - 14]) / 14.0, 6)
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


def size_lots(equity: float, risk: float, stop_dist: float, symbol: str, entry: float) -> float:
    """Lot size so stop ≈ risk% of equity in USD."""
    if stop_dist <= 0 or equity <= 0 or entry <= 0:
        return 0.0
    contract = CONTRACT
    if CAD_PROFIT.get(symbol, False):
        # stop loss USD ≈ stop_dist * lots * contract / entry_cad (USDCAD)
        lots = equity * risk * entry / (stop_dist * contract)
    else:
        lots = equity * risk / (stop_dist * contract)
    lots = round(lots, 2)
    lots = min(lots, MAX_LOT)
    if lots < MIN_LOT:
        return 0.0
    return float(lots)


def pnl_fx(side: str, entry: float, exit_px: float, lots: float, spread: float, symbol: str) -> float:
    """FX PnL in USD. USDCAD: CAD PnL / exit mid (ASSUMPTION bid≈mid)."""
    raw = (exit_px - entry) if side == "long" else (entry - exit_px)
    gross = raw * lots * CONTRACT - spread * lots * CONTRACT
    if CAD_PROFIT.get(symbol, False):
        mid = exit_px if exit_px > 0 else entry
        return gross / mid - COMMISSION * lots
    return gross - COMMISSION * lots


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


def run_donchian(
    daily: pd.DataFrame,
    spread: float,
    full_risk: float,
    mid_risk: float,
    floor_risk: float,
    use_gov: bool,
    book: str,
    symbol: str,
):
    opens = daily["open"].to_numpy(dtype=float)
    highs = daily["high"].to_numpy(dtype=float)
    lows = daily["low"].to_numpy(dtype=float)
    closes = daily["close"].to_numpy(dtype=float)
    index = daily.index
    atr = atr14(highs, lows, closes)
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
                    if use_gov:
                        risk, gstate = soft_gov_risk(
                            equity, peak, full_risk, mid_risk, floor_risk
                        )
                        funnel[f"gov_{gstate}"] += 1
                    else:
                        risk, gstate = full_risk, "n/a"

                    sl_dist = ATR_MULT * float(pending["atr"])
                    lots = size_lots(equity, risk, sl_dist, symbol, entry)
                    if lots < MIN_LOT or sl_dist <= 0:
                        funnel["skip_lots"] += 1
                        pending = None
                    else:
                        side = pending["side"]
                        if side == "long":
                            stop = entry - sl_dist
                            target = entry + R_MULT * sl_dist
                        else:
                            stop = entry + sl_dist
                            target = entry - R_MULT * sl_dist
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
                pnl = pnl_fx(
                    position["side"], position["entry"], float(fill), position["lots"], spread, symbol
                )
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
                        book=book,
                        risk_used=position["risk_used"],
                        gov_state=position["gov_state"],
                        symbol=symbol,
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
        "chassis": f"{symbol.lower()}-donchian-20d-dual-1r" + ("+softgov" if use_gov else ""),
        "taken": len(trades),
        "use_gov": use_gov,
        "full_risk": full_risk,
        "mid_risk": mid_risk,
        "floor_risk": floor_risk,
        "spread": spread,
        "contract": CONTRACT,
        "commission": COMMISSION,
        "symbol": symbol,
    }
    return trades, day_pnl, day_start_eq, meta


def extract_signals(daily: pd.DataFrame, symbol: str):
    """Precompute Donchian signal→fill→exit triples (no sizing) for joint replay."""
    opens = daily["open"].to_numpy(dtype=float)
    highs = daily["high"].to_numpy(dtype=float)
    lows = daily["low"].to_numpy(dtype=float)
    closes = daily["close"].to_numpy(dtype=float)
    index = daily.index
    atr = atr14(highs, lows, closes)
    n = len(daily)
    signals = []
    pending = None
    pos = None

    for i in range(n):
        if pending is not None and pos is None:
            entry = float(opens[i])
            entry_ts = pd.Timestamp(index[i])
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.tz_localize("UTC")
            sl_dist = ATR_MULT * float(pending["atr"])
            if sl_dist > 0:
                side = pending["side"]
                if side == "long":
                    stop = entry - sl_dist
                    target = entry + R_MULT * sl_dist
                else:
                    stop = entry + sl_dist
                    target = entry - R_MULT * sl_dist
                pos = {
                    "side": side,
                    "entry": entry,
                    "entry_ts": entry_ts,
                    "entry_i": i,
                    "stop": stop,
                    "target": target,
                    "sl_dist": sl_dist,
                }
            pending = None

        if pos is not None:
            day_num = i - pos["entry_i"] + 1
            hit = resolve_daily_bar(
                pos["side"],
                float(opens[i]),
                float(highs[i]),
                float(lows[i]),
                float(closes[i]),
                pos["stop"],
                pos["target"],
                day_num,
            )
            if hit is not None:
                fill, reason, when = hit
                bar_ts = pd.Timestamp(index[i])
                if bar_ts.tzinfo is None:
                    bar_ts = bar_ts.tz_localize("UTC")
                exit_ts = bar_ts if when == "open" else bar_ts + pd.Timedelta(days=1)
                signals.append(
                    {
                        "symbol": symbol,
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
            if np.isfinite(atr[i]) and atr[i] > 0:
                hh = float(highs[i - DONCH_N : i].max())
                ll = float(lows[i - DONCH_N : i].min())
                c = float(closes[i])
                if c > hh:
                    pending = {"side": "long", "atr": float(atr[i])}
                elif c < ll:
                    pending = {"side": "short", "atr": float(atr[i])}

    return signals


def run_joint(aud_daily, cad_daily, use_gov: bool):
    """Shared equity: each leg @ FULL/2 soft-gov (one DD peak). One position at a time."""
    aud_sigs = extract_signals(aud_daily, "AUDUSD")
    cad_sigs = extract_signals(cad_daily, "USDCAD")
    for s in aud_sigs:
        s["spread"] = AUD_SPREAD
    for s in cad_sigs:
        s["spread"] = CAD_SPREAD
    all_sigs = sorted(aud_sigs + cad_sigs, key=lambda s: s["entry_ts"])

    equity = START_EQUITY
    peak = START_EQUITY
    trades: list[Trade] = []
    day_pnl: dict[date, float] = defaultdict(float)
    day_start_eq: dict[date, float] = {}
    killed_days: set[date] = set()
    funnel = defaultdict(int)
    busy_until = None

    for sig in all_sigs:
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
            risk, gstate = soft_gov_risk(equity, peak, JOINT_FULL, JOINT_MID, JOINT_FLOOR)
            funnel[f"gov_{gstate}"] += 1
        else:
            risk, gstate = JOINT_FULL, "n/a"

        lots = size_lots(equity, risk, sig["stop_dist"], sig["symbol"], sig["entry"])
        if lots < MIN_LOT:
            funnel["skip_lots"] += 1
            continue

        pnl = pnl_fx(sig["side"], sig["entry"], sig["exit"], lots, sig["spread"], sig["symbol"])
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
                book="33C",
                risk_used=risk,
                gov_state=gstate,
                symbol=sig["symbol"],
            )
        )
        busy_until = sig["exit_ts"]
        funnel["taken"] += 1

    meta = {
        "funnel": dict(funnel),
        "final_equity": equity,
        "peak_equity": peak,
        "killed_days": len(killed_days),
        "chassis": "aud+cad-donchian-joint-1/2" + ("+softgov" if use_gov else ""),
        "taken": len(trades),
        "use_gov": use_gov,
        "full_risk": JOINT_FULL,
        "mid_risk": JOINT_MID,
        "floor_risk": JOINT_FLOOR,
        "n_aud_sigs": len(aud_sigs),
        "n_cad_sigs": len(cad_sigs),
        "symbol": "JOINT",
        "joint_share_rule": "equal 1/2 of soft tiers on shared equity / one DD peak; one pos global",
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


def count_sequential_reset(
    trades: list[Trade],
    full_risk: float,
    mid_risk: float,
    floor_risk: float,
    use_gov: bool,
    spreads_by_symbol: dict,
    window_days: int = 90,
):
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
                    risk, _ = soft_gov_risk(eq, peak, full_risk, mid_risk, floor_risk)
                else:
                    risk = full_risk
                lots = size_lots(eq, risk, tr.stop_dist, tr.symbol, tr.entry)
                if lots < MIN_LOT:
                    continue
                spread = spreads_by_symbol.get(tr.symbol, AUD_SPREAD)
                pnl = pnl_fx(tr.side, tr.entry, tr.exit, lots, spread, tr.symbol)
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
    data_end,
    spreads_by_symbol,
):
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

    n60, w60, p60 = count_pass_windows(trades, day_pnl, day_start_eq, 60)
    n90, w90, p90 = count_pass_windows(trades, day_pnl, day_start_eq, 90)
    nseq, wseq, pseq = count_sequential_reset(
        trades, full_risk, mid_risk, floor_risk, use_gov, spreads_by_symbol, 90
    )

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
    elif (
        legal
        and has_90_ho
        and ho_ok
        and leave_ok
        and ext_ok
    ):
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
        "book": book,
        "symbol": meta.get("symbol", book),
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
        "meta": meta,
    }


def write_docs(summaries, measured, ends, shas):
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
            f"**YES — AUDUSD/USDCAD Donchian+softgov opens a deployable ~3mo path** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq {primary['nseq']}/{primary['wseq']} (HO-era {primary['nseq_ho']}), "
            f"HO ~${primary['ho_pace']:,.0f}/mo."
        )
    elif primary["decision"] == "CONDITIONAL":
        lead = (
            f"**CONDITIONAL — AUDUSD/USDCAD Donchian+softgov legal DD + windows, not ACCEPT** via "
            f"{primary['book']} ({primary['label']}): max DD {primary['max_dd']*100:.1f}%, "
            f"≤90d {primary['n90']}/{primary['w90']} (HO-era {primary['n90_ho']}), "
            f"seq HO-era {primary['nseq_ho']}, HO ~${primary['ho_pace']:,.0f}/mo. "
            f"Fit-only / leave-out / Ext weak → not deployable."
        )
    else:
        lead = (
            "**NO — AUDUSD/USDCAD Donchian+softgov does not open a deployable ~3mo path.** "
            "DD illegal, HO≤0, or zero ≤90d windows."
        )

    lines = []
    lines.append("# Candidate 33 Results — AUDUSD/USDCAD Donchian + soft DD governor")
    lines.append("")
    lines.append(lead)
    lines.append("")
    lines.append(f"**Measured:** {measured}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**AUDUSD data:** `{AUD_PATH}` sha256 `{shas['AUDUSD']}` end `{ends['AUDUSD']}`")
    lines.append(f"**USDCAD data:** `{CAD_PATH}` sha256 `{shas['USDCAD']}` end `{ends['USDCAD']}`")
    lines.append("")
    lines.append("## ASSUMPTIONS")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step |")
    lines.append("| Challenge / Verification | +10% / +5% |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |")
    lines.append("| Single-book risks | **2.50% / 1.25% / 0.75%** |")
    lines.append("| Joint per-leg risks | **1.25% / 0.625% / 0.375%** (equal 1/2 of soft tiers) |")
    lines.append("| contractSize | **100000** both (catalogue) |")
    lines.append("| commission | **$5/lot** flat_USD (catalogue) |")
    lines.append("| maxTradeVolume | **100** (catalogue) |")
    lines.append("| AUDUSD spread | **0.00015** (**ASSUMPTION** — feed missing; ≈1.5 pip mid) |")
    lines.append("| USDCAD spread | **0.00020** (**ASSUMPTION** — feed missing; ≈2.0 pip mid) |")
    lines.append("| USDCAD→USD | CAD PnL / exit bid as mid (**ASSUMPTION**, bid-only feed) |")
    lines.append("| Gold packaging | Forbidden |")
    lines.append("")

    lines.append("## Scoreboard")
    lines.append("")
    lines.append(
        "| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for s in summaries:
        gov = "SOFT" if s["use_gov"] else "OFF"
        rc = f"{s['full_risk']*100:.2f}/{s['mid_risk']*100:.2f}/{s['floor_risk']*100:.2f}%"
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        lines.append(
            f"| {s['book']} {s['label']} | {s['symbol']} | {gov} | {rc} | {s['ho_pace']:,.0f} | "
            f"{s['leave_net']:+,.0f} | {ext_cell} | "
            f"{s['worst_pct']*100:.2f}% | {s['max_dd']*100:.1f}% | "
            f"{s['n90']}/{s['w90']} ({s['n90_ho']}) | {s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{'YES' if s['legal'] else 'NO'} | {s['decision']} |"
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
            f"reasons={s['reasons']} gov={s['gov_counts']} by_sym={s['by_sym']}"
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

    lines.append("## Live")
    lines.append("")
    lines.append("Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.")
    lines.append("Gold not packaged. Do not deploy.")
    lines.append("")

    RESULTS.write_text("\n".join(lines) + "\n")
    (PACK / "candidate-33-results.md").write_text(RESULTS.read_text())
    if SPEC.exists():
        (PACK / "ftmo-candidate-33.md").write_text(SPEC.read_text())

    SUMMARY_TXT.write_text(
        f"{lead}\n"
        + "\n".join(
            f"{s['book']}|{s['symbol']}|gov={s['use_gov']}|{s['decision']}|pace=${s['ho_pace']:.0f}/mo|"
            f"DD={s['max_dd']*100:.1f}%|90d={s['n90']}/{s['w90']}(HO={s['n90_ho']})|"
            f"seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']})|legal={s['legal']}"
            for s in summaries
        )
        + "\n"
    )
    (PACK / "candidate-33-summary.txt").write_text(SUMMARY_TXT.read_text())

    # Build C33 section; preserve prior C31/C32 (and earlier) from existing STATUS.md
    c33_lines = []
    c33_lines.append(f"**Status: C33 AUDUSD/USDCAD Donchian+softgov — {primary['decision']}** — {lead}")
    c33_lines.append("")
    c33_lines.append("_Prior:_ preserved below (C32 / C31 / C30).")
    c33_lines.append("")
    c33_lines.append("## Candidate 33")
    c33_lines.append("")
    c33_lines.append(
        "| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Decision |"
    )
    c33_lines.append("|---|---|---|---:|---:|---:|---:|---|---:|---|---|")
    for s in summaries:
        ext_cell = f"{s['ext_net']:+,.0f}" if s["ext_available"] else "N/A"
        c33_lines.append(
            f"| {s['book']} | {s['symbol']} | {'SOFT' if s['use_gov'] else 'OFF'} | {s['ho_pace']:,.0f} | "
            f"{s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | "
            f"{ext_cell} | {s['leave_net']:+,.0f} | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    c33_lines.append("")

    prior = ""
    if ROOT_STATUS.exists():
        prior_text = ROOT_STATUS.read_text()
        # Keep from first "## Candidate 3" / "## Prior" / "## Candidate 32" onward (drop old header+live)
        keep_from = None
        for marker in ("## Candidate 32", "## Candidate 31", "## Prior: Candidate 30", "## Candidate 30"):
            m = prior_text.find(marker)
            if m >= 0:
                keep_from = m if keep_from is None else min(keep_from, m)
        if keep_from is not None:
            # Drop trailing Live section from prior (we'll rewrite)
            chunk = prior_text[keep_from:]
            live_m = chunk.rfind("\n## Live")
            if live_m >= 0:
                chunk = chunk[:live_m]
            prior = chunk.rstrip() + "\n\n"

    status = []
    status.append("# BTC FTMO research baseline (2026-10-07)")
    status.append("")
    status.extend(c33_lines)
    if prior:
        status.append(prior.rstrip())
        status.append("")
    status.append("## Live")
    status.append("Catalogue drip / C4 ops: **untouched**. Nothing from C33 arms without Odin approval. Gold not packaged.")
    status.append("")

    ROOT_STATUS.write_text("\n".join(status) + "\n")
    (PACK / "STATUS.md").write_text(
        "# Candidate 33 pack STATUS\n\n"
        + "\n".join(c33_lines)
        + "\n## Live\nCatalogue drip / C4 ops: **untouched**. Gold not packaged.\n"
    )

    pr = []
    pr.append("## Candidate 33 — AUDUSD/USDCAD Donchian + soft DD governor")
    pr.append("")
    pr.append(lead)
    pr.append("")
    pr.append("Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).")
    pr.append("33C joint: equal 1/2 soft-gov risk share on shared equity / one DD peak; one position globally.")
    pr.append("Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.")
    pr.append("")
    pr.append("### Scoreboard")
    pr.append("")
    pr.append("| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |")
    pr.append("|---|---|---|---:|---:|---:|---:|---|---|")
    for s in summaries:
        pr.append(
            f"| {s['book']} {s['label']} | {s['symbol']} | {'SOFT' if s['use_gov'] else 'OFF'} | "
            f"{s['ho_pace']:,.0f} | {s['max_dd']*100:.1f}% | {s['n90']}/{s['w90']} ({s['n90_ho']}) | "
            f"{s['nseq']}/{s['wseq']} ({s['nseq_ho']}) | {'YES' if s['legal'] else 'NO'} | {s['decision']} |"
        )
    pr.append("")
    pr.append("### ASSUMPTIONS")
    pr.append("- contractSize=100000 / commission=$5/lot (catalogue); spreads AUD=0.00015 / CAD=0.00020 (ASSUMPTION, feed missing)")
    pr.append("- USDCAD→USD: CAD PnL / exit bid as mid (ASSUMPTION, bid-only feed)")
    pr.append("")
    pr.append("### Files")
    pr.append("- `research/btc/2026-10-07-candidate-33/`")
    pr.append("- `run_candidate_33.py`, `ftmo-candidate-33.md`, `candidate-33-results.md`, `STATUS.md`")
    pr.append("")
    pr.append("### Live")
    pr.append("Research only — do not deploy.")
    PR_BODY.write_text("\n".join(pr) + "\n")
    (PACK / "GITHUB-PR-BODY-C33.md").write_text(PR_BODY.read_text())

    shutil.copy2(RUNNER, PACK / "run_candidate_33.py")

    dump = []
    for s in summaries:
        row = {k: v for k, v in s.items() if k not in ("p60",)}
        dump.append(row)
    (PACK / "candidate-33-results.json").write_text(json.dumps(dump, indent=2, default=str))
    (OUT_DIR / "candidate-33-results.json").write_text(json.dumps(dump, indent=2, default=str))

    return lead, primary, opens


def main():
    measured = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("Loading AUDUSD M1...")
    aud = load_m1(AUD_PATH, AUD_SHA)
    aud_end = aud.index[-1]
    print(f"  AUDUSD M1: {len(aud)} → {aud_end}")
    aud_daily = build_daily(aud)
    print(f"  AUDUSD D1: {len(aud_daily)}")

    print("Loading USDCAD M1...")
    cad = load_m1(CAD_PATH, CAD_SHA)
    cad_end = cad.index[-1]
    print(f"  USDCAD M1: {len(cad)} → {cad_end}")
    cad_daily = build_daily(cad)
    print(f"  USDCAD D1: {len(cad_daily)}")

    spreads = {"AUDUSD": AUD_SPREAD, "USDCAD": CAD_SPREAD, "JOINT": AUD_SPREAD}
    summaries = []
    data_end = max(aud_end, cad_end)

    # 33A AUDUSD
    for use_gov, tag in [(False, "ungov 2.50%"), (True, "soft 2.50→1.25→0.75")]:
        print(f"Running 33A AUDUSD {tag}...")
        trades, day_pnl, day_start, meta = run_donchian(
            aud_daily, AUD_SPREAD, FULL, MID, FLOOR, use_gov, "33A", "AUDUSD"
        )
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
        s = summarize(
            tag, "33A", trades, day_pnl, day_start, meta,
            FULL, MID, FLOOR, use_gov, data_end, spreads,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
            f"legal={s['legal']}"
        )
        summaries.append(s)

    # 33B USDCAD
    for use_gov, tag in [(False, "ungov 2.50%"), (True, "soft 2.50→1.25→0.75")]:
        print(f"Running 33B USDCAD {tag}...")
        trades, day_pnl, day_start, meta = run_donchian(
            cad_daily, CAD_SPREAD, FULL, MID, FLOOR, use_gov, "33B", "USDCAD"
        )
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
        s = summarize(
            tag, "33B", trades, day_pnl, day_start, meta,
            FULL, MID, FLOOR, use_gov, data_end, spreads,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
            f"legal={s['legal']}"
        )
        summaries.append(s)

    # 33C joint
    for use_gov, tag in [(False, "ungov joint@1/2"), (True, "soft joint 1.25→0.625→0.375")]:
        print(f"Running 33C JOINT {tag}...")
        trades, day_pnl, day_start, meta = run_joint(aud_daily, cad_daily, use_gov)
        print(f"  trades={len(trades)} eq={meta['final_equity']:.2f} funnel={meta['funnel']}")
        s = summarize(
            tag, "33C", trades, day_pnl, day_start, meta,
            JOINT_FULL, JOINT_MID, JOINT_FLOOR, use_gov, data_end, spreads,
        )
        print(
            f"  → {s['decision']} pace=${s['ho_pace']:.0f}/mo DD={s['max_dd']*100:.1f}% "
            f"90d={s['n90']}/{s['w90']}(HO={s['n90_ho']}) seq={s['nseq']}/{s['wseq']}(HO={s['nseq_ho']}) "
            f"legal={s['legal']}"
        )
        summaries.append(s)

    lead, primary, opens = write_docs(
        summaries,
        measured,
        {"AUDUSD": aud_end, "USDCAD": cad_end},
        {"AUDUSD": AUD_SHA, "USDCAD": CAD_SHA},
    )
    print("\n" + lead)
    print(f"Wrote {RESULTS}")
    print(f"Pack {PACK}")


if __name__ == "__main__":
    main()
