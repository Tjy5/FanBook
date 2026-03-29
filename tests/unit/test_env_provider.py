from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

import backend.config.env_provider as env_provider_module
from backend.api.schemas.provider import ProviderConfigRequest
from backend.config.dotenv_loader import load_project_dotenv


RUNTIME_ROOT = Path("temp/.codex_env_test")
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


def make_root() -> Path:
    root = RUNTIME_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_root(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def test_load_project_dotenv_keeps_existing_environment_values(monkeypatch) -> None:
    root = make_root()
    try:
        env_file = root / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "# comment",
                    "FANBOOK_TRANSLATION_PROVIDER=openai",
                    "FANBOOK_TRANSLATION_MODEL=from-dotenv",
                    "FANBOOK_TRANSLATION_API_KEY='dotenv-key'",
                    "FANBOOK_TRANSLATION_BASE_URL=https://example.test # inline comment",
                ]
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("FANBOOK_TRANSLATION_MODEL", "from-env")
        monkeypatch.delenv("FANBOOK_TRANSLATION_PROVIDER", raising=False)
        monkeypatch.delenv("FANBOOK_TRANSLATION_API_KEY", raising=False)
        monkeypatch.delenv("FANBOOK_TRANSLATION_BASE_URL", raising=False)

        load_project_dotenv(env_path=env_file)

        assert env_provider_module.os.getenv("FANBOOK_TRANSLATION_PROVIDER") == "openai"
        assert env_provider_module.os.getenv("FANBOOK_TRANSLATION_MODEL") == "from-env"
        assert env_provider_module.os.getenv("FANBOOK_TRANSLATION_API_KEY") == "dotenv-key"
        assert env_provider_module.os.getenv("FANBOOK_TRANSLATION_BASE_URL") == "https://example.test"
    finally:
        cleanup_root(root)


def test_build_env_translation_provider_reads_values_from_dotenv(monkeypatch) -> None:
    root = make_root()
    try:
        env_file = root / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "FANBOOK_TRANSLATION_PROVIDER=openai",
                    "FANBOOK_TRANSLATION_MODEL=gpt-4.1-mini",
                    "FANBOOK_TRANSLATION_API_KEY=test-key",
                    "FANBOOK_TRANSLATION_BASE_URL=https://api.example.test",
                    "FANBOOK_TRANSLATION_RUNTIME_PROFILE=generic_rate_limited",
                    "FANBOOK_TRANSLATION_DETECTED_CONTEXT_WINDOW=32000",
                    "FANBOOK_TRANSLATION_STRUCTURED_OUTPUT_STRENGTH=strong",
                    "FANBOOK_TRANSLATION_REASONING_MODE=standard",
                    "FANBOOK_TRANSLATION_API_MODE=chat_completions",
                    "FANBOOK_TRANSLATION_REASONING_EFFORT=medium",
                    "FANBOOK_TRANSLATION_TIMEOUT_SECONDS=45",
                    "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_ENABLED=false",
                    "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TIMEOUT_SECONDS=7",
                    "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS=600",
                    "FANBOOK_TRANSLATION_MAX_REQUESTS_PER_MINUTE=30",
                    "FANBOOK_TRANSLATION_PER_CHAPTER_CONCURRENCY=4",
                    "FANBOOK_TRANSLATION_MIN_PER_CHAPTER_CONCURRENCY=2",
                    "FANBOOK_TRANSLATION_ADAPTIVE_PER_CHAPTER_CONCURRENCY=false",
                    "FANBOOK_TRANSLATION_CHUNK_TARGET_TOKENS=1800",
                    "FANBOOK_TRANSLATION_MEMORY_SIZE=0",
                    "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_ENABLED=true",
                    "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_MIN_CHARS=18",
                    "FANBOOK_TRANSLATION_DYNAMIC_RATE_CONTROL_ENABLED=true",
                    "FANBOOK_TRANSLATION_DYNAMIC_INITIAL_GLOBAL_CONCURRENCY=6",
                    "FANBOOK_TRANSLATION_DYNAMIC_MIN_GLOBAL_CONCURRENCY=3",
                    "FANBOOK_TRANSLATION_DYNAMIC_SCALE_UP_SUCCESS_STREAK=5",
                    "FANBOOK_TRANSLATION_HARD_GLOBAL_MAX_IN_FLIGHT=7",
                    "FANBOOK_TRANSLATION_HARD_TARGET_MAX_IN_FLIGHT=3",
                    "FANBOOK_TRANSLATION_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS=25",
                ]
            ),
            encoding="utf-8",
        )

        for key in (
            "FANBOOK_TRANSLATION_PROFILES",
            "FANBOOK_TRANSLATION_DEFAULT_PROFILE",
            "FANBOOK_TRANSLATION_PROVIDER",
            "FANBOOK_TRANSLATION_MODEL",
            "FANBOOK_TRANSLATION_API_KEY",
            "FANBOOK_TRANSLATION_BASE_URL",
            "FANBOOK_TRANSLATION_RUNTIME_PROFILE",
            "FANBOOK_TRANSLATION_DETECTED_CONTEXT_WINDOW",
            "FANBOOK_TRANSLATION_STRUCTURED_OUTPUT_STRENGTH",
            "FANBOOK_TRANSLATION_REASONING_MODE",
            "FANBOOK_TRANSLATION_API_MODE",
            "FANBOOK_TRANSLATION_REASONING_EFFORT",
            "FANBOOK_TRANSLATION_TIMEOUT_SECONDS",
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_ENABLED",
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TIMEOUT_SECONDS",
            "FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS",
            "FANBOOK_TRANSLATION_MAX_REQUESTS_PER_MINUTE",
            "FANBOOK_TRANSLATION_PER_CHAPTER_CONCURRENCY",
            "FANBOOK_TRANSLATION_MIN_PER_CHAPTER_CONCURRENCY",
            "FANBOOK_TRANSLATION_ADAPTIVE_PER_CHAPTER_CONCURRENCY",
            "FANBOOK_TRANSLATION_CHUNK_TARGET_TOKENS",
            "FANBOOK_TRANSLATION_MEMORY_SIZE",
            "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_ENABLED",
            "FANBOOK_TRANSLATION_DUPLICATE_TEXT_CACHE_MIN_CHARS",
            "FANBOOK_TRANSLATION_DYNAMIC_RATE_CONTROL_ENABLED",
            "FANBOOK_TRANSLATION_DYNAMIC_INITIAL_GLOBAL_CONCURRENCY",
            "FANBOOK_TRANSLATION_DYNAMIC_MIN_GLOBAL_CONCURRENCY",
            "FANBOOK_TRANSLATION_DYNAMIC_SCALE_UP_SUCCESS_STREAK",
            "FANBOOK_TRANSLATION_HARD_GLOBAL_MAX_IN_FLIGHT",
            "FANBOOK_TRANSLATION_HARD_TARGET_MAX_IN_FLIGHT",
            "FANBOOK_TRANSLATION_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
        ):
            monkeypatch.delenv(key, raising=False)
        for key in tuple(os.environ):
            if key.startswith("FANBOOK_TRANSLATION_PROFILE_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setattr(
            env_provider_module,
            "load_project_dotenv",
            lambda: load_project_dotenv(env_path=env_file),
        )

        provider = env_provider_module.build_env_translation_provider()

        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-4.1-mini"
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.example.test"
        assert provider.runtime_profile == "generic_rate_limited"
        assert provider.detected_context_window == 32000
        assert provider.structured_output_strength == "strong"
        assert provider.reasoning_mode == "standard"
        assert provider.api_mode == "chat_completions"
        assert provider.reasoning_effort == "medium"
        assert provider.timeout_seconds == 45.0
        assert provider.endpoint_capability_detection_enabled is False
        assert provider.endpoint_capability_detection_timeout_seconds == 7.0
        assert provider.endpoint_capability_detection_ttl_seconds == 600.0
        assert provider.max_requests_per_minute == 30
        assert provider.per_chapter_concurrency == 4
        assert provider.min_per_chapter_concurrency == 2
        assert provider.adaptive_per_chapter_concurrency is False
        assert provider.chunk_target_tokens == 1800
        assert provider.translation_memory_size == 0
        assert provider.duplicate_text_cache_enabled is True
        assert provider.duplicate_text_cache_min_chars == 18
        assert provider.dynamic_rate_control_enabled is True
        assert provider.dynamic_rate_control_initial_global_concurrency == 6
        assert provider.dynamic_rate_control_min_global_concurrency == 3
        assert provider.dynamic_rate_control_scale_up_success_streak == 5
        assert provider.hard_global_max_in_flight == 7
        assert provider.hard_target_max_in_flight == 3
        assert provider.hard_concurrency_acquire_timeout_seconds == 25.0
    finally:
        cleanup_root(root)


def test_build_env_translation_provider_profiles_reads_multiple_profiles_from_dotenv(monkeypatch) -> None:
    root = make_root()
    try:
        env_file = root / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "FANBOOK_TRANSLATION_PROFILES=fast,cheap",
                    "FANBOOK_TRANSLATION_DEFAULT_PROFILE=cheap",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_PROVIDER=openai",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_MODEL=gpt-5.4",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_API_KEY=fast-key",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_BASE_URL=https://fast.example.test",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_RUNTIME_PROFILE=generic_large_context",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_DETECTED_CONTEXT_WINDOW=64000",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_API_MODE=responses",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_ENDPOINT_CAPABILITY_DETECTION_ENABLED=false",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_MAX_REQUESTS_PER_MINUTE=60",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_MAX_CONCURRENCY=30",
                    "FANBOOK_TRANSLATION_PROFILE_FAST_CHUNK_TARGET_TOKENS=2200",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_PROVIDER=openai",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_MODEL=gpt-4.1-mini",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_API_KEY=cheap-key",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_BASE_URL=https://cheap.example.test",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_RUNTIME_PROFILE=generic_rate_limited",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_STRUCTURED_OUTPUT_STRENGTH=weak",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_REASONING_MODE=reasoning",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_API_MODE=chat_completions",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS=120",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_REQUESTS_PER_MINUTE=30",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_CONCURRENCY=10",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_CHUNK_TARGET_TOKENS=1400",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_REASONING_EFFORT=medium",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_GLOBAL_MAX_IN_FLIGHT=6",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_TARGET_MAX_IN_FLIGHT=2",
                    "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS=15",
                ]
            ),
            encoding="utf-8",
        )

        for key in (
            "FANBOOK_TRANSLATION_PROFILES",
            "FANBOOK_TRANSLATION_DEFAULT_PROFILE",
            "FANBOOK_TRANSLATION_PROFILE_FAST_PROVIDER",
            "FANBOOK_TRANSLATION_PROFILE_FAST_MODEL",
            "FANBOOK_TRANSLATION_PROFILE_FAST_API_KEY",
            "FANBOOK_TRANSLATION_PROFILE_FAST_BASE_URL",
            "FANBOOK_TRANSLATION_PROFILE_FAST_RUNTIME_PROFILE",
            "FANBOOK_TRANSLATION_PROFILE_FAST_DETECTED_CONTEXT_WINDOW",
            "FANBOOK_TRANSLATION_PROFILE_FAST_API_MODE",
            "FANBOOK_TRANSLATION_PROFILE_FAST_ENDPOINT_CAPABILITY_DETECTION_ENABLED",
            "FANBOOK_TRANSLATION_PROFILE_FAST_MAX_REQUESTS_PER_MINUTE",
            "FANBOOK_TRANSLATION_PROFILE_FAST_MAX_CONCURRENCY",
            "FANBOOK_TRANSLATION_PROFILE_FAST_CHUNK_TARGET_TOKENS",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_PROVIDER",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_MODEL",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_API_KEY",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_BASE_URL",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_RUNTIME_PROFILE",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_STRUCTURED_OUTPUT_STRENGTH",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_REASONING_MODE",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_API_MODE",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_REQUESTS_PER_MINUTE",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_CONCURRENCY",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_CHUNK_TARGET_TOKENS",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_REASONING_EFFORT",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_GLOBAL_MAX_IN_FLIGHT",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_TARGET_MAX_IN_FLIGHT",
            "FANBOOK_TRANSLATION_PROFILE_CHEAP_HARD_CONCURRENCY_ACQUIRE_TIMEOUT_SECONDS",
            "FANBOOK_TRANSLATION_PROVIDER",
            "FANBOOK_TRANSLATION_MODEL",
            "FANBOOK_TRANSLATION_API_KEY",
            "FANBOOK_TRANSLATION_BASE_URL",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
        ):
            monkeypatch.delenv(key, raising=False)
        for key in tuple(os.environ):
            if key.startswith("FANBOOK_TRANSLATION_PROFILE_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setattr(
            env_provider_module,
            "load_project_dotenv",
            lambda: load_project_dotenv(env_path=env_file),
        )

        profile_set = env_provider_module.build_env_translation_provider_profiles()

        assert profile_set.default_profile_name == "cheap"
        assert tuple(profile_set.profiles) == ("fast", "cheap")
        assert profile_set.profiles["fast"].model_name == "gpt-5.4"
        assert profile_set.profiles["fast"].api_key == "fast-key"
        assert profile_set.profiles["fast"].runtime_profile == "generic_large_context"
        assert profile_set.profiles["fast"].detected_context_window == 64000
        assert profile_set.profiles["fast"].api_mode == "responses"
        assert profile_set.profiles["fast"].endpoint_capability_detection_enabled is False
        assert profile_set.profiles["fast"].max_requests_per_minute == 60
        assert profile_set.profiles["fast"].global_max_concurrency == 30
        assert profile_set.profiles["fast"].chunk_target_tokens == 2200
        assert profile_set.profiles["cheap"].model_name == "gpt-4.1-mini"
        assert profile_set.profiles["cheap"].api_key == "cheap-key"
        assert profile_set.profiles["cheap"].runtime_profile == "generic_rate_limited"
        assert profile_set.profiles["cheap"].structured_output_strength == "weak"
        assert profile_set.profiles["cheap"].reasoning_mode == "reasoning"
        assert profile_set.profiles["cheap"].api_mode == "chat_completions"
        assert profile_set.profiles["cheap"].endpoint_capability_detection_ttl_seconds == 120.0
        assert profile_set.profiles["cheap"].max_requests_per_minute == 30
        assert profile_set.profiles["cheap"].global_max_concurrency == 10
        assert profile_set.profiles["cheap"].chunk_target_tokens == 1400
        assert profile_set.profiles["cheap"].reasoning_effort == "medium"
        assert profile_set.profiles["cheap"].hard_global_max_in_flight == 6
        assert profile_set.profiles["cheap"].hard_target_max_in_flight == 2
        assert profile_set.profiles["cheap"].hard_concurrency_acquire_timeout_seconds == 15.0
        assert env_provider_module.build_env_translation_provider().model_name == "gpt-4.1-mini"
    finally:
        cleanup_root(root)


def test_build_env_translation_provider_omits_reasoning_effort_when_unset(monkeypatch) -> None:
    root = make_root()
    try:
        env_file = root / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "FANBOOK_TRANSLATION_PROFILES=hf_deepseek",
                    "FANBOOK_TRANSLATION_DEFAULT_PROFILE=hf_deepseek",
                    "FANBOOK_TRANSLATION_PROFILE_HF_DEEPSEEK_PROVIDER=openai",
                    "FANBOOK_TRANSLATION_PROFILE_HF_DEEPSEEK_MODEL=deepseek-chat",
                    "FANBOOK_TRANSLATION_PROFILE_HF_DEEPSEEK_API_KEY=test-key",
                    "FANBOOK_TRANSLATION_PROFILE_HF_DEEPSEEK_BASE_URL=https://api.example.test",
                    "FANBOOK_TRANSLATION_PROFILE_HF_DEEPSEEK_API_MODE=chat_completions",
                ]
            ),
            encoding="utf-8",
        )

        for key in tuple(os.environ):
            if key.startswith("FANBOOK_TRANSLATION_") or key.startswith("OPENAI_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setattr(
            env_provider_module,
            "load_project_dotenv",
            lambda: load_project_dotenv(env_path=env_file),
        )

        provider = env_provider_module.build_env_translation_provider()

        assert provider.model_name == "deepseek-chat"
        assert provider.api_mode == "chat_completions"
        assert provider.reasoning_effort is None
    finally:
        cleanup_root(root)


def test_provider_config_request_merges_runtime_overrides_without_losing_defaults() -> None:
    provider = ProviderConfigRequest(
        provider_name="openai",
        model_name="gpt-5.4",
        runtime_profile="generic_safe",
        detected_context_window=16000,
        structured_output_strength="strong",
        reasoning_mode="standard",
        reasoning_effort="low",
        endpoint_capability_detection_enabled=True,
        endpoint_capability_detection_timeout_seconds=5.0,
        per_chapter_concurrency=2,
        min_per_chapter_concurrency=1,
        adaptive_per_chapter_concurrency=True,
        chunk_target_tokens=900,
        translation_memory_size=2,
        duplicate_text_cache_enabled=True,
        duplicate_text_cache_min_chars=16,
        dynamic_rate_control_enabled=False,
        dynamic_rate_control_initial_global_concurrency=12,
        dynamic_rate_control_min_global_concurrency=4,
        dynamic_rate_control_scale_up_success_streak=3,
    )

    merged = provider.merged_with(
        model_name="gpt-5.4-mini",
        runtime_profile="generic_reasoning",
        detected_context_window=32000,
        structured_output_strength="weak",
        reasoning_mode="reasoning",
        endpoint_capability_detection_enabled=False,
        endpoint_capability_detection_timeout_seconds=8.0,
        adaptive_per_chapter_concurrency=False,
        chunk_target_tokens=1500,
        translation_memory_size=0,
        duplicate_text_cache_enabled=False,
        duplicate_text_cache_min_chars=24,
        dynamic_rate_control_enabled=True,
        dynamic_rate_control_initial_global_concurrency=8,
        dynamic_rate_control_min_global_concurrency=2,
        dynamic_rate_control_scale_up_success_streak=6,
    )

    assert merged.provider_name == "openai"
    assert merged.model_name == "gpt-5.4-mini"
    assert merged.runtime_profile == "generic_reasoning"
    assert merged.detected_context_window == 32000
    assert merged.structured_output_strength == "weak"
    assert merged.reasoning_mode == "reasoning"
    assert merged.reasoning_effort == "low"
    assert merged.endpoint_capability_detection_enabled is False
    assert merged.endpoint_capability_detection_timeout_seconds == 8.0
    assert merged.per_chapter_concurrency == 2
    assert merged.min_per_chapter_concurrency == 1
    assert merged.adaptive_per_chapter_concurrency is False
    assert merged.chunk_target_tokens == 1500
    assert merged.translation_memory_size == 0
    assert merged.duplicate_text_cache_enabled is False
    assert merged.duplicate_text_cache_min_chars == 24
    assert merged.dynamic_rate_control_enabled is True
    assert merged.dynamic_rate_control_initial_global_concurrency == 8
    assert merged.dynamic_rate_control_min_global_concurrency == 2
    assert merged.dynamic_rate_control_scale_up_success_streak == 6
    assert merged.runtime_option_sources["runtime_profile"] == "request_override"
    assert merged.runtime_option_sources["chunk_target_tokens"] == "request_override"
    assert merged.runtime_option_sources["per_chapter_concurrency"] == "provider_config"
    assert merged.options_dict()["_fanbook_runtime_option_sources"]["runtime_profile"] == (
        "request_override"
    )
