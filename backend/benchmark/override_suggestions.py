from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from backend.benchmark.capability_tier import derive_capability_tier
from backend.core.translation.runtime_settings import (
    MODEL_OR_ENDPOINT_RUNTIME_PROFILE_OVERRIDES,
    RUNTIME_PROFILES,
    detect_runtime_profile,
    normalize_api_mode,
    normalize_reasoning_mode,
    normalize_runtime_profile,
    normalize_structured_output_strength,
)
from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore

_PASS_LIKE_QUALITY_GATE_STATUSES = {"pass"}
_PRESET_SIGNATURE_FIELDS = (
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
)


@dataclass(slots=True, frozen=True)
class BenchmarkReportEvidence:
    report_path: str
    report_format: str
    benchmark_name: str | None = None
    runtime_root: str | None = None
    job_id: int | None = None
    provider_name: str | None = None
    model_name: str | None = None
    provider_base_url: str | None = None
    override_target_key: str | None = None
    status: str | None = None
    quality_gate_status: str | None = None
    duration_seconds: float | None = None
    runtime_profile: str | None = None
    runtime_profile_source: str | None = None
    requested_runtime_profile: str | None = None
    candidate_runtime_profile: str | None = None
    candidate_runtime_profile_source: str | None = None
    inferable_runtime_profile: str | None = None
    api_mode: str | None = None
    max_requests_per_minute: int | None = None
    detected_context_window: int | None = None
    structured_output_strength: str | None = None
    reasoning_mode: str | None = None
    capability_tier: str | None = None
    chunk_failed: int = 0
    fallback_count: int = 0
    chunk_failure_reason_counts: dict[str, int] = field(default_factory=dict)
    chunk_fallback_reason_counts: dict[str, int] = field(default_factory=dict)
    runtime_setting_sources: dict[str, str] = field(default_factory=dict)
    requested_provider_options: dict[str, object] = field(default_factory=dict)
    requested_provider_option_sources: dict[str, str] = field(default_factory=dict)
    runtime_settings: dict[str, object] = field(default_factory=dict)
    models_endpoint: str | None = None
    endpoint_capability_strategy: str | None = None
    endpoint_capability_confidence: str | None = None
    deep_probe_status: str | None = None
    error_summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class RuntimeProfileOverrideSuggestion:
    target_key: str
    model_name: str
    base_url: str
    status: str
    suggested_runtime_profile: str | None = None
    confidence: str = "low"
    rationale: tuple[str, ...] = ()
    supporting_reports: tuple[str, ...] = ()
    rejected_reports: tuple[str, ...] = ()
    curated_override_snippet: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class BenchmarkOverrideSuggestionReport:
    evidences: tuple[BenchmarkReportEvidence, ...]
    suggestions: tuple[RuntimeProfileOverrideSuggestion, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "evidences": [evidence.to_dict() for evidence in self.evidences],
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
            "warnings": list(self.warnings),
        }

    def render_markdown(self) -> str:
        suggested = sum(
            1 for suggestion in self.suggestions if suggestion.status == "suggested"
        )
        already_curated = sum(
            1 for suggestion in self.suggestions if suggestion.status == "already_curated"
        )
        inferable = sum(
            1
            for suggestion in self.suggestions
            if suggestion.status == "inferable_without_curated_override"
        )
        lines = [
            "# Runtime Profile Override Suggestions",
            "",
            f"- report_count: `{len(self.evidences)}`",
            f"- target_group_count: `{len(self.suggestions)}`",
            f"- suggested_count: `{suggested}`",
            f"- already_curated_count: `{already_curated}`",
            f"- inferable_without_curated_override_count: `{inferable}`",
        ]
        if self.warnings:
            lines.extend(
                [
                    "",
                    "## Warnings",
                    "",
                ]
            )
            lines.extend(f"- {warning}" for warning in self.warnings)
        if not self.suggestions:
            lines.extend(["", "## Targets", "", "- No target-qualified benchmark evidence was found."])
            return "\n".join(lines)

        lines.extend(["", "## Targets", ""])
        for suggestion in self.suggestions:
            lines.append(f"### `{suggestion.target_key}`")
            lines.append("")
            lines.append(f"- status: `{suggestion.status}`")
            lines.append(f"- suggested_runtime_profile: `{suggestion.suggested_runtime_profile}`")
            lines.append(f"- confidence: `{suggestion.confidence}`")
            if suggestion.curated_override_snippet:
                lines.append("- curated_override_snippet:")
                lines.append("```python")
                lines.append(suggestion.curated_override_snippet)
                lines.append("```")
            if suggestion.rationale:
                lines.append("- rationale:")
                lines.extend(f"  - {item}" for item in suggestion.rationale)
            if suggestion.supporting_reports:
                lines.append("- supporting_reports:")
                lines.extend(f"  - `{item}`" for item in suggestion.supporting_reports)
            if suggestion.rejected_reports:
                lines.append("- rejected_reports:")
                lines.extend(f"  - `{item}`" for item in suggestion.rejected_reports)
            lines.append("")
        return "\n".join(lines).rstrip()


def suggest_runtime_profile_overrides(
    report_paths: Iterable[str | Path],
    *,
    fallback_base_url: str | None = None,
    fallback_model_name: str | None = None,
    fallback_runtime_profile: str | None = None,
) -> BenchmarkOverrideSuggestionReport:
    normalized_paths = _normalize_report_paths(report_paths)
    evidences: list[BenchmarkReportEvidence] = []
    warnings: list[str] = []
    for path in normalized_paths:
        try:
            evidences.append(
                load_benchmark_report(
                    path,
                    fallback_base_url=fallback_base_url,
                    fallback_model_name=fallback_model_name,
                    fallback_runtime_profile=fallback_runtime_profile,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"Failed to load `{path}`: {exc}")

    grouped: dict[str, list[BenchmarkReportEvidence]] = {}
    for evidence in evidences:
        if not evidence.override_target_key:
            warnings.append(
                f"`{evidence.report_path}` does not include a target key. "
                "Pass `--base-url` or rerun benchmark with provider_base_url recorded."
            )
            continue
        grouped.setdefault(evidence.override_target_key, []).append(evidence)

    suggestions = tuple(
        _build_target_suggestion(grouped[target_key])
        for target_key in sorted(grouped)
    )
    return BenchmarkOverrideSuggestionReport(
        evidences=tuple(evidences),
        suggestions=suggestions,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def load_benchmark_report(
    path: str | Path,
    *,
    fallback_base_url: str | None = None,
    fallback_model_name: str | None = None,
    fallback_runtime_profile: str | None = None,
) -> BenchmarkReportEvidence:
    report_path = Path(path).resolve()
    payload, report_format = _load_report_payload(report_path)
    checkpoint_payload = _load_checkpoint_payload(
        runtime_root=payload.get("runtime_root"),
        job_id=payload.get("job_id"),
    )
    runtime_settings = _merge_runtime_settings(
        checkpoint_payload.get("runtime_settings"),
        payload.get("runtime_settings"),
    )
    runtime_target = _as_dict(runtime_settings.get("runtime_target"))
    capability_detection = _as_dict(runtime_settings.get("endpoint_capability_detection"))
    runtime_setting_sources = _dict_of_text(
        payload.get("runtime_setting_sources")
    ) or _dict_of_text(runtime_settings.get("runtime_setting_sources"))
    requested_provider_options = _as_dict(payload.get("requested_provider_options"))
    requested_provider_option_sources = _dict_of_text(
        payload.get("requested_provider_option_sources")
    )
    models_endpoint = _optional_text(
        payload.get("models_endpoint") or capability_detection.get("models_endpoint")
    )
    provider_base_url = _optional_text(
        payload.get("provider_base_url")
        or requested_provider_options.get("base_url")
        or payload.get("base_url")
        or runtime_target.get("base_url")
        or _derive_base_url_from_models_endpoint(models_endpoint)
        or fallback_base_url
    )
    provider_name = _optional_text(
        payload.get("provider_name") or checkpoint_payload.get("provider_name")
    )
    model_name = _optional_text(
        payload.get("model_name")
        or checkpoint_payload.get("model_name")
        or runtime_target.get("model_name")
        or fallback_model_name
    )
    if provider_name is None or model_name is None:
        raise ValueError(f"`{report_path}` is not a benchmark report with provider/model metadata.")
    requested_runtime_profile = normalize_runtime_profile(
        requested_provider_options.get("runtime_profile") or fallback_runtime_profile
    )
    runtime_profile = normalize_runtime_profile(
        payload.get("runtime_profile") or runtime_settings.get("runtime_profile")
    )
    runtime_profile_source = _optional_text(
        payload.get("runtime_profile_source")
        or runtime_settings.get("runtime_profile_source")
    )
    api_mode = normalize_api_mode(
        payload.get("api_mode")
        or runtime_settings.get("api_mode")
        or requested_provider_options.get("api_mode")
    )
    max_requests_per_minute = _optional_int(
        payload.get("max_requests_per_minute")
        or runtime_settings.get("max_requests_per_minute")
        or requested_provider_options.get("max_requests_per_minute")
    )
    detected_context_window = _optional_int(
        payload.get("detected_context_window")
        or runtime_settings.get("detected_context_window")
        or requested_provider_options.get("detected_context_window")
    )
    structured_output_strength = normalize_structured_output_strength(
        payload.get("structured_output_strength")
        or runtime_settings.get("structured_output_strength")
        or requested_provider_options.get("structured_output_strength")
    )
    reasoning_mode = normalize_reasoning_mode(
        payload.get("reasoning_mode")
        or runtime_settings.get("reasoning_mode")
        or requested_provider_options.get("reasoning_mode")
    )
    override_target_key = (
        _optional_text(payload.get("override_target_key"))
        or _optional_text(runtime_target.get("target_key"))
        or (
        RuntimeProfileOverrideStore.build_target_key(
            model_name=model_name or "",
            base_url=provider_base_url or "",
        )
        or None
    ))
    inferable_runtime_profile = detect_runtime_profile(
        provider_name=provider_name,
        model_name=model_name,
        api_mode=api_mode,
        max_requests_per_minute=max_requests_per_minute,
        detected_context_window=detected_context_window,
        structured_output_strength=structured_output_strength,
        reasoning_mode=reasoning_mode,
    )
    candidate_runtime_profile, candidate_runtime_profile_source = _resolve_candidate_runtime_profile(
        runtime_profile=runtime_profile,
        runtime_profile_source=runtime_profile_source,
        requested_runtime_profile=requested_runtime_profile,
        runtime_settings=runtime_settings,
        error_summary=_optional_text(payload.get("error_summary")),
        chunk_failure_reason_counts=_dict_of_int(payload.get("chunk_failure_reason_counts")),
        chunk_fallback_reason_counts=_dict_of_int(payload.get("chunk_fallback_reason_counts")),
    )
    return BenchmarkReportEvidence(
        report_path=str(report_path),
        report_format=report_format,
        benchmark_name=_optional_text(payload.get("benchmark_name")),
        runtime_root=_optional_text(payload.get("runtime_root")),
        job_id=_optional_int(payload.get("job_id")),
        provider_name=provider_name,
        model_name=model_name,
        provider_base_url=provider_base_url,
        override_target_key=override_target_key,
        status=_optional_text(payload.get("status")),
        quality_gate_status=_optional_text(payload.get("quality_gate_status")),
        duration_seconds=_optional_float(payload.get("duration_seconds")),
        runtime_profile=runtime_profile,
        runtime_profile_source=runtime_profile_source,
        requested_runtime_profile=requested_runtime_profile,
        candidate_runtime_profile=candidate_runtime_profile,
        candidate_runtime_profile_source=candidate_runtime_profile_source,
        inferable_runtime_profile=inferable_runtime_profile,
        api_mode=api_mode,
        max_requests_per_minute=max_requests_per_minute,
        detected_context_window=detected_context_window,
        structured_output_strength=structured_output_strength,
        reasoning_mode=reasoning_mode,
        capability_tier=_optional_text(payload.get("capability_tier"))
        or derive_capability_tier(
            api_mode=api_mode,
            reasoning_mode=reasoning_mode,
            structured_output_strength=structured_output_strength,
            detected_context_window=detected_context_window,
            max_requests_per_minute=max_requests_per_minute,
        ),
        chunk_failed=_optional_int(payload.get("chunk_failed")) or 0,
        fallback_count=_optional_int(payload.get("fallback_count")) or 0,
        chunk_failure_reason_counts=_dict_of_int(payload.get("chunk_failure_reason_counts")),
        chunk_fallback_reason_counts=_dict_of_int(payload.get("chunk_fallback_reason_counts")),
        runtime_setting_sources=runtime_setting_sources,
        requested_provider_options=requested_provider_options,
        requested_provider_option_sources=requested_provider_option_sources,
        runtime_settings=runtime_settings,
        models_endpoint=models_endpoint,
        endpoint_capability_strategy=_optional_text(
            payload.get("endpoint_capability_strategy")
            or capability_detection.get("strategy")
        ),
        endpoint_capability_confidence=_optional_text(
            payload.get("endpoint_capability_confidence")
            or capability_detection.get("confidence")
        ),
        deep_probe_status=_optional_text(
            payload.get("deep_probe_status")
            or capability_detection.get("deep_probe_status")
        ),
        error_summary=_optional_text(payload.get("error_summary")),
    )


def _normalize_report_paths(report_paths: Iterable[str | Path]) -> tuple[Path, ...]:
    normalized: dict[str, Path] = {}
    for value in report_paths:
        path = Path(value)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.suffix.lower() not in {".json", ".md"}:
                    continue
                if child.suffix.lower() == ".md" and child.with_suffix(".json").exists():
                    continue
                normalized[str(child.resolve()).lower()] = child.resolve()
            continue
        normalized[str(path.resolve()).lower()] = path.resolve()
    return tuple(normalized.values())


def _load_report_payload(path: Path) -> tuple[dict[str, Any], str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json_dict(path), "json"
    if suffix == ".md":
        sibling_json = path.with_suffix(".json")
        if sibling_json.exists():
            return _load_json_dict(sibling_json), "markdown+json"
        return _parse_markdown_report(path.read_text(encoding="utf-8")), "markdown"
    raise ValueError(f"Unsupported benchmark report format: {path.suffix}")


def _load_checkpoint_payload(
    *,
    runtime_root: object,
    job_id: object,
) -> dict[str, Any]:
    normalized_runtime_root = _optional_text(runtime_root)
    normalized_job_id = _optional_int(job_id)
    if normalized_runtime_root is None or normalized_job_id is None:
        return {}
    state_path = (
        Path(normalized_runtime_root)
        / "checkpoints"
        / str(normalized_job_id)
        / "state.json"
    )
    if not state_path.exists():
        return {}
    return _load_json_dict(state_path)


def _load_json_dict(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in `{path}`.")
    return data


def _merge_runtime_settings(*candidates: object) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key, value in candidate.items():
            merged[key] = value
    return merged


def _derive_base_url_from_models_endpoint(value: object) -> str | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    if normalized.lower().endswith("/models"):
        return normalized[:-7].rstrip("/") or None
    return None


def _parse_markdown_report(markdown_text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    runtime_setting_sources: dict[str, str] = {}
    runtime_settings: dict[str, object] = {}
    requested_provider_options: dict[str, object] = {}
    requested_provider_option_sources: dict[str, str] = {}
    current_json_heading: str | None = None
    inside_json_block = False
    buffer: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_json_heading = line[3:].strip().lower()
            continue
        if line == "```json":
            inside_json_block = True
            buffer = []
            continue
        if inside_json_block and line == "```":
            inside_json_block = False
            parsed = _safe_parse_json_object("\n".join(buffer))
            if current_json_heading == "runtime setting sources":
                runtime_setting_sources = _dict_of_text(parsed)
            elif current_json_heading == "runtime settings":
                runtime_settings = _as_dict(parsed)
            elif current_json_heading == "requested provider options":
                requested_provider_options = _as_dict(parsed)
            elif current_json_heading == "requested provider option sources":
                requested_provider_option_sources = _dict_of_text(parsed)
            buffer = []
            continue
        if inside_json_block:
            buffer.append(raw_line)
            continue
        bullet_match = re.match(r"^- ([^:]+): `?(.*?)`?$", line.strip())
        if not bullet_match:
            continue
        key = bullet_match.group(1).strip().lower()
        value = bullet_match.group(2).strip()
        if key == "provider/model":
            provider_name, _, model_name = value.partition(" / ")
            payload["provider_name"] = provider_name.strip("` ")
            payload["model_name"] = model_name.strip("` ")
            continue
        payload[_normalize_markdown_key(key)] = value.strip("` ")

    if runtime_setting_sources:
        payload["runtime_setting_sources"] = runtime_setting_sources
    if runtime_settings:
        payload["runtime_settings"] = runtime_settings
    if requested_provider_options:
        payload["requested_provider_options"] = requested_provider_options
    if requested_provider_option_sources:
        payload["requested_provider_option_sources"] = requested_provider_option_sources
    return payload


def _normalize_markdown_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized


def _safe_parse_json_object(raw_value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _resolve_candidate_runtime_profile(
    *,
    runtime_profile: str | None,
    runtime_profile_source: str | None,
    requested_runtime_profile: str | None,
    runtime_settings: dict[str, object],
    error_summary: str | None,
    chunk_failure_reason_counts: dict[str, int],
    chunk_fallback_reason_counts: dict[str, int],
) -> tuple[str | None, str | None]:
    if runtime_profile is not None:
        return runtime_profile, (
            f"report.runtime_profile:{runtime_profile_source or 'unknown'}"
        )
    if requested_runtime_profile is not None:
        return requested_runtime_profile, "requested_provider_options.runtime_profile"
    preset_match = _infer_runtime_profile_from_runtime_settings(runtime_settings)
    if preset_match is not None:
        return preset_match, "runtime_settings_exact_preset"
    if _has_rate_limit_signal(
        error_summary=error_summary,
        chunk_failure_reason_counts=chunk_failure_reason_counts,
        chunk_fallback_reason_counts=chunk_fallback_reason_counts,
    ):
        return "generic_rate_limited", "benchmark_rate_limit_signal"
    return None, None


def _infer_runtime_profile_from_runtime_settings(
    runtime_settings: dict[str, object],
) -> str | None:
    if not runtime_settings:
        return None
    matches: list[str] = []
    for runtime_profile, preset in RUNTIME_PROFILES.items():
        preset_dict = asdict(preset)
        if all(
            runtime_settings.get(field_name) == preset_dict.get(field_name)
            for field_name in _PRESET_SIGNATURE_FIELDS
        ):
            matches.append(runtime_profile)
    if len(matches) == 1:
        return matches[0]
    return None


def _has_rate_limit_signal(
    *,
    error_summary: str | None,
    chunk_failure_reason_counts: dict[str, int],
    chunk_fallback_reason_counts: dict[str, int],
) -> bool:
    if "rate_limited" in chunk_failure_reason_counts:
        return True
    if "rate_limited" in chunk_fallback_reason_counts:
        return True
    normalized_error_summary = str(error_summary or "").strip().lower()
    return "rate limit" in normalized_error_summary or "status 429" in normalized_error_summary


def _build_target_suggestion(
    evidences: list[BenchmarkReportEvidence],
) -> RuntimeProfileOverrideSuggestion:
    first = evidences[0]
    target_key = first.override_target_key or ""
    model_name = first.model_name or ""
    base_url = first.provider_base_url or ""

    existing_curated = normalize_runtime_profile(
        MODEL_OR_ENDPOINT_RUNTIME_PROFILE_OVERRIDES.get(target_key)
    )
    if existing_curated is not None:
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="already_curated",
            suggested_runtime_profile=existing_curated,
            confidence="high",
            rationale=(
                "target already exists in MODEL_OR_ENDPOINT_RUNTIME_PROFILE_OVERRIDES",
            ),
            supporting_reports=tuple(sorted(_report_labels(evidences))),
            curated_override_snippet=f'"{target_key}": "{existing_curated}",',
        )

    supporting = [
        evidence
        for evidence in evidences
        if evidence.candidate_runtime_profile is not None
        and (evidence.quality_gate_status or "").strip().lower()
        in _PASS_LIKE_QUALITY_GATE_STATUSES
    ]
    strong_supporting = [
        evidence
        for evidence in supporting
        if _is_strong_curated_evidence(evidence)
    ]
    rejected = [
        evidence
        for evidence in evidences
        if (evidence.quality_gate_status or "").strip().lower() == "reject"
    ]
    support_by_profile: dict[str, list[BenchmarkReportEvidence]] = {}
    for evidence in supporting:
        support_by_profile.setdefault(evidence.candidate_runtime_profile or "", []).append(
            evidence
        )

    if not support_by_profile:
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="insufficient_evidence",
            confidence="low",
            rationale=(
                "no pass benchmark report contained a usable runtime_profile candidate",
            ),
            rejected_reports=tuple(sorted(_report_labels(rejected))),
        )

    if len(support_by_profile) > 1:
        conflicts = ", ".join(sorted(support_by_profile))
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="conflict",
            confidence="low",
            rationale=(f"conflicting candidate runtime profiles: {conflicts}",),
            supporting_reports=tuple(sorted(_report_labels(supporting))),
            rejected_reports=tuple(sorted(_report_labels(rejected))),
        )

    suggested_runtime_profile = next(iter(support_by_profile))
    supporting_reports = support_by_profile[suggested_runtime_profile]
    inferable_profiles = {
        evidence.inferable_runtime_profile
        for evidence in supporting_reports
        if evidence.inferable_runtime_profile is not None
    }
    all_support_inferable = (
        bool(supporting_reports)
        and inferable_profiles == {suggested_runtime_profile}
    )
    rationale = [
        f"supporting_reports={len(supporting_reports)}",
        f"candidate_source={_summarize_candidate_sources(supporting_reports)}",
    ]
    if strong_supporting:
        rationale.append(f"strong_supporting_reports={len(strong_supporting)}")
    else:
        rationale.append("strong_supporting_reports=0")
    if all_support_inferable:
        rationale.append("generic detection already infers the same runtime_profile")
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="inferable_without_curated_override",
            suggested_runtime_profile=suggested_runtime_profile,
            confidence="medium" if len(supporting_reports) >= 2 else "low",
            rationale=tuple(rationale),
            supporting_reports=tuple(sorted(_report_labels(supporting_reports))),
            rejected_reports=tuple(sorted(_report_labels(rejected))),
            curated_override_snippet=f'"{target_key}": "{suggested_runtime_profile}",',
        )

    rationale.append("generic detection does not reliably infer the same runtime_profile")
    if len(supporting_reports) < 2:
        rationale.append("at least two pass reports are required for a curated suggestion")
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="insufficient_evidence",
            suggested_runtime_profile=suggested_runtime_profile,
            confidence="low",
            rationale=tuple(rationale),
            supporting_reports=tuple(sorted(_report_labels(supporting_reports))),
            rejected_reports=tuple(sorted(_report_labels(rejected))),
        )
    if not strong_supporting:
        rationale.append("pass evidence is manual or weak; no strong detected/high-confidence support")
        return RuntimeProfileOverrideSuggestion(
            target_key=target_key,
            model_name=model_name,
            base_url=base_url,
            status="insufficient_evidence",
            suggested_runtime_profile=suggested_runtime_profile,
            confidence="low",
            rationale=tuple(rationale),
            supporting_reports=tuple(sorted(_report_labels(supporting_reports))),
            rejected_reports=tuple(sorted(_report_labels(rejected))),
        )
    confidence = "high" if len(strong_supporting) >= 2 else "medium"
    if rejected:
        rationale.append(f"rejected_reports={len(rejected)}")
    return RuntimeProfileOverrideSuggestion(
        target_key=target_key,
        model_name=model_name,
        base_url=base_url,
        status="suggested",
        suggested_runtime_profile=suggested_runtime_profile,
        confidence=confidence,
        rationale=tuple(rationale),
        supporting_reports=tuple(sorted(_report_labels(supporting_reports))),
        rejected_reports=tuple(sorted(_report_labels(rejected))),
        curated_override_snippet=f'"{target_key}": "{suggested_runtime_profile}",',
    )


def _is_strong_curated_evidence(evidence: BenchmarkReportEvidence) -> bool:
    runtime_profile_source = str(evidence.runtime_profile_source or "").strip().lower()
    if runtime_profile_source in {"detected", "override"}:
        return True
    endpoint_confidence = str(evidence.endpoint_capability_confidence or "").strip().lower()
    if endpoint_confidence == "high":
        return True
    candidate_source = str(evidence.candidate_runtime_profile_source or "").strip().lower()
    if candidate_source.startswith("report.runtime_profile:detected"):
        return True
    if candidate_source.startswith("report.runtime_profile:override"):
        return True
    return False


def _summarize_candidate_sources(
    evidences: Iterable[BenchmarkReportEvidence],
) -> str:
    counts: dict[str, int] = {}
    for evidence in evidences:
        source = evidence.candidate_runtime_profile_source or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return ", ".join(
        f"{source} x{counts[source]}" for source in sorted(counts)
    )


def _report_labels(evidences: Iterable[BenchmarkReportEvidence]) -> list[str]:
    labels: list[str] = []
    for evidence in evidences:
        label = evidence.benchmark_name or Path(evidence.report_path).name
        labels.append(label)
    return labels


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _dict_of_text(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _optional_text(key)
        normalized_value = _optional_text(item)
        if normalized_key is None or normalized_value is None:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _dict_of_int(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, item in value.items():
        normalized_key = _optional_text(key)
        normalized_value = _optional_int(item)
        if normalized_key is None or normalized_value is None:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
