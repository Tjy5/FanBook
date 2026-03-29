from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from backend.domain.enums import SegmentType
from backend.domain.models import SegmentExtra


_INLINE_WHITESPACE_RE = re.compile(r"[\r\n\t]+")
_MULTI_SPACE_RE = re.compile(r" {2,}")
_TITLE_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = _TITLE_TAGS | {
    "article",
    "aside",
    "blockquote",
    "caption",
    "dd",
    "div",
    "dt",
    "figcaption",
    "li",
    "p",
    "section",
    "td",
    "th",
}
_SKIP_SUBTREE_TAGS = {
    "code",
    "kbd",
    "math",
    "noscript",
    "pre",
    "rt",
    "samp",
    "script",
    "style",
    "svg",
    "var",
}
_FOOTNOTE_HINTS = ("footnote", "endnote", "note")


@dataclass(slots=True, frozen=True)
class TextPartRef:
    slot: str
    path: str


@dataclass(slots=True, frozen=True)
class LocatedSegment:
    source_text: str
    segment_type: SegmentType
    extra: SegmentExtra


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def normalize_epub_path(path: str) -> str:
    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def normalize_slot_text(text: str) -> str:
    if (
        "\r" not in text
        and "\n" not in text
        and "\t" not in text
        and "  " not in text
    ):
        return text
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    return _MULTI_SPACE_RE.sub(" ", text)


def sha1_hex_with_null_separator(parts: list[str]) -> str:
    hasher = hashlib.sha1()
    for index, part in enumerate(parts):
        if index:
            hasher.update(b"\x00")
        hasher.update(part.encode("utf-8"))
    return hasher.hexdigest()


def iter_children_elements(elem: ET.Element) -> list[ET.Element]:
    return [child for child in list(elem) if isinstance(child.tag, str)]


def build_elem_path_map(root: ET.Element) -> dict[int, str]:
    path_map: dict[int, str] = {}

    def walk(elem: ET.Element, path: str) -> None:
        path_map[id(elem)] = path
        counters: dict[str, int] = {}
        for child in iter_children_elements(elem):
            name = local_name(child.tag)
            counters[name] = counters.get(name, 0) + 1
            walk(child, f"{path}/{name}[{counters[name]}]")

    walk(root, f"/{local_name(root.tag)}[1]")
    return path_map


def find_first_descendant(root: ET.Element, tag_name: str) -> ET.Element | None:
    for elem in root.iter():
        if isinstance(elem.tag, str) and local_name(elem.tag) == tag_name:
            return elem
    return None


def has_block_descendant(
    elem: ET.Element,
    cache: dict[int, bool],
) -> bool:
    cached = cache.get(id(elem))
    if cached is not None:
        return cached

    result = False
    for child in iter_children_elements(elem):
        if local_name(child.tag).lower() in _BLOCK_TAGS or has_block_descendant(
            child,
            cache,
        ):
            result = True
            break

    cache[id(elem)] = result
    return result


def iter_translatable_text_slots(
    root: ET.Element,
    block: ET.Element,
    path_map: dict[int, str],
) -> list[tuple[TextPartRef, str]]:
    del root
    results: list[tuple[TextPartRef, str]] = []

    def walk(elem: ET.Element) -> None:
        name = local_name(elem.tag).lower()
        if name in _SKIP_SUBTREE_TAGS:
            return

        elem_path = path_map[id(elem)]
        if elem.text:
            results.append((TextPartRef(slot="text", path=elem_path), elem.text))

        for child in iter_children_elements(elem):
            walk(child)
            if child.tail:
                results.append(
                    (
                        TextPartRef(slot="tail", path=path_map[id(child)]),
                        child.tail,
                    )
                )

    walk(block)
    return results


def classify_segment_type(elem: ET.Element) -> SegmentType:
    name = local_name(elem.tag).lower()
    if name in _TITLE_TAGS:
        return SegmentType.TITLE
    if name in {"caption", "figcaption"}:
        return SegmentType.IMAGE_CAPTION
    if name in {"dd", "dt", "li"}:
        return SegmentType.LIST_ITEM

    attr_text = " ".join(str(value) for value in elem.attrib.values()).lower()
    if any(hint in attr_text for hint in _FOOTNOTE_HINTS):
        return SegmentType.FOOTNOTE

    if name in {
        "article",
        "aside",
        "blockquote",
        "div",
        "p",
        "section",
        "td",
        "th",
    }:
        return SegmentType.PARAGRAPH
    return SegmentType.OTHER


def collect_document_units(
    root: ET.Element,
    elem: ET.Element,
    path_map: dict[int, str],
    block_descendant_cache: dict[int, bool],
) -> list[tuple[ET.Element, str, list[tuple[TextPartRef, str]]]]:
    name = local_name(elem.tag).lower()
    if name in _SKIP_SUBTREE_TAGS:
        return []

    is_block = name in _BLOCK_TAGS
    has_nested_blocks = has_block_descendant(elem, block_descendant_cache)
    elem_path = path_map[id(elem)]

    if is_block and not has_nested_blocks:
        return [
            (
                elem,
                elem_path,
                iter_translatable_text_slots(root, elem, path_map),
            )
        ]

    units: list[tuple[ET.Element, str, list[tuple[TextPartRef, str]]]] = []
    if is_block and has_nested_blocks and elem.text:
        units.append(
            (
                elem,
                elem_path,
                [(TextPartRef(slot="text", path=elem_path), elem.text)],
            )
        )

    for child in iter_children_elements(elem):
        units.extend(
            collect_document_units(
                root=root,
                elem=child,
                path_map=path_map,
                block_descendant_cache=block_descendant_cache,
            )
        )
        if is_block and has_nested_blocks and child.tail:
            units.append(
                (
                    elem,
                    elem_path,
                    [
                        (
                            TextPartRef(slot="tail", path=path_map[id(child)]),
                            child.tail,
                        )
                    ],
                )
            )

    return units


def extract_segments_from_document(
    root: ET.Element,
    *,
    doc_path: str,
    is_nav: bool = False,
    is_ncx: bool = False,
    is_opf_metadata: bool = False,
) -> list[LocatedSegment]:
    body_root = find_first_descendant(root, "body")
    document_root = body_root if body_root is not None else root
    path_map = build_elem_path_map(root)
    block_descendant_cache: dict[int, bool] = {}
    units = collect_document_units(
        root=root,
        elem=document_root,
        path_map=path_map,
        block_descendant_cache=block_descendant_cache,
    )

    segments: list[LocatedSegment] = []
    normalized_doc_path = normalize_epub_path(doc_path)
    for block_elem, block_path, slots in units:
        part_defs: list[dict[str, str]] = []
        part_texts: list[str] = []
        has_visible_text = False

        for ref, raw_text in slots:
            normalized_text = normalize_slot_text(raw_text)
            part_defs.append({"slot": ref.slot, "path": ref.path})
            part_texts.append(normalized_text)
            if normalized_text.strip():
                has_visible_text = True

        if not has_visible_text:
            continue

        slot_value = part_defs[0]["slot"] if len(part_defs) == 1 else "mixed"
        extra = SegmentExtra(
            doc_path=normalized_doc_path,
            block_path=block_path,
            parts=part_defs,
            slot=slot_value,
            src_digest=sha1_hex_with_null_separator(part_texts),
            is_nav=is_nav,
            is_ncx=is_ncx,
            is_opf_metadata=is_opf_metadata,
        )
        segments.append(
            LocatedSegment(
                source_text="\n".join(part_texts),
                segment_type=classify_segment_type(block_elem),
                extra=extra,
            )
        )

    return segments

