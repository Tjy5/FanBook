from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

from backend.core.epub.locator import (
    build_elem_path_map,
    local_name,
    normalize_epub_path,
    normalize_slot_text,
    sha1_hex_with_null_separator,
)
from backend.domain.enums import ExportArtifactKind
from backend.domain.models import Segment


class EpubExportError(Exception):
    pass


_BILINGUAL_STYLE_MARKER = "data-fanbook-bilingual-style"
_BILINGUAL_SOURCE_CLASS = "fanbook-bilingual-source"
_BILINGUAL_TRANSLATION_CLASS = "fanbook-bilingual-translation"
_BILINGUAL_STYLE_TEXT = f"""
.{_BILINGUAL_SOURCE_CLASS} {{
  opacity: 0.52;
  margin-top: 0 !important;
  margin-bottom: 0.28em !important;
}}
.{_BILINGUAL_TRANSLATION_CLASS} {{
  margin-top: 0 !important;
  margin-bottom: 0.95em !important;
}}
h1.{_BILINGUAL_SOURCE_CLASS}, h2.{_BILINGUAL_SOURCE_CLASS}, h3.{_BILINGUAL_SOURCE_CLASS},
h4.{_BILINGUAL_SOURCE_CLASS}, h5.{_BILINGUAL_SOURCE_CLASS}, h6.{_BILINGUAL_SOURCE_CLASS} {{
  margin-bottom: 0.18em !important;
}}
h1.{_BILINGUAL_TRANSLATION_CLASS}, h2.{_BILINGUAL_TRANSLATION_CLASS}, h3.{_BILINGUAL_TRANSLATION_CLASS},
h4.{_BILINGUAL_TRANSLATION_CLASS}, h5.{_BILINGUAL_TRANSLATION_CLASS}, h6.{_BILINGUAL_TRANSLATION_CLASS} {{
  margin-bottom: 1.1em !important;
}}
li.{_BILINGUAL_TRANSLATION_CLASS}, aside.{_BILINGUAL_TRANSLATION_CLASS},
blockquote.{_BILINGUAL_TRANSLATION_CLASS}, div.{_BILINGUAL_TRANSLATION_CLASS},
section.{_BILINGUAL_TRANSLATION_CLASS}, td.{_BILINGUAL_TRANSLATION_CLASS},
th.{_BILINGUAL_TRANSLATION_CLASS} {{
  margin-bottom: 0.75em !important;
}}
""".strip()


@dataclass(slots=True, frozen=True)
class DocumentWriteResult:
    content: bytes
    applied_segments: int
    skipped_segments: int


class BaseEpubWriter:
    def __init__(self, *, bilingual: bool) -> None:
        self.bilingual = bilingual

    def write_document(
        self,
        *,
        raw_document: bytes,
        doc_path: str,
        segments: list[Segment],
    ) -> DocumentWriteResult:
        try:
            root = ET.fromstring(raw_document)
        except ET.ParseError as exc:
            raise EpubExportError(
                f"Failed to parse EPUB document '{doc_path}' during export."
            ) from exc

        path_map = build_elem_path_map(root)
        elem_by_path = {
            path_map[id(elem)]: elem
            for elem in root.iter()
            if isinstance(elem.tag, str)
        }

        applied = 0
        skipped = 0
        block_refs: list[tuple[ET.Element, ET.Element]] = []
        inserted_block_paths: set[str] = set()
        styled_translation_paths: set[str] = set()
        allow_bilingual_insert = self._allow_bilingual_insert(doc_path, root, segments)

        for segment in segments:
            translated_text = (segment.translated_text or "").strip()
            if translated_text == "":
                skipped += 1
                continue

            extra = segment.extra
            part_defs = extra.parts
            if not part_defs:
                skipped += 1
                continue

            dst_lines = segment.translated_text.split("\n")
            if len(dst_lines) != len(part_defs):
                skipped += 1
                continue

            current_texts: list[str] = []
            resolved_parts: list[tuple[str, ET.Element]] = []
            ok = True
            for part in part_defs:
                slot = part.get("slot")
                path = part.get("path")
                if slot not in {"text", "tail"} or not path:
                    ok = False
                    break
                elem = elem_by_path.get(path)
                if elem is None:
                    ok = False
                    break
                if slot == "text":
                    current_texts.append(normalize_slot_text(elem.text or ""))
                else:
                    current_texts.append(normalize_slot_text(elem.tail or ""))
                resolved_parts.append((slot, elem))

            if not ok:
                skipped += 1
                continue

            if sha1_hex_with_null_separator(current_texts) != extra.src_digest:
                skipped += 1
                continue

            if allow_bilingual_insert:
                block_elem = elem_by_path.get(extra.block_path)
                if block_elem is not None and (
                    "\n".join(current_texts) != segment.translated_text
                ):
                    if extra.block_path not in styled_translation_paths:
                        self._style_bilingual_translation(block_elem)
                        styled_translation_paths.add(extra.block_path)
                    if extra.block_path not in inserted_block_paths:
                        block_refs.append((block_elem, deepcopy(block_elem)))
                        inserted_block_paths.add(extra.block_path)

            for (slot, elem), text in zip(resolved_parts, dst_lines, strict=True):
                if slot == "text":
                    elem.text = text
                else:
                    elem.tail = text
            applied += 1

        if allow_bilingual_insert:
            for block_elem, clone in reversed(block_refs):
                self._style_bilingual_clone(clone)
                self._insert_clone_before(root, block_elem, clone)
            if block_refs:
                self._ensure_bilingual_styles(root)

        _register_document_namespaces(raw_document)
        return DocumentWriteResult(
            content=ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            ),
            applied_segments=applied,
            skipped_segments=skipped,
        )

    def _allow_bilingual_insert(
        self,
        doc_path: str,
        root: ET.Element,
        segments: list[Segment],
    ) -> bool:
        if not self.bilingual:
            return False

        doc_lower = doc_path.lower()
        if doc_lower.endswith(".ncx") or doc_lower.endswith(".opf"):
            return False
        root_name = local_name(root.tag).lower()
        if root_name in {"ncx", "package"}:
            return False

        return not any(
            segment.extra.is_nav
            or segment.extra.is_ncx
            or segment.extra.is_opf_metadata
            for segment in segments
        )

    def _insert_clone_before(
        self,
        root: ET.Element,
        target: ET.Element,
        clone: ET.Element,
        ) -> bool:
        for index, child in enumerate(list(root)):
            if child is target:
                root.insert(index, clone)
                clone.tail = (clone.tail or "") + "\n"
                return True
            if self._insert_clone_before(child, target, clone):
                return True
        return False

    @staticmethod
    def _style_bilingual_clone(clone: ET.Element) -> None:
        BaseEpubWriter._remove_css_class(clone, _BILINGUAL_TRANSLATION_CLASS)
        BaseEpubWriter._append_css_class(clone, _BILINGUAL_SOURCE_CLASS)
        BaseEpubWriter._sanitize_bilingual_clone(clone)

    @staticmethod
    def _style_bilingual_translation(block: ET.Element) -> None:
        BaseEpubWriter._append_css_class(block, _BILINGUAL_TRANSLATION_CLASS)

    @staticmethod
    def _append_css_class(elem: ET.Element, css_class: str) -> None:
        current = elem.attrib.get("class", "").split()
        if css_class not in current:
            current.append(css_class)
        elem.attrib["class"] = " ".join(part for part in current if part)

    @staticmethod
    def _remove_css_class(elem: ET.Element, css_class: str) -> None:
        current = [part for part in elem.attrib.get("class", "").split() if part != css_class]
        if current:
            elem.attrib["class"] = " ".join(current)
            return
        elem.attrib.pop("class", None)

    @staticmethod
    def _strip_ids(elem: ET.Element) -> None:
        elem.attrib.pop("id", None)

    @staticmethod
    def _sanitize_bilingual_clone(elem: ET.Element) -> None:
        BaseEpubWriter._prune_pagebreak_children(elem)
        BaseEpubWriter._strip_ids(elem)
        for attr_name in ("aria-labelledby", "aria-describedby", "headers"):
            elem.attrib.pop(attr_name, None)
        for child in elem:
            if isinstance(child.tag, str):
                BaseEpubWriter._sanitize_bilingual_clone(child)

    @staticmethod
    def _prune_pagebreak_children(parent: ET.Element) -> None:
        for child in list(parent):
            if not isinstance(child.tag, str):
                continue
            BaseEpubWriter._prune_pagebreak_children(child)
            if BaseEpubWriter._is_pagebreak_element(child):
                BaseEpubWriter._unwrap_child(parent, child)

    @staticmethod
    def _is_pagebreak_element(elem: ET.Element) -> bool:
        role = str(elem.attrib.get("role", "")).lower()
        if role == "doc-pagebreak":
            return True
        for attr_name, attr_value in elem.attrib.items():
            if local_name(attr_name).lower() == "type" and "pagebreak" in str(attr_value).lower():
                return True
        return False

    @staticmethod
    def _unwrap_child(parent: ET.Element, child: ET.Element) -> None:
        serialized_text = (child.text or "") + (child.tail or "")
        siblings = list(parent)
        try:
            child_index = siblings.index(child)
        except ValueError:
            return
        parent.remove(child)
        if not serialized_text:
            return
        if child_index == 0:
            parent.text = f"{parent.text or ''}{serialized_text}"
            return
        previous = siblings[child_index - 1]
        previous.tail = f"{previous.tail or ''}{serialized_text}"

    def _ensure_bilingual_styles(self, root: ET.Element) -> None:
        head = self._find_first_element(root, "head")
        if head is None:
            return
        for child in head:
            if (
                isinstance(child.tag, str)
                and local_name(child.tag).lower() == "style"
                and child.attrib.get(_BILINGUAL_STYLE_MARKER) == "1"
            ):
                return

        style_elem = ET.Element(
            self._qualified_name(root, "style"),
            {"type": "text/css", _BILINGUAL_STYLE_MARKER: "1"},
        )
        style_elem.text = _BILINGUAL_STYLE_TEXT
        head.append(style_elem)

    @staticmethod
    def _find_first_element(root: ET.Element, tag_name: str) -> ET.Element | None:
        lowered = tag_name.lower()
        for elem in root.iter():
            if isinstance(elem.tag, str) and local_name(elem.tag).lower() == lowered:
                return elem
        return None

    @staticmethod
    def _qualified_name(root: ET.Element, local_tag: str) -> str:
        tag = root.tag
        if isinstance(tag, str) and tag.startswith("{") and "}" in tag:
            namespace = tag[1:].split("}", 1)[0]
            return f"{{{namespace}}}{local_tag}"
        return local_tag


def _register_document_namespaces(raw_document: bytes) -> None:
    seen_namespaces: set[tuple[str, str]] = set()
    for _, namespace in ET.iterparse(BytesIO(raw_document), events=("start-ns",)):
        prefix, uri = namespace
        key = (prefix or "", uri)
        if key in seen_namespaces:
            continue
        seen_namespaces.add(key)
        ET.register_namespace(prefix or "", uri)


@dataclass(slots=True, frozen=True)
class EpubExportResult:
    output_path: str
    applied_segments: int
    skipped_segments: int
    size: int


class EpubExporter:
    def __init__(
        self,
        *,
        zh_writer: BaseEpubWriter,
        bilingual_writer: BaseEpubWriter,
    ) -> None:
        self.zh_writer = zh_writer
        self.bilingual_writer = bilingual_writer

    def export(
        self,
        *,
        original_epub_path: str | Path,
        segments: list[Segment],
        kind: ExportArtifactKind,
        output_path: str | Path,
        book_title_override: str | None = None,
    ) -> EpubExportResult:
        writer = self._select_writer(kind)
        grouped_segments = self._group_segments_by_doc(segments)
        normalized_output = Path(output_path)
        normalized_output.parent.mkdir(parents=True, exist_ok=True)

        modified_docs: dict[str, bytes] = {}
        applied_segments = 0
        skipped_segments = 0

        with zipfile.ZipFile(original_epub_path, "r") as reader:
            archive_index = {
                normalize_epub_path(info.filename): info.filename
                for info in reader.infolist()
            }
            self._apply_package_title_override(
                reader=reader,
                archive_index=archive_index,
                modified_docs=modified_docs,
                title_override=book_title_override,
            )
            for doc_path, doc_segments in grouped_segments.items():
                actual_path = archive_index.get(normalize_epub_path(doc_path))
                if actual_path is None:
                    skipped_segments += len(doc_segments)
                    continue
                write_result = writer.write_document(
                    raw_document=reader.read(actual_path),
                    doc_path=doc_path,
                    segments=doc_segments,
                )
                modified_docs[normalize_epub_path(doc_path)] = write_result.content
                applied_segments += write_result.applied_segments
                skipped_segments += write_result.skipped_segments

            with zipfile.ZipFile(normalized_output, "w") as writer_zip:
                mimetype_name = archive_index.get("mimetype")
                if mimetype_name is not None:
                    writer_zip.writestr(
                        "mimetype",
                        reader.read(mimetype_name),
                        compress_type=zipfile.ZIP_STORED,
                    )

                for info in reader.infolist():
                    normalized_name = normalize_epub_path(info.filename)
                    if normalized_name == "mimetype":
                        continue
                    writer_zip.writestr(
                        info.filename,
                        modified_docs.get(normalized_name, reader.read(info.filename)),
                    )

        return EpubExportResult(
            output_path=str(normalized_output),
            applied_segments=applied_segments,
            skipped_segments=skipped_segments,
            size=normalized_output.stat().st_size,
        )

    def _select_writer(self, kind: ExportArtifactKind) -> BaseEpubWriter:
        if kind is ExportArtifactKind.ZH:
            return self.zh_writer
        if kind is ExportArtifactKind.BILINGUAL:
            return self.bilingual_writer
        raise EpubExportError(f"Unsupported export kind '{kind.value}'.")

    @staticmethod
    def _group_segments_by_doc(segments: list[Segment]) -> dict[str, list[Segment]]:
        grouped: dict[str, list[Segment]] = {}
        for segment in segments:
            doc_path = segment.extra.doc_path
            if not doc_path:
                continue
            grouped.setdefault(doc_path, []).append(segment)
        return grouped

    def _apply_package_title_override(
        self,
        *,
        reader: zipfile.ZipFile,
        archive_index: dict[str, str],
        modified_docs: dict[str, bytes],
        title_override: str | None,
    ) -> None:
        normalized_title = str(title_override or "").strip()
        if not normalized_title:
            return

        package_doc_path = self._find_package_document_path(reader, archive_index)
        if package_doc_path is None:
            return

        actual_path = archive_index.get(package_doc_path)
        if actual_path is None:
            return

        modified_docs[package_doc_path] = self._rewrite_package_title(
            raw_document=reader.read(actual_path),
            doc_path=package_doc_path,
            title_override=normalized_title,
        )

    @staticmethod
    def _find_package_document_path(
        reader: zipfile.ZipFile,
        archive_index: dict[str, str],
    ) -> str | None:
        actual_container_path = archive_index.get("META-INF/container.xml")
        if actual_container_path is None:
            return None
        try:
            root = ET.fromstring(reader.read(actual_container_path))
        except ET.ParseError:
            return None

        for elem in root.iter():
            if local_name(elem.tag) != "rootfile":
                continue
            full_path = str(elem.attrib.get("full-path") or "").strip()
            if full_path:
                return normalize_epub_path(full_path)
        return None

    @staticmethod
    def _rewrite_package_title(
        *,
        raw_document: bytes,
        doc_path: str,
        title_override: str,
    ) -> bytes:
        try:
            root = ET.fromstring(raw_document)
        except ET.ParseError as exc:
            raise EpubExportError(
                f"Failed to parse EPUB package document '{doc_path}' during export."
            ) from exc

        for elem in root.iter():
            if local_name(elem.tag) != "title":
                continue
            elem.text = title_override
            break

        _register_document_namespaces(raw_document)
        return ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )
