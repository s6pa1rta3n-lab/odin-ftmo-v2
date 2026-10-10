"""The executor: live reads -> guards -> sizing -> (gated) order.

Order placement is disabled unless ``AUTOEXEC_ORDERS_ENABLED=1`` *and* the
kill switch is off. In dry-run every guard still runs against live read-only
data; the would-be order payload is logged and nothing is sent.

Fail closed: any failed live read rejects the request. A rejected or dry-run
decision never calls ``broker.trade``.

Reliability (Trading Ops 2026-10-10 09:57 ET): reads and the idempotent
``POSITION_MODIFY`` retry 429/5xx with backoff and ``Retry-After``; the symbol
spec and the commission lookback are cached (~30 min); ``status()`` serves a
short-lived snapshot. New-order placement is never retried. None of this
changes guards, sizing, decisions, or the state-file format.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import guards
from . import second_position as second
from .broker import BrokerError, trade_ok
from .commission import resolve_commission
from .config import Config
from .guards import Rejected
from .jsonlog import JsonLogger
from .retry import RetryPolicy, run_with_retry
from .sizing import D, SizingError, parse_spec, size_position
from .state import HaltLatch, StateStore
from .trading_day import day_window_utc, trading_day, tz


class Executor:
    def __init__(
        self,
        cfg: Config,
        broker: Any,
        logger: JsonLogger,
        *,
        state: Optional[StateStore] = None,
        halt: Optional[HaltLatch] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        monotonic_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.cfg = cfg
        self.broker = broker
        self.log = logger
        self.state = state or StateStore(f"{cfg.state_dir}/state.json")
        self.halt = halt or HaltLatch(cfg.halt_file)
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.sleep_fn = sleep_fn or time.sleep
        self.monotonic_fn = monotonic_fn or time.monotonic
        self.zone = tz(cfg.day_tz)
        self._lock = threading.Lock()
        self.retry_policy = RetryPolicy(
            attempts=cfg.retry_attempts,
            budget_sec=cfg.retry_budget_sec,
            base_sec=cfg.retry_base_sec,
            max_sec=cfg.retry_max_sec,
        )
        self.retry_policy.validate()
        # In-memory caches (never persisted; the state-file format is unchanged).
        self._cache_lock = threading.Lock()
        self._spec_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # per symbol
        self._lookback_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
        self._status_cache: Optional[Tuple[float, Optional[Dict[str, Any]], Optional[Rejected]]] = None

    # ------------------------------------------------------------------ utils

    def _now(self) -> datetime:
        n = self.now_fn()
        return n if n.tzinfo else n.replace(tzinfo=timezone.utc)

    def _retry(self, label: str, fn: Callable[[], Any]) -> Any:
        """429/5xx retry for reads and the idempotent position modify. Never used for entries."""

        return run_with_retry(
            fn,
            policy=self.retry_policy,
            label=label,
            logger=self.log,
            sleep=self.sleep_fn,
            monotonic=self.monotonic_fn,
        )

    def _cached(self, slot: str, ttl: float) -> Optional[Any]:
        with self._cache_lock:
            entry = getattr(self, slot)
        if entry is None or ttl <= 0:
            return None
        at, value = entry[0], entry[1]
        if self.monotonic_fn() - at >= ttl:
            return None
        return value

    def _store(self, slot: str, value: Any) -> None:
        with self._cache_lock:
            setattr(self, slot, (self.monotonic_fn(), value))

    def _cached_spec(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._cache_lock:
            entry = self._spec_cache.get(symbol)
        if entry is None or self.cfg.spec_cache_sec <= 0:
            return None
        if self.monotonic_fn() - entry[0] >= self.cfg.spec_cache_sec:
            return None
        return entry[1]

    def _store_spec(self, symbol: str, spec: Dict[str, Any]) -> None:
        with self._cache_lock:
            self._spec_cache[symbol] = (self.monotonic_fn(), spec)

    def _spec_for(self, symbol: str, cache_hits: Optional[List[str]] = None) -> Dict[str, Any]:
        """Symbol specification with the per-symbol cache and 429/5xx retry."""

        spec = self._cached_spec(symbol)
        if spec is None:
            spec = self._retry(f"symbol_specification({symbol})", lambda: self.broker.symbol_specification(symbol))
            self._store_spec(symbol, spec)
        elif cache_hits is not None:
            cache_hits.append(f"symbol_specification({symbol})")
        return spec

    def _quote_for(self, symbol: str) -> Dict[str, Any]:
        return self._retry(f"current_price({symbol})", lambda: self.broker.current_price(symbol))

    def invalidate_caches(self) -> None:
        with self._cache_lock:
            self._spec_cache = {}
            self._lookback_cache = None
            self._status_cache = None

    # ------------------------------------------------------------------ symbols

    def resolve_symbol(self, payload: Dict[str, Any]) -> str:
        """Symbol from the request, defaulting to the configured default (BTCUSD). Unknown -> Rejected."""

        raw = payload.get("symbol") if isinstance(payload, dict) else None
        if raw is None or str(raw).strip() == "":
            return self.cfg.symbol
        symbol = self.cfg.canonical_symbol(raw)
        if symbol is None:
            raise Rejected("SYMBOL_NOT_ALLOWED", f"symbol {raw!r} is not in the allowed set {list(self.cfg.symbols)}")
        return symbol

    def _scope_symbols(self) -> Optional[List[str]]:
        """Symbols whose positions count for the position limit / second-position rule (None = all)."""

        return None if self.cfg.second_position_scope == "all" else list(self.cfg.symbols)

    def _book(self, positions: List[Dict[str, Any]]) -> guards.Book:
        return guards.classify_positions(positions, symbols=self._scope_symbols(), magic=self.cfg.magic, comment=self.cfg.comment)

    @property
    def armed(self) -> bool:
        return bool(self.cfg.orders_enabled) and not self.cfg.kill_active

    def _mode(self, force_dry_run: bool) -> str:
        return "live" if (self.armed and not force_dry_run) else "dry_run"

    # ------------------------------------------------------------------ reads

    def _read_all(self, *, symbol: Optional[str] = None, need_spec: bool, need_deals: bool, extra_symbols: Sequence[str] = ()) -> Dict[str, Any]:
        """Every read the guards need. Raises Rejected(READ_FAILED) on any failure.

        ``quote_raw``/``spec_raw`` are for ``symbol`` (default: the configured default
        symbol); ``quotes``/``specs`` additionally hold ``extra_symbols``.
        """

        symbol = symbol or self.cfg.symbol
        now = self._now()
        out: Dict[str, Any] = {"now": now, "symbol": symbol, "quotes": {}, "specs": {}}
        cache_hits: List[str] = []
        step = "account_information"
        try:
            out["account"] = self._retry(step, self.broker.account_information)
            step = "positions"
            out["positions"] = self._retry(step, self.broker.positions)
            for sym in [symbol] + [x for x in extra_symbols if x != symbol]:
                step = f"current_price({sym})"
                out["quotes"][sym] = self._quote_for(sym)
                if need_spec:
                    step = f"symbol_specification({sym})"
                    out["specs"][sym] = self._spec_for(sym, cache_hits)
            out["quote_raw"] = out["quotes"][symbol]
            if need_spec:
                out["spec_raw"] = out["specs"][symbol]
            if need_deals:
                day_start, day_end = day_window_utc(now, self.zone)
                out["day_start"], out["day_end"] = day_start, day_end
                step = "history_deals(today)"
                out["deals_today"] = self._retry(step, lambda: self.broker.history_deals(day_start, now + timedelta(minutes=5)))
                step = "history_deals(lookback)"
                lookback = self._cached("_lookback_cache", self.cfg.commission_cache_sec)
                if lookback is None:
                    lookback_start = now - timedelta(days=self.cfg.commission_lookback_days)
                    lookback = self._retry(step, lambda: self.broker.history_deals(lookback_start, now + timedelta(minutes=5)))
                    self._store("_lookback_cache", lookback)
                else:
                    cache_hits.append(step)
                out["deals_lookback"] = lookback
            out["cache_hits"] = cache_hits
        except BrokerError as exc:
            raise Rejected("READ_FAILED", f"live read failed at {step}: {exc}", step=step)
        except Rejected:
            raise
        except Exception as exc:  # malformed payloads, etc.
            raise Rejected("READ_FAILED", f"live read failed at {step}: {type(exc).__name__}: {exc}", step=step)
        return out

    def _commission_for(self, symbol: str, spec_raw: Optional[Dict[str, Any]], deals_lookback: Optional[List[Dict[str, Any]]]):
        env_value = self.cfg.commission_env_for(symbol)
        return resolve_commission(
            mode=self.cfg.commission_source,
            env_value=D(env_value) if env_value is not None else None,
            spec=spec_raw,
            deals=deals_lookback,
            symbol=symbol,
        )

    def _symbol_view(self, symbol: str, quote_raw: Optional[Dict[str, Any]], spec_raw: Optional[Dict[str, Any]], deals_lookback: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Per-symbol quote/spec/commission summary for /status and the preflight. Does not raise."""

        view: Dict[str, Any] = {"symbol": symbol}
        if quote_raw is not None:
            try:
                q = guards.parse_quote(quote_raw)
                view["quote"] = {"bid": float(q.bid), "ask": float(q.ask), "spread": float(q.spread)}
            except Rejected as exc:
                view["quote"] = {"error": exc.reason}
        if spec_raw is not None:
            view["broker_symbol"] = spec_raw.get("symbol")
            view["description"] = spec_raw.get("description")
            view["path"] = spec_raw.get("path")
            try:
                view["spec"] = parse_spec(spec_raw).as_dict()
            except SizingError as exc:
                view["spec"] = {"error": str(exc)}
            view["commission"] = self._commission_for(symbol, spec_raw, deals_lookback).as_dict()
        view["margin_calibration"] = {
            "margin_per_lot_usd": self.cfg.margin_per_lot_for(symbol),
            "symbol_leverage": self.cfg.symbol_leverage_for(symbol),
        }
        return view

    def _check_login(self, account: Dict[str, Any]) -> None:
        login = str(account.get("login") or "")
        if self.cfg.expected_login and login != str(self.cfg.expected_login):
            raise Rejected("ACCOUNT_MISMATCH", f"account login {login!r} != expected {self.cfg.expected_login!r}; refusing")

    def _equity(self, account: Dict[str, Any]) -> Decimal:
        eq = account.get("equity")
        if eq is None:
            raise Rejected("READ_FAILED", "account information has no equity")
        return D(eq)

    # ------------------------------------------------------------------ guard snapshot

    def guard_state(self, reads: Dict[str, Any]) -> Dict[str, Any]:
        """Guard values for logs, /status and the preflight. Does not raise."""

        now: datetime = reads["now"]
        today = trading_day(now, self.zone).isoformat()
        account = reads.get("account") or {}
        positions = reads.get("positions") or []
        symbol = reads.get("symbol") or self.cfg.symbol
        book = self._book(positions)
        auto_all = guards.auto_positions(positions, magic=self.cfg.magic, comment=self.cfg.comment)
        per_symbol_open = {}
        for p in guards.all_symbol_positions(book):
            per_symbol_open[p.get("symbol")] = per_symbol_open.get(p.get("symbol"), 0) + 1
        state: Dict[str, Any] = {
            "symbol": symbol,
            "symbols": list(self.cfg.symbols),
            "second_position_scope": self.cfg.second_position_scope,
            "trading_day": today,
            "day_tz": self.cfg.day_tz,
            "login": account.get("login"),
            "login_ok": str(account.get("login") or "") == str(self.cfg.expected_login),
            "equity": account.get("equity"),
            "balance": account.get("balance"),
            "equity_halt_threshold": self.cfg.equity_halt_usd,
            "equity_at_or_below_halt": (D(account["equity"]) <= D(self.cfg.equity_halt_usd)) if account.get("equity") is not None else None,
            "halt_latched": self.halt.active,
            "halt_record": self.halt.read(),
            "book": book.summary(),
            "auto_open": len(book.auto),
            "manual_open": len(book.manual),
            "other_magic_open": len(book.other),
            "total_open": len(guards.all_symbol_positions(book)),
            "open_by_symbol": per_symbol_open,
            "auto_open_all_symbols": len(auto_all),
            "max_positions_total": self.cfg.max_positions_total,
            "daily_cap_usd": self.cfg.daily_loss_cap_usd,
            "daily_cap_latched_day": self.state.daily_cap_hit_day(),
            "daily_cap_latched_today": self.state.daily_cap_hit_day() == today,
            "orders_enabled": self.cfg.orders_enabled,
            "kill_active": self.cfg.kill_active,
            "armed": self.armed,
            "post_place_cooldown": self._cooldown_state(now),
        }
        if "deals_today" in reads:
            pnl = guards.daily_pnl(reads["deals_today"], auto_all, magic=self.cfg.magic, comment=self.cfg.comment)
            state["daily_pnl"] = pnl.as_dict()
            state["day_window_utc"] = [reads["day_start"].isoformat(), reads["day_end"].isoformat()]
        if "quote_raw" in reads:
            try:
                q = guards.parse_quote(reads["quote_raw"])
                state["quote"] = {"bid": float(q.bid), "ask": float(q.ask), "spread": float(q.spread)}
            except Rejected as exc:
                state["quote"] = {"error": exc.reason}
        if "spec_raw" in reads:
            try:
                state["spec"] = parse_spec(reads["spec_raw"]).as_dict()
            except SizingError as exc:
                state["spec"] = {"error": str(exc)}
            state["commission"] = self._commission_for(symbol, reads.get("spec_raw"), reads.get("deals_lookback")).as_dict()
        quotes = reads.get("quotes") or {}
        specs = reads.get("specs") or {}
        if quotes or specs:
            state["per_symbol"] = {
                sym: self._symbol_view(sym, quotes.get(sym), specs.get(sym), reads.get("deals_lookback"))
                for sym in sorted(set(quotes) | set(specs), key=lambda x: (x != symbol, x))
            }
        return state

    def _cooldown_state(self, now: datetime) -> Dict[str, Any]:
        last = self.state.last_place_attempt()
        if not last:
            return {"active": False}
        remaining = float(last.get("at_epoch", 0)) + self.cfg.post_place_cooldown_sec - now.timestamp()
        return {"active": remaining > 0, "remaining_sec": max(0.0, remaining), "last": last}

    def status(self) -> Dict[str, Any]:
        """Read-only status for GET /status and the preflight."""

        # Snapshot cache for /status ONLY (AUTOEXEC_STATUS_CACHE_SEC). /setup and /tighten
        # call _read_all directly and always read fresh. Failures are cached for the same
        # TTL so a poller cannot amplify rate limiting; every failure is logged.
        ttl = self.cfg.status_cache_sec
        cached = self._cached("_status_cache", ttl)
        if cached is not None:
            reads, error, at = cached["reads"], cached["error"], cached["at"]
            age = round(self.monotonic_fn() - at, 3)
        else:
            error = None
            reads = None
            age = 0.0
            try:
                reads = self._read_all(symbol=self.cfg.symbol, need_spec=True, need_deals=True, extra_symbols=self.cfg.symbols)
            except Rejected as exc:
                error = exc
                self.log.emit("status_read_failed", code=exc.code, reason=exc.reason, step=exc.detail.get("step"), cached_for_sec=ttl, alert=True)
            if ttl > 0:
                self._store("_status_cache", {"reads": reads, "error": error, "at": self.monotonic_fn()})
        if error is not None:
            return {
                "ok": False,
                "code": error.code,
                "reason": error.reason,
                "config": self.cfg.public_dict(),
                "snapshot": {"cached": cached is not None, "age_sec": age, "ttl_sec": ttl},
            }
        assert reads is not None
        # Guard state is recomputed from the snapshot so local inputs (halt file, kill
        # file, cooldown, cap latch) stay live even while broker reads are cached.
        live = dict(reads)
        live["now"] = self._now()
        return {
            "ok": True,
            "guards": self.guard_state(live),
            "config": self.cfg.public_dict(),
            "reads": live,
            "snapshot": {"cached": cached is not None, "age_sec": age, "ttl_sec": ttl, "cache_hits": live.get("cache_hits", [])},
        }

    # ------------------------------------------------------------------ entry

    def decide_entry(self, payload: Dict[str, Any], *, force_dry_run: bool = False) -> Dict[str, Any]:
        with self._lock:
            return self._decide_entry(payload, force_dry_run=force_dry_run)

    def _decide_entry(self, payload: Dict[str, Any], *, force_dry_run: bool) -> Dict[str, Any]:
        decision_id = str(uuid.uuid4())
        mode = self._mode(force_dry_run)
        decision: Dict[str, Any] = {
            "decision_id": decision_id,
            "action": "ENTRY",
            "mode": mode,
            "orders_enabled": self.cfg.orders_enabled,
            "kill_active": self.cfg.kill_active,
            "sent": False,
            "accepted": False,
            "request": payload,
            "guards": {},
        }
        self.log.emit("request", decision_id=decision_id, action="ENTRY", mode=mode, request=payload)
        reads: Dict[str, Any] = {}
        symbol = self.cfg.symbol
        try:
            symbol = self.resolve_symbol(payload)
            decision["symbol"] = symbol
            setup = guards.parse_setup(payload)
            decision["setup"] = {"symbol": symbol, "side": setup.side, "entry_type": setup.entry_type, "stop": float(setup.stop), "target": float(setup.target), "request_id": setup.request_id}
            if self.cfg.kill_active:
                raise Rejected("KILL_SWITCH", "kill switch is active; no mutations")

            reads = self._read_all(symbol=symbol, need_spec=True, need_deals=True)
            now: datetime = reads["now"]
            gs = self.guard_state(reads)
            decision["guards"] = gs
            self._check_login(reads["account"])

            # #6 equity halt (latched or live)
            equity = self._equity(reads["account"])
            try:
                guards.check_equity_halt(equity, threshold=D(self.cfg.equity_halt_usd), latched=self.halt.active)
            except Rejected as exc:
                if exc.code == "EQUITY_HALT":
                    rec = self.halt.latch(equity=float(equity), threshold=self.cfg.equity_halt_usd, reason=exc.reason)
                    self.log.emit("equity_halt_latched", decision_id=decision_id, halt=rec, halt_file=str(self.halt.path))
                    decision["guards"]["halt_latched"] = True
                    decision["guards"]["halt_record"] = rec
                raise

            # #3 pending/cooldown after a previous place attempt, then the position count
            cd = gs["post_place_cooldown"]
            if cd.get("active"):
                raise Rejected("POST_PLACE_COOLDOWN", f"a place attempt happened {self.cfg.post_place_cooldown_sec - cd['remaining_sec']:.0f}s ago; waiting for the book to settle", cooldown=cd)
            book = self._book(reads["positions"])
            existing_positions = guards.all_symbol_positions(book)
            second.check_max_positions(len(existing_positions), max_total=self.cfg.max_positions_total)

            # #5 shared daily cap (closed + floating on every auto-magic trade, any symbol), Prague day
            today = trading_day(now, self.zone).isoformat()
            auto_all = guards.auto_positions(reads["positions"], magic=self.cfg.magic, comment=self.cfg.comment)
            pnl = guards.daily_pnl(reads["deals_today"], auto_all, magic=self.cfg.magic, comment=self.cfg.comment)
            try:
                guards.check_daily_cap(pnl, cap_usd=D(self.cfg.daily_loss_cap_usd), today_iso=today, latched_day=self.state.daily_cap_hit_day())
            except Rejected as exc:
                if exc.code == "DAILY_CAP_HIT":
                    self.state.latch_daily_cap(today, float(pnl.total))
                    self.log.emit("daily_cap_latched", decision_id=decision_id, day=today, pnl=pnl.as_dict())
                    decision["guards"]["daily_cap_latched_day"] = today
                    decision["guards"]["daily_cap_latched_today"] = True
                raise

            # #1 levels, #2 sizing incl. spread + commission
            quote = guards.parse_quote(reads["quote_raw"])
            stop_distance = guards.check_levels(setup, quote)
            spec = parse_spec(reads["spec_raw"])
            comm = self._commission_for(symbol, reads["spec_raw"], reads.get("deals_lookback"))
            decision["commission"] = comm.as_dict()
            if comm.per_lot_roundtrip is None:
                raise Rejected("COMMISSION_UNAVAILABLE", comm.note, symbol=symbol)
            sizing = size_position(
                stop_distance=stop_distance,
                spread=quote.spread,
                spec=spec,
                commission_per_lot_roundtrip=comm.per_lot_roundtrip,
                max_risk_usd=D(self.cfg.max_risk_usd),
            )
            decision["sizing"] = sizing.as_dict()
            decision.update(
                {
                    "lots": float(sizing.lots),
                    "risk_usd": float(sizing.risk_usd),
                    "per_lot_loss": float(sizing.per_lot_loss),
                    "spread": float(quote.spread),
                    "spread_cost_per_lot": float(sizing.spread_cost_per_lot),
                    "commission_per_lot_roundtrip": float(comm.per_lot_roundtrip),
                    "commission_source": comm.source,
                    "stop_distance": float(stop_distance),
                    "quote": {"bid": float(quote.bid), "ask": float(quote.ask)},
                }
            )
            if not sizing.ok:
                raise Rejected("SKIP_MIN_VOLUME", sizing.reason, sizing=sizing.as_dict())
            reward, rr = second.reward_risk_ratio(setup, quote, sizing)
            decision["reward_per_lot"] = float(reward)
            decision["reward_risk"] = float(rr)

            # #3 second-position rule (only when a BTC position is already open)
            if existing_positions:
                decision["second_position"] = self._check_second_position(
                    symbol=symbol,
                    existing_positions=existing_positions,
                    setup=setup,
                    quote=quote,
                    sizing=sizing,
                    rr=rr,
                    pnl=pnl,
                    equity=equity,
                    spec=spec,
                    reads=reads,
                )

            # Build the order: SL and TP attached in the same request, always.
            order = {
                "actionType": "ORDER_TYPE_BUY" if setup.side == "BUY" else "ORDER_TYPE_SELL",
                "symbol": symbol,
                "volume": float(sizing.lots),
                "stopLoss": float(setup.stop),
                "takeProfit": float(setup.target),
                "comment": self.cfg.comment,
                "magic": int(self.cfg.magic),
            }
            if not (order["stopLoss"] > 0 and order["takeProfit"] > 0):
                raise Rejected("MISSING_SL_TP", "internal: order built without SL/TP; refusing")
            decision["order"] = order
            decision["accepted"] = True

            if mode != "live":
                decision["code"] = "DRY_RUN_WOULD_PLACE"
                decision["reason"] = "dry-run: all guards passed; order logged, nothing sent"
                self.log.emit("decision", **self._loggable(decision))
                return decision

            return self._place(decision, order, setup.request_id, now)

        except Rejected as exc:
            decision["accepted"] = False
            decision["code"] = exc.code
            decision["reason"] = exc.reason
            if exc.detail:
                decision["detail"] = exc.detail
            decision.setdefault("symbol", str((payload or {}).get("symbol") or symbol) if isinstance(payload, dict) else symbol)
            self._attach_informational_sizing(decision, reads, payload, symbol)
            self.log.emit("decision", **self._loggable(decision))
            return decision
        except SizingError as exc:
            decision["code"] = "SIZING_ERROR"
            decision["reason"] = str(exc)
            self.log.emit("decision", **self._loggable(decision))
            return decision

    def _check_second_position(
        self,
        *,
        symbol: str,
        existing_positions: List[Dict[str, Any]],
        setup: guards.Setup,
        quote: guards.Quote,
        sizing: Any,
        rr: Decimal,
        pnl: guards.DailyPnl,
        equity: Decimal,
        spec: Any,
        reads: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate every second-position condition combined across symbols; raises Rejected on the first failure.

        The returned dict is attached to the decision so the guard values are logged
        even when the entry is accepted.
        """

        # Each existing position's risk at SL uses ITS OWN symbol's value per price unit.
        values: Dict[str, Decimal] = {symbol: sizing.value_per_unit_per_lot}
        for p in existing_positions:
            sym = str(p.get("symbol") or "")
            if sym in values:
                continue
            spec_raw = reads["specs"].get(sym)
            try:
                if spec_raw is None:
                    spec_raw = self._spec_for(sym, reads.get("cache_hits"))
                    reads["specs"][sym] = spec_raw
                values[sym] = parse_spec(spec_raw).value_per_unit_per_lot
            except BrokerError as exc:
                raise Rejected("READ_FAILED", f"live read failed at symbol_specification({sym}): {exc}", step=f"symbol_specification({sym})")
            except SizingError as exc:
                raise Rejected("SECOND_SPEC_UNAVAILABLE", f"cannot value the open {sym} position at its stop: {exc}", symbol=sym)
        existing = [second.existing_position_risk(p, values[str(p.get("symbol") or "")]) for p in existing_positions]
        combined = second.combined_open_risk(existing, sizing.risk_usd)
        room = second.daily_cap_room(pnl, cap_usd=D(self.cfg.daily_loss_cap_usd))
        fill_price = quote.ask if setup.side == "BUY" else quote.bid
        margin_override = self.cfg.margin_per_lot_for(symbol)
        leverage = self.cfg.symbol_leverage_for(symbol)
        margin = second.estimate_margin(
            lots=sizing.lots,
            fill_price=fill_price,
            spec_raw=reads["spec_raw"],
            spec=spec,
            account=reads["account"],
            margin_per_lot_override=D(margin_override) if margin_override else None,
            symbol_leverage=D(leverage) if leverage else None,
            use_account_leverage=self.cfg.margin_use_account_leverage,
        )
        info = {
            "symbol": symbol,
            "scope": self.cfg.second_position_scope,
            "existing": [e.as_dict() for e in existing],
            "new_risk_usd": float(sizing.risk_usd),
            "combined_open_risk_usd": float(combined),
            "reward_risk": float(rr),
            "min_rr": self.cfg.second_position_min_rr,
            "daily_cap_room_usd": float(room),
            "equity_after_combined_risk": float(equity - combined),
            "margin": margin.as_dict(),
            "fresh_setup_verified": False,
        }
        try:
            # 1. breakeven-or-better on every existing position (any symbol); combined risk <= $250
            second.check_all_breakeven(existing)
            second.check_combined_risk(combined, max_risk_usd=D(self.cfg.max_risk_usd))
            # 2. R:R >= 2 after costs; never averaging down (same symbol, same side)
            second.check_reward_risk(rr, min_rr=D(self.cfg.second_position_min_rr))
            second.check_no_averaging_down(existing, setup.side, symbol)
            # 3. shared daily-cap room and equity buffer above the halt
            second.check_daily_room(combined, room=room)
            second.check_equity_buffer(equity, combined, halt_usd=D(self.cfg.equity_halt_usd))
            # 4. projected margin level (per-symbol calibration)
            second.check_margin_level(margin, min_level_pct=D(self.cfg.min_margin_level_pct))
        except Rejected as exc:
            exc.detail.setdefault("second_position", info)
            raise
        info["passed"] = True
        return info

    def _place(self, decision: Dict[str, Any], order: Dict[str, Any], request_id: Optional[str], now: datetime) -> Dict[str, Any]:
        # Recorded before the send so an ambiguous result still starts the cooldown.
        self.state.note_place_attempt(at_epoch=now.timestamp(), request_id=request_id, outcome="sending")
        self.log.emit("order_send", decision_id=decision["decision_id"], order=order)
        try:
            res = self.broker.trade(order)
        except BrokerError as exc:
            self.state.note_place_attempt(at_epoch=now.timestamp(), request_id=request_id, outcome=f"error: {exc}")
            decision["sent"] = True
            decision["accepted"] = False
            decision["code"] = "PLACE_ERROR"
            decision["reason"] = f"order sent but the broker call failed: {exc}. Fill state unknown; cooldown active."
            decision["broker_response"] = {"error": str(exc), "status": exc.status}
            self._post_place_sync(decision)
            self.log.emit("decision", **self._loggable(decision))
            return decision
        decision["sent"] = True
        decision["broker_response"] = res
        ok = trade_ok(res)
        decision["code"] = "PLACED" if ok else "PLACE_REJECTED"
        decision["reason"] = "order placed" if ok else f"broker rejected the order: {res.get('stringCode')} {res.get('message') or ''}".strip()
        decision["accepted"] = ok
        self.state.note_place_attempt(at_epoch=now.timestamp(), request_id=request_id, outcome=decision["code"])
        self._post_place_sync(decision)
        self.log.emit("decision", **self._loggable(decision))
        return decision

    def _post_place_sync(self, decision: Dict[str, Any]) -> None:
        try:
            positions = self.broker.positions()
            book = self._book(positions)
            decision["post_place_book"] = book.summary()
            self.log.emit("post_place_sync", decision_id=decision["decision_id"], book=book.summary())
        except Exception as exc:
            decision["post_place_book"] = {"error": str(exc)}
            self.log.emit("post_place_sync_failed", decision_id=decision["decision_id"], error=str(exc))

    def _attach_informational_sizing(self, decision: Dict[str, Any], reads: Dict[str, Any], payload: Dict[str, Any], symbol: str) -> None:
        """Best-effort spread/commission/per-lot-loss on rejected decisions (mechanic #2 logging)."""

        if "sizing" in decision or not reads.get("quote_raw") or not reads.get("spec_raw"):
            return
        try:
            setup = guards.parse_setup(payload)
            quote = guards.parse_quote(reads["quote_raw"])
            stop_distance = guards.check_levels(setup, quote)
            spec = parse_spec(reads["spec_raw"])
            comm = self._commission_for(symbol, reads["spec_raw"], reads.get("deals_lookback"))
            decision.setdefault("commission", comm.as_dict())
            if comm.per_lot_roundtrip is None:
                return
            sizing = size_position(
                stop_distance=stop_distance,
                spread=quote.spread,
                spec=spec,
                commission_per_lot_roundtrip=comm.per_lot_roundtrip,
                max_risk_usd=D(self.cfg.max_risk_usd),
            )
            decision["sizing_informational"] = sizing.as_dict()
            decision.setdefault("spread", float(quote.spread))
            decision.setdefault("commission_per_lot_roundtrip", float(comm.per_lot_roundtrip))
            decision.setdefault("commission_source", comm.source)
            decision.setdefault("per_lot_loss", float(sizing.per_lot_loss))
        except Exception:
            return

    # ------------------------------------------------------------------ tighten

    def tighten_stop(self, payload: Dict[str, Any], *, force_dry_run: bool = False) -> Dict[str, Any]:
        with self._lock:
            return self._tighten_stop(payload, force_dry_run=force_dry_run)

    def _tighten_stop(self, payload: Dict[str, Any], *, force_dry_run: bool) -> Dict[str, Any]:
        decision_id = str(uuid.uuid4())
        mode = self._mode(force_dry_run)
        decision: Dict[str, Any] = {
            "decision_id": decision_id,
            "action": "TIGHTEN",
            "mode": mode,
            "orders_enabled": self.cfg.orders_enabled,
            "kill_active": self.cfg.kill_active,
            "sent": False,
            "accepted": False,
            "request": payload,
            "guards": {},
        }
        self.log.emit("request", decision_id=decision_id, action="TIGHTEN", mode=mode, request=payload)
        try:
            if not isinstance(payload, dict):
                raise Rejected("BAD_REQUEST", "body must be a JSON object")
            raw_stop = payload.get("stop", payload.get("stop_price", payload.get("sl")))
            if raw_stop in (None, "", 0, "0"):
                raise Rejected("SL_REMOVED", "a tighten request must carry a positive stop; removing SL is rejected")
            if payload.get("target") not in (None, "") or payload.get("tp") not in (None, "") or payload.get("take_profit") not in (None, ""):
                raise Rejected("TP_CHANGE_NOT_SUPPORTED", "tighten only moves the stop; the take profit is preserved as-is")
            try:
                new_stop = D(raw_stop)
            except Exception:
                raise Rejected("BAD_PRICE", "stop must be numeric")
            # Symbol: explicit, else the default (BTCUSD) so BTC behaviour is unchanged.
            # A position_id may address an auto position on any allowed symbol.
            symbol = self.resolve_symbol(payload)
            decision["symbol"] = symbol
            if self.cfg.kill_active:
                raise Rejected("KILL_SWITCH", "kill switch is active; no mutations")

            reads = self._read_all(symbol=symbol, need_spec=False, need_deals=False)
            decision["guards"] = self.guard_state(reads)
            self._check_login(reads["account"])
            wanted = payload.get("position_id", payload.get("positionId"))
            if wanted is not None:
                allowed_auto = guards.classify_positions(reads["positions"], symbols=self.cfg.symbols, magic=self.cfg.magic, comment=self.cfg.comment).auto
                matches = [p for p in allowed_auto if str(p.get("id")) == str(wanted)]
                if not matches:
                    raise Rejected("POSITION_NOT_FOUND", f"position {wanted} is not an open automated position on {list(self.cfg.symbols)}")
                target_pos = matches[0]
                symbol = str(target_pos.get("symbol") or symbol)
                decision["symbol"] = symbol
            else:
                book = guards.classify_positions(reads["positions"], symbol=symbol, magic=self.cfg.magic, comment=self.cfg.comment)
                if not book.auto:
                    raise Rejected("NO_AUTO_POSITION", f"no open automated {symbol} position to tighten")
                if len(book.auto) > 1:
                    raise Rejected("AMBIGUOUS_POSITION", f"more than one automated {symbol} position open; pass position_id", positions=[p.get("id") for p in book.auto])
                target_pos = book.auto[0]

            quote_raw = reads["quotes"].get(symbol)
            if quote_raw is None:
                try:
                    quote_raw = self._quote_for(symbol)
                except BrokerError as exc:
                    raise Rejected("READ_FAILED", f"live read failed at current_price({symbol}): {exc}", step=f"current_price({symbol})")
            quote = guards.parse_quote(quote_raw)
            levels = guards.check_tighten(target_pos, new_stop, quote)
            modify = {
                "actionType": "POSITION_MODIFY",
                "positionId": levels["positionId"],
                "stopLoss": levels["stopLoss"],
                "takeProfit": levels["takeProfit"],
            }
            decision["position"] = {
                "id": target_pos.get("id"),
                "symbol": target_pos.get("symbol"),
                "type": target_pos.get("type"),
                "openPrice": target_pos.get("openPrice"),
                "volume": target_pos.get("volume"),
                "stopLoss": target_pos.get("stopLoss"),
                "takeProfit": target_pos.get("takeProfit"),
            }
            decision["order"] = modify
            decision["previous_stop"] = levels["previousStopLoss"]
            decision["accepted"] = True
            if mode != "live":
                decision["code"] = "DRY_RUN_WOULD_MODIFY"
                decision["reason"] = "dry-run: tighten accepted; modify logged, nothing sent"
                self.log.emit("decision", **self._loggable(decision))
                return decision
            self.log.emit("order_send", decision_id=decision_id, order=modify)
            try:
                # POSITION_MODIFY is idempotent (same SL/TP), so 429/5xx are retried.
                res = self._retry("trade:POSITION_MODIFY", lambda: self.broker.trade(modify))
            except BrokerError as exc:
                decision["sent"] = True
                decision["accepted"] = False
                decision["code"] = "MODIFY_ERROR"
                decision["reason"] = f"modify failed after retries: {exc}"
                decision["broker_response"] = {"error": str(exc), "status": exc.status, "retry_after_sec": exc.retry_after}
                self._tighten_failed(decision)
                return decision
            decision["sent"] = True
            decision["broker_response"] = res
            ok = trade_ok(res)
            decision["accepted"] = ok
            decision["code"] = "MODIFIED" if ok else "MODIFY_REJECTED"
            decision["reason"] = "stop tightened" if ok else f"broker rejected the modify: {res.get('stringCode')} {res.get('message') or ''}".strip()
            if not ok:
                self._tighten_failed(decision)
                return decision
            self.log.emit("decision", **self._loggable(decision))
            return decision
        except Rejected as exc:
            decision["code"] = exc.code
            decision["reason"] = exc.reason
            if exc.detail:
                decision["detail"] = exc.detail
            decision.setdefault("symbol", str(payload.get("symbol") or self.cfg.symbol) if isinstance(payload, dict) else self.cfg.symbol)
            self._tighten_failed(decision)
            return decision

    def _tighten_failed(self, decision: Dict[str, Any]) -> None:
        """A tighten that did not go through is never silent: decision line + ALERT line."""

        decision["alert"] = True
        self.log.emit("decision", **self._loggable(decision))
        self.log.emit(
            "tighten_failed",
            alert=True,
            level="ALERT",
            decision_id=decision["decision_id"],
            code=decision.get("code"),
            reason=decision.get("reason"),
            mode=decision.get("mode"),
            sent=decision.get("sent"),
            request=decision.get("request"),
            position=decision.get("position"),
            symbol=decision.get("symbol"),
            broker_response=decision.get("broker_response"),
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _loggable(decision: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(decision)
        g = out.get("guards")
        if isinstance(g, dict):
            g = dict(g)
            g.pop("halt_record", None)
            out["guards"] = g
        return out
