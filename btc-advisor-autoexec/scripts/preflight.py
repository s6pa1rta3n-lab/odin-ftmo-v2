#!/usr/bin/env python3
"""Read-only preflight for Trading Ops. Places nothing, modifies nothing.

Prints, for every allowed symbol (BTCUSD, ETHUSD, SOLUSD by default): the
broker's symbol name and description, the specification, live quote and
spread, commission source and value, lot math for a sample stop distance and
the second-position margin estimate; plus every account-wide guard state
(halt latch, shared daily cap, position count, kill switch, orders flag).

    python3 scripts/preflight.py                 # sample stop distance 500 price units
    python3 scripts/preflight.py --stop-distance 350
    python3 scripts/preflight.py --json          # machine-readable

The MetaAPI token is read from AUTOEXEC_TOKEN or AUTOEXEC_TOKEN_SOURCE and is
never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from autoexec import second_position as second  # noqa: E402
from autoexec.broker import MetaApiRest  # noqa: E402
from autoexec.config import Config, load_token  # noqa: E402
from autoexec.engine import Executor  # noqa: E402
from autoexec.guards import parse_quote  # noqa: E402
from autoexec.jsonlog import JsonLogger, redact  # noqa: E402
from autoexec.sizing import D, parse_spec, size_position  # noqa: E402
from autoexec.state import HaltLatch, StateStore  # noqa: E402


class _ReadOnly:
    """Wraps the REST client so a programming error can never reach /trade."""

    def __init__(self, inner: MetaApiRest) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        if name == "trade":
            raise RuntimeError("preflight is read-only; trade() is not available")
        return getattr(self._inner, name)


def main() -> int:
    ap = argparse.ArgumentParser(description="read-only preflight; never places orders")
    ap.add_argument("--stop-distance", type=float, default=500.0, help="sample stop distance in price units for the lot math")
    ap.add_argument("--json", action="store_true", help="print one JSON document instead of text")
    args = ap.parse_args()

    cfg = Config.from_env()
    token = load_token(cfg)
    broker = _ReadOnly(MetaApiRest(token, cfg.account_id, host=cfg.client_host, timeout=cfg.http_timeout_sec))
    logger = JsonLogger(None, stdout=False, token=token)
    executor = Executor(cfg, broker, logger, state=StateStore(os.path.join(cfg.state_dir, "state.json")), halt=HaltLatch(cfg.halt_file))

    status = executor.status()
    out = {"ok": status.get("ok"), "config": cfg.public_dict()}
    if not status.get("ok"):
        out.update({"code": status.get("code"), "reason": status.get("reason")})
        print(json.dumps(redact(out), indent=2, default=str))
        return 1

    reads = status["reads"]
    guards = status["guards"]
    out["guards"] = guards

    def sample_for(symbol: str) -> dict:
        """Lot math and margin estimate for one symbol at the sample stop distance. Never raises."""

        sample: dict = {"symbol": symbol, "stop_distance": args.stop_distance}
        spec_raw = reads["specs"].get(symbol)
        quote_raw = reads["quotes"].get(symbol)
        try:
            if spec_raw is None or quote_raw is None:
                raise RuntimeError("no spec/quote read for this symbol")
            sample["broker_symbol"] = spec_raw.get("symbol")
            sample["description"] = spec_raw.get("description")
            spec = parse_spec(spec_raw)
            quote = parse_quote(quote_raw)
            comm = executor._commission_for(symbol, spec_raw, reads.get("deals_lookback"))
            sample["commission"] = comm.as_dict()
            if comm.per_lot_roundtrip is None:
                sample["error"] = comm.note
                return sample
            sizing = size_position(
                stop_distance=D(args.stop_distance),
                spread=quote.spread,
                spec=spec,
                commission_per_lot_roundtrip=comm.per_lot_roundtrip,
                max_risk_usd=D(cfg.max_risk_usd),
            )
            sample["sizing"] = sizing.as_dict()
            lots = sizing.lots if sizing.lots > 0 else spec.min_volume
            margin_override = cfg.margin_per_lot_for(symbol)
            leverage = cfg.symbol_leverage_for(symbol)
            margin = second.estimate_margin(
                lots=lots,
                fill_price=quote.ask,
                spec_raw=spec_raw,
                spec=spec,
                account=reads["account"],
                margin_per_lot_override=D(margin_override) if margin_override else None,
                symbol_leverage=D(leverage) if leverage else None,
                use_account_leverage=cfg.margin_use_account_leverage,
            )
            sample["margin_estimate_for_second_position"] = margin.as_dict()
        except Exception as exc:  # keep the preflight informative even when one piece fails
            sample["error"] = f"{type(exc).__name__}: {exc}"
        return sample

    out["sample"] = sample_for(cfg.symbol)
    out["samples"] = {sym: sample_for(sym) for sym in cfg.symbols}
    out["spec_raw_by_symbol"] = reads.get("specs")

    if args.json:
        print(json.dumps(redact(out), indent=2, default=str))
        return 0

    acct = reads["account"]
    print("== BTC Advisor autoexec preflight (READ-ONLY) ==")
    print(f"host            : {cfg.client_host}")
    print(f"account id      : {cfg.account_id}")
    print(f"login           : {acct.get('login')} (expected {cfg.expected_login}) ok={guards['login_ok']}")
    print(f"equity/balance  : {acct.get('equity')} / {acct.get('balance')}  margin={acct.get('margin')} freeMargin={acct.get('freeMargin')} marginLevel={acct.get('marginLevel')} leverage={acct.get('leverage')}")
    print(f"orders_enabled  : {cfg.orders_enabled}   kill_active: {cfg.kill_active}   armed: {executor.armed}")
    print(f"halt            : threshold={cfg.equity_halt_usd} at_or_below={guards.get('equity_at_or_below_halt')} latched={guards['halt_latched']} file={cfg.halt_file}")
    print(f"daily cap       : cap={cfg.daily_loss_cap_usd} day={guards['trading_day']} ({cfg.day_tz}) pnl={guards.get('daily_pnl')} latched_today={guards['daily_cap_latched_today']}")
    print(f"positions       : total={guards['total_open']} (max {cfg.max_positions_total}) auto={guards['auto_open']} manual={guards['manual_open']} other={guards['other_magic_open']}")
    for kind in ("auto", "manual", "other"):
        for p in guards["book"][kind]:
            print(f"   [{kind}] {p}")
    print(f"cooldown        : {guards['post_place_cooldown']}")
    print(f"symbols         : allowed={list(cfg.symbols)} default={cfg.symbol} second_position_scope={cfg.second_position_scope}")
    print(f"sample stop dist: {args.stop_distance} (price units, same for every symbol)")
    for sym in cfg.symbols:
        view = (guards.get("per_symbol") or {}).get(sym, {})
        smp = out["samples"][sym]
        q = view.get("quote") or {}
        print(f"-- {sym} --")
        print(f"   broker symbol: {view.get('broker_symbol')}  description: {view.get('description')}  path: {view.get('path')}")
        print(f"   quote        : bid={q.get('bid')} ask={q.get('ask')} spread={q.get('spread')}")
        print(f"   spec         : {json.dumps(view.get('spec'), default=str)}")
        print(f"   commission   : {json.dumps(view.get('commission'), default=str)}")
        print(f"   margin calib : {json.dumps(view.get('margin_calibration'), default=str)}")
        if "sizing" in smp:
            sz = smp["sizing"]
            print(f"   per-lot loss = stop {sz['stop_loss_per_lot']} + spread {sz['spread_cost_per_lot']} + commission {sz['commission_per_lot_roundtrip']} = {sz['per_lot_loss']}")
            print(f"   lots = floor({cfg.max_risk_usd} / {sz['per_lot_loss']}, step {sz['volume_step']}) = {sz['lots']}  risk=${sz['risk_usd']}  ok={sz['ok']} ({sz['reason']})")
            m = smp["margin_estimate_for_second_position"]
            level = m["projected_level_pct"]
            level_txt = f"{level:.1f}%" if isinstance(level, (int, float)) else "n/a"
            print(f"   margin est.  : new={m['new_margin_usd']} method={m['method']} projected_level={level_txt} (min {cfg.min_margin_level_pct}%)")
        else:
            print(f"   sizing       : SKIP -> {smp.get('error')}")
    print("No orders were placed. No positions were modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
