from __future__ import annotations

from backend.api.schemas.book import BookDetailResponse, BookResponse, ChapterProgressResponse, CreateBookRequest, CreateBookResponse, ExportArtifactResponse, RouteResult, TranslationJobResponse
from backend.services.book_service import BookNotFoundError, BookService, InvalidBookUploadError


class BookRoutes:
    def __init__(self, book_service: BookService) -> None:
        self.book_service = book_service

    def create_book(self, request: CreateBookRequest) -> RouteResult[CreateBookResponse]:
        try:
            created = self.book_service.create_book(
                filename=request.filename,
                content=request.content,
                title=request.title,
                source_language=request.source_language,
            )
        except InvalidBookUploadError as exc:
            return RouteResult.fail(400, "invalid_upload", str(exc))
        except Exception:
            return RouteResult.fail(500, "internal_error", "Failed to create book.")

        return RouteResult.ok(
            201,
            CreateBookResponse(
                book_id=created.book.id,
                job_id=created.job.id,
                status=created.job.status.value,
            ),
        )

    def get_book(self, book_id: int) -> RouteResult[BookDetailResponse]:
        try:
            detail = self.book_service.get_book(int(book_id))
        except ValueError:
            return RouteResult.fail(400, "invalid_book_id", "Book id must be an integer.")
        except BookNotFoundError as exc:
            return RouteResult.fail(404, "book_not_found", str(exc))
        except Exception:
            return RouteResult.fail(500, "internal_error", "Failed to load book.")

        return RouteResult.ok(
            200,
            BookDetailResponse(
                book=BookResponse.from_book(detail.book),
                current_job=(TranslationJobResponse.from_job(detail.current_job) if detail.current_job is not None else None),
                chapters=tuple(ChapterProgressResponse.from_progress(progress) for progress in detail.chapter_progress),
                artifacts=tuple(ExportArtifactResponse.from_artifact(artifact) for artifact in detail.artifacts),
            ),
        )
