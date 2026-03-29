from io import BytesIO
import json
import shutil
import threading
from pathlib import Path
from uuid import uuid4
import zipfile

from backend.api.routes.jobs import TranslationRoutes
from backend.api.schemas.job import StartTranslationRequest
from backend.api.schemas.provider import ProviderConfigRequest
from backend.core.providers.base import (
    ChunkTranslationRequest,
    RuntimeCapabilityDetection,
    TranslationProvider,
    TranslationProviderError,
    TranslationRequest,
    TranslationResponse,
)
from backend.core.providers.factory import TranslationProviderFactory
from backend.core.translation.runtime_settings import (
    RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION,
    TranslationRuntimeSettings,
)
from backend.domain.enums import ExportArtifactKind, SegmentStatus, TranslationJobStatus
from backend.services.book_service import BookService
from backend.services.translation_service import TranslationExecutionError, TranslationService
from backend.storage.artifact_store import ArtifactStore
from backend.storage.checkpoint_store import CheckpointStore
from backend.storage.database import FanbookDatabase
from backend.storage.runtime_profile_override_store import RuntimeProfileOverrideStore


RUNTIME_ROOT = Path("temp/.codex_runtime_test")
RUNTIME_ROOT.mkdir(exist_ok=True)



def make_root() -> Path:
    root = RUNTIME_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root



def cleanup_root(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)



def build_epub_bytes() -> bytes:
    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    content_opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Sample Book</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>
"""
    chapter_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Chapter One</title></head>
  <body>
    <section>
      <h1>Chapter 1</h1>
      <p>Hello <em>world</em>.</p>
      <ol><li>First item</li></ol>
      <aside epub:type="footnote">Footnote text</aside>
    </section>
  </body>
</html>
"""

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(
            "mimetype",
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/container.xml", container_xml)
        archive.writestr("OEBPS/content.opf", content_opf)
        archive.writestr("OEBPS/ch1.xhtml", chapter_xhtml)
    return buffer.getvalue()


def build_character_epub_bytes() -> bytes:
    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    content_opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Character Book</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>
"""
    chapter_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter One</title></head>
  <body>
    <section>
      <h1>Chapter 1</h1>
      <p>Alice answered Bob.</p>
      <p>Alice answered Bob again.</p>
    </section>
  </body>
</html>
"""

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(
            "mimetype",
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/container.xml", container_xml)
        archive.writestr("OEBPS/content.opf", content_opf)
        archive.writestr("OEBPS/ch1.xhtml", chapter_xhtml)
    return buffer.getvalue()



def build_services(
    root: Path,
    *,
    provider_factory: TranslationProviderFactory | None = None,
    checkpoint_store: CheckpointStore | None = None,
) -> tuple[BookService, TranslationService]:
    database = FanbookDatabase(root / "data" / "fanbook.db")
    storage_root = root / "storage"
    book_service = BookService(database=database, storage_root=storage_root)
    translation_service = TranslationService(
        database=database,
        provider_factory=provider_factory,
        checkpoint_store=checkpoint_store,
        artifact_store=ArtifactStore(storage_root),
    )
    return book_service, translation_service



def test_translation_service_translates_all_segments_with_mock_provider() -> None:
    root = make_root()
    try:
        book_service, translation_service = build_services(root)
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(created.book.id)

        assert run.job.status is TranslationJobStatus.COMPLETED
        assert run.job.provider_name == "mock"
        assert run.job.model_name == "mock-v1"
        assert run.job.progress == 1.0
        assert run.translated_segments == 4
        assert run.total_segments == 4
        assert run.runtime_settings.chunk_target_tokens == 900
        assert run.metrics.chunk_total >= 1
        assert run.metrics.chunk_completed == run.metrics.chunk_total
        assert run.metrics.chunk_failed == 0
        assert run.metrics.fallback_count == 0
        assert run.metrics.export_success is True

        chapter = book_service.database.list_chapters(created.book.id)[0]
        book = book_service.database.get_book(created.book.id)
        segments = book_service.database.list_segments(chapter.id)
        assert book is not None
        assert book.translated_title == "ZH: Sample Book"
        assert book.title_translation_status == "completed"
        assert all(segment.status is SegmentStatus.TRANSLATED for segment in segments)
        assert segments[0].translated_text == "ZH: Chapter 1"
        assert segments[1].translated_text == "ZH: Hello \nZH: world\nZH: ."
    finally:
        cleanup_root(root)



def test_translation_service_persists_chunk_checkpoints() -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        book_service, translation_service = build_services(
            root,
            checkpoint_store=checkpoint_store,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(created.book.id)
        chunk_snapshots = checkpoint_store.list_chunks(run.job.id)
        job_snapshot = checkpoint_store.load(run.job.id)

        assert chunk_snapshots
        assert all(snapshot.status == "completed" for snapshot in chunk_snapshots)
        assert job_snapshot is not None
        assert job_snapshot.runtime_settings is not None
        assert job_snapshot.runtime_settings["chunk_target_tokens"] == 900
        expected_segment_ids = {
            segment.id for segment in book_service.database.list_book_segments(created.book.id)
        }
        actual_segment_ids = {
            segment_id
            for snapshot in chunk_snapshots
            for segment_id in snapshot.segment_ids
        }
        assert actual_segment_ids == expected_segment_ids
        assert all(snapshot.segment_count >= 1 for snapshot in chunk_snapshots)
        assert all(snapshot.source_char_count >= 0 for snapshot in chunk_snapshots)
        assert all(snapshot.estimated_tokens >= 0 for snapshot in chunk_snapshots)
        assert all(snapshot.fallback_count == 0 for snapshot in chunk_snapshots)
    finally:
        cleanup_root(root)



def test_translation_route_rejects_unknown_provider() -> None:
    root = make_root()
    try:
        book_service, translation_service = build_services(root)
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())
        routes = TranslationRoutes(translation_service)

        response = routes.translate_book(
            created.book.id,
            StartTranslationRequest(
                provider=ProviderConfigRequest(provider_name="missing-provider"),
            ),
        )

        assert response.status_code == 400
        assert getattr(response.payload, "code") == "invalid_provider"
    finally:
        cleanup_root(root)



class FailingProvider(TranslationProvider):
    default_model_name = "failing-v1"

    @property
    def name(self) -> str:
        return "failing"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise RuntimeError("synthetic failure")


class ClosableProvider(TranslationProvider):
    default_model_name = "closable-v1"
    close_calls = 0

    @property
    def name(self) -> str:
        return "closable"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(
            translated_text=f"ZH: {request.text}",
            provider_name=self.name,
            model_name=self.model_name,
        )

    def close(self) -> None:
        type(self).close_calls += 1


class FallbackRecordingProvider(TranslationProvider):
    default_model_name = "fallback-v1"

    @property
    def name(self) -> str:
        return "fallback-recording"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        translated_lines = [
            f"ZH: {line}" if line else line
            for line in request.text.split("\n")
        ]
        return TranslationResponse(
            translated_text="\n".join(translated_lines),
            provider_name=self.name,
            model_name=self.model_name,
        )

    def translate_chunk(self, request: ChunkTranslationRequest):
        raise TranslationProviderError("OpenAI API returned invalid JSON for chunk translation.")


class InconsistentNameProvider(TranslationProvider):
    default_model_name = "inconsistent-v1"

    def __init__(
        self,
        *,
        model_name: str | None = None,
        options: dict[str, object] | None = None,
    ) -> None:
        super().__init__(model_name=model_name, options=options)
        self._call_count = 0

    @property
    def name(self) -> str:
        return "inconsistent-name"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self._call_count += 1
        if "Alice" in request.text:
            translated_text = (
                "爱丽丝 回答 鲍勃。"
                if self._call_count % 2 == 1
                else "艾丽斯 回答 鲍勃。"
            )
        else:
            translated_text = f"ZH: {request.text}"
        return TranslationResponse(
            translated_text=translated_text,
            provider_name=self.name,
            model_name=self.model_name,
        )


class CapabilityDetectingProvider(TranslationProvider):
    default_model_name = "capability-v1"
    last_options: dict[str, object] | None = None

    @property
    def name(self) -> str:
        return "capability-detecting"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        type(self).last_options = dict(self.options)
        return TranslationResponse(
            translated_text=f"ZH: {request.text}",
            provider_name=self.name,
            model_name=self.model_name,
        )

    def detect_runtime_capabilities(self) -> RuntimeCapabilityDetection:
        return RuntimeCapabilityDetection(
            options={
                "api_mode": "chat_completions",
                "detected_context_window": 64000,
                "reasoning_mode": "reasoning",
                "structured_output_strength": "strong",
            },
            option_sources={
                "api_mode": "endpoint_models_payload",
                "detected_context_window": "endpoint_model_directory",
                "reasoning_mode": "endpoint_models_payload",
                "structured_output_strength": "endpoint_models_payload",
            },
            metadata={
                "strategy": "models_list",
                "probe_status": "ok",
                "cache_hit": False,
                "model_listed": True,
                "snapshot_source": "live_probe",
            },
        )


class HighConfidenceCapabilityProvider(TranslationProvider):
    default_model_name = "verified-model"

    @property
    def name(self) -> str:
        return "high-confidence"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(
            translated_text=f"ZH: {request.text}",
            provider_name=self.name,
            model_name=self.model_name,
        )

    def detect_runtime_capabilities(self) -> RuntimeCapabilityDetection:
        return RuntimeCapabilityDetection(
            options={
                "api_mode": "responses",
                "structured_output_strength": "strong",
                "reasoning_mode": "reasoning",
            },
            option_sources={
                "api_mode": "endpoint_capability_detection",
                "structured_output_strength": "endpoint_capability_detection",
                "reasoning_mode": "endpoint_capability_detection",
            },
            metadata={
                "strategy": "models_list+deep_probe",
                "probe_status": "ok",
                "cache_hit": False,
                "confidence": "high",
                "returned_fields": [
                    "api_mode",
                    "reasoning_mode",
                    "structured_output_strength",
                ],
                "deep_probe": {
                    "status": "ok",
                    "chosen_api_mode": "responses",
                },
            },
        )



def test_translation_service_marks_job_failed_when_provider_raises() -> None:
    root = make_root()
    try:
        provider_factory = TranslationProviderFactory({"failing": FailingProvider})
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        try:
            translation_service.start_translation(
                created.book.id,
                provider_name="failing",
            )
        except TranslationExecutionError:
            pass
        else:
            raise AssertionError("Expected TranslationExecutionError for failing provider.")

        job = book_service.database.get_latest_translation_job(created.book.id)
        assert job is not None
        assert job.status is TranslationJobStatus.FAILED
        assert job.progress == 0.0
        assert job.error_summary == "synthetic failure"
    finally:
        cleanup_root(root)


def test_translation_service_closes_provider_after_run() -> None:
    root = make_root()
    ClosableProvider.close_calls = 0
    try:
        provider_factory = TranslationProviderFactory({"closable": ClosableProvider})
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(
            created.book.id,
            provider_name="closable",
        )

        assert run.job.status is TranslationJobStatus.COMPLETED
        assert ClosableProvider.close_calls == 1
    finally:
        cleanup_root(root)


def test_translation_service_persists_fallback_reason_codes_in_chunk_checkpoints() -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        provider_factory = TranslationProviderFactory({"fallback-recording": FallbackRecordingProvider})
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
            checkpoint_store=checkpoint_store,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(
            created.book.id,
            provider_name="fallback-recording",
        )

        assert run.job.status is TranslationJobStatus.COMPLETED
        assert run.metrics.fallback_count >= 1
        chunk_snapshots = checkpoint_store.list_chunks(run.job.id)
        assert chunk_snapshots
        assert any(snapshot.fallback_reason_code == "invalid_json" for snapshot in chunk_snapshots)
        assert all(snapshot.status == "completed" for snapshot in chunk_snapshots)
    finally:
        cleanup_root(root)


def test_translation_service_generates_consistency_report_artifact() -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        provider_factory = TranslationProviderFactory({"inconsistent-name": InconsistentNameProvider})
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
            checkpoint_store=checkpoint_store,
        )
        created = book_service.create_book(
            filename="characters.epub",
            content=build_character_epub_bytes(),
        )

        run = translation_service.start_translation(
            created.book.id,
            provider_name="inconsistent-name",
            provider_options={"runtime_profile": "novel_consistency"},
        )

        assert run.job.status is TranslationJobStatus.COMPLETED
        artifacts = book_service.database.list_export_artifacts(created.book.id)
        report_artifact = next(
            artifact
            for artifact in artifacts
            if artifact.kind is ExportArtifactKind.CONSISTENCY_REPORT
        )
        assert report_artifact.path is not None
        payload = json.loads(Path(report_artifact.path).read_text(encoding="utf-8"))
        assert payload["runtime_profile"] == "novel_consistency"
        assert payload["summary"]["term_conflict_count"] >= 1
        assert any(issue["source"] == "Alice" for issue in payload["term_conflicts"])
    finally:
        cleanup_root(root)


def test_translation_service_merges_detected_runtime_metadata_into_checkpoint() -> None:
    root = make_root()
    try:
        CapabilityDetectingProvider.last_options = None
        checkpoint_store = CheckpointStore(root / "runtime")
        provider_factory = TranslationProviderFactory(
            {"capability-detecting": CapabilityDetectingProvider}
        )
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
            checkpoint_store=checkpoint_store,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(
            created.book.id,
            provider_name="capability-detecting",
        )

        assert CapabilityDetectingProvider.last_options is not None
        assert CapabilityDetectingProvider.last_options["api_mode"] == "chat_completions"
        assert run.runtime_settings.detected_context_window == 64000
        assert run.runtime_settings.api_mode == "chat_completions"
        assert run.runtime_settings.reasoning_mode == "reasoning"
        assert run.runtime_settings.structured_output_strength == "strong"
        assert run.runtime_settings.runtime_setting_sources["api_mode"] == (
            "endpoint_models_payload"
        )
        assert run.runtime_settings.runtime_setting_sources["detected_context_window"] == (
            "endpoint_model_directory"
        )
        checkpoint = checkpoint_store.load(run.job.id)
        assert checkpoint is not None
        assert checkpoint.runtime_settings is not None
        assert checkpoint.runtime_settings["api_mode"] == "chat_completions"
        assert checkpoint.runtime_settings["detected_context_window"] == 64000
        assert checkpoint.runtime_settings["reasoning_mode"] == "reasoning"
        assert checkpoint.runtime_settings["structured_output_strength"] == "strong"
        assert checkpoint.runtime_settings["runtime_setting_sources"]["api_mode"] == (
            "endpoint_models_payload"
        )
        assert checkpoint.runtime_settings["runtime_setting_sources"]["detected_context_window"] == (
            "endpoint_model_directory"
        )
        assert checkpoint.runtime_settings["endpoint_capability_detection"]["strategy"] == (
            "models_list"
        )
        assert checkpoint.runtime_settings["endpoint_capability_detection"]["probe_status"] == "ok"
        assert checkpoint.runtime_settings["endpoint_capability_detection"]["model_listed"] is True
        assert checkpoint.runtime_settings["runtime_target"]["provider_name"] == "capability-detecting"
        assert checkpoint.runtime_settings["runtime_target"]["model_name"] == "capability-v1"
    finally:
        cleanup_root(root)


def test_translation_service_keeps_explicit_runtime_metadata_over_detected_values() -> None:
    root = make_root()
    try:
        provider_factory = TranslationProviderFactory(
            {"capability-detecting": CapabilityDetectingProvider}
        )
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(
            created.book.id,
            provider_name="capability-detecting",
            provider_options={
                "detected_context_window": 32000,
                "reasoning_mode": "standard",
            },
        )

        assert run.runtime_settings.detected_context_window == 32000
        assert run.runtime_settings.reasoning_mode == "standard"
        assert run.runtime_settings.runtime_setting_sources["detected_context_window"] == "option"
        assert run.runtime_settings.runtime_setting_sources["reasoning_mode"] == "option"
    finally:
        cleanup_root(root)


def test_translation_service_persists_high_confidence_runtime_profile_override() -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        provider_factory = TranslationProviderFactory(
            {"high-confidence": HighConfidenceCapabilityProvider}
        )
        book_service, translation_service = build_services(
            root,
            provider_factory=provider_factory,
            checkpoint_store=checkpoint_store,
        )
        created = book_service.create_book(filename="demo.epub", content=build_epub_bytes())

        run = translation_service.start_translation(
            created.book.id,
            provider_name="high-confidence",
            provider_options={
                "base_url": "https://api.example.test/v1",
            },
        )

        assert run.runtime_settings.runtime_profile == "generic_reasoning"
        assert run.runtime_settings.runtime_profile_source == "detected"

        override_root = checkpoint_store.root / "runtime_profile_overrides"
        override_store = RuntimeProfileOverrideStore(override_root)
        entry = override_store.load(
            model_name="verified-model",
            base_url="https://api.example.test/v1",
        )
        assert entry is not None
        assert entry.runtime_profile == "generic_reasoning"
        assert entry.source == "endpoint_capability_detection"
        assert entry.evidence is not None
        assert entry.evidence["confidence"] == "high"
        checkpoint = checkpoint_store.load(run.job.id)
        assert checkpoint is not None
        assert checkpoint.runtime_settings is not None
        assert checkpoint.runtime_settings["runtime_target"]["base_url"] == (
            "https://api.example.test/v1"
        )
        assert checkpoint.runtime_settings["runtime_target"]["target_key"] == (
            "verified-model@https://api.example.test/v1"
        )

        overridden = TranslationRuntimeSettings.from_options(
            {
                "base_url": "https://api.example.test/v1",
                RUNTIME_PROFILE_OVERRIDE_STORE_ROOT_OPTION: str(override_root),
            },
            provider_name="high-confidence",
            model_name="verified-model",
        )
        assert overridden.runtime_profile == "generic_reasoning"
        assert overridden.runtime_profile_source == "override"
    finally:
        cleanup_root(root)


def test_checkpoint_store_serializes_concurrent_save_state_calls() -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        errors: list[Exception] = []
        start_barrier = threading.Barrier(3)

        def writer(name: str, progress_seed: float) -> None:
            start_barrier.wait()
            try:
                for index in range(40):
                    checkpoint_store.save_state(
                        job_id=1,
                        book_id=99,
                        status="running",
                        provider_name="openai",
                        model_name="gpt-5.4",
                        progress=min(1.0, progress_seed + index / 100.0),
                        translated_segments=index,
                        total_segments=100,
                        checkpoint_reason="heartbeat",
                        thread_name=name,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=("writer-a", 0.1)),
            threading.Thread(target=writer, args=("writer-b", 0.2)),
        ]
        for thread in threads:
            thread.start()
        start_barrier.wait()
        for thread in threads:
            thread.join()

        assert not errors
        snapshot = checkpoint_store.load(1)
        assert snapshot is not None
        assert snapshot.job_id == 1
        assert snapshot.book_id == 99
        assert snapshot.status == "running"
        assert snapshot.provider_name == "openai"
        assert snapshot.model_name == "gpt-5.4"
        assert snapshot.total_segments == 100
    finally:
        cleanup_root(root)


def test_checkpoint_store_retries_transient_permission_error_on_replace(monkeypatch) -> None:
    root = make_root()
    try:
        checkpoint_store = CheckpointStore(root / "runtime")
        original_replace = Path.replace
        state_replace_attempts = {"count": 0}

        def flaky_replace(self: Path, target: Path) -> Path:
            if str(target).endswith("state.json") and state_replace_attempts["count"] == 0:
                state_replace_attempts["count"] += 1
                raise PermissionError(32, "sharing violation")
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", flaky_replace)

        checkpoint_store.save_state(
            job_id=1,
            book_id=99,
            status="running",
            provider_name="openai",
            model_name="gpt-5.4",
            progress=0.5,
            translated_segments=50,
            total_segments=100,
            checkpoint_reason="heartbeat",
            thread_name="writer-a",
        )

        snapshot = checkpoint_store.load(1)
        assert snapshot is not None
        assert snapshot.job_id == 1
        assert snapshot.progress == 0.5
        assert state_replace_attempts["count"] == 1
    finally:
        cleanup_root(root)
