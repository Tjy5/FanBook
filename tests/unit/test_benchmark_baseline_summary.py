from __future__ import annotations

import json
from pathlib import Path

from backend.benchmark.baseline_summary import summarize_benchmark_baselines
from backend.benchmark.cli import main as benchmark_cli_main


def _write_json_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_summarize_benchmark_baselines_groups_by_runtime_profile_and_capability_tier(tmp_path) -> None:
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"
    third_report = tmp_path / "third.json"
    _write_json_report(
        first_report,
        {
            "benchmark_name": "rate-limited-a",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://a.example.test/v1",
            "override_target_key": "deepseek-chat@https://a.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "duration_seconds": 12.5,
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "structured_output_strength": "weak",
            "max_requests_per_minute": 30,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )
    _write_json_report(
        second_report,
        {
            "benchmark_name": "rate-limited-b",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://b.example.test/v1",
            "override_target_key": "deepseek-chat@https://b.example.test/v1",
            "status": "completed",
            "quality_gate_status": "needs_review",
            "duration_seconds": 10.0,
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "structured_output_strength": "weak",
            "max_requests_per_minute": 30,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {"invalid_json": 1},
        },
    )
    _write_json_report(
        third_report,
        {
            "benchmark_name": "reasoning-pass",
            "provider_name": "openai",
            "model_name": "o3-pro",
            "provider_base_url": "https://reasoning.example.test/v1",
            "override_target_key": "o3-pro@https://reasoning.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "duration_seconds": 20.0,
            "runtime_profile": "generic_reasoning",
            "runtime_profile_source": "detected",
            "api_mode": "responses",
            "reasoning_mode": "reasoning",
            "structured_output_strength": "strong",
            "detected_context_window": 200000,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    summary = summarize_benchmark_baselines([first_report, second_report, third_report])

    assert len(summary.groups) == 2
    first_group = summary.groups[0]
    second_group = summary.groups[1]
    assert {group.runtime_profile for group in summary.groups} == {
        "generic_rate_limited",
        "generic_reasoning",
    }
    rate_group = next(group for group in summary.groups if group.runtime_profile == "generic_rate_limited")
    assert rate_group.capability_tier == (
        "chat_completions__unknown_reasoning__weak_structured__unknown_context__moderate_rate_limit"
    )
    assert rate_group.report_count == 2
    assert rate_group.pass_count == 1
    assert rate_group.needs_review_count == 1
    assert rate_group.unique_target_count == 2
    assert rate_group.precise_non_mock_target_count == 2
    assert rate_group.mock_target_count == 0
    assert rate_group.fastest_pass_report == "rate-limited-a"
    reasoning_group = next(group for group in summary.groups if group.runtime_profile == "generic_reasoning")
    assert reasoning_group.capability_tier == (
        "responses__reasoning__strong_structured__large_context__unknown_rate"
    )
    assert reasoning_group.pass_count == 1
    assert reasoning_group.precise_non_mock_target_count == 1
    assert reasoning_group.mock_target_count == 0


def test_summarize_benchmark_baselines_marks_under_sampled_coverage_gaps(tmp_path) -> None:
    report_path = tmp_path / "single.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "single-target",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://single.example.test/v1",
            "override_target_key": "deepseek-chat@https://single.example.test/v1",
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
        },
    )

    summary = summarize_benchmark_baselines([report_path], min_distinct_targets=2)

    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 1
    assert len(summary.metadata_refresh_only_gaps) == 0
    assert len(summary.ignored_coverage_gaps) == 0
    assert summary.coverage_gaps[0].reason == "need_more_distinct_targets"
    assert summary.coverage_gaps[0].actionability == "benchmark_distinct_target"
    assert summary.coverage_gaps[0].precise_non_mock_target_count == 1
    assert "second precise non-mock target" in summary.coverage_gaps[0].recommendation
    assert "## Real Benchmark Priorities" in summary.render_markdown()
    assert "[`benchmark_distinct_target`]" in summary.render_markdown()


def test_summarize_benchmark_baselines_marks_mock_only_gaps_as_non_decision_driving(tmp_path) -> None:
    report_path = tmp_path / "mock-only.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "mock-only",
            "provider_name": "mock",
            "model_name": "mock-v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_safe",
            "runtime_profile_source": "default",
            "api_mode": "responses",
            "structured_output_strength": "strong",
            "reasoning_mode": "standard",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    summary = summarize_benchmark_baselines([report_path], min_distinct_targets=2)

    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 0
    assert len(summary.metadata_refresh_only_gaps) == 0
    assert len(summary.ignored_coverage_gaps) == 1
    assert summary.coverage_gaps[0].actionability == "ignore_mock_only"
    assert "mock-only coverage" in summary.coverage_gaps[0].recommendation


def test_summarize_benchmark_baselines_ignores_heuristic_covered_real_bucket(tmp_path) -> None:
    report_path = tmp_path / "heuristic-covered.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "heuristic-covered",
            "provider_name": "openai",
            "model_name": "o3-pro",
            "provider_base_url": "https://reasoning.example.test/v1",
            "override_target_key": "o3-pro@https://reasoning.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_reasoning",
            "runtime_profile_source": "detected",
            "api_mode": "responses",
            "reasoning_mode": "reasoning",
            "structured_output_strength": "strong",
            "detected_context_window": 200000,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    summary = summarize_benchmark_baselines([report_path], min_distinct_targets=2)

    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 0
    assert len(summary.metadata_refresh_only_gaps) == 0
    assert len(summary.ignored_coverage_gaps) == 1
    assert summary.coverage_gaps[0].actionability == "ignore_heuristic_covered"
    assert "already covered by generic heuristics" in summary.coverage_gaps[0].recommendation


def test_summarize_benchmark_baselines_does_not_let_mock_target_close_real_coverage_gap(
    tmp_path,
) -> None:
    real_report = tmp_path / "real.json"
    mock_report = tmp_path / "mock.json"
    _write_json_report(
        real_report,
        {
            "benchmark_name": "real-target",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://real.example.test/v1",
            "override_target_key": "deepseek-chat@https://real.example.test/v1",
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
        },
    )
    _write_json_report(
        mock_report,
        {
            "benchmark_name": "mock-target",
            "provider_name": "mock",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://mock.example.test/v1",
            "override_target_key": "deepseek-chat@https://mock.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "explicit",
            "api_mode": "responses",
            "structured_output_strength": "strong",
            "reasoning_mode": "standard",
            "max_requests_per_minute": 60,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    summary = summarize_benchmark_baselines([real_report, mock_report], min_distinct_targets=2)

    assert len(summary.groups) == 1
    group = summary.groups[0]
    assert group.unique_target_count == 2
    assert group.precise_non_mock_target_count == 1
    assert group.mock_target_count == 1
    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 1
    gap = summary.coverage_gaps[0]
    assert gap.reason == "need_more_distinct_targets"
    assert gap.unique_target_count == 2
    assert gap.precise_non_mock_target_count == 1
    assert gap.actionability == "benchmark_distinct_target"
    assert "mock or imprecise targets" in gap.recommendation


def test_summarize_benchmark_baselines_marks_legacy_metadata_gaps_for_refresh(tmp_path) -> None:
    report_path = tmp_path / "legacy.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "legacy",
            "provider_name": "openai",
            "model_name": "gpt-5.4",
            "status": "failed",
            "quality_gate_status": "reject",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {"rate_limited": 1},
            "chunk_fallback_reason_counts": {"rate_limited": 1},
            "error_summary": "HTTP 429 rate limit exceeded",
        },
    )

    summary = summarize_benchmark_baselines([report_path], min_distinct_targets=2)

    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 0
    assert len(summary.metadata_refresh_only_gaps) == 1
    assert len(summary.ignored_coverage_gaps) == 0
    assert summary.coverage_gaps[0].actionability == "refresh_legacy_metadata"
    assert "rerun this target with current benchmark metadata" in summary.coverage_gaps[0].recommendation


def test_summarize_benchmark_baselines_ignores_legacy_bucket_when_refreshed_target_exists(
    tmp_path,
) -> None:
    legacy_report = tmp_path / "legacy.json"
    refreshed_report = tmp_path / "refreshed.json"
    mock_legacy_report = tmp_path / "mock-legacy.json"
    _write_json_report(
        legacy_report,
        {
            "benchmark_name": "legacy-gpt54",
            "provider_name": "openai",
            "model_name": "gpt-5.4",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )
    _write_json_report(
        mock_legacy_report,
        {
            "benchmark_name": "legacy-mock",
            "provider_name": "mock",
            "model_name": "mock-v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )
    _write_json_report(
        refreshed_report,
        {
            "benchmark_name": "refreshed-gpt54",
            "provider_name": "openai",
            "model_name": "gpt-5.4",
            "provider_base_url": "https://codex.example.test/v1",
            "override_target_key": "gpt-5.4@https://codex.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_reasoning",
            "runtime_profile_source": "detected",
            "api_mode": "responses",
            "reasoning_mode": "reasoning",
            "structured_output_strength": "strong",
            "detected_context_window": 200000,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )

    summary = summarize_benchmark_baselines(
        [legacy_report, mock_legacy_report, refreshed_report],
        min_distinct_targets=1,
    )

    assert len(summary.real_benchmark_priorities) == 0
    assert len(summary.metadata_refresh_only_gaps) == 0
    assert len(summary.ignored_coverage_gaps) == 1
    legacy_gap = next(
        gap
        for gap in summary.coverage_gaps
        if gap.runtime_profile == "unknown_runtime_profile"
    )
    assert legacy_gap.actionability == "ignore_superseded_legacy"
    assert "superseded by refreshed target-qualified reports" in legacy_gap.recommendation


def test_summarize_benchmark_baselines_marks_precise_failure_buckets_as_real_priority(tmp_path) -> None:
    report_path = tmp_path / "precise-failure.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "precise-failure",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://verify.example.test/v1",
            "override_target_key": "deepseek-chat@https://verify.example.test/v1",
            "status": "completed",
            "quality_gate_status": "reject",
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "structured_output_strength": "weak",
            "max_requests_per_minute": 30,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {"request_error": 1},
            "chunk_fallback_reason_counts": {"request_error": 1},
            "error_summary": "HTTP 429 rate limit exceeded",
        },
    )

    summary = summarize_benchmark_baselines([report_path], min_distinct_targets=1)

    assert len(summary.coverage_gaps) == 1
    assert len(summary.real_benchmark_priorities) == 1
    assert summary.coverage_gaps[0].reason == "no_pass_report"
    assert summary.coverage_gaps[0].actionability == "verify_before_expand"
    assert "get at least one precise pass report" in summary.coverage_gaps[0].recommendation


def test_benchmark_cli_summarize_baselines_writes_json_and_markdown_outputs(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "baseline.json"
    _write_json_report(
        report_path,
        {
            "benchmark_name": "baseline-pass",
            "provider_name": "openai",
            "model_name": "deepseek-chat",
            "provider_base_url": "https://baseline.example.test/v1",
            "override_target_key": "deepseek-chat@https://baseline.example.test/v1",
            "status": "completed",
            "quality_gate_status": "pass",
            "runtime_profile": "generic_rate_limited",
            "runtime_profile_source": "detected",
            "api_mode": "chat_completions",
            "structured_output_strength": "weak",
            "max_requests_per_minute": 30,
            "runtime_settings": {},
            "chunk_failure_reason_counts": {},
            "chunk_fallback_reason_counts": {},
        },
    )
    output_dir = tmp_path / "baseline-artifacts"

    exit_code = benchmark_cli_main(
        [
            "summarize-baselines",
            str(reports_dir),
            "--output-dir",
            str(output_dir),
            "--summary-name",
            "by-runtime-profile",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "by-runtime-profile.json").exists()
    assert (output_dir / "by-runtime-profile.md").exists()
