from __future__ import annotations

import os
import re
from dataclasses import dataclass

from backend.api.schemas.provider import ProviderConfigRequest
from backend.config.dotenv_loader import load_project_dotenv
from backend.core.translation.runtime_settings import DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY


DEFAULT_TRANSLATION_PROVIDER_NAME = "openai"
DEFAULT_TRANSLATION_MODEL_NAME = "gpt-5.4"
DEFAULT_TRANSLATION_BASE_URL = "https://api.openai.com"
DEFAULT_TRANSLATION_TIMEOUT_SECONDS = 90.0
DEFAULT_TRANSLATION_PROFILE_NAME = "default"
TRANSLATION_PROFILES_ENV = "FANBOOK_TRANSLATION_PROFILES"
DEFAULT_TRANSLATION_PROFILE_ENV = "FANBOOK_TRANSLATION_DEFAULT_PROFILE"


@dataclass(slots=True, frozen=True)
class TranslationProviderProfileSet:
    default_profile_name: str
    profiles: dict[str, ProviderConfigRequest]

    @property
    def default_provider(self) -> ProviderConfigRequest:
        return self.profiles[self.default_profile_name]


def build_env_translation_provider_profiles() -> TranslationProviderProfileSet:
    load_project_dotenv()

    profile_names = _read_profile_names()
    if not profile_names:
        default_profile_name = DEFAULT_TRANSLATION_PROFILE_NAME
        return TranslationProviderProfileSet(
            default_profile_name=default_profile_name,
            profiles={
                default_profile_name: _build_legacy_translation_provider(),
            },
        )

    profiles: dict[str, ProviderConfigRequest] = {}
    for profile_name in profile_names:
        normalized_name = normalize_translation_profile_name(profile_name)
        if normalized_name in profiles:
            continue
        profiles[normalized_name] = _build_profile_translation_provider(profile_name)

    default_profile_name = normalize_translation_profile_name(
        _read_optional_text(DEFAULT_TRANSLATION_PROFILE_ENV) or next(iter(profiles))
    )
    if default_profile_name not in profiles:
        default_profile_name = next(iter(profiles))

    return TranslationProviderProfileSet(
        default_profile_name=default_profile_name,
        profiles=profiles,
    )


def build_env_translation_provider() -> ProviderConfigRequest:
    return build_env_translation_provider_profiles().default_provider


def normalize_translation_profile_name(name: str | None) -> str:
    normalized = str(name or "").strip().lower()
    return normalized or DEFAULT_TRANSLATION_PROFILE_NAME


def _build_legacy_translation_provider() -> ProviderConfigRequest:
    provider_name = _read_text(
        "FANBOOK_TRANSLATION_PROVIDER",
        default=DEFAULT_TRANSLATION_PROVIDER_NAME,
    )
    model_name = _read_text(
        "FANBOOK_TRANSLATION_MODEL",
        default=DEFAULT_TRANSLATION_MODEL_NAME,
    )
    api_key = _read_optional_text(
        "FANBOOK_TRANSLATION_API_KEY",
        fallback_names=("OPENAI_API_KEY",),
    )
    base_url = _read_text(
        "FANBOOK_TRANSLATION_BASE_URL",
        fallback_names=("OPENAI_BASE_URL",),
        default=DEFAULT_TRANSLATION_BASE_URL,
    )
    reasoning_effort = _read_text(
        "FANBOOK_TRANSLATION_REASONING_EFFORT",
        default="",
    )
    timeout_seconds = _read_float(
        "FANBOOK_TRANSLATION_TIMEOUT_SECONDS",
        default=DEFAULT_TRANSLATION_TIMEOUT_SECONDS,
    )
    return _build_provider_request(
        provider_name=provider_name,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        runtime_option_source_label="env_config",
        runtime_profile=_read_text(
            "FANBOOK_TRANSLATION_RUNTIME_PROFILE",
            default="",
        ),
        detected_context_window=_read_optional_int(
            "FANBOOK_TRANSLATION_DETECTED_CONTEXT_WINDOW"
        ),
        structured_output_strength=_read_text(
            "FANBOOK_TRANSLATION_STRUCTURED_OUTPUT_STRENGTH",
            default="",
        ),
        reasoning_mode=_read_text(
            "FANBOOK_TRANSLATION_REASONING_MODE",
            default="",
        ),
        api_mode=_read_text(
            "FANBOOK_TRANSLATION_API_MODE",
            default="",
        ),
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        endpoint_capability_detection_enabled=_read_optional_bool(
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_ENABLED",
            default=True,
        ),
        endpoint_capability_detection_timeout_seconds=_read_optional_float(
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TIMEOUT_SECONDS"
        ),
        endpoint_capability_detection_ttl_seconds=_read_optional_float(
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS"
        ),
        max_requests_per_minute=_read_optional_int(
            "FANBOOK_TRANSLATION_MAX_REQUESTS_PER_MINUTE"
        ),
        global_max_concurrency=_read_optional_int("FANBOOK_TRANSLATION_MAX_CONCURRENCY"),
        per_chapter_concurrency=_read_optional_int(
            "FANBOOK_TRANSLATION_PER_CHAPTER_CONCURRENCY"
        ),
        min_per_chapter_concurrency=_read_optional_int(
            "FANBOOK_TRANSLATION_MIN_PER_CHAPTER_CONCURRENCY"
        ),
        adaptive_per_chapter_concurrency=_read_optional_bool(
            "FANBOOK_TRANSLATION_ADAPTIVE_PER_CHAPTER_CONCURRENCY",
            default=DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY,
        ),
        max_input_tokens=_read_optional_int("FANBOOK_TRANSLATION_MAX_INPUT_TOKENS"),
        reserved_output_tokens=_read_optional_int(
            "FANBOOK_TRANSLATION_RESERVED_OUTPUT_TOKENS"
        ),
        max_output_tokens=_read_optional_int("FANBOOK_TRANSLATION_MAX_OUTPUT_TOKENS"),
        chunk_target_tokens=_read_optional_int("FANBOOK_TRANSLATION_CHUNK_TARGET_TOKENS"),
        context_segments_before=_read_optional_int(
            "FANBOOK_TRANSLATION_CONTEXT_SEGMENTS_BEFORE"
        ),
        context_segments_after=_read_optional_int(
            "FANBOOK_TRANSLATION_CONTEXT_SEGMENTS_AFTER"
        ),
        translation_memory_size=_read_optional_int("FANBOOK_TRANSLATION_MEMORY_SIZE"),
        retry_max_attempts=_read_optional_int("FANBOOK_TRANSLATION_RETRY_MAX_ATTEMPTS"),
        duplicate_text_cache_enabled=_read_optional_bool(
            "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_ENABLED",
            default=True,
        ),
        duplicate_text_cache_min_chars=_read_optional_int(
            "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_MIN_CHARS"
        ),
        dynamic_rate_control_enabled=_read_optional_bool(
            "FANBOOK_TRANSLATION_DYNAMIC_RATE_CONTROL_ENABLED",
            default=False,
        ),
        dynamic_rate_control_initial_global_concurrency=_read_optional_int(
            "FANBOOK_TRANSLATION_DYNAMIC_INITIAL_GLOBAL_CONCURRENCY"
        ),
        dynamic_rate_control_min_global_concurrency=_read_optional_int(
            "FANBOOK_TRANSLATION_DYNAMIC_MIN_GLOBAL_CONCURRENCY"
        ),
        dynamic_rate_control_scale_up_success_streak=_read_optional_int(
            "FANBOOK_TRANSLATION_DYNAMIC_SCALE_UP_SUCCESS_STREAK"
        ),
        hard_global_max_in_flight=_read_optional_int(
            "FANBOOK_TRANSLATION_HARD_GLOBAL_MAX_IN_FLIGHT"
        ),
        hard_target_max_in_flight=_read_optional_int(
            "FANBOOK_TRANSLATION_HARD_TARGET_MAX_IN_FLIGHT"
        ),
        hard_concurrency_acquire_timeout_seconds=_read_optional_float(
            "FANBOOK_TRANSLATION_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS"
        ),
    )


def _build_profile_translation_provider(profile_name: str) -> ProviderConfigRequest:
    prefix = _profile_env_prefix(profile_name)
    provider_name = _read_text(
        f"{prefix}PROVIDER",
        default=DEFAULT_TRANSLATION_PROVIDER_NAME,
    )
    model_name = _read_text(
        f"{prefix}MODEL",
        default=DEFAULT_TRANSLATION_MODEL_NAME,
    )
    compat_api_key_names = ("OPENAI_API_KEY",) if provider_name.strip().lower() == "openai" else ()
    compat_base_url_names = ("OPENAI_BASE_URL",) if provider_name.strip().lower() == "openai" else ()
    api_key = _read_optional_text(
        f"{prefix}API_KEY",
        fallback_names=compat_api_key_names,
    )
    base_url = _read_text(
        f"{prefix}BASE_URL",
        fallback_names=compat_base_url_names,
        default=DEFAULT_TRANSLATION_BASE_URL,
    )
    reasoning_effort = _read_text(
        f"{prefix}REASONING_EFFORT",
        default="",
    )
    timeout_seconds = _read_float(
        f"{prefix}TIMEOUT_SECONDS",
        default=DEFAULT_TRANSLATION_TIMEOUT_SECONDS,
    )
    return _build_provider_request(
        provider_name=provider_name,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        runtime_option_source_label=(
            f"profile:{normalize_translation_profile_name(profile_name)}"
        ),
        runtime_profile=_read_text(
            f"{prefix}RUNTIME_PROFILE",
            default="",
        ),
        detected_context_window=_read_optional_int(
            f"{prefix}DETECTED_CONTEXT_WINDOW"
        ),
        structured_output_strength=_read_text(
            f"{prefix}STRUCTURED_OUTPUT_STRENGTH",
            default="",
        ),
        reasoning_mode=_read_text(
            f"{prefix}REASONING_MODE",
            default="",
        ),
        api_mode=_read_text(
            f"{prefix}API_MODE",
            default="",
        ),
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        endpoint_capability_detection_enabled=_read_optional_bool(
            f"{prefix}ENDPOINT_CAPABILITY_DETECTION_ENABLED",
            default=True,
        ),
        endpoint_capability_detection_timeout_seconds=_read_optional_float(
            f"{prefix}ENDPOINT_CAPABILITY_DETECTION_TIMEOUT_SECONDS"
        ),
        endpoint_capability_detection_ttl_seconds=_read_optional_float(
            f"{prefix}ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS"
        ),
        max_requests_per_minute=_read_optional_int(
            f"{prefix}MAX_REQUESTS_PER_MINUTE"
        ),
        global_max_concurrency=_read_optional_int(f"{prefix}MAX_CONCURRENCY"),
        per_chapter_concurrency=_read_optional_int(f"{prefix}PER_CHAPTER_CONCURRENCY"),
        min_per_chapter_concurrency=_read_optional_int(
            f"{prefix}MIN_PER_CHAPTER_CONCURRENCY"
        ),
        adaptive_per_chapter_concurrency=_read_optional_bool(
            f"{prefix}ADAPTIVE_PER_CHAPTER_CONCURRENCY",
            default=DEFAULT_ADAPTIVE_PER_CHAPTER_CONCURRENCY,
        ),
        max_input_tokens=_read_optional_int(f"{prefix}MAX_INPUT_TOKENS"),
        reserved_output_tokens=_read_optional_int(f"{prefix}RESERVED_OUTPUT_TOKENS"),
        max_output_tokens=_read_optional_int(f"{prefix}MAX_OUTPUT_TOKENS"),
        chunk_target_tokens=_read_optional_int(f"{prefix}CHUNK_TARGET_TOKENS"),
        context_segments_before=_read_optional_int(f"{prefix}CONTEXT_SEGMENTS_BEFORE"),
        context_segments_after=_read_optional_int(f"{prefix}CONTEXT_SEGMENTS_AFTER"),
        translation_memory_size=_read_optional_int(f"{prefix}MEMORY_SIZE"),
        retry_max_attempts=_read_optional_int(f"{prefix}RETRY_MAX_ATTEMPTS"),
        duplicate_text_cache_enabled=_read_optional_bool(
            f"{prefix}DUPLICATE_TEXT_CACHE_ENABLED",
            default=True,
        ),
        duplicate_text_cache_min_chars=_read_optional_int(
            f"{prefix}DUPLICATE_TEXT_CACHE_MIN_CHARS"
        ),
        dynamic_rate_control_enabled=_read_optional_bool(
            f"{prefix}DYNAMIC_RATE_CONTROL_ENABLED",
            default=False,
        ),
        dynamic_rate_control_initial_global_concurrency=_read_optional_int(
            f"{prefix}DYNAMIC_INITIAL_GLOBAL_CONCURRENCY"
        ),
        dynamic_rate_control_min_global_concurrency=_read_optional_int(
            f"{prefix}DYNAMIC_MIN_GLOBAL_CONCURRENCY"
        ),
        dynamic_rate_control_scale_up_success_streak=_read_optional_int(
            f"{prefix}DYNAMIC_SCALE_UP_SUCCESS_STREAK"
        ),
        hard_global_max_in_flight=_read_optional_int(
            f"{prefix}HARD_GLOBAL_MAX_IN_FLIGHT"
        ),
        hard_target_max_in_flight=_read_optional_int(
            f"{prefix}HARD_TARGET_MAX_IN_FLIGHT"
        ),
        hard_concurrency_acquire_timeout_seconds=_read_optional_float(
            f"{prefix}HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS"
        ),
    )


def _build_provider_request(
    *,
    provider_name: str,
    model_name: str,
    api_key: str | None,
    base_url: str,
    runtime_option_source_label: str,
    runtime_profile: str,
    detected_context_window: int | None,
    structured_output_strength: str,
    reasoning_mode: str,
    api_mode: str,
    reasoning_effort: str,
    timeout_seconds: float,
    endpoint_capability_detection_enabled: bool | None,
    endpoint_capability_detection_timeout_seconds: float | None,
    endpoint_capability_detection_ttl_seconds: float | None,
    max_requests_per_minute: int | None,
    global_max_concurrency: int | None,
    per_chapter_concurrency: int | None,
    min_per_chapter_concurrency: int | None,
    adaptive_per_chapter_concurrency: bool | None,
    max_input_tokens: int | None,
    reserved_output_tokens: int | None,
    max_output_tokens: int | None,
    chunk_target_tokens: int | None,
    context_segments_before: int | None,
    context_segments_after: int | None,
    translation_memory_size: int | None,
    retry_max_attempts: int | None,
    duplicate_text_cache_enabled: bool | None,
    duplicate_text_cache_min_chars: int | None,
    dynamic_rate_control_enabled: bool | None,
    dynamic_rate_control_initial_global_concurrency: int | None,
    dynamic_rate_control_min_global_concurrency: int | None,
    dynamic_rate_control_scale_up_success_streak: int | None,
    hard_global_max_in_flight: int | None,
    hard_target_max_in_flight: int | None,
    hard_concurrency_acquire_timeout_seconds: float | None,
) -> ProviderConfigRequest:
    normalized_runtime_profile = _normalize_optional_runtime_profile(runtime_profile)
    normalized_structured_output_strength = _normalize_optional_structured_output_strength(
        structured_output_strength
    )
    normalized_reasoning_mode = _normalize_optional_reasoning_mode(reasoning_mode)
    normalized_api_mode = _normalize_optional_api_mode(api_mode)
    normalized_reasoning_effort = _normalize_optional_reasoning_effort(reasoning_effort)
    provider_request = ProviderConfigRequest(
        provider_name=provider_name or DEFAULT_TRANSLATION_PROVIDER_NAME,
        model_name=model_name or DEFAULT_TRANSLATION_MODEL_NAME,
        api_key=api_key or None,
        base_url=base_url or DEFAULT_TRANSLATION_BASE_URL,
        runtime_profile=normalized_runtime_profile,
        detected_context_window=detected_context_window,
        structured_output_strength=normalized_structured_output_strength,
        reasoning_mode=normalized_reasoning_mode,
        api_mode=normalized_api_mode,
        reasoning_effort=normalized_reasoning_effort,
        timeout_seconds=timeout_seconds,
        endpoint_capability_detection_enabled=endpoint_capability_detection_enabled,
        endpoint_capability_detection_timeout_seconds=endpoint_capability_detection_timeout_seconds,
        endpoint_capability_detection_ttl_seconds=endpoint_capability_detection_ttl_seconds,
        max_requests_per_minute=max_requests_per_minute,
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
    )
    provider_request.runtime_option_sources.update(
        _runtime_option_sources_for_provider(
            provider_request,
            source_label=runtime_option_source_label,
        )
    )
    return provider_request


def _read_profile_names() -> tuple[str, ...]:
    raw = _read_optional_text(TRANSLATION_PROFILES_ENV)
    if raw is None:
        return ()
    normalized_names: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        normalized = normalize_translation_profile_name(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_names.append(normalized)
    return tuple(normalized_names)


def _profile_env_prefix(profile_name: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "_", profile_name.strip().upper()).strip("_")
    if not token:
        token = DEFAULT_TRANSLATION_PROFILE_NAME.upper()
    return f"FANBOOK_TRANSLATION_PROFILE_{token}_"


def _read_text(name: str, *, default: str, fallback_names: tuple[str, ...] = ()) -> str:
    raw = _read_optional_text(name, fallback_names=fallback_names)
    if raw is None:
        return default
    return raw


def _read_float(name: str, *, default: float, fallback_names: tuple[str, ...] = ()) -> float:
    raw = _get_env_value(name, *fallback_names)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _read_optional_int(name: str, *, fallback_names: tuple[str, ...] = ()) -> int | None:
    raw = _get_env_value(name, *fallback_names)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_optional_float(name: str, *, fallback_names: tuple[str, ...] = ()) -> float | None:
    raw = _get_env_value(name, *fallback_names)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _read_optional_bool(
    name: str,
    *,
    default: bool,
    fallback_names: tuple[str, ...] = (),
) -> bool | None:
    raw = _get_env_value(name, *fallback_names)
    if raw is None:
        return None
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _read_optional_text(name: str, *, fallback_names: tuple[str, ...] = ()) -> str | None:
    raw = _get_env_value(name, *fallback_names)
    if raw is None:
        return None
    return raw


def _get_env_value(name: str, *fallback_names: str) -> str | None:
    for env_name in (name, *fallback_names):
        raw = os.getenv(env_name)
        if raw is None:
            continue
        normalized = raw.strip()
        if normalized:
            return normalized
    return None


def _normalize_optional_reasoning_effort(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.lower() in {"none", "null", "off", "false", "disable", "disabled"}:
        return None
    return normalized


def _normalize_optional_api_mode(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"responses", "response"}:
        return "responses"
    if normalized in {"chat", "chat_completion", "chat_completions", "chat-completions"}:
        return "chat_completions"
    return normalized


def _normalize_optional_runtime_profile(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _normalize_optional_structured_output_strength(value: str | None) -> str | None:
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


def _normalize_optional_reasoning_mode(value: str | None) -> str | None:
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


def _runtime_option_sources_for_provider(
    provider: ProviderConfigRequest,
    *,
    source_label: str,
) -> dict[str, str]:
    sources: dict[str, str] = {}
    for field_name in (
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
    ):
        value = getattr(provider, field_name)
        if value is None:
            continue
        sources[field_name] = source_label
    return sources
