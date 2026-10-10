#!/usr/bin/env python3
"""Read-only preflight for Trading Ops. Places nothing, modifies nothing.

Account-wide guard states (halt latch, shared daily cap, position count, cooldown,
kill, orders flag), then for every requested symbol (Odin 2026-10-10 19:07 ET #7):
broker name/description/path, spec (+ missing fields), live bid/ask/spread in price
and $ per lot, commission model/source/value per lot round trip, sample lot math for
the given stop distance, margin per lot and method, the margin cap, and PASS/FAIL
with the reason.

    python3 scripts/preflight.py                                   # default symbol (BTCUSD)
    python3 scripts/preflight.py --symbols UNIUSD,US100.cash,XAUUSD --stop-distance 25
    python3 scripts/preflight.py --symbols XAUUSD --stop-pct 0.5    # stop as % of price
    python3 scripts/preflight.py --json                             # machine-readable

The MetaAPI token is read from AUTOEXEC_TOKEN or AUTOEXEC_TOKEN_SOURCE and is
never printed. The broker object is wrapped so trade() cannot be reached.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from autoexec.broker import MetaApiRest  # noqa: E402
from autoexec.config import Config, load_token  # noqa: E402
from autoexec.engine import Executor  # noqa: E402
from autoexec.jsonlog import JsonLogger, redact  # noqa: E402
from autoexec.state import HaltLatch, StateStore  # noqa: E402


class _ReadOnly:
    """Wraps the REST client so a programming error can never reach /trade."""

    def __init__(self, inner: MetaApiRest) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        if name == "trade":
            raise RuntimeError("preflight is read-only; trade() is not available")
        return getattr(self._inner, name)


def _fmt(x) -> str:
    return json.dumps(x, default=str)


def print_symbol(view: dict, cfg: Config) -> None:
    sym = view.get("symbol")
    print(f"-- {sym} -- {'PASS' if view.get('ok') else 'FAIL'}: {view.get('reason')}")
    if view.get("code") in ("SYMBOL_NOT_ALLOWED", "SYMBOL_NOT_LISTED", "SPEC_UNAVAILABLE", "SPEC_INCOMPLETE", "READ_FAILED"):
        print(f"   code         : {view.get('code')}")
        return
    print(f"   broker symbol: {view.get('broker_symbol')}  description: {view.get('description')}  path: {view.get('path')}  currencies: {_fmt(view.get('currencies'))}")
    q = view.get("quote") or {}
    print(f"   quote        : bid={q.get('bid')} ask={q.get('ask')} spread={q.get('spread')} spread_cost_per_lot=${q.get('spread_cost_per_lot_usd')}")
    print(f"   spec         : {_fmt(view.get('spec'))}  missing={view.get('spec_missing')}")
    ac = view.get("asset_class") or {}
    print(f"   asset class  : {ac.get('value')} (via {ac.get('source')})  commission model: {ac.get('commission_model')}")
    c = view.get("commission") or {}
    print(f"   commission   : per_lot_roundtrip={c.get('per_lot_roundtrip')} source={c.get('source')} model={c.get('model')} pct_per_side={c.get('pct_per_side')} notional/lot={c.get('notional_per_lot')} deals_rt={c.get('deals_round_trips')}")
    print(f"                  {c.get('note')}")
    m = view.get("margin") or {}
    print(f"   margin/lot   : {m.get('per_lot_usd')} method={m.get('method')} calibration={_fmt(view.get('margin_calibration'))}")
    if m.get("detail", {}).get("tried"):
        print(f"                  tried: {m['detail']['tried']}")
    smp = view.get("sample") or {}
    print(f"   sample stop  : {smp.get('stop_distance')} price units ({smp.get('stop_pct_of_price')!s:.6}% of price)")
    sz = smp.get("sizing")
    if sz:
        print(f"   per-lot loss = stop {sz['stop_loss_per_lot']} + spread {sz['spread_cost_per_lot']} + commission {sz['commission_per_lot_roundtrip']} = {sz['per_lot_loss']}")
        print(f"   lots = floor({cfg.max_risk_usd} / {sz['per_lot_loss']}, step {sz['volume_step']}) = {sz['lots']}  risk=${sz['risk_usd']}  ok={sz['ok']} ({sz['reason']})")
    cap = smp.get("margin_cap")
    if cap:
        lvl = cap.get("projected_level_pct")
        lvl_txt = f"{lvl:.1f}%" if isinstance(lvl, (int, float)) else "n/a"
        print(f"   margin cap   : lots {cap['lots_before']} -> {cap['lots_after']} (max {cap['max_lots']}), projected level {lvl_txt} (min {cap['min_level_pct']}%) {cap['reason']}")
    if view.get("ok"):
        print(f"   RESULT       : lots={smp.get('lots')} risk=${smp.get('risk_usd')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="read-only preflight; never places orders")
    ap.add_argument("--symbols", help="comma-separated symbols (default: the configured default symbol)")
    ap.add_argument("--stop-distance", type=float, help="sample stop distance in price units (same for every symbol)")
    ap.add_argument("--stop-pct", type=float, help="sample stop as %% of price (default AUTOEXEC_SAMPLE_STOP_PCT)")
    ap.add_argument("--side", default="BUY", choices=["BUY", "SELL", "buy", "sell"])
    ap.add_argument("--json", action="store_true", help="print one JSON document instead of text")
    args = ap.parse_args()

    cfg = Config.from_env()
    if args.stop_pct:
        cfg.sample_stop_pct = args.stop_pct
    token = load_token(cfg)
    broker = _ReadOnly(MetaApiRest(token, cfg.account_id, host=cfg.client_host, timeout=cfg.http_timeout_sec))
    logger = JsonLogger(None, stdout=False, token=token)
    executor = Executor(cfg, broker, logger, state=StateStore(os.path.join(cfg.state_dir, "state.json")), halt=HaltLatch(cfg.halt_file))

    symbols = [x.strip() for x in (args.symbols or "").split(",") if x.strip()] or [cfg.symbol]
    stop = Decimal(str(args.stop_distance)) if args.stop_distance else None

    status = executor.status()
    out = {"ok": status.get("ok"), "config": cfg.public_dict()}
    if not status.get("ok"):
        out.update({"code": status.get("code"), "reason": status.get("reason")})
        print(json.dumps(redact(out), indent=2, default=str))
        return 1
    reads = status["reads"]
    guards = status["guards"]
    out["guards"] = {k: v for k, v in guards.items() if k != "per_symbol"}
    views = [executor.symbol_info(sym, stop_distance=stop, side=args.side.upper()) for sym in symbols]
    out["symbols"] = views
    out["all_pass"] = all(v.get("ok") for v in views)

    if args.json:
        print(json.dumps(redact(out), indent=2, default=str))
        return 0 if out["all_pass"] else 2

    acct = reads["account"]
    print("== autoexec preflight (READ-ONLY) ==")
    print(f"host            : {cfg.client_host}")
    print(f"account id      : {cfg.account_id}")
    print(f"login           : {acct.get('login')} (expected {cfg.expected_login}) ok={guards['login_ok']}")
    print(f"equity/balance  : {acct.get('equity')} / {acct.get('balance')}  margin={acct.get('margin')} freeMargin={acct.get('freeMargin')} marginLevel={acct.get('marginLevel')} leverage={acct.get('leverage')} currency={acct.get('currency')}")
    print(f"orders_enabled  : {cfg.orders_enabled}   kill_active: {cfg.kill_active}   armed: {executor.armed}")
    print(f"halt            : threshold={cfg.equity_halt_usd} at_or_below={guards.get('equity_at_or_below_halt')} latched={guards['halt_latched']} file={cfg.halt_file}")
    print(f"daily cap       : cap={cfg.daily_loss_cap_usd} day={guards['trading_day']} ({cfg.day_tz}) pnl={guards.get('daily_pnl')} latched_today={guards['daily_cap_latched_today']}")
    print(f"positions       : total={guards['total_open']} (max {cfg.max_positions_total}, scope={cfg.second_position_scope}) by_symbol={guards.get('open_by_symbol')} auto={guards['auto_open']} manual={guards['manual_open']} other={guards['other_magic_open']}")
    for kind in ("auto", "manual", "other"):
        for p in guards["book"][kind]:
            print(f"   [{kind}] {p}")
    print(f"cooldown        : {guards['post_place_cooldown']}")
    print(f"symbol lists    : allowlist={list(cfg.symbols) or 'ALL broker symbols'} denylist={list(cfg.symbols_deny)} default={cfg.symbol}")
    print(f"margin cap      : min level {cfg.min_margin_level_pct}%  broker calc={cfg.margin_calc_broker}")
    print(f"commission      : pct model {cfg.commission_pct_per_side}%/side x2 (crypto default); flat/pct/model overrides via AUTOEXEC_COMMISSION_*_<SYMBOL|CLASS>")
    print(f"sample stop     : {args.stop_distance if args.stop_distance else str(cfg.sample_stop_pct) + '% of price'} side={args.side.upper()}")
    for v in views:
        print_symbol(v, cfg)
    print(f"== {'ALL PASS' if out['all_pass'] else 'SOME FAIL'} == No orders were placed. No positions were modified.")
    return 0 if out["all_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
