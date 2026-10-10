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
from typing import Any, Dict, Mapping, Optional

LONDON_CLIENT_HOST = "https://mt-client-api-v1.london.agiliumtrade.ai"

DEFAULT_ACCOUNT_ID = "a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf"
DEFAULT_EXPECTED_LOGIN = "541458001"
DEFAULT_SYMBOL = "BTCUSD"
DEFAULT_COMMENT = "BTC_ADVISOR_AUTO"
DEFAULT_MAGIC = 20261010

DEFAULT_TOKEN_SOURCE = "/home/solveetcoagula/odin_ftmo/config_us100.json"
DEFAULT_STATE_DIR = "/home/solveetcoagula/btc-advisor-autoexec/state"


Env = Mapping[str, str]


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
    symbol: str = DEFAULT_SYMBOL
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
    margin_per_lot_usd: Optional[float] = None
    symbol_leverage: Optional[float] = None
    margin_use_account_leverage: bool = False

    # Commission
    commission_per_lot_roundtrip: float = 27.0
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

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Optional[Env] = None) -> "Config":
        e: Env = os.environ if env is None else env
        state_dir = _env_str(e, "AUTOEXEC_STATE_DIR", DEFAULT_STATE_DIR)
        cfg = cls(
            account_id=_env_str(e, "AUTOEXEC_ACCOUNT_ID", DEFAULT_ACCOUNT_ID),
            expected_login=_env_str(e, "AUTOEXEC_EXPECTED_LOGIN", DEFAULT_EXPECTED_LOGIN),
            symbol=_env_str(e, "AUTOEXEC_SYMBOL", DEFAULT_SYMBOL),
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
            margin_use_account_leverage=_env_bool(e, "AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE", False),
            commission_per_lot_roundtrip=_env_float(e, "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP", 27.0),
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
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
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
        if self.magic == 0:
            raise ValueError("AUTOEXEC_MAGIC must be non-zero; magic 0 is reserved for manual positions")
        if not self.comment:
            raise ValueError("AUTOEXEC_COMMENT must be set")

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
