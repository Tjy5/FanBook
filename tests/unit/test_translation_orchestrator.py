from __future__ import annotations

import threading
import time

from backend.core.providers.base import (
    ChunkTranslationItem,
    ChunkTranslationRequest,
    ChunkTranslationResponse,
    TranslationProvider,
    TranslationRequest,
    TranslationResponse,
)
from backend.core.translation.orchestrator import (
    ChapterTranslationBatch,
    TranslationOrchestrator,
    _GlobalRateController,
)
from backend.core.translation.runtime_settings import TranslationRuntimeSettings
from backend.domain.enums import SegmentStatus, SegmentType
from backend.domain.models import Book, Chapter, Segment


class SleepingChunkProvider(TranslationProvider):
    default_model_name = "sleeping-v1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self.current_active = 0
        self.max_active = 0

    @property
    def name(self) -> str:
        return "sleeping"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(
            translated_text=request.text,
            provider_name=self.name,
            model_name=self.model_name,
        )

    def translate_chunk(
        self,
        request: ChunkTranslationRequest,
    ) -> ChunkTranslationResponse:
        with self._lock:
            self.current_active += 1
            self.max_active = max(self.max_active, self.current_active)
        try:
            time.sleep(0.05)
            return ChunkTranslationResponse(
                items=tuple(
                    ChunkTranslationItem(
                        segment_id=segment.segment_id,
                        translated_text=f"ZH: {segment.source_text}",
                    )
                    for segment in request.segments
                ),
                provider_name=self.name,
                model_name=self.model_name,
            )
        finally:
            with self._lock:
                self.current_active -= 1


class RecordingChunkProvider(TranslationProvider):
    default_model_name = "recording-v1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.requested_texts: list[str] = []

    @property
    def name(self) -> str:
        return "recording"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(
            translated_text=f"ZH: {request.text}",
            provider_name=self.name,
            model_name=self.model_name,
        )

    def translate_chunk(
        self,
        request: ChunkTranslationRequest,
    ) -> ChunkTranslationResponse:
        self.requested_texts.extend(segment.source_text for segment in request.segments)
        return ChunkTranslationResponse(
            items=tuple(
                ChunkTranslationItem(
                    segment_id=segment.segment_id,
                    translated_text=f"ZH: {segment.source_text}",
                )
                for segment in request.segments
            ),
            provider_name=self.name,
            model_name=self.model_name,
        )


def _build_book() -> Book:
    return Book(
        id=1,
        filename="demo.epub",
        title="Demo",
        source_language="en",
        source_path="demo.epub",
    )


def _build_batch(segment_count: int) -> ChapterTranslationBatch:
    chapter = Chapter(
        id=1,
        book_id=1,
        order=1,
        title="Chapter One",
        source_doc_path="chapter-1.xhtml",
    )
    segments = tuple(
        Segment(
            id=index + 1,
            chapter_id=chapter.id,
            order=index + 1,
            source_text=("Long segment " + str(index) + " ") * 40,
            segment_type=SegmentType.PARAGRAPH,
            status=SegmentStatus.PENDING,
        )
        for index in range(segment_count)
    )
    return ChapterTranslationBatch(chapter=chapter, segments=segments)


def test_orchestrator_adapts_single_chapter_concurrency() -> None:
    provider = SleepingChunkProvider()
    orchestrator = TranslationOrchestrator()
    settings = TranslationRuntimeSettings.from_options(
        {
            "global_max_concurrency": 6,
            "per_chapter_concurrency": 6,
            "min_per_chapter_concurrency": 2,
            "chunk_target_tokens": 64,
        }
    )

    results = orchestrator.translate_book(
        book=_build_book(),
        chapters=(_build_batch(6),),
        provider=provider,
        settings=settings,
    )

    assert len(results) == 6
    assert provider.max_active >= 4


def test_orchestrator_reuses_exact_duplicate_low_risk_segments() -> None:
    provider = RecordingChunkProvider()
    orchestrator = TranslationOrchestrator()
    chapter = Chapter(
        id=1,
        book_id=1,
        order=1,
        title="Chapter One",
        source_doc_path="chapter-1.xhtml",
    )
    batch = ChapterTranslationBatch(
        chapter=chapter,
        segments=(
            Segment(
                id=1,
                chapter_id=chapter.id,
                order=1,
                source_text="Repeatable Chapter Title",
                segment_type=SegmentType.TITLE,
                status=SegmentStatus.PENDING,
            ),
            Segment(
                id=2,
                chapter_id=chapter.id,
                order=2,
                source_text="Repeatable Chapter Title",
                segment_type=SegmentType.TITLE,
                status=SegmentStatus.PENDING,
            ),
            Segment(
                id=3,
                chapter_id=chapter.id,
                order=3,
                source_text="Repeated body text stays contextual.",
                segment_type=SegmentType.PARAGRAPH,
                status=SegmentStatus.PENDING,
            ),
            Segment(
                id=4,
                chapter_id=chapter.id,
                order=4,
                source_text="Repeated body text stays contextual.",
                segment_type=SegmentType.PARAGRAPH,
                status=SegmentStatus.PENDING,
            ),
        ),
    )

    results = orchestrator.translate_book(
        book=_build_book(),
        chapters=(batch,),
        provider=provider,
        settings=TranslationRuntimeSettings.from_options({"chunk_target_tokens": 1000}),
    )

    assert len(results) == 4
    assert provider.requested_texts.count("Repeatable Chapter Title") == 1
    assert provider.requested_texts.count("Repeated body text stays contextual.") == 2


def test_global_rate_controller_scales_up_and_down() -> None:
    controller = _GlobalRateController(
        enabled=True,
        max_limit=8,
        current_limit=3,
        min_limit=2,
        successes_before_scale_up=2,
    )

    controller.note_success()
    controller.note_success()
    assert controller.current_limit == 4

    controller.note_degraded_success()
    assert controller.current_limit == 3

    controller.note_failure("OpenAI API request failed with status 429: rate limit")
    assert controller.current_limit == 2
