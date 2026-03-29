from __future__ import annotations

import pytest

from backend.core.translation.retry_policy import (
    RetryPolicy,
    is_retryable_translation_error,
)


def test_retry_policy_applies_backoff_to_retryable_errors() -> None:
    attempts = {"count": 0}
    sleeps: list[float] = []

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("OpenAI API request failed with status 429: rate limit")
        return "ok"

    policy = RetryPolicy(
        max_attempts=2,
        retryable_error_checker=is_retryable_translation_error,
        base_delay_seconds=1.0,
        max_delay_seconds=8.0,
        jitter_ratio=0.0,
        sleep_func=sleeps.append,
    )

    result, attempt_count = policy.run_with_attempt_count(operation)

    assert result == "ok"
    assert attempt_count == 2
    assert sleeps == [1.0]


def test_retry_policy_stops_immediately_for_non_retryable_errors() -> None:
    sleeps: list[float] = []
    policy = RetryPolicy(
        max_attempts=3,
        retryable_error_checker=is_retryable_translation_error,
        base_delay_seconds=1.0,
        max_delay_seconds=8.0,
        jitter_ratio=0.0,
        sleep_func=sleeps.append,
    )

    with pytest.raises(RuntimeError, match="invalid json"):
        policy.run(lambda: (_ for _ in ()).throw(RuntimeError("invalid json")))

    assert not sleeps


def test_retry_policy_clone_with_preserves_backoff_configuration() -> None:
    policy = RetryPolicy(
        max_attempts=2,
        retryable_error_checker=is_retryable_translation_error,
        base_delay_seconds=0.5,
        max_delay_seconds=4.0,
        jitter_ratio=0.1,
    )

    cloned = policy.clone_with(max_attempts=5)

    assert cloned.max_attempts == 5
    assert cloned.base_delay_seconds == 0.5
    assert cloned.max_delay_seconds == 4.0
    assert cloned.jitter_ratio == 0.1
    assert cloned.retryable_error_checker is is_retryable_translation_error
