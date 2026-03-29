from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .enums import (
    ExportArtifactKind,
    ExportArtifactStatus,
    SegmentStatus,
    SegmentType,
    TranslationJobStatus,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class SegmentExtra:
    doc_path: str = ""
    block_path: str = ""
    parts: list[dict[str, str]] = field(default_factory=list)
    slot: str = "text"
    src_digest: str = ""
    is_nav: bool = False
    is_ncx: bool = False
    is_opf_metadata: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SegmentExtra":
        raw_parts = value.get("parts", [])
        parts: list[dict[str, str]] = []
        if isinstance(raw_parts, list):
            for item in raw_parts:
                if isinstance(item, dict):
                    path = str(item.get("path", ""))
                    if path:
                        parts.append(
                            {
                                "slot": str(item.get("slot", "text")),
                                "path": path,
                            }
                        )
                elif isinstance(item, str) and item:
                    parts.append({"slot": "text", "path": item})

        return cls(
            doc_path=str(value.get("doc_path", "")),
            block_path=str(value.get("block_path", "")),
            parts=parts,
            slot=str(value.get("slot", parts[0]["slot"] if parts else "text")),
            src_digest=str(value.get("src_digest", "")),
            is_nav=bool(value.get("is_nav", False)),
            is_ncx=bool(value.get("is_ncx", False)),
            is_opf_metadata=bool(value.get("is_opf_metadata", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_path": self.doc_path,
            "block_path": self.block_path,
            "parts": [
                {
                    "slot": str(item.get("slot", "text")),
                    "path": str(item.get("path", "")),
                }
                for item in self.parts
            ],
            "slot": self.slot,
            "src_digest": self.src_digest,
            "is_nav": self.is_nav,
            "is_ncx": self.is_ncx,
            "is_opf_metadata": self.is_opf_metadata,
        }


@dataclass(slots=True)
class Book:
    filename: str
    title: str
    source_language: str
    source_path: str
    translated_title: str | None = None
    title_translation_status: str = "pending"
    id: int = 0
    created_at: str = field(default_factory=now_iso)


@dataclass(slots=True)
class Chapter:
    book_id: int
    order: int
    title: str
    source_doc_path: str
    id: int = 0


@dataclass(slots=True)
class Segment:
    chapter_id: int
    order: int
    source_text: str
    segment_type: SegmentType | str
    status: SegmentStatus | str
    id: int = 0
    translated_text: str | None = None
    extra: SegmentExtra | dict[str, Any] = field(default_factory=SegmentExtra)

    def __post_init__(self) -> None:
        if isinstance(self.segment_type, str):
            self.segment_type = SegmentType(self.segment_type)
        if isinstance(self.status, str):
            self.status = SegmentStatus(self.status)
        if isinstance(self.extra, dict):
            self.extra = SegmentExtra.from_dict(self.extra)


@dataclass(slots=True)
class TranslationJob:
    book_id: int
    status: TranslationJobStatus | str
    id: int = 0
    provider_profile_name: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    progress: float = 0.0
    error_summary: str | None = None
    resume_from: int | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = TranslationJobStatus(self.status)


@dataclass(slots=True)
class ExportArtifact:
    book_id: int
    kind: ExportArtifactKind | str
    status: ExportArtifactStatus | str
    id: int = 0
    path: str | None = None
    size: int | None = None
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            self.kind = ExportArtifactKind(self.kind)
        if isinstance(self.status, str):
            self.status = ExportArtifactStatus(self.status)
