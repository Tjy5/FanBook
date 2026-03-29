from __future__ import annotations

from backend.domain.enums import TranslationJobStatus
from backend.domain.models import TranslationJob
from backend.storage.database import FanbookDatabase


class TranslationJobStateManager:
    def __init__(self, database: FanbookDatabase) -> None:
        self.database = database

    def ensure_runnable_job(self, book_id: int) -> TranslationJob:
        latest_job = self.database.get_latest_translation_job(book_id)
        if latest_job is None or latest_job.status in {
            TranslationJobStatus.COMPLETED,
            TranslationJobStatus.FAILED,
            TranslationJobStatus.CANCELED,
        }:
            return self.database.create_translation_job(
                TranslationJob(book_id=book_id, status=TranslationJobStatus.PENDING)
            )
        return latest_job

    def mark_running(
        self,
        job: TranslationJob,
        *,
        provider_profile_name: str | None,
        provider_name: str,
        model_name: str,
        completed_segments: int,
        total_segments: int,
    ) -> TranslationJob:
        job.status = TranslationJobStatus.RUNNING
        job.provider_profile_name = provider_profile_name
        job.provider_name = provider_name
        job.model_name = model_name
        job.progress = self._progress(completed_segments, total_segments)
        job.resume_from = completed_segments
        job.error_summary = None
        return self.database.update_translation_job(job)

    def mark_progress(
        self,
        job: TranslationJob,
        *,
        completed_segments: int,
        total_segments: int,
    ) -> TranslationJob:
        job.status = TranslationJobStatus.RUNNING
        job.progress = self._progress(completed_segments, total_segments)
        job.resume_from = completed_segments
        return self.database.update_translation_job(job)

    def mark_completed(
        self,
        job: TranslationJob,
        *,
        completed_segments: int,
        total_segments: int,
    ) -> TranslationJob:
        job.status = TranslationJobStatus.COMPLETED
        job.progress = self._progress(completed_segments, total_segments)
        job.resume_from = completed_segments
        job.error_summary = None
        return self.database.update_translation_job(job)

    def mark_failed(
        self,
        job: TranslationJob,
        *,
        error_summary: str,
        completed_segments: int,
        total_segments: int,
    ) -> TranslationJob:
        job.status = TranslationJobStatus.FAILED
        job.progress = self._progress(completed_segments, total_segments)
        job.resume_from = completed_segments
        job.error_summary = error_summary
        return self.database.update_translation_job(job)

    def mark_canceled(
        self,
        job: TranslationJob,
        *,
        error_summary: str | None = None,
        completed_segments: int,
        total_segments: int,
    ) -> TranslationJob:
        job.status = TranslationJobStatus.CANCELED
        job.progress = self._progress(completed_segments, total_segments)
        job.resume_from = completed_segments
        job.error_summary = error_summary
        return self.database.update_translation_job(job)

    @staticmethod
    def _progress(completed_segments: int, total_segments: int) -> float:
        if total_segments <= 0:
            return 1.0
        return max(0.0, min(1.0, completed_segments / total_segments))
