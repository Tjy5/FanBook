from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from backend.domain.models import Book, Chapter, ExportArtifact, Segment, TranslationJob


@dataclass(slots=True)
class ChapterProgress:
    chapter_id: int
    chapter_order: int
    chapter_title: str
    total_segments: int
    translated_segments: int
    failed_segments: int


class FanbookDatabase:
    """SQLite persistence for fanbook's minimum backend slice."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._lock, self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL,
                    translated_title TEXT,
                    title_translation_status TEXT NOT NULL DEFAULT 'pending',
                    source_language TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    chapter_order INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    source_doc_path TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL,
                    segment_order INTEGER NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT,
                    segment_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    extra TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS translation_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    provider_profile_name TEXT,
                    provider_name TEXT,
                    model_name TEXT,
                    progress REAL NOT NULL DEFAULT 0,
                    error_summary TEXT,
                    resume_from INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS export_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    path TEXT,
                    size INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chapters_book_order
                ON chapters(book_id, chapter_order);

                CREATE INDEX IF NOT EXISTS idx_segments_chapter_order
                ON segments(chapter_id, segment_order);

                CREATE INDEX IF NOT EXISTS idx_jobs_book_updated
                ON translation_jobs(book_id, updated_at DESC, id DESC);

                CREATE INDEX IF NOT EXISTS idx_artifacts_book_kind
                ON export_artifacts(book_id, kind);
                """
            )
            self._ensure_column(
                conn,
                "translation_jobs",
                "provider_profile_name",
                "TEXT",
            )
            self._ensure_column(
                conn,
                "books",
                "translated_title",
                "TEXT",
            )
            self._ensure_column(
                conn,
                "books",
                "title_translation_status",
                "TEXT NOT NULL DEFAULT 'pending'",
            )
            conn.execute(
                """
                UPDATE books
                SET title_translation_status = 'pending'
                WHERE COALESCE(title_translation_status, '') = ''
                """
            )
            conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _enum_value(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _safe_json_loads(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )

    @staticmethod
    def _models() -> Any:
        from backend.domain import models as domain_models

        return domain_models

    @staticmethod
    def _attr(obj: Any, *names: str, default: Any = None) -> Any:
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value is not None:
                    return value
        return default

    def _to_book(self, row: sqlite3.Row) -> "Book":
        m = self._models()
        return m.Book(
            id=int(row["id"]),
            filename=str(row["filename"]),
            title=str(row["title"]),
            source_language=str(row["source_language"]),
            source_path=str(row["source_path"]),
            translated_title=row["translated_title"],
            title_translation_status=str(row["title_translation_status"] or "pending"),
            created_at=str(row["created_at"]),
        )

    def _to_chapter(self, row: sqlite3.Row) -> "Chapter":
        m = self._models()
        return m.Chapter(
            id=int(row["id"]),
            book_id=int(row["book_id"]),
            order=int(row["chapter_order"]),
            title=str(row["title"]),
            source_doc_path=str(row["source_doc_path"]),
        )

    def _to_segment(self, row: sqlite3.Row) -> "Segment":
        m = self._models()
        return m.Segment(
            id=int(row["id"]),
            chapter_id=int(row["chapter_id"]),
            order=int(row["segment_order"]),
            source_text=str(row["source_text"]),
            translated_text=row["translated_text"],
            segment_type=str(row["segment_type"]),
            status=str(row["status"]),
            extra=self._safe_json_loads(row["extra"]),
        )

    def _to_translation_job(self, row: sqlite3.Row) -> "TranslationJob":
        m = self._models()
        return m.TranslationJob(
            id=int(row["id"]),
            book_id=int(row["book_id"]),
            status=str(row["status"]),
            provider_profile_name=row["provider_profile_name"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            progress=float(row["progress"]),
            error_summary=row["error_summary"],
            resume_from=row["resume_from"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _to_export_artifact(self, row: sqlite3.Row) -> "ExportArtifact":
        m = self._models()
        return m.ExportArtifact(
            id=int(row["id"]),
            book_id=int(row["book_id"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            path=row["path"],
            size=row["size"],
            created_at=str(row["created_at"]),
        )

    def create_book(self, book: "Book") -> "Book":
        created_at = self._attr(book, "created_at", default=self._now_iso())
        filename = self._attr(book, "filename")
        title = self._attr(book, "title")
        source_language = self._attr(book, "source_language", default="en")
        source_path = self._attr(book, "source_path", default="")
        translated_title = self._attr(book, "translated_title", default=None)
        title_translation_status = self._attr(
            book,
            "title_translation_status",
            default="pending",
        )

        with self._lock, self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books (
                    filename, title, translated_title, title_translation_status,
                    source_language, source_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    title,
                    translated_title,
                    title_translation_status,
                    source_language,
                    source_path,
                    created_at,
                ),
            )
            book_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load inserted book")
        return self._to_book(row)

    def update_book_source_path(self, book_id: int, source_path: str) -> "Book":
        with self._lock, self._connection() as conn:
            conn.execute(
                "UPDATE books SET source_path = ? WHERE id = ?",
                (source_path, book_id),
            )
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to update book source path")
        return self._to_book(row)

    def update_book_title_translation(
        self,
        book_id: int,
        *,
        translated_title: str | None,
        title_translation_status: str,
    ) -> "Book":
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE books
                SET translated_title = ?, title_translation_status = ?
                WHERE id = ?
                """,
                (translated_title, title_translation_status, book_id),
            )
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to update book title translation")
        return self._to_book(row)

    def delete_book(self, book_id: int) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            conn.commit()

    def create_translation_job(self, job: "TranslationJob") -> "TranslationJob":
        book_id = int(self._attr(job, "book_id"))
        status = self._enum_value(self._attr(job, "status"))
        provider_profile_name = self._attr(job, "provider_profile_name", default=None)
        provider_name = self._attr(job, "provider_name", default=None)
        model_name = self._attr(job, "model_name", default=None)
        progress = float(self._attr(job, "progress", default=0.0))
        error_summary = self._attr(job, "error_summary", default=None)
        resume_from = self._attr(job, "resume_from", default=None)
        created_at = self._attr(job, "created_at", default=self._now_iso())
        updated_at = self._attr(job, "updated_at", default=created_at)

        with self._lock, self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO translation_jobs (
                    book_id, status, provider_profile_name, provider_name, model_name, progress,
                    error_summary, resume_from, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    status,
                    provider_profile_name,
                    provider_name,
                    model_name,
                    progress,
                    error_summary,
                    resume_from,
                    created_at,
                    updated_at,
                ),
            )
            job_id = int(cursor.lastrowid)
            row = conn.execute(
                "SELECT * FROM translation_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load inserted translation job")
        return self._to_translation_job(row)

    def update_translation_job(self, job: "TranslationJob") -> "TranslationJob":
        job_id = int(self._attr(job, "id", default=0) or 0)
        if job_id <= 0:
            raise ValueError("Translation job id is required for update")

        book_id = int(self._attr(job, "book_id"))
        status = self._enum_value(self._attr(job, "status"))
        provider_profile_name = self._attr(job, "provider_profile_name", default=None)
        provider_name = self._attr(job, "provider_name", default=None)
        model_name = self._attr(job, "model_name", default=None)
        progress = float(self._attr(job, "progress", default=0.0))
        error_summary = self._attr(job, "error_summary", default=None)
        resume_from = self._attr(job, "resume_from", default=None)
        created_at = self._attr(job, "created_at", default=self._now_iso())
        updated_at = self._now_iso()

        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE translation_jobs
                SET
                    book_id = ?,
                    status = ?,
                    provider_profile_name = ?,
                    provider_name = ?,
                    model_name = ?,
                    progress = ?,
                    error_summary = ?,
                    resume_from = ?,
                    created_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    book_id,
                    status,
                    provider_profile_name,
                    provider_name,
                    model_name,
                    progress,
                    error_summary,
                    resume_from,
                    created_at,
                    updated_at,
                    job_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM translation_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load updated translation job")
        return self._to_translation_job(row)

    def upsert_chapter(self, chapter: "Chapter") -> "Chapter":
        chapter_id = int(self._attr(chapter, "id", default=0) or 0)
        values = (
            int(self._attr(chapter, "book_id")),
            int(self._attr(chapter, "order")),
            str(self._attr(chapter, "title")),
            str(self._attr(chapter, "source_doc_path")),
        )

        with self._lock, self._connection() as conn:
            if chapter_id > 0:
                conn.execute(
                    """
                    INSERT INTO chapters (id, book_id, chapter_order, title, source_doc_path)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        book_id = excluded.book_id,
                        chapter_order = excluded.chapter_order,
                        title = excluded.title,
                        source_doc_path = excluded.source_doc_path
                    """,
                    (chapter_id, *values),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO chapters (book_id, chapter_order, title, source_doc_path)
                    VALUES (?, ?, ?, ?)
                    """,
                    values,
                )
                chapter_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load chapter")
        return self._to_chapter(row)

    def upsert_segment(self, segment: "Segment") -> "Segment":
        segment_id = int(self._attr(segment, "id", default=0) or 0)
        extra_value = self._attr(segment, "extra", default={})
        extra_json = json.dumps(
            extra_value.to_dict() if hasattr(extra_value, "to_dict") else extra_value,
            ensure_ascii=False,
        )
        values = (
            int(self._attr(segment, "chapter_id")),
            int(self._attr(segment, "order")),
            str(self._attr(segment, "source_text")),
            self._attr(segment, "translated_text", default=None),
            self._enum_value(self._attr(segment, "segment_type")),
            self._enum_value(self._attr(segment, "status")),
            extra_json,
        )

        with self._lock, self._connection() as conn:
            if segment_id > 0:
                conn.execute(
                    """
                    INSERT INTO segments (
                        id, chapter_id, segment_order, source_text, translated_text,
                        segment_type, status, extra
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        chapter_id = excluded.chapter_id,
                        segment_order = excluded.segment_order,
                        source_text = excluded.source_text,
                        translated_text = excluded.translated_text,
                        segment_type = excluded.segment_type,
                        status = excluded.status,
                        extra = excluded.extra
                    """,
                    (segment_id, *values),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO segments (
                        chapter_id, segment_order, source_text, translated_text,
                        segment_type, status, extra
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                segment_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load segment")
        return self._to_segment(row)

    def upsert_export_artifact(self, artifact: "ExportArtifact") -> "ExportArtifact":
        artifact_id = int(self._attr(artifact, "id", default=0) or 0)
        values = (
            int(self._attr(artifact, "book_id")),
            self._enum_value(self._attr(artifact, "kind")),
            self._enum_value(self._attr(artifact, "status")),
            self._attr(artifact, "path", default=None),
            self._attr(artifact, "size", default=None),
            self._attr(artifact, "created_at", default=self._now_iso()),
        )

        with self._lock, self._connection() as conn:
            if artifact_id > 0:
                conn.execute(
                    """
                    INSERT INTO export_artifacts (id, book_id, kind, status, path, size, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        book_id = excluded.book_id,
                        kind = excluded.kind,
                        status = excluded.status,
                        path = excluded.path,
                        size = excluded.size,
                        created_at = excluded.created_at
                    """,
                    (artifact_id, *values),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO export_artifacts (book_id, kind, status, path, size, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                artifact_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM export_artifacts WHERE id = ?", (artifact_id,)).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load export artifact")
        return self._to_export_artifact(row)

    def get_book(self, book_id: int) -> "Book | None":
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            return None
        return self._to_book(row)

    def list_books(self) -> list["Book"]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM books
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._to_book(row) for row in rows]

    def get_latest_translation_job(self, book_id: int) -> "TranslationJob | None":
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM translation_jobs
                WHERE book_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (book_id,),
            ).fetchone()
        if row is None:
            return None
        return self._to_translation_job(row)

    def get_translation_job(self, job_id: int) -> "TranslationJob | None":
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM translation_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._to_translation_job(row)

    def list_chapters(self, book_id: int) -> list["Chapter"]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM chapters
                WHERE book_id = ?
                ORDER BY chapter_order ASC, id ASC
                """,
                (book_id,),
            ).fetchall()
        return [self._to_chapter(row) for row in rows]

    def list_export_artifacts(self, book_id: int) -> list["ExportArtifact"]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM export_artifacts
                WHERE book_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (book_id,),
            ).fetchall()
        return [self._to_export_artifact(row) for row in rows]

    def list_segments(self, chapter_id: int) -> list["Segment"]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM segments
                WHERE chapter_id = ?
                ORDER BY segment_order ASC, id ASC
                """,
                (chapter_id,),
            ).fetchall()
        return [self._to_segment(row) for row in rows]

    def list_book_segments(self, book_id: int) -> list["Segment"]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM segments s
                JOIN chapters c ON c.id = s.chapter_id
                WHERE c.book_id = ?
                ORDER BY c.chapter_order ASC, s.segment_order ASC, s.id ASC
                """,
                (book_id,),
            ).fetchall()
        return [self._to_segment(row) for row in rows]

    def count_book_segments(self, book_id: int) -> int:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(s.id) AS total_segments
                FROM segments s
                JOIN chapters c ON c.id = s.chapter_id
                WHERE c.book_id = ?
                """,
                (book_id,),
            ).fetchone()
        return int(row["total_segments"] or 0) if row is not None else 0

    def update_segment_translation(
        self,
        segment_id: int,
        *,
        translated_text: str | None,
        status: Any,
    ) -> "Segment":
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE segments
                SET translated_text = ?, status = ?
                WHERE id = ?
                """,
                (translated_text, self._enum_value(status), segment_id),
            )
            row = conn.execute(
                "SELECT * FROM segments WHERE id = ?",
                (segment_id,),
            ).fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to load updated segment")
        return self._to_segment(row)

    def get_chapter_progress(self, book_id: int) -> list[ChapterProgress]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                   c.id AS chapter_id,
                   c.chapter_order AS chapter_order,
                   c.title AS chapter_title,
                   COUNT(s.id) AS total_segments,
                   SUM(
                       CASE
                           WHEN LOWER(COALESCE(s.status, '')) = 'translated'
                           THEN 1 ELSE 0
                       END
                   ) AS translated_segments,
                   SUM(
                       CASE
                           WHEN LOWER(s.status) IN ('failed', 'error')
                           THEN 1 ELSE 0
                       END
                   ) AS failed_segments
               FROM chapters c
               LEFT JOIN segments s ON s.chapter_id = c.id
               WHERE c.book_id = ?
               GROUP BY c.id, c.chapter_order, c.title
               ORDER BY c.chapter_order ASC, c.id ASC
                """,
                (book_id,),
            ).fetchall()

        return [
            ChapterProgress(
                chapter_id=int(row["chapter_id"]),
                chapter_order=int(row["chapter_order"]),
                chapter_title=str(row["chapter_title"]),
                total_segments=int(row["total_segments"] or 0),
                translated_segments=int(row["translated_segments"] or 0),
                failed_segments=int(row["failed_segments"] or 0),
            )
            for row in rows
        ]

