from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RUNTIME_OPTION_SOURCE_METADATA_KEY = "_fanbook_runtime_option_sources"
_RUNTIME_OPTION_FIELDS: tuple[str, ...] = (
    "runtime_profile",
    "detected_context_window",
    "structured_output_strength",
    "reasoning_mode",
    "api_mode",
    "reasoning_effort",
    "max_requests_per_minute",
    "global_max_concurrency",
    "per_chapter_concurrency",
    "min_per_chapter_concurrency",
    "adaptive_per_chapter_concurrency",
    "max_input_tokens",
    "reserved_output_tokens",
    "max_output_tokens",
    "chunk_target_tokens",
    "context_segments_before",
    "context_segments_after",
    "translation_memory_size",
    "retry_max_attempts",
    "duplicate_text_cache_enabled",
    "duplicate_text_cache_min_chars",
    "dynamic_rate_control_enabled",
    "dynamic_rate_control_initial_global_concurrency",
    "dynamic_rate_control_min_global_concurrency",
    "dynamic_rate_control_scale_up_success_streak",
    "hard_global_max_in_flight",
    "hard_target_max_in_flight",
    "hard_concurrency_acquire_timeout_seconds",
)


@dataclass(slots=True)
class ProviderConfigRequest:
    provider_name: str = "mock"
    model_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    runtime_profile: str | None = None
    detected_context_window: int | None = None
    structured_output_strength: str | None = None
    reasoning_mode: str | None = None
    api_mode: str | None = None
    reasoning_effort: str | None = None
    timeout_seconds: float | None = None
    endpoint_capability_detection_enabled: bool | None = None
    endpoint_capability_detection_timeout_seconds: float | None = None
    endpoint_capability_detection_ttl_seconds: float | None = None
    max_requests_per_minute: int | None = None
    global_max_concurrency: int | None = None
    per_chapter_concurrency: int | None = None
    min_per_chapter_concurrency: int | None = None
    adaptive_per_chapter_concurrency: bool | None = None
    max_input_tokens: int | None = None
    reserved_output_tokens: int | None = None
    max_output_tokens: int | None = None
    chunk_target_tokens: int | None = None
    context_segments_before: int | None = None
    context_segments_after: int | None = None
    translation_memory_size: int | None = None
    retry_max_attempts: int | None = None
    duplicate_text_cache_enabled: bool | None = None
    duplicate_text_cache_min_chars: int | None = None
    dynamic_rate_control_enabled: bool | None = None
    dynamic_rate_control_initial_global_concurrency: int | None = None
    dynamic_rate_control_min_global_concurrency: int | None = None
    dynamic_rate_control_scale_up_success_streak: int | None = None
    hard_global_max_in_flight: int | None = None
    hard_target_max_in_flight: int | None = None
    hard_concurrency_acquire_timeout_seconds: float | None = None
    runtime_option_sources: dict[str, str] = field(default_factory=dict, repr=False)

    def merged_with(
        self,
        *,
        provider_name: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        runtime_profile: str | None = None,
        detected_context_window: int | None = None,
        structured_output_strength: str | None = None,
        reasoning_mode: str | None = None,
        api_mode: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: float | None = None,
        endpoint_capability_detection_enabled: bool | None = None,
        endpoint_capability_detection_timeout_seconds: float | None = None,
        endpoint_capability_detection_ttl_seconds: float | None = None,
        max_requests_per_minute: int | None = None,
        global_max_concurrency: int | None = None,
        per_chapter_concurrency: int | None = None,
        min_per_chapter_concurrency: int | None = None,
        adaptive_per_chapter_concurrency: bool | None = None,
        max_input_tokens: int | None = None,
        reserved_output_tokens: int | None = None,
        max_output_tokens: int | None = None,
        chunk_target_tokens: int | None = None,
        context_segments_before: int | None = None,
        context_segments_after: int | None = None,
        translation_memory_size: int | None = None,
        retry_max_attempts: int | None = None,
        duplicate_text_cache_enabled: bool | None = None,
        duplicate_text_cache_min_chars: int | None = None,
        dynamic_rate_control_enabled: bool | None = None,
        dynamic_rate_control_initial_global_concurrency: int | None = None,
        dynamic_rate_control_min_global_concurrency: int | None = None,
        dynamic_rate_control_scale_up_success_streak: int | None = None,
        hard_global_max_in_flight: int | None = None,
        hard_target_max_in_flight: int | None = None,
        hard_concurrency_acquire_timeout_seconds: float | None = None,
    ) -> "ProviderConfigRequest":
        merged_sources = _merge_runtime_option_sources(
            self,
            overrides={
                "runtime_profile": runtime_profile,
                "detected_context_window": detected_context_window,
                "structured_output_strength": structured_output_strength,
                "reasoning_mode": reasoning_mode,
                "api_mode": api_mode,
                "reasoning_effort": reasoning_effort,
                "max_requests_per_minute": max_requests_per_minute,
                "global_max_concurrency": global_max_concurrency,
                "per_chapter_concurrency": per_chapter_concurrency,
                "min_per_chapter_concurrency": min_per_chapter_concurrency,
                "adaptive_per_chapter_concurrency": adaptive_per_chapter_concurrency,
                "max_input_tokens": max_input_tokens,
                "reserved_output_tokens": reserved_output_tokens,
                "max_output_tokens": max_output_tokens,
                "chunk_target_tokens": chunk_target_tokens,
                "context_segments_before": context_segments_before,
                "context_segments_after": context_segments_after,
                "translation_memory_size": translation_memory_size,
                "retry_max_attempts": retry_max_attempts,
                "duplicate_text_cache_enabled": duplicate_text_cache_enabled,
                "duplicate_text_cache_min_chars": duplicate_text_cache_min_chars,
                "dynamic_rate_control_enabled": dynamic_rate_control_enabled,
                "dynamic_rate_control_initial_global_concurrency": dynamic_rate_control_initial_global_concurrency,
                "dynamic_rate_control_min_global_concurrency": dynamic_rate_control_min_global_concurrency,
                "dynamic_rate_control_scale_up_success_streak": dynamic_rate_control_scale_up_success_streak,
                "hard_global_max_in_flight": hard_global_max_in_flight,
                "hard_target_max_in_flight": hard_target_max_in_flight,
                "hard_concurrency_acquire_timeout_seconds": hard_concurrency_acquire_timeout_seconds,
            },
        )
        return ProviderConfigRequest(
            provider_name=_merge_text(self.provider_name, provider_name, fallback="mock"),
            model_name=_merge_optional_text(self.model_name, model_name),
            api_key=_merge_optional_text(self.api_key, api_key),
            base_url=_merge_optional_text(self.base_url, base_url),
            runtime_profile=_merge_optional_text(self.runtime_profile, runtime_profile),
            detected_context_window=_merge_number(
                self.detected_context_window,
                detected_context_window,
                cast=int,
            ),
            structured_output_strength=_merge_optional_text(
                self.structured_output_strength,
                structured_output_strength,
            ),
            reasoning_mode=_merge_optional_text(self.reasoning_mode, reasoning_mode),
            api_mode=_merge_optional_text(self.api_mode, api_mode),
            reasoning_effort=_merge_optional_text(self.reasoning_effort, reasoning_effort),
            timeout_seconds=_merge_number(self.timeout_seconds, timeout_seconds, cast=float),
            endpoint_capability_detection_enabled=_merge_bool(
                self.endpoint_capability_detection_enabled,
                endpoint_capability_detection_enabled,
            ),
            endpoint_capability_detection_timeout_seconds=_merge_number(
                self.endpoint_capability_detection_timeout_seconds,
                endpoint_capability_detection_timeout_seconds,
                cast=float,
            ),
            endpoint_capability_detection_ttl_seconds=_merge_number(
                self.endpoint_capability_detection_ttl_seconds,
                endpoint_capability_detection_ttl_seconds,
                cast=float,
            ),
            max_requests_per_minute=_merge_number(
                self.max_requests_per_minute,
                max_requests_per_minute,
                cast=int,
            ),
            global_max_concurrency=_merge_number(
                self.global_max_concurrency,
                global_max_concurrency,
                cast=int,
            ),
            per_chapter_concurrency=_merge_number(
                self.per_chapter_concurrency,
                per_chapter_concurrency,
                cast=int,
            ),
            min_per_chapter_concurrency=_merge_number(
                self.min_per_chapter_concurrency,
                min_per_chapter_concurrency,
                cast=int,
            ),
            adaptive_per_chapter_concurrency=_merge_bool(
                self.adaptive_per_chapter_concurrency,
                adaptive_per_chapter_concurrency,
            ),
            max_input_tokens=_merge_number(self.max_input_tokens, max_input_tokens, cast=int),
            reserved_output_tokens=_merge_number(
                self.reserved_output_tokens,
                reserved_output_tokens,
                cast=int,
            ),
            max_output_tokens=_merge_number(self.max_output_tokens, max_output_tokens, cast=int),
            chunk_target_tokens=_merge_number(
                self.chunk_target_tokens,
                chunk_target_tokens,
                cast=int,
            ),
            context_segments_before=_merge_number(
                self.context_segments_before,
                context_segments_before,
                cast=int,
            ),
            context_segments_after=_merge_number(
                self.context_segments_after,
                context_segments_after,
                cast=int,
            ),
            translation_memory_size=_merge_number(
                self.translation_memory_size,
                translation_memory_size,
                cast=int,
            ),
            retry_max_attempts=_merge_number(
                self.retry_max_attempts,
                retry_max_attempts,
                cast=int,
            ),
            duplicate_text_cache_enabled=_merge_bool(
                self.duplicate_text_cache_enabled,
                duplicate_text_cache_enabled,
            ),
            duplicate_text_cache_min_chars=_merge_number(
                self.duplicate_text_cache_min_chars,
                duplicate_text_cache_min_chars,
                cast=int,
            ),
            dynamic_rate_control_enabled=_merge_bool(
                self.dynamic_rate_control_enabled,
                dynamic_rate_control_enabled,
            ),
            dynamic_rate_control_initial_global_concurrency=_merge_number(
                self.dynamic_rate_control_initial_global_concurrency,
                dynamic_rate_control_initial_global_concurrency,
                cast=int,
            ),
            dynamic_rate_control_min_global_concurrency=_merge_number(
                self.dynamic_rate_control_min_global_concurrency,
                dynamic_rate_control_min_global_concurrency,
                cast=int,
            ),
            dynamic_rate_control_scale_up_success_streak=_merge_number(
                self.dynamic_rate_control_scale_up_success_streak,
                dynamic_rate_control_scale_up_success_streak,
                cast=int,
            ),
            hard_global_max_in_flight=_merge_number(
                self.hard_global_max_in_flight,
                hard_global_max_in_flight,
                cast=int,
            ),
            hard_target_max_in_flight=_merge_number(
                self.hard_target_max_in_flight,
                hard_target_max_in_flight,
                cast=int,
            ),
            hard_concurrency_acquire_timeout_seconds=_merge_number(
                self.hard_concurrency_acquire_timeout_seconds,
                hard_concurrency_acquire_timeout_seconds,
                cast=float,
            ),
            runtime_option_sources=merged_sources,
        )

    def options_dict(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self.api_key:
            options["api_key"] = self.api_key
        if self.base_url:
            options["base_url"] = self.base_url
        if self.runtime_profile:
            options["runtime_profile"] = self.runtime_profile
        if self.detected_context_window is not None:
            options["detected_context_window"] = int(self.detected_context_window)
        if self.structured_output_strength:
            options["structured_output_strength"] = self.structured_output_strength
        if self.reasoning_mode:
            options["reasoning_mode"] = self.reasoning_mode
        if self.api_mode:
            options["api_mode"] = self.api_mode
        if self.reasoning_effort:
            options["reasoning_effort"] = self.reasoning_effort
        if self.timeout_seconds is not None:
            options["timeout_seconds"] = float(self.timeout_seconds)
        if self.endpoint_capability_detection_enabled is not None:
            options["endpoint_capability_detection_enabled"] = bool(
                self.endpoint_capability_detection_enabled
            )
        if self.endpoint_capability_detection_timeout_seconds is not None:
            options["endpoint_capability_detection_timeout_seconds"] = float(
                self.endpoint_capability_detection_timeout_seconds
            )
        if self.endpoint_capability_detection_ttl_seconds is not None:
            options["endpoint_capability_detection_ttl_seconds"] = float(
                self.endpoint_capability_detection_ttl_seconds
            )
        if self.max_requests_per_minute is not None:
            options["max_requests_per_minute"] = int(self.max_requests_per_minute)
        if self.global_max_concurrency is not None:
            options["global_max_concurrency"] = int(self.global_max_concurrency)
        if self.per_chapter_concurrency is not None:
            options["per_chapter_concurrency"] = int(self.per_chapter_concurrency)
        if self.min_per_chapter_concurrency is not None:
            options["min_per_chapter_concurrency"] = int(self.min_per_chapter_concurrency)
        if self.adaptive_per_chapter_concurrency is not None:
            options["adaptive_per_chapter_concurrency"] = bool(self.adaptive_per_chapter_concurrency)
        if self.max_input_tokens is not None:
            options["max_input_tokens"] = int(self.max_input_tokens)
        if self.reserved_output_tokens is not None:
            options["reserved_output_tokens"] = int(self.reserved_output_tokens)
        if self.max_output_tokens is not None:
            options["max_output_tokens"] = int(self.max_output_tokens)
        if self.chunk_target_tokens is not None:
            options["chunk_target_tokens"] = int(self.chunk_target_tokens)
        if self.context_segments_before is not None:
            options["context_segments_before"] = int(self.context_segments_before)
        if self.context_segments_after is not None:
            options["context_segments_after"] = int(self.context_segments_after)
        if self.translation_memory_size is not None:
            options["translation_memory_size"] = int(self.translation_memory_size)
        if self.retry_max_attempts is not None:
            options["retry_max_attempts"] = int(self.retry_max_attempts)
        if self.duplicate_text_cache_enabled is not None:
            options["duplicate_text_cache_enabled"] = bool(self.duplicate_text_cache_enabled)
        if self.duplicate_text_cache_min_chars is not None:
            options["duplicate_text_cache_min_chars"] = int(self.duplicate_text_cache_min_chars)
        if self.dynamic_rate_control_enabled is not None:
            options["dynamic_rate_control_enabled"] = bool(self.dynamic_rate_control_enabled)
        if self.dynamic_rate_control_initial_global_concurrency is not None:
            options["dynamic_rate_control_initial_global_concurrency"] = int(
                self.dynamic_rate_control_initial_global_concurrency
            )
        if self.dynamic_rate_control_min_global_concurrency is not None:
            options["dynamic_rate_control_min_global_concurrency"] = int(
                self.dynamic_rate_control_min_global_concurrency
            )
        if self.dynamic_rate_control_scale_up_success_streak is not None:
            options["dynamic_rate_control_scale_up_success_streak"] = int(
                self.dynamic_rate_control_scale_up_success_streak
            )
        if self.hard_global_max_in_flight is not None:
            options["hard_global_max_in_flight"] = int(self.hard_global_max_in_flight)
        if self.hard_target_max_in_flight is not None:
            options["hard_target_max_in_flight"] = int(self.hard_target_max_in_flight)
        if self.hard_concurrency_acquire_timeout_seconds is not None:
            options["hard_concurrency_acquire_timeout_seconds"] = float(
                self.hard_concurrency_acquire_timeout_seconds
            )
        source_metadata = {
            field_name: source
            for field_name, source in _effective_runtime_option_sources(self).items()
            if field_name in options
        }
        if source_metadata:
            options[RUNTIME_OPTION_SOURCE_METADATA_KEY] = source_metadata
        return options


def _merge_text(current: str | None, override: str | None, *, fallback: str) -> str:
    if override is not None and override.strip():
        return override.strip()
    if current is not None and current.strip():
        return current.strip()
    return fallback


def _merge_optional_text(current: str | None, override: str | None) -> str | None:
    if override is not None:
        normalized = override.strip()
        if normalized:
            return normalized
        return current
    if current is None:
        return None
    normalized_current = current.strip()
    return normalized_current or None


def _merge_number(
    current: int | float | None,
    override: int | float | None,
    *,
    cast,
) -> Any:
    if override is not None:
        return cast(override)
    if current is None:
        return None
    return cast(current)


def _merge_bool(current: bool | None, override: bool | None) -> bool | None:
    if override is not None:
        return bool(override)
    if current is None:
        return None
    return bool(current)


def _effective_runtime_option_sources(
    provider: ProviderConfigRequest,
    *,
    fallback_label: str = "provider_config",
) -> dict[str, str]:
    normalized_sources: dict[str, str] = {}
    for field_name, source in dict(provider.runtime_option_sources).items():
        if field_name not in _RUNTIME_OPTION_FIELDS:
            continue
        if not _option_value_is_present(getattr(provider, field_name)):
            continue
        normalized_source = str(source or "").strip()
        if normalized_source:
            normalized_sources[field_name] = normalized_source
    for field_name in _RUNTIME_OPTION_FIELDS:
        if field_name in normalized_sources:
            continue
        if not _option_value_is_present(getattr(provider, field_name)):
            continue
        normalized_sources[field_name] = fallback_label
    return normalized_sources


def _merge_runtime_option_sources(
    provider: ProviderConfigRequest,
    *,
    overrides: dict[str, Any],
) -> dict[str, str]:
    merged_sources = _effective_runtime_option_sources(provider)
    for field_name, override_value in overrides.items():
        if field_name not in _RUNTIME_OPTION_FIELDS:
            continue
        if _option_value_is_present(override_value):
            merged_sources[field_name] = "request_override"
    return merged_sources


def _option_value_is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True
