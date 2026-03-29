from __future__ import annotations

from dataclasses import dataclass

from backend.core.providers.base import ChunkSegment
from backend.domain.enums import SegmentType
from backend.domain.models import Chapter, Segment

from .runtime_settings import TranslationRuntimeSettings
from .token_budget import TokenBudgetEstimator


@dataclass(slots=True, frozen=True)
class PlannedChunk:
    chunk_id: str
    chapter_id: int
    chapter_order: int
    chapter_title: str
    sequence_no: int
    start_index: int
    end_index: int
    estimated_tokens: int
    segments: tuple[ChunkSegment, ...]

    @property
    def segment_ids(self) -> tuple[int, ...]:
        return tuple(segment.segment_id for segment in self.segments)


class TranslationChunkPlanner:
    _DIALOGUE_SLACK_RATIO = 1.12

    def __init__(
        self,
        *,
        estimator: TokenBudgetEstimator,
        settings: TranslationRuntimeSettings,
    ) -> None:
        self.estimator = estimator
        self.settings = settings.normalized()

    def plan_chapter(
        self,
        *,
        chapter: Chapter,
        segments: tuple[Segment, ...],
    ) -> tuple[PlannedChunk, ...]:
        if not segments:
            return ()

        chunks: list[PlannedChunk] = []
        current_segments: list[ChunkSegment] = []
        current_start = 0
        current_tokens = 0
        sequence_no = 0
        target_budget = self.estimator.target_chunk_budget()

        for index, segment in enumerate(segments):
            candidate = ChunkSegment(
                segment_id=segment.id,
                segment_order=segment.order,
                segment_type=segment.segment_type,
                source_text=segment.source_text,
                extra=segment.extra,
            )
            segment_tokens = self.estimator.estimate_text_tokens(candidate.source_text)
            if not current_segments:
                current_start = index
                current_segments.append(candidate)
                current_tokens = segment_tokens
                continue

            if self._should_flush_before_segment(
                current_segments=current_segments,
                candidate=candidate,
                current_tokens=current_tokens,
                target_budget=target_budget,
            ):
                chunks.append(
                    self._build_chunk(
                        chapter=chapter,
                        sequence_no=sequence_no,
                        start_index=current_start,
                        end_index=index,
                        estimated_tokens=current_tokens,
                        segments=tuple(current_segments),
                    )
                )
                sequence_no += 1
                current_segments = [candidate]
                current_start = index
                current_tokens = segment_tokens
                continue

            would_exceed = current_tokens + segment_tokens > target_budget
            if would_exceed and not self._can_borrow_dialogue_slack(
                current_segments=current_segments,
                candidate=candidate,
                current_tokens=current_tokens,
                segment_tokens=segment_tokens,
                target_budget=target_budget,
            ):
                chunks.append(
                    self._build_chunk(
                        chapter=chapter,
                        sequence_no=sequence_no,
                        start_index=current_start,
                        end_index=index,
                        estimated_tokens=current_tokens,
                        segments=tuple(current_segments),
                    )
                )
                sequence_no += 1
                current_segments = [candidate]
                current_start = index
                current_tokens = segment_tokens
                continue

            current_segments.append(candidate)
            current_tokens += segment_tokens

        if current_segments:
            chunks.append(
                self._build_chunk(
                    chapter=chapter,
                    sequence_no=sequence_no,
                    start_index=current_start,
                    end_index=len(segments),
                    estimated_tokens=current_tokens,
                    segments=tuple(current_segments),
                )
            )

        return tuple(chunks)

    @staticmethod
    def _build_chunk(
        *,
        chapter: Chapter,
        sequence_no: int,
        start_index: int,
        end_index: int,
        estimated_tokens: int,
        segments: tuple[ChunkSegment, ...],
    ) -> PlannedChunk:
        return PlannedChunk(
            chunk_id=f"chapter-{chapter.id}-chunk-{sequence_no}",
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            chapter_title=chapter.title,
            sequence_no=sequence_no,
            start_index=start_index,
            end_index=end_index,
            estimated_tokens=estimated_tokens,
            segments=segments,
        )

    def _should_flush_before_segment(
        self,
        *,
        current_segments: list[ChunkSegment],
        candidate: ChunkSegment,
        current_tokens: int,
        target_budget: int,
    ) -> bool:
        if not current_segments:
            return False
        current_ratio = current_tokens / max(1, target_budget)
        previous = current_segments[-1]
        if current_ratio < 0.7:
            return False
        if candidate.segment_type is SegmentType.TITLE:
            return True
        if (
            previous.segment_type is SegmentType.PARAGRAPH
            and candidate.segment_type is SegmentType.FOOTNOTE
        ):
            return True
        return False

    def _can_borrow_dialogue_slack(
        self,
        *,
        current_segments: list[ChunkSegment],
        candidate: ChunkSegment,
        current_tokens: int,
        segment_tokens: int,
        target_budget: int,
    ) -> bool:
        if not current_segments:
            return False
        previous = current_segments[-1]
        if not self._is_dialogue_like(previous.source_text):
            return False
        if not self._is_dialogue_like(candidate.source_text):
            return False
        expanded_budget = max(target_budget, int(target_budget * self._DIALOGUE_SLACK_RATIO))
        return current_tokens + segment_tokens <= expanded_budget

    @staticmethod
    def _is_dialogue_like(text: str) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return False
        return (
            normalized.startswith(("“", "\"", "‘", "'"))
            or normalized.count("“") >= 2
            or normalized.count("\"") >= 2
        )
