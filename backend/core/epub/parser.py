from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
import zipfile
from xml.etree import ElementTree as ET

from backend.domain.enums import SegmentType
from backend.domain.models import SegmentExtra

from .locator import (
    extract_segments_from_document,
    local_name,
    normalize_epub_path,
    normalize_slot_text,
)


@dataclass(slots=True, frozen=True)
class ParsedSegment:
    order: int
    source_text: str
    segment_type: SegmentType
    extra: SegmentExtra


@dataclass(slots=True, frozen=True)
class ParsedChapter:
    order: int
    title: str
    source_doc_path: str
    segments: tuple[ParsedSegment, ...]


@dataclass(slots=True, frozen=True)
class ParsedBook:
    title: str | None
    chapters: tuple[ParsedChapter, ...]


@dataclass(slots=True, frozen=True)
class _ManifestItem:
    path: str
    media_type: str
    properties: frozenset[str]


@dataclass(slots=True, frozen=True)
class _PackageDocument:
    title: str | None
    spine_paths: tuple[str, ...]
    nav_path: str | None
    ncx_path: str | None


class EpubParserError(Exception):
    pass


class EpubParser:
    _content_media_types = {"application/xhtml+xml", "text/html"}

    def parse_bytes(self, epub_bytes: bytes) -> ParsedBook:
        try:
            archive = zipfile.ZipFile(BytesIO(epub_bytes))
        except zipfile.BadZipFile as exc:
            raise EpubParserError("Uploaded file is not a valid EPUB archive.") from exc

        with archive:
            archive_index = {
                normalize_epub_path(info.filename): info.filename
                for info in archive.infolist()
            }
            opf_path = self._parse_container_opf_path(archive, archive_index)
            package = self._parse_package_document(archive, archive_index, opf_path)

            chapters: list[ParsedChapter] = []
            for doc_path in package.spine_paths:
                raw_document = self._read_archive_member(archive, archive_index, doc_path)
                document_root = self._parse_xml(raw_document, doc_path)
                located_segments = extract_segments_from_document(
                    document_root,
                    doc_path=doc_path,
                    is_nav=doc_path == package.nav_path,
                    is_ncx=doc_path == package.ncx_path,
                )
                if not located_segments:
                    continue

                title = self._derive_chapter_title(
                    doc_path,
                    document_root,
                    located_segments,
                )
                segments = tuple(
                    ParsedSegment(
                        order=index,
                        source_text=segment.source_text,
                        segment_type=segment.segment_type,
                        extra=segment.extra,
                    )
                    for index, segment in enumerate(located_segments, start=1)
                )
                chapters.append(
                    ParsedChapter(
                        order=len(chapters) + 1,
                        title=title,
                        source_doc_path=doc_path,
                        segments=segments,
                    )
                )

        if not chapters:
            raise EpubParserError(
                "EPUB does not contain any readable text segments in spine documents."
            )
        return ParsedBook(title=package.title, chapters=tuple(chapters))

    def _parse_container_opf_path(
        self,
        archive: zipfile.ZipFile,
        archive_index: dict[str, str],
    ) -> str:
        try:
            raw_container = self._read_archive_member(
                archive,
                archive_index,
                "META-INF/container.xml",
            )
        except EpubParserError as exc:
            raise EpubParserError(
                "EPUB is missing META-INF/container.xml."
            ) from exc

        root = self._parse_xml(raw_container, "META-INF/container.xml")
        for elem in root.iter():
            if local_name(elem.tag) != "rootfile":
                continue
            full_path = elem.attrib.get("full-path")
            if full_path:
                return normalize_epub_path(full_path)

        raise EpubParserError(
            "EPUB container.xml does not define an OPF package document."
        )

    def _parse_package_document(
        self,
        archive: zipfile.ZipFile,
        archive_index: dict[str, str],
        opf_path: str,
    ) -> _PackageDocument:
        raw_opf = self._read_archive_member(archive, archive_index, opf_path)
        root = self._parse_xml(raw_opf, opf_path)
        opf_dir = posixpath.dirname(opf_path)

        manifest: dict[str, _ManifestItem] = {}
        package_title: str | None = None
        spine_elem: ET.Element | None = None

        for elem in root.iter():
            name = local_name(elem.tag)
            if name == "item":
                item_id = elem.attrib.get("id")
                href = elem.attrib.get("href")
                if not item_id or not href:
                    continue
                manifest[item_id] = _ManifestItem(
                    path=self._resolve_href(opf_dir, href),
                    media_type=(elem.attrib.get("media-type") or "").lower(),
                    properties=frozenset(
                        part.strip()
                        for part in (elem.attrib.get("properties") or "").split()
                        if part.strip()
                    ),
                )
            elif name == "title" and package_title is None:
                text = normalize_slot_text(elem.text or "").strip()
                if text:
                    package_title = text
            elif name == "spine" and spine_elem is None:
                spine_elem = elem

        if spine_elem is None:
            raise EpubParserError("EPUB package document is missing a spine.")

        nav_path = next(
            (
                item.path
                for item in manifest.values()
                if "nav" in item.properties
            ),
            None,
        )

        ncx_path = None
        toc_id = spine_elem.attrib.get("toc")
        if toc_id and toc_id in manifest:
            ncx_path = manifest[toc_id].path
        else:
            for item in manifest.values():
                if item.media_type == "application/x-dtbncx+xml":
                    ncx_path = item.path
                    break

        spine_paths: list[str] = []
        seen_paths: set[str] = set()
        for child in list(spine_elem):
            if local_name(child.tag) != "itemref":
                continue
            idref = child.attrib.get("idref")
            if not idref or idref not in manifest:
                continue
            item = manifest[idref]
            if item.media_type not in self._content_media_types:
                continue
            if item.path in seen_paths:
                continue
            seen_paths.add(item.path)
            spine_paths.append(item.path)

        if not spine_paths:
            raise EpubParserError(
                "EPUB package does not contain any XHTML or HTML spine documents."
            )

        return _PackageDocument(
            title=package_title,
            spine_paths=tuple(spine_paths),
            nav_path=nav_path,
            ncx_path=ncx_path,
        )

    def _read_archive_member(
        self,
        archive: zipfile.ZipFile,
        archive_index: dict[str, str],
        path: str,
    ) -> bytes:
        normalized_path = normalize_epub_path(path)
        actual_path = archive_index.get(normalized_path)
        if actual_path is None:
            raise EpubParserError(
                f"EPUB archive is missing required member '{normalized_path}'."
            )
        return archive.read(actual_path)

    def _parse_xml(self, raw_xml: bytes, path: str) -> ET.Element:
        try:
            return ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            raise EpubParserError(
                f"EPUB document '{path}' is not well-formed XML."
            ) from exc

    def _resolve_href(self, base_dir: str, href: str) -> str:
        href = normalize_epub_path(href.split("#", 1)[0])
        if not href:
            raise EpubParserError("EPUB manifest contains an empty href.")
        resolved = posixpath.normpath(posixpath.join(base_dir, href))
        if resolved == ".":
            raise EpubParserError("EPUB manifest href resolves to an empty path.")
        return normalize_epub_path(resolved)

    def _derive_chapter_title(
        self,
        doc_path: str,
        document_root: ET.Element,
        segments: list,
    ) -> str:
        for segment in segments:
            if segment.segment_type == SegmentType.TITLE:
                title = self._normalize_display_text(segment.source_text)
                if title:
                    return title

        document_title = self._find_document_title(document_root)
        if document_title:
            return document_title
        return PurePosixPath(doc_path).stem

    def _find_document_title(self, root: ET.Element) -> str | None:
        for elem in root.iter():
            if local_name(elem.tag) != "title":
                continue
            text = normalize_slot_text(elem.text or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _normalize_display_text(value: str) -> str:
        parts = [part.strip() for part in value.splitlines() if part.strip()]
        return " ".join(parts)
