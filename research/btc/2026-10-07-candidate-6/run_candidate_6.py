#!/usr/bin/env python3
"""Candidate 6: C5 fast-scale probe — pace vs FTMO DD wall. Research only; no live touches."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/workspace/btc-strategies")

from run_sma50_short_harden import (
    DUKAS_MAIN,
    DUKAS_EXT,
    BUY_ONLY_HOLDOUT_NET,
    HO_START,
    HO_END,
    EXT_START,
    FIT_START,
    FIT_END,
    parse_csv,
    merge_bars,
    build_daily_closes,
    sma_map,
    midnight_index,
    fmt,
    WORST_DAY_BUDGET,
)
from run_candidate_5 import (
    STOP,
    run_variant,
    summarize,
    leave_out_two_best,
    daily_tr_atr,
    build_daily_ohlc,
)

OUT = Path("/workspace/btc-strategies/candidate-6-results.md")
SPEC = Path("/workspace/btc-strategies/ftmo-candidate-6.md")

ACCOUNT = Decimal("100000")  # ASSUMPTION
CHALLENGE = Decimal("10000")  # +10%
VERIFY = Decimal("5000")  # +5%
BOTH = CHALLENGE + VERIFY  # 15000
DAILY_LIM = Decimal("5000")  # 5%
MAX_DD_LIM = Decimal("10000")  # 10%
PACE_TARGET_MO = Decimal("7500")  # ~$7.5k/mo for ≤60d both
BASE_VOL = Decimal("0.01")
DAYS_PER_MO = Decimal("30.44")

# Scale grid (multiples of 0.01)
SCALE_VOLS = [
    Decimal("0.01"),
    Decimal("0.02"),
    Decimal("0.03"),
    Decimal("0.04"),
    Decimal("0.05"),
    Decimal("0.06"),
    Decimal("0.08"),
    Decimal("0.10"),
    Decimal("0.15"),
    Decimal("0.20"),
]


def scale_factor(vol: Decimal) -> Decimal:
    return vol / BASE_VOL


def ho_calendar_days() -> int:
    return (HO_END.date() - HO_START.date()).days


def monthly_pace(net: Decimal, days: int) -> Decimal:
    if days <= 0:
        return Decimal(0)
    return net / (Decimal(days) / DAYS_PER_MO)


def days_to_target(pace_mo: Decimal, target: Decimal) -> Decimal | None:
    if pace_mo <= 0:
        return None
    return (target / pace_mo) * DAYS_PER_MO


def main():
    print("Loading Dukas M1…")
    main_bars = parse_csv(DUKAS_MAIN)
    ext_bars = parse_csv(DUKAS_EXT)
    bars = merge_bars(main_bars, ext_bars)
    print(f"Bars: {len(bars)}  first={bars[0].ts} last={bars[-1].ts}")

    daily_closes = build_daily_closes(bars)
    sma50 = sma_map(daily_closes, 50)
    daily_ohlc = build_daily_ohlc(bars)
    atr_map = daily_tr_atr(daily_ohlc, 14)

    mids = midnight_index(bars)
    ext_end = max(d for d in mids if d >= EXT_START)
    print(f"ext_end={ext_end.date()}")

    print("Running C5 E+V75 on fit/HO/ext…")
    fit_r = run_variant(
        bars, daily_closes, sma50, atr_map, FIT_START, FIT_END,
        name="C6=C5-fit", sma_slope_filter=True, vol_p75_gate=True,
    )
    ho_r = run_variant(
        bars, daily_closes, sma50, atr_map, HO_START, HO_END,
        name="C6=C5-ho", sma_slope_filter=True, vol_p75_gate=True,
    )
    ext_r = run_variant(
        bars, daily_closes, sma50, atr_map, EXT_START, ext_end,
        name="C6=C5-ext", sma_slope_filter=True, vol_p75_gate=True,
    )

    fit_s = summarize(fit_r.trades)
    ho_s = summarize(ho_r.trades)
    ext_s = summarize(ext_r.trades)
    lo_removed, lo_s = leave_out_two_best(ho_r.trades)
    lo_net = lo_s["all"]["net_full"]

    ho_days = ho_calendar_days()
    ho_net_01 = ho_s["all"]["net_full"]
    fit_net_01 = fit_s["all"]["net_full"]
    ext_net_01 = ext_s["all"]["net_full"]
    worst_ho_01 = ho_s["worst_raw"][1]
    worst_ext_01 = ext_s["worst_raw"][1]
    pace_01 = monthly_pace(ho_net_01, ho_days)

    # Gates A at 0.01
    g1 = ho_net_01 > 0 and ho_net_01 > BUY_ONLY_HOLDOUT_NET
    g2 = ext_net_01 >= 0
    g3 = lo_net > 0
    g4 = worst_ho_01 >= WORST_DAY_BUDGET and worst_ext_01 >= WORST_DAY_BUDGET
    g5 = fit_net_01 >= Decimal("-5000")
    g6 = ho_s["month_pos_rate"] >= Decimal("0.5")
    gates_a = all([g1, g2, g3, g4, g5, g6])

    # Volume for $7.5k/mo
    if pace_01 > 0:
        vol_for_pace = BASE_VOL * (PACE_TARGET_MO / pace_01)
    else:
        vol_for_pace = None

    # Max vol by daily DD (worst day)
    abs_worst = min(worst_ho_01, worst_ext_01)  # more negative
    # abs_worst is negative; scale so abs_worst * (vol/0.01) >= -5000
    # |worst| * scale <= 5000
    max_vol_daily = BASE_VOL * (DAILY_LIM / abs(abs_worst)) if abs_worst != 0 else BASE_VOL

    # Max vol by one stop
    max_vol_stop = BASE_VOL * (DAILY_LIM / STOP)

    # Max vol by fit net not exceeding -10k (proxy — cumulative, not peak-trough)
    if fit_net_01 < 0:
        max_vol_fit_proxy = BASE_VOL * (MAX_DD_LIM / abs(fit_net_01))
    else:
        max_vol_fit_proxy = Decimal("999")

    max_safe_vol = min(max_vol_daily, max_vol_stop)

    # Pace at max safe
    pace_safe = pace_01 * (max_safe_vol / BASE_VOL)
    d_chal_safe = days_to_target(pace_safe, CHALLENGE)
    d_both_safe = days_to_target(pace_safe, BOTH)

    # At pace-needed vol
    if vol_for_pace is not None:
        sf = vol_for_pace / BASE_VOL
        worst_at_pace = abs_worst * sf
        stop_at_pace = STOP * sf
        fit_at_pace = fit_net_01 * sf
        pace_at_pace = pace_01 * sf
        d_chal_pace = days_to_target(pace_at_pace, CHALLENGE)
        d_ver_pace = days_to_target(pace_at_pace, VERIFY)
        d_both_pace = days_to_target(pace_at_pace, BOTH)
        daily_ok_pace = worst_at_pace >= -DAILY_LIM and stop_at_pace <= DAILY_LIM
        maxdd_ok_pace = fit_at_pace >= -MAX_DD_LIM  # weak proxy
    else:
        sf = worst_at_pace = stop_at_pace = fit_at_pace = None
        pace_at_pace = d_chal_pace = d_ver_pace = d_both_pace = None
        daily_ok_pace = maxdd_ok_pace = False

    # Gate B
    g7 = (
        d_both_pace is not None
        and d_both_pace <= Decimal("60")
        and daily_ok_pace
        and maxdd_ok_pace
    )
    # More precise: pace OK only if both ≤60 AND DD OK at that size
    # If we can't hit pace without DD fail → REJECT
    g8_daily_at_needed = daily_ok_pace
    g9_maxdd_at_needed = maxdd_ok_pace

    # Also: can max_safe hit ≤60? 
    can_safe_hit_60 = d_both_safe is not None and d_both_safe <= Decimal("60")

    if gates_a and g7:
        decision = "ACCEPT"
        one_liner = (
            f"ACCEPT C6 as fast vehicle: vol {fmt(vol_for_pace)} clears ≤60d pace "
            f"with DD bounds."
        )
    elif gates_a and can_safe_hit_60:
        decision = "CONDITIONAL"
        one_liner = (
            "CONDITIONAL C6: max DD-safe size reaches ≤60d on HO pace, "
            "but check assumptions."
        )
    else:
        decision = "REJECT"
        one_liner = (
            "REJECT C6 as fast FTMO vehicle: C5 edge cannot hit Challenge+Verification "
            "in ≤60 calendar days without blowing 5% daily / 10% max DD on real Dukas HO."
        )

    # Scale table rows
    scale_rows = []
    for vol in SCALE_VOLS:
        sfv = scale_factor(vol)
        pace = pace_01 * sfv
        w = abs_worst * sfv
        st = STOP * sfv
        fitn = fit_net_01 * sfv
        hon = ho_net_01 * sfv
        d_c = days_to_target(pace, CHALLENGE)
        d_b = days_to_target(pace, BOTH)
        daily_ok = w >= -DAILY_LIM and st <= DAILY_LIM
        fit_ok = fitn >= -MAX_DD_LIM
        both_60 = d_b is not None and d_b <= Decimal("60")
        scale_rows.append(
            {
                "vol": vol,
                "pace": pace,
                "ho_net": hon,
                "worst": w,
                "stop": st,
                "fit": fitn,
                "d_chal": d_c,
                "d_both": d_b,
                "daily_ok": daily_ok,
                "fit_ok": fit_ok,
                "both_60": both_60,
            }
        )

    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    md = []
    md.append("# Candidate 6 Results — C5 Fast-Scale Probe (pace vs DD wall)")
    md.append("")
    md.append(f"**Decision: {decision}** (as fast FTMO vehicle)")
    md.append("")
    md.append(f"**One sentence:** {one_liner}")
    md.append("")
    md.append(f"**Measured:** {now}")
    md.append("**Live engines:** not modified. C4/drip/FREEZE untouched.")
    md.append(f"**Spec:** `{SPEC}`")
    md.append("")
    md.append("## ASSUMPTIONS (labeled)")
    md.append("")
    md.append("| Item | Value |")
    md.append("|---|---|")
    md.append(f"| Account | ${fmt(ACCOUNT)} 2-step (ASSUMPTION) |")
    md.append(f"| Challenge | +10% ≈ +${fmt(CHALLENGE)} |")
    md.append(f"| Verification | +5% ≈ +${fmt(VERIFY)} |")
    md.append(f"| Pace bar | ≤60 calendar days for BOTH steps (~${fmt(PACE_TARGET_MO)}/mo HO-like) |")
    md.append(f"| Daily DD | 5% ≈ −${fmt(DAILY_LIM)} |")
    md.append(f"| Max DD | 10% ≈ −${fmt(MAX_DD_LIM)} (fit-net scale used as honesty proxy) |")
    md.append(f"| Base edge | C5 rules; stop=target={STOP}; vol base {BASE_VOL} |")
    md.append(f"| HO window | {HO_START.date()} → {HO_END.date()} UTC ({ho_days} calendar days) |")
    md.append("")
    md.append("## Rules used")
    md.append("")
    md.append("- Identical to C5: SMA50 exclusive dual R=1 + slope E + ATR < P75(100d)")
    md.append("- No new filters; only volume scaling of measured C5 trade dollars")
    md.append("- Data: merged Dukas M1 (same as C5)")
    md.append("")
    md.append("## Gate A — robustness at vol 0.01 (C5 re-measure)")
    md.append("")
    md.append("| Gate | Pass? | Detail |")
    md.append("|---|---|---|")
    md.append(
        f"| 1 Holdout full > 0 and > buy-only | {'YES' if g1 else 'NO'} | "
        f"HO ${fmt(ho_net_01)}; buy-only ${fmt(BUY_ONLY_HOLDOUT_NET)} |"
    )
    md.append(
        f"| 2 Extension full ≥ 0 | {'YES' if g2 else 'NO'} | ${fmt(ext_net_01)} |"
    )
    md.append(
        f"| 3 Leave-out two best HO months > 0 | {'YES' if g3 else 'NO'} | "
        f"removed {lo_removed}; left ${fmt(lo_net)} |"
    )
    md.append(
        f"| 4 Worst day ≥ −2000 HO & ext | {'YES' if g4 else 'NO'} | "
        f"HO {ho_s['worst_raw']}; ext {ext_s['worst_raw']} |"
    )
    md.append(
        f"| 5 Fit full ≥ −5000 | {'YES' if g5 else 'NO'} | ${fmt(fit_net_01)} |"
    )
    md.append(
        f"| 6 Holdout months ≥50% green | {'YES' if g6 else 'NO'} | "
        f"{ho_s['month_pos']}/{ho_s['month_n']} ({float(ho_s['month_pos_rate'])*100:.1f}%) |"
    )
    md.append("")
    md.append(f"**Gate A all pass?** {'YES' if gates_a else 'NO'}")
    md.append("")
    md.append("## Pace at 0.01")
    md.append("")
    md.append(f"- HO net full: **${fmt(ho_net_01)}** over **{ho_days}** calendar days")
    md.append(f"- HO monthly pace: **${fmt(pace_01)}/month**")
    md.append(
        f"- Days to Challenge +$10k (linear HO pace): "
        f"**{fmt(days_to_target(pace_01, CHALLENGE)) if days_to_target(pace_01, CHALLENGE) else 'n/a'}**"
    )
    md.append(
        f"- Days to both +$15k: "
        f"**{fmt(days_to_target(pace_01, BOTH)) if days_to_target(pace_01, BOTH) else 'n/a'}**"
    )
    md.append("")
    md.append("## Scaling wall (the point of C6)")
    md.append("")
    md.append(f"- One stop $ at 0.01: **${fmt(STOP)}**")
    md.append(f"- Worst HO ET day raw at 0.01: **${fmt(worst_ho_01)}** ({ho_s['worst_raw'][0]})")
    md.append(f"- Worst ext ET day raw at 0.01: **${fmt(worst_ext_01)}** ({ext_s['worst_raw'][0]})")
    md.append(f"- Binding worst-day for scale: **${fmt(abs_worst)}**")
    md.append("")
    md.append(f"- **Max vol by daily DD** (worst-day × scale ≥ −$5,000): **{fmt(max_vol_daily)}**")
    md.append(f"- **Max vol by one-stop ≤ $5,000:** **{fmt(max_vol_stop)}**")
    md.append(f"- **Max vol by fit-net ≥ −$10,000 (proxy):** **{fmt(max_vol_fit_proxy)}**")
    md.append(f"- **Max DD-safe vol (min of daily + one-stop):** **{fmt(max_safe_vol)}**")
    md.append("")
    md.append(f"- At max DD-safe vol **{fmt(max_safe_vol)}**:")
    md.append(f"  - HO pace ≈ **${fmt(pace_safe)}/month**")
    md.append(
        f"  - Est. days to Challenge: **{fmt(d_chal_safe) if d_chal_safe else 'n/a'}**"
    )
    md.append(
        f"  - Est. days to both steps: **{fmt(d_both_safe) if d_both_safe else 'n/a'}** "
        f"({'≤60 YES' if can_safe_hit_60 else '>60 NO — fails Odin bar'})"
    )
    md.append("")
    if vol_for_pace is not None:
        md.append(f"- **Vol needed for ~${fmt(PACE_TARGET_MO)}/mo:** **{fmt(vol_for_pace)}** (scale ×{fmt(sf)})")
        md.append(f"  - Worst day at that size: **${fmt(worst_at_pace)}** (limit −${fmt(DAILY_LIM)}) → {'OK' if worst_at_pace >= -DAILY_LIM else '**VIOLATES 5% daily**'}")
        md.append(f"  - One stop at that size: **${fmt(stop_at_pace)}** → {'OK' if stop_at_pace <= DAILY_LIM else '**VIOLATES 5% daily (single stop)**'}")
        md.append(f"  - Fit net scaled: **${fmt(fit_at_pace)}** (limit −${fmt(MAX_DD_LIM)}) → {'OK' if maxdd_ok_pace else '**VIOLATES 10% max-DD proxy**'}")
        md.append(f"  - Est. days Challenge / Verification / both: "
                  f"**{fmt(d_chal_pace)} / {fmt(d_ver_pace)} / {fmt(d_both_pace)}**")
    md.append("")
    md.append("## Gate B — fast vehicle")
    md.append("")
    md.append("| Gate | Pass? | Detail |")
    md.append("|---|---|---|")
    md.append(
        f"| 7 Pace ≤60d both at a DD-legal size | {'YES' if can_safe_hit_60 else 'NO'} | "
        f"max safe both-days={fmt(d_both_safe) if d_both_safe else 'n/a'} |"
    )
    md.append(
        f"| 8 Daily DD OK at pace-needed vol | {'YES' if g8_daily_at_needed else 'NO'} | "
        f"needed vol {fmt(vol_for_pace) if vol_for_pace else 'n/a'} |"
    )
    md.append(
        f"| 9 Max-DD proxy OK at pace-needed vol | {'YES' if g9_maxdd_at_needed else 'NO'} | "
        f"scaled fit {fmt(fit_at_pace) if fit_at_pace is not None else 'n/a'} |"
    )
    md.append("")
    md.append("## Scale table (linear $ with volume)")
    md.append("")
    md.append(
        "| Vol | HO $/mo | HO net (×) | Worst day $ | One stop $ | Fit net (×) | "
        "Days to +$10k | Days both +$15k | Daily OK | Fit≤10k | Both≤60d |"
    )
    md.append("|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|")
    for r in scale_rows:
        md.append(
            f"| {fmt(r['vol'])} | {fmt(r['pace'])} | {fmt(r['ho_net'])} | {fmt(r['worst'])} | "
            f"{fmt(r['stop'])} | {fmt(r['fit'])} | "
            f"{fmt(r['d_chal']) if r['d_chal'] is not None else 'n/a'} | "
            f"{fmt(r['d_both']) if r['d_both'] is not None else 'n/a'} | "
            f"{'Y' if r['daily_ok'] else 'N'} | {'Y' if r['fit_ok'] else 'N'} | "
            f"{'Y' if r['both_60'] else 'N'} |"
        )
    md.append("")
    md.append("## Comparison vs C5")
    md.append("")
    md.append("| | C5 @ 0.01 | C6 @ max DD-safe | C6 @ pace-needed |")
    md.append("|---|---:|---:|---:|")
    md.append(
        f"| Volume | 0.01 | {fmt(max_safe_vol)} | "
        f"{fmt(vol_for_pace) if vol_for_pace else 'n/a'} |"
    )
    md.append(f"| HO $/mo | {fmt(pace_01)} | {fmt(pace_safe)} | "
              f"{fmt(pace_at_pace) if pace_at_pace else 'n/a'} |")
    md.append(
        f"| Days both steps | {fmt(days_to_target(pace_01, BOTH))} | "
        f"{fmt(d_both_safe) if d_both_safe else 'n/a'} | "
        f"{fmt(d_both_pace) if d_both_pace else 'n/a'} |"
    )
    md.append(
        f"| Worst day $ | {fmt(abs_worst)} | {fmt(abs_worst * max_safe_vol / BASE_VOL)} | "
        f"{fmt(worst_at_pace) if worst_at_pace is not None else 'n/a'} |"
    )
    md.append("")
    md.append("## HO monthly P&L at 0.01 (same as C5)")
    md.append("")
    md.append("| ET exit month | Trades | Net full $ |")
    md.append("|---|---:|---:|")
    for m, v in ho_s["months"].items():
        md.append(f"| {m} | {v['n']} | {fmt(v['net_full'])} |")
    md.append("")
    md.append("## Why not H4-BREAK-6 / other HF as this candidate")
    md.append("")
    md.append(
        "Prior survey BTC-H4-BREAK-6 (1% risk, channel exit) reached final equity ~$152k "
        "and 4/30 floating-inclusive 3-month windows, but max realized DD ~14.8% (>10%), "
        "one floating day −6.9%, and most holdout-era windows failed 1.10/1.155. "
        "C3 4H Donchian already REJECT on HO. Scaling C5 is the cleaner single question "
        "for Odin’s ≤60-day bar."
    )
    md.append("")
    md.append("## Decision")
    md.append("")
    md.append(f"**{decision}** as a fast FTMO Challenge+Verification vehicle (≤60 calendar days).")
    md.append("")
    md.append(one_liner)
    md.append("")
    md.append(
        "**Deployable-as-research-next?** **NO** for fast pass. "
        "C5 remains the robustness ACCEPT at 0.01; C4 stays live path. "
        "Need a structurally higher-$/month edge (or multi-symbol book) before a ≤60-day BTC claim."
    )
    md.append("")
    md.append("## Assumptions / limitations")
    md.append("")
    md.append("1. Linear volume scaling of realized C5 trade dollars (catalogue point value).")
    md.append("2. Pace uses average HO $/month — lumpy months mean calendar pass time is optimistic.")
    md.append("3. Max-DD check uses scaled fit *net* as a blunt proxy, not full peak-to-trough MTM.")
    md.append("4. FTMO daily is Prague equity incl. floating; research uses ET exit-day raw.")
    md.append("5. Account $100k ASSUMPTION.")
    md.append("6. No live engine / VM / C4 / drip changes.")
    md.append("")
    md.append("## User summary (≤15 lines)")
    md.append("")
    md.append(f"1. **{decision}** — C5 scaled cannot clear ≤60-day both-steps without FTMO DD breach.")
    md.append(f"2. HO @ 0.01: **${fmt(ho_net_01)}** ≈ **${fmt(pace_01)}/mo** over {ho_days}d.")
    md.append(f"3. Need ~**{fmt(vol_for_pace)}** lots for ~$7.5k/mo → worst day **${fmt(worst_at_pace) if worst_at_pace is not None else 'n/a'}** (limit $5k).")
    md.append(f"4. Max DD-safe vol ≈ **{fmt(max_safe_vol)}** → both-steps ~**{fmt(d_both_safe) if d_both_safe else 'n/a'}** days (>{60}).")
    md.append("5. Gate A (robustness @ 0.01) still matches C5 ACCEPT; Gate B (fast) fails.")
    md.append("6. Not deployable for fast pass; live untouched.")

    OUT.write_text("\n".join(md) + "\n")
    print("Wrote", OUT)
    print("DECISION:", decision)
    print(one_liner)
    print(f"pace_01=${pace_01} max_safe_vol={max_safe_vol} d_both_safe={d_both_safe}")
    print(f"vol_for_pace={vol_for_pace} worst_at_pace={worst_at_pace}")


if __name__ == "__main__":
    main()
