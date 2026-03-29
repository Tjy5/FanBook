from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.export.bilingual_epub_writer import BilingualEpubWriter
from backend.core.export.exporter import EpubExporter, EpubExportError
from backend.core.export.zh_epub_writer import ZHEpubWriter
from backend.domain.enums import (
    ExportArtifactKind,
    ExportArtifactStatus,
    SegmentStatus,
    TranslationJobStatus,
)
from backend.domain.models import ExportArtifact
from backend.services.book_service import BookNotFoundError
from backend.storage.artifact_store import ArtifactStore
from backend.storage.database import FanbookDatabase


class ExportServiceError(Exception):
    pass


class ExportPreconditionError(ExportServiceError):
    pass


@dataclass(slots=True, frozen=True)
class ExportDownload:
    artifact: ExportArtifact
    filename: str
    media_type: str
    path: str


class ExportService:
    def __init__(
        self,
        database: FanbookDatabase,
        *,
        artifact_store: ArtifactStore,
        exporter: EpubExporter | None = None,
    ) -> None:
        self.database = database
        self.artifact_store = artifact_store
        self.exporter = exporter or EpubExporter(
            zh_writer=ZHEpubWriter(),
            bilingual_writer=BilingualEpubWriter(),
        )

    def get_export_download(
        self,
        *,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> ExportDownload:
        book = self.database.get_book(int(book_id))
        if book is None:
            raise BookNotFoundError(f"Book '{book_id}' was not found.")

        artifact = self._latest_artifact(book.id, kind)
        if artifact is not None and artifact.status is ExportArtifactStatus.READY:
            if artifact.path is not None and Path(artifact.path).exists():
                return ExportDownload(
                    artifact=artifact,
                    filename=Path(artifact.path).name,
                    media_type="application/epub+zip",
                    path=artifact.path,
                )

        return self._build_export(book.id, kind)

    def _build_export(
        self,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> ExportDownload:
        book = self.database.get_book(book_id)
        if book is None:
            raise BookNotFoundError(f"Book '{book_id}' was not found.")

        latest_job = self.database.get_latest_translation_job(book.id)
        if latest_job is None or latest_job.status is not TranslationJobStatus.COMPLETED:
            raise ExportPreconditionError(
                f"Book '{book_id}' is not ready for export until translation completes."
            )

        segments = self.database.list_book_segments(book.id)
        if not segments:
            raise ExportPreconditionError(
                f"Book '{book_id}' does not have translated segments to export."
            )
        if any(
            segment.status is not SegmentStatus.TRANSLATED
            or (segment.translated_text or "").strip() == ""
            for segment in segments
        ):
            raise ExportPreconditionError(
                f"Book '{book_id}' is not ready for export until all segments are translated."
            )

        current_artifact = self._latest_artifact(book.id, kind)
        pending_artifact = self.database.upsert_export_artifact(
            ExportArtifact(
                id=current_artifact.id if current_artifact is not None else 0,
                book_id=book.id,
                kind=kind,
                status=ExportArtifactStatus.PENDING,
                path=None,
                size=None,
                created_at=(
                    current_artifact.created_at
                    if current_artifact is not None
                    else ExportArtifact(book_id=book.id, kind=kind, status=ExportArtifactStatus.PENDING).created_at
                ),
            )
        )

        temp_path = self.artifact_store.temp_export_path(book.id, kind)
        final_path = self.artifact_store.export_path(book.id, kind)
        try:
            export_result = self.exporter.export(
                original_epub_path=book.source_path,
                segments=segments,
                kind=kind,
                output_path=temp_path,
                book_title_override=(
                    book.translated_title
                    if str(book.title_translation_status or "").strip().lower() == "completed"
                    and str(book.translated_title or "").strip()
                    else book.title
                ),
            )
            temp_path.replace(final_path)
            ready_artifact = self.database.upsert_export_artifact(
                ExportArtifact(
                    id=pending_artifact.id,
                    book_id=book.id,
                    kind=kind,
                    status=ExportArtifactStatus.READY,
                    path=str(final_path),
                    size=export_result.size,
                    created_at=pending_artifact.created_at,
                )
            )
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            self.database.upsert_export_artifact(
                ExportArtifact(
                    id=pending_artifact.id,
                    book_id=book.id,
                    kind=kind,
                    status=ExportArtifactStatus.FAILED,
                    path=None,
                    size=None,
                    created_at=pending_artifact.created_at,
                )
            )
            raise ExportServiceError(str(exc)) from exc

        return ExportDownload(
            artifact=ready_artifact,
            filename=final_path.name,
            media_type="application/epub+zip",
            path=str(final_path),
        )

    def _latest_artifact(
        self,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> ExportArtifact | None:
        for artifact in self.database.list_export_artifacts(book_id):
            if artifact.kind is kind:
                return artifact
        return None
