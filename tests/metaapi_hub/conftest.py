"""Isolate hub tests from a developer shell that already exported hub flags."""

from __future__ import annotations

import pytest

_HUB_ENV = (
    "ODIN_METAAPI_HUB",
    "ODIN_METAAPI_HUB_ORDERS",
    "ODIN_METAAPI_HUB_SOCKET",
)


@pytest.fixture(autouse=True)
def _clear_hub_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _HUB_ENV:
        monkeypatch.delenv(key, raising=False)
