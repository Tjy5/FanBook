from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore


DEFAULT_GLOBAL_MAX_CONCURRENCY = 10
DEFAULT_PER_CHAPTER_CONCURRENCY = 4
DEFAULT_MIN_PER_CHAPTER_CONCURRENCY = 1
DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY = True
DEFAULT_MAX_INPUT_TOKENS = 12000
DEFAULT_RESERVED_OUTPUT_TOKENS = 1200
DEFAULT_MAX_OUTPUT_TOKENS = 1800
DEFAULT_CHUNK_TARGET_TOKENS = 900
DEFAULT_CONTEXT_SEGMENTS_BEFORE = 1
DEFAULT_CONTEXT_SEGMENTS_AFTER = 1
DEFAULT_TRANSLATION_MEMORY_SIZE = 2
DEFAULT_RETRY_MAX_ATTEMPTS = 2
DEFAULT_DUPLICATE_TEXT_CACHE_ENABLED = True
DEFAULT_DUPLICATE_TEXT_CACHE_MIN_CHARS = 12
DEFAULT_DYNAMIC_RATE_CONTROL_ENABLED = False
DEFAULT_DYNAMIC_RATE_CONTROL_INITIAL_GLOBAL_CONCURRENCY = 4
DEFAULT_DYNAMIC_RATE_CONTROL_MIN_GLOBAL_CONCURRENCY = 1
DEFAULT_DYNAMIC_RATE_CONTROL_SCALE_UP_SUCCESS_STREAK = 3
DEFAULT_HARD_GLOBAL_MAX_IN_FLIGHT: int | None = None
DEFAULT_HARD_TARGET_MAX_IN_FLIGHT: int | None = None
DEFAULT_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS: float | None = None
DEFAULT_RUNTIME_PROFILE = "generic_safe"
DEFAULT_RUNTIME_PROFILE_SOURCE = "default"
RUNTIME_OPTION_SOURCE_METADATA_KEY = "_fanbook_runtime_option_sources"
RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION = "_fanbook_runtime_profile_override_store_root"


@dataclass(slots=True, frozen=True)
class TranslationRuntimePreset:
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


RUNTIME_PROFILES: dict[str, TranslationRuntimePreset] = {
    "generic_safe": TranslationRuntimePreset(
        global_max_concurrency=10,
        per_chapter_concurrency=4,
        min_per_chapter_concurrency=1,
        max_input_tokens=12000,
        reserved_output_tokens=1200,
        max_output_tokens=1800,
        chunk_target_tokens=900,
        context_segments_before=1,
        context_segments_after=1,
        translation_memory_size=2,
        retry_max_attempts=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=12,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=4,
        dynamic_rate_control_min_global_concurrency=1,
        dynamic_rate_control_scale_up_success_streak=3,
    ),
    "generic_large_context": TranslationRuntimePreset(
        global_max_concurrency=24,
        per_chapter_concurrency=10,
        min_per_chapter_concurrency=2,
        max_input_tokens=16000,
        reserved_output_tokens=1600,
        max_output_tokens=2400,
        chunk_target_tokens=2200,
        context_segments_before=1,
        context_segments_after=1,
        translation_memory_size=2,
        retry_max_attempts=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=12,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=8,
        dynamic_rate_control_min_global_concurrency=2,
        dynamic_rate_control_scale_up_success_streak=3,
    ),
    "generic_low_latency": TranslationRuntimePreset(
        global_max_concurrency=12,
        per_chapter_concurrency=4,
        min_per_chapter_concurrency=1,
        max_input_tokens=10000,
        reserved_output_tokens=1000,
        max_output_tokens=1600,
        chunk_target_tokens=700,
        context_segments_before=1,
        context_segments_after=0,
        translation_memory_size=1,
        retry_max_attempts=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=12,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=5,
        dynamic_rate_control_min_global_concurrency=1,
        dynamic_rate_control_scale_up_success_streak=2,
    ),
    "generic_reasoning": TranslationRuntimePreset(
        global_max_concurrency=8,
        per_chapter_concurrency=3,
        min_per_chapter_concurrency=1,
        max_input_tokens=14000,
        reserved_output_tokens=2200,
        max_output_tokens=2800,
        chunk_target_tokens=1100,
        context_segments_before=1,
        context_segments_after=1,
        translation_memory_size=2,
        retry_max_attempts=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=12,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=3,
        dynamic_rate_control_min_global_concurrency=1,
        dynamic_rate_control_scale_up_success_streak=3,
    ),
    "generic_rate_limited": TranslationRuntimePreset(
        global_max_concurrency=4,
        per_chapter_concurrency=2,
        min_per_chapter_concurrency=1,
        max_input_tokens=10000,
        reserved_output_tokens=1200,
        max_output_tokens=1600,
        chunk_target_tokens=800,
        context_segments_before=1,
        context_segments_after=1,
        translation_memory_size=2,
        retry_max_attempts=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=12,
        dynamic_rate_control_enabled=True,
        dynamic_rate_control_initial_global_concurrency=2,
        dynamic_rate_control_min_global_concurrency=1,
        dynamic_rate_control_scale_up_success_streak=4,
    ),
    "novel_consistency": TranslationRuntimePreset(
        global_max_concurrency=6,
        per_chapter_concurrency=1,
        min_per_chapter_concurrency=1,
        max_input_tokens=14000,
        reserved_output_tokens=1800,
        max_output_tokens=2200,
        chunk_target_tokens=1600,
        context_segments_before=3,
        context_segments_after=1,
        translation_memory_size=8,
        retry_max_attempts=3,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=16,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=2,
        dynamic_rate_control_min_global_concurrency=1,
        dynamic_rate_control_scale_up_success_streak=4,
    ),
}

MODEL_FAMILY_RUNTIME_PROFILE_FALLBACKS: tuple[tuple[str, str], ...] = (
    ("o1", "generic_reasoning"),
    ("o3", "generic_reasoning"),
    ("qwq", "generic_reasoning"),
    ("reasoning", "generic_reasoning"),
    ("reasoner", "generic_reasoning"),
    ("deepseek-r1", "generic_reasoning"),
)

MODEL_OR_ENDPOINT_RUNTIME_PROFILE_OVERRIDES: dict[str, str] = {}


@dataclass(slots=True, frozen=True)
class TranslationRuntimeSettings:
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE
    runtime_profile_source: str = DEFAULT_RUNTIME_PROFILE_SOURCE
    api_mode: str = "responses"
    max_requests_per_minute: int | None = None
    detected_context_window: int | None = None
    structured_output_strength: str | None = None
    reasoning_mode: str | None = None
    global_max_concurrency: int = DEFAULT_GLOBAL_MAX_CONCURRENCY
    per_chapter_concurrency: int = DEFAULT_PER_CHAPTER_CONCURRENCY
    min_per_chapter_concurrency: int = DEFAULT_MIN_PER_CHAPTER_CONCURRENCY
    adaptive_per_chapter_concurrency: bool = DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS
    reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    chunk_target_tokens: int = DEFAULT_CHUNK_TARGET_TOKENS
    context_segments_before: int = DEFAULT_CONTEXT_SEGMENTS_BEFORE
    context_segments_after: int = DEFAULT_CONTEXT_SEGMENTS_AFTER
    translation_memory_size: int = DEFAULT_TRANSLATION_MEMORY_SIZE
    retry_max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS
    duplicate_text_cache_enabled: bool = DEFAULT_DUPLICATE_TEXT_CACHE_ENABLED
    duplicate_text_cache_min_chars: int = DEFAULT_DUPLICATE_TEXT_CACHE_MIN_CHARS
    dynamic_rate_control_enabled: bool = DEFAULT_DYNAMIC_RATE_CONTROL_ENABLED
    dynamic_rate_control_initial_global_concurrency: int = DEFAULT_DYNAMIC_RATE_CONTROL_INITIAL_GLOBAL_CONCURRENCY
    dynamic_rate_control_min_global_concurrency: int = DEFAULT_DYNAMIC_RATE_CONTROL_MIN_GLOBAL_CONCURRENCY
    dynamic_rate_control_scale_up_success_streak: int = DEFAULT_DYNAMIC_RATE_CONTROL_SCALE_UP_SUCCESS_STREAK
    hard_global_max_in_flight: int | None = DEFAULT_HARD_GLOBAL_MAX_IN_FLIGHT
    hard_target_max_in_flight: int | None = DEFAULT_HARD_TARGET_MAX_IN_FLIGHT
    hard_concurrency_acquire_timeout_seconds: float | None = DEFAULT_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS
    runtime_setting_sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_options(
        cls,
        options: Mapping[str, Any] | None,
        *,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> "TranslationRuntimeSettings":
        data = dict(options or {})
        option_sources = _read_runtime_option_sources(data)
        api_mode = normalize_api_mode(data.get("api_mode")) or "responses"
        api_mode_source = _option_source(data, option_sources, "api_mode") or "default"
        structured_output_strength = normalize_structured_output_strength(
            data.get("structured_output_strength")
        )
        structured_output_strength_source = _option_source(
            data,
            option_sources,
            "structured_output_strength",
        )
        if structured_output_strength is None:
            structured_output_strength = infer_structured_output_strength(api_mode=api_mode)
            structured_output_strength_source = f"inferred_from_api_mode:{api_mode_source}"
        reasoning_mode = normalize_reasoning_mode(data.get("reasoning_mode"))
        reasoning_mode_source = _option_source(data, option_sources, "reasoning_mode")
        if reasoning_mode is None:
            reasoning_mode = infer_reasoning_mode(
                model_name=model_name,
                reasoning_effort=data.get("reasoning_effort"),
            )
            reasoning_effort_source = _option_source(
                data,
                option_sources,
                "reasoning_effort",
            )
            reasoning_mode_source = (
                f"inferred_from_reasoning_effort:{reasoning_effort_source}"
                if reasoning_effort_source is not None
                and _option_value_is_present(data.get("reasoning_effort"))
                else "default"
            )
        detected_context_window = _optional_int(data.get("detected_context_window"))
        detected_context_window_source = _option_source(
            data,
            option_sources,
            "detected_context_window",
        )
        max_requests_per_minute = _optional_int(data.get("max_requests_per_minute"))
        max_requests_per_minute_source = _option_source(
            data,
            option_sources,
            "max_requests_per_minute",
        )
        resolved_profile_name, resolved_profile_source, preset = resolve_runtime_profile(
            options=data,
            provider_name=provider_name,
            model_name=model_name,
            api_mode=api_mode,
            max_requests_per_minute=max_requests_per_minute,
            detected_context_window=detected_context_window,
            structured_output_strength=structured_output_strength,
            reasoning_mode=reasoning_mode,
        )
        runtime_profile_value_source = _runtime_profile_value_source(
            resolved_profile_name=resolved_profile_name,
            resolved_profile_source=resolved_profile_source,
            explicit_source=_option_source(data, option_sources, "runtime_profile"),
        )
        if reasoning_mode == "standard" and resolved_profile_name == "generic_reasoning":
            reasoning_mode = "reasoning"
            reasoning_mode_source = _append_source_note(
                reasoning_mode_source or "default",
                f"overridden_by_runtime_profile:{resolved_profile_name}",
            )
        preset_source = (
            f"runtime_profile:{resolved_profile_name}:{runtime_profile_value_source}"
        )
        capped_max_input_tokens = _cap_max_input_tokens(
            preset.max_input_tokens,
            detected_context_window=detected_context_window,
        )
        max_input_tokens, max_input_tokens_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("max_input_tokens",),
            preset=capped_max_input_tokens,
            default=DEFAULT_MAX_INPUT_TOKENS,
            minimum=256,
            preset_source=preset_source,
        )
        if (
            _option_source(data, option_sources, "max_input_tokens") is None
            and detected_context_window is not None
            and preset.max_input_tokens is not None
            and int(capped_max_input_tokens or 0) < int(preset.max_input_tokens)
        ):
            max_input_tokens_source = _append_source_note(
                max_input_tokens_source,
                "bounded_by_detected_context_window",
            )
        global_max_concurrency, global_max_concurrency_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("global_max_concurrency", "max_concurrency"),
            preset=preset.global_max_concurrency,
            default=DEFAULT_GLOBAL_MAX_CONCURRENCY,
            minimum=1,
            preset_source=preset_source,
        )
        per_chapter_concurrency, per_chapter_concurrency_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("per_chapter_concurrency",),
            preset=preset.per_chapter_concurrency,
            default=DEFAULT_PER_CHAPTER_CONCURRENCY,
            minimum=1,
            preset_source=preset_source,
        )
        min_per_chapter_concurrency, min_per_chapter_concurrency_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("min_per_chapter_concurrency",),
            preset=preset.min_per_chapter_concurrency,
            default=DEFAULT_MIN_PER_CHAPTER_CONCURRENCY,
            minimum=1,
            preset_source=preset_source,
        )
        adaptive_per_chapter_concurrency, adaptive_per_chapter_concurrency_source = _resolve_bool_with_source(
            data=data,
            option_sources=option_sources,
            keys=("adaptive_per_chapter_concurrency",),
            preset=preset.adaptive_per_chapter_concurrency,
            default=DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY,
            preset_source=preset_source,
        )
        reserved_output_tokens, reserved_output_tokens_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("reserved_output_tokens",),
            preset=preset.reserved_output_tokens,
            default=DEFAULT_RESERVED_OUTPUT_TOKENS,
            minimum=64,
            preset_source=preset_source,
        )
        max_output_tokens, max_output_tokens_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("max_output_tokens",),
            preset=preset.max_output_tokens,
            default=DEFAULT_MAX_OUTPUT_TOKENS,
            minimum=64,
            preset_source=preset_source,
        )
        chunk_target_tokens, chunk_target_tokens_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("chunk_target_tokens",),
            preset=preset.chunk_target_tokens,
            default=DEFAULT_CHUNK_TARGET_TOKENS,
            minimum=64,
            preset_source=preset_source,
        )
        context_segments_before, context_segments_before_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("context_segments_before",),
            preset=preset.context_segments_before,
            default=DEFAULT_CONTEXT_SEGMENTS_BEFORE,
            minimum=0,
            preset_source=preset_source,
        )
        context_segments_after, context_segments_after_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("context_segments_after",),
            preset=preset.context_segments_after,
            default=DEFAULT_CONTEXT_SEGMENTS_AFTER,
            minimum=0,
            preset_source=preset_source,
        )
        translation_memory_size, translation_memory_size_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("translation_memory_size",),
            preset=preset.translation_memory_size,
            default=DEFAULT_TRANSLATION_MEMORY_SIZE,
            minimum=0,
            preset_source=preset_source,
        )
        retry_max_attempts, retry_max_attempts_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("retry_max_attempts",),
            preset=preset.retry_max_attempts,
            default=DEFAULT_RETRY_MAX_ATTEMPTS,
            minimum=1,
            preset_source=preset_source,
        )
        duplicate_text_cache_enabled, duplicate_text_cache_enabled_source = _resolve_bool_with_source(
            data=data,
            option_sources=option_sources,
            keys=("duplicate_text_cache_enabled",),
            preset=preset.duplicate_text_cache_enabled,
            default=DEFAULT_DUPLICATE_TEXT_CACHE_ENABLED,
            preset_source=preset_source,
        )
        duplicate_text_cache_min_chars, duplicate_text_cache_min_chars_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("duplicate_text_cache_min_chars",),
            preset=preset.duplicate_text_cache_min_chars,
            default=DEFAULT_DUPLICATE_TEXT_CACHE_MIN_CHARS,
            minimum=1,
            preset_source=preset_source,
        )
        dynamic_rate_control_enabled, dynamic_rate_control_enabled_source = _resolve_bool_with_source(
            data=data,
            option_sources=option_sources,
            keys=("dynamic_rate_control_enabled",),
            preset=preset.dynamic_rate_control_enabled,
            default=DEFAULT_DYNAMIC_RATE_CONTROL_ENABLED,
            preset_source=preset_source,
        )
        dynamic_rate_control_initial_global_concurrency, dynamic_rate_control_initial_global_concurrency_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("dynamic_rate_control_initial_global_concurrency",),
            preset=preset.dynamic_rate_control_initial_global_concurrency,
            default=DEFAULT_DYNAMIC_RATE_CONTROL_INITIAL_GLOBAL_CONCURRENCY,
            minimum=1,
            preset_source=preset_source,
        )
        dynamic_rate_control_min_global_concurrency, dynamic_rate_control_min_global_concurrency_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("dynamic_rate_control_min_global_concurrency",),
            preset=preset.dynamic_rate_control_min_global_concurrency,
            default=DEFAULT_DYNAMIC_RATE_CONTROL_MIN_GLOBAL_CONCURRENCY,
            minimum=1,
            preset_source=preset_source,
        )
        dynamic_rate_control_scale_up_success_streak, dynamic_rate_control_scale_up_success_streak_source = _resolve_int_with_source(
            data=data,
            option_sources=option_sources,
            keys=("dynamic_rate_control_scale_up_success_streak",),
            preset=preset.dynamic_rate_control_scale_up_success_streak,
            default=DEFAULT_DYNAMIC_RATE_CONTROL_SCALE_UP_SUCCESS_STREAK,
            minimum=1,
            preset_source=preset_source,
        )
        hard_global_max_in_flight = _optional_int(data.get("hard_global_max_in_flight"))
        hard_global_max_in_flight_source = _option_source(
            data,
            option_sources,
            "hard_global_max_in_flight",
        )
        if hard_global_max_in_flight is None and preset.hard_global_max_in_flight is not None:
            hard_global_max_in_flight = max(1, int(preset.hard_global_max_in_flight))
            hard_global_max_in_flight_source = _normalize_preset_source(preset_source)
        hard_target_max_in_flight = _optional_int(data.get("hard_target_max_in_flight"))
        hard_target_max_in_flight_source = _option_source(
            data,
            option_sources,
            "hard_target_max_in_flight",
        )
        if hard_target_max_in_flight is None and preset.hard_target_max_in_flight is not None:
            hard_target_max_in_flight = max(1, int(preset.hard_target_max_in_flight))
            hard_target_max_in_flight_source = _normalize_preset_source(preset_source)
        hard_concurrency_acquire_timeout_seconds = _optional_float(
            data.get("hard_concurrency_acquire_timeout_seconds")
        )
        hard_concurrency_acquire_timeout_seconds_source = _option_source(
            data,
            option_sources,
            "hard_concurrency_acquire_timeout_seconds",
        )
        if (
            hard_concurrency_acquire_timeout_seconds is None
            and preset.hard_concurrency_acquire_timeout_seconds is not None
        ):
            hard_concurrency_acquire_timeout_seconds = max(
                0.001,
                float(preset.hard_concurrency_acquire_timeout_seconds),
            )
            hard_concurrency_acquire_timeout_seconds_source = _normalize_preset_source(
                preset_source
            )
        runtime_setting_sources: dict[str, str] = {
            "runtime_profile": runtime_profile_value_source,
            "api_mode": api_mode_source,
            "structured_output_strength": structured_output_strength_source or "default",
            "reasoning_mode": reasoning_mode_source or "default",
            "global_max_concurrency": global_max_concurrency_source,
            "per_chapter_concurrency": per_chapter_concurrency_source,
            "min_per_chapter_concurrency": min_per_chapter_concurrency_source,
            "adaptive_per_chapter_concurrency": adaptive_per_chapter_concurrency_source,
            "max_input_tokens": max_input_tokens_source,
            "reserved_output_tokens": reserved_output_tokens_source,
            "max_output_tokens": max_output_tokens_source,
            "chunk_target_tokens": chunk_target_tokens_source,
            "context_segments_before": context_segments_before_source,
            "context_segments_after": context_segments_after_source,
            "translation_memory_size": translation_memory_size_source,
            "retry_max_attempts": retry_max_attempts_source,
            "duplicate_text_cache_enabled": duplicate_text_cache_enabled_source,
            "duplicate_text_cache_min_chars": duplicate_text_cache_min_chars_source,
            "dynamic_rate_control_enabled": dynamic_rate_control_enabled_source,
            "dynamic_rate_control_initial_global_concurrency": dynamic_rate_control_initial_global_concurrency_source,
            "dynamic_rate_control_min_global_concurrency": dynamic_rate_control_min_global_concurrency_source,
            "dynamic_rate_control_scale_up_success_streak": dynamic_rate_control_scale_up_success_streak_source,
        }
        if hard_global_max_in_flight is not None:
            runtime_setting_sources["hard_global_max_in_flight"] = (
                hard_global_max_in_flight_source or "option"
            )
        if hard_target_max_in_flight is not None:
            runtime_setting_sources["hard_target_max_in_flight"] = (
                hard_target_max_in_flight_source or "option"
            )
        if hard_concurrency_acquire_timeout_seconds is not None:
            runtime_setting_sources["hard_concurrency_acquire_timeout_seconds"] = (
                hard_concurrency_acquire_timeout_seconds_source or "option"
            )
        if max_requests_per_minute is not None:
            runtime_setting_sources["max_requests_per_minute"] = (
                max_requests_per_minute_source or "option"
            )
        if detected_context_window is not None:
            runtime_setting_sources["detected_context_window"] = (
                detected_context_window_source or "option"
            )
        settings = cls(
            runtime_profile=resolved_profile_name,
            runtime_profile_source=resolved_profile_source,
            api_mode=api_mode,
            max_requests_per_minute=max_requests_per_minute,
            detected_context_window=detected_context_window,
            structured_output_strength=structured_output_strength,
            reasoning_mode=reasoning_mode,
            global_max_concurrency=global_max_concurrency,
            per_chapter_concurrency=per_chapter_concurrency,
            min_per_chapter_concurrency=min_per_chapter_concurrency,
            adaptive_per_chapter_concurrency=adaptive_per_chapter_concurrency,
            max_input_tokens=max_input_tokens,
            reserved_output_tokens=reserved_output_tokens,
            max_output_tokens=max_output_tokens,
            chunk_target_tokens=chunk_target_tokens,
            context_segments_before=context_segments_before,
            context_segments_after=context_segments_after,
            translation_memory_size=translation_memory_size,
            retry_max_attempts=retry_max_attempts,
            duplicate_text_cache_enabled=duplicate_text_cache_enabled,
            duplicate_text_cache_min_chars=duplicate_text_cache_min_chars,
            dynamic_rate_control_enabled=dynamic_rate_control_enabled,
            dynamic_rate_control_initial_global_concurrency=dynamic_rate_control_initial_global_concurrency,
            dynamic_rate_control_min_global_concurrency=dynamic_rate_control_min_global_concurrency,
            dynamic_rate_control_scale_up_success_streak=dynamic_rate_control_scale_up_success_streak,
            hard_global_max_in_flight=hard_global_max_in_flight,
            hard_target_max_in_flight=hard_target_max_in_flight,
            hard_concurrency_acquire_timeout_seconds=hard_concurrency_acquire_timeout_seconds,
            runtime_setting_sources=runtime_setting_sources,
        )
        return settings.normalized()

    def normalized(self) -> "TranslationRuntimeSettings":
        runtime_setting_sources = dict(self.runtime_setting_sources)
        normalized_runtime_profile = normalize_runtime_profile(self.runtime_profile)
        max_input_tokens = max(256, int(self.max_input_tokens))
        if max_input_tokens != int(self.max_input_tokens):
            runtime_setting_sources["max_input_tokens"] = _append_source_note(
                runtime_setting_sources.get("max_input_tokens", "default"),
                "normalized:min_256",
            )
        reserved_output_tokens = max(64, int(self.reserved_output_tokens))
        if reserved_output_tokens != int(self.reserved_output_tokens):
            runtime_setting_sources["reserved_output_tokens"] = _append_source_note(
                runtime_setting_sources.get("reserved_output_tokens", "default"),
                "normalized:min_64",
            )
        max_output_tokens = max(64, int(self.max_output_tokens))
        if max_output_tokens != int(self.max_output_tokens):
            runtime_setting_sources["max_output_tokens"] = _append_source_note(
                runtime_setting_sources.get("max_output_tokens", "default"),
                "normalized:min_64",
            )
        per_chapter_concurrency = max(1, int(self.per_chapter_concurrency))
        if per_chapter_concurrency != int(self.per_chapter_concurrency):
            runtime_setting_sources["per_chapter_concurrency"] = _append_source_note(
                runtime_setting_sources.get("per_chapter_concurrency", "default"),
                "normalized:min_1",
            )
        min_per_chapter_concurrency = min(
            per_chapter_concurrency,
            max(1, int(self.min_per_chapter_concurrency)),
        )
        if min_per_chapter_concurrency != int(self.min_per_chapter_concurrency):
            runtime_setting_sources["min_per_chapter_concurrency"] = _append_source_note(
                runtime_setting_sources.get("min_per_chapter_concurrency", "default"),
                "normalized:bounded_by_per_chapter_concurrency",
            )
        global_max_concurrency = max(1, int(self.global_max_concurrency))
        if global_max_concurrency != int(self.global_max_concurrency):
            runtime_setting_sources["global_max_concurrency"] = _append_source_note(
                runtime_setting_sources.get("global_max_concurrency", "default"),
                "normalized:min_1",
            )
        normalized_hard_global_max_in_flight = (
            max(1, int(self.hard_global_max_in_flight))
            if self.hard_global_max_in_flight is not None
            else None
        )
        if (
            normalized_hard_global_max_in_flight is not None
            and normalized_hard_global_max_in_flight != int(self.hard_global_max_in_flight)
        ):
            runtime_setting_sources["hard_global_max_in_flight"] = _append_source_note(
                runtime_setting_sources.get("hard_global_max_in_flight", "default"),
                "normalized:min_1",
            )
        normalized_hard_target_max_in_flight = (
            max(1, int(self.hard_target_max_in_flight))
            if self.hard_target_max_in_flight is not None
            else None
        )
        if (
            normalized_hard_target_max_in_flight is not None
            and normalized_hard_target_max_in_flight != int(self.hard_target_max_in_flight)
        ):
            runtime_setting_sources["hard_target_max_in_flight"] = _append_source_note(
                runtime_setting_sources.get("hard_target_max_in_flight", "default"),
                "normalized:min_1",
            )
        normalized_hard_concurrency_acquire_timeout_seconds = (
            max(0.001, float(self.hard_concurrency_acquire_timeout_seconds))
            if self.hard_concurrency_acquire_timeout_seconds is not None
            else None
        )
        if (
            normalized_hard_concurrency_acquire_timeout_seconds is not None
            and normalized_hard_concurrency_acquire_timeout_seconds
            != float(self.hard_concurrency_acquire_timeout_seconds)
        ):
            runtime_setting_sources["hard_concurrency_acquire_timeout_seconds"] = _append_source_note(
                runtime_setting_sources.get(
                    "hard_concurrency_acquire_timeout_seconds",
                    "default",
                ),
                "normalized:min_0.001",
            )
        if (
            normalized_hard_global_max_in_flight is not None
            and global_max_concurrency > normalized_hard_global_max_in_flight
        ):
            global_max_concurrency = normalized_hard_global_max_in_flight
            runtime_setting_sources["global_max_concurrency"] = _append_source_note(
                runtime_setting_sources.get("global_max_concurrency", "default"),
                "normalized:bounded_by_hard_global_max_in_flight",
            )
        if (
            normalized_hard_target_max_in_flight is not None
            and global_max_concurrency > normalized_hard_target_max_in_flight
        ):
            global_max_concurrency = normalized_hard_target_max_in_flight
            runtime_setting_sources["global_max_concurrency"] = _append_source_note(
                runtime_setting_sources.get("global_max_concurrency", "default"),
                "normalized:bounded_by_hard_target_max_in_flight",
            )
        chunk_target_tokens = min(
            max(64, int(self.chunk_target_tokens)),
            max(64, max_input_tokens - reserved_output_tokens),
        )
        if chunk_target_tokens != int(self.chunk_target_tokens):
            runtime_setting_sources["chunk_target_tokens"] = _append_source_note(
                runtime_setting_sources.get("chunk_target_tokens", "default"),
                "normalized:bounded_by_input_budget",
            )
        dynamic_rate_control_initial_global_concurrency = min(
            global_max_concurrency,
            max(1, int(self.dynamic_rate_control_initial_global_concurrency)),
        )
        if (
            dynamic_rate_control_initial_global_concurrency
            != int(self.dynamic_rate_control_initial_global_concurrency)
        ):
            runtime_setting_sources["dynamic_rate_control_initial_global_concurrency"] = _append_source_note(
                runtime_setting_sources.get(
                    "dynamic_rate_control_initial_global_concurrency",
                    "default",
                ),
                "normalized:bounded_by_global_max_concurrency",
            )
        dynamic_rate_control_min_global_concurrency = min(
            dynamic_rate_control_initial_global_concurrency,
            max(1, int(self.dynamic_rate_control_min_global_concurrency)),
        )
        if (
            dynamic_rate_control_min_global_concurrency
            != int(self.dynamic_rate_control_min_global_concurrency)
        ):
            runtime_setting_sources["dynamic_rate_control_min_global_concurrency"] = _append_source_note(
                runtime_setting_sources.get(
                    "dynamic_rate_control_min_global_concurrency",
                    "default",
                ),
                "normalized:bounded_by_initial_global_concurrency",
            )
        normalized_max_requests_per_minute = (
            max(1, int(self.max_requests_per_minute))
            if self.max_requests_per_minute is not None
            else None
        )
        if (
            normalized_max_requests_per_minute is not None
            and normalized_max_requests_per_minute != int(self.max_requests_per_minute)
        ):
            runtime_setting_sources["max_requests_per_minute"] = _append_source_note(
                runtime_setting_sources.get("max_requests_per_minute", "default"),
                "normalized:min_1",
            )
        normalized_detected_context_window = (
            max(256, int(self.detected_context_window))
            if self.detected_context_window is not None
            else None
        )
        if (
            normalized_detected_context_window is not None
            and normalized_detected_context_window != int(self.detected_context_window)
        ):
            runtime_setting_sources["detected_context_window"] = _append_source_note(
                runtime_setting_sources.get("detected_context_window", "default"),
                "normalized:min_256",
            )
        normalized_context_segments_before = max(0, int(self.context_segments_before))
        if normalized_context_segments_before != int(self.context_segments_before):
            runtime_setting_sources["context_segments_before"] = _append_source_note(
                runtime_setting_sources.get("context_segments_before", "default"),
                "normalized:min_0",
            )
        normalized_context_segments_after = max(0, int(self.context_segments_after))
        if normalized_context_segments_after != int(self.context_segments_after):
            runtime_setting_sources["context_segments_after"] = _append_source_note(
                runtime_setting_sources.get("context_segments_after", "default"),
                "normalized:min_0",
            )
        normalized_translation_memory_size = max(0, int(self.translation_memory_size))
        if normalized_translation_memory_size != int(self.translation_memory_size):
            runtime_setting_sources["translation_memory_size"] = _append_source_note(
                runtime_setting_sources.get("translation_memory_size", "default"),
                "normalized:min_0",
            )
        normalized_retry_max_attempts = max(1, int(self.retry_max_attempts))
        if normalized_retry_max_attempts != int(self.retry_max_attempts):
            runtime_setting_sources["retry_max_attempts"] = _append_source_note(
                runtime_setting_sources.get("retry_max_attempts", "default"),
                "normalized:min_1",
            )
        normalized_duplicate_text_cache_min_chars = max(1, int(self.duplicate_text_cache_min_chars))
        if normalized_duplicate_text_cache_min_chars != int(self.duplicate_text_cache_min_chars):
            runtime_setting_sources["duplicate_text_cache_min_chars"] = _append_source_note(
                runtime_setting_sources.get("duplicate_text_cache_min_chars", "default"),
                "normalized:min_1",
            )
        normalized_dynamic_rate_control_scale_up_success_streak = max(
            1,
            int(self.dynamic_rate_control_scale_up_success_streak),
        )
        if (
            normalized_dynamic_rate_control_scale_up_success_streak
            != int(self.dynamic_rate_control_scale_up_success_streak)
        ):
            runtime_setting_sources["dynamic_rate_control_scale_up_success_streak"] = _append_source_note(
                runtime_setting_sources.get(
                    "dynamic_rate_control_scale_up_success_streak",
                    "default",
                ),
                "normalized:min_1",
            )
        return TranslationRuntimeSettings(
            runtime_profile=normalized_runtime_profile or DEFAULT_RUNTIME_PROFILE,
            runtime_profile_source=str(self.runtime_profile_source or DEFAULT_RUNTIME_PROFILE_SOURCE),
            api_mode=normalize_api_mode(self.api_mode) or "responses",
            max_requests_per_minute=normalized_max_requests_per_minute,
            detected_context_window=normalized_detected_context_window,
            structured_output_strength=normalize_structured_output_strength(
                self.structured_output_strength
            ),
            reasoning_mode=normalize_reasoning_mode(self.reasoning_mode),
            global_max_concurrency=global_max_concurrency,
            per_chapter_concurrency=per_chapter_concurrency,
            min_per_chapter_concurrency=min_per_chapter_concurrency,
            adaptive_per_chapter_concurrency=bool(self.adaptive_per_chapter_concurrency),
            max_input_tokens=max_input_tokens,
            reserved_output_tokens=reserved_output_tokens,
            max_output_tokens=max_output_tokens,
            chunk_target_tokens=chunk_target_tokens,
            context_segments_before=normalized_context_segments_before,
            context_segments_after=normalized_context_segments_after,
            translation_memory_size=normalized_translation_memory_size,
            retry_max_attempts=normalized_retry_max_attempts,
            duplicate_text_cache_enabled=bool(self.duplicate_text_cache_enabled),
            duplicate_text_cache_min_chars=normalized_duplicate_text_cache_min_chars,
            dynamic_rate_control_enabled=bool(self.dynamic_rate_control_enabled),
            dynamic_rate_control_initial_global_concurrency=dynamic_rate_control_initial_global_concurrency,
            dynamic_rate_control_min_global_concurrency=dynamic_rate_control_min_global_concurrency,
            dynamic_rate_control_scale_up_success_streak=normalized_dynamic_rate_control_scale_up_success_streak,
            hard_global_max_in_flight=normalized_hard_global_max_in_flight,
            hard_target_max_in_flight=normalized_hard_target_max_in_flight,
            hard_concurrency_acquire_timeout_seconds=normalized_hard_concurrency_acquire_timeout_seconds,
            runtime_setting_sources=runtime_setting_sources,
        )

    def effective_per_chapter_concurrency(
        self,
        *,
        active_chapter_count: int,
        global_limit: int | None = None,
    ) -> int:
        normalized = self.normalized()
        if not normalized.adaptive_per_chapter_concurrency:
            return normalized.per_chapter_concurrency

        active_count = max(1, int(active_chapter_count))
        effective_global_limit = max(1, int(global_limit or normalized.global_max_concurrency))
        distributed_limit = math.ceil(effective_global_limit / active_count)
        return max(
            normalized.min_per_chapter_concurrency,
            min(normalized.per_chapter_concurrency, distributed_limit),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_runtime_profile(
    *,
    options: Mapping[str, Any] | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
    api_mode: str | None = None,
    max_requests_per_minute: int | None = None,
    detected_context_window: int | None = None,
    structured_output_strength: str | None = None,
    reasoning_mode: str | None = None,
) -> tuple[str, str, TranslationRuntimePreset]:
    data = dict(options or {})
    explicit_runtime_profile = normalize_runtime_profile(data.get("runtime_profile"))
    if explicit_runtime_profile is not None:
        return (
            explicit_runtime_profile,
            "explicit",
            runtime_preset_for_profile(explicit_runtime_profile),
        )

    override_profile = runtime_profile_override_for_target(
        provider_name=provider_name,
        model_name=model_name,
        base_url=data.get("base_url"),
        override_store_root=data.get(RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION),
    )
    if override_profile is not None:
        return (
            override_profile,
            "override",
            runtime_preset_for_profile(override_profile),
        )

    detected_profile = detect_runtime_profile(
        provider_name=provider_name,
        model_name=model_name,
        api_mode=api_mode,
        max_requests_per_minute=max_requests_per_minute,
        detected_context_window=detected_context_window,
        structured_output_strength=structured_output_strength,
        reasoning_mode=reasoning_mode,
    )
    if detected_profile is not None:
        return (
            detected_profile,
            "detected",
            runtime_preset_for_profile(detected_profile),
        )

    fallback_profile = runtime_profile_for_model_family(
        provider_name=provider_name,
        model_name=model_name,
    )
    if fallback_profile is not None:
        return (
            fallback_profile,
            "model_family",
            runtime_preset_for_profile(fallback_profile),
        )

    return (
        DEFAULT_RUNTIME_PROFILE,
        DEFAULT_RUNTIME_PROFILE_SOURCE,
        runtime_preset_for_profile(DEFAULT_RUNTIME_PROFILE),
    )


def runtime_preset_for_profile(runtime_profile: str | None) -> TranslationRuntimePreset:
    normalized_runtime_profile = normalize_runtime_profile(runtime_profile)
    if normalized_runtime_profile is None:
        return TranslationRuntimePreset()
    return RUNTIME_PROFILES.get(normalized_runtime_profile, TranslationRuntimePreset())


def runtime_profile_override_for_target(
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
    base_url: object = None,
    override_store_root: object = None,
) -> str | None:
    del provider_name
    normalized_model_name = _normalize_model_name(model_name)
    normalized_base_url = str(base_url or "").strip().lower().rstrip("/")
    if normalized_model_name and normalized_base_url:
        target_key = f"{normalized_model_name}@{normalized_base_url}"
        override = normalize_runtime_profile(
            MODEL_OR_ENDPOINT_RUNTIME_PROFILE_OVERRIDES.get(target_key)
        )
        if override is not None:
            return override
        persisted_override = _load_persisted_runtime_profile_override(
            model_name=normalized_model_name,
            base_url=normalized_base_url,
            override_store_root=override_store_root,
        )
        if persisted_override is not None:
            return persisted_override
    return None


def runtime_profile_for_model_family(
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> str | None:
    del provider_name
    normalized_model_name = _normalize_model_name(model_name)
    for token, runtime_profile in MODEL_FAMILY_RUNTIME_PROFILE_FALLBACKS:
        if token and token in normalized_model_name:
            return runtime_profile
    return None


def detect_runtime_profile(
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
    api_mode: str | None = None,
    max_requests_per_minute: int | None = None,
    detected_context_window: int | None = None,
    structured_output_strength: str | None = None,
    reasoning_mode: str | None = None,
) -> str | None:
    del provider_name, model_name
    normalized_api_mode = normalize_api_mode(api_mode) or "responses"
    normalized_reasoning_mode = normalize_reasoning_mode(reasoning_mode)
    normalized_structured_output_strength = normalize_structured_output_strength(
        structured_output_strength
    )
    # Moderate RPM ceilings are operationally rate-limited for this runtime:
    # they should prefer the low-concurrency/rate-control preset before
    # reasoning or context-oriented heuristics.
    if max_requests_per_minute is not None and int(max_requests_per_minute) <= 30:
        return "generic_rate_limited"
    if normalized_reasoning_mode == "reasoning":
        return "generic_reasoning"
    if detected_context_window is not None and int(detected_context_window) >= 16000:
        return "generic_large_context"
    if normalized_api_mode == "chat_completions" and normalized_structured_output_strength == "weak":
        return "generic_low_latency"
    return None


def _read_runtime_option_sources(data: Mapping[str, Any]) -> dict[str, str]:
    raw = data.get(RUNTIME_OPTION_SOURCE_METADATA_KEY)
    if not isinstance(raw, Mapping):
        return {}
    normalized_sources: dict[str, str] = {}
    for key, value in raw.items():
        normalized_key = str(key or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_key or not normalized_value:
            continue
        normalized_sources[normalized_key] = normalized_value
    return normalized_sources


def _runtime_profile_value_source(
    *,
    resolved_profile_name: str,
    resolved_profile_source: str,
    explicit_source: str | None,
) -> str:
    if resolved_profile_source == "explicit":
        return explicit_source or "option"
    if resolved_profile_source == "override":
        return f"target_override:{resolved_profile_name}"
    if resolved_profile_source == "detected":
        return f"detected_capabilities:{resolved_profile_name}"
    if resolved_profile_source == "model_family":
        return f"model_family_fallback:{resolved_profile_name}"
    return "default"


def _option_source(
    data: Mapping[str, Any],
    option_sources: Mapping[str, str],
    *keys: str,
) -> str | None:
    for key in keys:
        normalized_source = str(option_sources.get(key) or "").strip()
        if normalized_source:
            return normalized_source
    for key in keys:
        if _option_value_is_present(data.get(key)):
            return "option"
    return None


def _resolve_int_with_source(
    *,
    data: Mapping[str, Any],
    option_sources: Mapping[str, str],
    keys: tuple[str, ...],
    preset: int | None,
    default: int,
    minimum: int,
    preset_source: str,
) -> tuple[int, str]:
    explicit_value = _first_present_value(data, *keys)
    explicit_source = _option_source(data, option_sources, *keys)
    if explicit_value is not None and explicit_source is not None:
        return _as_int(explicit_value, default, minimum=minimum), explicit_source
    if preset is not None:
        return _as_int(preset, default, minimum=minimum), _normalize_preset_source(preset_source)
    return _as_int(default, default, minimum=minimum), "default"


def _resolve_bool_with_source(
    *,
    data: Mapping[str, Any],
    option_sources: Mapping[str, str],
    keys: tuple[str, ...],
    preset: bool | None,
    default: bool,
    preset_source: str,
) -> tuple[bool, str]:
    explicit_value = _first_present_value(data, *keys)
    explicit_source = _option_source(data, option_sources, *keys)
    if explicit_value is not None and explicit_source is not None:
        return _as_bool(explicit_value, default), explicit_source
    if preset is not None:
        return bool(preset), _normalize_preset_source(preset_source)
    return bool(default), "default"


def _first_present_value(data: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        value = data.get(key)
        if _option_value_is_present(value):
            return value
    return None


def _append_source_note(source: str, note: str) -> str:
    normalized_source = str(source or "").strip() or "default"
    normalized_note = str(note or "").strip()
    if not normalized_note:
        return normalized_source
    return f"{normalized_source}|{normalized_note}"


def _normalize_preset_source(source: str) -> str:
    normalized_source = str(source or "").strip() or "default"
    if not normalized_source.startswith("runtime_profile:"):
        return normalized_source
    parts = normalized_source.split(":")
    if len(parts) >= 2:
        return ":".join(parts[:2])
    return normalized_source


def _option_value_is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _normalize_model_name(model_name: str | None) -> str:
    return str(model_name or "").strip().lower()


def _load_persisted_runtime_profile_override(
    *,
    model_name: str,
    base_url: str,
    override_store_root: object,
) -> str | None:
    normalized_override_store_root = str(override_store_root or "").strip()
    if not normalized_override_store_root:
        return None
    store = RuntimeProfileOverrideStore(normalized_override_store_root)
    entry = store.load(model_name=model_name, base_url=base_url)
    if entry is None:
        return None
    return normalize_runtime_profile(entry.runtime_profile)


def normalize_runtime_profile(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in RUNTIME_PROFILES:
        return normalized
    return None


def normalize_api_mode(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"responses", "response"}:
        return "responses"
    if normalized in {"chat", "chat_completion", "chat_completions", "chat-completions"}:
        return "chat_completions"
    return normalized


def normalize_structured_output_strength(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"weak", "low"}:
        return "weak"
    if normalized in {"standard", "medium", "normal"}:
        return "standard"
    if normalized in {"strong", "high"}:
        return "strong"
    return normalized


def infer_structured_output_strength(*, api_mode: str) -> str:
    normalized_api_mode = normalize_api_mode(api_mode) or "responses"
    if normalized_api_mode == "chat_completions":
        return "weak"
    return "strong"


def normalize_reasoning_mode(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"off", "none", "disabled", "disable", "false"}:
        return "none"
    if normalized in {"reasoning", "thinking", "think", "enabled", "enable"}:
        return "reasoning"
    if normalized in {"standard", "default", "normal"}:
        return "standard"
    return normalized


def infer_reasoning_mode(
    *,
    model_name: str | None = None,
    reasoning_effort: object = None,
) -> str:
    del model_name
    normalized_reasoning_effort = str(reasoning_effort or "").strip().lower()
    if normalized_reasoning_effort:
        return "reasoning"
    return "standard"


def _cap_max_input_tokens(
    preset_value: int | None,
    *,
    detected_context_window: int | None,
) -> int | None:
    if detected_context_window is None:
        return preset_value
    normalized_detected_context_window = max(256, int(detected_context_window))
    if preset_value is None:
        return normalized_detected_context_window
    return min(int(preset_value), normalized_detected_context_window)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _resolve_int(
    value: Any,
    preset: int | None,
    default: int,
    *,
    minimum: int,
) -> int:
    if value is not None:
        return _as_int(value, default, minimum=minimum)
    if preset is not None:
        return _as_int(preset, default, minimum=minimum)
    return _as_int(default, default, minimum=minimum)


def _resolve_bool(
    value: Any,
    preset: bool | None,
    default: bool,
) -> bool:
    if value is not None:
        return _as_bool(value, default)
    if preset is not None:
        return bool(preset)
    return bool(default)


def _as_int(value: Any, default: int, *, minimum: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(minimum, normalized)


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)
