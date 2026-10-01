"""In-process hub startup used by the shadow probe and tests."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from metaapi_hub.broker import InMemoryBroker
from metaapi_hub.owner import SyncOwner
from metaapi_hub.server import HubServer


@dataclass
class HubHandle:
    """Running shadow or scripted hub."""

    owner: SyncOwner
    broker: InMemoryBroker
    server: HubServer
    socket_path: str
    directory: str | None = None

    async def close(self) -> None:
        await self.server.close()
        if self.directory and os.path.isdir(self.directory):
            try:
                os.rmdir(self.directory)
            except OSError:
                pass


async def start_hub(
    *,
    mode: str = "shadow",
    orders_mode: str = "deny",
    account_id: str = "shadow",
    socket_path: str | None = None,
    broker: InMemoryBroker | None = None,
    owner_kwargs: dict | None = None,
) -> HubHandle:
    """Start a unix-socket hub bound to an in-memory broker.

    This never constructs ``MetaApiBroker`` and never reads a token file.
    """

    directory = None
    if socket_path is None:
        directory = tempfile.mkdtemp(prefix="odin-metaapi-hub-")
        socket_path = os.path.join(directory, "hub.sock")
    memory = broker or InMemoryBroker()
    owner = SyncOwner(
        memory,
        mode=mode,
        orders_mode=orders_mode,
        account_id=account_id,
        **(owner_kwargs or {}),
    )
    server = HubServer(owner, socket_path)
    await server.start()
    return HubHandle(owner=owner, broker=memory, server=server, socket_path=socket_path, directory=directory)


def assert_shadow_proof(snapshot: dict, *, engines: set[str]) -> None:
    """Raise AssertionError unless the snapshot shows a single sync owner."""

    if snapshot["synchronize_calls"] != 1:
        raise AssertionError(f"expected exactly 1 synchronization, saw {snapshot['synchronize_calls']}")
    if snapshot["broker_synchronize_calls"] != 1:
        raise AssertionError(f"broker synchronize_calls={snapshot['broker_synchronize_calls']}")
    if snapshot["broker_order_calls"] not in (0, None):
        raise AssertionError(f"broker accepted orders: {snapshot['broker_order_calls']}")
    if snapshot["broker_mutation_calls"] not in (0, None):
        raise AssertionError(f"broker accepted mutations: {snapshot['broker_mutation_calls']}")
    missing = engines.difference(snapshot["clients"])
    if missing:
        raise AssertionError(f"missing engine clients: {sorted(missing)}")
    if snapshot["orders_live"]:
        raise AssertionError("shadow proof hub reports orders_live")
