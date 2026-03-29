from __future__ import annotations

import json
from pathlib import Path

from backend.benchmark.cli import main as benchmark_cli_main
from backend.benchmark.override_suggestions import (
    load_benchmark_report,
    suggest_runtime_profile_overrides,
)


def _write_json_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_suggest_runtime_profile_override_for_non_inferable_target(tmp_path) -> None:
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"
    payload = {
        "benchmark_name": "hf-deepseek-pass-1",
        "provider_name": "openai",
        "model_name": "deepseek-chat",
        "provider_base_url": "https://api.example.test/v1",
        "override_target_key": "deepseek-chat@https://api.example.test/v1",
        "status": "completed",
        "quality_gate_status": "pass",
        "runtime_profile": "generic_rate_limited",
        "runtime_profile_source": "detected",
        "api_mode": "responses",
        "structured_output_strength": "strong",
        "reasoning_mode": "standard",
        "max_requests_per_minute": 60,
        "runtime_settings": {},
        "chunk_failure_reason_counts": {},
        "chunk_fallback_reason_counts": {},
    }
    _write_json_report(first_report, payload)
    _write_json_report(
        second_report,
        {
            **payload,
            "benchmark_name": "hf-deepseek-pass-2",
        },
    )

    report = suggest_runtime_profile_overrides([first_report, second_report])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "suggested"
    assert suggestion.suggested_runtime_profile == "generic_rate_limited"
    assert suggestion.confidence == "high"
    assert suggestion.curated_override_snippet == (
        '"deepseek-chat@https://api.example.test/v1": "generic_rate_limited",'
    )


def test_suggest_runtime_profile_override_marks_inferable_profiles_as_non_curated(tmp_path) -> None:
    report_path = tmp_path / "reasoning.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "reasoning-pass",
            "provider_name": "openai",
            "model_name": "reasoner-v1",
            "provider_base_url": "https://reasoning.example.test/v1",
            "override_target_key": "reasoner-v1@https://reasoning.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_reasoning",
            "runtime_profile_source": "detected",
            "reasoning_mode": "reasoning",
            "api_mode": "responses",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    report = suggest_runtime_profile_overrides([report_path])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "inferable_without_curated_override"
    assert suggestion.suggested_runtime_profile == "generic_reasoning"


def test_suggest_runtime_profile_override_marks_inferable_rate_limited_targets_as_non_curated(
    tmp_path,
) -> None:
    report_path = tmp_path / "inferable-rate-limited.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "hf-inferable-pass",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://2c2ch1u11-share-api-0.hf.space/v1",
            "override_target_key": "deepseek-chat@https://2c2ch1u11-share-api-0.hf.space/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "max_requests_per_minute": 30,
            "structured_output_strength": "strong",
            "reasoning_mode": "reasoning",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    report = suggest_runtime_profile_overrides([report_path])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "inferable_without_curated_override"
    assert suggestion.suggested_runtime_profile == "generic_rate_limited"


def test_suggest_runtime_profile_override_does_not_promote_needs_review_only_reports(tmp_path) -> None:
    report_path = tmp_path / "needs-review.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "needs-review-only",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://review.example.test/v1",
            "override_target_key": "deepseek-chat@https://review.example.test/v1",
            "status": "completed",
            "quality_gate_status": "needs_review",
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "structured_output_strength": "weak",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {"invalid_json": 1},
        },
    )

    report = suggest_runtime_profile_overrides([report_path])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "insufficient_evidence"
    assert suggestion.curated_override_snippet is None


def test_suggest_runtime_profile_override_does_not_promote_failure_only_reports(tmp_path) -> None:
    report_path = tmp_path / "reject.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "reject-only",
            "provider_name": "openai",
            "model_name": "gpt-5.4",
            "provider_base_url": "https://endpoint.example.test/v1",
            "override_target_key": "gpt-5.4@https://endpoint.example.test/v1",
            "status": "failed",
            "quality_gate_status": "reject",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {"rate_limited": 2},
            "chunk_fallback_reason_counts": {"rate_limited": 2},
            "error_summary": "HTTP 429 rate limit exceeded",
        },
    )

    report = suggest_runtime_profile_overrides([report_path])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "insufficient_evidence"
    assert suggestion.curated_override_snippet is None


def test_suggest_runtime_profile_override_requires_strong_non_manual_support(tmp_path) -> None:
    first_report = tmp_path / "manual-1.json"
    second_report = tmp_path / "manual-2.json"
    payload = {
        "benchmark_name": "manual-pass-1",
        "provider_name": "openai",
        "model_name": "deepseek-chat",
        "provider_base_url": "https://manual.example.test/v1",
        "override_target_key": "deepseek-chat@https://manual.example.test/v1",
        "status": "completed",
        "quality_gate_status": "pass",
        "runtime_profile": "generic_rate_limited",
        "runtime_profile_source": "option",
        "api_mode": "chat_completions",
        "structured_output_strength": "weak",
        "runtime_settings": {},
        "chunk_failure_reason_counts": {},
        "chunk_fallback_reason_counts": {},
    }
    _write_json_report(first_report, payload)
    _write_json_report(second_report, {**payload, "benchmark_name": "manual-pass-2"})

    report = suggest_runtime_profile_overrides([first_report, second_report])

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.status == "insufficient_evidence"
    assert suggestion.curated_override_snippet is None


def test_load_markdown_report_without_sibling_json_uses_fallback_base_url(tmp_path) -> None:
    report_path = tmp_path / "legacy.md"
    report_path.write_text(
        "\n".join(
            [
                "# Benchmark legacy",
                "",
                "- benchmark_name: `legacy-report`",
                "- status: `completed`",
                "- provider/model: `openai` / `legacy-model`",
                "- quality_gate_status: `pass`",
                "- runtime_profile: `generic_rate_limited`",
                "- runtime_profile_source: `option`",
                "- api_mode: `chat_completions`",
                "",
                "## Runtime Setting Sources",
                "",
                "```json",
                "{\"runtime_profile\": \"option\"}",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    evidence = load_benchmark_report(
        report_path,
        fallback_base_url="https://legacy.example.test/v1",
    )

    assert evidence.report_format == "markdown"
    assert evidence.model_name == "legacy-model"
    assert evidence.provider_base_url == "https://legacy.example.test/v1"
    assert evidence.override_target_key == "legacy-model@https://legacy.example.test/v1"
    assert evidence.runtime_profile == "generic_rate_limited"


def test_load_json_report_uses_checkpoint_runtime_metadata_fallback(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    checkpoint_dir = runtime_root / "checkpoints" / "1"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (checkpoint_dir / "state.json").write_text(
        json.dumps(
            {
                "provider_name": "openai",
                "model_name": "verified-model",
                "runtime_settings": {
                    "runtime_profile": "generic_reasoning",
                    "runtime_profile_source": "detected",
                    "runtime_target": {
                        "base_url": "https://api.example.test/v1",
                        "target_key": "verified-model@https://api.example.test/v1",
                    },
                    "endpoint_capability_detection": {
                        "models_endpoint": "https://api.example.test/v1/models",
                        "strategy": "models_list+deep_probe",
                        "confidence": "high",
                        "deep_probe_status": "ok",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "checkpoint-backed.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "checkpoint-backed",
            "runtime_root": str(runtime_root),
            "job_id": 1,
            "status": "completed",
            "quality_gate_status": "pass",
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    evidence = load_benchmark_report(report_path)

    assert evidence.provider_name == "openai"
    assert evidence.model_name == "verified-model"
    assert evidence.provider_base_url == "https://api.example.test/v1"
    assert evidence.override_target_key == "verified-model@https://api.example.test/v1"
    assert evidence.runtime_profile == "generic_reasoning"
    assert evidence.endpoint_capability_confidence == "high"
    assert evidence.models_endpoint == "https://api.example.test/v1/models"


def test_benchmark_cli_suggest_overrides_writes_json_and_markdown_outputs(tmp_path) -> None:
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"
    payload = {
        "benchmark_name": "hf-deepseek-pass-1",
        "provider_name": "openai",
        "model_name": "deepseek-chat",
        "provider_base_url": "https://api.example.test/v1",
        "override_target_key": "deepseek-chat@https://api.example.test/v1",
        "status": "completed",
        "quality_gate_status": "pass",
        "runtime_profile": "generic_rate_limited",
        "runtime_profile_source": "detected",
        "runtime_settings": {},
        "chunk_failure_reason_counts": {},
        "chunk_fallback_reason_counts": {},
    }
    _write_json_report(first_report, payload)
    _write_json_report(second_report, {**payload, "benchmark_name": "hf-deepseek-pass-2"})
    output_dir = tmp_path / "artifacts"

    exit_code = benchmark_cli_main(
        [
            "suggest-overrides",
            str(first_report),
            str(second_report),
            "--output-dir",
            str(output_dir),
            "--suggestion-name",
            "demo",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "demo.json").exists()
    assert (output_dir / "demo.md").exists()
