"""Choose the direct wrapper or the hub adapter.

``ODIN_METAAPI_HUB`` defaults to off. Unknown values also stay off.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("odin.metaapi_hub.factory")

_OFF = {"", "0", "off", "false", "no"}
_SHADOW = {"shadow", "dry-run", "dry_run"}
_ON = {"1", "on", "true", "yes"}


def hub_mode() -> str:
    """Return ``off``, ``shadow``, or ``on``.

    The default is ``off`` so a deploy of this code does not change engines.
    """

    raw = os.environ.get("ODIN_METAAPI_HUB", "0").strip().lower()
    if raw in _OFF:
        return "off"
    if raw in _SHADOW:
        return "shadow"
    if raw in _ON:
        return "on"
    log.warning("Unknown ODIN_METAAPI_HUB=%r; staying off", raw)
    return "off"


def engine_name_for_symbol(symbol: str | None) -> str:
    """Map a trading symbol onto the hub client name used in health output."""

    text = (symbol or "").upper()
    if "BTC" in text:
        return "btc"
    if "XAU" in text or "GOLD" in text:
        return "gold"
    if "US100" in text or "NAS" in text:
        return "us100"
    return "engine"


def build_execution_wrapper(
    token: str | None,
    account_id: str,
    *,
    engine_name: str,
    socket_path: str | None = None,
):
    """Return the object engines assign to ``self.wrapper``.

    Off mode imports ``MetaApiWrapper`` exactly as the engines did before.
    On and shadow modes return ``HubBackedWrapper`` and do not import the SDK.
    """

    mode = hub_mode()
    if mode == "off":
        try:
            from MetaApiWrapper import MetaApiWrapper
        except ImportError as exc:
            raise RuntimeError("MetaApiWrapper module not available") from exc
        return MetaApiWrapper(token, account_id)

    from metaapi_hub.adapter import HubBackedWrapper

    log.info("Building hub-backed wrapper engine=%s hub_mode=%s", engine_name, mode)
    return HubBackedWrapper(
        token,
        account_id,
        engine_name=engine_name,
        socket_path=socket_path,
        shadow=(mode == "shadow"),
    )
