from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from backend.core.translation.metrics import TranslationRunMetrics
from backend.domain.models import Book, Segment
from backend.storage.checkpoint_store import ChunkCheckpointSnapshot

from .book_term_memory import BookTermMemorySnapshot, TermTranslationCandidate

_LATIN_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z'_-]{2,}\b")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True, frozen=True)
class TermConflictIssue:
    source: str
    preferred_target: str | None
    chapter_ids: tuple[int, ...]
    candidates: tuple[TermTranslationCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "preferred_target": self.preferred_target,
            "chapter_ids": list(self.chapter_ids),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(slots=True, frozen=True)
class ResidueIssue:
    segment_id: int
    chapter_id: int
    source_excerpt: str
    translated_excerpt: str
    residue_tokens: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "chapter_id": self.chapter_id,
            "source_excerpt": self.source_excerpt,
            "translated_excerpt": self.translated_excerpt,
            "residue_tokens": list(self.residue_tokens),
        }


@dataclass(slots=True, frozen=True)
class ConsistencyReport:
    book_id: int
    book_title: str
    generated_at: str
    runtime_profile: str
    tracked_terms: int
    term_conflicts: tuple[TermConflictIssue, ...]
    untranslated_residue_segments: tuple[ResidueIssue, ...]
    fallback_reason_counts: dict[str, int]
    failure_reason_counts: dict[str, int]
    retry_attempt_counts: dict[str, int]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": 1,
            "report_type": "consistency_report",
            "book_id": self.book_id,
            "book_title": self.book_title,
            "generated_at": self.generated_at,
            "runtime_profile": self.runtime_profile,
            "summary": {
                "tracked_terms": self.tracked_terms,
                "term_conflict_count": len(self.term_conflicts),
                "untranslated_residue_count": len(self.untranslated_residue_segments),
                "fallback_count": int(self.metrics.get("fallback_count") or 0),
                "chunk_failed_count": int(self.metrics.get("chunk_failed") or 0),
            },
            "term_conflicts": [issue.to_dict() for issue in self.term_conflicts],
            "untranslated_residue_segments": [
                issue.to_dict() for issue in self.untranslated_residue_segments
            ],
            "fallback_reason_counts": dict(self.fallback_reason_counts),
            "failure_reason_counts": dict(self.failure_reason_counts),
            "retry_attempt_counts": dict(self.retry_attempt_counts),
            "metrics": dict(self.metrics),
        }

    def to_markdown(self) -> str:
        payload = self.to_dict()
        summary = payload["summary"]
        lines = [
            "# Consistency Report",
            "",
            f"- Book: `{self.book_title}` (#{self.book_id})",
            f"- Generated at: `{self.generated_at}`",
            f"- Runtime profile: `{self.runtime_profile}`",
            f"- Tracked terms: `{summary['tracked_terms']}`",
            f"- Term conflicts: `{summary['term_conflict_count']}`",
            f"- Untranslated residue segments: `{summary['untranslated_residue_count']}`",
            f"- Chunk fallbacks: `{summary['fallback_count']}`",
            f"- Failed chunks: `{summary['chunk_failed_count']}`",
            "",
            "## Term Conflicts",
        ]
        if not self.term_conflicts:
            lines.extend(["No high-confidence term conflicts detected.", ""])
        else:
            for issue in self.term_conflicts:
                candidates = ", ".join(
                    f"`{candidate.text}` x{candidate.count}"
                    for candidate in issue.candidates
                )
                lines.append(
                    f"- `{issue.source}` -> preferred `{issue.preferred_target or '-'}`; "
                    f"chapters {', '.join(str(chapter_id) for chapter_id in issue.chapter_ids)}; "
                    f"candidates: {candidates}"
                )
            lines.append("")
        lines.append("## Untranslated Residue")
        if not self.untranslated_residue_segments:
            lines.extend(["No obvious English residue detected.", ""])
        else:
            for issue in self.untranslated_residue_segments:
                residue = ", ".join(f"`{token}`" for token in issue.residue_tokens)
                lines.append(
                    f"- Segment `{issue.segment_id}` / chapter `{issue.chapter_id}` still contains {residue}: "
                    f"`{issue.translated_excerpt}`"
                )
            lines.append("")
        lines.append("## Chunk Diagnostics")
        lines.append(
            f"- fallback reasons: `{json.dumps(self.fallback_reason_counts, ensure_ascii=False, sort_keys=True)}`"
        )
        lines.append(
            f"- failure reasons: `{json.dumps(self.failure_reason_counts, ensure_ascii=False, sort_keys=True)}`"
        )
        lines.append(
            f"- retry attempts: `{json.dumps(self.retry_attempt_counts, ensure_ascii=False, sort_keys=True)}`"
        )
        lines.append("")
        return "\n".join(lines)


class ConsistencyReportGenerator:
    def generate(
        self,
        *,
        book: Book,
        segments: Iterable[Segment],
        term_memory_snapshot: BookTermMemorySnapshot | None,
        runtime_profile: str,
        metrics: TranslationRunMetrics | None = None,
        chunk_snapshots: tuple[ChunkCheckpointSnapshot, ...] = (),
    ) -> ConsistencyReport:
        materialized_segments = tuple(segments)
        term_conflicts = self._term_conflicts(term_memory_snapshot)
        residue_issues = self._residue_issues(materialized_segments)
        fallback_reason_counts = Counter(
            snapshot.fallback_reason_code
            for snapshot in chunk_snapshots
            if snapshot.fallback_reason_code
        )
        failure_reason_counts = Counter(
            snapshot.failure_reason_code
            for snapshot in chunk_snapshots
            if snapshot.failure_reason_code
        )
        retry_attempt_counts = Counter(
            str(snapshot.attempt_count)
            for snapshot in chunk_snapshots
            if snapshot.attempt_count > 0
        )
        metrics_payload = metrics.to_dict() if metrics is not None else {}
        return ConsistencyReport(
            book_id=book.id,
            book_title=book.title,
            generated_at=_now_iso(),
            runtime_profile=runtime_profile,
            tracked_terms=len(term_memory_snapshot.entries) if term_memory_snapshot is not None else 0,
            term_conflicts=term_conflicts,
            untranslated_residue_segments=residue_issues,
            fallback_reason_counts=dict(sorted(fallback_reason_counts.items())),
            failure_reason_counts=dict(sorted(failure_reason_counts.items())),
            retry_attempt_counts=dict(sorted(retry_attempt_counts.items())),
            metrics=metrics_payload,
        )

    @staticmethod
    def _term_conflicts(
        term_memory_snapshot: BookTermMemorySnapshot | None,
    ) -> tuple[TermConflictIssue, ...]:
        if term_memory_snapshot is None:
            return ()
        conflicts: list[TermConflictIssue] = []
        for entry in term_memory_snapshot.entries:
            meaningful_candidates = tuple(
                candidate
                for candidate in entry.target_candidates
                if candidate.count >= 2 or len(candidate.text) <= 4
            )
            if len(meaningful_candidates) < 2:
                continue
            if meaningful_candidates[0].count == meaningful_candidates[1].count:
                preferred_target = None
            else:
                preferred_target = entry.preferred_target
            conflicts.append(
                TermConflictIssue(
                    source=entry.source,
                    preferred_target=preferred_target,
                    chapter_ids=entry.chapter_ids,
                    candidates=meaningful_candidates,
                )
            )
        return tuple(conflicts)

    @staticmethod
    def _residue_issues(segments: tuple[Segment, ...]) -> tuple[ResidueIssue, ...]:
        issues: list[ResidueIssue] = []
        for segment in segments:
            translated_text = str(segment.translated_text or "").strip()
            if not translated_text:
                continue
            residue_tokens = tuple(
                sorted(
                    {
                        token
                        for token in _LATIN_TOKEN_RE.findall(translated_text)
                        if len(token) >= 3
                    }
                )
            )
            if not residue_tokens:
                continue
            issues.append(
                ResidueIssue(
                    segment_id=segment.id,
                    chapter_id=segment.chapter_id,
                    source_excerpt=ConsistencyReportGenerator._excerpt(segment.source_text),
                    translated_excerpt=ConsistencyReportGenerator._excerpt(translated_text),
                    residue_tokens=residue_tokens,
                )
            )
        return tuple(issues)

    @staticmethod
    def _excerpt(text: str, *, limit: int = 120) -> str:
        normalized = " ".join(str(text or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 1)].rstrip() + "…"
