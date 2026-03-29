from __future__ import annotations

from backend.api.schemas.book import ExportArtifactResponse, RouteResult
from backend.api.schemas.export import ExportDownloadResponse
from backend.domain.enums import ExportArtifactKind
from backend.services.book_service import BookNotFoundError
from backend.services.export_service import (
    ExportPreconditionError,
    ExportService,
    ExportServiceError,
)


class ExportRoutes:
    def __init__(self, export_service: ExportService) -> None:
        self.export_service = export_service

    def download_zh(self, book_id: int) -> RouteResult[ExportDownloadResponse]:
        return self._download(book_id, ExportArtifactKind.ZH)

    def download_bilingual(
        self,
        book_id: int,
    ) -> RouteResult[ExportDownloadResponse]:
        return self._download(book_id, ExportArtifactKind.BILINGUAL)

    def _download(
        self,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> RouteResult[ExportDownloadResponse]:
        try:
            download = self.export_service.get_export_download(
                book_id=int(book_id),
                kind=kind,
            )
        except ValueError:
            return RouteResult.fail(400, "invalid_book_id", "Book id must be an integer.")
        except BookNotFoundError as exc:
            return RouteResult.fail(404, "book_not_found", str(exc))
        except ExportPreconditionError as exc:
            return RouteResult.fail(409, "export_not_ready", str(exc))
        except ExportServiceError as exc:
            return RouteResult.fail(500, "export_failed", str(exc))
        except Exception:
            return RouteResult.fail(500, "internal_error", "Failed to export book.")

        return RouteResult.ok(
            200,
            ExportDownloadResponse(
                artifact=ExportArtifactResponse.from_artifact(download.artifact),
                filename=download.filename,
                media_type=download.media_type,
                path=download.path,
            ),
        )
