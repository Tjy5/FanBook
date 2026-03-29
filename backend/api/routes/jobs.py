from __future__ import annotations

from backend.api.schemas.book import RouteResult
from backend.api.schemas.job import StartTranslationRequest, StartTranslationResponse
from backend.core.providers.base import UnsupportedTranslationProviderError
from backend.services.translation_service import (
    TranslationBookNotFoundError,
    TranslationExecutionError,
    TranslationService,
)


class TranslationRoutes:
    def __init__(self, translation_service: TranslationService) -> None:
        self.translation_service = translation_service

    def translate_book(
        self,
        book_id: int,
        request: StartTranslationRequest | None = None,
    ) -> RouteResult[StartTranslationResponse]:
        payload = request or StartTranslationRequest()
        try:
            run = self.translation_service.start_translation(
                int(book_id),
                provider_name=payload.provider.provider_name,
                model_name=payload.provider.model_name,
                provider_options=payload.provider.options_dict(),
            )
        except ValueError:
            return RouteResult.fail(400, "invalid_book_id", "Book id must be an integer.")
        except UnsupportedTranslationProviderError as exc:
            return RouteResult.fail(400, "invalid_provider", str(exc))
        except TranslationBookNotFoundError as exc:
            return RouteResult.fail(404, "book_not_found", str(exc))
        except TranslationExecutionError as exc:
            return RouteResult.fail(500, "translation_failed", str(exc))
        except Exception:
            return RouteResult.fail(500, "internal_error", "Failed to translate book.")

        return RouteResult.ok(
            200,
            StartTranslationResponse(
                book_id=run.job.book_id,
                job_id=run.job.id,
                status=run.job.status.value,
                provider_name=run.job.provider_name,
                model_name=run.job.model_name,
                progress=run.job.progress,
                translated_segments=run.translated_segments,
                total_segments=run.total_segments,
            ),
        )
