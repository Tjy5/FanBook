from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GlossaryEntry:
    source: str
    target: str


class GlossaryStore:
    def __init__(self, entries: tuple[GlossaryEntry, ...] = ()) -> None:
        self.entries = entries

    @classmethod
    def from_text(cls, raw_text: str | None) -> "GlossaryStore":
        if not raw_text:
            return cls(())

        entries: list[GlossaryEntry] = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            for separator in ("=>", "->", "=", "\t"):
                if separator not in line:
                    continue
                source, target = line.split(separator, 1)
                source = source.strip()
                target = target.strip()
                if source and target:
                    entries.append(GlossaryEntry(source=source, target=target))
                break
        return cls(tuple(entries))

    def render_prompt_block(self) -> str:
        if not self.entries:
            return ""
        return "\n".join(
            f"- {entry.source} => {entry.target}"
            for entry in self.entries
        )
