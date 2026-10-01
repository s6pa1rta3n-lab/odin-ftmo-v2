"""Error types for the MetaAPI hub.

These are raised by the in-memory broker, the real MetaAPI adapter, and the
socket server. Clients turn them into ``HubRequestError``.
"""

from __future__ import annotations


class HubError(Exception):
    """Base class for hub failures that are safe to return to an engine."""

    def __init__(self, code: str, message: str, *, retryable: bool = False, receipt: dict | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.receipt = receipt


class TooManyRequestsError(HubError):
    """MetaAPI rejected a synchronization because the account slot is taken.

    The production failure mode is one concurrent synchronization per account.
    A second ``wait_synchronized()`` raises this rather than joining the
    existing stream.
    """

    def __init__(self, message: str = "TooManyRequests: max concurrent synchronizations exceeded", *, max_sync: int = 1) -> None:
        super().__init__("TOO_MANY_REQUESTS", message, retryable=True)
        self.max_sync = max_sync


class NotConnectedError(HubError):
    """Terminal RPC failed because the account is not connected to the broker."""

    def __init__(self, message: str = "not connected to broker") -> None:
        super().__init__("NOT_CONNECTED", message, retryable=True)


class GatewayTimeoutError(HubError):
    """Historical candle request failed with a gateway timeout (HTTP 504)."""

    def __init__(self, message: str = "504 while fetching historical candles") -> None:
        super().__init__("GATEWAY_TIMEOUT", message, retryable=True)


class OrdersDisabledError(HubError):
    """Mutating broker call blocked because live orders are not enabled."""

    def __init__(self, message: str = "order placement is disabled on this hub") -> None:
        super().__init__("ORDERS_DISABLED", message, retryable=False)


class DryRunOrderError(HubError):
    """Mutating broker call was not sent. A receipt explains the dry run."""

    def __init__(self, message: str, receipt: dict) -> None:
        super().__init__("DRY_RUN", message, retryable=False, receipt=receipt)


class HubRequestError(HubError):
    """Error returned over the hub socket to an engine client."""


def classify_metaapi_error(exc: BaseException) -> BaseException:
    """Map a MetaAPI SDK exception onto a hub error.

    Timeouts stay timeouts. They must not be treated as a dropped stream, or
    every slow candle fetch would open another synchronization.
    """

    if isinstance(exc, HubError):
        return exc

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "status", None)

    if (
        "toomanyrequests" in name
        or status == 429
        or "too many" in text
        or "too_many_requests" in text
        or "concurrent synchronization" in text
    ):
        return TooManyRequestsError(str(exc))

    if status == 504 or "504" in text or "gateway time-out" in text or "gateway timeout" in text:
        return GatewayTimeoutError(str(exc))

    if "not connected" in text or "notconnected" in name:
        return NotConnectedError(str(exc))

    if "timeoutexception" in name or "timeout" in name or isinstance(exc, TimeoutError):
        return HubError("TIMEOUT", str(exc), retryable=True)

    return HubError("BROKER_ERROR", f"{type(exc).__name__}: {exc}", retryable=False)
