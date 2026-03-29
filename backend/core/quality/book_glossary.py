from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.core.providers.base import GlossaryHint
from backend.core.quality.glossary_store import GlossaryStore

if TYPE_CHECKING:
    from backend.core.translation.orchestrator import ChapterTranslationBatch


_TITLE_CASE_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")


@dataclass(slots=True, frozen=True)
class BookGlossarySnapshot:
    global_hints: tuple[GlossaryHint, ...]
    chapter_hints: dict[int, tuple[GlossaryHint, ...]]

    def hints_for_chapter(self, chapter_id: int) -> tuple[GlossaryHint, ...]:
        return self.chapter_hints.get(int(chapter_id), ())


class BookGlossaryBuilder:
    def build(
        self,
        *,
        chapters: tuple[ChapterTranslationBatch, ...],
        user_glossary: GlossaryStore | None = None,
    ) -> BookGlossarySnapshot:
        user_glossary = user_glossary or GlossaryStore()
        user_entries = tuple(
            GlossaryHint(entry.source, entry.target)
            for entry in user_glossary.entries
        )
        known_sources = {entry.source for entry in user_entries}

        global_counter: Counter[str] = Counter()
        chapter_counter: dict[int, Counter[str]] = defaultdict(Counter)
        for batch in chapters:
            for segment in batch.segments:
                for candidate in self._extract_candidates(segment.source_text):
                    if candidate in known_sources:
                        continue
                    global_counter[candidate] += 1
                    chapter_counter[batch.chapter.id][candidate] += 1

        global_hints = user_entries + tuple(
            GlossaryHint(source=name)
            for name, count in global_counter.most_common(24)
            if count >= 2
        )
        chapter_hints = {
            chapter_id: tuple(
                GlossaryHint(source=name)
                for name, count in counter.most_common(8)
                if count >= 2
            )
            for chapter_id, counter in chapter_counter.items()
        }
        return BookGlossarySnapshot(
            global_hints=global_hints,
            chapter_hints=chapter_hints,
        )

    @staticmethod
    def _extract_candidates(text: str) -> tuple[str, ...]:
        if not text:
            return ()
        return tuple(
            dict.fromkeys(match.group(0).strip() for match in _TITLE_CASE_RE.finditer(text))
        )
