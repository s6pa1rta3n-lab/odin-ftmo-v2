#!/usr/bin/env python3
"""Candidate 10: C5 entry + R-multiple trail runner (1.0×R behind extreme).

Research only. No live VM / MetaAPI / C4 / drip / FREEZE touches.
Do NOT re-run hard R=2/R=3 (C8 REJECT). Cost model: C4/C5 0.065% + swap.

C9 lesson: ATR(14)×1 trail never left BE (ATR ≫ 412.91). C10 uses fixed
1.0×R (412.91) trail behind favorable extreme so the trail can engage.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/workspace/btc-strategies")
from run_sma50_short_harden import (
    DUKAS_MAIN,
    DUKAS_EXT,
    WORST_DAY_BUDGET,
    BUY_ONLY_HOLDOUT_NET,
    HO_START,
    HO_END,
    EXT_START,
    FIT_START,
    FIT_END,
    COMMISSION_PCT,
    SWAP_ANNUAL,
    parse_csv,
    merge_bars,
    utc_dt,
    et_day,
    ym_et,
    build_daily_closes,
    sma_map,
    midnight_index,
    fmt,
    pct,
    Bar,
)
from run_candidate_5 import (
    daily_tr_atr,
    build_daily_ohlc,
    percentile,
    SLOPE_LOOKBACK,
    ATR_WINDOW,
    ATR_PCTILE,
)

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

OUT = Path("/workspace/btc-strategies/candidate-10-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-10.md")

STOP = Decimal("412.91")
ONE_R = STOP
EMERGENCY_R = Decimal("5")
EMERGENCY_DIST = STOP * EMERGENCY_R  # 2064.55
TRAIL_R = Decimal("1.0")  # a priori: trail distance = TRAIL_R × ONE_R (= STOP)
TRAIL_DIST = ONE_R * TRAIL_R  # 412.91
START_EQUITY = Decimal("100000")
RISK = Decimal("0.01")  # 1.0% primary Gate B
RISK_HALF = Decimal("0.005")  # 0.5% also reported
DAILY_KILL = Decimal("-0.03")
MIN_LOT = Decimal("0.01")
BASE_LOT = Decimal("0.01")

WINDOW_DAYS = 60
CHALLENGE_MULT = Decimal("1.10")
BOTH_MULT = Decimal("1.155")
FLOOR_MULT = Decimal("0.90")
DAY_FAIL = Decimal("-0.05")
MAX_DD_LIM = Decimal("0.10")
FIT_SOFT_01 = Decimal("-5000")
PACE_TARGET_MO = Decimal("7500")
DAYS_PER_MO = Decimal("30.44")


@dataclass
class Trade01:
    side: str
    entry_ts: int
    entry: Decimal
    exit_ts: int
    exit: Decimal
    reason: str
    pnl_raw: Decimal
    commission: Decimal
    swap: Decimal
    max_fav_r: Decimal = Decimal(0)
    activated: bool = False

    @property
    def pnl_full(self) -> Decimal:
        return self.pnl_raw - self.commission - self.swap


@dataclass
class TradeEq:
    side: str
    entry_ts: int
    entry: Decimal
    exit_ts: int
    exit: Decimal
    reason: str
    lots: Decimal
    stop_dist: Decimal
    pnl: Decimal
    equity_after: Decimal
    prague_exit: date
    max_fav_r: Decimal = Decimal(0)
    activated: bool = False


@dataclass
class Meta:
    name: str
    trades: list = field(default_factory=list)
    regime_long: int = 0
    regime_short: int = 0
    regime_flat: int = 0
    regime_unknown: int = 0
    skipped_no_bar: int = 0
    skipped_in_trade: int = 0
    skipped_filter: int = 0
    skip_slope: int = 0
    skip_vol: int = 0
    skipped_kill: int = 0
    skipped_lots: int = 0
    entry_ops: int = 0
    n_activated: int = 0
    n_trail_exit: int = 0
    n_be_exit: int = 0
    n_init_stop: int = 0
    n_emergency: int = 0


def bar_utc_day(ts: int) -> datetime:
    return utc_dt(ts).replace(hour=0, minute=0, second=0, microsecond=0)


def raw_pnl(side, entry, exit_px):
    return (exit_px - entry) if side == "long" else (entry - exit_px)


def commission_scaled(entry, exit_px, lots):
    return (entry + exit_px) * lots * COMMISSION_PCT


def swap_scaled(entry, entry_ts, exit_ts, lots):
    start = utc_dt(entry_ts)
    end = utc_dt(exit_ts)
    first_mid = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    n = 0
    cur = first_mid
    while cur <= end:
        n += 1
        cur += timedelta(days=1)
    if n <= 0:
        return Decimal(0)
    return entry * lots * SWAP_ANNUAL / Decimal(360) * Decimal(n)


def prague_day_ms(ms: int) -> date:
    return utc_dt(ms).astimezone(PRAGUE).date()


def round_lots(x: Decimal) -> Decimal:
    return max(MIN_LOT, (x * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / Decimal(100))


def filters_ok(side, prior, days_sorted, day_index, sma50, atr_map) -> tuple[bool, str]:
    idx = day_index.get(prior)
    if idx is None or idx < SLOPE_LOOKBACK:
        return False, "slope"
    ago = days_sorted[idx - SLOPE_LOOKBACK]
    s_ago = sma50.get(ago)
    ps = sma50.get(prior)
    if s_ago is None or ps is None:
        return False, "slope"
    if side == "long" and not (ps > s_ago):
        return False, "slope"
    if side == "short" and not (ps < s_ago):
        return False, "slope"

    atr_p = atr_map.get(prior)
    if atr_p is None or idx < ATR_WINDOW - 1:
        return False, "vol"
    window_days = days_sorted[idx - (ATR_WINDOW - 1) : idx + 1]
    vals = [atr_map[d] for d in window_days if atr_map.get(d) is not None]
    if len(vals) < 50:
        return False, "vol"
    thr = percentile(vals, ATR_PCTILE)
    if atr_p >= thr:
        return False, "vol"
    return True, ""


def atr_for_bar(atr_map, bar_ts: int, cache_last: list) -> Decimal | None:
    """Prior completed UTC day ATR for this bar's day. cache_last is [last_atr] mutable."""
    d = bar_utc_day(bar_ts)
    prior = d - timedelta(days=1)
    a = atr_map.get(prior)
    if a is not None:
        cache_last[0] = a
        return a
    return cache_last[0]


def scan_trail_exit(bars, start_i, side, entry, atr_map=None, trail_dist=TRAIL_DIST):
    """
    Locked C10 exit (R-multiple trail — NOT ATR):
      initial SL = entry ± STOP
      activate at +1R → SL = entry (BE)
      then trail: SL = extreme ± trail_dist (1.0×R), never widen
        long:  trail SL = highest high since entry − trail_dist
        short: trail SL = lowest low since entry + trail_dist
      emergency TP at +5R
    atr_map unused (kept for call-site compatibility with C9).
    Returns: j, fill, reason, max_fav_r, activated
    """
    if side == "long":
        sl = entry - STOP
        emergency_tp = entry + EMERGENCY_DIST
        act_level = entry + ONE_R
        extreme = bars[start_i].h  # favorable extreme since entry
    else:
        sl = entry + STOP
        emergency_tp = entry - EMERGENCY_DIST
        act_level = entry - ONE_R
        extreme = bars[start_i].l

    activated = False
    max_fav = Decimal(0)

    for j in range(start_i, len(bars)):
        b = bars[j]

        # Favorable excursion / extreme tracking (include this bar)
        if side == "long":
            if b.h > extreme:
                extreme = b.h
            fav = extreme - entry
        else:
            if b.l < extreme:
                extreme = b.l
            fav = entry - extreme
        if fav > max_fav:
            max_fav = fav
        max_fav_r = max_fav / ONE_R if ONE_R > 0 else Decimal(0)

        # --- Exit checks using SL / emergency from start of bar ---
        if side == "long":
            hit_sl = b.l <= sl
            hit_em = b.h >= emergency_tp
            gap_sl = b.o <= sl
            gap_em = b.o >= emergency_tp
        else:
            hit_sl = b.h >= sl
            hit_em = b.l <= emergency_tp
            gap_sl = b.o >= sl
            gap_em = b.o <= emergency_tp

        if hit_sl and hit_em:
            # conservative: stop wins
            if gap_sl and not gap_em:
                reason = "gap-stop"
                fill = b.o
            elif gap_em and not gap_sl:
                reason = "gap-emergency"
                fill = b.o
            else:
                reason = "both-stop"
                fill = sl
            return j, fill, reason, max_fav_r, activated
        if hit_sl:
            if gap_sl:
                return j, b.o, "gap-stop", max_fav_r, activated
            # classify stop type
            if not activated:
                reason = "init-stop"
            elif sl == entry:
                reason = "be-stop"
            else:
                reason = "trail-stop"
            return j, sl, reason, max_fav_r, activated
        if hit_em:
            if gap_em:
                return j, b.o, "gap-emergency", max_fav_r, activated
            return j, emergency_tp, "emergency-tp", max_fav_r, activated

        # --- Activate BE if +1R reached this bar ---
        if not activated:
            reached = (b.h >= act_level) if side == "long" else (b.l <= act_level)
            if reached:
                activated = True
                sl = entry  # breakeven

        # --- R-multiple trail ratchet after activation ---
        # long: SL = highest_high_since_entry − TRAIL_DIST; never widen
        # short: SL = lowest_low_since_entry + TRAIL_DIST; never widen
        if activated:
            if side == "long":
                cand = extreme - trail_dist
                if cand > sl:
                    sl = cand
            else:
                cand = extreme + trail_dist
                if cand < sl:
                    sl = cand

    return len(bars) - 1, bars[-1].c, "open-eod", max_fav / ONE_R if ONE_R else Decimal(0), activated


def hard_r1_exit(bars, start_i, side, entry):
    """C5-style hard R=1 for buy-only baseline only."""
    if side == "long":
        sl, tp = entry - STOP, entry + STOP
    else:
        sl, tp = entry + STOP, entry - STOP
    for j in range(start_i, len(bars)):
        b = bars[j]
        if side == "long":
            hit_sl, hit_tp = b.l <= sl, b.h >= tp
            gap_sl, gap_tp = b.o <= sl, b.o >= tp
        else:
            hit_sl, hit_tp = b.h >= sl, b.l <= tp
            gap_sl, gap_tp = b.o >= sl, b.o <= tp
        if not hit_sl and not hit_tp:
            continue
        if hit_sl and hit_tp:
            if gap_sl and not gap_tp:
                return j, b.o, "gap-stop"
            if gap_tp and not gap_sl:
                return j, tp, "gap-target"
            return j, sl, "both-stop"
        if hit_sl:
            return j, (b.o if gap_sl else sl), ("gap-stop" if gap_sl else "stop")
        return j, tp, "target"
    return len(bars) - 1, bars[-1].c, "open-eod"


def run_catalogue_01(
    bars, daily_closes, sma50, atr_map, start, end, *, use_filters=True, name="c10-01"
):
    res = Meta(name=name)
    midnight = midnight_index(bars)
    days_sorted = sorted(daily_closes)
    day_index = {d: i for i, d in enumerate(days_sorted)}
    free_after = 0

    day = start
    while day <= end:
        res.entry_ops += 1
        prior = day - timedelta(days=1)
        pc = daily_closes.get(prior)
        ps = sma50.get(prior)
        if pc is None or ps is None:
            res.regime_unknown += 1
            day += timedelta(days=1)
            continue
        if pc > ps:
            res.regime_long += 1
            side = "long"
        elif pc < ps:
            res.regime_short += 1
            side = "short"
        else:
            res.regime_flat += 1
            day += timedelta(days=1)
            continue

        if use_filters:
            ok, why = filters_ok(side, prior, days_sorted, day_index, sma50, atr_map)
            if not ok:
                res.skipped_filter += 1
                if why == "slope":
                    res.skip_slope += 1
                else:
                    res.skip_vol += 1
                day += timedelta(days=1)
                continue

        i = midnight.get(day)
        if i is None:
            res.skipped_no_bar += 1
            day += timedelta(days=1)
            continue
        entry_ts = bars[i].ts
        if entry_ts < free_after:
            res.skipped_in_trade += 1
            day += timedelta(days=1)
            continue

        entry_px = bars[i].o
        j, fill, reason, max_fav_r, activated = scan_trail_exit(
            bars, i, side, entry_px, atr_map, TRAIL_DIST
        )
        if activated:
            res.n_activated += 1
        if reason in ("trail-stop",):
            res.n_trail_exit += 1
        elif reason in ("be-stop",):
            res.n_be_exit += 1
        elif reason in ("init-stop", "gap-stop", "both-stop"):
            res.n_init_stop += 1
        elif reason in ("emergency-tp", "gap-emergency"):
            res.n_emergency += 1

        if reason == "open-eod":
            pnl = comm = sw = Decimal(0)
            free_after = bars[-1].ts + 1
        else:
            pnl = raw_pnl(side, entry_px, fill)
            comm = commission_scaled(entry_px, fill, BASE_LOT)
            sw = swap_scaled(entry_px, entry_ts, bars[j].ts, BASE_LOT)
            free_after = bars[j].ts + 1
        res.trades.append(
            Trade01(
                side, entry_ts, entry_px, bars[j].ts, fill, reason, pnl, comm, sw,
                max_fav_r, activated,
            )
        )
        day += timedelta(days=1)
    return res


def run_equity(
    bars,
    daily_closes,
    sma50,
    atr_map,
    start,
    end,
    *,
    risk=RISK,
    use_filters=True,
    name="c10-eq",
    daily_kill=True,
):
    res = Meta(name=name)
    midnight = midnight_index(bars)
    days_sorted = sorted(daily_closes)
    day_index = {d: i for i, d in enumerate(days_sorted)}
    free_after = 0
    equity = START_EQUITY
    day_pnl: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
    day_start_eq: dict[date, Decimal] = {}
    killed_days: set[date] = set()
    peak = equity
    max_dd = Decimal(0)

    day = start
    while day <= end:
        res.entry_ops += 1
        prior = day - timedelta(days=1)
        pc = daily_closes.get(prior)
        ps = sma50.get(prior)
        if pc is None or ps is None:
            res.regime_unknown += 1
            day += timedelta(days=1)
            continue
        if pc > ps:
            res.regime_long += 1
            side = "long"
        elif pc < ps:
            res.regime_short += 1
            side = "short"
        else:
            res.regime_flat += 1
            day += timedelta(days=1)
            continue

        if use_filters:
            ok, why = filters_ok(side, prior, days_sorted, day_index, sma50, atr_map)
            if not ok:
                res.skipped_filter += 1
                if why == "slope":
                    res.skip_slope += 1
                else:
                    res.skip_vol += 1
                day += timedelta(days=1)
                continue

        i = midnight.get(day)
        if i is None:
            res.skipped_no_bar += 1
            day += timedelta(days=1)
            continue
        entry_ts = bars[i].ts
        if entry_ts < free_after:
            res.skipped_in_trade += 1
            day += timedelta(days=1)
            continue

        pd_entry = prague_day_ms(entry_ts)
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if daily_kill and pd_entry in killed_days:
            res.skipped_kill += 1
            day += timedelta(days=1)
            continue
        if daily_kill and day_start_eq[pd_entry] > 0:
            so_far = day_pnl[pd_entry] / day_start_eq[pd_entry]
            if so_far <= DAILY_KILL:
                killed_days.add(pd_entry)
                res.skipped_kill += 1
                day += timedelta(days=1)
                continue

        if equity <= START_EQUITY * FLOOR_MULT or equity <= Decimal("0"):
            res.skipped_lots += 1
            day += timedelta(days=1)
            continue

        risk_dollars = equity * risk
        scale = risk_dollars / STOP
        lots = round_lots(BASE_LOT * scale)
        if lots < MIN_LOT or scale <= 0:
            res.skipped_lots += 1
            day += timedelta(days=1)
            continue
        scale = lots / BASE_LOT

        entry_px = bars[i].o
        j, fill, reason, max_fav_r, activated = scan_trail_exit(
            bars, i, side, entry_px, atr_map, TRAIL_DIST
        )
        if activated:
            res.n_activated += 1
        if reason == "open-eod":
            free_after = bars[-1].ts + 1
            day += timedelta(days=1)
            continue

        price_pnl = raw_pnl(side, entry_px, fill)
        raw_dollars = price_pnl * scale
        comm = commission_scaled(entry_px, fill, lots)
        sw = swap_scaled(entry_px, entry_ts, bars[j].ts, lots)
        pnl = raw_dollars - comm - sw
        equity = equity + pnl
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else Decimal(0)
        if dd > max_dd:
            max_dd = dd

        pd_exit = prague_day_ms(bars[j].ts)
        if pd_exit not in day_start_eq:
            day_start_eq[pd_exit] = equity - pnl
        day_pnl[pd_exit] += pnl
        if daily_kill and day_start_eq[pd_exit] > 0:
            if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
                killed_days.add(pd_exit)

        free_after = bars[j].ts + 1
        res.trades.append(
            TradeEq(
                side, entry_ts, entry_px, bars[j].ts, fill, reason, lots, STOP,
                pnl, equity, pd_exit, max_fav_r, activated,
            )
        )
        day += timedelta(days=1)

    res.max_dd = max_dd  # type: ignore
    res.final_equity = equity  # type: ignore
    res.day_pnl = dict(day_pnl)  # type: ignore
    res.day_start_eq = day_start_eq  # type: ignore
    res.killed_days = killed_days  # type: ignore
    return res


def summarize_01(trades: list[Trade01]):
    closed = [t for t in trades if t.reason != "open-eod"]
    long_t = [t for t in closed if t.side == "long"]
    short_t = [t for t in closed if t.side == "short"]

    def pack(ts):
        if not ts:
            return {
                "n": 0, "wins": 0, "losses": 0, "win_rate": Decimal(0),
                "net_raw": Decimal(0), "net_full": Decimal(0),
                "avg_win": Decimal(0), "avg_loss": Decimal(0),
                "avg_max_r": Decimal(0),
            }
        wins_t = [t for t in ts if t.pnl_raw > 0]
        losses_t = [t for t in ts if t.pnl_raw < 0]
        wins = len(wins_t)
        return {
            "n": len(ts),
            "wins": wins,
            "losses": len(losses_t),
            "win_rate": Decimal(wins) / Decimal(len(ts)),
            "net_raw": sum((t.pnl_raw for t in ts), Decimal(0)),
            "net_full": sum((t.pnl_full for t in ts), Decimal(0)),
            "avg_win": (sum((t.pnl_raw for t in wins_t), Decimal(0)) / Decimal(wins)) if wins else Decimal(0),
            "avg_loss": (sum((t.pnl_raw for t in losses_t), Decimal(0)) / Decimal(len(losses_t))) if losses_t else Decimal(0),
            "avg_max_r": sum((t.max_fav_r for t in ts), Decimal(0)) / Decimal(len(ts)),
        }

    daily_raw = defaultdict(lambda: Decimal(0))
    month_full = defaultdict(lambda: Decimal(0))
    month_n = defaultdict(int)
    reasons = defaultdict(int)
    for t in closed:
        daily_raw[et_day(t.exit_ts)] += t.pnl_raw
        m = ym_et(t.exit_ts)
        month_full[m] += t.pnl_full
        month_n[m] += 1
        reasons[t.reason] += 1
    worst = (
        min(daily_raw.items(), key=lambda kv: (kv[1], kv[0]))
        if daily_raw else ("none", Decimal(0))
    )
    months = {m: {"n": month_n[m], "net_full": month_full[m]} for m in sorted(month_full)}
    pos_m = sum(1 for v in months.values() if v["net_full"] >= 0)
    n_m = len(months)
    n_act = sum(1 for t in closed if t.activated)
    return {
        "all": pack(closed),
        "long": pack(long_t),
        "short": pack(short_t),
        "worst_raw": worst,
        "days_breach_raw": sum(1 for v in daily_raw.values() if v < WORST_DAY_BUDGET),
        "months": months,
        "month_pos": pos_m,
        "month_n": n_m,
        "month_pos_rate": (Decimal(pos_m) / Decimal(n_m)) if n_m else Decimal(0),
        "reasons": dict(reasons),
        "n_activated": n_act,
    }


def leave_out_two_best(trades: list[Trade01]):
    s = summarize_01(trades)
    months = [(m, v["net_full"]) for m, v in s["months"].items() if v["n"] > 0]
    top2 = [m for m, _ in sorted(months, key=lambda kv: kv[1], reverse=True)[:2]]
    kept = [t for t in trades if t.reason == "open-eod" or ym_et(t.exit_ts) not in top2]
    return top2, summarize_01(kept)


def count_60d_pass_windows(trades: list[TradeEq], day_pnl, day_start_eq):
    if not trades:
        return 0, 0, []
    exits_sorted = sorted(
        [(utc_dt(t.exit_ts), t.prague_exit, t.equity_after) for t in trades],
        key=lambda x: x[0],
    )
    all_days = sorted(set(day_start_eq.keys()) | {t.prague_exit for t in trades})
    if not all_days:
        return 0, 0, []
    first_day, last_day = all_days[0], all_days[-1]
    end_limit = last_day - timedelta(days=WINDOW_DAYS - 1)
    passes = []
    n_windows = 0
    cur = first_day
    while cur <= end_limit:
        ws, we = cur, cur + timedelta(days=WINDOW_DAYS - 1)
        n_windows += 1
        start_eq = START_EQUITY
        for ts, pd, eq in exits_sorted:
            if pd < ws:
                start_eq = eq
            else:
                break
        window_exits = [(pd, eq) for ts, pd, eq in exits_sorted if ws <= pd <= we]
        if not window_exits:
            cur += timedelta(days=1)
            continue
        max_eq = max(eq for _, eq in window_exits)
        min_eq = min(eq for _, eq in window_exits)
        hit_10 = max_eq >= start_eq * CHALLENGE_MULT
        hit_15 = max_eq >= start_eq * BOTH_MULT
        floor_ok = min_eq > start_eq * FLOOR_MULT
        day_fail = False
        worst_day_in = Decimal(0)
        d = ws
        while d <= we:
            if d in day_pnl and d in day_start_eq and day_start_eq[d] > 0:
                p = day_pnl[d] / day_start_eq[d]
                if p < worst_day_in:
                    worst_day_in = p
                if p <= DAY_FAIL:
                    day_fail = True
                    break
            d += timedelta(days=1)
        ok = hit_10 and hit_15 and floor_ok and not day_fail
        if ok:
            passes.append(
                {
                    "start": ws.isoformat(),
                    "end": we.isoformat(),
                    "start_eq": float(start_eq),
                    "max_mult": float(max_eq / start_eq) if start_eq else 0,
                    "min_mult": float(min_eq / start_eq) if start_eq else 0,
                    "worst_day": float(worst_day_in),
                }
            )
        cur += timedelta(days=1)
    return len(passes), n_windows, passes[:20]


def max_realized_dd(trades: list[TradeEq]) -> Decimal:
    if not trades:
        return Decimal(0)
    peak = START_EQUITY
    max_dd = Decimal(0)
    for t in trades:
        eq = t.equity_after
        peak = max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def worst_day_pct(day_pnl, day_start_eq):
    worst_d, worst_p = None, Decimal(0)
    for d, pnl in day_pnl.items():
        se = day_start_eq.get(d)
        if se and se > 0:
            p = pnl / se
            if p < worst_p:
                worst_p = p
                worst_d = d
    return worst_d, worst_p


def monthly_pace(net: Decimal, days: int) -> Decimal:
    if days <= 0:
        return Decimal(0)
    return net / (Decimal(days) / DAYS_PER_MO)


def days_to_target(pace_mo: Decimal, target: Decimal):
    if pace_mo <= 0:
        return None
    return (target / pace_mo) * DAYS_PER_MO


def buy_only_r3(bars, start, end):
    midnight = midnight_index(bars)
    stop, tgt = Decimal("825.82"), Decimal("2477.46")
    pnls = []
    day = start
    while day <= end:
        i = midnight.get(day)
        if i is not None:
            # hard R=3 buy-only baseline (legacy gate compare)
            entry = bars[i].o
            sl, tp = entry - stop, entry + tgt
            for j in range(i, len(bars)):
                b = bars[j]
                hit_sl, hit_tp = b.l <= sl, b.h >= tp
                if not hit_sl and not hit_tp:
                    continue
                if hit_sl and hit_tp:
                    fill = sl
                elif hit_sl:
                    fill = sl if b.o > sl else b.o
                else:
                    fill = tp
                pnls.append(fill - entry)
                break
        day += timedelta(days=1)
    return sum(pnls, Decimal(0)), len(pnls)


def yn(b: bool) -> str:
    return "YES" if b else "NO"


def main():
    print("C10: Loading Dukas M1…")
    bars = merge_bars(parse_csv(DUKAS_MAIN), parse_csv(DUKAS_EXT))
    daily_closes = build_daily_closes(bars)
    daily_ohlc = build_daily_ohlc(bars)
    sma50 = sma_map(daily_closes, 50)
    atr_map = daily_tr_atr(daily_ohlc, 14)
    mids = midnight_index(bars)
    ext_end = max(d for d in mids if d >= EXT_START)
    print(f"bars={len(bars)} {utc_dt(bars[0].ts)} → {utc_dt(bars[-1].ts)} ext_end={ext_end.date()}")

    # --- Gate A: catalogue 0.01 with C5 filters ---
    print("C10 R-trail @0.01 fit/HO/ext (C5 filters)…")
    fit01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, FIT_START, FIT_END, name="c10-fit")
    ho01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, HO_START, HO_END, name="c10-ho")
    ext01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, EXT_START, ext_end, name="c10-ext")
    fit_s, ho_s, ext_s = map(summarize_01, (fit01.trades, ho01.trades, ext01.trades))
    top2, lo_s = leave_out_two_best(ho01.trades)
    buy_net, buy_n = buy_only_r3(bars, HO_START, HO_END)

    g1 = ho_s["all"]["net_full"] > 0 and ho_s["all"]["net_full"] > BUY_ONLY_HOLDOUT_NET and ho_s["all"]["net_full"] > buy_net
    g2 = ext_s["all"]["net_full"] >= 0
    g3 = lo_s["all"]["net_full"] > 0
    g4 = (
        ho_s["worst_raw"][1] >= WORST_DAY_BUDGET
        and ext_s["worst_raw"][1] >= WORST_DAY_BUDGET
        and ho_s["days_breach_raw"] == 0
        and ext_s["days_breach_raw"] == 0
    )
    g5 = fit_s["all"]["net_full"] >= FIT_SOFT_01
    g6 = ho_s["month_n"] >= 5 and ho_s["month_pos_rate"] >= Decimal("0.5")
    gates_a = all([g1, g2, g3, g4, g5, g6])

    ho_days = (HO_END.date() - HO_START.date()).days
    pace_01 = monthly_pace(ho_s["all"]["net_full"], ho_days)

    print(f"  HO net={float(ho_s['all']['net_full']):.2f} pace={float(pace_01):.2f}/mo WR={float(ho_s['all']['win_rate']):.1%}")
    print(f"  fit={float(fit_s['all']['net_full']):.2f} ext={float(ext_s['all']['net_full']):.2f} lo={float(lo_s['all']['net_full']):.2f} {top2}")
    print(f"  activated HO={ho_s['n_activated']}/{ho_s['all']['n']} reasons={ho_s['reasons']}")

    # --- Diagnostic: trail without C5 filters ---
    print("Diagnostic: R-trail no-filters @0.01 HO…")
    ho_nf = run_catalogue_01(
        bars, daily_closes, sma50, atr_map, HO_START, HO_END,
        use_filters=False, name="c10-ho-nofilt",
    )
    ho_nf_s = summarize_01(ho_nf.trades)
    print(f"  nofilt HO net={float(ho_nf_s['all']['net_full']):.2f} WR={float(ho_nf_s['all']['win_rate']):.1%} n={ho_nf_s['all']['n']}")

    # --- Gate B: equity 1% from HO_START ---
    print("C10 R-trail equity @ 1.0% risk from HO_START…")
    eq = run_equity(
        bars, daily_closes, sma50, atr_map, HO_START, ext_end,
        risk=RISK, name="c10-eq-1pct-ho",
    )
    trades_eq: list[TradeEq] = eq.trades
    day_pnl = eq.day_pnl  # type: ignore
    day_start_eq = eq.day_start_eq  # type: ignore
    max_dd = max_realized_dd(trades_eq)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail = sum(
        1 for d, pnl in day_pnl.items()
        if d in day_start_eq and day_start_eq[d] > 0 and pnl / day_start_eq[d] <= DAY_FAIL
    )
    worst_day_usd = min(day_pnl.values()) if day_pnl else Decimal(0)
    mean_stop = (
        sum(((t.lots / BASE_LOT) * t.stop_dist for t in trades_eq), Decimal(0))
        / Decimal(len(trades_eq))
        if trades_eq else Decimal(0)
    )

    def slice_eq(start_ts, end_ts):
        s = Decimal(0)
        for t in trades_eq:
            et = utc_dt(t.exit_ts)
            if et >= start_ts and (end_ts is None or et <= end_ts):
                s += t.pnl
        return s

    ho_eq = slice_eq(HO_START, datetime(2026, 9, 1, 23, 59, 59, tzinfo=timezone.utc))
    ext_eq = slice_eq(EXT_START, None)
    pace_eq = monthly_pace(ho_eq, ho_days)

    n_pass, n_win, sample_pass = count_60d_pass_windows(trades_eq, day_pnl, day_start_eq)
    g7 = n_pass >= 1
    g8 = pace_eq >= PACE_TARGET_MO or g7
    g9 = mean_stop <= Decimal("5000") and worst_day_usd >= Decimal("-5000") and max_dd <= MAX_DD_LIM
    g4b = n_fail == 0
    gates_b = all([g7, g8, g9, g4b]) if False else (g7 and g8 and g9)  # g4b informational under g7
    # Match C8: Gate B = g7, g8, g9 (g4b noted)
    gates_b = g7 and g8 and g9

    print(f"  eq HO pace={float(pace_eq):.2f}/mo final={float(eq.final_equity):.2f} DD={float(max_dd):.2%} 60d={n_pass}/{n_win}")

    # --- 0.5% risk path ---
    print("C10 R-trail equity @ 0.5% risk from HO_START…")
    eq05 = run_equity(
        bars, daily_closes, sma50, atr_map, HO_START, ext_end,
        risk=RISK_HALF, name="c10-eq-0.5pct-ho",
    )
    max_dd05 = max_realized_dd(eq05.trades)
    day_pnl05 = eq05.day_pnl  # type: ignore
    day_start_eq05 = eq05.day_start_eq  # type: ignore
    n_pass05, n_win05, _ = count_60d_pass_windows(eq05.trades, day_pnl05, day_start_eq05)
    ho_eq05 = sum(
        (t.pnl for t in eq05.trades
         if HO_START <= utc_dt(t.exit_ts) <= datetime(2026, 9, 1, 23, 59, 59, tzinfo=timezone.utc)),
        Decimal(0),
    )
    pace_eq05 = monthly_pace(ho_eq05, ho_days)
    print(f"  0.5% pace={float(pace_eq05):.2f}/mo DD={float(max_dd05):.2%} 60d={n_pass05}/{n_win05}")

    # Decision
    if gates_a and gates_b:
        verdict = "ACCEPT"
        binding = "none — clears Gate A + Gate B"
    elif gates_a and not gates_b:
        verdict = "CONDITIONAL"
        binding = "pace/DD (Gate B) — robust @0.01 but not ≤60d vehicle"
    else:
        verdict = "REJECT"
        fails = []
        if not g1:
            fails.append("HO")
        if not g2:
            fails.append("ext")
        if not g3:
            fails.append("leave-out")
        if not g4:
            fails.append("worst-day")
        if not g5:
            fails.append("fit")
        if not g6:
            fails.append("months")
        if not g7:
            fails.append("60d-windows")
        if not g8:
            fails.append("pace")
        if not g9:
            fails.append("DD/stop")
        # Primary binding for ≤60d vehicle
        if pace_eq <= 0 and not g7:
            binding = "EDGE (trail does not improve EV / pace vs hard R=1 enough for ≤60d)"
        elif not g9 and max_dd > MAX_DD_LIM:
            binding = "DD"
        elif not g7 and not g8:
            binding = "PACE (edge may exist @0.01 but $/mo too low for ≤60d at legal risk)"
        else:
            binding = "Gate A robustness (" + ", ".join(fails[:4]) + ")"

    sentence = (
        f"{verdict} C10 as ≤60d vehicle: HO@0.01 ${fmt(ho_s['all']['net_full'])} "
        f"(~${fmt(pace_01)}/mo); @1% risk pace ~${fmt(pace_eq)}/mo; "
        f"60d windows {n_pass}/{n_win}; max DD {pct(max_dd)}. Binding: {binding}."
    )
    print(sentence)

    # Avg R on winners that activated
    act_wins = [t for t in ho01.trades if t.reason != "open-eod" and t.activated and t.pnl_raw > 0]
    avg_win_r = (
        sum((t.pnl_raw / ONE_R for t in act_wins), Decimal(0)) / Decimal(len(act_wins))
        if act_wins else Decimal(0)
    )

    # Write results
    lines = []
    lines.append("# Candidate 10 Results — C5 Entry + R-Multiple Trail (1.0×R)")
    lines.append("")
    lines.append(f"**Decision: {verdict}**")
    lines.append("")
    lines.append(f"**One sentence:** {sentence}")
    lines.append("")
    lines.append(f"**Measured:** {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append("**Spec:** `/workspace/btc-strategies/ftmo-candidate-10.md`")
    lines.append("")
    lines.append("## Locked R-trail rule (a priori)")
    lines.append("")
    lines.append("| Step | Rule |")
    lines.append("|---|---|")
    lines.append("| Entry | C5: SMA50 exclusive dual + slope E + ATR < P75(100d); 00:00 UTC; max 1 |")
    lines.append("| Initial SL | entry ± 412.91 |")
    lines.append("| Activation | first +1R favorable touch → SL = entry (BE) |")
    lines.append("| Trail | after BE: **1.0×R (412.91)** behind favorable extreme (long: HH−412.91; short: LL+412.91); never widen. NOT ATR. |")
    lines.append("| Hard TP | emergency only at +5R (2064.55); not thesis payoff |")
    lines.append("| Cost | C4/C5 0.065%/side + swap est −30%/360 |")
    lines.append("")
    lines.append("## ASSUMPTIONS (labeled)")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Account | $100,000 2-step (ASSUMPTION) |")
    lines.append("| Challenge / Verification | +10% / +5% |")
    lines.append("| Pace bar | ≤60 calendar days both steps |")
    lines.append("| Daily / Max DD | 5% / 10% |")
    lines.append("| Trail distance | **1.0×R = 412.91** a priori (not tuned); R-multiple, not ATR |")
    lines.append("| Filters | C5 slope E + ATR < P75(100d) |")
    lines.append("| Risk Gate B | 1.0% equity / initial stop (also 0.5%) |")
    lines.append("| Daily kill | −3% realized Prague day |")
    lines.append("| Data | Merged Dukas M1 bid main+ext |")
    lines.append("")
    lines.append("## Gate A — robustness @ catalogue 0.01")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    lines.append(f"| 1 Holdout >0 & > buy-only | {yn(g1)} | HO ${fmt(ho_s['all']['net_full'])}; buy-only ${fmt(buy_net)} |")
    lines.append(f"| 2 Extension ≥ 0 | {yn(g2)} | Ext ${fmt(ext_s['all']['net_full'])} |")
    lines.append(f"| 3 Leave-out two best HO months > 0 | {yn(g3)} | removed {top2}; left ${fmt(lo_s['all']['net_full'])} |")
    lines.append(f"| 4 Worst ET day ≥ −$2k HO&ext | {yn(g4)} | HO {ho_s['worst_raw']}; ext {ext_s['worst_raw']} |")
    lines.append(f"| 5 Fit ≥ −$5k | {yn(g5)} | Fit ${fmt(fit_s['all']['net_full'])} |")
    lines.append(f"| 6 HO months ≥50% green | {yn(g6)} | {ho_s['month_pos']}/{ho_s['month_n']} ({pct(ho_s['month_pos_rate'])}) |")
    lines.append("")
    lines.append(f"**Gate A all pass?** {yn(gates_a)}")
    lines.append("")
    lines.append(f"- Trades HO L/S: {ho_s['long']['n']}/{ho_s['short']['n']}; WR {pct(ho_s['all']['win_rate'])}")
    lines.append(f"- Avg win / avg loss raw: ${fmt(ho_s['all']['avg_win'])} / ${fmt(ho_s['all']['avg_loss'])}")
    lines.append(f"- Avg max favorable R: {float(ho_s['all']['avg_max_r']):.2f}; activated {ho_s['n_activated']}/{ho_s['all']['n']}")
    lines.append(f"- Avg raw R on activated winners: {float(avg_win_r):.2f}R ({len(act_wins)} trades)")
    lines.append(f"- Exit reasons HO: {ho_s['reasons']}")
    lines.append(f"- Pace @0.01: **${fmt(pace_01)}/mo** over {ho_days} calendar days")
    lines.append(f"- Filter skips fit/HO: {fit01.skipped_filter}/{ho01.skipped_filter} (slope≈{fit01.skip_slope}/{ho01.skip_slope}, vol≈{fit01.skip_vol}/{ho01.skip_vol})")
    lines.append("")
    lines.append("### HO monthly P&L @0.01 (ET exit month)")
    lines.append("")
    lines.append("| ET exit month | Trades | Net full $ |")
    lines.append("|---|---:|---:|")
    for m, v in ho_s["months"].items():
        lines.append(f"| {m} | {v['n']} | {fmt(v['net_full'])} |")
    lines.append("")
    lines.append("## Gate B — ≤60-day vehicle @ 1.0% risk (R-trail)")
    lines.append("")
    lines.append("| Gate | Pass? | Detail |")
    lines.append("|---|---|---|")
    lines.append(f"| 7 ≥1 clean 60d window | {yn(g7)} | **{n_pass} / {n_win}** windows |")
    lines.append(f"| 8 Pace ≥$7.5k/mo OR Gate 7 | {yn(g8)} | HO pace ${fmt(pace_eq)}/mo |")
    lines.append(f"| 9 Stop+worst day ≤$5k; DD≤10% | {yn(g9)} | mean stop ${fmt(mean_stop)}; worst day ${fmt(worst_day_usd)}; DD {pct(max_dd)} |")
    lines.append(f"| 4b No −5% Prague days | {yn(g4b)} | worst {worst_d} {pct(worst_pct)}; fail-days={n_fail} |")
    lines.append("")
    lines.append(f"**Gate B all pass?** {yn(gates_b)}")
    lines.append("")
    lines.append(f"- Equity trades: {len(trades_eq)} (L/S {sum(1 for t in trades_eq if t.side=='long')}/{sum(1 for t in trades_eq if t.side=='short')})")
    lines.append(f"- Wins/losses: {sum(1 for t in trades_eq if t.pnl>0)}/{sum(1 for t in trades_eq if t.pnl<0)}")
    lines.append(f"- Final equity: ${fmt(eq.final_equity)} (net ${fmt(eq.final_equity - START_EQUITY)})")
    lines.append(f"- HO/Ext equity nets: ${fmt(ho_eq)} / ${fmt(ext_eq)}")
    lines.append(f"- Killed Prague days: {len(eq.killed_days)}")  # type: ignore
    lines.append("")
    lines.append("### 60-day pass windows (sample)")
    lines.append("")
    if sample_pass:
        lines.append("| start | end | start_eq | max_mult | min_mult | worst_day |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for p in sample_pass[:10]:
            lines.append(
                f"| {p['start']} | {p['end']} | {p['start_eq']:.0f} | {p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']:.2%} |"
            )
    else:
        lines.append("_None._")
    lines.append("")
    lines.append("### 0.5% risk path")
    lines.append("")
    lines.append(f"- HO pace ${fmt(pace_eq05)}/mo; max DD {pct(max_dd05)}; 60d passes **{n_pass05}/{n_win05}**; final ${fmt(eq05.final_equity)}")
    lines.append("")
    lines.append("## Diagnostic — R-trail without C5 filters (not a new candidate)")
    lines.append("")
    lines.append(f"- Catalogue 0.01 HO: ${fmt(ho_nf_s['all']['net_full'])} (~${fmt(monthly_pace(ho_nf_s['all']['net_full'], ho_days))}/mo); WR {pct(ho_nf_s['all']['win_rate'])}; n={ho_nf_s['all']['n']}; activated {ho_nf_s['n_activated']}")
    lines.append(f"- Reasons: {ho_nf_s['reasons']}")
    lines.append("")
    lines.append("## Comparison vs C5 / C9")
    lines.append("")
    lines.append("| | C5 @0.01 R=1 | C9 @0.01 ATR-trail | C10 @0.01 R-trail | C10 @1% R-trail |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(f"| HO $/mo | ~491 | ~660 | **{fmt(pace_01)}** | **{fmt(pace_eq)}** |")
    lines.append(f"| HO net | +$4,790 | +$6,444 | **${fmt(ho_s['all']['net_full'])}** | ${fmt(ho_eq)} |")
    lines.append(f"| HO WR | 53.5% | 11.6% | **{pct(ho_s['all']['win_rate'])}** | — |")
    lines.append(f"| Fit @0.01 | −$3,214 | −$830 | **${fmt(fit_s['all']['net_full'])}** | — |")
    lines.append(f"| Leave-out | +$707 | +$286 | **${fmt(lo_s['all']['net_full'])}** | — |")
    lines.append(f"| ≤60d @1% | n/a (slow) | 65/252 (DD 18.5%) | n/a | **{n_pass}/{n_win}** |")
    lines.append(f"| Max DD | low @0.01 | 18.5%@1% | low @0.01 | **{pct(max_dd)}** |")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"**{verdict}** — C10 is research-only. Not deployable live from this folder.")
    lines.append("")
    lines.append("### Binding constraint")
    lines.append("")
    lines.append(f"**{binding}**")
    lines.append("")
    d_to_15k = days_to_target(pace_eq, Decimal("15000"))
    if d_to_15k is not None:
        lines.append(f"- Est. calendar days to +$15k @1% pace: **{float(d_to_15k):.0f}** (bar ≤60).")
    else:
        lines.append("- Est. calendar days to +$15k @1% pace: **∞** (non-positive pace).")
    lines.append("")
    lines.append("## Live")
    lines.append("")
    lines.append("Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.")
    lines.append("")
    lines.append("## Research-next?")
    lines.append("")
    if verdict == "ACCEPT":
        lines.append("**NO for new thesis** — C10 clears ≤60d bar; next is Ops review / paper proof, not more fishing.")
    elif verdict == "CONDITIONAL":
        lines.append(
            "**YES — recommend different entry chassis as C11.** "
            "R-trail on SMA50 dual still DD-bound or too slow for ≤60d at legal risk. "
            "Do **not** keep milking SMA50 dual exits (no more trail k / BE variants). "
            "Do not re-run hard R=2/R=3."
        )
    else:
        n_trail = ho_s["reasons"].get("trail-stop", 0)
        if n_trail == 0:
            lines.append(
                "**YES — recommend different entry chassis as C11.** "
                "R-trail still never engaged usefully (0 trail-stop exits) OR edge destroyed. "
                "Do **not** keep milking SMA50 dual exits. Try a different entry "
                "(higher frequency / stronger edge at DD-legal risk). Do not re-run hard R=2/R=3."
            )
        else:
            lines.append(
                "**YES — recommend different entry chassis as C11.** "
                "R-trail engaged but still not a ≤60d vehicle (binding: see above). "
                "SMA50 dual exit milking is exhausted (C8 hard R, C9 ATR trail, C10 R-trail). "
                "Next: **different entry chassis**. Do not re-run hard R=2/R=3."
            )
    lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
