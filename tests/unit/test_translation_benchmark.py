from __future__ import annotations

import json
import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import zipfile

from backend.benchmark.cli import _normalize_chunk_sweep, _parse_provider_options
from backend.benchmark.override_advisor import (
    suggest_runtime_profile_overrides as build_override_suggestion_artifacts,
)
from backend.benchmark.runner import (
    _count_reason_codes,
    _evaluate_quality_gate,
    run_translation_benchmark,
)
from backend.benchmark import runner as benchmark_runner_module


RUNTIME_ROOT = Path("temp/.codex_benchmark_test")
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


def make_root() -> Path:
    root = RUNTIME_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_root(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def build_epub_bytes() -> bytes:
    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    content_opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Benchmark Book</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>
"""
    chapter_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Chapter One</title></head>
  <body>
    <section>
      <h1>Chapter 1</h1>
      <p>Hello <em>world</em>.</p>
      <ol><li>First item</li></ol>
      <aside epub:type="footnote">Footnote text</aside>
    </section>
  </body>
</html>
"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(
            "mimetype",
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/container.xml", container_xml)
        archive.writestr("OEBPS/content.opf", content_opf)
        archive.writestr("OEBPS/ch1.xhtml", chapter_xhtml)
    return buffer.getvalue()


def test_run_translation_benchmark_writes_json_and_markdown_reports() -> None:
    root = make_root()
    try:
        epub_path = root / "benchmark.epub"
        epub_path.write_bytes(build_epub_bytes())

        artifacts = run_translation_benchmark(
            epub_path=epub_path,
            runtime_root=root / "runtime",
            output_dir=root / "reports",
            provider_name="mock",
            benchmark_name="mock-benchmark",
        )

        assert artifacts.json_path.exists()
        assert artifacts.markdown_path.exists()
        payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
        assert payload["benchmark_name"] == "mock-benchmark"
        assert payload["provider_name"] == "mock"
        assert payload["translated_segments"] == payload["total_segments"] == 4
        assert payload["chunk_total"] >= 1
        assert payload["chunk_completed"] == payload["chunk_total"]
        assert payload["chunk_failed"] == 0
        assert payload["fallback_count"] == 0
        assert payload["chunk_failure_reason_counts"] == {}
        assert payload["chunk_fallback_reason_counts"] == {}
        assert payload["average_estimated_tokens_per_chunk"] >= 0
        assert payload["export_success"] is True
        assert payload["quality_gate_status"] == "pass"
        assert payload["quality_gate_reasons"] == []
        assert payload["runtime_profile"] == "generic_safe"
        assert payload["runtime_profile_source"] == "default"
        assert payload["runtime_setting_sources"]["runtime_profile"] == "default"
        assert payload["provider_base_url"] is None
        assert payload["override_target_key"] is None
        assert payload["models_endpoint"] is None
        assert payload["endpoint_capability_strategy"] is None
        assert payload["endpoint_capability_confidence"] is None
        assert payload["deep_probe_status"] is None
        assert payload["requested_provider_options"] == {}
        assert payload["requested_provider_option_sources"] == {}
        assert payload["runtime_setting_sources"]["chunk_target_tokens"].startswith(
            "runtime_profile:generic_safe"
        )
        assert payload["api_mode"] == "responses"
        assert payload["max_requests_per_minute"] is None
        assert payload["detected_context_window"] is None
        assert payload["structured_output_strength"] == "strong"
        assert payload["reasoning_mode"] == "standard"
        assert payload["capability_tier"] == (
            "responses__standard_reasoning__strong_structured__unknown_context__unknown_rate"
        )
        assert payload["runtime_settings"]["chunk_target_tokens"] == 900
        assert payload["runtime_settings"]["runtime_setting_sources"]["runtime_profile"] == "default"
        assert payload["runtime_settings"]["runtime_setting_sources"]["chunk_target_tokens"].startswith(
            "runtime_profile:generic_safe"
        )
        assert "average_estimated_tokens_per_chunk" in artifacts.markdown_path.read_text(encoding="utf-8")
        assert "## Quality Gate" in artifacts.markdown_path.read_text(encoding="utf-8")
        assert "## Runtime Setting Sources" in artifacts.markdown_path.read_text(encoding="utf-8")
        assert "## Runtime Settings" in artifacts.markdown_path.read_text(encoding="utf-8")
        assert "## Requested Provider Options" in artifacts.markdown_path.read_text(encoding="utf-8")
        assert "## Requested Provider Option Sources" in artifacts.markdown_path.read_text(encoding="utf-8")
    finally:
        cleanup_root(root)


def test_parse_provider_options_normalizes_scalar_values() -> None:
    parsed = _parse_provider_options(
        [
            "chunk_target_tokens=2200",
            "adaptive_per_chapter_concurrency=false",
            "timeout_seconds=45.5",
            "glossary=[\"Alice\"]",
        ]
    )

    assert parsed["chunk_target_tokens"] == 2200
    assert parsed["adaptive_per_chapter_concurrency"] is False
    assert parsed["timeout_seconds"] == 45.5
    assert parsed["glossary"] == ["Alice"]


def test_run_translation_benchmark_passes_api_key_and_base_url_into_provider_request(monkeypatch) -> None:
    captured_provider = None

    class FakeRunner:
        def run(self, request):
            nonlocal captured_provider
            captured_provider = request.provider
            return benchmark_runner_module.BenchmarkRunResult(
                run_id="run-1",
                benchmark_name="fake",
                input_path="input.epub",
                report_json_path="out.json",
                report_markdown_path="out.md",
                runtime_root="runtime",
                status="completed",
                provider_name="openai",
                model_name="gpt-5.4",
                book_id=1,
                job_id=1,
                started_at="",
                finished_at="",
                duration_seconds=1.0,
                total_segments=1,
                translated_segments=1,
                chunk_total=1,
                chunk_completed=1,
                chunk_failed=0,
                fallback_count=0,
                chunk_failure_reason_counts={},
                chunk_fallback_reason_counts={},
                average_segments_per_chunk=1.0,
                average_source_chars_per_chunk=10.0,
                average_estimated_tokens_per_chunk=5.0,
                export_success=True,
                quality_gate_status="pass",
                quality_gate_reasons=(),
                runtime_settings={},
                error_summary=None,
            )

    monkeypatch.setattr(benchmark_runner_module, "TranslationBenchmarkRunner", FakeRunner)

    artifacts = run_translation_benchmark(
        epub_path="sample.epub",
        provider_name="openai",
        model_name="gpt-5.4",
        provider_options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "runtime_profile": "generic_rate_limited",
            "detected_context_window": 32000,
            "structured_output_strength": "weak",
            "reasoning_mode": "none",
            "api_mode": "chat_completions",
            "max_requests_per_minute": 30,
            "chunk_target_tokens": 2200,
        },
    )

    assert artifacts.result.provider_name == "openai"
    assert captured_provider is not None
    assert captured_provider.api_key == "test-key"
    assert captured_provider.base_url == "https://api.example.test"
    assert captured_provider.runtime_profile == "generic_rate_limited"
    assert captured_provider.detected_context_window == 32000
    assert captured_provider.structured_output_strength == "weak"
    assert captured_provider.reasoning_mode == "none"
    assert captured_provider.api_mode == "chat_completions"
    assert captured_provider.max_requests_per_minute == 30
    assert captured_provider.chunk_target_tokens == 2200


def test_run_translation_benchmark_writes_sanitized_requested_provider_metadata() -> None:
    root = make_root()
    try:
        epub_path = root / "benchmark.epub"
        epub_path.write_bytes(build_epub_bytes())

        artifacts = run_translation_benchmark(
            epub_path=epub_path,
            runtime_root=root / "runtime",
            output_dir=root / "reports",
            provider_name="mock",
            model_name="synthetic-model",
            provider_options={
                "api_key": "secret-key",
                "base_url": "https://api.example.test/v1",
                "runtime_profile": "generic_rate_limited",
                "api_mode": "chat_completions",
                "max_requests_per_minute": 30,
            },
            benchmark_name="metadata-check",
        )

        payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
        assert payload["provider_base_url"] == "https://api.example.test/v1"
        assert payload["override_target_key"] == "synthetic-model@https://api.example.test/v1"
        assert payload["runtime_settings"]["runtime_target"]["base_url"] == (
            "https://api.example.test/v1"
        )
        assert payload["runtime_settings"]["runtime_target"]["target_key"] == (
            "synthetic-model@https://api.example.test/v1"
        )
        assert payload["requested_provider_options"]["base_url"] == "https://api.example.test/v1"
        assert payload["requested_provider_options"]["runtime_profile"] == "generic_rate_limited"
        assert payload["requested_provider_options"]["api_mode"] == "chat_completions"
        assert payload["requested_provider_options"]["max_requests_per_minute"] == 30
        assert "api_key" not in payload["requested_provider_options"]
        assert payload["capability_tier"] == (
            "chat_completions__standard_reasoning__weak_structured__unknown_context__moderate_rate_limit"
        )
    finally:
        cleanup_root(root)


def test_override_advisor_writes_json_and_markdown_artifacts(tmp_path) -> None:
    report_path = tmp_path / "benchmark.json"
    report_path.write_text(
        json.dumps(
            {
                "benchmark_name": "deepseek-pass",
                "provider_name": "openai",
                "model_name": "deepseek-chat",
                "provider_base_url": "https://api.example.test/v1",
                "override_target_key": "deepseek-chat@https://api.example.test/v1",
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
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    artifacts = build_override_suggestion_artifacts(
        report_paths=[str(report_path)],
        output_dir=tmp_path / "override-suggestions",
        suggestion_name="synthetic-suggestions",
    )

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["suggestion_name"] == "synthetic-suggestions"
    assert payload["suggestions"][0]["suggested_runtime_profile"] == "generic_rate_limited"
    assert "synthetic-suggestions" in artifacts.markdown_path.read_text(encoding="utf-8")


def test_normalize_chunk_sweep_deduplicates_and_clamps_values() -> None:
    assert _normalize_chunk_sweep([2200, 1800, 2200, 32]) == [64, 1800, 2200]


def test_count_reason_codes_ignores_empty_values() -> None:
    counts = _count_reason_codes([None, "", "timeout", "timeout", "invalid_json"])

    assert counts == {
        "timeout": 2,
        "invalid_json": 1,
    }


def test_evaluate_quality_gate_marks_fallback_runs_for_review() -> None:
    status, reasons = _evaluate_quality_gate(
        status="completed",
        export_success=True,
        translated_segments=10,
        total_segments=10,
        chunk_failed=0,
        fallback_count=2,
        chunk_failure_reason_counts={},
        chunk_fallback_reason_counts={"invalid_json": 2},
        error_summary=None,
    )

    assert status == "needs_review"
    assert "fallbacks_present" in reasons
    assert "chunk_fallback:invalid_json" in reasons


def test_evaluate_quality_gate_rejects_incomplete_or_failed_runs() -> None:
    status, reasons = _evaluate_quality_gate(
        status="failed",
        export_success=False,
        translated_segments=4,
        total_segments=10,
        chunk_failed=1,
        fallback_count=0,
        chunk_failure_reason_counts={"timeout": 1},
        chunk_fallback_reason_counts={},
        error_summary="synthetic failure",
    )

    assert status == "reject"
    assert "job_status:failed" in reasons
    assert "incomplete_translation" in reasons
    assert "export_failed" in reasons
    assert "chunk_failures_present" in reasons
