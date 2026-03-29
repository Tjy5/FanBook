from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable

from backend.core.providers.base import (
    ChunkContext,
    ChunkTranslationItem,
    ChunkTranslationRequest,
    ChunkTranslationResponse,
    GlossaryHint,
    SegmentContext,
    TranslationMemoryEntry,
    TranslationProvider,
    TranslationRequest,
)
from backend.core.quality.book_glossary import BookGlossarySnapshot
from backend.core.quality.book_term_memory import BookTermMemorySnapshot
from backend.core.quality.content_filter import ContentFilter
from backend.core.translation.error_codes import classify_chunk_issue
from backend.domain.enums import SegmentStatus, SegmentType
from backend.domain.models import Book, Chapter, Segment

from .chunk_planner import PlannedChunk, TranslationChunkPlanner
from .context_manager import ChapterContextManager
from .retry_policy import RetryPolicy, is_retryable_translation_error
from .runtime_settings import TranslationRuntimeSettings
from .token_budget import TokenBudgetEstimator


@dataclass(slots=True, frozen=True)
class ChapterTranslationBatch:
    chapter: Chapter
    segments: tuple[Segment, ...]


@dataclass(slots=True, frozen=True)
class TranslatedSegmentResult:
    segment_id: int
    translated_text: str
    provider_name: str
    model_name: str


@dataclass(slots=True, frozen=True)
class TranslatedChunkResult:
    results: tuple[TranslatedSegmentResult, ...]
    attempt_count: int = 1
    used_fallback: bool = False


@dataclass(slots=True)
class _ChapterExecutionState:
    batch: ChapterTranslationBatch
    chunks: tuple[PlannedChunk, ...]
    next_index: int = 0
    active_count: int = 0


@dataclass(slots=True)
class _GlobalRateController:
    enabled: bool
    max_limit: int
    current_limit: int
    min_limit: int
    successes_before_scale_up: int = 3
    _healthy_success_streak: int = 0

    @classmethod
    def from_settings(cls, settings: TranslationRuntimeSettings) -> "_GlobalRateController":
        normalized = settings.normalized()
        initial_limit = (
            normalized.dynamic_rate_control_initial_global_concurrency
            if normalized.dynamic_rate_control_enabled
            else normalized.global_max_concurrency
        )
        return cls(
            enabled=normalized.dynamic_rate_control_enabled,
            max_limit=normalized.global_max_concurrency,
            current_limit=max(1, int(initial_limit)),
            min_limit=max(1, int(normalized.dynamic_rate_control_min_global_concurrency)),
            successes_before_scale_up=max(
                1,
                int(normalized.dynamic_rate_control_scale_up_success_streak),
            ),
        )

    def note_success(self) -> None:
        if not self.enabled:
            return
        self._healthy_success_streak += 1
        if self._healthy_success_streak >= self.successes_before_scale_up:
            self.current_limit = min(self.max_limit, self.current_limit + 1)
            self._healthy_success_streak = 0

    def note_degraded_success(self) -> None:
        if not self.enabled:
            return
        self._healthy_success_streak = 0
        self.current_limit = max(self.min_limit, self.current_limit - 1)

    def note_failure(self, error_summary: str | None) -> None:
        if not self.enabled:
            return
        self._healthy_success_streak = 0
        error_code = classify_chunk_issue(error_summary)
        if error_code in {"rate_limited", "timeout"}:
            reduced_limit = max(self.min_limit, self.current_limit // 2)
        else:
            reduced_limit = max(self.min_limit, self.current_limit - 1)
        self.current_limit = max(self.min_limit, reduced_limit)


class TranslationOrchestrator:
    def __init__(
        self,
        *,
        context_manager: ChapterContextManager | None = None,
        retry_policy: RetryPolicy | None = None,
        content_filter: ContentFilter | None = None,
        target_language: str = "zh",
    ) -> None:
        self.context_manager = context_manager or ChapterContextManager()
        self.retry_policy = retry_policy or RetryPolicy(
            retryable_error_checker=is_retryable_translation_error,
            base_delay_seconds=1.0,
            max_delay_seconds=8.0,
            jitter_ratio=0.2,
        )
        self.content_filter = content_filter or ContentFilter()
        self.target_language = target_language

    def translate_book(
        self,
        *,
        book: Book,
        chapters: tuple[ChapterTranslationBatch, ...],
        provider: TranslationProvider,
        settings: TranslationRuntimeSettings | None = None,
        glossary_snapshot: BookGlossarySnapshot | None = None,
        term_memory_snapshot: BookTermMemorySnapshot | None = None,
        on_chunk_status: Callable[[PlannedChunk, str, int, str | None], None] | None = None,
        on_chunk_completed: Callable[[PlannedChunk, tuple[TranslatedSegmentResult, ...]], None] | None = None,
        on_chunk_fallback: Callable[[PlannedChunk, str | None], None] | None = None,
        on_segment_skipped: Callable[[Segment], None] | None = None,
    ) -> list[TranslatedSegmentResult]:
        runtime_settings = (settings or TranslationRuntimeSettings()).normalized()
        estimator = TokenBudgetEstimator(
            settings=runtime_settings,
            model_name=provider.model_name,
        )
        planner = TranslationChunkPlanner(estimator=estimator, settings=runtime_settings)
        retry_policy = self.retry_policy.clone_with(
            max_attempts=runtime_settings.retry_max_attempts,
        )
        rate_controller = _GlobalRateController.from_settings(runtime_settings)
        segment_by_id = {
            segment.id: segment
            for batch in chapters
            for segment in batch.segments
        }
        leader_by_duplicate_key: dict[str, int] = {}
        duplicate_segments_by_canonical_id: dict[int, list[Segment]] = {}

        chapter_states: list[_ChapterExecutionState] = []
        for batch in chapters:
            pending_segments: list[Segment] = []
            for segment in batch.segments:
                if self._is_already_done(segment):
                    continue
                if not self.content_filter.should_translate_segment(segment):
                    if on_segment_skipped is not None:
                        on_segment_skipped(segment)
                    continue
                pending_segments.append(segment)
            deduped_segments = self._dedupe_pending_segments(
                pending_segments,
                settings=runtime_settings,
                leader_by_duplicate_key=leader_by_duplicate_key,
                duplicate_segments_by_canonical_id=duplicate_segments_by_canonical_id,
            )
            planned_chunks = planner.plan_chapter(
                chapter=batch.chapter,
                segments=deduped_segments,
            )
            if planned_chunks:
                chapter_states.append(_ChapterExecutionState(batch=batch, chunks=planned_chunks))

        if not chapter_states:
            return []

        results: list[TranslatedSegmentResult] = []
        active_futures: dict[Future[TranslatedChunkResult], tuple[_ChapterExecutionState, PlannedChunk]] = {}
        executor_workers = min(
            runtime_settings.global_max_concurrency,
            max(1, sum(len(state.chunks) for state in chapter_states)),
        )

        with ThreadPoolExecutor(max_workers=executor_workers) as executor:
            self._submit_available_chunks(
                executor=executor,
                active_futures=active_futures,
                chapter_states=chapter_states,
                book=book,
                provider=provider,
                estimator=estimator,
                retry_policy=retry_policy,
                runtime_settings=runtime_settings,
                rate_controller=rate_controller,
                glossary_snapshot=glossary_snapshot,
                term_memory_snapshot=term_memory_snapshot,
                on_chunk_status=on_chunk_status,
                on_chunk_fallback=on_chunk_fallback,
            )

            while active_futures:
                done, _ = wait(tuple(active_futures), return_when=FIRST_COMPLETED)
                for future in done:
                    state, chunk = active_futures.pop(future)
                    state.active_count = max(0, state.active_count - 1)
                    try:
                        chunk_result = future.result()
                    except Exception as exc:
                        rate_controller.note_failure(str(exc))
                        if on_chunk_status is not None:
                            on_chunk_status(chunk, "failed", retry_policy.max_attempts, str(exc))
                        raise

                    expanded_results = self._expand_duplicate_results(
                        chunk_result.results,
                        duplicate_segments_by_canonical_id=duplicate_segments_by_canonical_id,
                    )
                    self._apply_chunk_results(segment_by_id, expanded_results)
                    results.extend(expanded_results)
                    if on_chunk_completed is not None:
                        on_chunk_completed(chunk, expanded_results)
                    if on_chunk_status is not None:
                        on_chunk_status(chunk, "completed", chunk_result.attempt_count, None)
                    if chunk_result.used_fallback or chunk_result.attempt_count > 1:
                        rate_controller.note_degraded_success()
                    else:
                        rate_controller.note_success()

                self._submit_available_chunks(
                    executor=executor,
                    active_futures=active_futures,
                    chapter_states=chapter_states,
                    book=book,
                    provider=provider,
                    estimator=estimator,
                    retry_policy=retry_policy,
                    runtime_settings=runtime_settings,
                    rate_controller=rate_controller,
                    glossary_snapshot=glossary_snapshot,
                    term_memory_snapshot=term_memory_snapshot,
                    on_chunk_status=on_chunk_status,
                    on_chunk_fallback=on_chunk_fallback,
                )

        return results

    def should_translate(self, segment: Segment) -> bool:
        if segment.status is SegmentStatus.SKIPPED:
            return False
        if self._is_already_done(segment):
            return False
        return self.content_filter.should_translate_segment(segment)

    @staticmethod
    def _is_already_done(segment: Segment) -> bool:
        return (
            segment.status is SegmentStatus.TRANSLATED
            and bool((segment.translated_text or "").strip())
        )

    def _submit_available_chunks(
        self,
        *,
        executor: ThreadPoolExecutor,
        active_futures: dict[Future[TranslatedChunkResult], tuple[_ChapterExecutionState, PlannedChunk]],
        chapter_states: list[_ChapterExecutionState],
        book: Book,
        provider: TranslationProvider,
        estimator: TokenBudgetEstimator,
        retry_policy: RetryPolicy,
        runtime_settings: TranslationRuntimeSettings,
        rate_controller: _GlobalRateController,
        glossary_snapshot: BookGlossarySnapshot | None,
        term_memory_snapshot: BookTermMemorySnapshot | None,
        on_chunk_status: Callable[[PlannedChunk, str, int, str | None], None] | None,
        on_chunk_fallback: Callable[[PlannedChunk, str | None], None] | None,
    ) -> None:
        while len(active_futures) < rate_controller.current_limit:
            submitted_any = False
            effective_per_chapter_limit = runtime_settings.effective_per_chapter_concurrency(
                active_chapter_count=self._active_chapter_count(chapter_states),
                global_limit=rate_controller.current_limit,
            )
            for state in chapter_states:
                if len(active_futures) >= rate_controller.current_limit:
                    break
                if state.active_count >= effective_per_chapter_limit:
                    continue
                if state.next_index >= len(state.chunks):
                    continue

                chunk = state.chunks[state.next_index]
                state.next_index += 1
                state.active_count += 1
                request = self._build_chunk_request(
                    book=book,
                    batch=state.batch,
                    chunk=chunk,
                    glossary_snapshot=glossary_snapshot,
                    term_memory_snapshot=term_memory_snapshot,
                    runtime_settings=runtime_settings,
                )
                future = executor.submit(
                    self._translate_chunk_with_fallback,
                    provider,
                    chunk,
                    request,
                    estimator,
                    retry_policy,
                    on_chunk_fallback,
                )
                active_futures[future] = (state, chunk)
                submitted_any = True
                if on_chunk_status is not None:
                    on_chunk_status(chunk, "running", 0, None)
            if not submitted_any:
                break

    def _build_chunk_request(
        self,
        *,
        book: Book,
        batch: ChapterTranslationBatch,
        chunk: PlannedChunk,
        glossary_snapshot: BookGlossarySnapshot | None,
        term_memory_snapshot: BookTermMemorySnapshot | None,
        runtime_settings: TranslationRuntimeSettings,
    ) -> ChunkTranslationRequest:
        chapter_segments = batch.segments
        index_by_id = {segment.id: index for index, segment in enumerate(chapter_segments)}
        first_index = index_by_id.get(chunk.segments[0].segment_id, 0)
        last_index = index_by_id.get(chunk.segments[-1].segment_id, first_index)
        window = self.context_manager.build_range(
            chapter_segments,
            start_index=first_index,
            end_index=last_index + 1,
            before_window=runtime_settings.context_segments_before,
            after_window=runtime_settings.context_segments_after,
            translated_lookup=None,
        )
        return ChunkTranslationRequest(
            source_language=book.source_language,
            target_language=self.target_language,
            book_title=book.title,
            context=ChunkContext(
                chapter_title=batch.chapter.title,
                chapter_order=batch.chapter.order,
                chunk_id=chunk.chunk_id,
                chunk_sequence=chunk.sequence_no,
                previous_source_texts=window.previous_source_texts,
                previous_translated_texts=window.previous_translated_texts,
                following_source_texts=window.following_source_texts,
                glossary_hints=self._build_glossary_hints(
                    glossary_snapshot,
                    term_memory_snapshot=term_memory_snapshot,
                    chapter_id=batch.chapter.id,
                ),
                translation_memory=self._build_translation_memory(
                    chapter_segments,
                    start_index=first_index,
                    limit=runtime_settings.translation_memory_size,
                ),
                chapter_summary=self._build_chapter_summary(
                    chapter_segments,
                    chapter_id=batch.chapter.id,
                    start_index=first_index,
                    term_memory_snapshot=term_memory_snapshot,
                ),
                narrative_mode=self._narrative_mode(chunk.segments),
            ),
            segments=chunk.segments,
            options={"max_output_tokens": runtime_settings.max_output_tokens},
        )

    @staticmethod
    def _build_glossary_hints(
        glossary_snapshot: BookGlossarySnapshot | None,
        *,
        term_memory_snapshot: BookTermMemorySnapshot | None,
        chapter_id: int,
    ) -> tuple[GlossaryHint, ...]:
        deduped: dict[str, GlossaryHint] = {}
        if glossary_snapshot is not None:
            for hint in glossary_snapshot.global_hints + glossary_snapshot.hints_for_chapter(chapter_id):
                deduped.setdefault(hint.source, hint)
        if term_memory_snapshot is not None:
            for hint in term_memory_snapshot.hints_for_chapter(chapter_id, limit=8):
                existing = deduped.get(hint.source)
                if existing is None:
                    deduped[hint.source] = hint
                    continue
                if existing.target is None and hint.target is not None:
                    deduped[hint.source] = hint
        return tuple(deduped.values())

    @staticmethod
    def _build_translation_memory(
        segments: tuple[Segment, ...],
        *,
        start_index: int,
        limit: int,
    ) -> tuple[TranslationMemoryEntry, ...]:
        if limit <= 0:
            return ()
        translated_segments = [
            segment
            for segment in segments[:start_index]
            if (segment.translated_text or "").strip()
        ]
        return tuple(
            TranslationMemoryEntry(
                source_text=segment.source_text,
                translated_text=segment.translated_text or "",
            )
            for segment in translated_segments[-limit:]
        )

    @staticmethod
    def _build_chapter_summary(
        segments: tuple[Segment, ...],
        *,
        chapter_id: int,
        start_index: int,
        term_memory_snapshot: BookTermMemorySnapshot | None,
    ) -> str | None:
        summary_parts: list[str] = []
        if term_memory_snapshot is not None:
            chapter_entries = term_memory_snapshot.entries_for_chapter(chapter_id, limit=4)
            if chapter_entries:
                summary_parts.append(
                    "Recurring names and settings: "
                    + ", ".join(
                        entry.source
                        if entry.preferred_target is None
                        else f"{entry.source} => {entry.preferred_target}"
                        for entry in chapter_entries
                    )
                )
        recent_translated = [
            segment.translated_text.strip()
            for segment in segments[max(0, start_index - 3):start_index]
            if (segment.translated_text or "").strip()
        ]
        if recent_translated:
            summary_parts.append(
                "Recent translated flow: "
                + " / ".join(
                    TranslationOrchestrator._summary_excerpt(text, limit=56)
                    for text in recent_translated[-2:]
                )
            )
        if not summary_parts:
            return None
        return "\n".join(summary_parts)

    @staticmethod
    def _summary_excerpt(text: str, *, limit: int) -> str:
        normalized = " ".join(str(text or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 1)].rstrip() + "…"

    @staticmethod
    def _narrative_mode(segments) -> str:
        dialogue_like = 0
        total = 0
        for segment in segments:
            total += 1
            normalized = str(segment.source_text or "").strip()
            if not normalized:
                continue
            if (
                normalized.startswith(("“", "\"", "‘", "'"))
                or normalized.count("“") >= 2
                or normalized.count("\"") >= 2
            ):
                dialogue_like += 1
        if total > 0 and dialogue_like * 2 >= total:
            return "dialogue_focus"
        return "narrative_focus"

    @staticmethod
    def _apply_chunk_results(
        segment_by_id: dict[int, Segment],
        chunk_results: tuple[TranslatedSegmentResult, ...],
    ) -> None:
        for result in chunk_results:
            segment = segment_by_id.get(result.segment_id)
            if segment is None:
                continue
            segment.translated_text = result.translated_text
            segment.status = SegmentStatus.TRANSLATED

    def _translate_chunk_with_fallback(
        self,
        provider: TranslationProvider,
        chunk: PlannedChunk | None,
        request: ChunkTranslationRequest,
        estimator: TokenBudgetEstimator,
        retry_policy: RetryPolicy,
        on_chunk_fallback: Callable[[PlannedChunk, str | None], None] | None = None,
    ) -> TranslatedChunkResult:
        used_fallback = False
        try:
            response, attempt_count = retry_policy.run_with_attempt_count(
                lambda: provider.translate_chunk(request)
            )
        except Exception as exc:
            used_fallback = True
            if chunk is not None and on_chunk_fallback is not None:
                on_chunk_fallback(chunk, str(exc))
            response = self._fallback_chunk_translation(
                provider=provider,
                request=request,
                estimator=estimator,
                retry_policy=retry_policy,
            )
            attempt_count = retry_policy.max_attempts
        return TranslatedChunkResult(
            results=tuple(
                TranslatedSegmentResult(
                    segment_id=item.segment_id,
                    translated_text=item.translated_text,
                    provider_name=response.provider_name,
                    model_name=response.model_name,
                )
                for item in response.items
            ),
            attempt_count=attempt_count,
            used_fallback=used_fallback,
        )

    def _fallback_chunk_translation(
        self,
        *,
        provider: TranslationProvider,
        request: ChunkTranslationRequest,
        estimator: TokenBudgetEstimator,
        retry_policy: RetryPolicy,
    ) -> ChunkTranslationResponse:
        if len(request.segments) > 1:
            midpoint = max(1, len(request.segments) // 2)
            left_request = self._clone_chunk_request(
                request,
                segments=request.segments[:midpoint],
                suffix="a",
            )
            right_request = self._clone_chunk_request(
                request,
                segments=request.segments[midpoint:],
                suffix="b",
            )
            left_results = self._translate_chunk_with_fallback(
                provider,
                None,
                left_request,
                estimator,
                retry_policy,
            )
            right_results = self._translate_chunk_with_fallback(
                provider,
                None,
                right_request,
                estimator,
                retry_policy,
            )
            return ChunkTranslationResponse(
                items=tuple(
                    self._result_to_chunk_item(result)
                    for result in [*left_results.results, *right_results.results]
                ),
                provider_name=provider.name,
                model_name=provider.model_name,
            )

        segment = request.segments[0]
        line_fragments = self._split_segment_lines(segment.source_text, estimator)
        translated_lines: list[str] = []
        for line in line_fragments:
            translated_fragments: list[str] = []
            for fragment in line:
                if fragment == "":
                    translated_fragments.append("")
                    continue
                response = retry_policy.run(
                    lambda fragment_text=fragment: provider.translate(
                        TranslationRequest(
                            text=fragment_text,
                            source_language=request.source_language,
                            target_language=request.target_language,
                            book_title=request.book_title,
                            context=SegmentContext(
                                chapter_title=request.context.chapter_title,
                                chapter_order=request.context.chapter_order,
                                segment_id=segment.segment_id,
                                segment_order=segment.segment_order,
                                segment_type=segment.segment_type,
                                extra=segment.extra,
                                previous_source_texts=request.context.previous_source_texts,
                                previous_translated_texts=request.context.previous_translated_texts,
                                following_source_texts=request.context.following_source_texts,
                                glossary_hints=request.context.glossary_hints,
                                translation_memory=request.context.translation_memory,
                                chapter_summary=request.context.chapter_summary,
                                narrative_mode=request.context.narrative_mode,
                            ),
                            options=request.options,
                        )
                    )
                )
                translated_fragments.append(response.translated_text)
            translated_lines.append("".join(translated_fragments))
        return ChunkTranslationResponse(
            items=(
                ChunkTranslationItem(
                    segment_id=segment.segment_id,
                    translated_text="\n".join(translated_lines),
                ),
            ),
            provider_name=provider.name,
            model_name=provider.model_name,
        )

    def _split_segment_lines(
        self,
        text: str,
        estimator: TokenBudgetEstimator,
    ) -> list[list[str]]:
        lines: list[list[str]] = []
        for raw_line in text.split("\n"):
            if raw_line == "":
                lines.append([""])
                continue
            if estimator.fits_single_segment(raw_line):
                lines.append([raw_line])
                continue
            split_fragments = estimator._split_line(raw_line)
            lines.append(split_fragments or [raw_line])
        return lines

    @staticmethod
    def _active_chapter_count(chapter_states: list[_ChapterExecutionState]) -> int:
        return max(
            1,
            sum(
                1
                for state in chapter_states
                if state.active_count > 0 or state.next_index < len(state.chunks)
            ),
        )

    @staticmethod
    def _dedupe_pending_segments(
        segments: list[Segment],
        *,
        settings: TranslationRuntimeSettings,
        leader_by_duplicate_key: dict[str, int],
        duplicate_segments_by_canonical_id: dict[int, list[Segment]],
    ) -> tuple[Segment, ...]:
        if not settings.duplicate_text_cache_enabled:
            return tuple(segments)

        canonical_segments: list[Segment] = []
        for segment in segments:
            cache_key = TranslationOrchestrator._duplicate_cache_key(segment, settings)
            if cache_key is None:
                canonical_segments.append(segment)
                continue
            canonical_id = leader_by_duplicate_key.get(cache_key)
            if canonical_id is None:
                leader_by_duplicate_key[cache_key] = segment.id
                canonical_segments.append(segment)
                continue
            duplicate_segments_by_canonical_id.setdefault(canonical_id, []).append(segment)
        return tuple(canonical_segments)

    @staticmethod
    def _duplicate_cache_key(
        segment: Segment,
        settings: TranslationRuntimeSettings,
    ) -> str | None:
        normalized_text = segment.source_text.strip()
        if len(normalized_text) < settings.duplicate_text_cache_min_chars:
            return None
        if segment.segment_type not in {
            SegmentType.TITLE,
            SegmentType.LIST_ITEM,
            SegmentType.IMAGE_CAPTION,
        }:
            return None
        return f"{segment.segment_type.value}:{normalized_text}"

    @staticmethod
    def _expand_duplicate_results(
        chunk_results: tuple[TranslatedSegmentResult, ...],
        *,
        duplicate_segments_by_canonical_id: dict[int, list[Segment]],
    ) -> tuple[TranslatedSegmentResult, ...]:
        expanded_results: list[TranslatedSegmentResult] = []
        for result in chunk_results:
            expanded_results.append(result)
            for duplicate_segment in duplicate_segments_by_canonical_id.get(result.segment_id, ()):
                expanded_results.append(
                    TranslatedSegmentResult(
                        segment_id=duplicate_segment.id,
                        translated_text=result.translated_text,
                        provider_name=result.provider_name,
                        model_name=result.model_name,
                    )
                )
        return tuple(expanded_results)

    @staticmethod
    def _clone_chunk_request(
        request: ChunkTranslationRequest,
        *,
        segments,
        suffix: str,
    ) -> ChunkTranslationRequest:
        return ChunkTranslationRequest(
            source_language=request.source_language,
            target_language=request.target_language,
            book_title=request.book_title,
            context=ChunkContext(
                chapter_title=request.context.chapter_title,
                chapter_order=request.context.chapter_order,
                chunk_id=f"{request.context.chunk_id}:{suffix}",
                chunk_sequence=request.context.chunk_sequence,
                previous_source_texts=request.context.previous_source_texts,
                previous_translated_texts=request.context.previous_translated_texts,
                following_source_texts=request.context.following_source_texts,
                glossary_hints=request.context.glossary_hints,
                translation_memory=request.context.translation_memory,
                chapter_summary=request.context.chapter_summary,
                narrative_mode=request.context.narrative_mode,
            ),
            segments=tuple(segments),
            options=request.options,
        )

    @staticmethod
    def _result_to_chunk_item(result: TranslatedSegmentResult) -> ChunkTranslationItem:
        return ChunkTranslationItem(
            segment_id=result.segment_id,
            translated_text=result.translated_text,
        )
