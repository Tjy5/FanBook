from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import threading
import time


@dataclass(slots=True, frozen=True)
class RequestRateLimitSpec:
    key: str
    max_requests_per_minute: int
    window_seconds: float = 60.0


class RequestRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float = 60.0,
        time_source=None,
    ) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(0.001, float(window_seconds))
        self._time_source = time_source or time.monotonic
        self._timestamps: deque[float] = deque()
        self._condition = threading.Condition()

    def acquire(self) -> None:
        with self._condition:
            while True:
                now = float(self._time_source())
                self._prune(now)
                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return
                earliest_allowed = self._timestamps[0] + self.window_seconds
                timeout_seconds = max(0.0, earliest_allowed - now)
                self._condition.wait(timeout=timeout_seconds)

    def _prune(self, now: float) -> None:
        while self._timestamps and (now - self._timestamps[0]) >= self.window_seconds:
            self._timestamps.popleft()


class RequestRateLimiterRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limiters: dict[RequestRateLimitSpec, RequestRateLimiter] = {}

    def get(self, spec: RequestRateLimitSpec | None) -> RequestRateLimiter | None:
        if spec is None:
            return None
        with self._lock:
            limiter = self._limiters.get(spec)
            if limiter is None:
                limiter = RequestRateLimiter(
                    max_requests=spec.max_requests_per_minute,
                    window_seconds=spec.window_seconds,
                )
                self._limiters[spec] = limiter
            return limiter


request_rate_limiter_registry = RequestRateLimiterRegistry()


def build_rate_limit_spec(
    *,
    provider_name: str,
    base_url: str,
    api_key: str,
    max_requests_per_minute: int | None,
    window_seconds: float = 60.0,
) -> RequestRateLimitSpec | None:
    if max_requests_per_minute is None:
        return None
    normalized_limit = int(max_requests_per_minute)
    if normalized_limit <= 0:
        return None
    api_key_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    normalized_key = "|".join(
        [
            provider_name.strip().lower(),
            base_url.strip().rstrip("/").lower(),
            api_key_digest,
        ]
    )
    return RequestRateLimitSpec(
        key=normalized_key,
        max_requests_per_minute=normalized_limit,
        window_seconds=window_seconds,
    )
