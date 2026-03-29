from __future__ import annotations

import math
from typing import Iterable

from .runtime_settings import TranslationRuntimeSettings

try:  # pragma: no cover - optional dependency
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    tiktoken = None


class TokenBudgetEstimator:
    def __init__(
        self,
        *,
        settings: TranslationRuntimeSettings,
        model_name: str | None = None,
    ) -> None:
        self.settings = settings.normalized()
        self.model_name = model_name or ""
        self._encoder = self._build_encoder(self.model_name)

    def estimate_text_tokens(self, text: str) -> int:
        normalized = text or ""
        if normalized == "":
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(normalized))
            except Exception:  # pragma: no cover - defensive fallback
                pass
        return max(1, math.ceil(len(normalized) / 4))

    def estimate_collection_tokens(self, texts: Iterable[str]) -> int:
        return sum(self.estimate_text_tokens(text) for text in texts)

    def chunk_fits(
        self,
        *,
        segment_texts: Iterable[str],
        prompt_overhead_tokens: int = 0,
        structured_output_tokens: int = 0,
    ) -> bool:
        estimated_input = (
            self.estimate_collection_tokens(segment_texts)
            + int(prompt_overhead_tokens)
            + int(structured_output_tokens)
        )
        return estimated_input <= self.settings.max_input_tokens

    def fits_single_segment(
        self,
        text: str,
        *,
        prompt_overhead_tokens: int = 0,
        structured_output_tokens: int = 0,
    ) -> bool:
        return self.chunk_fits(
            segment_texts=(text,),
            prompt_overhead_tokens=prompt_overhead_tokens,
            structured_output_tokens=structured_output_tokens,
        )

    def target_chunk_budget(self) -> int:
        return min(
            self.settings.chunk_target_tokens,
            max(64, self.settings.max_input_tokens - self.settings.reserved_output_tokens),
        )

    def split_text_for_segment(self, text: str) -> tuple[str, ...]:
        if self.fits_single_segment(text):
            return (text,)

        pieces: list[str] = []
        for line in text.split("\n"):
            if line == "":
                pieces.append(line)
                continue
            if self.fits_single_segment(line):
                pieces.append(line)
                continue
            pieces.extend(self._split_line(line))
        return tuple(piece for piece in pieces if piece != "") or (text,)

    def _split_line(self, line: str) -> list[str]:
        sentence_boundaries = ".!?;:。！？；："
        parts: list[str] = []
        current = ""
        for char in line:
            current += char
            if char in sentence_boundaries and self.fits_single_segment(current):
                parts.append(current)
                current = ""
        if current:
            if self.fits_single_segment(current):
                parts.append(current)
            else:
                parts.extend(self._split_hard(current))
        return parts or [line]

    def _split_hard(self, line: str) -> list[str]:
        max_chars = max(40, self.target_chunk_budget() * 4)
        return [line[index:index + max_chars] for index in range(0, len(line), max_chars)]

    @staticmethod
    def _build_encoder(model_name: str):
        if tiktoken is None:
            return None
        try:  # pragma: no cover - optional dependency path
            if model_name:
                return tiktoken.encoding_for_model(model_name)
        except Exception:
            pass
        try:  # pragma: no cover - optional dependency path
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None
