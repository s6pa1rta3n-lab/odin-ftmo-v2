"""Shadow probe: three engines subscribe and none of them synchronize.

Run with ``python -m metaapi_hub.shadow_probe``. The process exits 0 only when
the hub synchronized once, every named engine connected, and no order method
reached the broker. It does not read credentials and does not open a MetaAPI
connection.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from metaapi_hub.adapter import HubBackedWrapper
from metaapi_hub.errors import HubRequestError
from metaapi_hub.harness import assert_shadow_proof, start_hub


async def run_shadow_probe() -> dict[str, Any]:
    """Execute the three-engine dry run and return the evidence dict."""

    handle = await start_hub(mode="shadow", orders_mode="dry_run", account_id="shadow-account")
    engines = {
        "btc": "BTCUSD",
        "us100": "US100.cash",
        "gold": "XAUUSD",
    }
    wrappers = []
    order_errors: list[dict] = []
    local_syncs: dict[str, int] = {}
    try:
        async def _one(name: str, symbol: str) -> dict:
            wrapper = HubBackedWrapper(
                token="not-sent-to-hub",
                account_id="shadow-account",
                engine_name=name,
                socket_path=handle.socket_path,
                shadow=True,
            )
            wrappers.append(wrapper)
            await wrapper.connect()
            info = await wrapper.get_account_information()
            candles = await wrapper.account.get_historical_candles(symbol, "15m", limit=20)  # type: ignore[union-attr]
            try:
                await wrapper.connection.create_market_buy_order(  # type: ignore[union-attr]
                    symbol,
                    0.01,
                    stop_loss=1.0,
                    take_profit=2.0,
                    options={"comment": f"SHADOW_{name.upper()}"},
                )
                sent = True
                code = None
            except HubRequestError as exc:
                sent = False
                code = exc.code
                order_errors.append(
                    {
                        "engine": name,
                        "code": exc.code,
                        "dry_run": bool(exc.receipt and exc.receipt.get("dryRun")),
                        "sent": bool(exc.receipt and exc.receipt.get("sent")),
                    }
                )
            local_syncs[name] = wrapper.client.local_synchronize_calls
            return {
                "engine": name,
                "equity": info.get("equity"),
                "candles": len(candles),
                "order_sent": sent,
                "order_code": code,
                "local_synchronize_calls": wrapper.client.local_synchronize_calls,
            }

        results = await asyncio.gather(*[_one(name, symbol) for name, symbol in engines.items()])
        # A client refresh must not open a second synchronization.
        await wrappers[0].get_account_information()
        snapshot = handle.owner.snapshot()
        assert_shadow_proof(snapshot, engines=set(engines))
        if any(item["order_sent"] for item in results):
            raise AssertionError("shadow probe sent an order")
        if any(item["local_synchronize_calls"] for item in results):
            raise AssertionError(f"an engine synchronized locally: {local_syncs}")
        if handle.broker.synchronize_calls != 1:
            raise AssertionError("broker synchronization count drifted")
        evidence = {
            "ok": True,
            "note": "DO NOT CUT OVER until Odin approves. This probe did not contact MetaAPI.",
            "engines": results,
            "order_errors": order_errors,
            "snapshot": snapshot,
        }
        return evidence
    finally:
        for wrapper in wrappers:
            await wrapper.detach()
        await handle.close()


def main() -> int:
    """CLI entry. Prints JSON evidence."""

    try:
        evidence = asyncio.run(run_shadow_probe())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
        return 1
    print(json.dumps(evidence, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
