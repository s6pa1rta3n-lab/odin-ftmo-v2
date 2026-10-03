"""Run the MetaAPI hub process.

Examples (neither one is started by this repository's service installers)::

    python -m metaapi_hub --mode shadow --orders deny
    python -m metaapi_hub --mode live --orders deny --config config_us100.json

Live order placement is refused unless all three are present: ``--mode live``,
``--orders live``, ``--enable-live-orders``, and
``ODIN_METAAPI_HUB_ORDERS=live``. This pull request does not turn those on.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys

from metaapi_hub.broker import InMemoryBroker, MetaApiBroker
from metaapi_hub.owner import SyncOwner
from metaapi_hub.server import HubServer

log = logging.getLogger("odin.metaapi_hub")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Odin shared MetaAPI hub (single synchronization owner)")
    parser.add_argument("--mode", choices=["shadow", "live"], default="shadow")
    parser.add_argument("--orders", choices=["deny", "dry_run", "live"], default="deny")
    parser.add_argument(
        "--enable-live-orders",
        action="store_true",
        help="Required acknowledgement before --orders live is accepted. Do not pass this until Odin approves cutover.",
    )
    parser.add_argument("--socket", default=os.environ.get("ODIN_METAAPI_HUB_SOCKET", "/tmp/odin-metaapi-hub.sock"))
    parser.add_argument("--config", default="", help="JSON config with metaapi.token. Not read in shadow mode.")
    parser.add_argument("--account-id", default="")
    parser.add_argument("--cache-ttl", type=float, default=5.0)
    parser.add_argument("--rpc-timeout", type=float, default=20.0)
    parser.add_argument(
        "--sync-timeout",
        type=float,
        default=60.0,
        help="Budget for wait_synchronized on connect/reconnect (default 60s).",
    )
    parser.add_argument(
        "--close-timeout",
        type=float,
        default=10.0,
        help="Upper bound on closing an SDK connection before reconnecting (default 10s).",
    )
    parser.add_argument(
        "--backoff-base",
        type=float,
        default=0.5,
        help="First retry delay; doubles per attempt (default 0.5s).",
    )
    parser.add_argument(
        "--backoff-max",
        type=float,
        default=30.0,
        help="Cap on a single retry delay before jitter (default 30s).",
    )
    parser.add_argument(
        "--backoff-jitter",
        type=float,
        default=0.25,
        help="Random extra delay as a fraction of the capped delay (default 0.25).",
    )
    parser.add_argument(
        "--read-attempts",
        type=int,
        default=3,
        help="Attempts for idempotent reads on TIMEOUT/429/504 (default 3). Orders are never retried.",
    )
    parser.add_argument(
        "--read-concurrency",
        type=int,
        default=4,
        help="Concurrent read RPCs on the shared connection (default 4; 1 restores strict serialization). Mutations are always one at a time.",
    )
    parser.add_argument(
        "--candle-attempts",
        type=int,
        default=4,
        help="Attempts for one historical-candle flight (default 4).",
    )
    parser.add_argument(
        "--candle-stale-ttl",
        type=float,
        default=300.0,
        help="Serve the last good candle set for this many seconds when a fresh fetch fails (default 300s; 0 disables).",
    )
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    """Refuse accidental live trading. Shadow mode never places live orders."""

    if args.orders == "live" and not args.enable_live_orders:
        raise SystemExit(
            "Refusing --orders live without --enable-live-orders. "
            "Do not cut over until Odin approves."
        )
    if args.orders == "live" and os.environ.get("ODIN_METAAPI_HUB_ORDERS") != "live":
        raise SystemExit(
            "Refusing --orders live because ODIN_METAAPI_HUB_ORDERS is not 'live'. "
            "Do not cut over until Odin approves."
        )
    if args.mode != "live" and args.orders == "live":
        raise SystemExit("Refusing --orders live unless --mode live. Shadow hubs cannot trade.")
    if args.mode == "live" and not args.config:
        raise SystemExit("Live mode requires --config pointing at a MetaAPI config file. The file must not be committed.")
    return args


def _load_credentials(path: str, account_id: str) -> tuple[str, str]:
    with open(path, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    meta = cfg.get("metaapi") or {}
    token = meta.get("token") or ""
    resolved_account = account_id or meta.get("account_id") or ""
    if not token:
        raise SystemExit("config is missing metaapi.token")
    if not resolved_account:
        raise SystemExit("account id missing: pass --account-id or set metaapi.account_id")
    return token, resolved_account


async def _serve(args: argparse.Namespace) -> None:
    if args.mode == "shadow":
        broker = InMemoryBroker()
        account_id = args.account_id or "shadow"
        log.warning("Hub starting in SHADOW mode. No MetaAPI connection will be opened.")
    else:
        token, account_id = _load_credentials(args.config, args.account_id)
        broker = MetaApiBroker(
            token,
            account_id,
            rpc_timeout=args.rpc_timeout,
            sync_timeout=args.sync_timeout,
            close_timeout=args.close_timeout,
        )
        log.warning(
            "Hub starting in LIVE read path for account %s orders_mode=%s. Confirm Odin approved this cutover.",
            account_id,
            args.orders,
        )
    owner = SyncOwner(
        broker,
        mode=args.mode,
        orders_mode=args.orders,
        account_id=account_id,
        cache_ttl=args.cache_ttl,
        backoff_base=args.backoff_base,
        backoff_max=args.backoff_max,
        backoff_jitter=args.backoff_jitter,
        read_attempts=args.read_attempts,
        read_concurrency=args.read_concurrency,
        candle_attempts=args.candle_attempts,
        candle_stale_ttl=args.candle_stale_ttl,
    )
    log.info(
        "Hub resilience: rpc_timeout=%.0fs sync_timeout=%.0fs backoff=%.2fs..%.0fs jitter=%.2f "
        "read_attempts=%s read_concurrency=%s candle_attempts=%s candle_stale_ttl=%.0fs",
        args.rpc_timeout,
        args.sync_timeout,
        args.backoff_base,
        args.backoff_max,
        args.backoff_jitter,
        args.read_attempts,
        args.read_concurrency,
        args.candle_attempts,
        args.candle_stale_ttl,
    )
    server = HubServer(owner, args.socket)
    await server.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            pass
    await stop.wait()
    await server.close()
    if args.mode == "live":
        await broker.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )
    args = validate_args(parse_args(argv))
    try:
        asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
