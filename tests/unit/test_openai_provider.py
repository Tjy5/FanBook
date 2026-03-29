from __future__ import annotations

import threading
import time

import httpx
import pytest

from backend.core.providers.base import TranslationProviderError
from backend.core.providers.openai_provider import OpenAITranslationProvider
from backend.core.providers.request_concurrency_limiter import (
    request_concurrency_limiter_registry,
)


class TrackingHandler:
    def __init__(self, *, sleep_seconds: float = 0.05) -> None:
        self.sleep_seconds = sleep_seconds
        self._lock = threading.Lock()
        self.current_active = 0
        self.max_active = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.current_active += 1
            self.max_active = max(self.max_active, self.current_active)
        try:
            time.sleep(self.sleep_seconds)
            return httpx.Response(200, json={"ok": True})
        finally:
            with self._lock:
                self.current_active -= 1


class BlockingHandler:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self.entered.set()
            assert self.release.wait(timeout=2.0)
        return httpx.Response(200, json={"ok": True})


def _build_provider(
    *,
    transport: httpx.BaseTransport,
    base_url: str = "https://api.example.test",
    api_key: str = "test-key",
    hard_global_max_in_flight: int = 8,
    hard_target_max_in_flight: int = 2,
    hard_concurrency_acquire_timeout_seconds: float = 1.0,
) -> OpenAITranslationProvider:
    client = httpx.Client(transport=transport)
    return OpenAITranslationProvider(
        options={
            "api_key": api_key,
            "base_url": base_url,
            "endpoint_capability_detection_enabled": False,
            "hard_global_max_in_flight": hard_global_max_in_flight,
            "hard_target_max_in_flight": hard_target_max_in_flight,
            "hard_concurrency_acquire_timeout_seconds": hard_concurrency_acquire_timeout_seconds,
        },
        http_client=client,
    )


def _run_concurrently(*providers: OpenAITranslationProvider) -> list[Exception]:
    errors: list[Exception] = []
    start_barrier = threading.Barrier(len(providers) + 1)

    def worker(provider: OpenAITranslationProvider) -> None:
        start_barrier.wait()
        try:
            provider._send_payload({"model": provider.model_name})
        except Exception as exc:  # pragma: no cover - asserted via errors
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(provider,)) for provider in providers]
    for thread in threads:
        thread.start()
    start_barrier.wait()
    for thread in threads:
        thread.join(timeout=2.0)
    return errors


def teardown_function() -> None:
    request_concurrency_limiter_registry.clear()


def test_openai_provider_shares_target_concurrency_guard_across_instances() -> None:
    handler = TrackingHandler(sleep_seconds=0.05)
    transport = httpx.MockTransport(handler)
    provider_a = _build_provider(
        transport=transport,
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
    )
    provider_b = _build_provider(
        transport=transport,
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
    )

    try:
        errors = _run_concurrently(provider_a, provider_b)
    finally:
        provider_a.close()
        provider_b.close()

    assert not errors
    assert handler.max_active == 1


def test_openai_provider_allows_parallel_requests_for_different_targets() -> None:
    handler = TrackingHandler(sleep_seconds=0.05)
    transport = httpx.MockTransport(handler)
    provider_a = _build_provider(
        transport=transport,
        base_url="https://api-a.example.test",
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
    )
    provider_b = _build_provider(
        transport=transport,
        base_url="https://api-b.example.test",
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
    )

    try:
        errors = _run_concurrently(provider_a, provider_b)
    finally:
        provider_a.close()
        provider_b.close()

    assert not errors
    assert handler.max_active >= 2


def test_openai_provider_applies_global_concurrency_guard_across_targets() -> None:
    handler = TrackingHandler(sleep_seconds=0.05)
    transport = httpx.MockTransport(handler)
    provider_a = _build_provider(
        transport=transport,
        base_url="https://api-a.example.test",
        hard_global_max_in_flight=1,
        hard_target_max_in_flight=4,
    )
    provider_b = _build_provider(
        transport=transport,
        base_url="https://api-b.example.test",
        hard_global_max_in_flight=1,
        hard_target_max_in_flight=4,
    )

    try:
        errors = _run_concurrently(provider_a, provider_b)
    finally:
        provider_a.close()
        provider_b.close()

    assert not errors
    assert handler.max_active == 1


def test_openai_provider_raises_clear_error_when_target_guard_times_out() -> None:
    handler = BlockingHandler()
    transport = httpx.MockTransport(handler)
    provider_a = _build_provider(
        transport=transport,
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
        hard_concurrency_acquire_timeout_seconds=0.01,
    )
    provider_b = _build_provider(
        transport=transport,
        hard_global_max_in_flight=8,
        hard_target_max_in_flight=1,
        hard_concurrency_acquire_timeout_seconds=0.01,
    )
    thread = threading.Thread(target=lambda: provider_a._send_payload({"model": provider_a.model_name}))

    try:
        thread.start()
        assert handler.entered.wait(timeout=1.0)
        with pytest.raises(TranslationProviderError, match="target concurrency guard"):
            provider_b._send_payload({"model": provider_b.model_name})
    finally:
        handler.release.set()
        thread.join(timeout=2.0)
        provider_a.close()
        provider_b.close()
