from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import threading
from typing import Any, Protocol

from backend.domain.enums import SegmentStatus, TranslationJobStatus
from backend.domain.models import TranslationJob
from backend.jobs.state_manager import TranslationJobStateManager
from backend.storage.checkpoint_store import CheckpointStore, JobCheckpointSnapshot
from backend.storage.database import FanbookDatabase


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SupportsTranslationStart(Protocol):
    def start_translation(
        self,
        book_id: int,
        *,
        provider_profile_name: str | None = None,
        provider_name: str = "mock",
        model_name: str | None = None,
        provider_options: dict[str, object] | None = None,
    ) -> object:
        ...


@dataclass(slots=True, frozen=True)
class BackgroundTranslationRequest:
    book_id: int
    provider_profile_name: str | None = None
    provider_name: str = "mock"
    model_name: str | None = None
    provider_options: dict[str, object] | None = None


@dataclass(slots=True)
class BackgroundTranslationHandle:
    job_id: int
    book_id: int
    provider_profile_name: str | None
    provider_name: str
    model_name: str | None
    status: str
    started_at: str
    thread_name: str


@dataclass(slots=True, frozen=True)
class BackgroundTranslationSnapshot:
    job: TranslationJob | None
    checkpoint: JobCheckpointSnapshot | None
    is_active: bool
    translated_segments: int
    total_segments: int
    failed_segments: int


class ThreadedTranslationJobRunner:
    def __init__(
        self,
        *,
        database: FanbookDatabase,
        translation_service: SupportsTranslationStart,
        checkpoint_store: CheckpointStore,
        state_manager: TranslationJobStateManager | None = None,
        heartbeat_interval: float = 0.25,
    ) -> None:
        self.database = database
        self.translation_service = translation_service
        self.checkpoint_store = checkpoint_store
        self.state_manager = state_manager or TranslationJobStateManager(database)
        self.heartbeat_interval = max(0.05, float(heartbeat_interval))
        self._lock = threading.RLock()
        self._threads: dict[int, threading.Thread] = {}
        self._active_job_by_book: dict[int, int] = {}

    def start(self, request: BackgroundTranslationRequest) -> BackgroundTranslationHandle:
        with self._lock:
            active_job_id = self._active_job_by_book.get(request.book_id)
            active_thread = self._threads.get(active_job_id or -1)
            active_job = (
                self.database.get_translation_job(active_job_id)
                if active_job_id is not None
                else None
            )
            if (
                active_job_id is not None
                and active_thread is not None
                and active_thread.is_alive()
                and not self._is_terminal_job(active_job)
            ):
                return BackgroundTranslationHandle(
                    job_id=active_job_id,
                    book_id=request.book_id,
                    provider_profile_name=(
                        active_job.provider_profile_name
                        if active_job is not None and active_job.provider_profile_name
                        else request.provider_profile_name
                    ),
                    provider_name=(
                        active_job.provider_name
                        if active_job is not None and active_job.provider_name
                        else request.provider_name
                    ),
                    model_name=(
                        active_job.model_name if active_job is not None else request.model_name
                    ),
                    status=(
                        active_job.status.value
                        if active_job is not None
                        else TranslationJobStatus.RUNNING.value
                    ),
                    started_at=(
                        active_job.updated_at if active_job is not None else _now_iso()
                    ),
                    thread_name=active_thread.name,
                )

            job = self.state_manager.ensure_runnable_job(request.book_id)
            started_at = _now_iso()
            thread = threading.Thread(
                target=self._run_translation,
                args=(job.id, request),
                daemon=True,
                name=f"fanbook-job-{job.id}",
            )
            self._threads[job.id] = thread
            self._active_job_by_book[request.book_id] = job.id
            self.checkpoint_store.save_state(
                job_id=job.id,
                book_id=request.book_id,
                status=job.status.value,
                provider_profile_name=request.provider_profile_name,
                provider_name=request.provider_name,
                model_name=request.model_name,
                progress=job.progress,
                translated_segments=self._count_translated_segments(request.book_id),
                total_segments=self.database.count_book_segments(request.book_id),
                checkpoint_reason="queued",
                thread_name=thread.name,
            )
            thread.start()
            return BackgroundTranslationHandle(
                job_id=job.id,
                book_id=request.book_id,
                provider_profile_name=request.provider_profile_name,
                provider_name=request.provider_name,
                model_name=request.model_name,
                status=job.status.value,
                started_at=started_at,
                thread_name=thread.name,
            )

    def get_snapshot(self, job_id: int) -> BackgroundTranslationSnapshot:
        job = self.database.get_translation_job(int(job_id))
        checkpoint = self.checkpoint_store.load(int(job_id))
        thread = self._threads.get(int(job_id))
        book_id = job.book_id if job is not None else (checkpoint.book_id if checkpoint else 0)
        return BackgroundTranslationSnapshot(
            job=job,
            checkpoint=checkpoint,
            is_active=bool(thread is not None and thread.is_alive()),
            translated_segments=self._count_translated_segments(book_id),
            total_segments=self.database.count_book_segments(book_id) if book_id > 0 else 0,
            failed_segments=self._count_failed_segments(book_id),
        )

    def get_book_snapshot(self, book_id: int) -> BackgroundTranslationSnapshot | None:
        latest_job = self.database.get_latest_translation_job(int(book_id))
        if latest_job is None:
            return None
        return self.get_snapshot(latest_job.id)

    def has_active_job(self, book_id: int) -> bool:
        with self._lock:
            active_job_id = self._active_job_by_book.get(int(book_id))
            thread = self._threads.get(active_job_id or -1)
            active_job = (
                self.database.get_translation_job(active_job_id)
                if active_job_id is not None
                else None
            )
            return bool(
                active_job_id is not None
                and thread is not None
                and thread.is_alive()
                and not self._is_terminal_job(active_job)
            )

    def wait(self, job_id: int, timeout: float | None = None) -> bool:
        thread = self._threads.get(int(job_id))
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run_translation(self, job_id: int, request: BackgroundTranslationRequest) -> None:
        monitor_stop = threading.Event()
        monitor = threading.Thread(
            target=self._monitor_job,
            args=(
                job_id,
                request.book_id,
                request.provider_profile_name,
                request.provider_name,
                request.model_name,
                monitor_stop,
            ),
            daemon=True,
            name=f"fanbook-job-monitor-{job_id}",
        )
        monitor.start()

        final_state: dict[str, Any] | None = None
        try:
            self.translation_service.start_translation(
                request.book_id,
                provider_profile_name=request.provider_profile_name,
                provider_name=request.provider_name,
                model_name=request.model_name,
                provider_options=request.provider_options,
            )
            job = self.database.get_translation_job(job_id)
            translated_segments = self._count_translated_segments(request.book_id)
            total_segments = self.database.count_book_segments(request.book_id)
            if job is None:
                final_state = {
                    "job_id": job_id,
                    "book_id": request.book_id,
                    "status": TranslationJobStatus.COMPLETED.value,
                    "provider_profile_name": request.provider_profile_name,
                    "provider_name": request.provider_name,
                    "model_name": request.model_name,
                    "progress": 1.0 if total_segments > 0 else 0.0,
                    "translated_segments": translated_segments,
                    "total_segments": total_segments,
                    "checkpoint_reason": "completed",
                }
            else:
                final_state = {
                    "job_id": job.id,
                    "book_id": job.book_id,
                    "status": job.status.value,
                    "provider_profile_name": job.provider_profile_name,
                    "provider_name": job.provider_name,
                    "model_name": job.model_name,
                    "progress": job.progress,
                    "translated_segments": translated_segments,
                    "total_segments": total_segments,
                    "checkpoint_reason": "completed",
                }
        except Exception as exc:
            latest_job = self.database.get_latest_translation_job(request.book_id)
            if latest_job is None:
                final_state = {
                    "job_id": job_id,
                    "book_id": request.book_id,
                    "status": TranslationJobStatus.FAILED.value,
                    "provider_profile_name": request.provider_profile_name,
                    "provider_name": request.provider_name,
                    "model_name": request.model_name,
                    "progress": 0.0,
                    "translated_segments": self._count_translated_segments(request.book_id),
                    "total_segments": self.database.count_book_segments(request.book_id),
                    "error_summary": str(exc),
                    "checkpoint_reason": "failed",
                }
            else:
                final_state = {
                    "job_id": latest_job.id,
                    "book_id": latest_job.book_id,
                    "status": latest_job.status.value,
                    "provider_profile_name": latest_job.provider_profile_name,
                    "provider_name": latest_job.provider_name,
                    "model_name": latest_job.model_name,
                    "progress": latest_job.progress,
                    "translated_segments": self._count_translated_segments(request.book_id),
                    "total_segments": self.database.count_book_segments(request.book_id),
                    "error_summary": latest_job.error_summary or str(exc),
                    "checkpoint_reason": "failed",
                }
        finally:
            monitor_stop.set()
            monitor.join(timeout=self.heartbeat_interval * 2)
            if final_state is not None:
                self.checkpoint_store.save_state(
                    **final_state,
                    thread_name=threading.current_thread().name,
                    finished_at=_now_iso(),
                )
            with self._lock:
                if self._active_job_by_book.get(request.book_id) == job_id:
                    self._active_job_by_book.pop(request.book_id, None)

    def _monitor_job(
        self,
        job_id: int,
        book_id: int,
        provider_profile_name: str | None,
        provider_name: str,
        model_name: str | None,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.wait(self.heartbeat_interval):
            job = self.database.get_translation_job(job_id)
            translated_segments = self._count_translated_segments(book_id)
            total_segments = self.database.count_book_segments(book_id)
            if job is None:
                status = TranslationJobStatus.RUNNING.value
                progress = translated_segments / total_segments if total_segments > 0 else 0.0
                effective_provider_profile_name = provider_profile_name
                effective_provider_name = provider_name
                effective_model_name = model_name
                error_summary = None
            else:
                status = job.status.value
                progress = job.progress
                effective_provider_profile_name = (
                    job.provider_profile_name or provider_profile_name
                )
                effective_provider_name = job.provider_name or provider_name
                effective_model_name = job.model_name or model_name
                error_summary = job.error_summary

            self.checkpoint_store.save_state(
                job_id=job_id,
                book_id=book_id,
                status=status,
                provider_profile_name=effective_provider_profile_name,
                provider_name=effective_provider_name,
                model_name=effective_model_name,
                progress=progress,
                translated_segments=translated_segments,
                total_segments=total_segments,
                error_summary=error_summary,
                checkpoint_reason="heartbeat",
                thread_name=threading.current_thread().name,
            )

    def _count_translated_segments(self, book_id: int) -> int:
        if book_id <= 0:
            return 0
        return sum(
            1
            for segment in self.database.list_book_segments(book_id)
            if segment.status is SegmentStatus.TRANSLATED
            and (segment.translated_text or "").strip()
        )

    def _count_failed_segments(self, book_id: int) -> int:
        if book_id <= 0:
            return 0
        return sum(
            1
            for segment in self.database.list_book_segments(book_id)
            if segment.status is SegmentStatus.FAILED
        )

    @staticmethod
    def _is_terminal_job(job: TranslationJob | None) -> bool:
        if job is None:
            return False
        return job.status in {
            TranslationJobStatus.COMPLETED,
            TranslationJobStatus.FAILED,
            TranslationJobStatus.CANCELED,
        }
