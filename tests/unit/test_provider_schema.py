from __future__ import annotations

from backend.api.schemas.provider import (
    RUNTIME_OPTION_SOURCE_METADATA_KEY,
    ProviderConfigRequest,
)


def test_provider_config_request_tracks_request_override_sources() -> None:
    base = ProviderConfigRequest(
        provider_name="openai",
        runtime_profile="generic_safe",
        chunk_target_tokens=900,
        per_chapter_concurrency=2,
        endpoint_capability_detection_enabled=True,
    )

    merged = base.merged_with(
        runtime_profile="generic_low_latency",
        chunk_target_tokens=1500,
        endpoint_capability_detection_enabled=False,
        endpoint_capability_detection_timeout_seconds=6.0,
        hard_target_max_in_flight=2,
        hard_concurrency_acquire_timeout_seconds=30.0,
    )
    options = merged.options_dict()

    assert options["runtime_profile"] == "generic_low_latency"
    assert options["chunk_target_tokens"] == 1500
    assert options["per_chapter_concurrency"] == 2
    assert options["endpoint_capability_detection_enabled"] is False
    assert options["endpoint_capability_detection_timeout_seconds"] == 6.0
    assert options["hard_target_max_in_flight"] == 2
    assert options["hard_concurrency_acquire_timeout_seconds"] == 30.0
    assert options[RUNTIME_OPTION_SOURCE_METADATA_KEY]["runtime_profile"] == "request_override"
    assert options[RUNTIME_OPTION_SOURCE_METADATA_KEY]["chunk_target_tokens"] == "request_override"
    assert options[RUNTIME_OPTION_SOURCE_METADATA_KEY]["hard_target_max_in_flight"] == "request_override"
    assert options[RUNTIME_OPTION_SOURCE_METADATA_KEY]["per_chapter_concurrency"] == "provider_config"
