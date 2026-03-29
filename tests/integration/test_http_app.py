from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.schemas.provider import ProviderConfigRequest
from backend.core.providers.base import TranslationProvider, TranslationRequest, TranslationResponse


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
    <dc:title>HTTP Sample Book</dc:title>
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


def write_frontend(frontend_root: Path) -> None:
    frontend_root.mkdir(parents=True, exist_ok=True)
    (frontend_root / "index.html").write_text(
        "<!doctype html><html><body><h1>Fanbook</h1></body></html>",
        encoding="utf-8",
    )


def test_http_app_runs_full_mock_workflow() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        client = TestClient(
            create_app(
                runtime_root=runtime_root,
                frontend_root=frontend_root,
                translation_provider=ProviderConfigRequest(provider_name="mock"),
            )
        )

        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"

        create_response = client.post(
            "/api/books",
            json={
                "filename": "workflow.epub",
                "contentBase64": base64.b64encode(build_epub_bytes()).decode("utf-8"),
                "sourceLanguage": "en",
            },
        )
        assert create_response.status_code == 201
        book_id = create_response.json()["book_id"]

        translate_response = client.post(
            f"/api/books/{book_id}/translate",
            json={},
        )
        assert translate_response.status_code == 200

        for _ in range(50):
            detail_response = client.get(f"/api/books/{book_id}")
            assert detail_response.status_code == 200
            detail_payload = detail_response.json()
            if detail_payload["current_job"]["status"] == "completed":
                break
        assert detail_payload["book"]["title"] == "HTTP Sample Book"
        assert detail_payload["book"]["translated_title"] == "ZH: HTTP Sample Book"
        assert detail_payload["book"]["title_translation_status"] == "completed"
        assert detail_payload["current_job"]["status"] == "completed"
        assert detail_payload["chapters"][0]["translated_segments"] == 4
        consistency_artifact = next(
            artifact
            for artifact in detail_payload["artifacts"]
            if artifact["kind"] == "consistency_report"
        )
        assert consistency_artifact["status"] == "ready"

        report_response = client.get(f"/api/books/{book_id}/reports/consistency")
        assert report_response.status_code == 200
        report_payload = report_response.json()
        assert report_payload["report_type"] == "consistency_report"
        assert report_payload["book_id"] == book_id

        zh_response = client.get(f"/api/books/{book_id}/exports/zh")
        assert zh_response.status_code == 200
        assert zh_response.headers["content-type"] == "application/epub+zip"

        bilingual_response = client.get(f"/api/books/{book_id}/exports/bilingual")
        assert bilingual_response.status_code == 200
        assert bilingual_response.headers["content-type"] == "application/epub+zip"
    finally:
        cleanup_root(root)


def test_http_app_serves_frontend_index() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        client = TestClient(
            create_app(
                runtime_root=runtime_root,
                frontend_root=frontend_root,
                translation_provider=ProviderConfigRequest(provider_name="mock"),
            )
        )

        response = client.get("/")

        assert response.status_code == 200
        assert "Fanbook" in response.text
    finally:
        cleanup_root(root)


class FailingProvider(TranslationProvider):
    default_model_name = "failing-v1"

    @property
    def name(self) -> str:
        return "failing"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise RuntimeError("synthetic failure")


class RecordingProvider(TranslationProvider):
    default_model_name = "recording-v1"
    last_model_name: str | None = None
    last_options: dict[str, object] | None = None

    def __init__(
        self,
        *,
        model_name: str | None = None,
        options: dict[str, object] | None = None,
    ) -> None:
        super().__init__(model_name=model_name, options=options)
        type(self).last_model_name = self.model_name
        type(self).last_options = dict(self.options)

    @property
    def name(self) -> str:
        return "recording"

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

    @classmethod
    def reset(cls) -> None:
        cls.last_model_name = None
        cls.last_options = None


def test_http_app_lists_multiple_provider_profiles_and_uses_selected_profile() -> None:
    root = make_root()
    try:
        RecordingProvider.reset()
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        app = create_app(
            runtime_root=runtime_root,
            frontend_root=frontend_root,
            translation_provider_profiles={
                "fast": ProviderConfigRequest(
                    provider_name="recording",
                    model_name="fast-model",
                    runtime_profile="generic_large_context",
                    detected_context_window=64000,
                    structured_output_strength="strong",
                    reasoning_mode="standard",
                    api_mode="responses",
                    max_requests_per_minute=60,
                    global_max_concurrency=30,
                    chunk_target_tokens=2200,
                ),
                "cheap": ProviderConfigRequest(
                    provider_name="recording",
                    model_name="cheap-model",
                    runtime_profile="generic_rate_limited",
                    detected_context_window=16000,
                    structured_output_strength="weak",
                    reasoning_mode="reasoning",
                    api_mode="chat_completions",
                    max_requests_per_minute=30,
                    global_max_concurrency=10,
                    chunk_target_tokens=1400,
                ),
            },
            default_translation_profile_name="fast",
        )
        app.state.fanbook.provider_factory._providers["recording"] = RecordingProvider
        client = TestClient(app)

        providers_response = client.get("/api/providers")
        assert providers_response.status_code == 200
        providers_payload = providers_response.json()
        assert providers_payload["default_profile_name"] == "fast"
        assert [item["profile_name"] for item in providers_payload["providers"]] == ["fast", "cheap"]
        assert providers_payload["providers"][0]["provider_name"] == "recording"
        assert providers_payload["providers"][0]["runtime_profile"] == "generic_large_context"
        assert providers_payload["providers"][0]["detected_context_window"] == 64000
        assert providers_payload["providers"][0]["structured_output_strength"] == "strong"
        assert providers_payload["providers"][0]["reasoning_mode"] == "standard"
        assert providers_payload["providers"][0]["api_mode"] == "responses"
        assert providers_payload["providers"][0]["max_requests_per_minute"] == 60
        assert providers_payload["providers"][0]["global_max_concurrency"] == 30
        assert providers_payload["providers"][1]["default_model_name"] == "cheap-model"
        assert providers_payload["providers"][1]["runtime_profile"] == "generic_rate_limited"
        assert providers_payload["providers"][1]["detected_context_window"] == 16000
        assert providers_payload["providers"][1]["structured_output_strength"] == "weak"
        assert providers_payload["providers"][1]["reasoning_mode"] == "reasoning"
        assert providers_payload["providers"][1]["api_mode"] == "chat_completions"
        assert providers_payload["providers"][1]["max_requests_per_minute"] == 30
        assert providers_payload["providers"][1]["global_max_concurrency"] == 10

        create_response = client.post(
            "/api/books",
            json={
                "filename": "profiles.epub",
                "contentBase64": base64.b64encode(build_epub_bytes()).decode("utf-8"),
                "sourceLanguage": "en",
            },
        )
        assert create_response.status_code == 201
        book_id = create_response.json()["book_id"]

        translate_response = client.post(
            f"/api/books/{book_id}/translate",
            json={
                "provider": {
                    "profileName": "cheap",
                }
            },
        )
        assert translate_response.status_code == 200
        assert translate_response.json()["provider_profile_name"] == "cheap"
        assert translate_response.json()["provider_name"] == "recording"
        assert translate_response.json()["model_name"] == "cheap-model"

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "completed":
                break
        assert detail["current_job"]["status"] == "completed"
        assert detail["current_job"]["provider_profile_name"] == "cheap"
        assert RecordingProvider.last_model_name == "cheap-model"
        assert RecordingProvider.last_options is not None
        assert RecordingProvider.last_options["chunk_target_tokens"] == 1400
    finally:
        cleanup_root(root)


def test_http_app_can_resume_after_failed_background_job() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        app = create_app(
            runtime_root=runtime_root,
            frontend_root=frontend_root,
            translation_provider=ProviderConfigRequest(provider_name="failing"),
        )
        app.state.fanbook.provider_factory._providers["failing"] = FailingProvider
        client = TestClient(app)

        create_response = client.post(
            "/api/books",
            json={
                "filename": "resume.epub",
                "contentBase64": base64.b64encode(build_epub_bytes()).decode("utf-8"),
                "sourceLanguage": "en",
            },
        )
        assert create_response.status_code == 201
        book_id = create_response.json()["book_id"]

        first_run = client.post(
            f"/api/books/{book_id}/translate",
            json={},
        )
        assert first_run.status_code == 200

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "failed":
                break
        assert detail["current_job"]["status"] == "failed"

        resume_state = client.get(f"/api/books/{book_id}/resume")
        assert resume_state.status_code == 200
        assert resume_state.json()["can_resume"] is True

        app.state.fanbook.translation_provider = ProviderConfigRequest(provider_name="mock")
        resumed = client.post(
            f"/api/books/{book_id}/resume",
            json={},
        )
        assert resumed.status_code == 200

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "completed":
                break
        assert detail["current_job"]["status"] == "completed"
        assert detail["chapters"][0]["translated_segments"] == 4
    finally:
        cleanup_root(root)


def test_http_app_merges_request_overrides_with_env_defaults_for_translate() -> None:
    root = make_root()
    try:
        RecordingProvider.reset()
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        app = create_app(
            runtime_root=runtime_root,
            frontend_root=frontend_root,
            translation_provider=ProviderConfigRequest(
                provider_name="recording",
                model_name="env-model",
                runtime_profile="generic_safe",
                detected_context_window=12000,
                structured_output_strength="strong",
                reasoning_mode="standard",
                api_mode="responses",
                reasoning_effort="low",
                endpoint_capability_detection_enabled=True,
                endpoint_capability_detection_timeout_seconds=5.0,
                endpoint_capability_detection_ttl_seconds=1800.0,
                max_requests_per_minute=60,
                per_chapter_concurrency=2,
                min_per_chapter_concurrency=1,
                adaptive_per_chapter_concurrency=True,
                chunk_target_tokens=900,
                translation_memory_size=2,
                duplicate_text_cache_enabled=True,
                duplicate_text_cache_min_chars=12,
                dynamic_rate_control_enabled=False,
                dynamic_rate_control_initial_global_concurrency=10,
                dynamic_rate_control_min_global_concurrency=3,
                dynamic_rate_control_scale_up_success_streak=4,
            ),
        )
        app.state.fanbook.provider_factory._providers["recording"] = RecordingProvider
        client = TestClient(app)

        create_response = client.post(
            "/api/books",
            json={
                "filename": "override.epub",
                "contentBase64": base64.b64encode(build_epub_bytes()).decode("utf-8"),
                "sourceLanguage": "en",
            },
        )
        assert create_response.status_code == 201
        book_id = create_response.json()["book_id"]

        translate_response = client.post(
            f"/api/books/{book_id}/translate",
            json={
                "provider": {
                    "modelName": "request-model",
                    "runtimeProfile": "generic_low_latency",
                    "detectedContextWindow": 24000,
                    "structuredOutputStrength": "weak",
                    "reasoningMode": "reasoning",
                    "apiMode": "chat_completions",
                    "reasoningEffort": "medium",
                    "endpointCapabilityDetectionEnabled": False,
                    "endpointCapabilityDetectionTimeoutSeconds": 9,
                    "endpointCapabilityDetectionTtlSeconds": 120,
                    "maxRequestsPerMinute": 30,
                    "adaptivePerChapterConcurrency": False,
                    "chunkTargetTokens": 1500,
                    "translationMemorySize": 0,
                    "duplicateTextCacheEnabled": False,
                    "duplicateTextCacheMinChars": 20,
                    "dynamicRateControlEnabled": True,
                    "dynamicRateControlInitialGlobalConcurrency": 7,
                    "dynamicRateControlMinGlobalConcurrency": 2,
                    "dynamicRateControlScaleUpSuccessStreak": 6,
                    "hardGlobalMaxInFlight": 9,
                    "hardTargetMaxInFlight": 5,
                    "hardConcurrencyAcquireTimeoutSeconds": 45,
                }
            },
        )

        assert translate_response.status_code == 200
        assert translate_response.json()["provider_name"] == "recording"
        assert translate_response.json()["model_name"] == "request-model"

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "completed":
                break
        assert detail["current_job"]["status"] == "completed"
        assert RecordingProvider.last_model_name == "request-model"
        assert RecordingProvider.last_options is not None
        assert RecordingProvider.last_options["runtime_profile"] == "generic_low_latency"
        assert RecordingProvider.last_options["detected_context_window"] == 24000
        assert RecordingProvider.last_options["structured_output_strength"] == "weak"
        assert RecordingProvider.last_options["reasoning_mode"] == "reasoning"
        assert RecordingProvider.last_options["api_mode"] == "chat_completions"
        assert RecordingProvider.last_options["reasoning_effort"] == "medium"
        assert RecordingProvider.last_options["endpoint_capability_detection_enabled"] is False
        assert RecordingProvider.last_options["endpoint_capability_detection_timeout_seconds"] == 9.0
        assert RecordingProvider.last_options["endpoint_capability_detection_ttl_seconds"] == 120.0
        assert RecordingProvider.last_options["max_requests_per_minute"] == 30
        assert RecordingProvider.last_options["adaptive_per_chapter_concurrency"] is False
        assert RecordingProvider.last_options["chunk_target_tokens"] == 1500
        assert RecordingProvider.last_options["translation_memory_size"] == 0
        assert RecordingProvider.last_options["duplicate_text_cache_enabled"] is False
        assert RecordingProvider.last_options["duplicate_text_cache_min_chars"] == 20
        assert RecordingProvider.last_options["dynamic_rate_control_enabled"] is True
        assert RecordingProvider.last_options["dynamic_rate_control_initial_global_concurrency"] == 7
        assert RecordingProvider.last_options["dynamic_rate_control_min_global_concurrency"] == 2
        assert RecordingProvider.last_options["dynamic_rate_control_scale_up_success_streak"] == 6
        assert RecordingProvider.last_options["hard_global_max_in_flight"] == 9
        assert RecordingProvider.last_options["hard_target_max_in_flight"] == 5
        assert RecordingProvider.last_options["hard_concurrency_acquire_timeout_seconds"] == 45.0
        assert RecordingProvider.last_options["per_chapter_concurrency"] == 2
        checkpoint = app.state.fanbook.translation_runner.checkpoint_store.load(
            translate_response.json()["job_id"]
        )
        assert checkpoint is not None
        assert checkpoint.runtime_settings is not None
        assert checkpoint.runtime_settings["runtime_profile"] == "generic_low_latency"
        assert checkpoint.runtime_settings["detected_context_window"] == 24000
        assert checkpoint.runtime_settings["structured_output_strength"] == "weak"
        assert checkpoint.runtime_settings["reasoning_mode"] == "reasoning"
        assert checkpoint.runtime_settings["chunk_target_tokens"] == 1500
        assert checkpoint.runtime_settings["per_chapter_concurrency"] == 2
        assert checkpoint.runtime_settings["adaptive_per_chapter_concurrency"] is False
        assert checkpoint.runtime_settings["hard_global_max_in_flight"] == 9
        assert checkpoint.runtime_settings["hard_target_max_in_flight"] == 5
        assert checkpoint.runtime_settings["hard_concurrency_acquire_timeout_seconds"] == 45.0
        assert checkpoint.runtime_settings["runtime_setting_sources"]["runtime_profile"] == "request_override"
        assert checkpoint.runtime_settings["runtime_setting_sources"]["chunk_target_tokens"] == "request_override"
        assert checkpoint.runtime_settings["runtime_setting_sources"]["per_chapter_concurrency"] == "provider_config"
    finally:
        cleanup_root(root)


def test_http_app_applies_request_overrides_on_resume() -> None:
    root = make_root()
    try:
        RecordingProvider.reset()
        runtime_root = root / "runtime"
        frontend_root = root / "frontend"
        write_frontend(frontend_root)
        app = create_app(
            runtime_root=runtime_root,
            frontend_root=frontend_root,
            translation_provider=ProviderConfigRequest(
                provider_name="failing",
                runtime_profile="generic_large_context",
                detected_context_window=32000,
                structured_output_strength="strong",
                reasoning_mode="standard",
                api_mode="responses",
                max_requests_per_minute=60,
                global_max_concurrency=30,
                duplicate_text_cache_enabled=True,
                dynamic_rate_control_enabled=False,
            ),
        )
        app.state.fanbook.provider_factory._providers["failing"] = FailingProvider
        app.state.fanbook.provider_factory._providers["recording"] = RecordingProvider
        client = TestClient(app)

        create_response = client.post(
            "/api/books",
            json={
                "filename": "resume-override.epub",
                "contentBase64": base64.b64encode(build_epub_bytes()).decode("utf-8"),
                "sourceLanguage": "en",
            },
        )
        assert create_response.status_code == 201
        book_id = create_response.json()["book_id"]

        first_run = client.post(f"/api/books/{book_id}/translate", json={})
        assert first_run.status_code == 200

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "failed":
                break
        assert detail["current_job"]["status"] == "failed"

        resumed = client.post(
            f"/api/books/{book_id}/resume",
            json={
                    "provider": {
                        "providerName": "recording",
                        "modelName": "resume-model",
                        "runtimeProfile": "generic_rate_limited",
                        "detectedContextWindow": 8000,
                        "structuredOutputStrength": "weak",
                        "reasoningMode": "standard",
                        "apiMode": "chat_completions",
                        "maxRequestsPerMinute": 30,
                        "chunkTargetTokens": 2200,
                    "duplicateTextCacheEnabled": False,
                    "dynamicRateControlEnabled": True,
                    "dynamicRateControlInitialGlobalConcurrency": 9,
                }
            },
        )

        assert resumed.status_code == 200
        assert resumed.json()["provider_name"] == "recording"
        assert resumed.json()["model_name"] == "resume-model"

        for _ in range(50):
            detail = client.get(f"/api/books/{book_id}").json()
            if detail["current_job"]["status"] == "completed":
                break
        assert detail["current_job"]["status"] == "completed"
        assert RecordingProvider.last_model_name == "resume-model"
        assert RecordingProvider.last_options is not None
        assert RecordingProvider.last_options["runtime_profile"] == "generic_rate_limited"
        assert RecordingProvider.last_options["detected_context_window"] == 8000
        assert RecordingProvider.last_options["structured_output_strength"] == "weak"
        assert RecordingProvider.last_options["reasoning_mode"] == "standard"
        assert RecordingProvider.last_options["api_mode"] == "chat_completions"
        assert RecordingProvider.last_options["max_requests_per_minute"] == 30
        assert RecordingProvider.last_options["chunk_target_tokens"] == 2200
        assert RecordingProvider.last_options["global_max_concurrency"] == 30
        assert RecordingProvider.last_options["duplicate_text_cache_enabled"] is False
        assert RecordingProvider.last_options["dynamic_rate_control_enabled"] is True
        assert RecordingProvider.last_options["dynamic_rate_control_initial_global_concurrency"] == 9
        checkpoint = app.state.fanbook.translation_runner.checkpoint_store.load(
            resumed.json()["job_id"]
        )
        assert checkpoint is not None
        assert checkpoint.runtime_settings is not None
        assert checkpoint.runtime_settings["runtime_profile"] == "generic_rate_limited"
        assert checkpoint.runtime_settings["detected_context_window"] == 8000
        assert checkpoint.runtime_settings["structured_output_strength"] == "weak"
        assert checkpoint.runtime_settings["reasoning_mode"] == "standard"
        assert checkpoint.runtime_settings["chunk_target_tokens"] == 2200
        assert checkpoint.runtime_settings["global_max_concurrency"] == 30
        assert checkpoint.runtime_settings["runtime_setting_sources"]["runtime_profile"] == "request_override"
        assert checkpoint.runtime_settings["runtime_setting_sources"]["chunk_target_tokens"] == "request_override"
        assert checkpoint.runtime_settings["runtime_setting_sources"]["global_max_concurrency"] == "provider_config"
    finally:
        cleanup_root(root)

