from __future__ import annotations

from dataclasses import dataclass, field

from .provider import ProviderConfigRequest


@dataclass(slots=True)
class StartTranslationRequest:
    provider: ProviderConfigRequest = field(default_factory=ProviderConfigRequest)


@dataclass(slots=True)
class StartTranslationResponse:
    book_id: int
    job_id: int
    status: str
    provider_name: str | None
    model_name: str | None
    progress: float
    translated_segments: int
    total_segments: int
