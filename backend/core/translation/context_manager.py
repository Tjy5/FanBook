from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.domain.models import Segment


@dataclass(slots=True, frozen=True)
class TranslationContextWindow:
    previous_source_texts: tuple[str, ...]
    previous_translated_texts: tuple[str, ...]
    following_source_texts: tuple[str, ...] = ()


class ChapterContextManager:
    def __init__(self, window_size: int = 2) -> None:
        self.window_size = max(0, int(window_size))

    def build(
        self,
        segments: tuple[Segment, ...],
        current_index: int,
    ) -> TranslationContextWindow:
        return self.build_range(
            segments,
            start_index=current_index,
            end_index=current_index + 1,
            before_window=self.window_size,
            after_window=0,
            translated_lookup=None,
        )

    def build_range(
        self,
        segments: tuple[Segment, ...],
        *,
        start_index: int,
        end_index: int,
        before_window: int,
        after_window: int,
        translated_lookup: Mapping[int, str] | None,
    ) -> TranslationContextWindow:
        normalized_before = max(0, int(before_window))
        normalized_after = max(0, int(after_window))
        if not segments:
            return TranslationContextWindow((), (), ())

        start_index = max(0, int(start_index))
        end_index = max(start_index, min(len(segments), int(end_index)))

        previous_segments = segments[max(0, start_index - normalized_before):start_index]
        following_segments = segments[end_index:min(len(segments), end_index + normalized_after)]
        translated_lookup = translated_lookup or {}
        return TranslationContextWindow(
            previous_source_texts=tuple(segment.source_text for segment in previous_segments),
            previous_translated_texts=tuple(
                translated_lookup.get(segment.id, segment.translated_text or "")
                for segment in previous_segments
                if (translated_lookup.get(segment.id, segment.translated_text or "")).strip()
            ),
            following_source_texts=tuple(segment.source_text for segment in following_segments),
        )
