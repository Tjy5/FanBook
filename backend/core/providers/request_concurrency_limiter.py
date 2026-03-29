from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import threading
import time


@dataclass(slots=True, frozen=True)
class RequestConcurrencyLimitSpec:
    key: str
    max_in_flight: int


@dataclass(slots=True, frozen=True)
class RequestConcurrencyLimiterMetrics:
    max_in_flight: int
    current_in_flight: int
    peak_in_flight: int
    wait_count: int


class RequestConcurrencyAcquireTimeoutError(TimeoutError):
    def __init__(self, *, key: str, timeout_seconds: float | None) -> None:
        self.key = str(key)
        self.timeout_seconds = timeout_seconds
        timeout_text = (
            f"{float(timeout_seconds):g}s"
            if timeout_seconds is not None
            else "an unspecified timeout"
        )
        super().__init__(
            f"Timed out acquiring request concurrency guard '{self.key}' after {timeout_text}."
        )


class RequestConcurrencyLimiter:
    def __init__(self, *, max_in_flight: int) -> None:
        self.max_in_flight = max(1, int(max_in_flight))
        self._condition = threading.Condition()
        self._current_in_flight = 0
        self._peak_in_flight = 0
        self._wait_count = 0

    def tighten(self, *, max_in_flight: int) -> None:
        normalized = max(1, int(max_in_flight))
        with self._condition:
            if normalized >= self.max_in_flight:
                return
            self.max_in_flight = normalized
            self._condition.notify_all()

    def metrics(self) -> RequestConcurrencyLimiterMetrics:
        with self._condition:
            return RequestConcurrencyLimiterMetrics(
                max_in_flight=self.max_in_flight,
                current_in_flight=self._current_in_flight,
                peak_in_flight=self._peak_in_flight,
                wait_count=self._wait_count,
            )

    @contextmanager
    def acquire(self, *, key: str, timeout_seconds: float | None = None) -> Iterator[None]:
        normalized_timeout = (
            None if timeout_seconds is None else max(0.001, float(timeout_seconds))
        )
        deadline = (
            None if normalized_timeout is None else time.monotonic() + normalized_timeout
        )
        counted_wait = False
        with self._condition:
            while self._current_in_flight >= self.max_in_flight:
                if not counted_wait:
                    self._wait_count += 1
                    counted_wait = True
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RequestConcurrencyAcquireTimeoutError(
                        key=key,
                        timeout_seconds=normalized_timeout,
                    )
                self._condition.wait(timeout=remaining)

            self._current_in_flight += 1
            self._peak_in_flight = max(self._peak_in_flight, self._current_in_flight)

        try:
            yield
        finally:
            with self._condition:
                self._current_in_flight = max(0, self._current_in_flight - 1)
                self._condition.notify_all()


class RequestConcurrencyLimiterRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limiters: dict[str, RequestConcurrencyLimiter] = {}

    def get(self, spec: RequestConcurrencyLimitSpec | None) -> RequestConcurrencyLimiter | None:
        if spec is None:
            return None
        with self._lock:
            limiter = self._limiters.get(spec.key)
            if limiter is None:
                limiter = RequestConcurrencyLimiter(max_in_flight=spec.max_in_flight)
                self._limiters[spec.key] = limiter
            else:
                limiter.tighten(max_in_flight=spec.max_in_flight)
            return limiter

    def clear(self) -> None:
        with self._lock:
            self._limiters.clear()


request_concurrency_limiter_registry = RequestConcurrencyLimiterRegistry()


def build_global_concurrency_limit_spec(
    *,
    max_in_flight: int | None,
    scope_key: str = "fanbook-process-global",
) -> RequestConcurrencyLimitSpec | None:
    normalized_limit = _normalize_limit(max_in_flight)
    if normalized_limit is None:
        return None
    normalized_scope_key = str(scope_key or "").strip().lower() or "fanbook-process-global"
    return RequestConcurrencyLimitSpec(
        key=f"global|{normalized_scope_key}",
        max_in_flight=normalized_limit,
    )


def build_target_concurrency_limit_spec(
    *,
    provider_name: str,
    base_url: str,
    api_key: str,
    max_in_flight: int | None,
) -> RequestConcurrencyLimitSpec | None:
    normalized_limit = _normalize_limit(max_in_flight)
    if normalized_limit is None:
        return None
    api_key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    normalized_key = "|".join(
        [
            "target",
            str(provider_name or "").strip().lower(),
            str(base_url or "").strip().rstrip("/").lower(),
            api_key_digest,
        ]
    )
    return RequestConcurrencyLimitSpec(
        key=normalized_key,
        max_in_flight=normalized_limit,
    )


def _normalize_limit(value: int | None) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized <= 0:
        return None
    return normalized
