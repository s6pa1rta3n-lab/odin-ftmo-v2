"""Fixtures: a fake MetaAPI broker and an executor factory. No network, no token file."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autoexec.broker import BrokerError  # noqa: E402
from autoexec.config import Config  # noqa: E402
from autoexec.engine import Executor  # noqa: E402
from autoexec.jsonlog import JsonLogger  # noqa: E402
from autoexec.state import HaltLatch, StateStore  # noqa: E402

LOGIN = "541458001"
MAGIC = 20261010
COMMENT = "BTC_ADVISOR_AUTO"

# FTMO BTCUSD-like specification: $1 per 1.0 price unit per lot.
SPEC = {
    "symbol": "BTCUSD",
    "tickSize": 0.01,
    "tickValue": 0.01,
    "contractSize": 1,
    "volumeStep": 0.01,
    "minVolume": 0.01,
    "maxVolume": 50,
    "digits": 2,
    "marginCurrency": "USD",
    "initialMargin": 0,
}
QUOTE = {"symbol": "BTCUSD", "bid": 85000.0, "ask": 85020.0, "time": "2026-10-10T10:00:00.000Z"}
ACCOUNT = {"login": LOGIN, "equity": 95000.0, "balance": 95000.0, "margin": 0.0, "freeMargin": 95000.0, "leverage": 100, "currency": "USD", "marginLevel": 0}

NOW = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


class FakeBroker:
    def __init__(
        self,
        *,
        account: Optional[Dict[str, Any]] = None,
        positions: Optional[List[Dict[str, Any]]] = None,
        spec: Optional[Dict[str, Any]] = None,
        quote: Optional[Dict[str, Any]] = None,
        deals: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.account = dict(account or ACCOUNT)
        self.positions_list = list(positions or [])
        self.spec = dict(spec or SPEC)
        self.quote = dict(quote or QUOTE)
        # Per-symbol overrides; anything not listed falls back to self.spec / self.quote.
        self.specs: Dict[str, Dict[str, Any]] = {}
        self.quotes: Dict[str, Dict[str, Any]] = {}
        self.unknown_symbols: set = set()  # symbols the "broker" does not know (404)
        # Broker symbol list: None -> derived from known specs + the three defaults.
        self.symbol_list: Optional[List[str]] = None
        # MetaAPI calculate-margin: notional / leverage per symbol (default 1:2 like FTMO crypto);
        # set calc_margin_supported=False to exercise the calibration fallbacks.
        self.calc_margin_supported = True
        self.margin_leverage_default = 2.0
        self.margin_leverage: Dict[str, float] = {}
        self.calc_margin_calls: List[Dict[str, Any]] = []
        self.deals = list(deals or [])
        self.trade_calls: List[Dict[str, Any]] = []
        self.trade_response: Dict[str, Any] = {"numericCode": 10009, "stringCode": "TRADE_RETCODE_DONE", "orderId": "9001", "positionId": "9001"}
        self.trade_error: Optional[Exception] = None
        self.fail_reads: set = set()
        self.read_calls: List[str] = []
        self.history_windows: List[tuple] = []
        # Transient failures: one exception popped per call for that operation name
        # ("account_information", "positions", ..., "trade").
        self.fail_queue: Dict[str, List[Exception]] = {}

    def fail_next(self, name: str, *errors: Exception) -> None:
        self.fail_queue.setdefault(name, []).extend(errors)

    def _maybe_fail(self, name: str) -> None:
        self.read_calls.append(name)
        queued = self.fail_queue.get(name)
        if queued:
            raise queued.pop(0)
        if name in self.fail_reads:
            raise BrokerError(f"simulated failure in {name}", status=503)

    def account_information(self) -> Dict[str, Any]:
        self._maybe_fail("account_information")
        return dict(self.account)

    def positions(self) -> List[Dict[str, Any]]:
        self._maybe_fail("positions")
        return [dict(p) for p in self.positions_list]

    def set_symbol(self, symbol: str, *, spec: Optional[Dict[str, Any]] = None, quote: Optional[Dict[str, Any]] = None) -> None:
        if spec is not None:
            self.specs[symbol] = dict(spec, symbol=symbol)
        if quote is not None:
            self.quotes[symbol] = dict(quote, symbol=symbol)

    def symbols(self) -> List[str]:
        self._maybe_fail("symbols")
        if self.symbol_list is not None:
            return list(self.symbol_list)
        names = {"BTCUSD", "ETHUSD", "SOLUSD", *self.specs.keys()}
        return sorted(n for n in names if n not in self.unknown_symbols)

    def calculate_margin(self, symbol: str, order_type: str, volume: float, open_price: float) -> Dict[str, Any]:
        self._maybe_fail("calculate_margin")
        self.calc_margin_calls.append({"symbol": symbol, "type": order_type, "volume": volume, "openPrice": open_price})
        if not self.calc_margin_supported:
            raise BrokerError("HTTP 404 POST /calculate-margin: not supported", status=404)
        spec = self.specs.get(symbol, self.spec)
        contract = float(spec.get("contractSize") or 1)
        lev = self.margin_leverage.get(symbol, self.margin_leverage_default)
        return {"margin": volume * contract * open_price / lev}

    def symbol_specification(self, symbol: str) -> Dict[str, Any]:
        self._maybe_fail("symbol_specification")
        if symbol in self.unknown_symbols:
            raise BrokerError(f"HTTP 404 GET /symbols/{symbol}/specification: not found", status=404)
        return dict(self.specs.get(symbol, self.spec), symbol=symbol)

    def current_price(self, symbol: str) -> Dict[str, Any]:
        self._maybe_fail("current_price")
        if symbol in self.unknown_symbols:
            raise BrokerError(f"HTTP 404 GET /symbols/{symbol}/current-price: not found", status=404)
        return dict(self.quotes.get(symbol, self.quote), symbol=symbol)

    def history_deals(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        self._maybe_fail("history_deals")
        self.history_windows.append((start, end))
        return [dict(d) for d in self.deals if start <= _parse_time(d["time"]) < end]

    def trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.trade_calls.append(dict(payload))
        queued = self.fail_queue.get("trade")
        if queued:
            raise queued.pop(0)
        if self.trade_error is not None:
            raise self.trade_error
        return dict(self.trade_response)


def position(
    pid: str = "P1",
    *,
    side: str = "BUY",
    volume: float = 0.4,
    open_price: float = 84000.0,
    stop_loss: Optional[float] = 83500.0,
    take_profit: Optional[float] = 86000.0,
    magic: int = MAGIC,
    comment: str = COMMENT,
    profit: float = 10.0,
    commission: float = -5.0,
    swap: float = 0.0,
    symbol: str = "BTCUSD",
) -> Dict[str, Any]:
    return {
        "id": pid,
        "symbol": symbol,
        "type": "POSITION_TYPE_BUY" if side == "BUY" else "POSITION_TYPE_SELL",
        "volume": volume,
        "openPrice": open_price,
        "stopLoss": stop_loss,
        "takeProfit": take_profit,
        "magic": magic,
        "comment": comment,
        "profit": profit,
        "commission": commission,
        "swap": swap,
    }


def deal(
    did: str,
    *,
    time: str,
    profit: float,
    commission: float = 0.0,
    swap: float = 0.0,
    magic: int = MAGIC,
    comment: str = COMMENT,
    symbol: str = "BTCUSD",
    entry_type: str = "DEAL_ENTRY_OUT",
    volume: float = 0.4,
    position_id: str = "P0",
    dtype: str = "DEAL_TYPE_SELL",
) -> Dict[str, Any]:
    return {
        "id": did,
        "type": dtype,
        "entryType": entry_type,
        "symbol": symbol,
        "magic": magic,
        "comment": comment,
        "time": time,
        "volume": volume,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "positionId": position_id,
    }


def make_config(tmp_path, **env: str) -> Config:
    base = {
        "AUTOEXEC_STATE_DIR": str(tmp_path / "state"),
        "AUTOEXEC_LOG_PATH": str(tmp_path / "state" / "autoexec.jsonl"),
        "AUTOEXEC_TOKEN_SOURCE": str(tmp_path / "missing.json"),
    }
    base.update(env)
    return Config.from_env(base)


def make_executor(tmp_path, broker: FakeBroker, *, now: datetime = NOW, env: Optional[Dict[str, str]] = None, token: str = "SECRET-TOKEN-123") -> Executor:
    cfg = make_config(tmp_path, **(env or {}))
    clock = {"now": now, "mono": 1000.0}
    sleeps: List[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["mono"] += seconds

    logger = JsonLogger(cfg.log_path, stdout=False, token=token)
    ex = Executor(
        cfg,
        broker,
        logger,
        state=StateStore(os.path.join(cfg.state_dir, "state.json")),
        halt=HaltLatch(cfg.halt_file),
        now_fn=lambda: clock["now"],
        sleep_fn=fake_sleep,
        monotonic_fn=lambda: clock["mono"],
    )
    ex.clock = clock  # type: ignore[attr-defined]  # tests advance time via ex.clock["now"] / ex.clock["mono"]
    ex.sleeps = sleeps  # type: ignore[attr-defined]  # recorded retry delays; no real sleeping in tests
    return ex


def entry(side: str = "BUY", stop: float = 84500.0, target: float = 86500.0, entry_type: str = "MARKET", **extra: Any) -> Dict[str, Any]:
    body = {"side": side, "entry_type": entry_type, "stop": stop, "target": target}
    body.update(extra)
    return body


@pytest.fixture
def broker() -> FakeBroker:
    return FakeBroker()


@pytest.fixture
def executor(tmp_path, broker):
    return make_executor(tmp_path, broker)
