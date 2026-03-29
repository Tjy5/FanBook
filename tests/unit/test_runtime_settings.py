from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from backend.core.translation.runtime_settings import (
    RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION,
    TranslationRuntimeSettings,
)
from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore


RUNTIME_ROOT = Path("temp/.codex_runtime_settings_test")
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


def make_root() -> Path:
    root = RUNTIME_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_root(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def test_runtime_settings_use_generic_safe_baseline_without_overrides() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {},
        provider_name="openai",
        model_name="gpt-5.4",
    )

    assert settings.runtime_profile == "generic_safe"
    assert settings.runtime_profile_source == "default"
    assert settings.api_mode == "responses"
    assert settings.max_input_tokens == 12000
    assert settings.reserved_output_tokens == 1200
    assert settings.max_output_tokens == 1800
    assert settings.chunk_target_tokens == 900
    assert settings.per_chapter_concurrency == 4
    assert settings.adaptive_per_chapter_concurrency is True
    assert settings.runtime_setting_sources["runtime_profile"] == "default"
    assert settings.runtime_setting_sources["api_mode"] == "default"
    assert settings.runtime_setting_sources["structured_output_strength"] == "inferred_from_api_mode:default"
    assert settings.runtime_setting_sources["chunk_target_tokens"].startswith(
        "runtime_profile:generic_safe"
    )


def test_runtime_settings_explicit_values_override_runtime_profile_defaults() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "chunk_target_tokens": 1500,
            "max_input_tokens": 8192,
            "max_concurrency": 9,
            "per_chapter_concurrency": 4,
            "runtime_profile": "generic_large_context",
        },
        provider_name="openai",
        model_name="gpt-5.4",
    )

    assert settings.runtime_profile == "generic_large_context"
    assert settings.runtime_profile_source == "explicit"
    assert settings.global_max_concurrency == 9
    assert settings.max_input_tokens == 8192
    assert settings.chunk_target_tokens == 1500
    assert settings.per_chapter_concurrency == 4
    assert settings.runtime_setting_sources["runtime_profile"] == "option"
    assert settings.runtime_setting_sources["global_max_concurrency"] == "option"
    assert settings.runtime_setting_sources["max_input_tokens"] == "option"
    assert settings.runtime_setting_sources["chunk_target_tokens"] == "option"


def test_runtime_settings_detect_runtime_profile_from_capabilities() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "api_mode": "chat_completions",
            "detected_context_window": 20000,
            "structured_output_strength": "weak",
        },
        provider_name="openai",
        model_name="custom-model",
    )

    assert settings.runtime_profile == "generic_large_context"
    assert settings.runtime_profile_source == "detected"
    assert settings.api_mode == "chat_completions"
    assert settings.detected_context_window == 20000
    assert settings.structured_output_strength == "weak"
    assert settings.max_input_tokens == 16000
    assert settings.chunk_target_tokens == 2200
    assert settings.runtime_setting_sources["runtime_profile"] == "detected_capabilities:generic_large_context"
    assert settings.runtime_setting_sources["api_mode"] == "option"
    assert settings.runtime_setting_sources["detected_context_window"] == "option"
    assert settings.runtime_setting_sources["structured_output_strength"] == "option"
    assert settings.runtime_setting_sources["max_input_tokens"].startswith(
        "runtime_profile:generic_large_context"
    )


def test_runtime_settings_fall_back_to_model_family_profile() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {},
        provider_name="openai",
        model_name="deepseek-r1-distill",
    )

    assert settings.runtime_profile == "generic_reasoning"
    assert settings.runtime_profile_source == "model_family"
    assert settings.reasoning_mode == "reasoning"
    assert settings.max_input_tokens == 14000
    assert settings.reserved_output_tokens == 2200
    assert settings.chunk_target_tokens == 1100
    assert settings.runtime_setting_sources["runtime_profile"] == "model_family_fallback:generic_reasoning"
    assert settings.runtime_setting_sources["reasoning_mode"] == (
        "default|overridden_by_runtime_profile:generic_reasoning"
    )


def test_runtime_settings_use_persisted_runtime_profile_override() -> None:
    root = make_root()
    try:
        store_root = root / "runtime-profile-overrides"
        store = RuntimeProfileOverrideStore(store_root)
        store.upsert(
            provider_name="openai",
            model_name="persisted-model",
            base_url="https://api.example.test/v1",
            runtime_profile="generic_reasoning",
            evidence={"source": "unit-test"},
        )

        settings = TranslationRuntimeSettings.from_options(
            {
                "base_url": "https://api.example.test/v1",
                RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION: str(store_root),
            },
            provider_name="openai",
            model_name="persisted-model",
        )

        assert settings.runtime_profile == "generic_reasoning"
        assert settings.runtime_profile_source == "override"
        assert settings.runtime_setting_sources["runtime_profile"] == (
            "target_override:generic_reasoning"
        )
    finally:
        cleanup_root(root)


def test_runtime_settings_detect_rate_limited_profile_from_moderate_rpm_signal() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "api_mode": "chat_completions",
            "max_requests_per_minute": 30,
            "structured_output_strength": "strong",
            "reasoning_mode": "reasoning",
        },
        provider_name="openai",
        model_name="deepseek-r1",
    )

    assert settings.runtime_profile == "generic_rate_limited"
    assert settings.runtime_profile_source == "detected"
    assert settings.runtime_setting_sources["runtime_profile"] == (
        "detected_capabilities:generic_rate_limited"
    )


def test_runtime_settings_normalize_chunk_target_to_input_budget() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "max_input_tokens": 1000,
            "reserved_output_tokens": 400,
            "chunk_target_tokens": 9000,
            "_fanbook_runtime_option_sources": {
                "max_input_tokens": "request_override",
                "reserved_output_tokens": "request_override",
                "chunk_target_tokens": "request_override",
            },
        }
    )

    assert settings.chunk_target_tokens == 600
    assert settings.runtime_setting_sources["chunk_target_tokens"] == (
        "request_override|normalized:bounded_by_input_budget"
    )


def test_effective_per_chapter_concurrency_scales_with_active_chapters() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "global_max_concurrency": 30,
            "per_chapter_concurrency": 12,
            "min_per_chapter_concurrency": 2,
        }
    )

    assert settings.effective_per_chapter_concurrency(active_chapter_count=1) == 12
    assert settings.effective_per_chapter_concurrency(active_chapter_count=3) == 10
    assert settings.effective_per_chapter_concurrency(active_chapter_count=10) == 3


def test_effective_per_chapter_concurrency_respects_fixed_mode() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "per_chapter_concurrency": 4,
            "adaptive_per_chapter_concurrency": False,
        }
    )

    assert settings.effective_per_chapter_concurrency(active_chapter_count=1) == 4
    assert settings.effective_per_chapter_concurrency(active_chapter_count=8) == 4


def test_runtime_settings_include_duplicate_cache_and_dynamic_rate_control_fields() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "duplicate_text_cache_enabled": False,
            "duplicate_text_cache_min_chars": 20,
            "dynamic_rate_control_enabled": True,
            "dynamic_rate_control_initial_global_concurrency": 5,
            "dynamic_rate_control_min_global_concurrency": 3,
            "dynamic_rate_control_scale_up_success_streak": 4,
        }
    )

    assert settings.duplicate_text_cache_enabled is False
    assert settings.duplicate_text_cache_min_chars == 20
    assert settings.dynamic_rate_control_enabled is True
    assert settings.dynamic_rate_control_initial_global_concurrency == 5
    assert settings.dynamic_rate_control_min_global_concurrency == 3
    assert settings.dynamic_rate_control_scale_up_success_streak == 4


def test_runtime_settings_normalize_dynamic_rate_control_limits() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "global_max_concurrency": 4,
            "dynamic_rate_control_enabled": True,
            "dynamic_rate_control_initial_global_concurrency": 9,
            "dynamic_rate_control_min_global_concurrency": 7,
        }
    )

    assert settings.dynamic_rate_control_initial_global_concurrency == 4
    assert settings.dynamic_rate_control_min_global_concurrency == 4
    assert settings.effective_per_chapter_concurrency(
        active_chapter_count=2,
        global_limit=2,
    ) == 1
    assert settings.runtime_setting_sources["dynamic_rate_control_initial_global_concurrency"] == (
        "option|normalized:bounded_by_global_max_concurrency"
    )
    assert settings.runtime_setting_sources["dynamic_rate_control_min_global_concurrency"] == (
        "option|normalized:bounded_by_initial_global_concurrency"
    )


def test_runtime_settings_clamp_global_concurrency_when_hard_limits_are_explicit() -> None:
    settings = TranslationRuntimeSettings.from_options(
        {
            "global_max_concurrency": 12,
            "hard_global_max_in_flight": 9,
            "hard_target_max_in_flight": 4,
            "hard_concurrency_acquire_timeout_seconds": 0.0,
        }
    )

    assert settings.global_max_concurrency == 4
    assert settings.hard_global_max_in_flight == 9
    assert settings.hard_target_max_in_flight == 4
    assert settings.hard_concurrency_acquire_timeout_seconds == 0.001
    assert settings.runtime_setting_sources["global_max_concurrency"] == (
        "option|normalized:bounded_by_hard_global_max_in_flight|normalized:bounded_by_hard_target_max_in_flight"
    )
    assert settings.runtime_setting_sources["hard_concurrency_acquire_timeout_seconds"] == (
        "option|normalized:min_0.001"
    )
