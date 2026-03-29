from __future__ import annotations

from typing import Any

from .base import TranslationProvider, UnsupportedTranslationProviderError
from .mock_provider import MockTranslationProvider
from .openai_provider import OpenAITranslationProvider


class TranslationProviderFactory:
    def __init__(
        self,
        providers: dict[str, type[TranslationProvider]] | None = None,
    ) -> None:
        self._providers = {
            name.strip().lower(): provider
            for name, provider in (
                providers
                or {
                    "mock": MockTranslationProvider,
                    "openai": OpenAITranslationProvider,
                }
            ).items()
        }

    def available_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def create(
        self,
        provider_name: str,
        *,
        model_name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> TranslationProvider:
        normalized = provider_name.strip().lower()
        provider_cls = self._providers.get(normalized)
        if provider_cls is None:
            raise UnsupportedTranslationProviderError(
                f"Provider '{provider_name}' is not supported."
            )
        return provider_cls(model_name=model_name, options=options)
