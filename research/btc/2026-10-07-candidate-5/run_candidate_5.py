#!/usr/bin/env python3
"""Candidate 5: C4 base + SMA50 slope (E) + elevated-vol skip (ATR < P75 of 100d). Research only."""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
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
    commission_rt,
    swap_cost,
    Trade,
    RunMeta,
    Bar,
)

ET = ZoneInfo("America/New_York")
OUT = Path("/workspace/btc-strategies/candidate-5-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-5.md")

STOP = Decimal("412.91")
TARGET = Decimal("412.91")
FIT_SOFT = Decimal("-5000")
SLOPE_LOOKBACK = 10
ATR_WINDOW = 100
ATR_PCTILE = Decimal("0.75")  # skip if ATR >= P75 (milder than A's median)


def scan_exit(bars, start_i, side, entry, stop=STOP, target=TARGET):
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


def daily_tr_atr(daily_ohlc: dict, n=14):
    days = sorted(daily_ohlc)
    atr_map: dict[datetime, Decimal | None] = {d: None for d in days}
    if not days:
        return atr_map
    trs = []
    atr_list = []
    for i, d in enumerate(days):
        o, h, l, c = daily_ohlc[d]
        if i == 0:
            tr = h - l
        else:
            prev_c = daily_ohlc[days[i - 1]][3]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
        if i == n - 1:
            a = sum(trs[:n], Decimal(0)) / Decimal(n)
            atr_list.append(a)
            atr_map[d] = a
        elif i >= n:
            a = (atr_list[-1] * Decimal(n - 1) + tr) / Decimal(n)
            atr_list.append(a)
            atr_map[d] = a
        else:
            atr_list.append(None)
    return atr_map


def build_daily_ohlc(bars: list[Bar]):
    by: dict[datetime, list[Bar]] = defaultdict(list)
    for b in bars:
        d = utc_dt(b.ts).replace(hour=0, minute=0, second=0, microsecond=0)
        by[d].append(b)
    out = {}
    for d in sorted(by):
        xs = by[d]
        out[d] = (xs[0].o, max(x.h for x in xs), min(x.l for x in xs), xs[-1].c)
    return out


def percentile(vals: list[Decimal], p: Decimal) -> Decimal:
    """Inclusive linear percentile on sorted values; p in [0,1]."""
    sv = sorted(vals)
    if not sv:
        raise ValueError("empty")
    if len(sv) == 1:
        return sv[0]
    # nearest-rank / index: (n-1)*p
    pos = float(p) * (len(sv) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sv) - 1)
    w = Decimal(str(pos - lo))
    return sv[lo] * (1 - w) + sv[hi] * w


def run_variant(
    bars,
    daily_closes,
    sma50,
    atr_map,
    start,
    end,
    *,
    name: str,
    sma_slope_filter: bool = True,
    vol_p75_gate: bool = True,
):
    """
    C5 primary: sma_slope_filter + vol_p75_gate.
    Diagnostic: sma_slope_filter only (E-only).
    """
    res = RunMeta(name=name)
    midnight = midnight_index(bars)
    days_sorted = sorted(daily_closes)
    day_index = {d: i for i, d in enumerate(days_sorted)}
    free_after = 0
    skipped_filter = 0
    skip_slope = 0
    skip_vol = 0

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

        ok = True
        if sma_slope_filter:
            idx = day_index.get(prior)
            if idx is None or idx < SLOPE_LOOKBACK:
                ok = False
                skip_slope += 1
            else:
                ago = days_sorted[idx - SLOPE_LOOKBACK]
                s_ago = sma50.get(ago)
                if s_ago is None:
                    ok = False
                    skip_slope += 1
                elif side == "long" and not (ps > s_ago):
                    ok = False
                    skip_slope += 1
                elif side == "short" and not (ps < s_ago):
                    ok = False
                    skip_slope += 1

        if ok and vol_p75_gate:
            atr_p = atr_map.get(prior)
            idx = day_index.get(prior)
            if atr_p is None or idx is None or idx < ATR_WINDOW - 1:
                ok = False
                skip_vol += 1
            else:
                window_days = days_sorted[idx - (ATR_WINDOW - 1) : idx + 1]
                vals = [atr_map[d] for d in window_days if atr_map.get(d) is not None]
                if len(vals) < 50:
                    ok = False
                    skip_vol += 1
                else:
                    thr = percentile(vals, ATR_PCTILE)
                    if atr_p >= thr:
                        ok = False
                        skip_vol += 1

        if not ok:
            skipped_filter += 1
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
        j, fill, reason = scan_exit(bars, i, side, entry_px)
        if reason == "open-eod":
            pnl = comm = sw = Decimal(0)
            free_after = bars[-1].ts + 1
        else:
            pnl = raw_pnl(side, entry_px, fill)
            comm = commission_rt(entry_px, fill)
            sw = swap_cost(entry_px, entry_ts, bars[j].ts)
            free_after = bars[j].ts + 1
        res.trades.append(
            Trade(side, side, entry_ts, entry_px, bars[j].ts, fill, reason, pnl, comm, sw)
        )
        day += timedelta(days=1)

    res.skipped_filter = skipped_filter  # type: ignore
    res.skip_slope = skip_slope  # type: ignore
    res.skip_vol = skip_vol  # type: ignore
    return res


def summarize(trades):
    closed = [t for t in trades if t.reason != "open-eod"]
    open_n = len(trades) - len(closed)
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
                "net_comm": Decimal(0),
                "net_full": Decimal(0),
            }
        wins = sum(1 for t in ts if t.pnl_raw > 0)
        return {
            "n": len(ts),
            "wins": wins,
            "losses": sum(1 for t in ts if t.pnl_raw < 0),
            "win_rate": Decimal(wins) / Decimal(len(ts)),
            "net_raw": sum((t.pnl_raw for t in ts), Decimal(0)),
            "net_comm": sum((t.pnl_raw - t.commission for t in ts), Decimal(0)),
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
        "open_n": open_n,
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


def leave_out_two_best(trades):
    s = summarize(trades)
    months = [(m, v["net_full"]) for m, v in s["months"].items() if v["n"] > 0]
    top2 = [m for m, _ in sorted(months, key=lambda kv: kv[1], reverse=True)[:2]]
    kept = [t for t in trades if t.reason == "open-eod" or ym_et(t.exit_ts) not in top2]
    return top2, summarize(kept)


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


def main():
    print("Loading…")
    bars = merge_bars(parse_csv(DUKAS_MAIN), parse_csv(DUKAS_EXT))
    daily_closes = build_daily_closes(bars)
    daily_ohlc = build_daily_ohlc(bars)
    sma50 = sma_map(daily_closes, 50)
    atr_map = daily_tr_atr(daily_ohlc, 14)
    mids = midnight_index(bars)
    ext_end = max(d for d in mids if d >= EXT_START)
    print(f"bars={len(bars)} ext_end={ext_end.date()}")

    print("C5 primary: E slope + V75 vol…")
    fit = run_variant(
        bars, daily_closes, sma50, atr_map, FIT_START, FIT_END, name="c5-fit"
    )
    ho = run_variant(
        bars, daily_closes, sma50, atr_map, HO_START, HO_END, name="c5-ho"
    )
    ext = run_variant(
        bars, daily_closes, sma50, atr_map, EXT_START, ext_end, name="c5-ext"
    )
    fit_s, ho_s, ext_s = map(summarize, (fit.trades, ho.trades, ext.trades))
    top2, lo_s = leave_out_two_best(ho.trades)

    print("Diagnostic: E-only…")
    fit_e = run_variant(
        bars,
        daily_closes,
        sma50,
        atr_map,
        FIT_START,
        FIT_END,
        name="e-only-fit",
        vol_p75_gate=False,
    )
    ho_e = run_variant(
        bars,
        daily_closes,
        sma50,
        atr_map,
        HO_START,
        HO_END,
        name="e-only-ho",
        vol_p75_gate=False,
    )
    ext_e = run_variant(
        bars,
        daily_closes,
        sma50,
        atr_map,
        EXT_START,
        ext_end,
        name="e-only-ext",
        vol_p75_gate=False,
    )
    fit_e_s, ho_e_s, ext_e_s = map(summarize, (fit_e.trades, ho_e.trades, ext_e.trades))
    top2_e, lo_e_s = leave_out_two_best(ho_e.trades)

    buy_net, buy_n = buy_only_r3(bars, HO_START, HO_END)
    print("buy-only", float(buy_net))
    print(
        "C5 HO",
        float(ho_s["all"]["net_full"]),
        "leave",
        top2,
        float(lo_s["all"]["net_full"]),
    )
    print("C5 ext", float(ext_s["all"]["net_full"]), "fit", float(fit_s["all"]["net_full"]))
    print("C5 months", ho_s["month_pos"], ho_s["month_n"])
    print(
        "E-only fit/ho/ext/lo",
        float(fit_e_s["all"]["net_full"]),
        float(ho_e_s["all"]["net_full"]),
        float(ext_e_s["all"]["net_full"]),
        float(lo_e_s["all"]["net_full"]),
    )

    g1 = (
        ho_s["all"]["net_full"] > 0
        and ho_s["all"]["net_full"] > BUY_ONLY_HOLDOUT_NET
        and ho_s["all"]["net_full"] > buy_net
    )
    g2 = ext_s["all"]["net_full"] >= 0
    g3 = lo_s["all"]["net_full"] > 0
    g4 = (
        ho_s["worst_raw"][1] >= WORST_DAY_BUDGET
        and ext_s["worst_raw"][1] >= WORST_DAY_BUDGET
        and ho_s["days_breach_raw"] == 0
        and ext_s["days_breach_raw"] == 0
    )
    g5 = fit_s["all"]["net_full"] >= FIT_SOFT
    if ho_s["month_n"] < 5:
        g6 = False
        g6_note = f"<5 months ({ho_s['month_n']})"
    else:
        g6 = ho_s["month_pos_rate"] >= Decimal("0.5")
        g6_note = f"{ho_s['month_pos']}/{ho_s['month_n']} ({pct(ho_s['month_pos_rate'])})"

    # C4 reference (published)
    c4 = {
        "fit": Decimal("-8949.23"),
        "ho": Decimal("7158.94"),
        "ext": Decimal("786.15"),
        "lo": Decimal("2251.35"),
        "months": "8/11",
        "worst": Decimal("-825.82"),
    }

    if all([g1, g2, g3, g4, g5, g6]):
        verdict = "ACCEPT"
        sentence = (
            f"ACCEPT Candidate 5: E+V75 clears all gates "
            f"(HO ${fmt(ho_s['all']['net_full'])}, leave-out ${fmt(lo_s['all']['net_full'])}, "
            f"ext ${fmt(ext_s['all']['net_full'])}, fit ${fmt(fit_s['all']['net_full'])}, months {g6_note})."
        )
        gate = "Research ACCEPT only — no live deploy without separate approval."
    elif g1 and g2 and g4 and (not g3 or not g5 or not g6):
        verdict = "CONDITIONAL"
        fails = []
        if not g3:
            fails.append(f"leave-out ${fmt(lo_s['all']['net_full'])} {top2}")
        if not g5:
            fails.append(f"fit ${fmt(fit_s['all']['net_full'])}")
        if not g6:
            fails.append(f"months {g6_note}")
        sentence = (
            "CONDITIONAL Candidate 5: HO/ext/worst-day OK but " + "; ".join(fails) + "."
        )
        gate = "Remaining: " + "; ".join(fails) + ". No live changes."
    else:
        verdict = "REJECT"
        fails = []
        if not g1:
            fails.append(f"HO ${fmt(ho_s['all']['net_full'])}")
        if not g2:
            fails.append(f"ext ${fmt(ext_s['all']['net_full'])}")
        if not g3:
            fails.append(f"leave-out ${fmt(lo_s['all']['net_full'])} {top2}")
        if not g4:
            fails.append(f"worst HO {ho_s['worst_raw']} ext {ext_s['worst_raw']}")
        if not g5:
            fails.append(f"fit ${fmt(fit_s['all']['net_full'])}")
        if not g6:
            fails.append(f"months {g6_note}")
        sentence = "REJECT Candidate 5: " + "; ".join(fails) + "."
        gate = "Do not propose live."

    # Clearly better than C4?
    better_bits = []
    worse_bits = []
    if fit_s["all"]["net_full"] > c4["fit"]:
        better_bits.append(f"fit Δ ${fmt(fit_s['all']['net_full'] - c4['fit'])}")
    else:
        worse_bits.append("fit")
    if ho_s["all"]["net_full"] >= c4["ho"]:
        better_bits.append(f"HO ≥ C4")
    elif ho_s["all"]["net_full"] > 0 and g1:
        better_bits.append(f"HO still + (${fmt(ho_s['all']['net_full'])})")
        if ho_s["all"]["net_full"] < c4["ho"]:
            worse_bits.append(f"HO lower than C4 by ${fmt(c4['ho'] - ho_s['all']['net_full'])}")
    else:
        worse_bits.append("HO")
    if ext_s["all"]["net_full"] >= 0:
        if ext_s["all"]["net_full"] >= c4["ext"]:
            better_bits.append("ext ≥ C4")
        else:
            worse_bits.append(f"ext lower (${fmt(ext_s['all']['net_full'])} vs C4 ${fmt(c4['ext'])})")
    else:
        worse_bits.append("ext < 0")
    if lo_s["all"]["net_full"] > 0:
        if lo_s["all"]["net_full"] >= c4["lo"]:
            better_bits.append("leave-out ≥ C4")
        else:
            worse_bits.append(
                f"leave-out lower (${fmt(lo_s['all']['net_full'])} vs C4 ${fmt(c4['lo'])})"
            )
    else:
        worse_bits.append("leave-out ≤ 0")

    # Clear better = clears more gates OR (same gates and strictly better fit without killing OOS)
    c4_gates_pass = 5  # all but fit
    c5_gates_pass = sum([g1, g2, g3, g4, g5, g6])
    if verdict == "ACCEPT" and c4_gates_pass < 6:
        clearly_better = True
        better_why = "Clears all 6 gates including fit; C4 failed fit."
    elif g5 and g1 and g2 and g3 and g4 and g6:
        clearly_better = True
        better_why = "Clears all gates."
    elif g5 and (not g2 or not g3):
        clearly_better = False
        better_why = "Fit repaired but OOS/leave-out damaged (same failure mode as C4b-A)."
    elif fit_s["all"]["net_full"] > c4["fit"] and g1 and g2 and g3 and g4 and g6 and not g5:
        # better fit, preserves OOS, still CONDITIONAL
        if fit_s["all"]["net_full"] > c4["fit"] + Decimal("1000"):
            clearly_better = True
            better_why = (
                f"Materially better fit ({fmt(fit_s['all']['net_full'])} vs C4 {fmt(c4['fit'])}) "
                f"while preserving HO/ext/leave-out/worst-day/months — still CONDITIONAL on fit gate."
            )
        else:
            clearly_better = False
            better_why = "Only marginal fit improvement; not clearly better than C4."
    else:
        clearly_better = False
        better_why = "Does not dominate C4 on the gate set."

    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")

    def block(title, summ, meta=None):
        lines = [f"### {title}", ""]
        if meta:
            tot = meta.regime_long + meta.regime_short + meta.regime_flat
            if tot:
                lines.append(
                    f"- Regime days L/S/F: {meta.regime_long}/{meta.regime_short}/{meta.regime_flat}; "
                    f"skip no-bar/in-trade: {meta.skipped_no_bar}/{meta.skipped_in_trade}; "
                    f"filter skips: {getattr(meta, 'skipped_filter', 0)} "
                    f"(slope≈{getattr(meta, 'skip_slope', '?')}, vol≈{getattr(meta, 'skip_vol', '?')})"
                )
                lines.append("")
        lines += [
            "| Book | Trades | Win rate | Net raw $ | Net − comm $ | Net full $ |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for label, key in [("Long", "long"), ("Short", "short"), ("Combined", "all")]:
            s = summ[key]
            lines.append(
                f"| {label} | {s['n']} | {pct(s['win_rate']) if s['n'] else 'n/a'} | "
                f"{fmt(s['net_raw'])} | {fmt(s['net_comm'])} | {fmt(s['net_full'])} |"
            )
        lines += [
            "",
            f"- Worst ET day raw: **{summ['worst_raw'][0]}** → **${fmt(summ['worst_raw'][1])}**; "
            f"days < −$2,000: **{summ['days_breach_raw']}**; open-at-end: {summ['open_n']}",
            f"- Months ≥0: **{summ['month_pos']}/{summ['month_n']}** ({pct(summ['month_pos_rate'])})",
            "",
            "| ET exit month | Trades | Net full $ |",
            "|---|---:|---:|",
        ]
        for m, v in summ["months"].items():
            lines.append(f"| {m} | {v['n']} | {fmt(v['net_full'])} |")
        lines.append("")
        return "\n".join(lines)

    md = [
        "# Candidate 5 Results — SMA50 Slope + Elevated-Vol Skip (R=1)",
        "",
        f"**Decision: {verdict}**",
        "",
        f"**One sentence:** {sentence}",
        "",
        f"**Clearly better than C4?** {'YES' if clearly_better else 'NO'} — {better_why}",
        "",
        f"**Measured:** {now}",
        "**Live engines:** not modified.",
        f"**Spec:** `{SPEC}`",
        "",
        "## Rules used",
        "",
        f"- SMA50 exclusive dual; stop=target=**{STOP}** (R=1); max 1; 00:00 UTC entry",
        f"- Filter E: SMA50 slope rising for long / falling for short (lookback {SLOPE_LOOKBACK} series days)",
        f"- Filter V75: prior ATR(14) < P{int(ATR_PCTILE*100)} of prior {ATR_WINDOW}d ATR (≥50 non-null)",
        f"- One-stop risk ≈ **${STOP}** at vol 0.01; costs 0.065% + swap est.",
        f"- Data: merged Dukas M1 {utc_dt(bars[0].ts)} → {utc_dt(bars[-1].ts)}",
        "",
        "## Gate checklist",
        "",
        "| Gate | Pass? | Detail |",
        "|---|---|---|",
        f"| 1 Holdout full > 0 and > buy-only | {'YES' if g1 else 'NO'} | HO ${fmt(ho_s['all']['net_full'])}; buy-only ${fmt(buy_net)} |",
        f"| 2 Extension full ≥ 0 | {'YES' if g2 else 'NO'} | ${fmt(ext_s['all']['net_full'])} |",
        f"| 3 Leave-out two best HO months > 0 | {'YES' if g3 else 'NO'} | removed {top2}; left ${fmt(lo_s['all']['net_full'])} |",
        f"| 4 Worst day ≥ −2000 HO & ext | {'YES' if g4 else 'NO'} | HO {ho_s['worst_raw']}; ext {ext_s['worst_raw']} |",
        f"| 5 Fit full ≥ −5000 | {'YES' if g5 else 'NO'} | ${fmt(fit_s['all']['net_full'])} |",
        f"| 6 Holdout months ≥50% green | {'YES' if g6 else 'NO'} | {g6_note} |",
        "",
        f"**Remaining gate / next:** {gate}",
        "",
        "## Comparison vs C4 / C4b-E",
        "",
        "| Variant | Fit full | HO full | Ext full | Leave-out | HO months | Worst HO | Gates passed |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
        f"| C4 baseline | {fmt(c4['fit'])} | {fmt(c4['ho'])} | {fmt(c4['ext'])} | {fmt(c4['lo'])} | {c4['months']} | {fmt(c4['worst'])} | 5/6 |",
        f"| C4b-E (prior) | -6,693.22 | 7,229.50 | 786.15 | 2,320.09 | 7/11 | -825.82 | 5/6 |",
        f"| C5 E+V75 (this) | {fmt(fit_s['all']['net_full'])} | {fmt(ho_s['all']['net_full'])} | {fmt(ext_s['all']['net_full'])} | {fmt(lo_s['all']['net_full'])} | {g6_note} | {fmt(ho_s['worst_raw'][1])} | {c5_gates_pass}/6 |",
        f"| Diagnostic E-only | {fmt(fit_e_s['all']['net_full'])} | {fmt(ho_e_s['all']['net_full'])} | {fmt(ext_e_s['all']['net_full'])} | {fmt(lo_e_s['all']['net_full'])} | {ho_e_s['month_pos']}/{ho_e_s['month_n']} | {fmt(ho_e_s['worst_raw'][1])} | (diag) |",
        "",
        f"- Better bits: {', '.join(better_bits) if better_bits else 'none'}",
        f"- Worse bits: {', '.join(worse_bits) if worse_bits else 'none'}",
        "",
        "## Slices (C5 primary)",
        "",
        block(f"Holdout ({HO_START.date()} → {HO_END.date()} UTC entries)", ho_s, ho),
        f"### Leave-out (removed {top2})\n\n"
        f"| Trades left | Net full $ | Worst raw |\n|---:|---:|---|\n"
        f"| {lo_s['all']['n']} | **{fmt(lo_s['all']['net_full'])}** | {lo_s['worst_raw'][0]} {fmt(lo_s['worst_raw'][1])} |\n",
        block(f"Extension ({EXT_START.date()} → {ext_end.date()})", ext_s, ext),
        block(f"Fit ({FIT_START.date()} → {FIT_END.date()})", fit_s, fit),
        "## Diagnostic — E-only (no V75; not a new candidate)",
        "",
        f"- Fit ${fmt(fit_e_s['all']['net_full'])}; HO ${fmt(ho_e_s['all']['net_full'])}; "
        f"ext ${fmt(ext_e_s['all']['net_full'])}; leave-out removed {top2_e} → ${fmt(lo_e_s['all']['net_full'])}",
        f"- Filter skips fit/HO: {getattr(fit_e, 'skipped_filter', 0)}/{getattr(ho_e, 'skipped_filter', 0)}",
        "",
        "## Assumptions / limitations",
        "",
        "1. Real Dukas M1 only; missing midnights skipped.",
        "2. Slope lookback 10 and V75 locked a priori (not fit-tuned).",
        "3. Catalogue $ at vol 0.01; leave-out by ET exit month.",
        "4. No live engine changes.",
        "",
        "## User summary (≤15 lines)",
        "",
        f"1. **{verdict}** — SMA50 exclusive dual R=1 + E slope + ATR < P75(100d).",
        f"2. Holdout full **${fmt(ho_s['all']['net_full'])}** (L/S {ho_s['long']['n']}/{ho_s['short']['n']}, "
        f"{pct(ho_s['all']['win_rate'])} wins) vs buy-only **${fmt(buy_net)}**.",
        f"3. Extension **${fmt(ext_s['all']['net_full'])}**; fit **${fmt(fit_s['all']['net_full'])}**.",
        f"4. Leave-out removed **{top2}** → **${fmt(lo_s['all']['net_full'])}**.",
        f"5. Worst HO **{ho_s['worst_raw'][0]} ${fmt(ho_s['worst_raw'][1])}**; "
        f"ext **{ext_s['worst_raw'][0]} ${fmt(ext_s['worst_raw'][1])}**.",
        f"6. Months green **{g6_note}**.",
        f"7. vs C4: clearly better? **{'YES' if clearly_better else 'NO'}** — {better_why}",
        f"8. {sentence}",
        "9. Live engines untouched.",
        "",
    ]

    OUT.write_text("\n".join(md))
    print("Wrote", OUT)
    print("VERDICT", verdict)
    print(sentence)
    print("CLEARLY_BETTER", clearly_better, better_why)


if __name__ == "__main__":
    main()
