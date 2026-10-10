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
DEFAULT_SYMBOLS = ("BTCUSD", "ETHUSD", "SOLUSD")
DEFAULT_COMMENT = "BTC_ADVISOR_AUTO"
DEFAULT_MAGIC = 20261010

DEFAULT_TOKEN_SOURCE = "/home/solveetcoagula/odin_ftmo/config_us100.json"
DEFAULT_STATE_DIR = "/home/solveetcoagula/btc-advisor-autoexec/state"


Env = Mapping[str, str]


def env_suffix(symbol: str) -> str:
    """``US100.cash`` -> ``US100_CASH``: the suffix used by per-symbol env variables."""

    return re.sub(r"[^A-Z0-9]", "_", symbol.upper())


def _env_per_symbol(env: Env, prefix: str, symbols: Tuple[str, ...]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for sym in symbols:
        raw = env.get(f"{prefix}_{env_suffix(sym)}")
        if raw is not None and raw.strip() != "":
            out[sym] = float(raw)
    return out


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
    symbols: Tuple[str, ...] = DEFAULT_SYMBOLS  # allowed set, AUTOEXEC_SYMBOLS
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
    margin_per_lot_usd_by_symbol: Dict[str, float] = field(default_factory=dict)
    symbol_leverage_by_symbol: Dict[str, float] = field(default_factory=dict)
    margin_use_account_leverage: bool = False
    second_position_scope: str = "allowed"  # allowed | all: which symbols' positions count for the second-position rule

    # Commission. The un-suffixed fallback is BTCUSD's figure (Odin 05:47 ET) and applies
    # to BTCUSD only; other symbols need AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_<SYMBOL>
    # or a broker/deals-derived value, otherwise the entry is skipped (no guessed values).
    commission_per_lot_roundtrip: float = 27.0
    commission_per_lot_roundtrip_by_symbol: Dict[str, float] = field(default_factory=dict)
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
        symbols = tuple(
            dict.fromkeys(sym.strip() for sym in _env_str(e, "AUTOEXEC_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",") if sym.strip())
        )
        cfg = cls(
            account_id=_env_str(e, "AUTOEXEC_ACCOUNT_ID", DEFAULT_ACCOUNT_ID),
            expected_login=_env_str(e, "AUTOEXEC_EXPECTED_LOGIN", DEFAULT_EXPECTED_LOGIN),
            symbol=_env_str(e, "AUTOEXEC_SYMBOL", DEFAULT_SYMBOL),
            symbols=symbols,
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
            margin_per_lot_usd_by_symbol=_env_per_symbol(e, "AUTOEXEC_MARGIN_PER_LOT_USD", symbols),
            symbol_leverage_by_symbol=_env_per_symbol(e, "AUTOEXEC_SYMBOL_LEVERAGE", symbols),
            margin_use_account_leverage=_env_bool(e, "AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE", False),
            second_position_scope=_env_str(e, "AUTOEXEC_SECOND_POSITION_SCOPE", "allowed").lower(),
            commission_per_lot_roundtrip=_env_float(e, "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP", 27.0),
            commission_per_lot_roundtrip_by_symbol=_env_per_symbol(e, "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP", symbols),
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
        if not self.symbols:
            raise ValueError("AUTOEXEC_SYMBOLS must list at least one symbol")
        if self.symbol not in self.symbols:
            raise ValueError(f"AUTOEXEC_SYMBOL {self.symbol!r} must be in AUTOEXEC_SYMBOLS {list(self.symbols)}")
        if self.second_position_scope not in {"allowed", "all"}:
            raise ValueError("AUTOEXEC_SECOND_POSITION_SCOPE must be allowed|all")
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
        return symbol in self.symbols

    def canonical_symbol(self, raw: str) -> Optional[str]:
        """Case-insensitive match of a requested symbol against the allowed set; None if unknown."""

        wanted = str(raw).strip().upper()
        for sym in self.symbols:
            if sym.upper() == wanted:
                return sym
        return None

    def commission_env_for(self, symbol: str) -> Optional[float]:
        """Env fallback commission for ``symbol``; None means no fallback (skip, never guess)."""

        if symbol in self.commission_per_lot_roundtrip_by_symbol:
            return self.commission_per_lot_roundtrip_by_symbol[symbol]
        if symbol == DEFAULT_SYMBOL:
            return self.commission_per_lot_roundtrip
        return None

    def margin_per_lot_for(self, symbol: str) -> Optional[float]:
        if symbol in self.margin_per_lot_usd_by_symbol:
            return self.margin_per_lot_usd_by_symbol[symbol]
        if symbol == DEFAULT_SYMBOL:
            return self.margin_per_lot_usd
        return None

    def symbol_leverage_for(self, symbol: str) -> Optional[float]:
        if symbol in self.symbol_leverage_by_symbol:
            return self.symbol_leverage_by_symbol[symbol]
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
        out["api_key_set"] = bool(self.api_key)
        out["kill_active"] = self.kill_active
        out["per_symbol"] = {
            sym: {
                "commission_env_fallback": self.commission_env_for(sym),
                "margin_per_lot_usd": self.margin_per_lot_for(sym),
                "symbol_leverage": self.symbol_leverage_for(sym),
            }
            for sym in self.symbols
        }
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
