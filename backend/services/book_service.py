from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from backend.core.epub.parser import EpubParser, EpubParserError, ParsedBook
from backend.domain.enums import SegmentStatus, TranslationJobStatus
from backend.domain.models import Book, Chapter, ExportArtifact, Segment, TranslationJob
from backend.storage.database import ChapterProgress, FanbookDatabase


class BookServiceError(Exception):
    pass


class InvalidBookUploadError(BookServiceError):
    pass


class BookNotFoundError(BookServiceError):
    pass


@dataclass(slots=True)
class CreatedBook:
    book: Book
    job: TranslationJob


@dataclass(slots=True)
class BookDetail:
    book: Book
    current_job: TranslationJob | None
    chapter_progress: tuple[ChapterProgress, ...]
    artifacts: tuple[ExportArtifact, ...]


class BookService:
    _unsafe_filename_chars = re.compile(r"[^A-Za-z0-9._ -]+")

    def __init__(
        self,
        database: FanbookDatabase,
        storage_root: str | Path,
        epub_parser: EpubParser | None = None,
    ) -> None:
        self.database = database
        self.storage_root = Path(storage_root)
        self.epub_parser = epub_parser or EpubParser()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def create_book(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None = None,
        source_language: str = "en",
    ) -> CreatedBook:
        safe_filename = self._sanitize_filename(filename)
        file_bytes = bytes(content)
        if not file_bytes:
            raise InvalidBookUploadError("Uploaded EPUB content is empty.")
        parsed_book = self._parse_epub(file_bytes)

        created_book = self.database.create_book(
            Book(
                filename=safe_filename,
                title=(
                    title.strip()
                    if title and title.strip()
                    else parsed_book.title or Path(safe_filename).stem
                ),
                source_language=source_language.strip() or "en",
                source_path="",
            )
        )

        upload_dir = self.storage_root / "uploads" / str(created_book.id)
        upload_path = upload_dir / "original.epub"

        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            upload_path.write_bytes(file_bytes)
            created_book = self.database.update_book_source_path(created_book.id, str(upload_path))
            self._persist_parsed_book(created_book.id, parsed_book)
            created_job = self.database.create_translation_job(
                TranslationJob(book_id=created_book.id, status=TranslationJobStatus.PENDING)
            )
        except Exception:
            shutil.rmtree(upload_dir, ignore_errors=True)
            self.database.delete_book(created_book.id)
            raise

        return CreatedBook(book=created_book, job=created_job)

    def get_book(self, book_id: int) -> BookDetail:
        book = self.database.get_book(int(book_id))
        if book is None:
            raise BookNotFoundError(f"Book '{book_id}' was not found.")

        return BookDetail(
            book=book,
            current_job=self.database.get_latest_translation_job(book.id),
            chapter_progress=tuple(self.database.get_chapter_progress(book.id)),
            artifacts=tuple(self.database.list_export_artifacts(book.id)),
        )

    def _sanitize_filename(self, filename: str) -> str:
        candidate = Path(filename).name.strip()
        if not candidate:
            raise InvalidBookUploadError("Filename is required.")
        candidate = self._unsafe_filename_chars.sub("_", candidate)
        if not candidate.lower().endswith(".epub"):
            raise InvalidBookUploadError("Only .epub uploads are supported.")
        return candidate

    def _parse_epub(self, file_bytes: bytes) -> ParsedBook:
        try:
            return self.epub_parser.parse_bytes(file_bytes)
        except EpubParserError as exc:
            raise InvalidBookUploadError(str(exc)) from exc

    def _persist_parsed_book(self, book_id: int, parsed_book: ParsedBook) -> None:
        for parsed_chapter in parsed_book.chapters:
            chapter = self.database.upsert_chapter(
                Chapter(
                    book_id=book_id,
                    order=parsed_chapter.order,
                    title=parsed_chapter.title,
                    source_doc_path=parsed_chapter.source_doc_path,
                )
            )
            for parsed_segment in parsed_chapter.segments:
                self.database.upsert_segment(
                    Segment(
                        chapter_id=chapter.id,
                        order=parsed_segment.order,
                        source_text=parsed_segment.source_text,
                        segment_type=parsed_segment.segment_type,
                        status=SegmentStatus.PENDING,
                        extra=parsed_segment.extra,
                    )
                )
