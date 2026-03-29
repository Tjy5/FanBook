from __future__ import annotations

from collections.abc import Callable
import random
import time
from typing import TypeVar

from .error_codes import classify_chunk_issue


ResultT = TypeVar("ResultT")


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 1,
        *,
        retryable_error_checker: Callable[[Exception], bool] | None = None,
        base_delay_seconds: float = 0.0,
        max_delay_seconds: float | None = None,
        jitter_ratio: float = 0.0,
        sleep_func: Callable[[float], None] | None = None,
        random_func: Callable[[], float] | None = None,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.retryable_error_checker = retryable_error_checker
        self.base_delay_seconds = max(0.0, float(base_delay_seconds))
        normalized_max_delay = (
            self.base_delay_seconds if max_delay_seconds is None else float(max_delay_seconds)
        )
        self.max_delay_seconds = max(self.base_delay_seconds, normalized_max_delay)
        self.jitter_ratio = max(0.0, float(jitter_ratio))
        self._sleep_func = sleep_func or time.sleep
        self._random_func = random_func or random.random

    def clone_with(self, *, max_attempts: int | None = None) -> "RetryPolicy":
        return RetryPolicy(
            max_attempts=self.max_attempts if max_attempts is None else max_attempts,
            retryable_error_checker=self.retryable_error_checker,
            base_delay_seconds=self.base_delay_seconds,
            max_delay_seconds=self.max_delay_seconds,
            jitter_ratio=self.jitter_ratio,
            sleep_func=self._sleep_func,
            random_func=self._random_func,
        )

    def run(self, operation: Callable[[], ResultT]) -> ResultT:
        result, _ = self.run_with_attempt_count(operation)
        return result

    def run_with_attempt_count(self, operation: Callable[[], ResultT]) -> tuple[ResultT, int]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation(), attempt
            except Exception as exc:  # pragma: no cover - exercised via caller behavior
                last_error = exc
                if attempt >= self.max_attempts:
                    break
                if (
                    self.retryable_error_checker is not None
                    and not self.retryable_error_checker(exc)
                ):
                    break
                delay_seconds = self._retry_delay_for_attempt(attempt)
                if delay_seconds > 0:
                    self._sleep_func(delay_seconds)
        if last_error is None:  # pragma: no cover - defensive guard
            raise RuntimeError("RetryPolicy failed without capturing an exception.")
        raise last_error

    def _retry_delay_for_attempt(self, attempt: int) -> float:
        if self.base_delay_seconds <= 0:
            return 0.0
        delay_seconds = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** max(0, int(attempt) - 1)),
        )
        if self.jitter_ratio <= 0:
            return delay_seconds
        jitter = delay_seconds * self.jitter_ratio * max(0.0, float(self._random_func()))
        return min(self.max_delay_seconds, delay_seconds + jitter)


def is_retryable_translation_error(exc: Exception) -> bool:
    error_code = classify_chunk_issue(str(exc))
    return error_code in {"rate_limited", "timeout"}
