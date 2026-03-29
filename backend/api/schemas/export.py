from __future__ import annotations

from dataclasses import dataclass

from backend.api.schemas.book import ExportArtifactResponse


@dataclass(slots=True)
class ExportDownloadResponse:
    artifact: ExportArtifactResponse
    filename: str
    media_type: str
    path: str
