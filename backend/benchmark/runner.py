from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.schemas.provider import (
    RUNTIME_OPTION_SOURCE_METADATA_KEY,
    ProviderConfigRequest,
)
from backend.benchmark.capability_tier import derive_capability_tier
from backend.storage.checkpoint_store import CheckpointStore
from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore


@dataclass(slots=True, frozen=True)
class BenchmarkRunRequest:
    input_path: Path
    provider: ProviderConfigRequest | None = None
    output_dir: Path | None = None
    runtime_root: Path | None = None
    frontend_root: Path | None = None
    title: str | None = None
    source_language: str = "en"
    poll_interval_seconds: float = 0.25
    timeout_seconds: float = 600.0
    export_kind: str = "bilingual"
    benchmark_name: str | None = None


@dataclass(slots=True, frozen=True)
class BenchmarkArtifacts:
    json_path: Path
    markdown_path: Path
    result: "BenchmarkRunResult"


@dataclass(slots=True, frozen=True)
class BenchmarkRunResult:
    run_id: str
    benchmark_name: str
    input_path: str
    report_json_path: str
    report_markdown_path: str
    runtime_root: str
    status: str
    provider_name: str | None
    model_name: str | None
    book_id: int
    job_id: int
    started_at: str
    finished_at: str
    duration_seconds: float
    total_segments: int
    translated_segments: int
    chunk_total: int
    chunk_completed: int
    chunk_failed: int
    fallback_count: int
    chunk_failure_reason_counts: dict[str, int]
    chunk_fallback_reason_counts: dict[str, int]
    average_segments_per_chunk: float
    average_source_chars_per_chunk: float
    average_estimated_tokens_per_chunk: float
    export_success: bool
    quality_gate_status: str
    quality_gate_reasons: tuple[str, ...]
    runtime_settings: dict[str, object] = field(default_factory=dict)
    runtime_profile: str | None = None
    runtime_profile_source: str | None = None
    runtime_setting_sources: dict[str, str] = field(default_factory=dict)
    requested_provider_options: dict[str, object] = field(default_factory=dict)
    requested_provider_option_sources: dict[str, str] = field(default_factory=dict)
    api_mode: str | None = None
    max_requests_per_minute: int | None = None
    detected_context_window: int | None = None
    structured_output_strength: str | None = None
    reasoning_mode: str | None = None
    capability_tier: str | None = None
    provider_base_url: str | None = None
    override_target_key: str | None = None
    models_endpoint: str | None = None
    endpoint_capability_strategy: str | None = None
    endpoint_capability_confidence: str | None = None
    deep_probe_status: str | None = None
    error_summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TranslationBenchmarkRunner:
    def run(self, request: BenchmarkRunRequest) -> BenchmarkRunResult:
        input_path = Path(request.input_path).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f"Benchmark input file was not found: {input_path}")

        run_id = uuid4().hex
        output_dir = Path(request.output_dir or Path("temp") / "benchmark_results").resolve()
        runtime_root = Path(
            request.runtime_root
            or output_dir / run_id / "runtime"
        ).resolve()
        frontend_root = Path(
            request.frontend_root
            or output_dir / run_id / "frontend"
        ).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self._ensure_frontend(frontend_root)

        client = TestClient(
            create_app(
                runtime_root=runtime_root,
                frontend_root=frontend_root,
                translation_provider=request.provider,
            )
        )

        encoded_content = base64.b64encode(input_path.read_bytes()).decode("utf-8")
        created = client.post(
            "/api/books",
            json={
                "filename": input_path.name,
                "contentBase64": encoded_content,
                "sourceLanguage": request.source_language,
                "title": request.title,
            },
        )
        if created.status_code != 201:
            raise RuntimeError(f"Failed to create benchmark book: {created.text}")
        book_id = int(created.json()["book_id"])

        started_monotonic = time.monotonic()
        started = client.post(f"/api/books/{book_id}/translate", json={})
        if started.status_code != 200:
            raise RuntimeError(f"Failed to start benchmark translation: {started.text}")
        started_payload = started.json()
        job_id = int(started_payload["job_id"])
        started_at = str(started_payload.get("started_at") or "")

        detail_payload, finished_at = self._wait_for_completion(
            client=client,
            book_id=book_id,
            timeout_seconds=request.timeout_seconds,
            poll_interval_seconds=request.poll_interval_seconds,
        )
        current_job = detail_payload.get("current_job") or {}
        status = str(current_job.get("status") or "unknown")
        finished_monotonic = time.monotonic()
        translated_segments = sum(
            int(chapter.get("translated_segments") or 0)
            for chapter in detail_payload.get("chapters", [])
        )
        total_segments = sum(
            int(chapter.get("total_segments") or 0)
            for chapter in detail_payload.get("chapters", [])
        )

        export_success = False
        if status == "completed":
            export_response = client.get(
                f"/api/books/{book_id}/exports/{request.export_kind}",
            )
            export_success = export_response.status_code == 200

        checkpoint_store = CheckpointStore(runtime_root)
        checkpoint = checkpoint_store.load(job_id)
        chunk_snapshots = checkpoint_store.list_chunks(job_id)

        chunk_total = len(chunk_snapshots)
        chunk_completed = sum(1 for snapshot in chunk_snapshots if snapshot.status == "completed")
        chunk_failed = sum(1 for snapshot in chunk_snapshots if snapshot.status == "failed")
        fallback_count = sum(int(snapshot.fallback_count) for snapshot in chunk_snapshots)
        chunk_failure_reason_counts = _count_reason_codes(
            snapshot.failure_reason_code
            for snapshot in chunk_snapshots
            if snapshot.status == "failed"
        )
        chunk_fallback_reason_counts = _count_reason_codes(
            snapshot.fallback_reason_code
            for snapshot in chunk_snapshots
            if snapshot.fallback_count > 0
        )
        total_chunk_segments = sum(int(snapshot.segment_count) for snapshot in chunk_snapshots)
        total_source_chars = sum(int(snapshot.source_char_count) for snapshot in chunk_snapshots)
        total_estimated_tokens = sum(int(snapshot.estimated_tokens) for snapshot in chunk_snapshots)
        average_segments_per_chunk = (
            total_chunk_segments / chunk_total if chunk_total > 0 else 0.0
        )
        average_source_chars_per_chunk = (
            total_source_chars / chunk_total if chunk_total > 0 else 0.0
        )
        average_estimated_tokens_per_chunk = (
            total_estimated_tokens / chunk_total if chunk_total > 0 else 0.0
        )
        runtime_settings = dict(checkpoint.runtime_settings or {}) if checkpoint is not None else {}
        endpoint_capability_detection = _optional_dict(
            runtime_settings.get("endpoint_capability_detection")
        )

        if checkpoint is not None and not finished_at:
            finished_at = str(checkpoint.finished_at or checkpoint.updated_at or "")

        benchmark_name = request.benchmark_name or input_path.stem
        requested_provider_options, requested_provider_option_sources = (
            _requested_provider_metadata(request.provider)
        )
        provider_base_url = _optional_text(
            requested_provider_options.get("base_url")
            if requested_provider_options
            else None
        )
        override_target_key = RuntimeProfileOverrideStore.build_target_key(
            model_name=(
                str(current_job.get("model_name"))
                if current_job.get("model_name") is not None
                else str(request.provider.model_name if request.provider is not None else "")
            ),
            base_url=provider_base_url or "",
        )
        quality_gate_status, quality_gate_reasons = _evaluate_quality_gate(
            status=status,
            export_success=export_success,
            translated_segments=translated_segments,
            total_segments=total_segments,
            chunk_failed=chunk_failed,
            fallback_count=fallback_count,
            chunk_failure_reason_counts=chunk_failure_reason_counts,
            chunk_fallback_reason_counts=chunk_fallback_reason_counts,
            error_summary=(
                str(current_job.get("error_summary"))
                if current_job.get("error_summary") is not None
                else None
            ),
        )
        result = BenchmarkRunResult(
            run_id=run_id,
            benchmark_name=benchmark_name,
            input_path=str(input_path),
            report_json_path=str((output_dir / f"{run_id}.json").resolve()),
            report_markdown_path=str((output_dir / f"{run_id}.md").resolve()),
            runtime_root=str(runtime_root),
            status=status,
            provider_name=(
                str(current_job.get("provider_name"))
                if current_job.get("provider_name") is not None
                else None
            ),
            model_name=(
                str(current_job.get("model_name"))
                if current_job.get("model_name") is not None
                else None
            ),
            book_id=book_id,
            job_id=job_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(max(0.0, finished_monotonic - started_monotonic), 6),
            total_segments=total_segments,
            translated_segments=translated_segments,
            chunk_total=chunk_total,
            chunk_completed=chunk_completed,
            chunk_failed=chunk_failed,
            fallback_count=fallback_count,
            chunk_failure_reason_counts=chunk_failure_reason_counts,
            chunk_fallback_reason_counts=chunk_fallback_reason_counts,
            average_segments_per_chunk=round(average_segments_per_chunk, 6),
            average_source_chars_per_chunk=round(average_source_chars_per_chunk, 6),
            average_estimated_tokens_per_chunk=round(average_estimated_tokens_per_chunk, 6),
            export_success=export_success,
            quality_gate_status=quality_gate_status,
            quality_gate_reasons=quality_gate_reasons,
            runtime_profile=_optional_text(runtime_settings.get("runtime_profile")),
            runtime_profile_source=_optional_text(runtime_settings.get("runtime_profile_source")),
            runtime_setting_sources=_optional_dict_of_text(
                runtime_settings.get("runtime_setting_sources")
            ),
            requested_provider_options=requested_provider_options,
            requested_provider_option_sources=requested_provider_option_sources,
            api_mode=_optional_text(runtime_settings.get("api_mode")),
            max_requests_per_minute=_optional_int(
                runtime_settings.get("max_requests_per_minute")
            ),
            detected_context_window=_optional_int(
                runtime_settings.get("detected_context_window")
            ),
            structured_output_strength=_optional_text(
                runtime_settings.get("structured_output_strength")
            ),
            reasoning_mode=_optional_text(runtime_settings.get("reasoning_mode")),
            capability_tier=derive_capability_tier(
                api_mode=runtime_settings.get("api_mode"),
                reasoning_mode=runtime_settings.get("reasoning_mode"),
                structured_output_strength=runtime_settings.get("structured_output_strength"),
                detected_context_window=runtime_settings.get("detected_context_window"),
                max_requests_per_minute=runtime_settings.get("max_requests_per_minute"),
            ),
            provider_base_url=provider_base_url,
            override_target_key=override_target_key or None,
            models_endpoint=_optional_text(endpoint_capability_detection.get("models_endpoint")),
            endpoint_capability_strategy=_optional_text(
                endpoint_capability_detection.get("strategy")
            ),
            endpoint_capability_confidence=_optional_text(
                endpoint_capability_detection.get("confidence")
            ),
            deep_probe_status=_optional_text(
                endpoint_capability_detection.get("deep_probe_status")
            ),
            runtime_settings=runtime_settings,
            error_summary=(
                str(current_job.get("error_summary"))
                if current_job.get("error_summary") is not None
                else None
            ),
        )
        self._write_reports(result, output_dir=output_dir)
        return result

    def _wait_for_completion(
        self,
        *,
        client: TestClient,
        book_id: int,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> tuple[dict[str, object], str]:
        deadline = time.monotonic() + max(1.0, float(timeout_seconds))
        last_payload: dict[str, object] | None = None
        while time.monotonic() < deadline:
            response = client.get(f"/api/books/{book_id}")
            if response.status_code != 200:
                raise RuntimeError(f"Failed to poll benchmark job: {response.text}")
            payload = dict(response.json())
            last_payload = payload
            current_job = payload.get("current_job") or {}
            status = str(current_job.get("status") or "")
            if status in {"completed", "failed", "canceled"}:
                return payload, str(current_job.get("updated_at") or "")
            time.sleep(max(0.05, float(poll_interval_seconds)))

        raise TimeoutError(f"Benchmark translation timed out for book {book_id}.")

    @staticmethod
    def _ensure_frontend(frontend_root: Path) -> None:
        frontend_root.mkdir(parents=True, exist_ok=True)
        index_file = frontend_root / "index.html"
        if not index_file.exists():
            index_file.write_text(
                "<!doctype html><html><body><h1>Fanbook Benchmark</h1></body></html>",
                encoding="utf-8",
            )

    @staticmethod
    def _write_reports(result: BenchmarkRunResult, *, output_dir: Path) -> None:
        json_path = output_dir / f"{result.run_id}.json"
        markdown_path = output_dir / f"{result.run_id}.md"
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(
            "\n".join(
                [
                    f"# Benchmark {result.benchmark_name}",
                    "",
                    f"- input: `{result.input_path}`",
                    f"- status: `{result.status}`",
                    f"- provider/model: `{result.provider_name}` / `{result.model_name}`",
                    f"- provider_base_url: `{result.provider_base_url}`",
                    f"- override_target_key: `{result.override_target_key}`",
                    f"- duration_seconds: `{result.duration_seconds}`",
                    f"- segments: `{result.translated_segments}/{result.total_segments}`",
                    f"- chunk_total: `{result.chunk_total}`",
                    f"- chunk_completed: `{result.chunk_completed}`",
                    f"- chunk_failed: `{result.chunk_failed}`",
                    f"- fallback_count: `{result.fallback_count}`",
                    f"- quality_gate_status: `{result.quality_gate_status}`",
                    f"- runtime_profile: `{result.runtime_profile}`",
                    f"- runtime_profile_source: `{result.runtime_profile_source}`",
                    f"- runtime_setting_source_keys: `{', '.join(sorted(result.runtime_setting_sources)) or 'none'}`",
                    f"- api_mode: `{result.api_mode}`",
                    f"- max_requests_per_minute: `{result.max_requests_per_minute}`",
                    f"- detected_context_window: `{result.detected_context_window}`",
                    f"- structured_output_strength: `{result.structured_output_strength}`",
                    f"- reasoning_mode: `{result.reasoning_mode}`",
                    f"- capability_tier: `{result.capability_tier}`",
                    f"- models_endpoint: `{result.models_endpoint}`",
                    f"- endpoint_capability_strategy: `{result.endpoint_capability_strategy}`",
                    f"- endpoint_capability_confidence: `{result.endpoint_capability_confidence}`",
                    f"- deep_probe_status: `{result.deep_probe_status}`",
                    f"- average_segments_per_chunk: `{result.average_segments_per_chunk}`",
                    f"- average_source_chars_per_chunk: `{result.average_source_chars_per_chunk}`",
                    f"- average_estimated_tokens_per_chunk: `{result.average_estimated_tokens_per_chunk}`",
                    f"- export_success: `{result.export_success}`",
                    "",
                    "## Quality Gate",
                    "",
                    f"- status: `{result.quality_gate_status}`",
                    f"- reasons: `{', '.join(result.quality_gate_reasons) if result.quality_gate_reasons else 'none'}`",
                    f"- chunk_failure_reason_counts: `{json.dumps(result.chunk_failure_reason_counts, ensure_ascii=False, sort_keys=True)}`",
                    f"- chunk_fallback_reason_counts: `{json.dumps(result.chunk_fallback_reason_counts, ensure_ascii=False, sort_keys=True)}`",
                    "",
                    "## Runtime Setting Sources",
                    "",
                    "```json",
                    json.dumps(result.runtime_setting_sources, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "## Runtime Settings",
                    "",
                    "```json",
                    json.dumps(result.runtime_settings, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "## Requested Provider Options",
                    "",
                    "```json",
                    json.dumps(result.requested_provider_options, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "## Requested Provider Option Sources",
                    "",
                    "```json",
                    json.dumps(
                        result.requested_provider_option_sources,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "```",
                ]
            ),
            encoding="utf-8",
        )

def run_translation_benchmark(
    *,
    epub_path: str | Path,
    runtime_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    provider_name: str = "mock",
    model_name: str | None = None,
    provider_options: dict[str, object] | None = None,
    benchmark_name: str | None = None,
    export_kind="bilingual",
) -> BenchmarkArtifacts:
    normalized_options = dict(provider_options or {})
    provider = ProviderConfigRequest(
        provider_name=provider_name,
        model_name=model_name,
        api_key=_optional_text(normalized_options.pop("api_key", None)),
        base_url=_optional_text(normalized_options.pop("base_url", None)),
        runtime_profile=_optional_text(normalized_options.pop("runtime_profile", None)),
        detected_context_window=_optional_int(
            normalized_options.pop("detected_context_window", None)
        ),
        structured_output_strength=_optional_text(
            normalized_options.pop("structured_output_strength", None)
        ),
        reasoning_mode=_optional_text(normalized_options.pop("reasoning_mode", None)),
        api_mode=_optional_text(normalized_options.pop("api_mode", None)),
        reasoning_effort=_optional_text(normalized_options.pop("reasoning_effort", None)),
        timeout_seconds=_optional_float(normalized_options.pop("timeout_seconds", None)),
        max_requests_per_minute=_optional_int(
            normalized_options.pop("max_requests_per_minute", None)
        ),
        global_max_concurrency=_optional_int(normalized_options.pop("global_max_concurrency", None)),
        per_chapter_concurrency=_optional_int(normalized_options.pop("per_chapter_concurrency", None)),
        min_per_chapter_concurrency=_optional_int(normalized_options.pop("min_per_chapter_concurrency", None)),
        adaptive_per_chapter_concurrency=_optional_bool(
            normalized_options.pop("adaptive_per_chapter_concurrency", None)
        ),
        max_input_tokens=_optional_int(normalized_options.pop("max_input_tokens", None)),
        reserved_output_tokens=_optional_int(normalized_options.pop("reserved_output_tokens", None)),
        max_output_tokens=_optional_int(normalized_options.pop("max_output_tokens", None)),
        chunk_target_tokens=_optional_int(normalized_options.pop("chunk_target_tokens", None)),
        context_segments_before=_optional_int(normalized_options.pop("context_segments_before", None)),
        context_segments_after=_optional_int(normalized_options.pop("context_segments_after", None)),
        translation_memory_size=_optional_int(normalized_options.pop("translation_memory_size", None)),
        retry_max_attempts=_optional_int(normalized_options.pop("retry_max_attempts", None)),
        duplicate_text_cache_enabled=_optional_bool(
            normalized_options.pop("duplicate_text_cache_enabled", None)
        ),
        duplicate_text_cache_min_chars=_optional_int(
            normalized_options.pop("duplicate_text_cache_min_chars", None)
        ),
        dynamic_rate_control_enabled=_optional_bool(
            normalized_options.pop("dynamic_rate_control_enabled", None)
        ),
        dynamic_rate_control_initial_global_concurrency=_optional_int(
            normalized_options.pop("dynamic_rate_control_initial_global_concurrency", None)
        ),
        dynamic_rate_control_min_global_concurrency=_optional_int(
            normalized_options.pop("dynamic_rate_control_min_global_concurrency", None)
        ),
        dynamic_rate_control_scale_up_success_streak=_optional_int(
            normalized_options.pop("dynamic_rate_control_scale_up_success_streak", None)
        ),
    )
    result = TranslationBenchmarkRunner().run(
        BenchmarkRunRequest(
            input_path=Path(epub_path),
            provider=provider,
            output_dir=Path(output_dir) if output_dir is not None else None,
            runtime_root=Path(runtime_root) if runtime_root is not None else None,
            export_kind=str(getattr(export_kind, "value", export_kind)),
            benchmark_name=benchmark_name,
        )
    )
    return BenchmarkArtifacts(
        json_path=Path(result.report_json_path),
        markdown_path=Path(result.report_markdown_path),
        result=result,
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(value)


def _optional_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _optional_dict_of_text(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = str(key or "").strip()
        normalized_value = str(item or "").strip()
        if not normalized_key or not normalized_value:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _requested_provider_metadata(
    provider: ProviderConfigRequest | None,
) -> tuple[dict[str, object], dict[str, str]]:
    if provider is None:
        return {}, {}
    requested_provider_options = dict(provider.options_dict())
    requested_provider_options.pop("api_key", None)
    requested_provider_option_sources = _optional_dict_of_text(
        requested_provider_options.pop(RUNTIME_OPTION_SOURCE_METADATA_KEY, None)
    )
    return requested_provider_options, requested_provider_option_sources


def _count_reason_codes(codes) -> dict[str, int]:
    counts: dict[str, int] = {}
    for code in codes:
        normalized = str(code or "").strip()
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _evaluate_quality_gate(
    *,
    status: str,
    export_success: bool,
    translated_segments: int,
    total_segments: int,
    chunk_failed: int,
    fallback_count: int,
    chunk_failure_reason_counts: dict[str, int],
    chunk_fallback_reason_counts: dict[str, int],
    error_summary: str | None,
) -> tuple[str, tuple[str, ...]]:
    reject_reasons: list[str] = []
    if status != "completed":
        reject_reasons.append(f"job_status:{status}")
    if translated_segments != total_segments:
        reject_reasons.append("incomplete_translation")
    if not export_success:
        reject_reasons.append("export_failed")
    if chunk_failed > 0:
        reject_reasons.append("chunk_failures_present")
    if reject_reasons:
        return "reject", tuple(reject_reasons)

    review_reasons: list[str] = []
    if fallback_count > 0:
        review_reasons.append("fallbacks_present")
    if chunk_failure_reason_counts:
        review_reasons.extend(
            f"chunk_failure:{code}"
            for code in sorted(chunk_failure_reason_counts)
        )
    if chunk_fallback_reason_counts:
        review_reasons.extend(
            f"chunk_fallback:{code}"
            for code in sorted(chunk_fallback_reason_counts)
        )
    if error_summary:
        review_reasons.append("error_summary_present")
    if review_reasons:
        return "needs_review", tuple(review_reasons)
    return "pass", ()
