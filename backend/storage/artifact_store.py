from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.domain.enums import ExportArtifactKind


@dataclass(slots=True)
class ArtifactStore:
    root: Path

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def export_path(self, book_id: int, kind: ExportArtifactKind | str) -> Path:
        normalized_kind = self._kind_value(kind)
        export_dir = self.root / "exports" / str(book_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir / f"{normalized_kind}.epub"

    def temp_export_path(self, book_id: int, kind: ExportArtifactKind | str) -> Path:
        return self.export_path(book_id, kind).with_suffix(".epub.tmp")

    def report_path(
        self,
        book_id: int,
        kind: ExportArtifactKind | str,
        *,
        extension: str = ".json",
    ) -> Path:
        normalized_kind = self._kind_value(kind)
        normalized_extension = extension if str(extension).startswith(".") else f".{extension}"
        report_dir = self.root / "reports" / str(book_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir / f"{normalized_kind}{normalized_extension}"

    def temp_report_path(
        self,
        book_id: int,
        kind: ExportArtifactKind | str,
        *,
        extension: str = ".json",
    ) -> Path:
        report_path = self.report_path(book_id, kind, extension=extension)
        return report_path.with_suffix(f"{report_path.suffix}.tmp")

    @staticmethod
    def file_size(path: str | Path) -> int:
        return Path(path).stat().st_size

    @staticmethod
    def _kind_value(kind: ExportArtifactKind | str) -> str:
        if hasattr(kind, "value"):
            return str(kind.value)
        return str(kind)
