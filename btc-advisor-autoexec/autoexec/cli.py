"""CLI equivalent of the HTTP endpoint.

    python3 -m autoexec serve
    python3 -m autoexec setup --side BUY --entry-type MARKET --stop 84000 --target 88000 [--dry-run]
    python3 -m autoexec tighten --stop 85500 [--position-id ID] [--dry-run]
    python3 -m autoexec status
    python3 -m autoexec kill            # create the kill file (blocks every mutation)
    python3 -m autoexec unkill          # remove the kill file
    python3 -m autoexec halt-clear --yes  # manual re-enable after an equity halt

Every command prints one JSON document to stdout. ``setup`` / ``tighten`` exit
0 when accepted (dry-run or live), 2 when rejected.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .broker import MetaApiRest
from .config import Config, load_token
from .engine import Executor
from .jsonlog import JsonLogger, redact
from .state import HaltLatch, StateStore


def build_executor(cfg: Optional[Config] = None, *, stdout_log: bool = False) -> Executor:
    cfg = cfg or Config.from_env()
    token = load_token(cfg)
    broker = MetaApiRest(token, cfg.account_id, host=cfg.client_host, timeout=cfg.http_timeout_sec, trade_timeout=cfg.trade_timeout_sec)
    logger = JsonLogger(cfg.log_path, stdout=stdout_log, token=token)
    return Executor(cfg, broker, logger, state=StateStore(os.path.join(cfg.state_dir, "state.json")), halt=HaltLatch(cfg.halt_file))


def _print(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(redact(obj), indent=2, default=str) + "\n")
    sys.stdout.flush()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="autoexec", description="BTC Advisor auto-execution (orders disabled by default)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="run the local HTTP endpoint")

    p_setup = sub.add_parser("setup", help="submit an entry setup")
    p_setup.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"])
    p_setup.add_argument("--entry-type", default="MARKET")
    p_setup.add_argument("--stop", required=True)
    p_setup.add_argument("--target", required=True)
    p_setup.add_argument("--request-id")
    p_setup.add_argument("--dry-run", action="store_true", help="force dry-run even if orders are enabled")

    p_t = sub.add_parser("tighten", help="tighten the auto position's stop")
    p_t.add_argument("--stop", required=True)
    p_t.add_argument("--position-id")
    p_t.add_argument("--request-id")
    p_t.add_argument("--dry-run", action="store_true")

    sub.add_parser("status", help="read-only guard states")
    sub.add_parser("kill", help="create the kill file")
    sub.add_parser("unkill", help="remove the kill file")
    p_hc = sub.add_parser("halt-clear", help="remove the equity HALT latch (manual re-enable)")
    p_hc.add_argument("--yes", action="store_true", help="required; confirms Odin/Trading Ops approved the re-enable")

    args = parser.parse_args(argv)
    cfg = Config.from_env()

    if args.cmd == "kill":
        Path(cfg.kill_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg.kill_file).write_text("kill\n", encoding="utf-8")
        _print({"ok": True, "kill_file": cfg.kill_file, "kill_active": True})
        return 0
    if args.cmd == "unkill":
        existed = Path(cfg.kill_file).exists()
        if existed:
            Path(cfg.kill_file).unlink()
        _print({"ok": True, "kill_file": cfg.kill_file, "removed": existed, "kill_active": cfg.kill_active})
        return 0
    if args.cmd == "halt-clear":
        if not args.yes:
            _print({"ok": False, "reason": "pass --yes to confirm the manual re-enable", "halt_file": cfg.halt_file})
            return 2
        latch = HaltLatch(cfg.halt_file)
        record = latch.read()
        removed = latch.clear()
        logger = JsonLogger(cfg.log_path, stdout=False)
        logger.emit("halt_cleared_manually", halt_file=cfg.halt_file, removed=removed, previous=record)
        _print({"ok": True, "halt_file": cfg.halt_file, "removed": removed, "previous": record})
        return 0

    if args.cmd == "serve":
        from .server import serve_forever

        executor = build_executor(cfg, stdout_log=True)
        serve_forever(executor)
        return 0

    executor = build_executor(cfg, stdout_log=False)
    if args.cmd == "status":
        st = executor.status()
        st.pop("reads", None)
        _print(st)
        return 0 if st.get("ok") else 1
    if args.cmd == "setup":
        payload = {
            "side": args.side.upper(),
            "entry_type": args.entry_type,
            "stop": args.stop,
            "target": args.target,
        }
        if args.request_id:
            payload["request_id"] = args.request_id
        decision = executor.decide_entry(payload, force_dry_run=args.dry_run)
        _print(decision)
        return 0 if decision.get("accepted") else 2
    if args.cmd == "tighten":
        payload: Dict[str, Any] = {"stop": args.stop}
        if args.position_id:
            payload["position_id"] = args.position_id
        if args.request_id:
            payload["request_id"] = args.request_id
        decision = executor.tighten_stop(payload, force_dry_run=args.dry_run)
        _print(decision)
        return 0 if decision.get("accepted") else 2
    parser.error("unknown command")
    return 2
