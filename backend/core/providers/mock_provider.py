from __future__ import annotations

from .base import (
    ChunkTranslationItem,
    ChunkTranslationRequest,
    ChunkTranslationResponse,
    TranslationProvider,
    TranslationRequest,
    TranslationResponse,
)


class MockTranslationProvider(TranslationProvider):
    default_model_name = "mock-v1"

    @property
    def name(self) -> str:
        return "mock"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        prefix = str(self.options.get("prefix", "ZH: "))
        translated_lines = [
            f"{prefix}{line}" if line else line
            for line in request.text.split("\n")
        ]
        return TranslationResponse(
            translated_text="\n".join(translated_lines),
            provider_name=self.name,
            model_name=self.model_name,
        )

    def translate_chunk(
        self,
        request: ChunkTranslationRequest,
    ) -> ChunkTranslationResponse:
        prefix = str(self.options.get("prefix", "ZH: "))
        items = []
        for segment in request.segments:
            translated_lines = [
                f"{prefix}{line}" if line else line
                for line in segment.source_text.split("\n")
            ]
            items.append(
                ChunkTranslationItem(
                    segment_id=segment.segment_id,
                    translated_text="\n".join(translated_lines),
                )
            )
        return ChunkTranslationResponse(
            items=tuple(items),
            provider_name=self.name,
            model_name=self.model_name,
        )
