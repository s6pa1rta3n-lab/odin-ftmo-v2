#!/usr/bin/env python3
"""2026-10-02 live-rules backtest of the three FTMO Griff engines.

Read-only with respect to the engines: this script IMPORTS the strategy
functions from the live engine modules (``griff_engine_live.py``,
``griff_engine_us100.py``, ``griff_engine_gold.py``) and replays them over
1-minute bid history. It does not modify live risk, configs, or engine code.

Engines replayed (LIVE CODE references are the repo files at the commit this
backtest was run on):

  BTC   griff_engine_live.py   1H inside-bar breakout, EMA50 trend filter,
                                ADX14 >= 25, one pending stop at the inside-bar
                                extreme, 1.5xATR14 initial stop, structural
                                trailing stop, no take profit.
  US100 griff_engine_us100.py  15m NY-session pullback to EMA20 between
                                09:45-11:30 ET, 1.5xATR SL / 3.0xATR TP,
                                16:00 ET hard close, no daily trade cap.
  GOLD  griff_engine_gold.py   15m Asian range (28 x 15m ending 03:00 ET),
                                breakout 03:15-10:00 ET, 1.5xATR SL /
                                3.0xATR TP, one trade/day, 16:00 ET hard close.

Risk stacks (fraction of account equity per trade):
  A (current live code)  BTC 0.80%  US100 1.00%  GOLD 0.50%
  B (proposed, NOT approved)  BTC 0.25%  US100 0.50%  GOLD 0.25%

Outputs are written next to this script under ``results/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytz

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import griff_engine_live as btc_live  # noqa: E402  (live BTC engine module)
from griff_engine_gold import GoldEngine  # noqa: E402  (live Gold engine class)
from griff_engine_us100 import US100Engine  # noqa: E402  (live US100 engine class)

RUN_DATE = "2026-10-02"
START_EQUITY = 100_000.0
ET = pytz.timezone("US/Eastern")
FTMO_TZ = pytz.timezone("Europe/Prague")  # FTMO daily reset is 00:00 CE(S)T

STACKS = {
    "A_live": {"BTC": 0.0080, "US100": 0.0100, "GOLD": 0.0050},
    "B_proposed": {"BTC": 0.0025, "US100": 0.0050, "GOLD": 0.0025},
}

FEEDS = {
    "BTC": REPO / "data/raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv",
    "US100": REPO / "usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv",
    "GOLD": REPO / "data/raw/xauusd-m1-bid-2024-01-01-2026-09-02.csv",
}
SPEC_SYMBOL = {"BTC": "BTCUSD", "US100": "US100.cash", "GOLD": "XAUUSD"}

# MetaApi get_historical_candles() is called by the US100 engine with no
# limit. The SDK documents a 1000-candle maximum; the server default when the
# parameter is omitted is not verifiable from this repo. 1000 is assumed. The
# seeded EMA20 / Wilder ATR14 decay to numerical identity long before 999
# bars, so this assumption does not change any trade.
US100_CANDLE_WINDOW = 1000
BTC_CANDLE_WINDOW = 60  # griff_engine_live.py step(): fetch_completed_1h_candles(limit=60)
GOLD_RANGE_CANDLES = 28  # griff_engine_gold.py: fetch_15m_candles(limit=28) at 03:00 ET
GOLD_ATR_CANDLES = 20  # griff_engine_gold.py: fetch_15m_candles(limit=20) at breakout


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_m1(path: Path) -> pd.DataFrame:
    """Load Dukascopy 1m bid OHLC (ms epoch, UTC) and drop consecutive flat rows.

    Same cleaning as backtest_suite/data_loader.py: a row whose OHLC are all
    equal and whose close did not change from the previous row is a
    weekend/holiday fill, not a traded minute.
    """
    df = pd.read_csv(path, usecols=["timestamp", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("ts")[["open", "high", "low", "close"]].sort_index()
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    unchanged = df["close"].diff().fillna(0.0) == 0.0
    df = df[~(flat & unchanged)].copy()
    return df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    out = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return out.dropna()


def bars_to_dicts(bars: pd.DataFrame) -> list[dict]:
    return [
        {"time": t, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        for t, o, h, l, c in zip(bars.index, bars["open"], bars["high"], bars["low"], bars["close"])
    ]


def load_specs() -> dict:
    with open(REPO / "data/ftmo_asset_specs.json") as fh:
        specs = json.load(fh)
    by_symbol = {inst["symbol"]: inst for inst in specs["instruments"]}
    costs = {}
    for asset, sym in SPEC_SYMBOL.items():
        inst = by_symbol[sym]
        costs[asset] = {
            "symbol": sym,
            "spread": float(inst["typical_spread"]),
            "commission_per_lot": float(inst["commission_per_lot"]),
            "contract_size": float(inst["contract_size"]),
            "tick_value": float(inst["tick_value"]),
            "min_lot": float(inst["min_lot_size"]),
        }
    return costs


# --------------------------------------------------------------------------
# trade record helpers
# --------------------------------------------------------------------------
def make_trade(asset, direction, entry_time, entry, sl, tp, sl_dist, exit_time, exit_price, reason, extra=None):
    rec = {
        "asset": asset,
        "direction": direction,
        "entry_time": pd.Timestamp(entry_time).tz_convert("UTC"),
        "entry": float(entry),
        "sl_initial": float(sl),
        "tp": None if tp is None else float(tp),
        "sl_dist": float(sl_dist),
        "exit_time": pd.Timestamp(exit_time).tz_convert("UTC"),
        "exit": float(exit_price),
        "exit_reason": reason,
    }
    if extra:
        rec.update(extra)
    return rec


def first_exit_in_minute(direction, o, h, l, sl, tp):
    """Resolve SL/TP inside one 1m bar.

    Conservative conventions: SL has priority when both are touched; a stop
    gapped through fills at the bar open (worse than SL); a take profit fills
    at the TP level, never better.
    """
    if direction == "BUY":
        if l <= sl:
            return (min(sl, o), "SL")
        if tp is not None and h >= tp:
            return (tp, "TP")
    else:
        if h >= sl:
            return (max(sl, o), "SL")
        if tp is not None and l <= tp:
            return (tp, "TP")
    return None


# --------------------------------------------------------------------------
# BTC: griff_engine_live.py (1H inside bar, EMA50 + ADX filter, structural trail)
# --------------------------------------------------------------------------
FUNNEL: dict = {}


def simulate_btc(m1: pd.DataFrame) -> list[dict]:
    funnel = FUNNEL.setdefault("BTC", {"h1_bars": 0, "inside_bars_scanned": 0, "adx_blocked": 0, "pending_placed": 0,
                                       "filled": 0, "expired_unfilled": 0})
    h1 = resample(m1, "1h")
    funnel["h1_bars"] = len(h1)
    bars = bars_to_dicts(h1)
    n = len(bars)
    bar_times = h1.index
    m1_ts = m1.index.values
    m1_o, m1_h, m1_l = m1["open"].values, m1["high"].values, m1["low"].values

    trades: list[dict] = []
    state = "SEARCHING"
    pending = None  # {"direction","price","sl","atr","setup_time"}
    pos = None  # {"direction","entry","sl","sl_initial","atr","entry_time"}

    def minute_slice(bar_idx: int, after=None):
        start = bar_times[bar_idx]
        end = start + pd.Timedelta(hours=1)
        lo = np.searchsorted(m1_ts, start.tz_convert("UTC").tz_localize(None).to_datetime64(), "left")
        hi = np.searchsorted(m1_ts, end.tz_convert("UTC").tz_localize(None).to_datetime64(), "left")
        if after is not None:
            lo = max(lo, np.searchsorted(m1_ts, after.tz_convert("UTC").tz_localize(None).to_datetime64(), "right"))
        return range(lo, hi)

    def scan_setup(i: int):
        """Live SEARCHING branch evaluated on completed bar i (candles[-1])."""
        if i < btc_live.MIN_CANDLES_FOR_SETUP_SCAN - 1:
            return None
        window = bars[max(0, i - BTC_CANDLE_WINDOW + 1): i + 1]
        if len(window) < btc_live.MIN_CANDLES_FOR_SETUP_SCAN:
            return None
        cur, mother = bars[i], bars[i - 1]
        if not btc_live.is_inside_bar(cur, mother):
            return None
        funnel["inside_bars_scanned"] += 1
        atr = btc_live.compute_atr_14(window)
        ema50 = btc_live.compute_ema_50(window)
        direction = "BUY" if cur["close"] > ema50 else "SELL"
        adx = btc_live.compute_adx(window, 14)[-1]
        if adx < 25:
            funnel["adx_blocked"] += 1
            return None
        funnel["pending_placed"] += 1
        if direction == "BUY":
            price = round(cur["high"], 2)
        else:
            price = round(cur["low"], 2)
        sl = btc_live.calculate_initial_stop_loss(direction, price, atr)
        return {"direction": direction, "price": price, "sl": sl, "atr": atr, "setup_time": cur["time"], "adx": adx, "ema50": ema50}

    def close_trade(p, exit_time, exit_price, reason):
        trades.append(
            make_trade(
                "BTC", p["direction"], p["entry_time"], p["entry"], p["sl_initial"], None,
                abs(p["entry"] - p["sl_initial"]), exit_time, exit_price, reason,
                {"atr_entry": p["atr"], "adx_setup": p.get("adx"), "setup_time": p.get("setup_time")},
            )
        )

    def run_pending_in_minutes(pend, rng):
        """Fill-then-stop resolution of a pending stop order over 1m bars."""
        nonlocal pos
        d = pend["direction"]
        for k in rng:
            o, h, l = m1_o[k], m1_h[k], m1_l[k]
            t = pd.Timestamp(m1_ts[k], tz="UTC")
            if d == "BUY" and h >= pend["price"]:
                entry = max(pend["price"], o)
            elif d == "SELL" and l <= pend["price"]:
                entry = min(pend["price"], o)
            else:
                continue
            p = {"direction": d, "entry": entry, "sl": pend["sl"], "sl_initial": pend["sl"], "atr": pend["atr"],
                 "entry_time": t, "adx": pend["adx"], "setup_time": pend["setup_time"]}
            funnel["filled"] += 1
            # Conservative: a stop touched inside the fill minute is a stop-out.
            hit = first_exit_in_minute(d, entry, h, l, p["sl"], None)
            if hit:
                close_trade(p, t, hit[0], "SL_same_minute_as_fill")
                return ("CLOSED", t, k)
            pos = p
            return ("FILLED", t, k)
        funnel["expired_unfilled"] += 1
        return ("EXPIRED", None, None)

    def run_position_in_minutes(rng):
        nonlocal pos
        for k in rng:
            o, h, l = m1_o[k], m1_h[k], m1_l[k]
            hit = first_exit_in_minute(pos["direction"], o, h, l, pos["sl"], None)
            if hit:
                t = pd.Timestamp(m1_ts[k], tz="UTC")
                close_trade(pos, t, hit[0], "SL")
                pos = None
                return ("CLOSED", t, k)
        return ("OPEN", None, None)

    def rescan_mid_bar(i: int, after_time):
        """After an exit inside bar i, live re-enters SEARCHING immediately and
        scans candles[-1] = bar i-1 (never scanned while IN_TRADE). The pending
        lives only for the remainder of bar i."""
        nonlocal state, pending, pos
        setup = scan_setup(i - 1)
        if setup is None:
            state = "SEARCHING"
            return
        res, t, k = run_pending_in_minutes(setup, minute_slice(i, after=after_time))
        if res == "FILLED":
            state = "IN_TRADE"
            r2, t2, _ = run_position_in_minutes(range(k + 1, minute_slice(i).stop))
            if r2 == "CLOSED":
                state = "SEARCHING"
                # a second exit inside the same bar: live would rescan bar i-1
                # again, but its pending was already consumed; stay SEARCHING.
        elif res == "CLOSED":
            state = "SEARCHING"
        else:
            state = "SEARCHING"  # expired at bar close

    for i in range(1, n):
        # ---- intrabar phase for bar i (price action inside this hour) ----
        if state == "IN_TRADE":
            res, t, k = run_position_in_minutes(minute_slice(i))
            if res == "CLOSED":
                rescan_mid_bar(i, t)
        elif state == "PENDING_PLACED":
            res, t, k = run_pending_in_minutes(pending, minute_slice(i))
            pending = None
            if res == "FILLED":
                state = "IN_TRADE"
                r2, t2, _ = run_position_in_minutes(range(k + 1, minute_slice(i).stop))
                if r2 == "CLOSED":
                    rescan_mid_bar(i, t2)
            elif res == "CLOSED":
                rescan_mid_bar(i, t)
            else:
                state = "SEARCHING"

        # ---- bar-close phase: trailing ratchet, then setup scan ----
        if state == "IN_TRADE" and pos is not None:
            window = bars[max(0, i - BTC_CANDLE_WINDOW + 1): i + 1]
            if len(window) >= btc_live.MIN_CANDLES_FOR_POSITION_MANAGEMENT:
                atr = btc_live.compute_atr_14(window)
                pos["sl"] = btc_live.calculate_structural_trailing_stop(pos["direction"], pos["sl"], window, atr)
        if state == "SEARCHING":
            setup = scan_setup(i)
            if setup is not None:
                pending = setup
                state = "PENDING_PLACED"

    return trades


# --------------------------------------------------------------------------
# US100: griff_engine_us100.py (15m NY pullback to EMA20)
# --------------------------------------------------------------------------
def simulate_us100(m1_utc: pd.DataFrame) -> list[dict]:
    m1 = m1_utc.tz_convert(ET)
    b15 = resample(m1, "15min")
    b15_start = b15.index
    b15_start_ns = b15_start.tz_convert("UTC").tz_localize(None).values
    b15_o, b15_h, b15_l, b15_c = (b15[c].values for c in ("open", "high", "low", "close"))

    m1_ts = m1.index
    m1_ns = m1_ts.tz_convert("UTC").tz_localize(None).values
    m1_o, m1_h, m1_l, m1_c = (m1[c].values for c in ("open", "high", "low", "close"))
    m1_hhmm = np.asarray(m1_ts.strftime("%H:%M"))
    m1_date = np.asarray(m1_ts.date)

    engine = US100Engine.__new__(US100Engine)  # live methods only; no broker
    trades: list[dict] = []

    # Cache of indicator state per completed-bar index: EMA(last completed), ATR(last completed), prev close.
    ind_cache: dict[int, tuple] = {}

    def indicators_for_completed(n_completed: int):
        """Live: candles = last 1000 (999 completed + forming). Returns
        (ema at last completed, Wilder ATR at last completed, last completed close, count)."""
        if n_completed in ind_cache:
            return ind_cache[n_completed]
        lo = max(0, n_completed - (US100_CANDLE_WINDOW - 1))
        window = [
            {"open": float(b15_o[j]), "high": float(b15_h[j]), "low": float(b15_l[j]), "close": float(b15_c[j])}
            for j in range(lo, n_completed)
        ]
        if len(window) < 25:  # live: `if len(candles) > 25`
            res = None
        else:
            ema = engine.compute_ema(window, 20)
            atr = engine.compute_atr(window, 14)
            res = (ema[-1], atr[-1], window[-1]["close"], len(window))
        ind_cache[n_completed] = res
        return res

    n = len(m1_ts)
    state = "SEARCHING"
    pos = None
    forming_idx = -1
    pf_h = pf_l = None  # partial forming-candle high/low

    def close(pos, t, price, reason):
        trades.append(make_trade("US100", pos["direction"], pos["entry_time"], pos["entry"], pos["sl"], pos["tp"],
                                 pos["sl_dist"], t, price, reason, {"atr_entry": pos["atr"]}))

    for k in range(n):
        hhmm = m1_hhmm[k]
        fi = np.searchsorted(b15_start_ns, m1_ns[k], "right") - 1
        if fi != forming_idx:
            forming_idx = fi
            pf_h, pf_l = m1_h[k], m1_l[k]
        else:
            pf_h = max(pf_h, m1_h[k])
            pf_l = min(pf_l, m1_l[k])
        o, h, l, c = m1_o[k], m1_h[k], m1_l[k], m1_c[k]
        t = m1_ts[k]

        if state == "IN_TRADE":
            # The broker holds SL/TP, so they act on every traded minute, including
            # overnight if an early-close day had no 16:00-16:15 ET bar to hard close on.
            if "16:00" <= hhmm < "16:15":
                close(pos, t, o, "HARD_CLOSE_16:00ET")
                pos = None
                state = "SEARCHING"
                continue
            hit = first_exit_in_minute(pos["direction"], o, h, l, pos["sl"], pos["tp"])
            if hit:
                close(pos, t, hit[0], hit[1])
                pos = None
                state = "SEARCHING"
                # live: SEARCHING again at once; a new entry may follow in this same minute
            else:
                continue

        if state == "SEARCHING" and "09:45" <= hhmm <= "11:30":
            ind = indicators_for_completed(forming_idx)  # completed bars are those before the forming one
            if ind is None:
                continue
            ema_prev, atr_prev, prev_close, _ = ind
            trend = "BUY" if prev_close > ema_prev else "SELL"
            # Live condition ask <= EMA(forming, incl. current price) is algebraically
            # equivalent to price <= EMA(last completed) because the EMA multiplier < 1.
            if trend == "BUY" and l <= ema_prev:
                entry = ema_prev if o > ema_prev else o
            elif trend == "SELL" and h >= ema_prev:
                entry = ema_prev if o < ema_prev else o
            else:
                continue
            # Live ATR = Wilder ATR including the forming candle's TR so far.
            tr_forming = max(pf_h - pf_l, abs(pf_h - prev_close), abs(pf_l - prev_close))
            atr = (atr_prev * 13 + tr_forming) / 14
            sl_dist = 1.5 * atr
            if sl_dist <= 0:
                continue
            if trend == "BUY":
                sl, tp = round(entry - sl_dist, 2), round(entry + 3.0 * atr, 2)
            else:
                sl, tp = round(entry + sl_dist, 2), round(entry - 3.0 * atr, 2)
            pos = {"direction": trend, "entry": entry, "sl": sl, "tp": tp, "sl_dist": abs(entry - sl), "atr": atr,
                   "entry_time": t, "ema_prev": ema_prev}
            state = "IN_TRADE"
            # conservative: stop touched in the entry minute is a stop-out
            hit = first_exit_in_minute(trend, entry, h, l, sl, None)
            if hit:
                close(pos, t, hit[0], "SL_same_minute_as_fill")
                pos = None
                state = "SEARCHING"
    if pos is not None:
        close(pos, m1_ts[n - 1], m1_c[n - 1], "DATA_END")
    return trades


# --------------------------------------------------------------------------
# GOLD: griff_engine_gold.py (15m Asian range breakout)
# --------------------------------------------------------------------------
def simulate_gold(m1_utc: pd.DataFrame) -> list[dict]:
    m1 = m1_utc.tz_convert(ET)
    b15 = resample(m1, "15min")
    b15_start_ns = b15.index.tz_convert("UTC").tz_localize(None).values
    b15_o, b15_h, b15_l, b15_c = (b15[c].values for c in ("open", "high", "low", "close"))

    m1_ts = m1.index
    m1_ns = m1_ts.tz_convert("UTC").tz_localize(None).values
    m1_o, m1_h, m1_l, m1_c = (m1[c].values for c in ("open", "high", "low", "close"))
    m1_hhmm = np.asarray(m1_ts.strftime("%H:%M"))
    m1_date = np.asarray(m1_ts.date)

    engine = GoldEngine.__new__(GoldEngine)  # live compute_atr only
    trades: list[dict] = []

    def candles_with_forming(fi: int, limit: int, pf):
        """Last `limit` 15m candles including the forming one (partial OHLC so far)."""
        lo = max(0, fi - (limit - 1))
        out = [
            {"open": float(b15_o[j]), "high": float(b15_h[j]), "low": float(b15_l[j]), "close": float(b15_c[j])}
            for j in range(lo, fi)
        ]
        out.append({"open": pf[0], "high": pf[1], "low": pf[2], "close": pf[3]})
        return out

    def close(pos, t, price, reason):
        trades.append(make_trade("GOLD", pos["direction"], pos["entry_time"], pos["entry"], pos["sl"], pos["tp"],
                                 pos["sl_dist"], t, price, reason, {"atr_entry": pos["atr"], "asian_high": pos["asian_high"],
                                                                     "asian_low": pos["asian_low"]}))

    n = len(m1_ts)
    state = "SEARCHING"
    pos = None
    asian_high = asian_low = 0.0
    day_triggered = False
    cur_date = None
    forming_idx = -1
    pf = None  # partial forming candle (o,h,l,c)

    for k in range(n):
        hhmm = m1_hhmm[k]
        if m1_date[k] != cur_date:
            # live resets day_triggered at 00:01 ET; the range is re-captured at 03:00
            cur_date = m1_date[k]
            day_triggered = False
            asian_high = asian_low = 0.0
        fi = np.searchsorted(b15_start_ns, m1_ns[k], "right") - 1
        if fi != forming_idx:
            forming_idx = fi
            pf = [m1_o[k], m1_h[k], m1_l[k], m1_c[k]]
        else:
            pf[1] = max(pf[1], m1_h[k]); pf[2] = min(pf[2], m1_l[k]); pf[3] = m1_c[k]
        o, h, l, c = m1_o[k], m1_h[k], m1_l[k], m1_c[k]
        t = m1_ts[k]

        if state == "IN_TRADE":
            if "16:00" <= hhmm < "16:15":
                close(pos, t, o, "HARD_CLOSE_16:00ET")
                pos = None
                state = "SEARCHING"
                continue
            hit = first_exit_in_minute(pos["direction"], o, h, l, pos["sl"], pos["tp"])
            if hit:
                close(pos, t, hit[0], hit[1])
                pos = None
                state = "SEARCHING"
            continue

        if day_triggered:
            continue
        if hhmm == "03:00":
            # live polls inside the 03:00 minute: 27 completed candles + the just-opened 03:00 candle
            cands = candles_with_forming(forming_idx, GOLD_RANGE_CANDLES, pf)
            if len(cands) >= GOLD_RANGE_CANDLES:
                asian_high = max(x["high"] for x in cands)
                asian_low = min(x["low"] for x in cands)
            continue
        if "03:15" <= hhmm <= "10:00" and asian_high > 0:
            buy_hit = h >= asian_high
            sell_hit = l <= asian_low
            if buy_hit and sell_hit:
                # both levels inside one minute: take the one nearer the minute's open
                buy_hit = abs(o - asian_high) <= abs(o - asian_low)
                sell_hit = not buy_hit
            if buy_hit:
                trend, entry = "BUY", (asian_high if o < asian_high else o)
            elif sell_hit:
                trend, entry = "SELL", (asian_low if o > asian_low else o)
            else:
                continue
            cands = candles_with_forming(forming_idx, GOLD_ATR_CANDLES, pf)
            atr = engine.compute_atr(cands, 14)[-1]
            sl_dist = 1.5 * atr
            if sl_dist <= 0:
                continue
            if trend == "BUY":
                sl, tp = round(entry - sl_dist, 2), round(entry + 3.0 * atr, 2)
            else:
                sl, tp = round(entry + sl_dist, 2), round(entry - 3.0 * atr, 2)
            pos = {"direction": trend, "entry": entry, "sl": sl, "tp": tp, "sl_dist": abs(entry - sl), "atr": atr,
                   "entry_time": t, "asian_high": asian_high, "asian_low": asian_low}
            state = "IN_TRADE"
            asian_high = 0.0
            day_triggered = True
            hit = first_exit_in_minute(trend, entry, h, l, sl, None)
            if hit:
                close(pos, t, hit[0], "SL_same_minute_as_fill")
                pos = None
                state = "SEARCHING"
    if pos is not None:
        close(pos, m1_ts[n - 1], m1_c[n - 1], "DATA_END")
    return trades


# --------------------------------------------------------------------------
# costs, sizing, portfolio
# --------------------------------------------------------------------------
def add_costed_r(trades: list[dict], costs: dict) -> None:
    for tr in trades:
        c = costs[tr["asset"]]
        sign = 1.0 if tr["direction"] == "BUY" else -1.0
        gross_per_unit = sign * (tr["exit"] - tr["entry"])
        net_per_unit = gross_per_unit - c["spread"]
        risk_per_unit = tr["sl_dist"]
        tr["r_gross"] = gross_per_unit / risk_per_unit
        # commission is per lot; one lot = contract_size units
        tr["r_net"] = net_per_unit / risk_per_unit - c["commission_per_lot"] / (risk_per_unit * c["contract_size"] * c["tick_value"])
        tr["win"] = tr["r_net"] > 0


def size_lots(asset: str, equity: float, risk_pct: float, sl_dist: float, costs: dict) -> float:
    c = costs[asset]
    if asset == "BTC":
        # griff_engine_live.calculate_position_size: 1.5*ATR stop, round 2dp, clamp [0.01, 50]
        atr = sl_dist / 1.5
        return btc_live.calculate_position_size(equity, atr, c["tick_value"], c["contract_size"], risk_pct, 0.01, 50.0)
    # US100Engine / GoldEngine.calculate_position_size: round(risk$/(sl*tick*contract), 2), require >= 0.01
    lots = round(equity * risk_pct / (sl_dist * c["tick_value"] * c["contract_size"]), 2)
    return lots if lots >= 0.01 else 0.0


def run_portfolio(trades: list[dict], risk: dict, costs: dict) -> dict:
    """Chronological shared-account replay. Lots are sized on the realized
    balance at entry time; PnL is booked at exit time."""
    ordered = sorted(trades, key=lambda t: t["entry_time"])
    import heapq

    equity = START_EQUITY
    open_exits: list[tuple] = []  # (exit_time, seq, pnl)
    seq = 0
    rows = []
    for tr in ordered:
        while open_exits and open_exits[0][0] <= tr["entry_time"]:
            _, _, pnl = heapq.heappop(open_exits)
            equity += pnl
        lots = size_lots(tr["asset"], equity, risk[tr["asset"]], tr["sl_dist"], costs)
        c = costs[tr["asset"]]
        units = lots * c["contract_size"]
        sign = 1.0 if tr["direction"] == "BUY" else -1.0
        pnl = sign * (tr["exit"] - tr["entry"]) * units - c["spread"] * units - c["commission_per_lot"] * lots
        risk_dollars = tr["sl_dist"] * units
        rows.append({**tr, "lots": lots, "equity_at_entry": equity, "risk_dollars": risk_dollars, "pnl": pnl})
        seq += 1
        heapq.heappush(open_exits, (tr["exit_time"], seq, pnl))
    while open_exits:
        _, _, pnl = heapq.heappop(open_exits)
        equity += pnl

    df = pd.DataFrame(rows)
    df = df.sort_values("exit_time").reset_index(drop=True)
    df["equity_after"] = START_EQUITY + df["pnl"].cumsum()

    # realized equity curve -> drawdown
    peak = np.maximum.accumulate(np.concatenate([[START_EQUITY], df["equity_after"].values]))[1:]
    df["dd_pct"] = (df["equity_after"] - peak) / peak * 100.0
    max_dd_pct = float(df["dd_pct"].min()) if len(df) else 0.0

    # daily (FTMO day = Europe/Prague calendar day) and monthly
    exit_local = pd.DatetimeIndex(df["exit_time"]).tz_convert(FTMO_TZ)
    df["ftmo_day"] = exit_local.date
    df["month"] = exit_local.strftime("%Y-%m")
    daily = df.groupby("ftmo_day")["pnl"].sum()
    daily_eq_end = START_EQUITY + daily.cumsum()
    daily_eq_start = daily_eq_end.shift(1).fillna(START_EQUITY)
    daily_pct = daily / daily_eq_start * 100.0
    daily_df = pd.DataFrame({"pnl": daily, "equity_start": daily_eq_start, "equity_end": daily_eq_end, "pct": daily_pct})

    months = pd.period_range(exit_local.min().tz_localize(None).to_period("M"), exit_local.max().tz_localize(None).to_period("M"), freq="M").strftime("%Y-%m")
    monthly_pnl = df.groupby("month")["pnl"].sum().reindex(months).fillna(0.0)
    monthly_eq_end = START_EQUITY + monthly_pnl.cumsum()
    monthly_eq_start = monthly_eq_end.shift(1).fillna(START_EQUITY)
    monthly_pct = monthly_pnl / monthly_eq_start * 100.0
    per_asset_month = df.pivot_table(index="month", columns="asset", values="pnl", aggfunc="sum").reindex(months).fillna(0.0)
    monthly_df = pd.DataFrame({"pnl": monthly_pnl, "equity_start": monthly_eq_start, "equity_end": monthly_eq_end, "pct": monthly_pct})
    for a in ("BTC", "US100", "GOLD"):
        monthly_df[f"pnl_{a}"] = per_asset_month[a] if a in per_asset_month else 0.0
    trades_per_month = df.groupby("month").size().reindex(months).fillna(0).astype(int)
    monthly_df["trades"] = trades_per_month

    return {"trades": df, "daily": daily_df, "monthly": monthly_df, "final_equity": float(equity), "max_dd_pct": max_dd_pct}


def month_stats(monthly: pd.DataFrame, complete_months: list[str]) -> dict:
    m = monthly.loc[monthly.index.isin(complete_months), "pct"]
    return {
        "n_months": int(len(m)),
        "median_pct": float(m.median()),
        "mean_pct": float(m.mean()),
        "best_pct": float(m.max()),
        "best_month": str(m.idxmax()),
        "worst_pct": float(m.min()),
        "worst_month": str(m.idxmin()),
        "months_ge_10pct": int((m >= 10.0).sum()),
        "months_ge_10pct_list": [str(x) for x in m[m >= 10.0].index],
        "months_le_minus10pct": int((m <= -10.0).sum()),
        "months_positive": int((m > 0).sum()),
    }


def per_asset_stats(port_trades: pd.DataFrame, asset: str) -> dict:
    d = port_trades[port_trades["asset"] == asset]
    if d.empty:
        return {"n": 0}
    wins = d[d["r_net"] > 0]
    losses = d[d["r_net"] <= 0]
    gross_win = d.loc[d["pnl"] > 0, "pnl"].sum()
    gross_loss = -d.loc[d["pnl"] < 0, "pnl"].sum()
    best = d.loc[d["r_net"].idxmax()]
    return {
        "n": int(len(d)),
        "win_rate_pct": float(len(wins) / len(d) * 100.0),
        "expectancy_r": float(d["r_net"].mean()),
        "sum_r": float(d["r_net"].sum()),
        "best_trade": {"entry_time": str(best["entry_time"]), "r_net": float(best["r_net"]), "pnl": float(best["pnl"])},
        "sum_r_ex_best": float(d["r_net"].sum() - best["r_net"]),
        "expectancy_r_ex_best": float((d["r_net"].sum() - best["r_net"]) / max(len(d) - 1, 1)),
        "pnl_usd_ex_best": float(d["pnl"].sum() - best["pnl"]),
        "avg_win_r": float(wins["r_net"].mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses["r_net"].mean()) if len(losses) else 0.0,
        "pnl_usd": float(d["pnl"].sum()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "avg_lots": float(d["lots"].mean()),
        "exit_reasons": {str(k): int(v) for k, v in d["exit_reason"].value_counts().items()},
    }


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--trades-cache", default=None,
                    help="optional pickle path (outside the repo) to reuse raw simulated trades while iterating on reporting")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.trades_cache) if args.trades_cache else None

    costs = load_specs()
    manifest = {"run_date": RUN_DATE, "generated_utc": datetime.now(timezone.utc).isoformat(), "feeds": {}, "costs": costs,
                "stacks": STACKS, "start_equity": START_EQUITY}

    raw = {}
    for asset, path in FEEDS.items():
        if not path.exists():
            raise SystemExit(f"UNKNOWN: feed for {asset} missing at {path}")
        df = load_m1(path)
        raw[asset] = df
        manifest["feeds"][asset] = {
            "path": str(path.relative_to(REPO)),
            "sha256": sha256_of(path),
            "rows_after_flat_clean": int(len(df)),
            "first_utc": df.index.min().isoformat(),
            "last_utc": df.index.max().isoformat(),
            "price_side": "bid",
            "source": "Dukascopy via dukascopy-node 1.50.0 (repo downloader path: data/downloaders/fetch_all_data.py)",
        }
        print(f"[{asset}] {len(df):,} 1m rows {df.index.min()} -> {df.index.max()}", flush=True)

    import pickle

    if cache and cache.exists():
        with open(cache, "rb") as fh:
            btc, us100, gold, cached_funnel = pickle.load(fh)
            FUNNEL.update(cached_funnel)
        print(f"loaded cached raw trades from {cache}", flush=True)
    else:
        print("simulating BTC (griff_engine_live.py rules)...", flush=True)
        btc = simulate_btc(raw["BTC"])
        print(f"  BTC trades: {len(btc)}", flush=True)
        print("simulating US100 (griff_engine_us100.py rules)...", flush=True)
        us100 = simulate_us100(raw["US100"])
        print(f"  US100 trades: {len(us100)}", flush=True)
        print("simulating GOLD (griff_engine_gold.py rules)...", flush=True)
        gold = simulate_gold(raw["GOLD"])
        print(f"  GOLD trades: {len(gold)}", flush=True)
        if cache:
            with open(cache, "wb") as fh:
                pickle.dump((btc, us100, gold, dict(FUNNEL)), fh)

    all_trades = btc + us100 + gold
    add_costed_r(all_trades, costs)

    # complete calendar months: the feed must cover the month to within one day at each edge
    feed_start = min(df.index.min() for df in raw.values()).tz_convert(FTMO_TZ).tz_localize(None)
    feed_end = max(df.index.max() for df in raw.values()).tz_convert(FTMO_TZ).tz_localize(None)
    all_months = pd.period_range(feed_start.to_period("M"), feed_end.to_period("M"), freq="M")
    complete = []
    for p in all_months:
        if feed_start <= p.start_time + pd.Timedelta(days=1) and feed_end >= p.end_time - pd.Timedelta(days=1):
            complete.append(p.strftime("%Y-%m"))
    manifest["setup_funnel"] = dict(FUNNEL)
    manifest["complete_months"] = complete
    manifest["partial_months_excluded"] = [p.strftime("%Y-%m") for p in all_months if p.strftime("%Y-%m") not in complete]

    summary = {"manifest": manifest, "stacks": {}}
    for stack_name, risk in STACKS.items():
        port = run_portfolio(all_trades, risk, costs)
        tdf, daily, monthly = port["trades"], port["daily"], port["monthly"]
        tdf.to_csv(out / f"trades_{stack_name}_{RUN_DATE}.csv", index=False)
        daily.to_csv(out / f"daily_{stack_name}_{RUN_DATE}.csv")
        monthly.to_csv(out / f"monthly_{stack_name}_{RUN_DATE}.csv")
        worst_day = daily["pct"].idxmin()
        s = {
            "risk": risk,
            "final_equity": port["final_equity"],
            "total_return_pct": (port["final_equity"] - START_EQUITY) / START_EQUITY * 100.0,
            "max_drawdown_pct_realized": port["max_dd_pct"],
            "worst_day": {"date": str(worst_day), "pnl": float(daily.loc[worst_day, "pnl"]), "pct": float(daily.loc[worst_day, "pct"])},
            "best_day": {"date": str(daily["pct"].idxmax()), "pct": float(daily["pct"].max())},
            "days_le_minus5pct": int((daily["pct"] <= -5.0).sum()),
            "min_realized_equity": float(tdf["equity_after"].min()),
            "breached_90k_floor": bool(tdf["equity_after"].min() <= 90_000.0),
            "months": month_stats(monthly, complete),
            "per_asset": {a: per_asset_stats(tdf, a) for a in ("BTC", "US100", "GOLD")},
            "n_trades": int(len(tdf)),
        }
        summary["stacks"][stack_name] = s
        print(f"\n=== {stack_name} ===")
        print(json.dumps({k: v for k, v in s.items() if k != "per_asset"}, indent=1, default=str))
        for a, st in s["per_asset"].items():
            print(a, json.dumps(st, default=str))

    with open(out / f"summary_{RUN_DATE}.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # markdown tables for the report
    lines = []
    for stack_name, s in summary["stacks"].items():
        lines.append(f"### Stack {stack_name}  (BTC {s['risk']['BTC']*100:.2f}% / US100 {s['risk']['US100']*100:.2f}% / Gold {s['risk']['GOLD']*100:.2f}%)\n")
        lines.append("| Asset | N | Win rate | Expectancy (R, net of costs) | Sum R | Avg win R | Avg loss R | Profit factor | $ PnL |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for a in ("BTC", "US100", "GOLD"):
            st = s["per_asset"][a]
            lines.append(f"| {a} | {st['n']} | {st['win_rate_pct']:.1f}% | {st['expectancy_r']:+.3f} | {st['sum_r']:+.1f} | {st['avg_win_r']:+.2f} | {st['avg_loss_r']:+.2f} | {st['profit_factor']:.2f} | {st['pnl_usd']:+,.0f} |")
        m = s["months"]
        lines.append("")
        lines.append(f"Portfolio: final equity ${s['final_equity']:,.0f} ({s['total_return_pct']:+.2f}% over the window), "
                     f"max realized drawdown {s['max_drawdown_pct_realized']:.2f}%, worst FTMO day {s['worst_day']['date']} "
                     f"{s['worst_day']['pct']:+.2f}% (${s['worst_day']['pnl']:+,.0f}), days <= -5%: {s['days_le_minus5pct']}, "
                     f"min realized equity ${s['min_realized_equity']:,.0f}.")
        lines.append("")
        lines.append(f"Calendar months (n={m['n_months']} complete): median {m['median_pct']:+.2f}%, mean {m['mean_pct']:+.2f}%, "
                     f"best {m['best_pct']:+.2f}% ({m['best_month']}), worst {m['worst_pct']:+.2f}% ({m['worst_month']}), "
                     f"months >= +10%: {m['months_ge_10pct']} {m['months_ge_10pct_list']}, months <= -10%: {m['months_le_minus10pct']}, "
                     f"positive months: {m['months_positive']}/{m['n_months']}.")
        lines.append("")
    # month-by-month side by side
    ma = summary["stacks"]["A_live"]
    mon_a = pd.read_csv(out / f"monthly_A_live_{RUN_DATE}.csv", index_col=0)
    mon_b = pd.read_csv(out / f"monthly_B_proposed_{RUN_DATE}.csv", index_col=0)
    lines.append("### Month by month (realized, FTMO CE(S)T calendar months)\n")
    lines.append("| Month | Trades | A: BTC $ | A: US100 $ | A: Gold $ | A: total $ | A: % | B: total $ | B: % |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for mth in mon_a.index:
        a = mon_a.loc[mth]; b = mon_b.loc[mth]
        flag = "" if mth in complete else " (partial)"
        lines.append(f"| {mth}{flag} | {int(a['trades'])} | {a['pnl_BTC']:+,.0f} | {a['pnl_US100']:+,.0f} | {a['pnl_GOLD']:+,.0f} | {a['pnl']:+,.0f} | {a['pct']:+.2f}% | {b['pnl']:+,.0f} | {b['pct']:+.2f}% |")
    with open(out / f"tables_{RUN_DATE}.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
