from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.providers.base import GlossaryHint

if TYPE_CHECKING:
    from backend.core.translation.orchestrator import ChapterTranslationBatch


_TITLE_CASE_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
_HONORIFIC_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Professor|Captain|Colonel|Sir|Lady)\.?\s+"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)
_ALL_CAPS_RE = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})?\b")
_CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")
_SOURCE_STOPWORDS = frozenset(
    {
        "A",
        "An",
        "As",
        "At",
        "But",
        "Chapter",
        "He",
        "Her",
        "His",
        "I",
        "If",
        "In",
        "It",
        "Its",
        "My",
        "No",
        "Not",
        "Of",
        "On",
        "Or",
        "She",
        "The",
        "Their",
        "There",
        "They",
        "This",
        "Those",
        "We",
        "What",
        "When",
        "Who",
        "Why",
        "You",
    }
)
_TARGET_STOPWORDS = frozenset(
    {
        "一个",
        "一种",
        "一阵",
        "不是",
        "不能",
        "他们",
        "但是",
        "你们",
        "你说",
        "先生",
        "其实",
        "出来",
        "只是",
        "可以",
        "可是",
        "因为",
        "地方",
        "如果",
        "她们",
        "已经",
        "应该",
        "我们",
        "没有",
        "然后",
        "现在",
        "知道",
        "突然",
        "自己",
        "这样",
        "还是",
    }
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True, frozen=True)
class TermTranslationCandidate:
    text: str
    count: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TermTranslationCandidate":
        return cls(
            text=str(payload.get("text") or "").strip(),
            count=max(0, int(payload.get("count") or 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "count": self.count,
        }


@dataclass(slots=True, frozen=True)
class BookTermMemoryEntry:
    source: str
    occurrences: int
    chapter_ids: tuple[int, ...]
    aliases: tuple[str, ...] = ()
    preferred_target: str | None = None
    target_candidates: tuple[TermTranslationCandidate, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BookTermMemoryEntry":
        raw_candidates = payload.get("target_candidates") or []
        return cls(
            source=str(payload.get("source") or "").strip(),
            occurrences=max(0, int(payload.get("occurrences") or 0)),
            chapter_ids=tuple(int(item) for item in payload.get("chapter_ids") or ()),
            aliases=tuple(str(item).strip() for item in payload.get("aliases") or () if str(item).strip()),
            preferred_target=(
                str(payload["preferred_target"]).strip()
                if payload.get("preferred_target") is not None
                else None
            ),
            target_candidates=tuple(
                TermTranslationCandidate.from_dict(item)
                for item in raw_candidates
                if isinstance(item, dict)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "occurrences": self.occurrences,
            "chapter_ids": list(self.chapter_ids),
            "aliases": list(self.aliases),
            "preferred_target": self.preferred_target,
            "target_candidates": [candidate.to_dict() for candidate in self.target_candidates],
        }

    def to_hint(self) -> GlossaryHint:
        return GlossaryHint(source=self.source, target=self.preferred_target)


@dataclass(slots=True, frozen=True)
class BookTermMemorySnapshot:
    entries: tuple[BookTermMemoryEntry, ...]
    chapter_index: dict[int, tuple[BookTermMemoryEntry, ...]]
    created_at: str = ""

    @classmethod
    def empty(cls) -> "BookTermMemorySnapshot":
        return cls(entries=(), chapter_index={}, created_at=_now_iso())

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BookTermMemorySnapshot":
        raw_entries = payload.get("entries") or ()
        entries = tuple(
            BookTermMemoryEntry.from_dict(item)
            for item in raw_entries
            if isinstance(item, dict)
        )
        entry_by_source = {entry.source: entry for entry in entries}
        raw_chapter_index = payload.get("chapter_index") or {}
        chapter_index: dict[int, tuple[BookTermMemoryEntry, ...]] = {}
        if isinstance(raw_chapter_index, dict):
            for chapter_id, sources in raw_chapter_index.items():
                try:
                    normalized_chapter_id = int(chapter_id)
                except (TypeError, ValueError):
                    continue
                normalized_entries = tuple(
                    entry_by_source[source]
                    for source in sources or ()
                    if source in entry_by_source
                )
                if normalized_entries:
                    chapter_index[normalized_chapter_id] = normalized_entries
        return cls(
            entries=entries,
            chapter_index=chapter_index,
            created_at=str(payload.get("created_at") or _now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_version": 1,
            "created_at": self.created_at or _now_iso(),
            "entries": [entry.to_dict() for entry in self.entries],
            "chapter_index": {
                str(chapter_id): [entry.source for entry in entries]
                for chapter_id, entries in self.chapter_index.items()
            },
        }

    def hints_for_chapter(
        self,
        chapter_id: int,
        *,
        limit: int | None = None,
    ) -> tuple[GlossaryHint, ...]:
        hints = tuple(entry.to_hint() for entry in self.chapter_index.get(int(chapter_id), ()))
        if not hints:
            hints = tuple(entry.to_hint() for entry in self.entries)
        if limit is not None:
            return hints[: max(0, int(limit))]
        return hints

    def entries_for_chapter(
        self,
        chapter_id: int,
        *,
        limit: int | None = None,
    ) -> tuple[BookTermMemoryEntry, ...]:
        entries = self.chapter_index.get(int(chapter_id), self.entries)
        if limit is not None:
            return entries[: max(0, int(limit))]
        return entries


class BookTermMemoryBuilder:
    def build(
        self,
        *,
        chapters: tuple["ChapterTranslationBatch", ...],
        max_global_terms: int = 36,
        max_terms_per_chapter: int = 8,
    ) -> BookTermMemorySnapshot:
        source_counter: Counter[str] = Counter()
        chapter_counter: dict[int, Counter[str]] = defaultdict(Counter)
        translated_candidates: dict[str, Counter[str]] = defaultdict(Counter)

        for batch in chapters:
            for segment in batch.segments:
                source_terms = self.extract_source_candidates(segment.source_text)
                if not source_terms:
                    continue
                for source_term in source_terms:
                    source_counter[source_term] += 1
                    chapter_counter[batch.chapter.id][source_term] += 1
                target_terms = self._extract_target_candidates(segment.translated_text or "")
                if not target_terms:
                    continue
                # Limit noisy co-occurrence mapping to small candidate sets.
                if len(source_terms) > 2 or len(target_terms) > 4:
                    continue
                for source_term in source_terms:
                    for target_term in target_terms:
                        translated_candidates[source_term][target_term] += 1

        ranked_sources = [
            source
            for source, count in source_counter.most_common(max_global_terms * 2)
            if count >= 2
        ]
        if not ranked_sources:
            return BookTermMemorySnapshot.empty()

        aliases_by_source = self._build_aliases(tuple(ranked_sources))
        selected_sources = tuple(ranked_sources[: max(1, int(max_global_terms))])
        entries_by_source: dict[str, BookTermMemoryEntry] = {}
        for source in selected_sources:
            target_candidates = tuple(
                TermTranslationCandidate(text=text, count=count)
                for text, count in translated_candidates[source].most_common(4)
                if count >= 1
            )
            preferred_target = self._preferred_target(target_candidates)
            chapter_ids = tuple(
                sorted(
                    chapter_id
                    for chapter_id, counter in chapter_counter.items()
                    if counter.get(source, 0) > 0
                )
            )
            entries_by_source[source] = BookTermMemoryEntry(
                source=source,
                occurrences=source_counter[source],
                chapter_ids=chapter_ids,
                aliases=aliases_by_source.get(source, ()),
                preferred_target=preferred_target,
                target_candidates=target_candidates,
            )

        chapter_index: dict[int, tuple[BookTermMemoryEntry, ...]] = {}
        for chapter_id, counter in chapter_counter.items():
            chapter_entries = tuple(
                entries_by_source[source]
                for source, _count in counter.most_common(max_terms_per_chapter * 2)
                if source in entries_by_source
            )
            if chapter_entries:
                chapter_index[int(chapter_id)] = chapter_entries[: max(1, int(max_terms_per_chapter))]

        return BookTermMemorySnapshot(
            entries=tuple(entries_by_source[source] for source in selected_sources if source in entries_by_source),
            chapter_index=chapter_index,
            created_at=_now_iso(),
        )

    @classmethod
    def extract_source_candidates(cls, text: str) -> tuple[str, ...]:
        normalized = str(text or "")
        if not normalized.strip():
            return ()
        ordered_candidates: list[str] = []
        for pattern in (_HONORIFIC_RE, _TITLE_CASE_RE, _ALL_CAPS_RE):
            for match in pattern.finditer(normalized):
                candidate = " ".join(match.group(0).strip().split())
                if not cls._valid_source_candidate(candidate):
                    continue
                if candidate not in ordered_candidates:
                    ordered_candidates.append(candidate)
        return tuple(ordered_candidates)

    @staticmethod
    def _extract_target_candidates(text: str) -> tuple[str, ...]:
        normalized = str(text or "")
        if not normalized.strip():
            return ()
        candidates: list[str] = []
        for match in _CJK_TOKEN_RE.finditer(normalized):
            candidate = match.group(0).strip()
            for variant in BookTermMemoryBuilder._target_variants(candidate):
                if variant in _TARGET_STOPWORDS:
                    continue
                if variant not in candidates:
                    candidates.append(variant)
        return tuple(candidates)

    @staticmethod
    def _target_variants(candidate: str) -> tuple[str, ...]:
        normalized = str(candidate or "").strip()
        if len(normalized) <= 4:
            return (normalized,)
        variants = [normalized]
        max_window = min(4, len(normalized))
        for size in range(2, max_window + 1):
            prefix = normalized[:size]
            suffix = normalized[-size:]
            if prefix not in variants:
                variants.append(prefix)
            if suffix not in variants:
                variants.append(suffix)
        return tuple(variants)

    @staticmethod
    def _valid_source_candidate(candidate: str) -> bool:
        normalized = " ".join(str(candidate or "").strip().split())
        if not normalized or len(normalized) < 3:
            return False
        tokens = normalized.split()
        if any(token in _SOURCE_STOPWORDS for token in tokens):
            return False
        if len(tokens) == 1 and normalized.lower() == normalized:
            return False
        return True

    @staticmethod
    def _preferred_target(
        candidates: tuple[TermTranslationCandidate, ...],
    ) -> str | None:
        if not candidates:
            return None
        top = candidates[0]
        if len(candidates) == 1:
            return top.text
        second = candidates[1]
        if top.count >= max(2, second.count + 1):
            return top.text
        return None

    @staticmethod
    def _build_aliases(sources: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        aliases_by_source: dict[str, list[str]] = defaultdict(list)
        tokenized = {source: tuple(source.split()) for source in sources}
        for source, tokens in tokenized.items():
            if not tokens:
                continue
            last_token = tokens[-1]
            for other_source, other_tokens in tokenized.items():
                if other_source == source or not other_tokens:
                    continue
                if other_tokens[-1] != last_token:
                    continue
                if other_source not in aliases_by_source[source]:
                    aliases_by_source[source].append(other_source)
        return {
            source: tuple(sorted(aliases))
            for source, aliases in aliases_by_source.items()
            if aliases
        }


class BookTermMemoryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, book_id: int, snapshot: BookTermMemorySnapshot) -> Path:
        path = self.snapshot_path(book_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, book_id: int) -> BookTermMemorySnapshot | None:
        path = self.snapshot_path(book_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return BookTermMemorySnapshot.from_dict(payload)

    def snapshot_path(self, book_id: int) -> Path:
        return self.root / str(int(book_id)) / "term_memory.json"
