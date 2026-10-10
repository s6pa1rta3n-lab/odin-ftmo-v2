"""Configuration from environment variables and an optional token file.

The MetaAPI token is never a default and never logged. It comes from
``AUTOEXEC_TOKEN`` or from the JSON file at ``AUTOEXEC_TOKEN_SOURCE``
(``metaapi.token`` or ``metaapi_token`` key, same layout as the existing
``config_us100.json`` on the VM).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

LONDON_CLIENT_HOST = "https://mt-client-api-v1.london.agiliumtrade.ai"

DEFAULT_ACCOUNT_ID = "a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf"
DEFAULT_EXPECTED_LOGIN = "541458001"
DEFAULT_SYMBOL = "BTCUSD"
DEFAULT_SYMBOLS: Tuple[str, ...] = ()  # empty allowlist = every symbol the broker lists (Odin 2026-10-10 19:07 ET)
ASSET_CLASSES = ("crypto", "forex", "index", "metals")
DEFAULT_COMMENT = "BTC_ADVISOR_AUTO"
DEFAULT_MAGIC = 20261010

DEFAULT_TOKEN_SOURCE = "/home/solveetcoagula/odin_ftmo/config_us100.json"
DEFAULT_STATE_DIR = "/home/solveetcoagula/btc-advisor-autoexec/state"


Env = Mapping[str, str]


def env_suffix(symbol: str) -> str:
    """``US100.cash`` -> ``US100_CASH``: the suffix used by per-symbol env variables."""

    return re.sub(r"[^A-Z0-9]", "_", symbol.upper())


def _env_by_suffix(env: Env, prefix: str, *, exclude: Tuple[str, ...] = ()) -> Dict[str, str]:
    """``{SUFFIX: value}`` for every ``<prefix>_<SUFFIX>`` env var (symbols are open-ended)."""

    out: Dict[str, str] = {}
    head = prefix + "_"
    for key, raw in env.items():
        if not key.startswith(head) or raw is None or str(raw).strip() == "":
            continue
        suffix = key[len(head):]
        if not suffix or key in exclude:
            continue
        out[suffix] = str(raw).strip()
    return out


def _env_by_suffix_float(env: Env, prefix: str, *, exclude: Tuple[str, ...] = ()) -> Dict[str, float]:
    return {k: float(v) for k, v in _env_by_suffix(env, prefix, exclude=exclude).items()}


def _csv(value: str) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(x.strip() for x in value.split(",") if x.strip()))


def _env_bool(env: Env, name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(env: Env, name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_opt_float(env: Env, name: str) -> Optional[float]:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return None
    return float(raw)


def _env_int(env: Env, name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_str(env: Env, name: str, default: str) -> str:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass
class Config:
    # Target account
    account_id: str = DEFAULT_ACCOUNT_ID
    expected_login: str = DEFAULT_EXPECTED_LOGIN
    symbol: str = DEFAULT_SYMBOL  # default symbol when a request carries none (Odin 2026-10-10 17:07 ET)
    symbols: Tuple[str, ...] = DEFAULT_SYMBOLS  # optional allowlist, AUTOEXEC_SYMBOLS; empty = everything the broker lists
    symbols_deny: Tuple[str, ...] = ()  # optional denylist, AUTOEXEC_SYMBOLS_DENY
    status_symbols: Tuple[str, ...] = ()  # extra symbols to report in /status, AUTOEXEC_STATUS_SYMBOLS
    client_host: str = LONDON_CLIENT_HOST

    # Identity of the auto-trader's own trades
    magic: int = DEFAULT_MAGIC
    comment: str = DEFAULT_COMMENT

    # Arming / kill
    orders_enabled: bool = False
    kill: bool = False
    kill_file: str = ""

    # Guard parameters (approved mechanics; defaults are the approved values)
    max_risk_usd: float = 250.0
    daily_loss_cap_usd: float = 500.0
    equity_halt_usd: float = 90750.0
    halt_file: str = ""
    post_place_cooldown_sec: float = 60.0

    # Second-position rule (Odin 2026-10-10 05:55 ET)
    max_positions_total: int = 2
    second_position_min_rr: float = 2.0
    min_margin_level_pct: float = 200.0
    margin_per_lot_usd: Optional[float] = None  # BTCUSD (legacy un-suffixed name)
    symbol_leverage: Optional[float] = None  # BTCUSD (legacy un-suffixed name)
    margin_per_lot_usd_by_symbol: Dict[str, float] = field(default_factory=dict)  # keyed by env suffix
    symbol_leverage_by_symbol: Dict[str, float] = field(default_factory=dict)  # keyed by env suffix
    margin_use_account_leverage: bool = False
    margin_calc_broker: bool = True  # prefer MetaAPI calculate-margin (broker-reported) for the margin estimate
    second_position_scope: str = "all"  # all (account-wide, Odin 19:07 ET) | allowed (allowlist symbols only)
    sample_stop_pct: float = 1.0  # default sample stop distance for /symbol as % of price

    # Commission (Odin 19:07 ET): broker/deals-derived when available, else a model per
    # symbol or asset class. ``pct`` = percentage of notional per side (default 0.065 %,
    # Trading Ops' measured FTMO crypto rate); ``flat`` = per-lot round trip. The pct model
    # is the default for crypto only; forex/index/metals need broker/deals data or an
    # explicit per-symbol value, otherwise the entry skips (COMMISSION_UNAVAILABLE).
    # The un-suffixed flat fallback (27) is BTCUSD's legacy figure (Odin 05:47 ET) and is
    # used only when BTCUSD resolves to the flat model.
    commission_per_lot_roundtrip: float = 27.0
    commission_per_lot_roundtrip_by_symbol: Dict[str, float] = field(default_factory=dict)  # keyed by env suffix
    commission_pct_per_side: float = 0.065
    commission_pct_per_side_by_symbol: Dict[str, float] = field(default_factory=dict)  # keyed by env suffix (symbol or class)
    commission_model_by_symbol: Dict[str, str] = field(default_factory=dict)  # keyed by env suffix (symbol or class): pct | flat
    asset_class_by_symbol: Dict[str, str] = field(default_factory=dict)  # keyed by env suffix
    commission_source: str = "auto"  # auto | env | spec | deals
    commission_lookback_days: int = 30

    # Timezone of the FTMO day boundary
    day_tz: str = "Europe/Prague"

    # Local interface
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787
    api_key: str = ""

    # Files
    state_dir: str = DEFAULT_STATE_DIR
    log_path: str = ""
    token_source: str = DEFAULT_TOKEN_SOURCE

    # HTTP
    http_timeout_sec: float = 30.0
    trade_timeout_sec: float = 120.0

    # Reliability (Trading Ops 2026-10-10 09:57 ET): caches and 429/5xx retry.
    # None of these change guards, sizing, decisions or the state-file format.
    spec_cache_sec: float = 1800.0  # symbol specification
    commission_cache_sec: float = 1800.0  # deals-derived commission lookback
    status_cache_sec: float = 15.0  # /status snapshot only; /setup and /tighten read fresh
    retry_attempts: int = 3
    retry_budget_sec: float = 10.0
    retry_base_sec: float = 1.0
    retry_max_sec: float = 4.0

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Optional[Env] = None) -> "Config":
        e: Env = os.environ if env is None else env
        state_dir = _env_str(e, "AUTOEXEC_STATE_DIR", DEFAULT_STATE_DIR)
        # Broker symbol names are case-sensitive (e.g. US100.cash); keep them as written.
        symbols = _csv(_env_str(e, "AUTOEXEC_SYMBOLS", ""))
        cfg = cls(
            account_id=_env_str(e, "AUTOEXEC_ACCOUNT_ID", DEFAULT_ACCOUNT_ID),
            expected_login=_env_str(e, "AUTOEXEC_EXPECTED_LOGIN", DEFAULT_EXPECTED_LOGIN),
            symbol=_env_str(e, "AUTOEXEC_SYMBOL", DEFAULT_SYMBOL),
            symbols=symbols,
            symbols_deny=_csv(_env_str(e, "AUTOEXEC_SYMBOLS_DENY", "")),
            status_symbols=_csv(_env_str(e, "AUTOEXEC_STATUS_SYMBOLS", "")),
            client_host=_env_str(e, "AUTOEXEC_CLIENT_HOST", LONDON_CLIENT_HOST).rstrip("/"),
            magic=_env_int(e, "AUTOEXEC_MAGIC", DEFAULT_MAGIC),
            comment=_env_str(e, "AUTOEXEC_COMMENT", DEFAULT_COMMENT),
            orders_enabled=_env_bool(e, "AUTOEXEC_ORDERS_ENABLED", False),
            kill=_env_bool(e, "AUTOEXEC_KILL", False),
            kill_file=_env_str(e, "AUTOEXEC_KILL_FILE", os.path.join(state_dir, "KILL")),
            max_risk_usd=_env_float(e, "AUTOEXEC_MAX_RISK_USD", 250.0),
            daily_loss_cap_usd=_env_float(e, "AUTOEXEC_DAILY_LOSS_CAP_USD", 500.0),
            equity_halt_usd=_env_float(e, "AUTOEXEC_EQUITY_HALT_USD", 90750.0),
            halt_file=_env_str(e, "AUTOEXEC_HALT_FILE", os.path.join(state_dir, "HALT")),
            post_place_cooldown_sec=_env_float(e, "AUTOEXEC_POST_PLACE_COOLDOWN_SEC", 60.0),
            max_positions_total=_env_int(e, "AUTOEXEC_MAX_POSITIONS_TOTAL", 2),
            second_position_min_rr=_env_float(e, "AUTOEXEC_SECOND_POSITION_MIN_RR", 2.0),
            min_margin_level_pct=_env_float(e, "AUTOEXEC_MIN_MARGIN_LEVEL_PCT", 200.0),
            margin_per_lot_usd=_env_opt_float(e, "AUTOEXEC_MARGIN_PER_LOT_USD"),
            symbol_leverage=_env_opt_float(e, "AUTOEXEC_SYMBOL_LEVERAGE"),
            margin_per_lot_usd_by_symbol=_env_by_suffix_float(e, "AUTOEXEC_MARGIN_PER_LOT_USD"),
            symbol_leverage_by_symbol=_env_by_suffix_float(e, "AUTOEXEC_SYMBOL_LEVERAGE"),
            margin_use_account_leverage=_env_bool(e, "AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE", False),
            margin_calc_broker=_env_bool(e, "AUTOEXEC_MARGIN_CALC_BROKER", True),
            second_position_scope=_env_str(e, "AUTOEXEC_SECOND_POSITION_SCOPE", "all").lower(),
            sample_stop_pct=_env_float(e, "AUTOEXEC_SAMPLE_STOP_PCT", 1.0),
            commission_per_lot_roundtrip=_env_float(e, "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP", 27.0),
            commission_per_lot_roundtrip_by_symbol=_env_by_suffix_float(e, "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP"),
            commission_pct_per_side=_env_float(e, "AUTOEXEC_COMMISSION_PCT_PER_SIDE", 0.065),
            commission_pct_per_side_by_symbol=_env_by_suffix_float(e, "AUTOEXEC_COMMISSION_PCT_PER_SIDE"),
            commission_model_by_symbol={k: v.lower() for k, v in _env_by_suffix(e, "AUTOEXEC_COMMISSION_MODEL").items()},
            asset_class_by_symbol={k: v.lower() for k, v in _env_by_suffix(e, "AUTOEXEC_ASSET_CLASS").items()},
            commission_source=_env_str(e, "AUTOEXEC_COMMISSION_SOURCE", "auto").lower(),
            commission_lookback_days=_env_int(e, "AUTOEXEC_COMMISSION_LOOKBACK_DAYS", 30),
            day_tz=_env_str(e, "AUTOEXEC_DAY_TZ", "Europe/Prague"),
            bind_host=_env_str(e, "AUTOEXEC_BIND_HOST", "127.0.0.1"),
            bind_port=_env_int(e, "AUTOEXEC_BIND_PORT", 8787),
            api_key=_env_str(e, "AUTOEXEC_API_KEY", ""),
            state_dir=state_dir,
            log_path=_env_str(e, "AUTOEXEC_LOG_PATH", os.path.join(state_dir, "autoexec.jsonl")),
            token_source=_env_str(e, "AUTOEXEC_TOKEN_SOURCE", DEFAULT_TOKEN_SOURCE),
            http_timeout_sec=_env_float(e, "AUTOEXEC_HTTP_TIMEOUT_SEC", 30.0),
            trade_timeout_sec=_env_float(e, "AUTOEXEC_TRADE_TIMEOUT_SEC", 120.0),
            spec_cache_sec=_env_float(e, "AUTOEXEC_SPEC_CACHE_SEC", 1800.0),
            commission_cache_sec=_env_float(e, "AUTOEXEC_COMMISSION_CACHE_SEC", 1800.0),
            status_cache_sec=_env_float(e, "AUTOEXEC_STATUS_CACHE_SEC", 15.0),
            retry_attempts=_env_int(e, "AUTOEXEC_RETRY_ATTEMPTS", 3),
            retry_budget_sec=_env_float(e, "AUTOEXEC_RETRY_BUDGET_SEC", 10.0),
            retry_base_sec=_env_float(e, "AUTOEXEC_RETRY_BASE_SEC", 1.0),
            retry_max_sec=_env_float(e, "AUTOEXEC_RETRY_MAX_SEC", 4.0),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("AUTOEXEC_SYMBOL must be set")
        if self.symbols and self.symbol not in self.symbols:
            raise ValueError(f"AUTOEXEC_SYMBOL {self.symbol!r} must be in the AUTOEXEC_SYMBOLS allowlist {list(self.symbols)}")
        if self.symbol in self.symbols_deny:
            raise ValueError(f"AUTOEXEC_SYMBOL {self.symbol!r} is in AUTOEXEC_SYMBOLS_DENY")
        if self.second_position_scope not in {"allowed", "all"}:
            raise ValueError("AUTOEXEC_SECOND_POSITION_SCOPE must be all|allowed")
        for suffix, model in self.commission_model_by_symbol.items():
            if model not in {"pct", "flat"}:
                raise ValueError(f"AUTOEXEC_COMMISSION_MODEL_{suffix} must be pct|flat, got {model!r}")
        for suffix, cls_name in self.asset_class_by_symbol.items():
            if cls_name not in ASSET_CLASSES:
                raise ValueError(f"AUTOEXEC_ASSET_CLASS_{suffix} must be one of {list(ASSET_CLASSES)}")
        if self.commission_pct_per_side < 0:
            raise ValueError("AUTOEXEC_COMMISSION_PCT_PER_SIDE must be >= 0")
        if self.sample_stop_pct <= 0:
            raise ValueError("AUTOEXEC_SAMPLE_STOP_PCT must be > 0")
        if self.commission_source not in {"auto", "env", "spec", "deals"}:
            raise ValueError(f"AUTOEXEC_COMMISSION_SOURCE must be auto|env|spec|deals, got {self.commission_source!r}")
        if self.max_risk_usd <= 0:
            raise ValueError("AUTOEXEC_MAX_RISK_USD must be > 0")
        if self.daily_loss_cap_usd <= 0:
            raise ValueError("AUTOEXEC_DAILY_LOSS_CAP_USD must be > 0")
        if self.equity_halt_usd <= 0:
            raise ValueError("AUTOEXEC_EQUITY_HALT_USD must be > 0")
        if self.commission_per_lot_roundtrip < 0:
            raise ValueError("AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP must be >= 0")
        if self.max_positions_total < 1:
            raise ValueError("AUTOEXEC_MAX_POSITIONS_TOTAL must be >= 1")
        if self.max_positions_total > 2:
            raise ValueError("AUTOEXEC_MAX_POSITIONS_TOTAL above 2 is not an approved mechanic")
        if self.second_position_min_rr <= 0:
            raise ValueError("AUTOEXEC_SECOND_POSITION_MIN_RR must be > 0")
        if self.min_margin_level_pct <= 0:
            raise ValueError("AUTOEXEC_MIN_MARGIN_LEVEL_PCT must be > 0")
        if self.spec_cache_sec < 0 or self.commission_cache_sec < 0 or self.status_cache_sec < 0:
            raise ValueError("AUTOEXEC_*_CACHE_SEC must be >= 0 (0 disables the cache)")
        if self.retry_attempts < 1:
            raise ValueError("AUTOEXEC_RETRY_ATTEMPTS must be >= 1 (1 = no retry)")
        if self.retry_budget_sec < 0 or self.retry_base_sec < 0 or self.retry_max_sec < 0:
            raise ValueError("AUTOEXEC_RETRY_*_SEC must be >= 0")
        if self.magic == 0:
            raise ValueError("AUTOEXEC_MAGIC must be non-zero; magic 0 is reserved for manual positions")
        if not self.comment:
            raise ValueError("AUTOEXEC_COMMENT must be set")

    # ---- per-symbol lookups --------------------------------------------------

    def is_allowed_symbol(self, symbol: str) -> bool:
        """Env allow/deny lists only; broker validation happens in the executor."""

        if any(symbol.upper() == d.upper() for d in self.symbols_deny):
            return False
        if self.symbols:
            return any(symbol.upper() == a.upper() for a in self.symbols)
        return True

    def canonical_symbol(self, raw: str) -> Optional[str]:
        """Case-insensitive match against the env allowlist (if any); None if denied/not allowed.

        With an empty allowlist the raw name is returned as written and the broker list
        decides (see ``Executor.resolve_symbol``).
        """

        wanted = str(raw).strip()
        if not wanted or not self.is_allowed_symbol(wanted):
            return None
        for sym in self.symbols:
            if sym.upper() == wanted.upper():
                return sym
        return wanted

    def _by_symbol(self, table: Dict[str, Any], symbol: str) -> Any:
        return table.get(env_suffix(symbol))

    def asset_class_override(self, symbol: str) -> Optional[str]:
        return self._by_symbol(self.asset_class_by_symbol, symbol)

    def commission_model_for(self, symbol: str, asset_class: Optional[str]) -> Optional[str]:
        """Explicit per-symbol model, else the asset-class model (crypto defaults to pct)."""

        explicit = self._by_symbol(self.commission_model_by_symbol, symbol)
        if explicit:
            return explicit
        if self._by_symbol(self.commission_per_lot_roundtrip_by_symbol, symbol) is not None:
            return "flat"
        if self._by_symbol(self.commission_pct_per_side_by_symbol, symbol) is not None:
            return "pct"
        if asset_class:
            by_class = self.commission_model_by_symbol.get(env_suffix(asset_class))
            if by_class:
                return by_class
            if asset_class == "crypto":
                return "pct"
        if symbol == DEFAULT_SYMBOL and asset_class is None:
            return "flat"  # legacy BTCUSD fallback (Odin 05:47 ET) when the broker gives no asset class
        return None

    def commission_flat_for(self, symbol: str) -> Optional[float]:
        v = self._by_symbol(self.commission_per_lot_roundtrip_by_symbol, symbol)
        if v is not None:
            return v
        if symbol == DEFAULT_SYMBOL:
            return self.commission_per_lot_roundtrip
        return None

    def commission_pct_for(self, symbol: str, asset_class: Optional[str]) -> float:
        v = self._by_symbol(self.commission_pct_per_side_by_symbol, symbol)
        if v is not None:
            return v
        if asset_class:
            v = self.commission_pct_per_side_by_symbol.get(env_suffix(asset_class))
            if v is not None:
                return v
        return self.commission_pct_per_side

    def commission_env_for(self, symbol: str) -> Optional[float]:
        """Flat env fallback for ``symbol`` (kept for callers of the #86 API)."""

        return self.commission_flat_for(symbol)

    def margin_per_lot_for(self, symbol: str) -> Optional[float]:
        v = self._by_symbol(self.margin_per_lot_usd_by_symbol, symbol)
        if v is not None:
            return v
        if symbol == DEFAULT_SYMBOL:
            return self.margin_per_lot_usd
        return None

    def symbol_leverage_for(self, symbol: str) -> Optional[float]:
        v = self._by_symbol(self.symbol_leverage_by_symbol, symbol)
        if v is not None:
            return v
        if symbol == DEFAULT_SYMBOL:
            return self.symbol_leverage
        return None

    @property
    def kill_active(self) -> bool:
        """Kill switch: env flag or presence of the kill file. Blocks every mutation."""

        if self.kill:
            return True
        return bool(self.kill_file) and os.path.exists(self.kill_file)

    def public_dict(self) -> Dict[str, Any]:
        """Config for logs and /status. Never includes the token."""

        out: Dict[str, Any] = {}
        for f in fields(self):
            if f.name in {"extra", "api_key"}:
                continue
            out[f.name] = getattr(self, f.name)
        out["symbols"] = list(self.symbols)
        out["symbols_deny"] = list(self.symbols_deny)
        out["api_key_set"] = bool(self.api_key)
        out["kill_active"] = self.kill_active
        return out


def load_token(cfg: Config, env: Optional[Env] = None) -> str:
    """Read the MetaAPI token from env or the token file. Never log the result."""

    e: Env = os.environ if env is None else env
    env_token = (e.get("AUTOEXEC_TOKEN") or "").strip()
    if env_token:
        return env_token
    path = Path(cfg.token_source)
    if not path.exists():
        raise RuntimeError(
            f"MetaAPI token not found: set AUTOEXEC_TOKEN or point AUTOEXEC_TOKEN_SOURCE at a JSON file (tried {path})"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    token = ""
    if isinstance(data, dict):
        meta = data.get("metaapi")
        if isinstance(meta, dict):
            token = str(meta.get("token") or "")
        if not token:
            token = str(data.get("metaapi_token") or data.get("token") or "")
    if not token:
        raise RuntimeError(f"MetaAPI token missing in {path} (expected metaapi.token or metaapi_token)")
    return token
