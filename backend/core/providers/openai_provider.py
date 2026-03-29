from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Any

import httpx

from backend.core.quality.glossary_store import GlossaryStore
from backend.core.quality.prompt_builder import TranslationPromptBuilder
from backend.storage.endpoint_capability_store import (
    EndpointCapabilitySnapshot,
    EndpointCapabilityStore,
)

from .request_concurrency_limiter import (
    RequestConcurrencyAcquireTimeoutError,
    build_global_concurrency_limit_spec,
    build_target_concurrency_limit_spec,
    request_concurrency_limiter_registry,
)
from .request_rate_limiter import build_rate_limit_spec, request_rate_limiter_registry
from .base import (
    ChunkTranslationItem,
    ChunkTranslationRequest,
    ChunkTranslationResponse,
    RuntimeCapabilityDetection,
    TranslationProvider,
    TranslationProviderError,
    TranslationRequest,
    TranslationResponse,
    validate_chunk_response,
)

_ENDPOINT_CAPABILITY_CACHE: dict[str, tuple[float, RuntimeCapabilityDetection]] = {}
_ENDPOINT_CAPABILITY_CACHE_LOCK = threading.Lock()
_ENDPOINT_CAPABILITY_CACHE_ROOT_OPTION = "_fanbook_endpoint_capability_cache_root"
_DEFAULT_ENDPOINT_CAPABILITY_CACHE_TTL_SECONDS = 21600.0
_DEFAULT_ENDPOINT_CAPABILITY_ERROR_TTL_SECONDS = 900.0
_DEFAULT_HARD_GLOBAL_MAX_IN_FLIGHT = 8
_DEFAULT_HARD_TARGET_MAX_IN_FLIGHT = 2
_DEFAULT_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS = 120.0

# Context-window hints below are intentionally sparse and only cover model IDs
# we can verify from official OpenAI docs.
_OPENAI_MODEL_DIRECTORY_HINTS: dict[str, dict[str, object]] = {
    "gpt-4.1": {"detected_context_window": 1047576},
    "gpt-4.1-2025-04-14": {"detected_context_window": 1047576},
    "gpt-4.1-mini": {"detected_context_window": 1047576},
    "gpt-4.1-mini-2025-04-14": {"detected_context_window": 1047576},
    "gpt-4.1-nano": {"detected_context_window": 1047576},
    "gpt-4.1-nano-2025-04-14": {"detected_context_window": 1047576},
    "gpt-4.5-preview": {"detected_context_window": 128000},
    "gpt-4.5-preview-2025-02-27": {"detected_context_window": 128000},
    "gpt-4o": {"detected_context_window": 128000},
    "gpt-4o-2024-08-06": {"detected_context_window": 128000},
    "gpt-4o-2024-11-20": {"detected_context_window": 128000},
    "gpt-4o-mini": {"detected_context_window": 128000},
    "gpt-4o-mini-2024-07-18": {"detected_context_window": 128000},
    "gpt-5.4": {"detected_context_window": 1050000},
    "gpt-5.4-2026-03-05": {"detected_context_window": 1050000},
    "gpt-5.4-pro": {"detected_context_window": 1050000},
    "gpt-5.4-pro-2026-03-05": {"detected_context_window": 1050000},
    "gpt-5.4-mini": {"detected_context_window": 400000},
    "gpt-5.4-mini-2026-03-17": {"detected_context_window": 400000},
    "gpt-5.4-nano": {"detected_context_window": 400000},
    "gpt-5.4-nano-2026-03-17": {"detected_context_window": 400000},
    "gpt-5": {"detected_context_window": 400000},
    "gpt-5-2025-08-07": {"detected_context_window": 400000},
    "gpt-5.2": {"detected_context_window": 400000},
    "gpt-5.2-pro": {"detected_context_window": 400000},
    "gpt-5.2-pro-2025-12-11": {"detected_context_window": 400000},
    "gpt-5.2-codex": {"detected_context_window": 400000},
    "gpt-5.1": {"detected_context_window": 400000},
    "gpt-5.1-2025-11-13": {"detected_context_window": 400000},
    "gpt-5.1-codex": {"detected_context_window": 400000},
    "gpt-5.1-codex-max": {"detected_context_window": 400000},
    "gpt-5.1-codex-mini": {"detected_context_window": 400000},
    "gpt-5-mini": {"detected_context_window": 400000},
    "gpt-5-mini-2025-08-07": {"detected_context_window": 400000},
    "gpt-5-nano": {"detected_context_window": 400000},
    "gpt-5-nano-2025-08-07": {"detected_context_window": 400000},
    "gpt-5-codex": {"detected_context_window": 400000},
    "gpt-5-codex-2025-09-11": {"detected_context_window": 400000},
    "o1": {"detected_context_window": 200000},
    "o1-2024-12-17": {"detected_context_window": 200000},
    "o1-preview": {"detected_context_window": 128000},
    "o1-preview-2024-09-12": {"detected_context_window": 128000},
    "o1-mini": {"detected_context_window": 128000},
    "o1-mini-2024-09-12": {"detected_context_window": 128000},
    "o1-pro": {"detected_context_window": 200000},
    "o1-pro-2025-03-19": {"detected_context_window": 200000},
    "o3": {"detected_context_window": 200000},
    "o3-2025-04-16": {"detected_context_window": 200000},
    "o3-pro": {"detected_context_window": 200000},
    "o3-pro-2025-06-10": {"detected_context_window": 200000},
    "o3-mini": {"detected_context_window": 200000},
    "o3-mini-2025-01-31": {"detected_context_window": 200000},
    "o4-mini": {"detected_context_window": 200000},
    "o4-mini-2025-04-16": {"detected_context_window": 200000},
}


class OpenAITranslationProvider(TranslationProvider):
    default_model_name = "gpt-5.4"

    @classmethod
    def reset_endpoint_capability_cache(cls) -> None:
        del cls
        with _ENDPOINT_CAPABILITY_CACHE_LOCK:
            _ENDPOINT_CAPABILITY_CACHE.clear()

    def __init__(
        self,
        *,
        model_name: str | None = None,
        options: dict[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(model_name=model_name, options=options)
        injected_client = http_client or self.options.get("http_client")
        if injected_client is not None and not isinstance(injected_client, httpx.Client):
            raise TranslationProviderError("OpenAI provider http_client must be an httpx.Client instance.")
        self._http_client = injected_client or self._build_http_client()
        self._owns_http_client = injected_client is None
        self._request_rate_limiter = self._build_request_rate_limiter()

    @property
    def name(self) -> str:
        return "openai"

    def translate(self, request_payload: TranslationRequest) -> TranslationResponse:
        response_payload = self._send_payload(
            self._build_payload(
                instructions=self._build_instructions(request_payload),
                input_messages=self._build_segment_input(request_payload),
            )
        )
        translated_text = self._extract_output_text(response_payload)
        if not translated_text.strip():
            raise TranslationProviderError("OpenAI API returned an empty translation.")

        return TranslationResponse(
            translated_text=translated_text,
            provider_name=self.name,
            model_name=str(response_payload.get("model", self.model_name)),
        )

    def translate_chunk(
        self,
        request_payload: ChunkTranslationRequest,
    ) -> ChunkTranslationResponse:
        response_payload = self._send_payload(
            self._build_payload(
                instructions=self._build_chunk_instructions(request_payload),
                input_messages=self._build_chunk_input(request_payload),
            )
        )
        output_text = self._extract_output_text(response_payload)
        items = self._parse_chunk_items(output_text)
        response = ChunkTranslationResponse(
            items=tuple(items),
            provider_name=self.name,
            model_name=str(response_payload.get("model", self.model_name)),
        )
        validate_chunk_response(request_payload, response)
        return response

    def detect_runtime_capabilities(self) -> RuntimeCapabilityDetection:
        if not self._endpoint_capability_detection_enabled():
            return RuntimeCapabilityDetection(
                metadata={
                    "strategy": "models_list",
                    "enabled": False,
                    "skipped_reason": "disabled",
                }
            )
        missing_fields = tuple(
            field_name
            for field_name in (
                "api_mode",
                "detected_context_window",
                "structured_output_strength",
                "reasoning_mode",
            )
            if not self._option_present(self.options.get(field_name))
        )
        if not missing_fields:
            return RuntimeCapabilityDetection(
                metadata={
                    "strategy": "models_list",
                    "enabled": True,
                    "skipped_reason": "no_missing_fields",
                }
            )
        api_key = self._api_key()
        if not api_key:
            return RuntimeCapabilityDetection(
                metadata={
                    "strategy": "models_list",
                    "enabled": True,
                    "skipped_reason": "missing_api_key",
                }
            )

        cache_key = self._endpoint_capability_cache_key(api_key=api_key)
        now = time.time()
        with _ENDPOINT_CAPABILITY_CACHE_LOCK:
            cached_entry = _ENDPOINT_CAPABILITY_CACHE.get(cache_key)
            if cached_entry is not None and cached_entry[0] > now:
                return self._filter_runtime_capability_detection(
                    cached_entry[1],
                    missing_fields=missing_fields,
                    cache_hit=True,
                )

        detected = self._detect_runtime_capabilities_uncached(
            api_key=api_key,
            missing_fields=missing_fields,
        )
        cache_ttl_seconds = (
            self._endpoint_capability_detection_ttl_seconds()
            if str(detected.metadata.get("probe_status") or "").strip().lower()
            in {"ok", "partial"}
            else self._endpoint_capability_detection_error_ttl_seconds()
        )
        with _ENDPOINT_CAPABILITY_CACHE_LOCK:
            _ENDPOINT_CAPABILITY_CACHE[cache_key] = (
                now + cache_ttl_seconds,
                detected,
            )
        return self._filter_runtime_capability_detection(
            detected,
            missing_fields=missing_fields,
            cache_hit=False,
        )

    def detect_runtime_metadata(self) -> dict[str, Any]:
        return dict(self.detect_runtime_capabilities().options)

    def update_options(self, options: dict[str, Any]) -> None:
        super().update_options(options)
        self._request_rate_limiter = self._build_request_rate_limiter()

    def _send_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = self._api_key()
        if not api_key:
            raise TranslationProviderError("OpenAI API key is required for the openai provider.")

        endpoint = self._request_endpoint()
        timeout_seconds = float(self.options.get("timeout_seconds", 90.0))
        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        global_guard = self._build_global_request_concurrency_limit_spec()
        target_guard = self._build_target_request_concurrency_limit_spec(api_key=api_key)
        acquire_timeout_seconds = self._hard_concurrency_acquire_timeout_seconds()

        try:
            with self._request_concurrency_guard(
                spec=global_guard,
                scope="global",
                timeout_seconds=acquire_timeout_seconds,
            ):
                with self._request_concurrency_guard(
                    spec=target_guard,
                    scope="target",
                    timeout_seconds=acquire_timeout_seconds,
                ):
                    if self._request_rate_limiter is not None:
                        self._request_rate_limiter.acquire()
                    response = self._http_client.post(
                        endpoint,
                        content=serialized_payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        timeout=timeout_seconds,
                    )
                    response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = self._read_error_message_text(exc.response)
            raise TranslationProviderError(
                f"OpenAI API request failed with status {exc.response.status_code}: {message}"
            ) from exc
        except httpx.RequestError as exc:
            raise TranslationProviderError(f"OpenAI API request failed: {exc}") from exc

        try:
            raw_text = response.content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TranslationProviderError("OpenAI API returned an invalid JSON response.") from exc

        return self._load_response_payload(raw_text)

    def close(self) -> None:
        if not self._owns_http_client:
            return
        self._http_client.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _build_http_client(self) -> httpx.Client:
        max_connections = self._pool_size_option(
            self.options.get("http_max_connections"),
            fallback=self.options.get("global_max_concurrency"),
        )
        max_keepalive_connections = self._pool_size_option(
            self.options.get("http_max_keepalive_connections"),
            fallback=max_connections,
        )
        return httpx.Client(
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
        )

    def _build_request_rate_limiter(self):
        max_requests_per_minute = self.options.get("max_requests_per_minute")
        try:
            normalized_limit = (
                int(max_requests_per_minute)
                if max_requests_per_minute is not None
                else None
            )
        except (TypeError, ValueError):
            normalized_limit = None
        if normalized_limit is None or normalized_limit <= 0:
            return None
        window_seconds = self.options.get("request_rate_limit_window_seconds", 60.0)
        try:
            normalized_window_seconds = float(window_seconds)
        except (TypeError, ValueError):
            normalized_window_seconds = 60.0
        spec = build_rate_limit_spec(
            provider_name=self.name,
            base_url=self._request_endpoint(),
            api_key=self._api_key(),
            max_requests_per_minute=normalized_limit,
            window_seconds=normalized_window_seconds,
        )
        return request_rate_limiter_registry.get(spec)

    @contextmanager
    def _request_concurrency_guard(
        self,
        *,
        spec,
        scope: str,
        timeout_seconds: float | None,
    ):
        limiter = request_concurrency_limiter_registry.get(spec)
        if limiter is None or spec is None:
            yield
            return
        try:
            with limiter.acquire(key=spec.key, timeout_seconds=timeout_seconds):
                yield
        except RequestConcurrencyAcquireTimeoutError as exc:
            timeout_text = (
                f"{float(timeout_seconds):g}s"
                if timeout_seconds is not None
                else "an unspecified timeout"
            )
            raise TranslationProviderError(
                f"OpenAI API request blocked by {scope} concurrency guard after {timeout_text}."
            ) from exc

    def _build_global_request_concurrency_limit_spec(self):
        return build_global_concurrency_limit_spec(
            max_in_flight=self._hard_global_max_in_flight(),
        )

    def _build_target_request_concurrency_limit_spec(self, *, api_key: str):
        return build_target_concurrency_limit_spec(
            provider_name=self.name,
            base_url=self._api_root_url(),
            api_key=api_key,
            max_in_flight=self._hard_target_max_in_flight(),
        )

    def _hard_global_max_in_flight(self) -> int:
        return self._positive_int_option(
            self.options.get("hard_global_max_in_flight"),
            fallback=_DEFAULT_HARD_GLOBAL_MAX_IN_FLIGHT,
        )

    def _hard_target_max_in_flight(self) -> int:
        return self._positive_int_option(
            self.options.get("hard_target_max_in_flight"),
            fallback=_DEFAULT_HARD_TARGET_MAX_IN_FLIGHT,
        )

    def _hard_concurrency_acquire_timeout_seconds(self) -> float:
        raw_value = self.options.get("hard_concurrency_acquire_timeout_seconds")
        try:
            normalized = float(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            normalized = None
        if normalized is None or normalized <= 0:
            return _DEFAULT_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS
        return normalized

    @staticmethod
    def _pool_size_option(value: object, *, fallback: object) -> int:
        option_value = value if value is not None else fallback
        try:
            option_value = int(option_value)
        except (TypeError, ValueError):
            try:
                option_value = int(fallback)
            except (TypeError, ValueError):
                option_value = 30
        return max(1, option_value)

    @staticmethod
    def _positive_int_option(value: object, *, fallback: int) -> int:
        try:
            normalized = int(value) if value is not None else int(fallback)
        except (TypeError, ValueError):
            normalized = int(fallback)
        return max(1, normalized)

    def _build_payload(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._api_mode() == "chat_completions":
            return self._build_chat_completions_payload(
                instructions=instructions,
                input_messages=input_messages,
            )
        return self._build_responses_payload(
            instructions=instructions,
            input_messages=input_messages,
        )

    def _build_responses_payload(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model_name,
            "input": input_messages,
            "instructions": instructions,
        }
        reasoning_effort = self.options.get("reasoning_effort")
        if reasoning_effort is not None:
            reasoning_effort = str(reasoning_effort).strip()
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        max_output_tokens = self.options.get("max_output_tokens")
        if max_output_tokens is not None:
            try:
                payload["max_output_tokens"] = int(max_output_tokens)
            except (TypeError, ValueError):
                pass
        return payload

    def _build_chat_completions_payload(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model_name,
            "messages": self._build_chat_completion_messages(
                instructions=instructions,
                input_messages=input_messages,
            ),
        }
        max_output_tokens = self.options.get("max_output_tokens")
        if max_output_tokens is not None:
            try:
                payload["max_tokens"] = int(max_output_tokens)
            except (TypeError, ValueError):
                pass
        return payload

    def _build_instructions(self, request_payload: TranslationRequest) -> str:
        glossary_store = GlossaryStore.from_text(
            str(self.options.get("glossary", "")) or None
        )
        builder = TranslationPromptBuilder(glossary_store)
        return builder.build(request_payload)

    def _build_chunk_instructions(self, request_payload: ChunkTranslationRequest) -> str:
        glossary_store = GlossaryStore.from_text(
            str(self.options.get("glossary", "")) or None
        )
        builder = TranslationPromptBuilder(glossary_store)
        return builder.build_chunk(request_payload)

    @staticmethod
    def _build_segment_input(request_payload: TranslationRequest) -> list[dict[str, Any]]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": request_payload.text,
                    }
                ],
            }
        ]

    @staticmethod
    def _build_chunk_input(request_payload: ChunkTranslationRequest) -> list[dict[str, Any]]:
        serialized_segments = [
            {
                "segment_id": segment.segment_id,
                "segment_type": segment.segment_type.value,
                "source_text": segment.source_text,
            }
            for segment in request_payload.segments
        ]
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            serialized_segments,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        ]

    def _api_key(self) -> str:
        value = str(self.options.get("api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
        return value

    def _request_endpoint(self) -> str:
        if self._api_mode() == "chat_completions":
            return self._chat_completions_endpoint()
        return self._responses_endpoint()

    def _responses_endpoint(self) -> str:
        normalized = self._api_root_url()
        if normalized.endswith("/responses"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/responses"
        return f"{normalized}/v1/responses"

    def _chat_completions_endpoint(self) -> str:
        normalized = self._api_root_url()
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    def _models_endpoint(self) -> str:
        normalized = self._api_root_url()
        if normalized.endswith("/models"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/models"
        return f"{normalized}/v1/models"

    def _base_url(self) -> str:
        return str(
            self.options.get("base_url")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com"
        ).strip()

    def _api_root_url(self) -> str:
        normalized = self._base_url().rstrip("/")
        for suffix in (
            "/chat/completions",
            "/responses",
            "/models",
        ):
            if normalized.endswith(suffix):
                return normalized[: -len(suffix)]
        return normalized

    def _api_mode(self) -> str:
        raw_value = str(self.options.get("api_mode") or "").strip().lower()
        if raw_value in {"chat", "chat_completion", "chat_completions", "chat-completions"}:
            return "chat_completions"
        return "responses"

    def _endpoint_capability_detection_enabled(self) -> bool:
        raw_value = self.options.get("endpoint_capability_detection_enabled")
        if raw_value is None:
            return True
        return self._as_bool(raw_value, True)

    def _endpoint_capability_detection_timeout_seconds(self) -> float:
        raw_value = self.options.get("endpoint_capability_detection_timeout_seconds")
        try:
            return max(1.0, float(raw_value))
        except (TypeError, ValueError):
            return 5.0

    def _endpoint_capability_detection_ttl_seconds(self) -> float:
        raw_value = self.options.get("endpoint_capability_detection_ttl_seconds")
        try:
            return max(30.0, float(raw_value))
        except (TypeError, ValueError):
            return _DEFAULT_ENDPOINT_CAPABILITY_CACHE_TTL_SECONDS

    def _endpoint_capability_detection_error_ttl_seconds(self) -> float:
        raw_value = self.options.get("endpoint_capability_detection_error_ttl_seconds")
        try:
            return max(30.0, float(raw_value))
        except (TypeError, ValueError):
            return _DEFAULT_ENDPOINT_CAPABILITY_ERROR_TTL_SECONDS

    def _endpoint_capability_cache_root(self) -> str | None:
        raw_value = self.options.get(_ENDPOINT_CAPABILITY_CACHE_ROOT_OPTION)
        if raw_value is None:
            return None
        normalized = str(raw_value).strip()
        return normalized or None

    def _endpoint_capability_store(self) -> EndpointCapabilityStore | None:
        cache_root = self._endpoint_capability_cache_root()
        if not cache_root:
            return None
        return EndpointCapabilityStore(cache_root)

    def _endpoint_capability_cache_key(self, *, api_key: str) -> str:
        return EndpointCapabilityStore.build_cache_key(
            provider_name=self.name,
            models_endpoint=self._models_endpoint(),
            api_key=api_key,
            model_name=self.model_name,
        )

    def _detect_runtime_capabilities_uncached(
        self,
        *,
        api_key: str,
        missing_fields: tuple[str, ...],
    ) -> RuntimeCapabilityDetection:
        snapshot = self._load_cached_endpoint_capability_snapshot(api_key=api_key)
        if snapshot is not None and snapshot.is_fresh():
            detection = self._runtime_capability_detection_from_snapshot(snapshot)
            if not self._snapshot_requires_refresh(
                snapshot=snapshot,
                detection=detection,
                required_fields=missing_fields,
            ):
                metadata = dict(detection.metadata)
                metadata["snapshot_source"] = "persistent_cache"
                return RuntimeCapabilityDetection(
                    options=dict(detection.options),
                    option_sources=dict(detection.option_sources),
                    metadata=metadata,
                )
        snapshot = self._probe_endpoint_capability_snapshot(
            api_key=api_key,
            required_fields=missing_fields,
        )
        self._save_endpoint_capability_snapshot(snapshot)
        detection = self._runtime_capability_detection_from_snapshot(snapshot)
        metadata = dict(detection.metadata)
        metadata["snapshot_source"] = "live_probe"
        return RuntimeCapabilityDetection(
            options=dict(detection.options),
            option_sources=dict(detection.option_sources),
            metadata=metadata,
        )

    def _load_cached_endpoint_capability_snapshot(
        self,
        *,
        api_key: str,
    ) -> EndpointCapabilitySnapshot | None:
        store = self._endpoint_capability_store()
        if store is None:
            return None
        return store.load(self._endpoint_capability_cache_key(api_key=api_key))

    def _save_endpoint_capability_snapshot(
        self,
        snapshot: EndpointCapabilitySnapshot,
    ) -> None:
        store = self._endpoint_capability_store()
        if store is None:
            return
        store.save(snapshot)

    @staticmethod
    def _snapshot_requires_refresh(
        *,
        snapshot: EndpointCapabilitySnapshot,
        detection: RuntimeCapabilityDetection,
        required_fields: tuple[str, ...],
    ) -> bool:
        unresolved_fields = {
            field_name
            for field_name in required_fields
            if field_name not in dict(detection.options)
        }
        if not unresolved_fields:
            return False
        high_confidence_fields = {
            "api_mode",
            "structured_output_strength",
            "reasoning_mode",
        }
        if not unresolved_fields.intersection(high_confidence_fields):
            return False
        return snapshot.verified_capability_metadata is None

    def _probe_endpoint_capability_snapshot(
        self,
        *,
        api_key: str,
        required_fields: tuple[str, ...],
    ) -> EndpointCapabilitySnapshot:
        endpoint = self._models_endpoint()
        models_probe_status = "ok"
        models_error_summary: str | None = None
        model_object: dict[str, Any] | None = None
        model_listed: bool | None = None
        available_model_count: int | None = None
        try:
            response = self._http_client.get(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=self._endpoint_capability_detection_timeout_seconds(),
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            models_probe_status = "error"
            models_error_summary = (
                self._read_error_message_text(exc.response)
                if isinstance(exc, httpx.HTTPStatusError)
                else str(exc)
            )
        else:
            try:
                payload = response.json()
            except ValueError:
                models_probe_status = "error"
                models_error_summary = "models endpoint returned invalid JSON"
            else:
                if not isinstance(payload, dict):
                    models_probe_status = "error"
                    models_error_summary = "models endpoint returned an unexpected payload"
                else:
                    (
                        model_object,
                        model_listed,
                        available_model_count,
                    ) = self._extract_model_directory_entry(
                        payload,
                        model_name=self.model_name,
                    )

        verified_capabilities, verified_capability_metadata = self._probe_verified_capabilities(
            api_key=api_key,
            required_fields=required_fields,
            model_object=model_object,
        )
        verified_probe_status = str(
            (verified_capability_metadata or {}).get("status") or "skipped"
        ).strip().lower()
        overall_probe_status = (
            "ok"
            if models_probe_status == "ok" or verified_probe_status in {"ok", "partial"}
            else "error"
        )
        ttl_seconds = (
            int(self._endpoint_capability_detection_ttl_seconds())
            if overall_probe_status == "ok"
            else int(self._endpoint_capability_detection_error_ttl_seconds())
        )
        error_summary = (
            None
            if overall_probe_status == "ok"
            else models_error_summary
            or str((verified_capability_metadata or {}).get("error_summary") or "").strip()
            or None
        )
        return EndpointCapabilityStore.build_snapshot(
            provider_name=self.name,
            models_endpoint=endpoint,
            api_key=api_key,
            model_name=self.model_name,
            model_listed=model_listed,
            model_object=model_object,
            available_model_count=available_model_count,
            probe_status=overall_probe_status,
            ttl_seconds=ttl_seconds,
            error_summary=error_summary,
            models_probe_status=models_probe_status,
            models_error_summary=models_error_summary,
            verified_capabilities=verified_capabilities or None,
            verified_capability_metadata=verified_capability_metadata,
        )

    @staticmethod
    def _filter_runtime_capability_detection(
        detection: RuntimeCapabilityDetection,
        *,
        missing_fields: tuple[str, ...],
        cache_hit: bool,
    ) -> RuntimeCapabilityDetection:
        allowed_fields = set(missing_fields)
        filtered_options = {
            key: value
            for key, value in dict(detection.options).items()
            if key in allowed_fields
        }
        filtered_option_sources = {
            key: value
            for key, value in dict(detection.option_sources).items()
            if key in filtered_options
        }
        metadata = dict(detection.metadata)
        metadata["cache_hit"] = (
            cache_hit or metadata.get("snapshot_source") == "persistent_cache"
        )
        metadata["requested_fields"] = list(missing_fields)
        metadata["returned_fields"] = sorted(filtered_options)
        return RuntimeCapabilityDetection(
            options=filtered_options,
            option_sources=filtered_option_sources,
            metadata=metadata,
        )

    @classmethod
    def _runtime_capability_detection_from_snapshot(
        cls,
        snapshot: EndpointCapabilitySnapshot,
    ) -> RuntimeCapabilityDetection:
        metadata: dict[str, Any] = {
            "strategy": "models_list",
            "enabled": True,
            "probe_status": snapshot.probe_status,
            "models_probe_status": snapshot.models_probe_status,
            "models_endpoint": snapshot.models_endpoint,
            "model_name": snapshot.model_name,
            "model_listed": snapshot.model_listed,
            "available_model_count": snapshot.available_model_count,
            "retrieved_at": snapshot.retrieved_at,
            "expires_at": snapshot.expires_at,
        }
        if snapshot.error_summary:
            metadata["error_summary"] = snapshot.error_summary
        if snapshot.models_error_summary:
            metadata["models_error_summary"] = snapshot.models_error_summary
        if snapshot.verified_capability_metadata is not None:
            metadata["deep_probe"] = dict(snapshot.verified_capability_metadata)
            deep_probe_status = str(
                snapshot.verified_capability_metadata.get("status") or "unknown"
            ).strip()
            metadata["deep_probe_status"] = deep_probe_status
            metadata["strategy"] = (
                "models_list+deep_probe"
                if snapshot.models_probe_status == "ok"
                else "deep_probe"
            )
        if snapshot.probe_status == "error":
            return RuntimeCapabilityDetection(metadata=metadata)

        detected_options: dict[str, Any] = {}
        option_sources: dict[str, str] = {}

        if snapshot.model_object is not None:
            payload_detected = cls._detect_runtime_metadata_from_model_object(snapshot.model_object)
            for field_name, value in payload_detected.items():
                detected_options[field_name] = value
                option_sources[field_name] = "endpoint_models_payload"

        if snapshot.model_listed:
            catalog_detected = cls._detect_runtime_metadata_from_model_catalog(snapshot.model_name)
            for field_name, value in catalog_detected.items():
                if field_name in detected_options:
                    continue
                detected_options[field_name] = value
                option_sources[field_name] = "endpoint_model_directory"
            if catalog_detected:
                metadata["catalog_match"] = cls._normalize_model_id(snapshot.model_name)

        if snapshot.verified_capabilities is not None:
            for field_name, value in snapshot.verified_capabilities.items():
                detected_options[field_name] = value
                option_sources[field_name] = "endpoint_capability_detection"

        metadata["confidence"] = (
            "high"
            if snapshot.verified_capabilities
            else "medium"
            if detected_options
            else "low"
        )

        return RuntimeCapabilityDetection(
            options=detected_options,
            option_sources=option_sources,
            metadata=metadata,
        )

    def _probe_verified_capabilities(
        self,
        *,
        api_key: str,
        required_fields: tuple[str, ...],
        model_object: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        requested_fields = tuple(
            field_name
            for field_name in required_fields
            if field_name in {"api_mode", "structured_output_strength", "reasoning_mode"}
        )
        if not requested_fields:
            return {}, {"status": "skipped", "requested_fields": []}

        model_detected = (
            self._detect_runtime_metadata_from_model_object(model_object)
            if model_object is not None
            else {}
        )
        preferred_api_mode = self._normalize_probe_api_mode(model_detected.get("api_mode"))
        attempts: dict[str, dict[str, Any]] = {}
        chosen_api_mode: str | None = None

        for api_mode in self._api_mode_probe_order(preferred_api_mode):
            probe_key = f"{api_mode}_basic"
            attempts[probe_key] = self._run_api_mode_probe(api_key=api_key, api_mode=api_mode)
            if attempts[probe_key]["status"] == "supported":
                chosen_api_mode = api_mode
                break

        verified_capabilities: dict[str, Any] = {}
        if chosen_api_mode is not None and "api_mode" in requested_fields:
            verified_capabilities["api_mode"] = chosen_api_mode

        if chosen_api_mode is not None and "structured_output_strength" in requested_fields:
            probe_key = f"{chosen_api_mode}_structured"
            attempts[probe_key] = self._run_structured_output_probe(
                api_key=api_key,
                api_mode=chosen_api_mode,
            )
            structured_status = attempts[probe_key]["status"]
            if structured_status == "supported":
                verified_capabilities["structured_output_strength"] = "strong"
            elif structured_status == "unsupported":
                verified_capabilities["structured_output_strength"] = "weak"

        if chosen_api_mode == "responses" and "reasoning_mode" in requested_fields:
            attempts["responses_reasoning"] = self._run_reasoning_probe(api_key=api_key)
            reasoning_status = attempts["responses_reasoning"]["status"]
            if reasoning_status == "supported":
                verified_capabilities["reasoning_mode"] = "reasoning"
            elif reasoning_status == "unsupported":
                verified_capabilities["reasoning_mode"] = "standard"

        probe_status = self._verified_probe_status(
            verified_capabilities=verified_capabilities,
            attempts=attempts,
        )
        metadata: dict[str, Any] = {
            "status": probe_status,
            "requested_fields": list(requested_fields),
            "attempts": attempts,
        }
        if chosen_api_mode is not None:
            metadata["chosen_api_mode"] = chosen_api_mode
            metadata["supported_api_modes"] = [chosen_api_mode]
        if probe_status == "error":
            error_summary = self._probe_error_summary(attempts)
            if error_summary:
                metadata["error_summary"] = error_summary
        return verified_capabilities, metadata

    @staticmethod
    def _verified_probe_status(
        *,
        verified_capabilities: dict[str, Any],
        attempts: dict[str, dict[str, Any]],
    ) -> str:
        if not attempts:
            return "skipped"
        statuses = {
            str((attempt or {}).get("status") or "error").strip().lower()
            for attempt in attempts.values()
        }
        if verified_capabilities:
            return "ok"
        if "supported" in statuses:
            return "ok"
        if "unsupported" in statuses:
            return "partial"
        if statuses == {"skipped"}:
            return "skipped"
        return "error"

    @staticmethod
    def _probe_error_summary(attempts: dict[str, dict[str, Any]]) -> str | None:
        for attempt in attempts.values():
            summary = str((attempt or {}).get("error_summary") or "").strip()
            if summary:
                return summary
        return None

    @staticmethod
    def _normalize_probe_api_mode(value: object) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized in {"responses", "response"}:
            return "responses"
        if normalized in {"chat", "chat_completion", "chat_completions", "chat-completions"}:
            return "chat_completions"
        return None

    @classmethod
    def _api_mode_probe_order(cls, preferred_api_mode: str | None) -> tuple[str, ...]:
        normalized_preferred = cls._normalize_probe_api_mode(preferred_api_mode)
        if normalized_preferred == "chat_completions":
            return ("chat_completions", "responses")
        return ("responses", "chat_completions")

    def _run_api_mode_probe(
        self,
        *,
        api_key: str,
        api_mode: str,
    ) -> dict[str, Any]:
        if api_mode == "chat_completions":
            return self._execute_probe_request(
                api_key=api_key,
                endpoint=self._chat_completions_endpoint(),
                payload=self._chat_basic_probe_payload(),
                probe_kind="api_mode",
            )
        return self._execute_probe_request(
            api_key=api_key,
            endpoint=self._responses_endpoint(),
            payload=self._responses_basic_probe_payload(),
            probe_kind="api_mode",
        )

    def _run_structured_output_probe(
        self,
        *,
        api_key: str,
        api_mode: str,
    ) -> dict[str, Any]:
        if api_mode == "chat_completions":
            return self._execute_probe_request(
                api_key=api_key,
                endpoint=self._chat_completions_endpoint(),
                payload=self._chat_structured_probe_payload(),
                probe_kind="structured_output",
            )
        return self._execute_probe_request(
            api_key=api_key,
            endpoint=self._responses_endpoint(),
            payload=self._responses_structured_probe_payload(),
            probe_kind="structured_output",
        )

    def _run_reasoning_probe(self, *, api_key: str) -> dict[str, Any]:
        return self._execute_probe_request(
            api_key=api_key,
            endpoint=self._responses_endpoint(),
            payload=self._responses_reasoning_probe_payload(),
            probe_kind="reasoning",
        )

    def _execute_probe_request(
        self,
        *,
        api_key: str,
        endpoint: str,
        payload: dict[str, Any],
        probe_kind: str,
    ) -> dict[str, Any]:
        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            response = self._http_client.post(
                endpoint,
                content=serialized_payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._endpoint_capability_detection_timeout_seconds(),
            )
        except httpx.RequestError as exc:
            return {
                "status": "error",
                "error_summary": str(exc),
            }

        payload_error_summary = self._read_probe_payload_error_text(response)
        if 200 <= response.status_code < 300:
            if payload_error_summary is None:
                return {
                    "status": "supported",
                    "http_status": response.status_code,
                }
            return {
                "status": self._classify_probe_failure(
                    status_code=400,
                    error_summary=payload_error_summary,
                    probe_kind=probe_kind,
                ),
                "http_status": response.status_code,
                "error_summary": payload_error_summary,
            }

        error_summary = self._read_error_message_text(response)
        return {
            "status": self._classify_probe_failure(
                status_code=response.status_code,
                error_summary=error_summary,
                probe_kind=probe_kind,
            ),
            "http_status": response.status_code,
            "error_summary": error_summary,
        }

    @classmethod
    def _classify_probe_failure(
        cls,
        *,
        status_code: int,
        error_summary: str,
        probe_kind: str,
    ) -> str:
        normalized_summary = str(error_summary or "").strip().lower()
        if status_code in {404, 405}:
            return "unsupported"
        if status_code not in {400, 401, 403, 422}:
            return "error"
        if status_code in {401, 403}:
            return "error"
        if probe_kind == "api_mode":
            if cls._summary_contains_any(
                normalized_summary,
                (
                    "unsupported",
                    "not support",
                    "not supported",
                    "unknown url",
                    "no route",
                    "method not allowed",
                    "chat/completions",
                    "responses",
                ),
            ):
                return "unsupported"
            return "error"
        if probe_kind == "structured_output":
            if cls._summary_contains_any(
                normalized_summary,
                (
                    "response_format",
                    "json_schema",
                    "structured",
                    "schema",
                    "format",
                ),
            ) and cls._summary_contains_any(
                normalized_summary,
                (
                    "unsupported",
                    "not support",
                    "not supported",
                    "unknown",
                    "unrecognized",
                    "invalid",
                ),
            ):
                return "unsupported"
            return "error"
        if probe_kind == "reasoning":
            if cls._summary_contains_any(
                normalized_summary,
                (
                    "reasoning",
                    "thinking",
                    "effort",
                ),
            ) and cls._summary_contains_any(
                normalized_summary,
                (
                    "unsupported",
                    "not support",
                    "not supported",
                    "unknown",
                    "unrecognized",
                    "invalid",
                ),
            ):
                return "unsupported"
            return "error"
        return "error"

    @staticmethod
    def _summary_contains_any(summary: str, tokens: tuple[str, ...]) -> bool:
        normalized_summary = str(summary or "").strip().lower()
        return any(token in normalized_summary for token in tokens if token)

    def _responses_basic_probe_payload(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "fanbook capability probe",
                        }
                    ],
                }
            ],
            "max_output_tokens": 1,
        }

    def _responses_structured_probe_payload(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Return a JSON object with ok=true.",
                        }
                    ],
                }
            ],
            "max_output_tokens": 16,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "fanbook_capability_probe",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                        },
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        }

    def _responses_reasoning_probe_payload(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "fanbook capability probe",
                        }
                    ],
                }
            ],
            "max_output_tokens": 1,
            "reasoning": {"effort": "low"},
        }

    def _chat_basic_probe_payload(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "fanbook capability probe"}],
            "max_tokens": 1,
        }

    def _chat_structured_probe_payload(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": "Return a JSON object with ok=true.",
                }
            ],
            "max_tokens": 16,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "fanbook_capability_probe",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                        },
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        }

    @classmethod
    def _extract_output_text(cls, payload: dict[str, Any]) -> str:
        chat_completion_text = cls._extract_chat_completion_text(payload)
        if chat_completion_text:
            return chat_completion_text
        direct_text = payload.get("output_text")
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        collected: list[str] = []
        for item in payload.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                content_type = str(content.get("type", ""))
                if content_type == "output_text":
                    text = content.get("text")
                    if isinstance(text, str) and text:
                        collected.append(text)
                elif content_type == "text":
                    text_value = content.get("text")
                    if isinstance(text_value, dict):
                        text = text_value.get("value")
                        if isinstance(text, str) and text:
                            collected.append(text)
        return "\n".join(part.strip() for part in collected if part.strip())

    @classmethod
    def _extract_chat_completion_text(cls, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return ""
        collected: list[str] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                collected.append(content.strip())
                continue
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") != "text":
                        continue
                    text_value = item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        collected.append(text_value.strip())
        return "\n".join(collected)

    @classmethod
    def _parse_chunk_items(cls, raw_text: str) -> list[ChunkTranslationItem]:
        normalized_text = cls._extract_json_text(raw_text)
        try:
            payload = json.loads(normalized_text)
        except json.JSONDecodeError as exc:
            raise TranslationProviderError("OpenAI API returned invalid JSON for chunk translation.") from exc

        if isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                payload = payload["items"]
            elif isinstance(payload.get("translations"), list):
                payload = payload["translations"]

        if not isinstance(payload, list):
            raise TranslationProviderError("OpenAI API returned an unexpected chunk translation payload.")

        items: list[ChunkTranslationItem] = []
        for entry in payload:
            if not isinstance(entry, dict):
                raise TranslationProviderError("OpenAI API returned a malformed chunk translation item.")
            segment_id = entry.get("segment_id")
            translated_text = entry.get("translated_text")
            try:
                normalized_segment_id = int(segment_id)
            except (TypeError, ValueError) as exc:
                raise TranslationProviderError("Chunk translation item is missing a numeric segment_id.") from exc
            if not isinstance(translated_text, str):
                raise TranslationProviderError(
                    f"Chunk translation item for segment '{normalized_segment_id}' is missing translated_text."
                )
            items.append(
                ChunkTranslationItem(
                    segment_id=normalized_segment_id,
                    translated_text=translated_text,
                )
            )
        return items

    @staticmethod
    def _extract_json_text(raw_text: str) -> str:
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()

        candidates = [stripped]
        for opening, closing in (("[", "]"), ("{", "}")):
            start_index = stripped.find(opening)
            end_index = stripped.rfind(closing)
            if start_index != -1 and end_index > start_index:
                candidates.append(stripped[start_index : end_index + 1].strip())

        for candidate in candidates:
            try:
                json.loads(candidate)
            except json.JSONDecodeError:
                continue
            return candidate
        return stripped

    @classmethod
    def _extract_model_directory_entry(
        cls,
        payload: dict[str, Any],
        *,
        model_name: str,
    ) -> tuple[dict[str, Any] | None, bool, int | None]:
        data = payload.get("data")
        if not isinstance(data, list):
            return None, False, None
        model_object = cls._find_model_object_in_data(data, model_name=model_name)
        return model_object, model_object is not None, len(data)

    @classmethod
    def _detect_runtime_metadata_from_model_object(
        cls,
        model_object: dict[str, Any],
    ) -> dict[str, Any]:
        detected: dict[str, Any] = {}
        api_mode = cls._detect_api_mode(model_object)
        if api_mode is not None:
            detected["api_mode"] = api_mode
        detected_context_window = cls._detect_context_window(model_object)
        if detected_context_window is not None:
            detected["detected_context_window"] = detected_context_window
        reasoning_mode = cls._detect_reasoning_mode(model_object)
        if reasoning_mode is not None:
            detected["reasoning_mode"] = reasoning_mode
        structured_output_strength = cls._detect_structured_output_strength(model_object)
        if structured_output_strength is not None:
            detected["structured_output_strength"] = structured_output_strength
        return detected

    @classmethod
    def _detect_runtime_metadata_from_model_catalog(
        cls,
        model_name: str,
    ) -> dict[str, Any]:
        hint = _OPENAI_MODEL_DIRECTORY_HINTS.get(cls._normalize_model_id(model_name))
        if hint is None:
            return {}
        return dict(hint)

    @classmethod
    def _find_model_object(
        cls,
        payload: dict[str, Any],
        *,
        model_name: str,
    ) -> dict[str, Any] | None:
        data = payload.get("data")
        if not isinstance(data, list):
            return None
        return cls._find_model_object_in_data(data, model_name=model_name)

    @classmethod
    def _find_model_object_in_data(
        cls,
        data: list[object],
        *,
        model_name: str,
    ) -> dict[str, Any] | None:
        normalized_model_name = cls._normalize_model_id(model_name)
        for item in data:
            if not isinstance(item, dict):
                continue
            if cls._normalize_model_id(item.get("id")) == normalized_model_name:
                return item
        return None

    @classmethod
    def _detect_context_window(cls, payload: dict[str, Any]) -> int | None:
        return cls._first_positive_int_for_keys(
            payload,
            {
                "context_window",
                "context_length",
                "max_context_length",
                "max_input_tokens",
                "input_token_limit",
                "max_prompt_tokens",
                "num_ctx",
            },
        )

    @classmethod
    def _detect_reasoning_mode(cls, payload: dict[str, Any]) -> str | None:
        detected = cls._first_bool_for_keys(
            payload,
            {
                "reasoning",
                "supports_reasoning",
                "supports_reasoning_effort",
                "reasoning_enabled",
                "thinking",
                "supports_thinking",
            },
        )
        if detected is True:
            return "reasoning"
        reasoning_value = cls._first_text_for_keys(
            payload,
            {
                "reasoning_mode",
                "reasoning_type",
                "thinking_type",
            },
        )
        if reasoning_value is None:
            return None
        normalized = reasoning_value.strip().lower()
        if normalized in {"reasoning", "thinking", "enabled", "on", "true"}:
            return "reasoning"
        return None

    @classmethod
    def _detect_api_mode(cls, payload: dict[str, Any]) -> str | None:
        values = tuple(
            cls._iter_values_for_keys(
                payload,
                {
                    "api_mode",
                    "api_modes",
                    "endpoint",
                    "endpoints",
                    "supported_endpoint",
                    "supported_endpoints",
                    "supported_api_mode",
                    "supported_api_modes",
                },
            )
        )
        if not values:
            return None
        normalized_tokens = cls._string_tokens(values)
        if "responses" in normalized_tokens:
            return "responses"
        if normalized_tokens.intersection(
            {"chat_completions", "chat/completions", "chat-completions"}
        ):
            return "chat_completions"
        return None

    @classmethod
    def _detect_structured_output_strength(cls, payload: dict[str, Any]) -> str | None:
        detected = cls._first_bool_for_keys(
            payload,
            {
                "structured_outputs",
                "supports_structured_outputs",
                "supports_json_schema",
                "json_schema",
                "response_format_json_schema",
                "supports_response_format",
            },
        )
        if detected is True:
            return "strong"
        if detected is False:
            return "weak"
        text_value = cls._first_text_for_keys(
            payload,
            {
                "structured_output_strength",
                "response_format",
                "output_format",
            },
        )
        if text_value is None:
            return None
        normalized = text_value.strip().lower()
        if normalized in {"strong", "high", "json_schema", "structured_outputs"}:
            return "strong"
        if normalized in {"weak", "low", "text"}:
            return "weak"
        return None

    @classmethod
    def _load_response_payload(cls, raw_text: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = cls._extract_sse_response_payload(raw_text)
            if payload is None:
                raise TranslationProviderError("OpenAI API returned an invalid JSON response.")

        if not isinstance(payload, dict):
            raise TranslationProviderError("OpenAI API returned an invalid JSON response.")
        return payload

    @staticmethod
    def _extract_sse_response_payload(raw_text: str) -> dict[str, Any] | None:
        latest_response_payload: dict[str, Any] | None = None
        for block in raw_text.split("\n\n"):
            data_lines = [
                line[5:].strip()
                for line in block.splitlines()
                if line.startswith("data:")
            ]
            if not data_lines:
                continue

            data_text = "\n".join(data_lines).strip()
            if not data_text or data_text == "[DONE]":
                continue

            try:
                event_payload = json.loads(data_text)
            except json.JSONDecodeError:
                continue
            if not isinstance(event_payload, dict):
                continue

            response_payload = event_payload.get("response")
            if isinstance(response_payload, dict):
                latest_response_payload = response_payload

        return latest_response_payload

    @staticmethod
    def _build_chat_completion_messages(
        *,
        instructions: str,
        input_messages: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        normalized_instructions = instructions.strip()
        if normalized_instructions:
            messages.append(
                {
                    "role": "system",
                    "content": normalized_instructions,
                }
            )
        for message in input_messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "user").strip() or "user"
            content = OpenAITranslationProvider._flatten_input_message_text(message)
            if not content:
                continue
            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )
        return messages

    @staticmethod
    def _flatten_input_message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _read_error_message_text(response: httpx.Response) -> str:
        try:
            raw_body = response.content.decode("utf-8")
        except Exception:
            return response.reason_phrase or "request failed"
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return raw_body or response.reason_phrase or "request failed"

        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return raw_body or response.reason_phrase or "request failed"

    @classmethod
    def _read_probe_payload_error_text(cls, response: httpx.Response) -> str | None:
        try:
            raw_body = response.content.decode("utf-8")
        except Exception:
            return None
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            return raw_body or None

        success_markers = ("choices", "output", "output_text", "id")
        has_success_markers = any(
            key in payload and payload.get(key) not in (None, "", [], {})
            for key in success_markers
        )
        if payload.get("success") is False:
            return cls._probe_payload_message(payload, raw_body)

        normalized_status = str(payload.get("status") or "").strip().lower()
        if normalized_status in {"error", "failed"}:
            return cls._probe_payload_message(payload, raw_body)

        try:
            normalized_code = int(payload.get("code"))
        except (TypeError, ValueError):
            normalized_code = None
        if normalized_code is not None and normalized_code < 0 and not has_success_markers:
            return cls._probe_payload_message(payload, raw_body)
        return None

    @staticmethod
    def _probe_payload_message(payload: dict[str, Any], raw_body: str) -> str | None:
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        return raw_body or None

    @staticmethod
    def _normalize_model_id(value: object) -> str:
        return str(value or "").strip().lower()

    @classmethod
    def _first_positive_int_for_keys(
        cls,
        payload: object,
        keys: set[str],
    ) -> int | None:
        for value in cls._iter_values_for_keys(payload, keys):
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized > 0:
                return normalized
        return None

    @classmethod
    def _first_bool_for_keys(
        cls,
        payload: object,
        keys: set[str],
    ) -> bool | None:
        for value in cls._iter_values_for_keys(payload, keys):
            if isinstance(value, bool):
                return value
            normalized = str(value or "").strip().lower()
            if normalized in {"1", "true", "yes", "on", "enabled"}:
                return True
            if normalized in {"0", "false", "no", "off", "disabled"}:
                return False
        return None

    @classmethod
    def _first_text_for_keys(
        cls,
        payload: object,
        keys: set[str],
    ) -> str | None:
        for value in cls._iter_values_for_keys(payload, keys):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _iter_values_for_keys(
        cls,
        payload: object,
        keys: set[str],
    ):
        normalized_keys = {
            cls._normalize_metadata_key(key)
            for key in keys
            if cls._normalize_metadata_key(key)
        }
        yield from cls._iter_values_for_keys_inner(payload, normalized_keys)

    @classmethod
    def _iter_values_for_keys_inner(
        cls,
        payload: object,
        normalized_keys: set[str],
    ):
        if isinstance(payload, dict):
            for key, value in payload.items():
                if cls._normalize_metadata_key(key) in normalized_keys:
                    yield value
                yield from cls._iter_values_for_keys_inner(value, normalized_keys)
        elif isinstance(payload, list):
            for item in payload:
                yield from cls._iter_values_for_keys_inner(item, normalized_keys)

    @staticmethod
    def _normalize_metadata_key(value: object) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    @classmethod
    def _string_tokens(
        cls,
        payload: object,
    ) -> set[str]:
        del cls
        tokens: set[str] = set()

        def visit(value: object) -> None:
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized:
                    tokens.add(normalized)
                return
            if isinstance(value, dict):
                for nested_value in value.values():
                    visit(nested_value)
                return
            if isinstance(value, list) or isinstance(value, tuple):
                for item in value:
                    visit(item)

        visit(payload)
        return tokens

    @staticmethod
    def _option_present(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _as_bool(value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return bool(default)
