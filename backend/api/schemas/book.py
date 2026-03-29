from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from backend.domain.models import Book, ExportArtifact, TranslationJob
from backend.storage.database import ChapterProgress

PayloadT = TypeVar("PayloadT")


@dataclass(slots=True)
class CreateBookRequest:
    filename: str
    content: bytes
    title: str | None = None
    source_language: str = "en"


@dataclass(slots=True)
class CreateBookResponse:
    book_id: int
    job_id: int
    status: str


@dataclass(slots=True)
class BookResponse:
    id: int
    filename: str
    title: str
    translated_title: str | None
    title_translation_status: str
    source_language: str
    source_path: str
    created_at: str

    @classmethod
    def from_book(cls, book: Book) -> "BookResponse":
        return cls(
            id=book.id,
            filename=book.filename,
            title=book.title,
            translated_title=book.translated_title,
            title_translation_status=book.title_translation_status,
            source_language=book.source_language,
            source_path=book.source_path,
            created_at=book.created_at,
        )


@dataclass(slots=True)
class TranslationJobResponse:
    id: int
    status: str
    provider_profile_name: str | None
    provider_name: str | None
    model_name: str | None
    progress: float
    error_summary: str | None
    resume_from: int | None
    created_at: str
    updated_at: str

    @classmethod
    def from_job(cls, job: TranslationJob) -> "TranslationJobResponse":
        return cls(
            id=job.id,
            status=job.status.value,
            provider_profile_name=job.provider_profile_name,
            provider_name=job.provider_name,
            model_name=job.model_name,
            progress=job.progress,
            error_summary=job.error_summary,
            resume_from=job.resume_from,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


@dataclass(slots=True)
class ChapterProgressResponse:
    chapter_id: int
    order: int
    title: str
    total_segments: int
    translated_segments: int
    failed_segments: int

    @classmethod
    def from_progress(cls, progress: ChapterProgress) -> "ChapterProgressResponse":
        return cls(
            chapter_id=progress.chapter_id,
            order=progress.chapter_order,
            title=progress.chapter_title,
            total_segments=progress.total_segments,
            translated_segments=progress.translated_segments,
            failed_segments=progress.failed_segments,
        )


@dataclass(slots=True)
class ExportArtifactResponse:
    id: int
    kind: str
    status: str
    path: str | None
    size: int | None
    created_at: str

    @classmethod
    def from_artifact(cls, artifact: ExportArtifact) -> "ExportArtifactResponse":
        return cls(
            id=artifact.id,
            kind=artifact.kind.value,
            status=artifact.status.value,
            path=artifact.path,
            size=artifact.size,
            created_at=artifact.created_at,
        )


@dataclass(slots=True)
class BookDetailResponse:
    book: BookResponse
    current_job: TranslationJobResponse | None
    chapters: tuple[ChapterProgressResponse, ...]
    artifacts: tuple[ExportArtifactResponse, ...]


@dataclass(slots=True)
class ErrorResponse:
    code: str
    message: str


@dataclass(slots=True)
class RouteResult(Generic[PayloadT]):
    status_code: int
    payload: PayloadT | ErrorResponse

    @classmethod
    def ok(cls, status_code: int, payload: PayloadT) -> "RouteResult[PayloadT]":
        return cls(status_code=status_code, payload=payload)

    @classmethod
    def fail(cls, status_code: int, code: str, message: str) -> "RouteResult[PayloadT]":
        return cls(status_code=status_code, payload=ErrorResponse(code=code, message=message))
