#!/usr/bin/env python3
"""Candidate 8: C5 filters + catalogue stop 412.91 + R=2 (diag R=3).

Research only. No live VM / MetaAPI / C4 / drip / FREEZE touches.
Cost model: C4/C5 commission 0.065% + swap est (NOT FTMO spread=15).
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

OUT = Path("/workspace/btc-strategies/candidate-8-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-8.md")

STOP = Decimal("412.91")
TARGET_R2 = Decimal("825.82")   # R=2 primary
TARGET_R3 = Decimal("1238.73")  # R=3 diagnostic
START_EQUITY = Decimal("100000")
RISK = Decimal("0.01")          # 1.0% primary
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
    """Catalogue 0.01 path trade."""
    side: str
    entry_ts: int
    entry: Decimal
    exit_ts: int
    exit: Decimal
    reason: str
    pnl_raw: Decimal
    commission: Decimal
    swap: Decimal

    @property
    def pnl_full(self) -> Decimal:
        return self.pnl_raw - self.commission - self.swap


@dataclass
class TradeEq:
    """Equity-sized path trade."""
    side: str
    entry_ts: int
    entry: Decimal
    exit_ts: int
    exit: Decimal
    reason: str
    lots: Decimal
    stop_dist: Decimal
    pnl: Decimal  # after costs
    equity_after: Decimal
    prague_exit: date


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


def scan_exit(bars, start_i, side, entry, stop=STOP, target=TARGET_R2):
    if side == "long":
        sl, tp = entry - stop, entry + target
    else:
        sl, tp = entry + stop, entry - target
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


def filters_ok(
    side, prior, days_sorted, day_index, sma50, atr_map
) -> tuple[bool, str]:
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


def run_catalogue_01(
    bars, daily_closes, sma50, atr_map, start, end, *, target=TARGET_R2, name="c8-01"
):
    """Fixed 0.01 catalogue dollars (C5-comparable Gate A)."""
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
        j, fill, reason = scan_exit(bars, i, side, entry_px, STOP, target)
        if reason == "open-eod":
            pnl = comm = sw = Decimal(0)
            free_after = bars[-1].ts + 1
        else:
            pnl = raw_pnl(side, entry_px, fill)
            comm = commission_scaled(entry_px, fill, BASE_LOT)
            sw = swap_scaled(entry_px, entry_ts, bars[j].ts, BASE_LOT)
            free_after = bars[j].ts + 1
        res.trades.append(
            Trade01(side, entry_ts, entry_px, bars[j].ts, fill, reason, pnl, comm, sw)
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
    target=TARGET_R2,
    risk=RISK,
    name="c8-eq",
    daily_kill=True,
):
    """Fractional risk equity path for Gate B / 60d windows."""
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
        # mark prague day start equity once
        # Use UTC midnight as proxy for "session start" — day_start when we first see the Prague day
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

        # Halt new risk once past static 10% floor or insolvent (FTMO max-loss)
        if equity <= START_EQUITY * FLOOR_MULT or equity <= Decimal("0"):
            res.skipped_lots += 1
            day += timedelta(days=1)
            continue

        # Catalogue convention: 0.01 lot → $1 per $1 price move.
        # scale = risk_dollars/STOP is the multiplier on that 0.01 book
        # (NOT lots=risk/STOP, which double-counts when scaled by /0.01).
        risk_dollars = equity * risk
        scale = risk_dollars / STOP
        lots = round_lots(BASE_LOT * scale)
        if lots < MIN_LOT or scale <= 0:
            res.skipped_lots += 1
            day += timedelta(days=1)
            continue
        # Recompute scale from rounded lots so stop $ matches booked size
        scale = lots / BASE_LOT

        entry_px = bars[i].o
        j, fill, reason = scan_exit(bars, i, side, entry_px, STOP, target)
        if reason == "open-eod":
            free_after = bars[-1].ts + 1
            # no pnl booked
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
            day_start_eq[pd_exit] = equity - pnl  # approx start before this trade
        day_pnl[pd_exit] += pnl
        if daily_kill and day_start_eq[pd_exit] > 0:
            if day_pnl[pd_exit] / day_start_eq[pd_exit] <= DAILY_KILL:
                killed_days.add(pd_exit)

        free_after = bars[j].ts + 1
        res.trades.append(
            TradeEq(
                side,
                entry_ts,
                entry_px,
                bars[j].ts,
                fill,
                reason,
                lots,
                STOP,
                pnl,
                equity,
                pd_exit,
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
                "n": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": Decimal(0),
                "net_raw": Decimal(0),
                "net_full": Decimal(0),
            }
        wins = sum(1 for t in ts if t.pnl_raw > 0)
        return {
            "n": len(ts),
            "wins": wins,
            "losses": sum(1 for t in ts if t.pnl_raw < 0),
            "win_rate": Decimal(wins) / Decimal(len(ts)),
            "net_raw": sum((t.pnl_raw for t in ts), Decimal(0)),
            "net_full": sum((t.pnl_full for t in ts), Decimal(0)),
        }

    daily_raw = defaultdict(lambda: Decimal(0))
    month_full = defaultdict(lambda: Decimal(0))
    month_n = defaultdict(int)
    for t in closed:
        daily_raw[et_day(t.exit_ts)] += t.pnl_raw
        m = ym_et(t.exit_ts)
        month_full[m] += t.pnl_full
        month_n[m] += 1
    worst = (
        min(daily_raw.items(), key=lambda kv: (kv[1], kv[0]))
        if daily_raw
        else ("none", Decimal(0))
    )
    months = {m: {"n": month_n[m], "net_full": month_full[m]} for m in sorted(month_full)}
    pos_m = sum(1 for v in months.values() if v["net_full"] >= 0)
    n_m = len(months)
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
    exits = [(t.prague_exit, t.equity_after, utc_dt(t.exit_ts)) for t in trades]
    # sort by exit time
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
    eq = START_EQUITY
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
            j, fill, reason = scan_exit(bars, i, "long", bars[i].o, stop, tgt)
            if reason != "open-eod":
                pnls.append(raw_pnl("long", bars[i].o, fill))
        day += timedelta(days=1)
    return sum(pnls, Decimal(0)), len(pnls)


def yn(b: bool) -> str:
    return "YES" if b else "NO"


def main():
    print("Loading Dukas M1…")
    bars = merge_bars(parse_csv(DUKAS_MAIN), parse_csv(DUKAS_EXT))
    daily_closes = build_daily_closes(bars)
    daily_ohlc = build_daily_ohlc(bars)
    sma50 = sma_map(daily_closes, 50)
    atr_map = daily_tr_atr(daily_ohlc, 14)
    mids = midnight_index(bars)
    ext_end = max(d for d in mids if d >= EXT_START)
    print(f"bars={len(bars)} {utc_dt(bars[0].ts)} → {utc_dt(bars[-1].ts)} ext_end={ext_end.date()}")

    # --- Catalogue 0.01 Gate A (R=2 primary) ---
    print("C8 R=2 catalogue 0.01 fit/HO/ext…")
    fit01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, FIT_START, FIT_END, target=TARGET_R2, name="r2-fit")
    ho01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, HO_START, HO_END, target=TARGET_R2, name="r2-ho")
    ext01 = run_catalogue_01(bars, daily_closes, sma50, atr_map, EXT_START, ext_end, target=TARGET_R2, name="r2-ext")
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

    # --- Equity 1% risk Gate B (R=2) ---
    # Fresh $100k from HO_START (Challenge-relevant). Fit@0.01 already Gate A.
    print("C8 R=2 equity @ 1.0% risk from HO_START (fresh $100k)…")
    eq = run_equity(
        bars, daily_closes, sma50, atr_map, HO_START, ext_end,
        target=TARGET_R2, risk=RISK, name="r2-eq-1pct-ho",
    )
    trades_eq: list[TradeEq] = eq.trades
    day_pnl = eq.day_pnl  # type: ignore
    day_start_eq = eq.day_start_eq  # type: ignore
    max_dd = max_realized_dd(trades_eq)
    worst_d, worst_pct = worst_day_pct(day_pnl, day_start_eq)
    n_fail = sum(
        1
        for d, pnl in day_pnl.items()
        if d in day_start_eq and day_start_eq[d] > 0 and pnl / day_start_eq[d] <= DAY_FAIL
    )
    worst_day_usd = min(day_pnl.values()) if day_pnl else Decimal(0)
    # Planned stop $ under catalogue convention = (lots/0.01) * STOP
    mean_stop = (
        sum(((t.lots / BASE_LOT) * t.stop_dist for t in trades_eq), Decimal(0))
        / Decimal(len(trades_eq))
        if trades_eq
        else Decimal(0)
    )

    # HO / ext / fit nets on equity path
    def slice_eq(start_ts, end_ts):
        s = Decimal(0)
        for t in trades_eq:
            et = utc_dt(t.exit_ts)
            if et >= start_ts and (end_ts is None or et <= end_ts):
                s += t.pnl
        return s

    ho_eq = slice_eq(HO_START, datetime(2026, 9, 1, 23, 59, 59, tzinfo=timezone.utc))
    ext_eq = slice_eq(EXT_START, None)
    fit_eq = slice_eq(FIT_START, FIT_END)
    pace_eq = monthly_pace(ho_eq, ho_days)

    n_pass, n_win, pass_sample = count_60d_pass_windows(trades_eq, day_pnl, day_start_eq)

    g7 = n_pass >= 1
    g8 = pace_eq >= PACE_TARGET_MO or g7
    g9 = mean_stop <= Decimal("5000") and abs(worst_day_usd) <= Decimal("5000") and max_dd <= MAX_DD_LIM
    # Also require no -5% days on equity path
    g4b = n_fail == 0 and (worst_pct > DAY_FAIL if worst_d else True)
    gates_b = all([g7, g8, g9, g4b])

    if gates_a and gates_b:
        decision = "ACCEPT"
    elif gates_a and not gates_b:
        decision = "CONDITIONAL"
    else:
        decision = "REJECT"

    # Risk scale table (linear from 1% run for pace/day; re-run DD% is ~scale-invariant for fractional)
    scale_rows = []
    for rp in [Decimal("0.005"), Decimal("0.0075"), Decimal("0.01"), Decimal("0.0125"), Decimal("0.015")]:
        sc = rp / RISK
        pace = pace_eq * sc
        wd = worst_day_usd * sc
        stop_u = mean_stop * sc
        d_both = days_to_target(pace, Decimal("15000"))
        daily_ok = abs(wd) <= Decimal("5000") and stop_u <= Decimal("5000")
        scale_rows.append((rp, pace, wd, stop_u, d_both, daily_ok))

    # Diagnostic R=3 catalogue + equity @ 1%
    print("Diagnostic R=3 catalogue 0.01…")
    fit3 = run_catalogue_01(bars, daily_closes, sma50, atr_map, FIT_START, FIT_END, target=TARGET_R3, name="r3-fit")
    ho3 = run_catalogue_01(bars, daily_closes, sma50, atr_map, HO_START, HO_END, target=TARGET_R3, name="r3-ho")
    ext3 = run_catalogue_01(bars, daily_closes, sma50, atr_map, EXT_START, ext_end, target=TARGET_R3, name="r3-ext")
    fit3_s, ho3_s, ext3_s = map(summarize_01, (fit3.trades, ho3.trades, ext3.trades))
    top2_3, lo3_s = leave_out_two_best(ho3.trades)
    pace3_01 = monthly_pace(ho3_s["all"]["net_full"], ho_days)

    print("Diagnostic R=3 equity @ 1.0% from HO_START…")
    eq3 = run_equity(
        bars, daily_closes, sma50, atr_map, HO_START, ext_end,
        target=TARGET_R3, risk=RISK, name="r3-eq-1pct-ho",
    )
    ho3_eq = sum(
        (
            t.pnl
            for t in eq3.trades
            if HO_START <= utc_dt(t.exit_ts) <= datetime(2026, 9, 1, 23, 59, 59, tzinfo=timezone.utc)
        ),
        Decimal(0),
    )
    pace3_eq = monthly_pace(ho3_eq, ho_days)
    max_dd3 = max_realized_dd(eq3.trades)
    n_pass3, n_win3, pass3 = count_60d_pass_windows(eq3.trades, eq3.day_pnl, eq3.day_start_eq)  # type: ignore
    worst3_d, worst3_pct = worst_day_pct(eq3.day_pnl, eq3.day_start_eq)  # type: ignore

    wins = sum(1 for t in trades_eq if t.pnl > 0)
    losses = sum(1 for t in trades_eq if t.pnl <= 0)
    longs = sum(1 for t in trades_eq if t.side == "long")
    shorts = sum(1 for t in trades_eq if t.side == "short")

    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    one = (
        f"{decision} C8 as ≤60d vehicle: HO@0.01 ${float(ho_s['all']['net_full']):,.2f} "
        f"(~${float(pace_01):,.0f}/mo); @1% risk pace ~${float(pace_eq):,.0f}/mo; "
        f"60d windows {n_pass}/{n_win}; max DD {float(max_dd)*100:.2f}%."
    )

    print(one)
    print(f"Gate A={gates_a} Gate B={gates_b}")
    print(f"HO01={float(ho_s['all']['net_full']):.2f} leave={top2}->{float(lo_s['all']['net_full']):.2f}")
    print(f"ext01={float(ext_s['all']['net_full']):.2f} fit01={float(fit_s['all']['net_full']):.2f}")
    print(f"eq HO pace={float(pace_eq):.2f} pass={n_pass}/{n_win} dd={float(max_dd)*100:.2f}% worst_day={worst_d} {float(worst_pct)*100:.2f}%")

    md = []
    md.append("# Candidate 8 Results — Filtered SMA50 Dual R=2 (catalogue stop)")
    md.append("")
    md.append(f"**Decision: {decision}**")
    md.append("")
    md.append(f"**One sentence:** {one}")
    md.append("")
    md.append(f"**Measured:** {now}")
    md.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    md.append(f"**Spec:** `{SPEC}`")
    md.append("")
    md.append("## ASSUMPTIONS (labeled)")
    md.append("")
    md.append("| Item | Value |")
    md.append("|---|---|")
    md.append("| Account | $100,000 2-step (ASSUMPTION) |")
    md.append("| Challenge / Verification | +10% / +5% |")
    md.append("| Pace bar | ≤60 calendar days both steps |")
    md.append("| Daily / Max DD | 5% / 10% |")
    md.append("| Primary stop / target | 412.91 / 825.82 (R=2) |")
    md.append("| Filters | C5 slope E + ATR < P75(100d) |")
    md.append("| Risk per trade (Gate B) | 1.0% equity / stop |")
    md.append("| Daily kill | −3% realized Prague day |")
    md.append("| Cost model | C4/C5: 0.065%/side + swap est −30%/360 |")
    md.append("| Data | Merged Dukas M1 bid main+ext |")
    md.append("")
    md.append("## vs C1 (a priori difference)")
    md.append("")
    md.append("| | C1 | C8 primary |")
    md.append("|---|---|---|")
    md.append("| Stop | 825.82 | **412.91** |")
    md.append("| Target / R | 2477.46 / R=3 | **825.82 / R=2** |")
    md.append("| Filters | none | **slope + V75** |")
    md.append("")
    md.append("## Gate A — robustness @ catalogue 0.01 (R=2)")
    md.append("")
    md.append("| Gate | Pass? | Detail |")
    md.append("|---|---|---|")
    md.append(f"| 1 Holdout >0 & > buy-only | {yn(g1)} | HO ${float(ho_s['all']['net_full']):,.2f}; buy-only ${float(buy_net):,.2f} |")
    md.append(f"| 2 Extension ≥ 0 | {yn(g2)} | Ext ${float(ext_s['all']['net_full']):,.2f} |")
    md.append(f"| 3 Leave-out two best HO months > 0 | {yn(g3)} | removed {top2}; left ${float(lo_s['all']['net_full']):,.2f} |")
    md.append(f"| 4 Worst ET day ≥ −$2k HO&ext | {yn(g4)} | HO {ho_s['worst_raw']}; ext {ext_s['worst_raw']} |")
    md.append(f"| 5 Fit ≥ −$5k | {yn(g5)} | Fit ${float(fit_s['all']['net_full']):,.2f} |")
    md.append(f"| 6 HO months ≥50% green | {yn(g6)} | {ho_s['month_pos']}/{ho_s['month_n']} ({pct(ho_s['month_pos_rate'])}) |")
    md.append("")
    md.append(f"**Gate A all pass?** {yn(gates_a)}")
    md.append("")
    md.append(f"- Trades HO L/S: {ho_s['long']['n']}/{ho_s['short']['n']}; WR {pct(ho_s['all']['win_rate'])}")
    md.append(f"- Pace @0.01: **${float(pace_01):,.2f}/mo** over {ho_days} calendar days")
    md.append(f"- Filter skips fit/HO: {fit01.skipped_filter}/{ho01.skipped_filter} (slope≈{fit01.skip_slope}/{ho01.skip_slope}, vol≈{fit01.skip_vol}/{ho01.skip_vol})")
    md.append("")
    md.append("### HO monthly P&L @0.01 (ET exit month)")
    md.append("")
    md.append("| ET exit month | Trades | Net full $ |")
    md.append("|---|---:|---:|")
    for m, v in ho_s["months"].items():
        md.append(f"| {m} | {v['n']} | {float(v['net_full']):,.2f} |")
    md.append("")
    md.append("## Gate B — ≤60-day vehicle @ 1.0% risk (R=2)")
    md.append("")
    md.append("| Gate | Pass? | Detail |")
    md.append("|---|---|---|")
    md.append(f"| 7 ≥1 clean 60d window | {yn(g7)} | **{n_pass} / {n_win}** windows |")
    md.append(f"| 8 Pace ≥$7.5k/mo OR Gate 7 | {yn(g8)} | HO pace ${float(pace_eq):,.2f}/mo |")
    md.append(f"| 9 Stop+worst day ≤$5k; DD≤10% | {yn(g9)} | mean stop ${float(mean_stop):,.2f}; worst day ${float(worst_day_usd):,.2f}; DD {float(max_dd)*100:.2f}% |")
    md.append(f"| 4b No −5% Prague days | {yn(g4b)} | worst {worst_d} {float(worst_pct)*100:.2f}%; fail-days={n_fail} |")
    md.append("")
    md.append(f"**Gate B all pass?** {yn(gates_b)}")
    md.append("")
    md.append(f"- Equity trades: {len(trades_eq)} (L/S {longs}/{shorts}); wins/losses {wins}/{losses}")
    md.append(f"- Final equity: ${float(eq.final_equity):,.2f} (net ${float(eq.final_equity - START_EQUITY):,.2f})")  # type: ignore
    md.append(f"- Fit/HO/Ext equity nets: ${float(fit_eq):,.2f} / ${float(ho_eq):,.2f} / ${float(ext_eq):,.2f}")
    md.append(f"- Killed Prague days: {len(eq.killed_days)}")  # type: ignore
    md.append("")
    md.append("### 60-day pass windows (sample)")
    md.append("")
    if pass_sample:
        md.append("| Start | End | Start eq | Max mult | Min mult | Worst day |")
        md.append("|---|---|---:|---:|---:|---:|")
        for p in pass_sample:
            md.append(
                f"| {p['start']} | {p['end']} | ${p['start_eq']:,.0f} | {p['max_mult']:.3f} | {p['min_mult']:.3f} | {p['worst_day']*100:.2f}% |"
            )
    else:
        md.append("_None._")
    md.append("")
    md.append("### Risk scale table (linear $ from 1.0% base; DD% ~scale-invariant for fractional risk)")
    md.append("")
    md.append("| Risk% | HO $/mo | Worst day $ | Mean stop $ | Est days both +$15k | Daily $ OK |")
    md.append("|---:|---:|---:|---:|---:|:---:|")
    for rp, pace, wd, stop_u, d_both, daily_ok in scale_rows:
        dbs = f"{float(d_both):.1f}" if d_both is not None else "inf"
        md.append(
            f"| {float(rp)*100:.2f} | {float(pace):,.2f} | {float(wd):,.2f} | {float(stop_u):,.2f} | {dbs} | {'Y' if daily_ok else 'N'} |"
        )
    md.append("")
    md.append("## Diagnostic — R=3 (same filters/stop; not a new candidate)")
    md.append("")
    md.append(f"- Catalogue 0.01: fit ${float(fit3_s['all']['net_full']):,.2f}; HO ${float(ho3_s['all']['net_full']):,.2f} (~${float(pace3_01):,.0f}/mo); ext ${float(ext3_s['all']['net_full']):,.2f}")
    md.append(f"- Leave-out removed {top2_3} → ${float(lo3_s['all']['net_full']):,.2f}")
    md.append(f"- HO WR {pct(ho3_s['all']['win_rate'])}; trades {ho3_s['all']['n']}")
    md.append(f"- Equity @1%: HO pace ~${float(pace3_eq):,.2f}/mo; max DD {float(max_dd3)*100:.2f}%; 60d passes **{n_pass3}/{n_win3}**; worst day {worst3_d} {float(worst3_pct)*100:.2f}%")
    md.append("")
    md.append("## Comparison vs C5 / C7")
    md.append("")
    md.append("| | C5 @0.01 R=1 | C7 @0.75% R=1 | C8 @0.01 R=2 | C8 @1% R=2 |")
    md.append("|---|---:|---:|---:|---:|")
    md.append(f"| HO $/mo | ~491 | ~508 | {float(pace_01):,.0f} | {float(pace_eq):,.0f} |")
    md.append(f"| ≤60d windows | n/a (slow) | 0/896 | n/a | **{n_pass}/{n_win}** |")
    md.append(f"| Max DD | low @0.01 | 17.39% | low @0.01 | {float(max_dd)*100:.2f}% |")
    md.append(f"| Leave-out @0.01 | +$707 | fail | ${float(lo_s['all']['net_full']):,.0f} | — |")
    md.append("")
    md.append("## Decision")
    md.append("")
    md.append(f"**{decision}** — C8 is research-only. Not deployable live from this folder.")
    md.append("")
    # Binding constraint narrative filled from measured flags
    if decision == "ACCEPT":
        md.append("### Why ACCEPT")
        md.append("")
        md.append("- Clears Gate A robustness and Gate B ≤60d windows at 1% risk with DD bars intact.")
        md.append("- Higher R (vs C5/C7 R=1) delivers the missing dollar pace without illegal size.")
    elif decision == "CONDITIONAL":
        md.append("### Why CONDITIONAL")
        md.append("")
        md.append("- Gate A (robustness @0.01) passes — filtered R=2 keeps leave-out/fit alive.")
        md.append("- Gate B (≤60d) fails — binding constraint documented below.")
    else:
        md.append("### Binding constraint")
        md.append("")
        reasons = []
        if not gates_a:
            reasons.append("**Edge/robustness (Gate A)** — filtered R=2 fails one or more of fit/HO/leave-out/months/worst-day at catalogue size.")
        if not gates_b:
            if not g7 and not (pace_eq >= PACE_TARGET_MO):
                reasons.append("**Pace** — HO $/mo at DD-legal 1% risk still below ~$7.5k and **0** clean ≤60d windows.")
            if max_dd > MAX_DD_LIM:
                reasons.append(f"**Max DD** — realized {float(max_dd)*100:.2f}% > 10%.")
            if not g4b:
                reasons.append("**Daily DD** — one or more Prague days ≤ −5%.")
            if mean_stop > Decimal("5000") or abs(worst_day_usd) > Decimal("5000"):
                reasons.append("**Per-trade / worst-day dollars** exceed $5k at chosen risk.")
        if not reasons:
            reasons.append("See gate tables.")
        for r in reasons:
            md.append(f"- {r}")
        md.append("")
        if not gates_a and not gates_b:
            md.append("**Binding: both edge and DD/pace.**")
        elif not gates_a:
            md.append("**Binding: edge (robustness), not only DD.**")
        else:
            md.append("**Binding: DD and/or pace (not edge absence at 0.01).**")
    md.append("")
    md.append("## Live")
    md.append("")
    md.append("Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.")
    md.append("")
    md.append("## Research-next?")
    md.append("")
    if decision == "ACCEPT":
        md.append("**YES** — paper/min-size path beside C4 only with explicit Odin approval (not from this folder).")
    elif decision == "CONDITIONAL":
        md.append("**YES (narrow)** — only if a different structure raises R-realized without killing leave-out; do not scale C8 past DD-legal size.")
    else:
        md.append("**YES** — next thesis should change **edge structure** (trail/runner or different setup), not re-scale R=1/R=2 SMA50 dual again without a new a priori fix.")

    OUT.write_text("\n".join(md) + "\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
