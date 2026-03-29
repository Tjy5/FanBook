from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from backend.benchmark.override_suggestions import (
    BenchmarkReportEvidence,
    load_benchmark_report,
)


@dataclass(slots=True, frozen=True)
class BenchmarkBaselineGroup:
    runtime_profile: str
    capability_tier: str
    report_count: int
    pass_count: int
    needs_review_count: int
    reject_count: int
    unique_target_count: int
    precise_non_mock_target_count: int
    mock_target_count: int
    unique_model_count: int
    fastest_pass_report: str | None = None
    fastest_pass_duration_seconds: float | None = None
    targets: tuple[str, ...] = ()
    benchmark_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class BenchmarkCoverageGap:
    runtime_profile: str
    capability_tier: str
    unique_target_count: int
    precise_non_mock_target_count: int
    pass_count: int
    report_count: int
    reason: str
    actionability: str
    recommendation: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class BenchmarkBaselineSummary:
    evidences: tuple[BenchmarkReportEvidence, ...]
    groups: tuple[BenchmarkBaselineGroup, ...]
    coverage_gaps: tuple[BenchmarkCoverageGap, ...]
    real_benchmark_priorities: tuple[BenchmarkCoverageGap, ...]
    metadata_refresh_only_gaps: tuple[BenchmarkCoverageGap, ...]
    ignored_coverage_gaps: tuple[BenchmarkCoverageGap, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "evidences": [evidence.to_dict() for evidence in self.evidences],
            "groups": [group.to_dict() for group in self.groups],
            "coverage_gaps": [gap.to_dict() for gap in self.coverage_gaps],
            "real_benchmark_priorities": [
                gap.to_dict() for gap in self.real_benchmark_priorities
            ],
            "metadata_refresh_only_gaps": [
                gap.to_dict() for gap in self.metadata_refresh_only_gaps
            ],
            "ignored_coverage_gaps": [gap.to_dict() for gap in self.ignored_coverage_gaps],
            "warnings": list(self.warnings),
        }

    def render_markdown(self) -> str:
        lines = [
            "# Benchmark Baseline Summary",
            "",
            f"- report_count: `{len(self.evidences)}`",
            f"- group_count: `{len(self.groups)}`",
            f"- coverage_gap_count: `{len(self.coverage_gaps)}`",
            f"- real_benchmark_priority_count: `{len(self.real_benchmark_priorities)}`",
            f"- metadata_refresh_only_count: `{len(self.metadata_refresh_only_gaps)}`",
            f"- ignored_coverage_gap_count: `{len(self.ignored_coverage_gaps)}`",
        ]
        if self.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)

        if self.groups:
            lines.extend(["", "## Groups", ""])
            for group in self.groups:
                lines.extend(
                    [
                        f"### `{group.runtime_profile}` / `{group.capability_tier}`",
                        "",
                        f"- report_count: `{group.report_count}`",
                        f"- pass_count: `{group.pass_count}`",
                        f"- needs_review_count: `{group.needs_review_count}`",
                        f"- reject_count: `{group.reject_count}`",
                        f"- unique_target_count: `{group.unique_target_count}`",
                        f"- precise_non_mock_target_count: `{group.precise_non_mock_target_count}`",
                        f"- mock_target_count: `{group.mock_target_count}`",
                        f"- unique_model_count: `{group.unique_model_count}`",
                        f"- fastest_pass_report: `{group.fastest_pass_report}`",
                        f"- fastest_pass_duration_seconds: `{group.fastest_pass_duration_seconds}`",
                    ]
                )
                if group.targets:
                    lines.append("- targets:")
                    lines.extend(f"  - `{target}`" for target in group.targets)
                if group.benchmark_names:
                    lines.append("- benchmark_names:")
                    lines.extend(f"  - `{name}`" for name in group.benchmark_names)
                lines.append("")

        if self.real_benchmark_priorities:
            lines.extend(["", "## Real Benchmark Priorities", ""])
            for gap in self.real_benchmark_priorities:
                lines.append(
                    "- "
                    f"`{gap.runtime_profile}` / `{gap.capability_tier}` -> "
                    f"`{gap.reason}` "
                    f"[`{gap.actionability}`] "
                    f"(precise_non_mock_targets={gap.precise_non_mock_target_count}, "
                    f"targets={gap.unique_target_count}, pass={gap.pass_count}, reports={gap.report_count}) "
                    f"- {gap.recommendation}"
                )

        if self.coverage_gaps:
            lines.extend(["", "## Coverage Gaps", ""])
            for gap in self.coverage_gaps:
                lines.append(
                    "- "
                    f"`{gap.runtime_profile}` / `{gap.capability_tier}` -> "
                    f"`{gap.reason}` "
                    f"[`{gap.actionability}`] "
                    f"(precise_non_mock_targets={gap.precise_non_mock_target_count}, "
                    f"targets={gap.unique_target_count}, pass={gap.pass_count}, reports={gap.report_count}) "
                    f"- {gap.recommendation}"
                )
        return "\n".join(lines).rstrip() + "\n"


def summarize_benchmark_baselines(
    report_paths: Iterable[str | Path],
    *,
    fallback_base_url: str | None = None,
    min_distinct_targets: int = 2,
) -> BenchmarkBaselineSummary:
    evidences: list[BenchmarkReportEvidence] = []
    warnings: list[str] = []
    for raw_path in report_paths:
        try:
            evidence = load_benchmark_report(
                raw_path,
                fallback_base_url=fallback_base_url,
            )
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"Failed to load `{raw_path}`: {exc}")
            continue
        evidences.append(evidence)
        if evidence.override_target_key is None:
            warnings.append(
                f"`{evidence.report_path}` is missing a precise target key; target diversity may be undercounted."
            )

    grouped: dict[tuple[str, str], list[BenchmarkReportEvidence]] = {}
    for evidence in evidences:
        group_key = (
            _runtime_profile_bucket(evidence),
            evidence.capability_tier or "unknown_capability_tier",
        )
        grouped.setdefault(group_key, []).append(evidence)

    group_evidence_map: dict[tuple[str, str], tuple[BenchmarkReportEvidence, ...]] = {}
    groups: list[BenchmarkBaselineGroup] = []
    for (runtime_profile, capability_tier), group_evidences in grouped.items():
        groups.append(
            _build_group_summary(
                runtime_profile=runtime_profile,
                capability_tier=capability_tier,
                evidences=group_evidences,
            )
        )
        group_evidence_map[(runtime_profile, capability_tier)] = tuple(group_evidences)
    groups.sort(
        key=lambda group: (
            group.runtime_profile,
            group.capability_tier,
            -group.pass_count,
            -group.report_count,
        )
    )
    refreshed_provider_model_identities = _refreshed_provider_model_identities(tuple(evidences))

    coverage_gaps: list[BenchmarkCoverageGap] = []
    for group in groups:
        actionability, recommendation = _classify_coverage_gap(
            group=group,
            evidences=group_evidence_map[(group.runtime_profile, group.capability_tier)],
            refreshed_provider_model_identities=refreshed_provider_model_identities,
        )
        if group.precise_non_mock_target_count < max(1, int(min_distinct_targets)):
            coverage_gaps.append(
                BenchmarkCoverageGap(
                    runtime_profile=group.runtime_profile,
                    capability_tier=group.capability_tier,
                    unique_target_count=group.unique_target_count,
                    precise_non_mock_target_count=group.precise_non_mock_target_count,
                    pass_count=group.pass_count,
                    report_count=group.report_count,
                    reason="need_more_distinct_targets",
                    actionability=actionability,
                    recommendation=recommendation,
                )
            )
        elif group.pass_count == 0:
            coverage_gaps.append(
                BenchmarkCoverageGap(
                    runtime_profile=group.runtime_profile,
                    capability_tier=group.capability_tier,
                    unique_target_count=group.unique_target_count,
                    precise_non_mock_target_count=group.precise_non_mock_target_count,
                    pass_count=group.pass_count,
                    report_count=group.report_count,
                    reason="no_pass_report",
                    actionability=actionability,
                    recommendation=recommendation,
                )
            )
    coverage_gaps.sort(key=_coverage_gap_sort_key)
    real_benchmark_priorities = tuple(
        gap for gap in coverage_gaps if _is_real_benchmark_priority(gap)
    )
    metadata_refresh_only_gaps = tuple(
        gap for gap in coverage_gaps if gap.actionability == "refresh_legacy_metadata"
    )
    ignored_coverage_gaps = tuple(
        gap
        for gap in coverage_gaps
        if gap.actionability
        in {
            "ignore_mock_only",
            "ignore_heuristic_covered",
            "ignore_superseded_legacy",
        }
    )
    return BenchmarkBaselineSummary(
        evidences=tuple(evidences),
        groups=tuple(groups),
        coverage_gaps=tuple(coverage_gaps),
        real_benchmark_priorities=real_benchmark_priorities,
        metadata_refresh_only_gaps=metadata_refresh_only_gaps,
        ignored_coverage_gaps=ignored_coverage_gaps,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _build_group_summary(
    *,
    runtime_profile: str,
    capability_tier: str,
    evidences: list[BenchmarkReportEvidence],
) -> BenchmarkBaselineGroup:
    status_counts = {"pass": 0, "needs_review": 0, "reject": 0}
    targets: set[str] = set()
    precise_non_mock_targets: set[str] = set()
    mock_targets: set[str] = set()
    models: set[str] = set()
    benchmark_names: set[str] = set()
    fastest_pass_report: str | None = None
    fastest_pass_duration_seconds: float | None = None

    for evidence in evidences:
        normalized_status = str(evidence.quality_gate_status or "").strip().lower()
        if normalized_status in status_counts:
            status_counts[normalized_status] += 1
        target_identity = _target_identity(evidence)
        targets.add(target_identity)
        if _is_mock_evidence(evidence):
            mock_targets.add(target_identity)
        elif evidence.override_target_key:
            precise_non_mock_targets.add(evidence.override_target_key)
        if evidence.model_name:
            models.add(evidence.model_name)
        if evidence.benchmark_name:
            benchmark_names.add(evidence.benchmark_name)
        duration_seconds = _duration_seconds_from_report(evidence)
        if normalized_status == "pass" and duration_seconds is not None:
            if (
                fastest_pass_duration_seconds is None
                or duration_seconds < fastest_pass_duration_seconds
            ):
                fastest_pass_duration_seconds = duration_seconds
                fastest_pass_report = evidence.benchmark_name or Path(evidence.report_path).name

    return BenchmarkBaselineGroup(
        runtime_profile=runtime_profile,
        capability_tier=capability_tier,
        report_count=len(evidences),
        pass_count=status_counts["pass"],
        needs_review_count=status_counts["needs_review"],
        reject_count=status_counts["reject"],
        unique_target_count=len(targets),
        precise_non_mock_target_count=len(precise_non_mock_targets),
        mock_target_count=len(mock_targets),
        unique_model_count=len(models),
        fastest_pass_report=fastest_pass_report,
        fastest_pass_duration_seconds=fastest_pass_duration_seconds,
        targets=tuple(sorted(targets)),
        benchmark_names=tuple(sorted(benchmark_names)),
    )


def _runtime_profile_bucket(evidence: BenchmarkReportEvidence) -> str:
    return (
        evidence.candidate_runtime_profile
        or evidence.runtime_profile
        or evidence.inferable_runtime_profile
        or "unknown_runtime_profile"
    )


def _target_identity(evidence: BenchmarkReportEvidence) -> str:
    if evidence.override_target_key:
        return evidence.override_target_key
    provider_name = evidence.provider_name or "unknown-provider"
    model_name = evidence.model_name or "unknown-model"
    return f"{provider_name}:{model_name}"


def _duration_seconds_from_report(evidence: BenchmarkReportEvidence) -> float | None:
    return evidence.duration_seconds


def _classify_coverage_gap(
    *,
    group: BenchmarkBaselineGroup,
    evidences: tuple[BenchmarkReportEvidence, ...],
    refreshed_provider_model_identities: frozenset[str],
) -> tuple[str, str]:
    if evidences and all(_is_mock_evidence(evidence) for evidence in evidences):
        return (
            "ignore_mock_only",
            "mock-only coverage does not justify more real-token benchmark spend",
        )

    precise_non_mock_targets = {
        evidence.override_target_key
        for evidence in evidences
        if evidence.override_target_key
        and not _is_mock_evidence(evidence)
    }
    has_runtime_metadata = any(_has_usable_runtime_metadata(evidence) for evidence in evidences)
    if not precise_non_mock_targets or not has_runtime_metadata:
        if _is_superseded_legacy_group(
            evidences=evidences,
            refreshed_provider_model_identities=refreshed_provider_model_identities,
        ):
            return (
                "ignore_superseded_legacy",
                "legacy-only evidence in this bucket is already superseded by refreshed target-qualified reports elsewhere, so rerunning these historical artifacts would not currently change runtime-profile decisions",
            )
        return (
            "refresh_legacy_metadata",
            "rerun this target with current benchmark metadata before adding more samples",
        )

    if _is_generic_heuristic_covered_group(
        runtime_profile=group.runtime_profile,
        evidences=evidences,
    ):
        return (
            "ignore_heuristic_covered",
            "precise pass evidence in this bucket is already covered by generic heuristics, so more real-token samples here would not currently change runtime-profile decisions",
        )

    if group.pass_count == 0:
        return (
            "verify_before_expand",
            "get at least one precise pass report before treating this bucket as a baseline candidate",
        )

    if group.unique_target_count > len(precise_non_mock_targets):
        return (
            "benchmark_distinct_target",
            "a second precise non-mock target in this bucket could change runtime-profile decisions; mock or imprecise targets here do not close that gap",
        )

    return (
        "benchmark_distinct_target",
        "a second precise non-mock target in this bucket could change runtime-profile decisions",
    )


def _has_usable_runtime_metadata(evidence: BenchmarkReportEvidence) -> bool:
    return any(
        [
            evidence.runtime_profile is not None,
            evidence.candidate_runtime_profile is not None,
            evidence.inferable_runtime_profile is not None,
            evidence.api_mode is not None,
            evidence.max_requests_per_minute is not None,
            evidence.detected_context_window is not None,
            evidence.structured_output_strength is not None,
            evidence.reasoning_mode is not None,
            bool(evidence.runtime_setting_sources),
        ]
    )


def _is_mock_evidence(evidence: BenchmarkReportEvidence) -> bool:
    return (evidence.provider_name or "").strip().lower() == "mock"


def _provider_model_identity(evidence: BenchmarkReportEvidence) -> str | None:
    provider_name = str(evidence.provider_name or "").strip().lower()
    model_name = str(evidence.model_name or "").strip().lower()
    if not provider_name or not model_name:
        return None
    return f"{provider_name}:{model_name}"


def _refreshed_provider_model_identities(
    evidences: tuple[BenchmarkReportEvidence, ...],
) -> frozenset[str]:
    identities: set[str] = set()
    for evidence in evidences:
        identity = _provider_model_identity(evidence)
        if identity is None:
            continue
        if not evidence.override_target_key:
            continue
        if not _has_usable_runtime_metadata(evidence):
            continue
        identities.add(identity)
    return frozenset(identities)


def _is_superseded_legacy_group(
    *,
    evidences: tuple[BenchmarkReportEvidence, ...],
    refreshed_provider_model_identities: frozenset[str],
) -> bool:
    legacy_non_mock_identities = {
        identity
        for evidence in evidences
        if not _is_mock_evidence(evidence)
        for identity in [_provider_model_identity(evidence)]
        if identity is not None
    }
    if not legacy_non_mock_identities:
        return False
    return legacy_non_mock_identities.issubset(refreshed_provider_model_identities)


def _is_generic_heuristic_covered_group(
    *,
    runtime_profile: str,
    evidences: tuple[BenchmarkReportEvidence, ...],
) -> bool:
    precise_non_mock_pass_evidences = [
        evidence
        for evidence in evidences
        if evidence.override_target_key
        and not _is_mock_evidence(evidence)
        and (evidence.quality_gate_status or "").strip().lower() == "pass"
    ]
    if not precise_non_mock_pass_evidences:
        return False
    return all(
        (evidence.inferable_runtime_profile or "").strip().lower() == runtime_profile
        for evidence in precise_non_mock_pass_evidences
    )


def _is_real_benchmark_priority(gap: BenchmarkCoverageGap) -> bool:
    return gap.actionability in {"benchmark_distinct_target", "verify_before_expand"}


def _coverage_gap_priority(gap: BenchmarkCoverageGap) -> int:
    if _is_real_benchmark_priority(gap):
        return 0
    if gap.actionability == "refresh_legacy_metadata":
        return 1
    if gap.actionability in {
        "ignore_mock_only",
        "ignore_heuristic_covered",
        "ignore_superseded_legacy",
    }:
        return 2
    return 3


def _coverage_gap_sort_key(gap: BenchmarkCoverageGap) -> tuple[int, str, str]:
    return (
        _coverage_gap_priority(gap),
        gap.runtime_profile,
        gap.capability_tier,
    )
