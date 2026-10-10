"""Bounded retry for MetaAPI 429 / 5xx responses.

Used for reads and for the idempotent ``POSITION_MODIFY`` behind ``/tighten``.
It is deliberately NOT used for new-order placement: a retried market order
can double-fill, and a 429 on ``/trade`` does not prove the order was never
accepted. Entry placement keeps its single attempt plus the ambiguous-place
cooldown.

Policy: up to ``attempts`` tries inside a ``budget_sec`` wall-clock budget.
``Retry-After`` is honoured when present (seconds or HTTP-date); otherwise the
delay is ``base_sec * 2**(n-1)`` capped at ``max_sec``. A delay that would
overrun the budget ends the retry loop and the last error is raised.

Every 429 (with its Retry-After), every retry attempt and the final outcome
are emitted as JSON lines through the supplied logger.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from .broker import BrokerError, parse_retry_after  # noqa: F401  (re-exported for callers/tests)

T = TypeVar("T")


@dataclass
class RetryPolicy:
    attempts: int = 3
    budget_sec: float = 10.0
    base_sec: float = 1.0
    max_sec: float = 4.0

    def validate(self) -> None:
        if self.attempts < 1:
            raise ValueError("retry attempts must be >= 1")
        if self.budget_sec < 0 or self.base_sec < 0 or self.max_sec < 0:
            raise ValueError("retry timings must be >= 0")


def is_retryable(exc: BaseException) -> bool:
    if not isinstance(exc, BrokerError):
        return False
    status = exc.status
    if status is None:
        return False
    return status == 429 or 500 <= status <= 599


def run_with_retry(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy,
    label: str,
    logger: Any,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``fn`` with the retry policy. Raises the last BrokerError when exhausted."""

    started = monotonic()
    attempt = 0
    while True:
        attempt += 1
        try:
            result = fn()
        except BrokerError as exc:
            elapsed = monotonic() - started
            retryable = is_retryable(exc)
            if exc.status == 429:
                logger.emit("broker_rate_limited", op=label, attempt=attempt, status=429, retry_after_sec=exc.retry_after, elapsed_sec=round(elapsed, 3), error=str(exc)[:300])
            if not retryable:
                raise
            if attempt >= policy.attempts:
                logger.emit("broker_retry_exhausted", op=label, attempts=attempt, status=exc.status, elapsed_sec=round(elapsed, 3), error=str(exc)[:300], outcome="failed")
                raise
            if exc.retry_after is not None:
                delay = exc.retry_after
                delay_source = "retry-after"
            else:
                delay = min(policy.base_sec * (2 ** (attempt - 1)), policy.max_sec)
                delay_source = "backoff"
            remaining = policy.budget_sec - elapsed
            if delay > remaining:
                logger.emit(
                    "broker_retry_exhausted",
                    op=label,
                    attempts=attempt,
                    status=exc.status,
                    elapsed_sec=round(elapsed, 3),
                    needed_delay_sec=delay,
                    budget_sec=policy.budget_sec,
                    reason="delay would exceed the retry budget",
                    error=str(exc)[:300],
                    outcome="failed",
                )
                raise
            logger.emit("broker_retry", op=label, attempt=attempt, next_attempt=attempt + 1, status=exc.status, delay_sec=delay, delay_source=delay_source, elapsed_sec=round(elapsed, 3), error=str(exc)[:300])
            sleep(delay)
            continue
        if attempt > 1:
            logger.emit("broker_retry_succeeded", op=label, attempts=attempt, elapsed_sec=round(monotonic() - started, 3), outcome="ok")
        return result
