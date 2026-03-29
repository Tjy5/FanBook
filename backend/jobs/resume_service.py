from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.domain.enums import SegmentStatus, TranslationJobStatus
from backend.jobs.runner import (
    BackgroundTranslationHandle,
    BackgroundTranslationRequest,
    ThreadedTranslationJobRunner,
)
from backend.storage.checkpoint_store import CheckpointStore, JobCheckpointSnapshot
from backend.storage.database import FanbookDatabase


@dataclass(slots=True, frozen=True)
class ResumeState:
    book_id: int
    job_id: int | None
    status: str | None
    can_resume: bool
    translated_segments: int
    total_segments: int
    failed_segments: int
    remaining_segments: int
    checkpoint: JobCheckpointSnapshot | None
    provider_profile_name: str | None
    provider_name: str | None
    model_name: str | None
    error_summary: str | None


class TranslationResumeService:
    def __init__(
        self,
        database: FanbookDatabase,
        checkpoint_store: CheckpointStore,
    ) -> None:
        self.database = database
        self.checkpoint_store = checkpoint_store

    def inspect(self, book_id: int, *, runner: ThreadedTranslationJobRunner | None = None) -> ResumeState:
        normalized_book_id = int(book_id)
        latest_job = self.database.get_latest_translation_job(normalized_book_id)
        translated_segments = self._count_segments(
            normalized_book_id,
            predicate=lambda status, text: (
                status is SegmentStatus.TRANSLATED and bool((text or "").strip())
            ),
        )
        failed_segments = self._count_segments(
            normalized_book_id,
            predicate=lambda status, _text: status is SegmentStatus.FAILED,
        )
        total_segments = self.database.count_book_segments(normalized_book_id)
        remaining_segments = max(0, total_segments - translated_segments)
        checkpoint = (
            self.checkpoint_store.load(latest_job.id)
            if latest_job is not None
            else None
        )
        latest_status = latest_job.status.value if latest_job is not None else None
        is_runner_active = (
            runner.has_active_job(normalized_book_id)
            if runner is not None
            else False
        )
        can_resume = (
            total_segments > 0
            and remaining_segments > 0
            and not is_runner_active
            and latest_status != TranslationJobStatus.COMPLETED.value
        )
        return ResumeState(
            book_id=normalized_book_id,
            job_id=latest_job.id if latest_job is not None else None,
            status=latest_status,
            can_resume=can_resume,
            translated_segments=translated_segments,
            total_segments=total_segments,
            failed_segments=failed_segments,
            remaining_segments=remaining_segments,
            checkpoint=checkpoint,
            provider_profile_name=(
                latest_job.provider_profile_name
                if latest_job is not None
                else (checkpoint.provider_profile_name if checkpoint is not None else None)
            ),
            provider_name=(
                latest_job.provider_name
                if latest_job is not None
                else (checkpoint.provider_name if checkpoint is not None else None)
            ),
            model_name=(
                latest_job.model_name
                if latest_job is not None
                else (checkpoint.model_name if checkpoint is not None else None)
            ),
            error_summary=(
                latest_job.error_summary
                if latest_job is not None
                else (checkpoint.error_summary if checkpoint is not None else None)
            ),
        )

    def resume(
        self,
        book_id: int,
        *,
        runner: ThreadedTranslationJobRunner,
        provider_profile_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        provider_options: dict[str, object] | None = None,
    ) -> BackgroundTranslationHandle:
        normalized_book_id = int(book_id)
        if runner.has_active_job(normalized_book_id):
            return runner.start(
                BackgroundTranslationRequest(
                    book_id=normalized_book_id,
                    provider_profile_name=provider_profile_name,
                    provider_name=provider_name or "mock",
                    model_name=model_name,
                    provider_options=provider_options,
                )
            )

        state = self.inspect(normalized_book_id, runner=runner)
        if not state.can_resume:
            raise ValueError(f"Book '{normalized_book_id}' does not have resumable work.")

        effective_provider_profile_name = (
            provider_profile_name or state.provider_profile_name
        )
        effective_provider_name = provider_name or state.provider_name or "mock"
        effective_model_name = model_name or state.model_name
        return runner.start(
            BackgroundTranslationRequest(
                book_id=normalized_book_id,
                provider_profile_name=effective_provider_profile_name,
                provider_name=effective_provider_name,
                model_name=effective_model_name,
                provider_options=provider_options,
            )
        )

    def recover_pending_jobs(
        self,
        *,
        runner: ThreadedTranslationJobRunner,
    ) -> list[BackgroundTranslationHandle]:
        handles: list[BackgroundTranslationHandle] = []
        for job_id in self.checkpoint_store.list_job_ids():
            checkpoint = self.checkpoint_store.load(job_id)
            if checkpoint is None:
                continue
            if checkpoint.finished_at is not None:
                continue
            state = self.inspect(checkpoint.book_id, runner=runner)
            if not state.can_resume:
                continue
            handles.append(
                self.resume(
                    checkpoint.book_id,
                    runner=runner,
                    provider_profile_name=checkpoint.provider_profile_name,
                    provider_name=checkpoint.provider_name,
                    model_name=checkpoint.model_name,
                )
            )
        return handles

    def _count_segments(
        self,
        book_id: int,
        *,
        predicate: Callable[[object, str | None], bool],
    ) -> int:
        if book_id <= 0:
            return 0
        return sum(
            1
            for segment in self.database.list_book_segments(book_id)
            if predicate(segment.status, segment.translated_text)
        )
