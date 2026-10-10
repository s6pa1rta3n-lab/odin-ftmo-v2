"""MetaAPI REST client (stdlib ``urllib``) against the London client host.

Same transport the repo's other MetaAPI REST scripts use: ``auth-token``
header, JSON bodies, ``/users/current/accounts/{id}/...`` paths. The token is
held only on this object and is never included in exceptions or logs.

Reads and the one mutating call (``trade``) are separated so the executor can
hand a read-only view to the preflight script and to dry-run decisions.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional


class BrokerError(RuntimeError):
    """HTTP or transport failure talking to MetaAPI. Never carries the token."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        body: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.retry_after = retry_after  # seconds, parsed from the Retry-After header when present


def parse_retry_after(value: Optional[str], *, now: Optional[datetime] = None) -> Optional[float]:
    """Seconds to wait from a ``Retry-After`` header value (delta-seconds or HTTP-date); None if absent/unparseable."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    return max(0.0, (when - ref).total_seconds())


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class MetaApiRest:
    """Thin REST wrapper. One instance per process; thread-safe (no shared state)."""

    def __init__(self, token: str, account_id: str, *, host: str, timeout: float = 30.0, trade_timeout: float = 120.0) -> None:
        if not token:
            raise ValueError("MetaAPI token is empty")
        self._token = token
        self.account_id = account_id
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.trade_timeout = trade_timeout
        self.trade_calls: List[Dict[str, Any]] = []

    # -- transport -----------------------------------------------------------

    def _request(self, method: str, path: str, body: Optional[dict] = None, *, timeout: Optional[float] = None) -> Any:
        url = f"{self.host}{path}"
        data = None
        headers = {"auth-token": self._token, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")[:800]
            retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
            raise BrokerError(
                f"HTTP {exc.code} {method} {path}: {err_body}", status=exc.code, body=err_body, retry_after=retry_after
            ) from None
        except urllib.error.URLError as exc:
            raise BrokerError(f"transport error {method} {path}: {exc.reason}") from None
        except (TimeoutError, OSError) as exc:
            raise BrokerError(f"transport error {method} {path}: {type(exc).__name__}: {exc}") from None

    def _acct(self, suffix: str) -> str:
        return f"/users/current/accounts/{self.account_id}{suffix}"

    # -- reads ---------------------------------------------------------------

    def account_information(self) -> Dict[str, Any]:
        info = self._request("GET", self._acct("/account-information"))
        return info if isinstance(info, dict) else {}

    def positions(self) -> List[Dict[str, Any]]:
        pos = self._request("GET", self._acct("/positions"))
        return pos if isinstance(pos, list) else []

    def symbols(self) -> List[str]:
        """Symbols the broker lists for this account (MetaAPI ``GET .../symbols``)."""

        syms = self._request("GET", self._acct("/symbols"))
        if isinstance(syms, dict):
            syms = syms.get("symbols") or syms.get("data") or []
        return [str(x) for x in syms] if isinstance(syms, list) else []

    def calculate_margin(self, symbol: str, order_type: str, volume: float, open_price: float) -> Dict[str, Any]:
        """Broker-side margin for a hypothetical order (MetaAPI ``POST .../calculate-margin``).

        Read-only computation; it does not place anything.
        """

        body = {"symbol": symbol, "type": order_type, "volume": float(volume), "openPrice": float(open_price)}
        res = self._request("POST", self._acct("/calculate-margin"), body)
        return res if isinstance(res, dict) else {"raw": res}

    def symbol_specification(self, symbol: str) -> Dict[str, Any]:
        spec = self._request("GET", self._acct(f"/symbols/{urllib.parse.quote(symbol)}/specification"))
        return spec if isinstance(spec, dict) else {}

    def current_price(self, symbol: str) -> Dict[str, Any]:
        px = self._request("GET", self._acct(f"/symbols/{urllib.parse.quote(symbol)}/current-price"))
        return px if isinstance(px, dict) else {}

    def history_deals(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        path = self._acct(f"/history-deals/time/{urllib.parse.quote(_iso_z(start))}/{urllib.parse.quote(_iso_z(end))}")
        deals = self._request("GET", path)
        if isinstance(deals, dict):
            deals = deals.get("deals") or deals.get("data") or []
        return deals if isinstance(deals, list) else []

    # -- the only mutation ---------------------------------------------------

    def trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /trade. Callers must have passed every guard and the arm check."""

        self.trade_calls.append(dict(payload))
        res = self._request("POST", self._acct("/trade"), payload, timeout=self.trade_timeout)
        return res if isinstance(res, dict) else {"raw": res}


def trade_ok(res: Dict[str, Any]) -> bool:
    code = str(res.get("stringCode") or "")
    numeric = res.get("numericCode")
    if code in {"TRADE_RETCODE_DONE", "TRADE_RETCODE_PLACED", "DONE"}:
        return True
    if numeric in (10008, 10009):
        return True
    return False
