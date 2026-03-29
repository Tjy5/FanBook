from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backend.domain.enums import ExportArtifactKind, ExportArtifactStatus
from backend.domain.models import ExportArtifact
from backend.services.book_service import BookNotFoundError
from backend.storage.artifact_store import ArtifactStore
from backend.storage.database import FanbookDatabase


class ConsistencyReportServiceError(Exception):
    pass


class ConsistencyReportNotReadyError(ConsistencyReportServiceError):
    pass


@dataclass(slots=True, frozen=True)
class ConsistencyReportDownload:
    artifact: ExportArtifact
    filename: str
    media_type: str
    path: str


class ConsistencyReportService:
    def __init__(
        self,
        database: FanbookDatabase,
        *,
        artifact_store: ArtifactStore,
    ) -> None:
        self.database = database
        self.artifact_store = artifact_store

    def get_download(
        self,
        *,
        book_id: int,
        markdown: bool = False,
    ) -> ConsistencyReportDownload:
        book = self.database.get_book(int(book_id))
        if book is None:
            raise BookNotFoundError(f"Book '{book_id}' was not found.")

        artifact = self._latest_report_artifact(book.id)
        if (
            artifact is None
            or artifact.status is not ExportArtifactStatus.READY
            or not artifact.path
            or not Path(artifact.path).exists()
        ):
            raise ConsistencyReportNotReadyError(
                f"Book '{book_id}' does not have a ready consistency report yet."
            )

        if markdown:
            markdown_path = self.artifact_store.report_path(
                book.id,
                ExportArtifactKind.CONSISTENCY_REPORT,
                extension=".md",
            )
            if not markdown_path.exists():
                raise ConsistencyReportNotReadyError(
                    f"Book '{book_id}' does not have a ready Markdown consistency report yet."
                )
            return ConsistencyReportDownload(
                artifact=artifact,
                filename=markdown_path.name,
                media_type="text/markdown; charset=utf-8",
                path=str(markdown_path),
            )

        return ConsistencyReportDownload(
            artifact=artifact,
            filename=Path(artifact.path).name,
            media_type="application/json",
            path=str(artifact.path),
        )

    def load_json(self, book_id: int) -> dict[str, object]:
        download = self.get_download(book_id=book_id, markdown=False)
        try:
            payload = json.loads(Path(download.path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConsistencyReportServiceError("Failed to load consistency report.") from exc
        if not isinstance(payload, dict):
            raise ConsistencyReportServiceError("Consistency report payload is invalid.")
        return payload

    def _latest_report_artifact(self, book_id: int) -> ExportArtifact | None:
        for artifact in self.database.list_export_artifacts(book_id):
            if artifact.kind is ExportArtifactKind.CONSISTENCY_REPORT:
                return artifact
        return None
