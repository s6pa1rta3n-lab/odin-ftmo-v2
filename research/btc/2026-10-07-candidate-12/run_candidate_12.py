#!/usr/bin/env python3
"""Candidate 12: Multi-position stack on known-positive C5 edge, capped aggregate risk.

Research only. No live VM / MetaAPI / C4 / drip / FREEZE touches.
Do NOT use C11 losers. Do NOT hard R=2/R=3.

Thesis (locked a priori):
  - Signal/filters = C5: SMA50 exclusive dual by prior UTC daily close,
    slope E, ATR < P75(100d), entry 00:00 UTC M1 open when signal fires
  - Per ticket: stop=target=412.91 (R=1)
  - Up to N=3 concurrent positions in SAME regime direction (never hedged)
  - Per-ticket risk: 0.5% equity (config B) or flat 0.01 lots (config A)
  - Aggregate open risk cap: sum remaining stop $ ≤ 2.0% equity
  - Prague-day kill: no new if realized day PnL ≤ −3%; flatten all if ≤ −4%
  - Cost model: C4/C5 0.065% + swap
  - Same Dukas data as C5
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
    STOP,
    TARGET,
    scan_exit,
    raw_pnl,
    daily_tr_atr,
    build_daily_ohlc,
    percentile,
    SLOPE_LOOKBACK,
    ATR_WINDOW,
    ATR_PCTILE,
)
from run_candidate_10 import (
    filters_ok,
    commission_scaled,
    swap_scaled,
    prague_day_ms,
    round_lots,
    count_60d_pass_windows,
    max_realized_dd,
    worst_day_pct,
    monthly_pace,
    days_to_target,
    yn,
)

ET = ZoneInfo("America/New_York")
PRAGUE = ZoneInfo("Europe/Prague")

OUT = Path("/workspace/btc-strategies/candidate-12-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-12.md")

START_EQUITY = Decimal("100000")
BASE_LOT = Decimal("0.01")
MIN_LOT = Decimal("0.01")
MAX_N = 3  # locked a priori
RISK_TICKET = Decimal("0.005")  # 0.5% per ticket (B/C)
AGG_CAP = Decimal("0.02")  # 2.0% aggregate open risk
DAILY_KILL = Decimal("-0.03")  # no new entries
DAILY_FLATTEN = Decimal("-0.04")  # flatten all open
WINDOW_DAYS = 60
CHALLENGE_MULT = Decimal("1.10")
BOTH_MULT = Decimal("1.155")
FLOOR_MULT = Decimal("0.90")
DAY_FAIL = Decimal("-0.05")
MAX_DD_LIM = Decimal("0.10")
PACE_TARGET_MO = Decimal("7500")
DAYS_PER_MO = Decimal("30.44")
FIT_SOFT_01 = Decimal("-5000")


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
    n_open_at_entry: int = 1
    risk_dollars: Decimal = Decimal(0)


@dataclass
class OpenPos:
    side: str
    entry_ts: int
    entry: Decimal
    lots: Decimal
    risk_dollars: Decimal
    exit_j: int
    exit_px: Decimal
    exit_reason: str
    exit_ts: int
    n_open_at_entry: int


@dataclass
class Meta:
    name: str
    trades: list = field(default_factory=list)
    regime_long: int = 0
    regime_short: int = 0
    regime_flat: int = 0
    regime_unknown: int = 0
    skipped_no_bar: int = 0
    skipped_in_trade: int = 0  # opposite side while open, or N full without using this
    skipped_filter: int = 0
    skip_slope: int = 0
    skip_vol: int = 0
    skipped_kill: int = 0
    skipped_agg: int = 0
    skipped_n_full: int = 0
    skipped_lots: int = 0
    skipped_side_mismatch: int = 0
    n_flatten: int = 0
    entry_ops: int = 0
    max_concurrent: int = 0
    n_entries: int = 0


def dollar_risk(lots: Decimal) -> Decimal:
    """Catalogue: 0.01 lots → $STOP risk."""
    return STOP * (lots / BASE_LOT)


def realize_opens(
    opens: list[OpenPos],
    now_ts: int,
    equity: Decimal,
    day_pnl: dict,
    day_start_eq: dict,
    killed_days: set,
    flatten_days: set,
    closed: list[TradeEq],
    peak: Decimal,
    max_dd: Decimal,
    *,
    force_flat_at: tuple[int, Decimal, str] | None = None,
) -> tuple[list[OpenPos], Decimal, Decimal, Decimal]:
    """Realize opens with exit_ts <= now_ts. Optional force-flat remaining at (ts, px, reason)."""
    due = [p for p in opens if p.exit_ts <= now_ts]
    still = [p for p in opens if p.exit_ts > now_ts]
    due.sort(key=lambda p: (p.exit_ts, p.entry_ts))

    for p in due:
        price_pnl = raw_pnl(p.side, p.entry, p.exit_px)
        scale = p.lots / BASE_LOT
        raw_d = price_pnl * scale
        comm = commission_scaled(p.entry, p.exit_px, p.lots)
        sw = swap_scaled(p.entry, p.entry_ts, p.exit_ts, p.lots)
        pnl = raw_d - comm - sw
        equity = equity + pnl
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        pd = prague_day_ms(p.exit_ts)
        if pd not in day_start_eq:
            day_start_eq[pd] = equity - pnl
        day_pnl[pd] += pnl
        if day_start_eq[pd] > 0:
            ratio = day_pnl[pd] / day_start_eq[pd]
            if ratio <= DAILY_KILL:
                killed_days.add(pd)
            if ratio <= DAILY_FLATTEN:
                flatten_days.add(pd)
        closed.append(
            TradeEq(
                p.side, p.entry_ts, p.entry, p.exit_ts, p.exit_px, p.exit_reason,
                p.lots, STOP, pnl, equity, pd, p.n_open_at_entry, p.risk_dollars,
            )
        )

    if force_flat_at is not None and still:
        fts, fpx, freason = force_flat_at
        for p in still:
            price_pnl = raw_pnl(p.side, p.entry, fpx)
            scale = p.lots / BASE_LOT
            raw_d = price_pnl * scale
            comm = commission_scaled(p.entry, fpx, p.lots)
            sw = swap_scaled(p.entry, p.entry_ts, fts, p.lots)
            pnl = raw_d - comm - sw
            equity = equity + pnl
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
            pd = prague_day_ms(fts)
            if pd not in day_start_eq:
                day_start_eq[pd] = equity - pnl
            day_pnl[pd] += pnl
            if day_start_eq[pd] > 0:
                ratio = day_pnl[pd] / day_start_eq[pd]
                if ratio <= DAILY_KILL:
                    killed_days.add(pd)
                if ratio <= DAILY_FLATTEN:
                    flatten_days.add(pd)
            closed.append(
                TradeEq(
                    p.side, p.entry_ts, p.entry, fts, fpx, freason,
                    p.lots, STOP, pnl, equity, pd, p.n_open_at_entry, p.risk_dollars,
                )
            )
        still = []

    return still, equity, peak, max_dd


def run_multi(
    bars,
    daily_closes,
    sma50,
    atr_map,
    start,
    end,
    *,
    name: str,
    max_n: int = MAX_N,
    risk_pct: Decimal | None = RISK_TICKET,
    flat_lots: Decimal | None = None,
    agg_cap: Decimal = AGG_CAP,
    use_filters: bool = True,
    daily_kill: bool = True,
    do_flatten: bool = True,
):
    """
    Multi-position C5 stack.
    - risk_pct: if set and flat_lots is None → size = equity * risk_pct / STOP
    - flat_lots: if set → fixed lots per ticket (config A)
    - max_n=1 + risk_pct → config C (scaled C5 single)
    """
    res = Meta(name=name)
    midnight = midnight_index(bars)
    days_sorted = sorted(daily_closes)
    day_index = {d: i for i, d in enumerate(days_sorted)}
    equity = START_EQUITY
    day_pnl: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
    day_start_eq: dict[date, Decimal] = {}
    killed_days: set[date] = set()
    flatten_days: set[date] = set()
    peak = equity
    max_dd = Decimal(0)
    opens: list[OpenPos] = []
    closed: list[TradeEq] = []

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
        entry_px = bars[i].o

        # Realize due exits before entry decision
        opens, equity, peak, max_dd = realize_opens(
            opens, entry_ts, equity, day_pnl, day_start_eq, killed_days, flatten_days,
            closed, peak, max_dd,
        )

        # Flatten if Prague day already ≤ −4%
        pd_entry = prague_day_ms(entry_ts)
        if pd_entry not in day_start_eq:
            day_start_eq[pd_entry] = equity
        if do_flatten and daily_kill and opens:
            so_far = (
                day_pnl[pd_entry] / day_start_eq[pd_entry]
                if day_start_eq[pd_entry] > 0
                else Decimal(0)
            )
            if so_far <= DAILY_FLATTEN or pd_entry in flatten_days:
                opens, equity, peak, max_dd = realize_opens(
                    opens, entry_ts, equity, day_pnl, day_start_eq, killed_days,
                    flatten_days, closed, peak, max_dd,
                    force_flat_at=(entry_ts, entry_px, "flatten-kill"),
                )
                res.n_flatten += 1
                flatten_days.add(pd_entry)
                killed_days.add(pd_entry)

        # Kill: no new entries
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

        # Same-direction only
        if opens:
            open_side = opens[0].side
            if side != open_side:
                res.skipped_side_mismatch += 1
                day += timedelta(days=1)
                continue

        if len(opens) >= max_n:
            res.skipped_n_full += 1
            day += timedelta(days=1)
            continue

        if equity <= START_EQUITY * FLOOR_MULT or equity <= Decimal("0"):
            res.skipped_lots += 1
            day += timedelta(days=1)
            continue

        # Size
        if flat_lots is not None:
            lots = flat_lots
            risk_d = dollar_risk(lots)
        else:
            risk_d_desired = equity * risk_pct
            scale = risk_d_desired / STOP
            lots = round_lots(BASE_LOT * scale)
            if lots < MIN_LOT or scale <= 0:
                res.skipped_lots += 1
                day += timedelta(days=1)
                continue
            risk_d = dollar_risk(lots)

        # Aggregate cap
        open_risk = sum((p.risk_dollars for p in opens), Decimal(0))
        if open_risk + risk_d > equity * agg_cap + Decimal("0.01"):  # 1¢ tolerance
            res.skipped_agg += 1
            day += timedelta(days=1)
            continue

        # Scan hard R=1 exit
        j, fill, reason = scan_exit(bars, i, side, entry_px, STOP, TARGET)
        if reason == "open-eod":
            # Keep as open till end; will realize at slice end
            opens.append(
                OpenPos(
                    side, entry_ts, entry_px, lots, risk_d,
                    len(bars) - 1, bars[-1].c, "open-eod", bars[-1].ts,
                    len(opens) + 1,
                )
            )
            res.n_entries += 1
            res.max_concurrent = max(res.max_concurrent, len(opens))
            day += timedelta(days=1)
            continue

        opens.append(
            OpenPos(
                side, entry_ts, entry_px, lots, risk_d,
                j, fill, reason, bars[j].ts, len(opens) + 1,
            )
        )
        res.n_entries += 1
        res.max_concurrent = max(res.max_concurrent, len(opens))
        day += timedelta(days=1)

    # End of slice: realize remaining (including open-eod as $0 if reason open-eod)
    end_ts = bars[midnight.get(end) or -1].ts if midnight.get(end) else bars[-1].ts
    # Force realize everything at last bar
    final_ts = bars[-1].ts
    final_px = bars[-1].c
    # First normal due
    opens, equity, peak, max_dd = realize_opens(
        opens, final_ts + 1, equity, day_pnl, day_start_eq, killed_days, flatten_days,
        closed, peak, max_dd,
    )
    # Anything still open (shouldn't) flatten
    if opens:
        opens, equity, peak, max_dd = realize_opens(
            opens, final_ts, equity, day_pnl, day_start_eq, killed_days, flatten_days,
            closed, peak, max_dd,
            force_flat_at=(final_ts, final_px, "slice-end"),
        )

    # Drop open-eod zero PnL from decision metrics? Keep them with pnl already computed.
    # Recompute open-eod as zero: if reason was open-eod, zero the pnl contribution...
    # Actually we filled at last close which may create fake PnL. Zero them out.
    adjusted = []
    eq = START_EQUITY
    peak2 = eq
    max_dd2 = Decimal(0)
    day_pnl2: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
    day_start_eq2: dict[date, Decimal] = {}
    for t in closed:
        if t.reason == "open-eod":
            pnl = Decimal(0)
        else:
            pnl = t.pnl
        eq = eq + pnl
        peak2 = max(peak2, eq)
        if peak2 > 0:
            dd = (peak2 - eq) / peak2
            if dd > max_dd2:
                max_dd2 = dd
        pd = t.prague_exit
        if pd not in day_start_eq2:
            day_start_eq2[pd] = eq - pnl
        day_pnl2[pd] += pnl
        adjusted.append(
            TradeEq(
                t.side, t.entry_ts, t.entry, t.exit_ts, t.exit, t.reason,
                t.lots, t.stop_dist, pnl, eq, pd, t.n_open_at_entry, t.risk_dollars,
            )
        )

    res.trades = adjusted
    res.max_dd = max_dd2  # type: ignore
    res.final_equity = eq  # type: ignore
    res.day_pnl = dict(day_pnl2)  # type: ignore
    res.day_start_eq = day_start_eq2  # type: ignore
    res.killed_days = killed_days  # type: ignore
    res.flatten_days = flatten_days  # type: ignore
    return res


def summarize_eq(trades: list[TradeEq]):
    closed = [t for t in trades if t.reason != "open-eod"]
    long_t = [t for t in closed if t.side == "long"]
    short_t = [t for t in closed if t.side == "short"]

    def pack(ts):
        if not ts:
            return {
                "n": 0, "wins": 0, "losses": 0, "win_rate": Decimal(0),
                "net": Decimal(0),
            }
        wins = sum(1 for t in ts if t.pnl > 0)
        return {
            "n": len(ts),
            "wins": wins,
            "losses": sum(1 for t in ts if t.pnl < 0),
            "win_rate": Decimal(wins) / Decimal(len(ts)),
            "net": sum((t.pnl for t in ts), Decimal(0)),
        }

    daily = defaultdict(lambda: Decimal(0))
    month = defaultdict(lambda: Decimal(0))
    month_n = defaultdict(int)
    for t in closed:
        daily[et_day(t.exit_ts)] += t.pnl
        m = ym_et(t.exit_ts)
        month[m] += t.pnl
        month_n[m] += 1
    worst = (
        min(daily.items(), key=lambda kv: (kv[1], kv[0])) if daily else ("none", Decimal(0))
    )
    months = {m: {"n": month_n[m], "net": month[m]} for m in sorted(month)}
    pos_m = sum(1 for v in months.values() if v["net"] >= 0)
    n_m = len(months)
    return {
        "all": pack(closed),
        "long": pack(long_t),
        "short": pack(short_t),
        "worst_day": worst,
        "months": months,
        "month_pos": pos_m,
        "month_n": n_m,
        "month_pos_rate": (Decimal(pos_m) / Decimal(n_m)) if n_m else Decimal(0),
        "avg_lots": (
            sum((t.lots for t in closed), Decimal(0)) / Decimal(len(closed))
            if closed else Decimal(0)
        ),
        "max_n_at_entry": max((t.n_open_at_entry for t in closed), default=0),
    }


def leave_out_two_best_eq(trades: list[TradeEq]):
    s = summarize_eq(trades)
    months = [(m, v["net"]) for m, v in s["months"].items() if v["n"] > 0]
    top2 = [m for m, _ in sorted(months, key=lambda kv: kv[1], reverse=True)[:2]]
    kept = [t for t in trades if t.reason == "open-eod" or ym_et(t.exit_ts) not in top2]
    return top2, summarize_eq(kept)


def slice_stats(res: Meta, start, end):
    """Filter trades whose entry is in [start, end]."""
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    # end is inclusive midnight; allow entries on that day
    end_ms_incl = end_ms + 24 * 3600 * 1000 - 1
    tr = [t for t in res.trades if start_ms <= t.entry_ts <= end_ms_incl and t.reason != "open-eod"]
    return summarize_eq(tr), tr


def run_full_range(bars, daily_closes, sma50, atr_map, start, end, **kwargs):
    return run_multi(bars, daily_closes, sma50, atr_map, start, end, **kwargs)


def main():
    print("C12: Loading Dukas M1…")
    bars = merge_bars(parse_csv(DUKAS_MAIN), parse_csv(DUKAS_EXT))
    daily_closes = build_daily_closes(bars)
    daily_ohlc = build_daily_ohlc(bars)
    sma50 = sma_map(daily_closes, 50)
    atr_map = daily_tr_atr(daily_ohlc, 14)
    mids = midnight_index(bars)
    ext_end = max(d for d in mids if d >= EXT_START)
    # Full range for equity path windows: fit start → ext end
    full_start, full_end = FIT_START, ext_end
    ho_days = (HO_END.date() - HO_START.date()).days
    print(f"bars={len(bars)} ext_end={ext_end.date()}")

    configs = [
        {
            "key": "A",
            "label": "max 3 × 0.01 lots + 2% agg",
            "kwargs": dict(
                name="c12-A", max_n=3, risk_pct=None, flat_lots=BASE_LOT, agg_cap=AGG_CAP
            ),
            "dd_legal_expected": True,  # 3×$413 ≈ 1.24% < 5%
        },
        {
            "key": "B",
            "label": "max 3 × 0.5%/ticket + 2% agg",
            "kwargs": dict(
                name="c12-B", max_n=3, risk_pct=RISK_TICKET, flat_lots=None, agg_cap=AGG_CAP
            ),
            "dd_legal_expected": True,  # agg 2% < 5% daily with buffer
        },
        {
            "key": "C",
            "label": "max 1 × 0.5% (scaled C5 single)",
            "kwargs": dict(
                name="c12-C", max_n=1, risk_pct=RISK_TICKET, flat_lots=None, agg_cap=AGG_CAP
            ),
            "dd_legal_expected": True,
        },
    ]

    results = {}
    for cfg in configs:
        print(f"\n=== Config {cfg['key']}: {cfg['label']} ===")
        # Full path for 60d windows + DD
        full = run_full_range(
            bars, daily_closes, sma50, atr_map, full_start, full_end, **cfg["kwargs"]
        )
        # Also slice-isolated runs for clean fit/HO/ext nets (independent equity resets)
        fit_r = run_full_range(
            bars, daily_closes, sma50, atr_map, FIT_START, FIT_END,
            **{**cfg["kwargs"], "name": cfg["kwargs"]["name"] + "-fit"},
        )
        ho_r = run_full_range(
            bars, daily_closes, sma50, atr_map, HO_START, HO_END,
            **{**cfg["kwargs"], "name": cfg["kwargs"]["name"] + "-ho"},
        )
        ext_r = run_full_range(
            bars, daily_closes, sma50, atr_map, EXT_START, ext_end,
            **{**cfg["kwargs"], "name": cfg["kwargs"]["name"] + "-ext"},
        )

        fit_s = summarize_eq(fit_r.trades)
        ho_s = summarize_eq(ho_r.trades)
        ext_s = summarize_eq(ext_r.trades)
        top2, lo_s = leave_out_two_best_eq(ho_r.trades)

        n_pass, n_win, samples = count_60d_pass_windows(
            full.trades, full.day_pnl, full.day_start_eq  # type: ignore
        )
        dd = max_realized_dd(full.trades)
        wd, wp = worst_day_pct(full.day_pnl, full.day_start_eq)  # type: ignore
        pace = monthly_pace(ho_s["all"]["net"], ho_days)
        d_both = days_to_target(pace, Decimal("15000"))
        fail_days = sum(
            1
            for d, pnl in full.day_pnl.items()  # type: ignore
            if full.day_start_eq.get(d) and full.day_start_eq[d] > 0  # type: ignore
            and pnl / full.day_start_eq[d] <= DAY_FAIL  # type: ignore
        )

        dd_ok = dd <= MAX_DD_LIM
        day_ok = (wp is None) or (wp > DAY_FAIL)
        legal = dd_ok and day_ok and fail_days == 0

        print(
            f"  HO net={float(ho_s['all']['net']):.2f} pace={float(pace):.2f}/mo "
            f"n={ho_s['all']['n']} WR={float(ho_s['all']['win_rate']):.1%} "
            f"maxN={ho_r.max_concurrent} skips_agg={ho_r.skipped_agg} "
            f"n_full={ho_r.skipped_n_full}"
        )
        print(
            f"  fit={float(fit_s['all']['net']):.2f} lo={float(lo_s['all']['net']):.2f} "
            f"ext={float(ext_s['all']['net']):.2f}"
        )
        print(
            f"  DD={float(dd):.1%} worst_day={wp and float(wp):.2%} "
            f"60d={n_pass}/{n_win} legal={legal} flatten={full.n_flatten}"
        )

        results[cfg["key"]] = {
            "cfg": cfg,
            "full": full,
            "fit_r": fit_r,
            "ho_r": ho_r,
            "ext_r": ext_r,
            "fit_s": fit_s,
            "ho_s": ho_s,
            "ext_s": ext_s,
            "top2": top2,
            "lo_s": lo_s,
            "n_pass": n_pass,
            "n_win": n_win,
            "samples": samples,
            "dd": dd,
            "wd": wd,
            "wp": wp,
            "pace": pace,
            "d_both": d_both,
            "fail_days": fail_days,
            "legal": legal,
            "dd_ok": dd_ok,
            "day_ok": day_ok,
        }

    # Decision
    a, b, c = results["A"], results["B"], results["C"]
    # ACCEPT if any DD-legal config has ≥1 clean 60d window
    legal_with_windows = [
        k for k, v in results.items() if v["legal"] and v["n_pass"] > 0
    ]
    legal_zero = [
        k for k, v in results.items() if v["legal"] and v["n_pass"] == 0
    ]
    illegal_only = [
        k for k, v in results.items() if (not v["legal"]) and v["n_pass"] > 0
    ]

    structural = False
    if legal_with_windows:
        verdict = "ACCEPT"
        binding = "none — ≥1 DD-legal ≤60d window"
        sentence = (
            f"ACCEPT C12 as ≤60d vehicle on config(s) {legal_with_windows}: "
            f"stacked C5 clears Challenge+Verification window(s) at legal DD."
        )
    elif illegal_only and not legal_with_windows:
        verdict = "CONDITIONAL"
        binding = "DD — windows only when DD illegal"
        sentence = (
            f"CONDITIONAL C12: 60d windows exist on {illegal_only} but DD/day fail; "
            f"DD-legal configs {list(results)} have 0 windows."
        )
    else:
        # all legal configs have 0 windows (or no legal configs)
        verdict = "REJECT"
        binding = "PACE+DD — stack cannot buy ≤60d at legal risk"
        structural = all(v["n_pass"] == 0 for v in results.values() if v["legal"]) or all(
            v["n_pass"] == 0 for v in results.values()
        )
        # Spec: If REJECT with 0 windows at DD-legal configs → structural implausible
        structural = len(legal_with_windows) == 0 and all(
            results[k]["n_pass"] == 0 for k in results if results[k]["dd_ok"]
        )
        # Broader: 0 windows at any config that is DD-legal
        dd_legal_keys = [k for k, v in results.items() if v["dd_ok"] and v["day_ok"]]
        structural = (
            verdict == "REJECT"
            and all(results[k]["n_pass"] == 0 for k in dd_legal_keys)
        )
        sentence = (
            f"REJECT C12 as ≤60d vehicle: 0 clean 60d windows on DD-legal configs "
            f"{dd_legal_keys}. A pace={float(a['pace']):.0f}/mo DD={float(a['dd']):.1%}; "
            f"B pace={float(b['pace']):.0f}/mo DD={float(b['dd']):.1%} 60d={b['n_pass']}/{b['n_win']}; "
            f"C pace={float(c['pace']):.0f}/mo DD={float(c['dd']):.1%}."
        )

    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")

    lines = []
    lines.append("# Candidate 12 Results — Multi-Position C5 Stack (N=3, 2% Agg Cap)")
    lines.append("")
    lines.append(f"**Decision: {verdict}**")
    lines.append("")
    lines.append(f"**One sentence:** {sentence}")
    lines.append("")
    if structural:
        lines.append(
            "**STRUCTURAL FINDING:** BTC-only Challenge+Verification in ≤60 days at FTMO "
            "5%/10% DD appears **structurally implausible** on measured C5–C12 + prior survey "
            "(robust edges too slow; HF no edge; size/stack hits DD wall)."
        )
        lines.append("")
    lines.append(f"**Measured:** {now}")
    lines.append("**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.")
    lines.append(f"**Spec:** `{SPEC}`")
    lines.append("")
    lines.append("## Locked thesis")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append("| Signal | C5: SMA50 exclusive dual + slope E + ATR < P75(100d) |")
    lines.append("| Entry | 00:00 UTC M1 open when signal fires |")
    lines.append("| Exit | hard R=1 stop=target=**412.91** (NOT R=2/3, NOT trail) |")
    lines.append("| Max concurrent | **3** same regime direction (a priori; never hedged) |")
    lines.append("| Per-ticket risk | 0.5% equity (B/C) or flat 0.01 lots (A) |")
    lines.append("| Aggregate open risk | sum remaining stop $ ≤ **2.0%** equity |")
    lines.append("| Prague kill | no new ≤ −3%; flatten all ≤ −4% |")
    lines.append("| Cost | C4/C5 0.065%/side + swap est −30%/360 |")
    lines.append("| Account | $100,000 2-step (ASSUMPTION) |")
    lines.append("| Pass bar | +10% then +15% in ≤60d without −5% day / −10% trough |")
    lines.append("")
    lines.append("## Config table")
    lines.append("")
    lines.append(
        "| Cfg | Mode | HO net | HO $/mo | Fit | Leave-out | Ext | "
        "Worst day % | Max DD | 60d passes | DD-legal? | Trades HO | Max concurrent |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    for k in ("A", "B", "C"):
        v = results[k]
        wp_s = f"{float(v['wp']):.2%}" if v["wp"] is not None else "n/a"
        lines.append(
            f"| {k} | {v['cfg']['label']} | ${fmt(v['ho_s']['all']['net'])} | "
            f"${fmt(v['pace'])} | ${fmt(v['fit_s']['all']['net'])} | "
            f"${fmt(v['lo_s']['all']['net'])} | ${fmt(v['ext_s']['all']['net'])} | "
            f"{wp_s} | {float(v['dd']):.1%} | **{v['n_pass']}/{v['n_win']}** | "
            f"{yn(v['legal'])} | {v['ho_s']['all']['n']} | {v['ho_r'].max_concurrent} |"
        )
    lines.append("")

    for k in ("A", "B", "C"):
        v = results[k]
        lines.append(f"## Config {k} detail — {v['cfg']['label']}")
        lines.append("")
        lines.append(
            f"- Entries full-range: {v['full'].n_entries}; max concurrent: {v['full'].max_concurrent}"
        )
        lines.append(
            f"- Skips HO: filter={v['ho_r'].skipped_filter} (slope≈{v['ho_r'].skip_slope}, "
            f"vol≈{v['ho_r'].skip_vol}); n_full={v['ho_r'].skipped_n_full}; "
            f"agg={v['ho_r'].skipped_agg}; side_mismatch={v['ho_r'].skipped_side_mismatch}; "
            f"kill={v['ho_r'].skipped_kill}; flatten_events={v['full'].n_flatten}"
        )
        lines.append(
            f"- HO WR {pct(v['ho_s']['all']['win_rate'])}; "
            f"L/S {v['ho_s']['long']['n']}/{v['ho_s']['short']['n']}; "
            f"avg lots {fmt(v['ho_s']['avg_lots'])}"
        )
        lines.append(
            f"- Leave-out removed {v['top2']} → ${fmt(v['lo_s']['all']['net'])}"
        )
        lines.append(
            f"- Final equity (full): ${fmt(v['full'].final_equity)} "
            f"(net ${fmt(v['full'].final_equity - START_EQUITY)})"  # type: ignore
        )
        lines.append(
            f"- Days to +15k at HO pace: "
            f"{fmt(v['d_both']) if v['d_both'] is not None else 'n/a'} d"
        )
        lines.append(f"- −5% Prague fail-days: {v['fail_days']}")
        lines.append("")
        lines.append("### HO monthly P&L")
        lines.append("")
        lines.append("| ET exit month | Trades | Net $ |")
        lines.append("|---|---:|---:|")
        for m, mv in v["ho_s"]["months"].items():
            lines.append(f"| {m} | {mv['n']} | {fmt(mv['net'])} |")
        lines.append("")
        lines.append("### 60-day pass windows (sample ≤20)")
        lines.append("")
        if v["samples"]:
            lines.append("| Start | End | Start eq | Max mult | Min mult | Worst day |")
            lines.append("|---|---|---:|---:|---:|---:|")
            for s in v["samples"]:
                lines.append(
                    f"| {s['start']} | {s['end']} | {s['start_eq']:.0f} | "
                    f"{s['max_mult']:.3f} | {s['min_mult']:.3f} | {s['worst_day']:.2%} |"
                )
        else:
            lines.append("_None._")
        lines.append("")

    lines.append("## Comparison vs C5 / C6 / C10")
    lines.append("")
    lines.append("| | C5 @0.01 | C6 @legal ~0.06 | C10 @0.5% | C12-A | C12-B | C12-C |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    lines.append(
        f"| HO $/mo | ~491 | ~scaled | ~450 | "
        f"**{fmt(a['pace'])}** | **{fmt(b['pace'])}** | **{fmt(c['pace'])}** |"
    )
    lines.append(
        f"| ≤60d windows | 0 (slow) | 0 (DD wall) | 0/252 | "
        f"**{a['n_pass']}/{a['n_win']}** | **{b['n_pass']}/{b['n_win']}** | "
        f"**{c['n_pass']}/{c['n_win']}** |"
    )
    lines.append(
        f"| Max DD | low | illegal at pace | 5.6%@0.5% | "
        f"**{float(a['dd']):.1%}** | **{float(b['dd']):.1%}** | **{float(c['dd']):.1%}** |"
    )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"**{verdict}** — C12 is research-only. Not deployable live from this folder.")
    lines.append("")
    lines.append(f"### Binding constraint")
    lines.append("")
    lines.append(binding)
    lines.append("")
    if structural:
        lines.append("### Structural implausibility (explicit)")
        lines.append("")
        lines.append(
            "**BTC-only Challenge + Verification in ≤60 days at FTMO 5% daily / 10% max DD "
            "appears structurally implausible** on the measured sample and rule set:"
        )
        lines.append("")
        lines.append(
            "- **C5** research ACCEPT @0.01 (~$480–490/mo) — robust but ~2y for both steps"
        )
        lines.append(
            "- **C6** C5 scale → REJECT (pace needs ~0.15 lots; DD wall; legal ~0.06 → ~5mo)"
        )
        lines.append("- **C7** H4 breakout R=1 → REJECT (DD ~17%, slow)")
        lines.append("- **C8** hard R=2 on SMA50 → REJECT (edge flipped negative)")
        lines.append("- **C9** ATR trail → CONDITIONAL (pace+DD; trail never left BE)")
        lines.append("- **C10** R-trail → CONDITIONAL (0/252 windows @ legal; DD 14.7%@1%)")
        lines.append("- **C11** H1 mom R=2 → REJECT (negative edge, DD 59.6%)")
        lines.append(
            f"- **C12** multi-stack N=3 + 2% agg on C5 → **REJECT** "
            f"(A {a['n_pass']}/{a['n_win']}, B {b['n_pass']}/{b['n_win']}, "
            f"C {c['n_pass']}/{c['n_win']} at DD-legal configs)"
        )
        lines.append("")
        lines.append("Prior survey: HF/breakout books either no edge or stop sizes blow DD.")
        lines.append("")
        lines.append("### Honest slower path (not fake hope)")
        lines.append("")
        lines.append(
            "1. **C5 @ legal size (0.01–0.05)** — robustness book; expect many months, not ≤60d."
        )
        lines.append(
            "2. **C10 @ 0.5%** — best fit of SMA50 family; still 0 ≤60d windows; robustness only."
        )
        lines.append(
            "3. **Longer horizon** — target Challenge alone in ~4–6 months at legal risk, "
            "or accept that BTC-only 2-step ≤60d is not in the measured edge set."
        )
        lines.append(
            "4. **Do not** raise live risk / stack live C4 / deploy C5–C12 without separate approval."
        )
        lines.append("")

    lines.append("## Research-next")
    lines.append("")
    if structural:
        lines.append(
            "Park BTC-only ≤60d hunt. Options for Ops/Odin: (a) run C5/C10 robustness at legal "
            "size on paper/challenge with honest multi-month timeline; (b) diversify beyond "
            "BTC-only for pace; (c) revisit only if new a-priori edge thesis (not more SMA50 milking)."
        )
    else:
        lines.append(
            "If CONDITIONAL/ACCEPT: paper-trade winning config only; no live arm from research."
        )
    lines.append("")
    lines.append("## Assumptions / limitations")
    lines.append("")
    lines.append("1. Real Dukas M1 bid only; missing midnights skipped.")
    lines.append("2. N=3 and 2% agg locked a priori (not fit-tuned).")
    lines.append("3. Remaining stop $ = full STOP×lots/0.01 while open (hard R=1; no trail).")
    lines.append("4. Same-direction stack only; opposite regime while open → skip.")
    lines.append("5. Flatten at ≤−4% closes remaining at next signal bar open (research approx).")
    lines.append("6. 60d windows use Prague-day equity path on full fit→ext continuum.")
    lines.append("7. No live engine changes.")
    lines.append("")
    lines.append("## User summary (≤15 lines)")
    lines.append("")
    lines.append(f"1. **{verdict}** — multi-position C5 stack N=3 + 2% agg cap.")
    lines.append(
        f"2. Config A (3×0.01): HO ${fmt(a['pace'])}/mo; DD {float(a['dd']):.1%}; "
        f"60d **{a['n_pass']}/{a['n_win']}**."
    )
    lines.append(
        f"3. Config B (3×0.5%, 2% agg): HO ${fmt(b['pace'])}/mo; DD {float(b['dd']):.1%}; "
        f"60d **{b['n_pass']}/{b['n_win']}**."
    )
    lines.append(
        f"4. Config C (1×0.5%): HO ${fmt(c['pace'])}/mo; DD {float(c['dd']):.1%}; "
        f"60d **{c['n_pass']}/{c['n_win']}**."
    )
    lines.append(f"5. Binding: {binding}.")
    if structural:
        lines.append(
            "6. **Structural:** BTC-only ≤60d Challenge+Verification @ FTMO 5%/10% "
            "appears implausible on C5–C12 + survey."
        )
        lines.append(
            "7. Honest path: C5/C10 at legal size over longer horizon — not fake hope."
        )
    lines.append("8. Live engines untouched.")

    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {OUT}")
    print(f"DECISION={verdict} STRUCTURAL={structural}")
    print(sentence)

    # Also write a small JSON sidecar for STATUS
    summary_path = Path("/workspace/btc-strategies/candidate-12-summary.txt")
    summary_path.write_text(
        f"verdict={verdict}\nstructural={structural}\n"
        f"A_pace={float(a['pace']):.2f} A_dd={float(a['dd']):.4f} A_60={a['n_pass']}/{a['n_win']}\n"
        f"B_pace={float(b['pace']):.2f} B_dd={float(b['dd']):.4f} B_60={b['n_pass']}/{b['n_win']}\n"
        f"C_pace={float(c['pace']):.2f} C_dd={float(c['dd']):.4f} C_60={c['n_pass']}/{c['n_win']}\n"
        f"binding={binding}\n"
        f"sentence={sentence}\n"
    )
    return verdict, structural, results


if __name__ == "__main__":
    main()
