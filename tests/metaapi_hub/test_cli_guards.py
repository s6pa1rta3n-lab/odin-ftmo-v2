"""Process flags that keep a mistaken start from trading."""

from __future__ import annotations

import pytest

from metaapi_hub.__main__ import parse_args, validate_args


def test_cli_defaults_to_shadow_and_denied_orders() -> None:
    args = parse_args([])
    assert args.mode == "shadow"
    assert args.orders == "deny"
    assert args.enable_live_orders is False
    validate_args(args)


def test_cli_refuses_live_orders_without_every_interlock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODIN_METAAPI_HUB_ORDERS", raising=False)
    with pytest.raises(SystemExit, match="enable-live-orders"):
        validate_args(parse_args(["--mode", "live", "--orders", "live", "--config", "config_us100.json"]))

    monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
    with pytest.raises(SystemExit, match="enable-live-orders"):
        validate_args(parse_args(["--mode", "live", "--orders", "live", "--config", "config_us100.json"]))

    monkeypatch.delenv("ODIN_METAAPI_HUB_ORDERS", raising=False)
    with pytest.raises(SystemExit, match="ODIN_METAAPI_HUB_ORDERS"):
        validate_args(
            parse_args(["--mode", "live", "--orders", "live", "--enable-live-orders", "--config", "config_us100.json"])
        )


def test_cli_refuses_live_orders_in_shadow_and_live_mode_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
    with pytest.raises(SystemExit, match="Shadow"):
        validate_args(parse_args(["--mode", "shadow", "--orders", "live", "--enable-live-orders"]))
    with pytest.raises(SystemExit, match="--config"):
        validate_args(parse_args(["--mode", "live", "--orders", "deny"]))
