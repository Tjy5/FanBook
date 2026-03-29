from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.domain.enums import SegmentType
from backend.domain.models import SegmentExtra


class TranslationProviderError(Exception):
    pass


class UnsupportedTranslationProviderError(TranslationProviderError):
    pass


@dataclass(slots=True, frozen=True)
class SegmentContext:
    chapter_title: str
    chapter_order: int
    segment_id: int
    segment_order: int
    segment_type: SegmentType
    extra: SegmentExtra
    previous_source_texts: tuple[str, ...] = ()
    previous_translated_texts: tuple[str, ...] = ()
    following_source_texts: tuple[str, ...] = ()
    glossary_hints: tuple["GlossaryHint", ...] = ()
    translation_memory: tuple["TranslationMemoryEntry", ...] = ()
    chapter_summary: str | None = None
    narrative_mode: str | None = None


@dataclass(slots=True, frozen=True)
class GlossaryHint:
    source: str
    target: str | None = None


@dataclass(slots=True, frozen=True)
class TranslationMemoryEntry:
    source_text: str
    translated_text: str


@dataclass(slots=True, frozen=True)
class TranslationRequest:
    text: str
    source_language: str
    target_language: str
    book_title: str
    context: SegmentContext
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ChunkSegment:
    segment_id: int
    segment_order: int
    segment_type: SegmentType
    source_text: str
    extra: SegmentExtra


@dataclass(slots=True, frozen=True)
class ChunkContext:
    chapter_title: str
    chapter_order: int
    chunk_id: str
    chunk_sequence: int
    previous_source_texts: tuple[str, ...] = ()
    previous_translated_texts: tuple[str, ...] = ()
    following_source_texts: tuple[str, ...] = ()
    glossary_hints: tuple[GlossaryHint, ...] = ()
    translation_memory: tuple[TranslationMemoryEntry, ...] = ()
    chapter_summary: str | None = None
    narrative_mode: str | None = None


@dataclass(slots=True, frozen=True)
class ChunkTranslationRequest:
    source_language: str
    target_language: str
    book_title: str
    context: ChunkContext
    segments: tuple[ChunkSegment, ...]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TranslationResponse:
    translated_text: str
    provider_name: str
    model_name: str


@dataclass(slots=True, frozen=True)
class ChunkTranslationItem:
    segment_id: int
    translated_text: str


@dataclass(slots=True, frozen=True)
class ChunkTranslationResponse:
    items: tuple[ChunkTranslationItem, ...]
    provider_name: str
    model_name: str


@dataclass(slots=True, frozen=True)
class RuntimeCapabilityDetection:
    options: dict[str, Any] = field(default_factory=dict)
    option_sources: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TranslationProvider(ABC):
    default_model_name = "default"

    def __init__(
        self,
        *,
        model_name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.model_name = model_name or self.default_model_name
        self.options = dict(options or {})

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise NotImplementedError

    def translate_chunk(
        self,
        request: ChunkTranslationRequest,
    ) -> ChunkTranslationResponse:
        items: list[ChunkTranslationItem] = []
        for segment in request.segments:
            response = self.translate(
                TranslationRequest(
                    text=segment.source_text,
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
            items.append(
                ChunkTranslationItem(
                    segment_id=segment.segment_id,
                    translated_text=response.translated_text,
                )
            )
        return ChunkTranslationResponse(
            items=tuple(items),
            provider_name=self.name,
            model_name=self.model_name,
        )

    def detect_runtime_capabilities(self) -> RuntimeCapabilityDetection:
        return RuntimeCapabilityDetection()

    def update_options(self, options: dict[str, Any]) -> None:
        self.options = dict(options)

    def close(self) -> None:
        return None

    def detect_runtime_metadata(self) -> dict[str, Any]:
        return {}


def validate_chunk_response(
    request: ChunkTranslationRequest,
    response: ChunkTranslationResponse,
) -> None:
    expected_ids = [segment.segment_id for segment in request.segments]
    actual_ids = [item.segment_id for item in response.items]
    if actual_ids != expected_ids:
        raise TranslationProviderError(
            "Chunk translation response segment ids did not match the request order."
        )

    seen_ids: set[int] = set()
    for item in response.items:
        if item.segment_id in seen_ids:
            raise TranslationProviderError(
                f"Chunk translation response duplicated segment '{item.segment_id}'."
            )
        seen_ids.add(item.segment_id)
        if not item.translated_text.strip():
            raise TranslationProviderError(
                f"Chunk translation response returned an empty translation for segment '{item.segment_id}'."
            )
