from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter

from backend.domain.models import Segment

from .chunk_planner import PlannedChunk
from .runtime_settings import TranslationRuntimeSettings


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class TranslationRunMetrics:
    runtime_settings: TranslationRuntimeSettings
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    export_success: bool | None = None
    chunk_total: int = 0
    chunk_completed: int = 0
    chunk_failed: int = 0
    fallback_count: int = 0
    skipped_segments: int = 0
    total_chunk_segments: int = 0
    total_chunk_source_chars: int = 0
    total_chunk_estimated_tokens: int = 0
    failure_messages: list[str] = field(default_factory=list)
    _started_chunk_ids: set[str] = field(default_factory=set, repr=False)
    _completed_chunk_ids: set[str] = field(default_factory=set, repr=False)
    _failed_chunk_ids: set[str] = field(default_factory=set, repr=False)
    _started_counter: float = field(default_factory=perf_counter, repr=False)
    _finished_counter: float | None = field(default=None, repr=False)

    def note_chunk_started(self, chunk: PlannedChunk) -> None:
        if chunk.chunk_id in self._started_chunk_ids:
            return
        self._started_chunk_ids.add(chunk.chunk_id)
        self.chunk_total += 1
        self.total_chunk_segments += len(chunk.segments)
        self.total_chunk_source_chars += sum(len(segment.source_text) for segment in chunk.segments)
        self.total_chunk_estimated_tokens += int(chunk.estimated_tokens)

    def note_chunk_completed(self, chunk: PlannedChunk) -> None:
        if chunk.chunk_id in self._completed_chunk_ids:
            return
        self._completed_chunk_ids.add(chunk.chunk_id)
        self.chunk_completed += 1

    def note_chunk_failed(self, chunk: PlannedChunk, error_summary: str | None) -> None:
        if chunk.chunk_id in self._failed_chunk_ids:
            return
        self._failed_chunk_ids.add(chunk.chunk_id)
        self.chunk_failed += 1
        if error_summary:
            self.failure_messages.append(str(error_summary))

    def note_chunk_fallback(self, chunk: PlannedChunk, error_summary: str | None) -> None:
        self.note_chunk_started(chunk)
        self.fallback_count += 1
        if error_summary:
            self.failure_messages.append(str(error_summary))

    def note_segment_skipped(self, segment: Segment) -> None:
        del segment
        self.skipped_segments += 1

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return max(0.0, perf_counter() - self._started_counter)
        finished_counter = self._finished_counter or self._started_counter
        return max(0.0, finished_counter - self._started_counter)

    def mark_finished(self) -> None:
        if self.finished_at is not None:
            return
        self.finished_at = _now_iso()
        self._finished_counter = perf_counter()

    @property
    def average_segments_per_chunk(self) -> float:
        if self.chunk_total <= 0:
            return 0.0
        return self.total_chunk_segments / self.chunk_total

    @property
    def average_source_chars_per_chunk(self) -> float:
        if self.chunk_total <= 0:
            return 0.0
        return self.total_chunk_source_chars / self.chunk_total

    @property
    def average_estimated_tokens_per_chunk(self) -> float:
        if self.chunk_total <= 0:
            return 0.0
        return self.total_chunk_estimated_tokens / self.chunk_total

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 6),
            "export_success": self.export_success,
            "chunk_total": self.chunk_total,
            "chunk_completed": self.chunk_completed,
            "chunk_failed": self.chunk_failed,
            "fallback_count": self.fallback_count,
            "skipped_segments": self.skipped_segments,
            "total_chunk_segments": self.total_chunk_segments,
            "total_chunk_source_chars": self.total_chunk_source_chars,
            "total_chunk_estimated_tokens": self.total_chunk_estimated_tokens,
            "average_segments_per_chunk": round(self.average_segments_per_chunk, 6),
            "average_source_chars_per_chunk": round(self.average_source_chars_per_chunk, 6),
            "average_estimated_tokens_per_chunk": round(self.average_estimated_tokens_per_chunk, 6),
            "failure_messages": list(self.failure_messages),
            "runtime_settings": self.runtime_settings.to_dict(),
        }
