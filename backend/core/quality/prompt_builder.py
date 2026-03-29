from __future__ import annotations

import json

from backend.core.providers.base import ChunkTranslationRequest, TranslationRequest
from backend.domain.enums import SegmentType

from .glossary_store import GlossaryStore


class TranslationPromptBuilder:
    _FAST_LANE_SEGMENT_TYPES = frozenset(
        {
            SegmentType.TITLE,
            SegmentType.LIST_ITEM,
            SegmentType.IMAGE_CAPTION,
        }
    )

    def __init__(self, glossary_store: GlossaryStore | None = None) -> None:
        self.glossary_store = glossary_store or GlossaryStore()

    def build(self, request_payload: TranslationRequest) -> str:
        context = request_payload.context
        is_fast_lane = self._is_fast_lane_segment_type(context.segment_type)
        sections: list[str] = self._build_segment_header(
            request_payload,
            is_fast_lane=is_fast_lane,
        )
        focus_guidance = self._focus_guidance(context.narrative_mode)
        if focus_guidance:
            sections.append(focus_guidance)

        if not is_fast_lane:
            if context.previous_source_texts:
                sections.append(
                    "Previous source context:\n" + "\n".join(context.previous_source_texts)
                )
            if context.previous_translated_texts:
                sections.append(
                    "Previous translated context:\n" + "\n".join(context.previous_translated_texts)
                )
            if context.following_source_texts:
                sections.append(
                    "Following source context:\n" + "\n".join(context.following_source_texts)
                )
            if context.chapter_summary:
                sections.append("Chapter memory:\n" + context.chapter_summary)
            if context.glossary_hints:
                sections.append(
                    "Glossary and consistency hints:\n"
                    + "\n".join(self._render_hint_line(hint) for hint in context.glossary_hints)
                )
            if context.translation_memory:
                sections.append(
                    "Recent translation memory:\n"
                    + "\n".join(
                        f"- SRC: {entry.source_text}\n  DST: {entry.translated_text}"
                        for entry in context.translation_memory
                    )
                )

        glossary_block = self.glossary_store.render_prompt_block()
        if glossary_block:
            sections.append("Glossary:\n" + glossary_block)
        return "\n\n".join(sections)

    def build_chunk(self, request_payload: ChunkTranslationRequest) -> str:
        context = request_payload.context
        is_fast_lane = self._is_fast_lane_chunk(request_payload)
        sections: list[str] = self._build_chunk_header(
            request_payload,
            is_fast_lane=is_fast_lane,
        )
        focus_guidance = self._focus_guidance(
            context.narrative_mode or self._detect_chunk_focus(request_payload)
        )
        if focus_guidance:
            sections.append(focus_guidance)

        if not is_fast_lane:
            if context.previous_source_texts:
                sections.append(
                    "Previous source context:\n" + "\n".join(context.previous_source_texts)
                )
            if context.previous_translated_texts:
                sections.append(
                    "Previous translated context:\n" + "\n".join(context.previous_translated_texts)
                )
            if context.following_source_texts:
                sections.append(
                    "Following source context:\n" + "\n".join(context.following_source_texts)
                )
            if context.chapter_summary:
                sections.append("Chapter memory:\n" + context.chapter_summary)
        if context.glossary_hints:
            rendered_hints = [self._render_hint_line(hint) for hint in context.glossary_hints]
            sections.append(
                "Glossary and consistency hints:\n" + "\n".join(rendered_hints)
            )
        if not is_fast_lane and context.translation_memory:
            sections.append(
                "Recent translation memory:\n"
                + "\n".join(
                    f"- SRC: {entry.source_text}\n  DST: {entry.translated_text}"
                    for entry in context.translation_memory
                )
            )
        sections.append(
            "Expected JSON shape:\n"
            + json.dumps(
                [
                    {
                        "segment_id": request_payload.segments[0].segment_id if request_payload.segments else 0,
                        "translated_text": "...",
                    }
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return "\n\n".join(sections)

    @staticmethod
    def _render_hint_line(hint) -> str:
        if hint.target:
            return f"- {hint.source} => {hint.target}"
        return f"- Keep translation consistent for: {hint.source}"

    @staticmethod
    def _focus_guidance(narrative_mode: str | None) -> str:
        normalized = str(narrative_mode or "").strip().lower()
        if normalized == "dialogue_focus":
            return (
                "Dialogue focus:\n"
                "- Keep speaker tone and forms of address stable.\n"
                "- Preserve quotation rhythm and conversational pacing."
            )
        if normalized == "narrative_focus":
            return (
                "Narrative focus:\n"
                "- Keep viewpoint, tense, and descriptive pacing stable.\n"
                "- Prefer smooth literary narration over literal phrasing."
            )
        return ""

    @staticmethod
    def _detect_chunk_focus(request_payload: ChunkTranslationRequest) -> str:
        dialogue_segments = 0
        total_segments = 0
        for segment in request_payload.segments:
            total_segments += 1
            text = segment.source_text.strip()
            if not text:
                continue
            if text.startswith(("“", "\"", "'", "‘")) or text.count("“") >= 2 or text.count("\"") >= 2:
                dialogue_segments += 1
        if total_segments > 0 and dialogue_segments * 2 >= total_segments:
            return "dialogue_focus"
        return "narrative_focus"

    @classmethod
    def _is_fast_lane_segment_type(cls, segment_type: SegmentType) -> bool:
        return segment_type in cls._FAST_LANE_SEGMENT_TYPES

    @classmethod
    def _is_fast_lane_chunk(cls, request_payload: ChunkTranslationRequest) -> bool:
        if not request_payload.segments:
            return False
        return all(
            cls._is_fast_lane_segment_type(segment.segment_type)
            for segment in request_payload.segments
        )

    @staticmethod
    def _build_segment_header(
        request_payload: TranslationRequest,
        *,
        is_fast_lane: bool,
    ) -> list[str]:
        context = request_payload.context
        if is_fast_lane:
            return [
                "Translate the provided short text into fluent Simplified Chinese.",
                "Keep the wording concise and preserve numbering or emphasis markers when present.",
                "Return only the translated text with no explanations.",
                f"Book title: {request_payload.book_title}",
                f"Chapter {context.chapter_order}: {context.chapter_title}",
                f"Segment type: {context.segment_type.value}",
                "Routing mode: fast_lane",
            ]
        return [
            "Translate the provided text into fluent Simplified Chinese.",
            "Preserve structure, line breaks, numbering, and emphasis markers when they matter.",
            "Return only the translated text with no explanations.",
            f"Book title: {request_payload.book_title}",
            f"Chapter {context.chapter_order}: {context.chapter_title}",
            f"Segment type: {context.segment_type.value}",
            "Routing mode: heavy_context",
        ]

    @staticmethod
    def _build_chunk_header(
        request_payload: ChunkTranslationRequest,
        *,
        is_fast_lane: bool,
    ) -> list[str]:
        context = request_payload.context
        segment_types = sorted({segment.segment_type.value for segment in request_payload.segments})
        segment_types_text = ", ".join(segment_types) if segment_types else "unknown"
        if is_fast_lane:
            return [
                "Translate each short segment into fluent Simplified Chinese.",
                "Keep each translation concise and preserve numbering, bullets, and emphasis markers.",
                "Return a JSON array only.",
                "Each item must have exactly two keys: segment_id and translated_text.",
                "The array order must match the input order.",
                "Do not merge segments, do not omit segments, and do not add commentary.",
                f"Book title: {request_payload.book_title}",
                f"Chapter {context.chapter_order}: {context.chapter_title}",
                f"Chunk id: {context.chunk_id}",
                f"Segment types: {segment_types_text}",
                "Routing mode: fast_lane",
            ]
        return [
            "Translate each segment into fluent Simplified Chinese.",
            "Preserve line breaks, numbering, emphasis markers, and intra-segment structure.",
            "Return a JSON array only.",
            "Each item must have exactly two keys: segment_id and translated_text.",
            "The array order must match the input order.",
            "Do not merge segments, do not omit segments, and do not add commentary.",
            f"Book title: {request_payload.book_title}",
            f"Chapter {context.chapter_order}: {context.chapter_title}",
            f"Chunk id: {context.chunk_id}",
            f"Segment types: {segment_types_text}",
            "Routing mode: heavy_context",
        ]
