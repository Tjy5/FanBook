from __future__ import annotations

import json
from dataclasses import dataclass

from backend.core.providers.base import (
    SegmentContext,
    TranslationRequest,
    TranslationProviderError,
    UnsupportedTranslationProviderError,
)
from backend.core.providers.factory import TranslationProviderFactory
from backend.core.quality.book_glossary import BookGlossaryBuilder
from backend.core.quality.book_term_memory import (
    BookTermMemoryBuilder,
    BookTermMemorySnapshot,
    BookTermMemoryStore,
)
from backend.core.quality.consistency_report import ConsistencyReportGenerator
from backend.core.quality.glossary_store import GlossaryStore
from backend.core.translation.error_codes import classify_chunk_issue
from backend.core.translation.metrics import TranslationRunMetrics
from backend.core.translation.orchestrator import (
    ChapterTranslationBatch,
    TranslatedSegmentResult,
    TranslationOrchestrator,
)
from backend.core.translation.runtime_settings import (
    RUNTIME_OPTION_SOURCE_METADATA_KEY,
    RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION,
    TranslationRuntimeSettings,
)
from backend.domain.enums import (
    ExportArtifactKind,
    ExportArtifactStatus,
    SegmentStatus,
    SegmentType,
)
from backend.domain.models import (
    Book,
    Chapter,
    ExportArtifact,
    Segment,
    SegmentExtra,
    TranslationJob,
)
from backend.jobs.state_manager import TranslationJobStateManager
from backend.storage.artifact_store import ArtifactStore
from backend.storage.checkpoint_store import CheckpointStore
from backend.storage.database import FanbookDatabase
from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore

_ENDPOINT_CAPABILITY_CACHE_ROOT_OPTION = "_fanbook_endpoint_capability_cache_root"


class TranslationServiceError(Exception):
    pass


class TranslationBookNotFoundError(TranslationServiceError):
    pass


class TranslationExecutionError(TranslationServiceError):
    pass


@dataclass(slots=True)
class TranslationRun:
    job: TranslationJob
    total_segments: int
    translated_segments: int
    runtime_settings: TranslationRuntimeSettings
    metrics: TranslationRunMetrics


class TranslationService:
    def __init__(
        self,
        database: FanbookDatabase,
        *,
        provider_factory: TranslationProviderFactory | None = None,
        orchestrator: TranslationOrchestrator | None = None,
        state_manager: TranslationJobStateManager | None = None,
        checkpoint_store: CheckpointStore | None = None,
        artifact_store: ArtifactStore | None = None,
        glossary_builder: BookGlossaryBuilder | None = None,
        term_memory_builder: BookTermMemoryBuilder | None = None,
        consistency_report_generator: ConsistencyReportGenerator | None = None,
    ) -> None:
        self.database = database
        self.provider_factory = provider_factory or TranslationProviderFactory()
        self.orchestrator = orchestrator or TranslationOrchestrator()
        self.state_manager = state_manager or TranslationJobStateManager(database)
        self.checkpoint_store = checkpoint_store
        self.artifact_store = artifact_store
        self.glossary_builder = glossary_builder or BookGlossaryBuilder()
        self.term_memory_builder = term_memory_builder or BookTermMemoryBuilder()
        self.consistency_report_generator = (
            consistency_report_generator or ConsistencyReportGenerator()
        )

    def start_translation(
        self,
        book_id: int,
        *,
        provider_profile_name: str | None = None,
        provider_name: str = "mock",
        model_name: str | None = None,
        provider_options: dict[str, object] | None = None,
    ) -> TranslationRun:
        normalized_provider_options = dict(provider_options or {})
        capability_cache_root = self._endpoint_capability_cache_root()
        if capability_cache_root is not None:
            normalized_provider_options.setdefault(
                _ENDPOINT_CAPABILITY_CACHE_ROOT_OPTION,
                str(capability_cache_root),
            )
        runtime_profile_override_root = self._runtime_profile_override_store_root()
        if runtime_profile_override_root is not None:
            normalized_provider_options.setdefault(
                RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION,
                str(runtime_profile_override_root),
            )
        book = self.database.get_book(int(book_id))
        if book is None:
            raise TranslationBookNotFoundError(f"Book '{book_id}' was not found.")

        chapters = self._load_chapters(book.id)
        total_segments = self._count_translatable_segments(chapters)
        translated_segments = self._count_completed_segments(chapters)

        job = self.state_manager.ensure_runnable_job(book.id)
        if self.checkpoint_store is not None:
            self.checkpoint_store.clear_chunks(job.id)

        try:
            provider = self.provider_factory.create(
                provider_name,
                model_name=model_name,
                options=normalized_provider_options,
            )
        except UnsupportedTranslationProviderError:
            raise
        except TranslationProviderError as exc:
            raise TranslationExecutionError(str(exc)) from exc

        try:
            capability_detection = provider.detect_runtime_capabilities()
            effective_provider_options = _merge_detected_runtime_options(
                normalized_provider_options,
                capability_detection.options,
                capability_detection.option_sources,
            )
            provider.update_options(effective_provider_options)
            runtime_settings = TranslationRuntimeSettings.from_options(
                effective_provider_options,
                provider_name=provider.name,
                model_name=provider.model_name,
            )
            self._persist_runtime_profile_override(
                provider_name=provider.name,
                model_name=provider.model_name,
                provider_options=effective_provider_options,
                runtime_settings=runtime_settings,
                capability_detection=capability_detection,
            )
            runtime_settings_payload = runtime_settings.to_dict()
            runtime_target = _build_runtime_target_metadata(
                provider_name=provider.name,
                model_name=provider.model_name,
                provider_options=effective_provider_options,
            )
            if runtime_target:
                runtime_settings_payload["runtime_target"] = runtime_target
            if capability_detection.metadata:
                runtime_settings_payload["endpoint_capability_detection"] = dict(
                    capability_detection.metadata
                )
            metrics = TranslationRunMetrics(runtime_settings=runtime_settings)
            chunk_fallback_counts: dict[str, int] = {}
            chunk_fallback_reasons: dict[str, str] = {}
            glossary_store = GlossaryStore.from_text(
                str(effective_provider_options.get("glossary", "")) or None
            )
            glossary_snapshot = self.glossary_builder.build(
                chapters=chapters,
                user_glossary=glossary_store,
            )
            initial_term_memory_snapshot = self.term_memory_builder.build(chapters=chapters)
            self._save_term_memory(book.id, initial_term_memory_snapshot)

            job = self.state_manager.mark_running(
                job,
                provider_profile_name=provider_profile_name,
                provider_name=provider.name,
                model_name=provider.model_name,
                completed_segments=translated_segments,
                total_segments=total_segments,
            )
            if self.checkpoint_store is not None:
                self.checkpoint_store.save_state(
                    job_id=job.id,
                    book_id=book.id,
                    status=job.status.value,
                    provider_profile_name=provider_profile_name,
                    provider_name=provider.name,
                    model_name=provider.model_name,
                    progress=job.progress,
                    translated_segments=translated_segments,
                    total_segments=total_segments,
                    runtime_settings=runtime_settings_payload,
                    checkpoint_reason="translation_started",
                )

            if total_segments == translated_segments:
                book = self._ensure_translated_book_title(
                    book=book,
                    chapters=chapters,
                    provider=provider,
                    runtime_settings=runtime_settings,
                )
                metrics.export_success = True
                metrics.mark_finished()
                self._save_consistency_outputs(
                    book=book,
                    job=job,
                    chapters=chapters,
                    runtime_settings=runtime_settings,
                    metrics=metrics,
                    term_memory_snapshot=initial_term_memory_snapshot,
                )
                self._ensure_export_artifacts(book.id)
                job = self.state_manager.mark_completed(
                    job,
                    completed_segments=translated_segments,
                    total_segments=total_segments,
                )
                return TranslationRun(
                    job=job,
                    total_segments=total_segments,
                    translated_segments=translated_segments,
                    runtime_settings=runtime_settings,
                    metrics=metrics,
                )

            try:
                def on_passthrough_segment(segment: Segment) -> None:
                    nonlocal translated_segments, job
                    if segment.status is SegmentStatus.TRANSLATED and (segment.translated_text or "").strip():
                        return
                    segment.translated_text = segment.source_text
                    segment.status = SegmentStatus.TRANSLATED
                    self.database.upsert_segment(segment)
                    metrics.note_segment_skipped(segment)
                    translated_segments += 1
                    job = self.state_manager.mark_progress(
                        job,
                        completed_segments=translated_segments,
                        total_segments=total_segments,
                    )

                def on_chunk_status(chunk, status: str, attempt_count: int, error_summary: str | None) -> None:
                    if status == "running":
                        metrics.note_chunk_started(chunk)
                    elif status == "failed":
                        metrics.note_chunk_failed(chunk, error_summary)
                    if self.checkpoint_store is None:
                        return
                    self.checkpoint_store.save_chunk_state(
                        job_id=job.id,
                        chunk_id=chunk.chunk_id,
                        book_id=book.id,
                        chapter_id=chunk.chapter_id,
                        segment_ids=chunk.segment_ids,
                        sequence_no=chunk.sequence_no,
                        status=status,
                        attempt_count=attempt_count,
                        provider_name=provider.name,
                        model_name=provider.model_name,
                        term_snapshot_version="glossary-v1",
                        last_error=error_summary,
                        failure_reason_code=(
                            classify_chunk_issue(error_summary)
                            if status == "failed"
                            else None
                        ),
                        fallback_reason_code=chunk_fallback_reasons.get(chunk.chunk_id),
                        segment_count=len(chunk.segments),
                        source_char_count=sum(len(segment.source_text) for segment in chunk.segments),
                        estimated_tokens=chunk.estimated_tokens,
                        fallback_count=chunk_fallback_counts.get(chunk.chunk_id, 0),
                    )

                def on_chunk_completed(chunk, results: tuple[TranslatedSegmentResult, ...]) -> None:
                    nonlocal translated_segments, job
                    metrics.note_chunk_completed(chunk)
                    for result in results:
                        segment = self._find_segment(chapters, result.segment_id)
                        segment.translated_text = result.translated_text
                        segment.status = SegmentStatus.TRANSLATED
                        self.database.upsert_segment(segment)
                        translated_segments += 1
                    job = self.state_manager.mark_progress(
                        job,
                        completed_segments=translated_segments,
                        total_segments=total_segments,
                    )

                def on_chunk_fallback(chunk, error_summary: str | None) -> None:
                    metrics.note_chunk_fallback(chunk, error_summary)
                    chunk_fallback_counts[chunk.chunk_id] = (
                        chunk_fallback_counts.get(chunk.chunk_id, 0) + 1
                    )
                    fallback_reason_code = classify_chunk_issue(error_summary)
                    if fallback_reason_code is not None:
                        chunk_fallback_reasons[chunk.chunk_id] = fallback_reason_code
                    if self.checkpoint_store is None:
                        return
                    self.checkpoint_store.save_chunk_state(
                        job_id=job.id,
                        chunk_id=chunk.chunk_id,
                        book_id=book.id,
                        chapter_id=chunk.chapter_id,
                        segment_ids=chunk.segment_ids,
                        sequence_no=chunk.sequence_no,
                        status="running",
                        provider_name=provider.name,
                        model_name=provider.model_name,
                        term_snapshot_version="glossary-v1",
                        last_error=error_summary,
                        fallback_reason_code=fallback_reason_code,
                        segment_count=len(chunk.segments),
                        source_char_count=sum(len(segment.source_text) for segment in chunk.segments),
                        estimated_tokens=chunk.estimated_tokens,
                        fallback_count=chunk_fallback_counts.get(chunk.chunk_id, 0),
                    )

                self.orchestrator.translate_book(
                    book=book,
                    chapters=chapters,
                    provider=provider,
                    settings=runtime_settings,
                    glossary_snapshot=glossary_snapshot,
                    term_memory_snapshot=initial_term_memory_snapshot,
                    on_chunk_status=on_chunk_status,
                    on_chunk_completed=on_chunk_completed,
                    on_chunk_fallback=on_chunk_fallback,
                    on_segment_skipped=on_passthrough_segment,
                )

                book = self._ensure_translated_book_title(
                    book=book,
                    chapters=chapters,
                    provider=provider,
                    runtime_settings=runtime_settings,
                )
                final_term_memory_snapshot = self.term_memory_builder.build(chapters=chapters)
                self._save_term_memory(book.id, final_term_memory_snapshot)
                metrics.export_success = True
                metrics.mark_finished()
                self._save_consistency_outputs(
                    book=book,
                    job=job,
                    chapters=chapters,
                    runtime_settings=runtime_settings,
                    metrics=metrics,
                    term_memory_snapshot=final_term_memory_snapshot,
                )
                self._ensure_export_artifacts(book.id)
                job = self.state_manager.mark_completed(
                    job,
                    completed_segments=translated_segments,
                    total_segments=total_segments,
                )
            except Exception as exc:
                metrics.export_success = False
                metrics.mark_finished()
                job = self.state_manager.mark_failed(
                    job,
                    error_summary=str(exc),
                    completed_segments=translated_segments,
                    total_segments=total_segments,
                )
                raise TranslationExecutionError(str(exc)) from exc

            return TranslationRun(
                job=job,
                total_segments=total_segments,
                translated_segments=translated_segments,
                runtime_settings=runtime_settings,
                metrics=metrics,
            )
        finally:
            provider.close()

    def _load_chapters(self, book_id: int) -> tuple[ChapterTranslationBatch, ...]:
        chapters: list[ChapterTranslationBatch] = []
        for chapter in self.database.list_chapters(book_id):
            segments = tuple(self.database.list_segments(chapter.id))
            chapters.append(ChapterTranslationBatch(chapter=chapter, segments=segments))
        return tuple(chapters)

    def _count_translatable_segments(self, chapters: tuple[ChapterTranslationBatch, ...]) -> int:
        return sum(
            1
            for batch in chapters
            for segment in batch.segments
            if segment.status is not SegmentStatus.SKIPPED
        )

    @staticmethod
    def _count_completed_segments(chapters: tuple[ChapterTranslationBatch, ...]) -> int:
        return sum(
            1
            for batch in chapters
            for segment in batch.segments
            if segment.status is SegmentStatus.TRANSLATED
            and (segment.translated_text or "").strip()
        )

    @staticmethod
    def _find_segment(
        chapters: tuple[ChapterTranslationBatch, ...],
        segment_id: int,
    ) -> Segment:
        for batch in chapters:
            for segment in batch.segments:
                if segment.id == segment_id:
                    return segment
        raise TranslationExecutionError(f"Segment '{segment_id}' was not found.")

    def _ensure_translated_book_title(
        self,
        *,
        book: Book,
        chapters: tuple[ChapterTranslationBatch, ...],
        provider,
        runtime_settings: TranslationRuntimeSettings,
    ) -> Book:
        if str(book.title_translation_status or "").strip().lower() == "completed":
            return book

        source_title = str(book.title or "").strip()
        if not source_title:
            return book

        try:
            translated_title = self._request_book_title_translation(
                book=book,
                chapters=chapters,
                provider=provider,
                runtime_settings=runtime_settings,
            )
        except Exception:
            return self.database.update_book_title_translation(
                book.id,
                translated_title=None,
                title_translation_status="failed",
            )

        if (
            book.translated_title == translated_title
            and str(book.title_translation_status or "").strip().lower() == "completed"
        ):
            return book

        return self.database.update_book_title_translation(
            book.id,
            translated_title=translated_title,
            title_translation_status="completed",
        )

    def _request_book_title_translation(
        self,
        *,
        book: Book,
        chapters: tuple[ChapterTranslationBatch, ...],
        provider,
        runtime_settings: TranslationRuntimeSettings,
    ) -> str:
        first_chapter = chapters[0].chapter if chapters else None
        response = provider.translate(
            TranslationRequest(
                text=book.title,
                source_language=book.source_language,
                target_language=self.orchestrator.target_language,
                book_title=book.title,
                context=SegmentContext(
                    chapter_title=(
                        first_chapter.title if first_chapter is not None else "Book metadata"
                    ),
                    chapter_order=first_chapter.order if first_chapter is not None else 0,
                    segment_id=0,
                    segment_order=0,
                    segment_type=SegmentType.OTHER,
                    extra=SegmentExtra(is_opf_metadata=True),
                    chapter_summary=(
                        "The input text is the title of the entire book. "
                        "Translate it as the final Chinese book title, not as a chapter heading."
                    ),
                    narrative_mode="narrative_focus",
                ),
                options={"max_output_tokens": min(256, runtime_settings.max_output_tokens)},
            )
        )

        translated_title = str(response.translated_text or "").strip()
        if not translated_title:
            raise TranslationExecutionError("Translated book title is empty.")
        return translated_title

    def _ensure_export_artifacts(self, book_id: int) -> None:
        existing_artifacts = self.database.list_export_artifacts(book_id)
        existing_kinds = {artifact.kind for artifact in existing_artifacts}
        for kind in (ExportArtifactKind.ZH, ExportArtifactKind.BILINGUAL):
            if kind in existing_kinds:
                continue
            self.database.upsert_export_artifact(
                ExportArtifact(
                    book_id=book_id,
                    kind=kind,
                    status=ExportArtifactStatus.PENDING,
                )
            )

    def _save_term_memory(self, book_id: int, snapshot: BookTermMemorySnapshot) -> None:
        if self.checkpoint_store is None:
            return
        store = BookTermMemoryStore(self.checkpoint_store.root / "book_term_memory")
        store.save(book_id, snapshot)

    def _save_consistency_outputs(
        self,
        *,
        book: Book,
        job: TranslationJob,
        chapters: tuple[ChapterTranslationBatch, ...],
        runtime_settings: TranslationRuntimeSettings,
        metrics: TranslationRunMetrics,
        term_memory_snapshot: BookTermMemorySnapshot,
    ) -> None:
        if self.artifact_store is None:
            return
        segments = tuple(segment for batch in chapters for segment in batch.segments)
        chunk_snapshots = (
            self.checkpoint_store.list_chunks(job.id)
            if self.checkpoint_store is not None and job.id > 0
            else ()
        )
        report = self.consistency_report_generator.generate(
            book=book,
            segments=segments,
            term_memory_snapshot=term_memory_snapshot,
            runtime_profile=runtime_settings.runtime_profile,
            metrics=metrics,
            chunk_snapshots=chunk_snapshots,
        )
        json_path = self.artifact_store.temp_report_path(
            book.id,
            ExportArtifactKind.CONSISTENCY_REPORT,
            extension=".json",
        )
        markdown_path = self.artifact_store.temp_report_path(
            book.id,
            ExportArtifactKind.CONSISTENCY_REPORT,
            extension=".md",
        )
        final_json_path = self.artifact_store.report_path(
            book.id,
            ExportArtifactKind.CONSISTENCY_REPORT,
            extension=".json",
        )
        final_markdown_path = self.artifact_store.report_path(
            book.id,
            ExportArtifactKind.CONSISTENCY_REPORT,
            extension=".md",
        )
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(report.to_markdown(), encoding="utf-8")
        json_path.replace(final_json_path)
        markdown_path.replace(final_markdown_path)
        existing_artifact = self._latest_artifact(
            book.id,
            ExportArtifactKind.CONSISTENCY_REPORT,
        )
        self.database.upsert_export_artifact(
            ExportArtifact(
                id=existing_artifact.id if existing_artifact is not None else 0,
                book_id=book.id,
                kind=ExportArtifactKind.CONSISTENCY_REPORT,
                status=ExportArtifactStatus.READY,
                path=str(final_json_path),
                size=self.artifact_store.file_size(final_json_path),
                created_at=(
                    existing_artifact.created_at
                    if existing_artifact is not None
                    else ExportArtifact(
                        book_id=book.id,
                        kind=ExportArtifactKind.CONSISTENCY_REPORT,
                        status=ExportArtifactStatus.READY,
                    ).created_at
                ),
            )
        )

    def _latest_artifact(
        self,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> ExportArtifact | None:
        for artifact in self.database.list_export_artifacts(book_id):
            if artifact.kind is kind:
                return artifact
        return None

    def _endpoint_capability_cache_root(self):
        if self.checkpoint_store is None:
            return None
        return self.checkpoint_store.root / "endpoint_capabilities"

    def _runtime_profile_override_store_root(self):
        if self.checkpoint_store is None:
            return None
        return self.checkpoint_store.root / "runtime_profile_overrides"

    def _persist_runtime_profile_override(
        self,
        *,
        provider_name: str,
        model_name: str,
        provider_options: dict[str, object],
        runtime_settings: TranslationRuntimeSettings,
        capability_detection,
    ) -> None:
        runtime_profile_override_root = self._runtime_profile_override_store_root()
        if runtime_profile_override_root is None:
            return
        if runtime_settings.runtime_profile_source != "detected":
            return
        confidence = str(capability_detection.metadata.get("confidence") or "").strip().lower()
        if confidence != "high":
            return
        base_url = str(provider_options.get("base_url") or "").strip()
        if not base_url:
            return
        store = RuntimeProfileOverrideStore(runtime_profile_override_root)
        store.upsert(
            provider_name=provider_name,
            model_name=model_name,
            base_url=base_url,
            runtime_profile=runtime_settings.runtime_profile,
            source="endpoint_capability_detection",
            evidence=_build_runtime_profile_override_evidence(
                runtime_settings=runtime_settings,
                capability_detection=capability_detection,
            ),
        )


def _merge_detected_runtime_options(
    base_options: dict[str, object],
    detected_options: dict[str, object],
    detected_option_sources: dict[str, str] | None = None,
) -> dict[str, object]:
    if not detected_options:
        return dict(base_options)
    merged = dict(base_options)
    source_metadata = _read_runtime_option_source_metadata(merged)
    for field_name, detected_value in detected_options.items():
        if _option_value_is_present(merged.get(field_name)):
            continue
        merged[field_name] = detected_value
        source_metadata[field_name] = (
            str((detected_option_sources or {}).get(field_name) or "").strip()
            or "endpoint_capability_detection"
        )
    if source_metadata:
        merged[RUNTIME_OPTION_SOURCE_METADATA_KEY] = source_metadata
    return merged


def _read_runtime_option_source_metadata(options: dict[str, object]) -> dict[str, str]:
    raw = options.get(RUNTIME_OPTION_SOURCE_METADATA_KEY)
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        normalized_key = str(key or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_key or not normalized_value:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _option_value_is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _build_runtime_profile_override_evidence(
    *,
    runtime_settings: TranslationRuntimeSettings,
    capability_detection,
) -> dict[str, object]:
    metadata = dict(capability_detection.metadata)
    deep_probe = metadata.get("deep_probe")
    evidence: dict[str, object] = {
        "runtime_profile": runtime_settings.runtime_profile,
        "runtime_profile_source": runtime_settings.runtime_profile_source,
        "confidence": metadata.get("confidence"),
        "strategy": metadata.get("strategy"),
        "returned_fields": list(metadata.get("returned_fields") or []),
    }
    if isinstance(deep_probe, dict):
        evidence["deep_probe"] = deep_probe
    return evidence


def _build_runtime_target_metadata(
    *,
    provider_name: str,
    model_name: str | None,
    provider_options: dict[str, object],
) -> dict[str, object]:
    normalized_provider_name = str(provider_name or "").strip()
    normalized_model_name = str(model_name or "").strip()
    normalized_base_url = str(provider_options.get("base_url") or "").strip().rstrip("/")
    target_key = RuntimeProfileOverrideStore.build_target_key(
        model_name=normalized_model_name,
        base_url=normalized_base_url,
    )
    metadata: dict[str, object] = {}
    if normalized_provider_name:
        metadata["provider_name"] = normalized_provider_name
    if normalized_model_name:
        metadata["model_name"] = normalized_model_name
    if normalized_base_url:
        metadata["base_url"] = normalized_base_url
    if target_key:
        metadata["target_key"] = target_key
    return metadata


