from __future__ import annotations

import base64
import binascii
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.api.routes.books import BookRoutes
from backend.api.routes.exports import ExportRoutes
from backend.api.schemas.book import CreateBookRequest, ErrorResponse, RouteResult
from backend.api.schemas.provider import ProviderConfigRequest
from backend.config.dotenv_loader import load_project_dotenv
from backend.config.env_provider import (
    TranslationProviderProfileSet,
    build_env_translation_provider_profiles,
    normalize_translation_profile_name,
)
from backend.core.providers.factory import TranslationProviderFactory
from backend.jobs.resume_service import TranslationResumeService
from backend.jobs.runner import BackgroundTranslationRequest, ThreadedTranslationJobRunner
from backend.services.book_service import BookNotFoundError, BookService
from backend.services.export_service import ExportService
from backend.services.report_service import (
    ConsistencyReportNotReadyError,
    ConsistencyReportService,
    ConsistencyReportServiceError,
)
from backend.services.translation_service import TranslationService
from backend.storage.artifact_store import ArtifactStore
from backend.storage.checkpoint_store import CheckpointStore
from backend.storage.database import FanbookDatabase


@dataclass(slots=True)
class AppState:
    runtime_root: Path
    frontend_root: Path
    database: FanbookDatabase
    book_routes: BookRoutes
    export_routes: ExportRoutes
    report_service: ConsistencyReportService
    translation_runner: ThreadedTranslationJobRunner
    resume_service: TranslationResumeService
    provider_factory: TranslationProviderFactory
    translation_provider: ProviderConfigRequest
    default_translation_profile_name: str
    translation_provider_profiles: dict[str, ProviderConfigRequest]


class UploadBookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    filename: str
    content_base64: str = Field(alias="contentBase64")
    title: str | None = None
    source_language: str = Field(default="en", alias="sourceLanguage")


class StartTranslationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    provider: "ProviderOverridePayload | None" = None


class ProviderOverridePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    profile_name: str | None = Field(default=None, alias="profileName")
    provider_name: str | None = Field(default=None, alias="providerName")
    model_name: str | None = Field(default=None, alias="modelName")
    api_key: str | None = Field(default=None, alias="apiKey")
    base_url: str | None = Field(default=None, alias="baseUrl")
    runtime_profile: str | None = Field(default=None, alias="runtimeProfile")
    detected_context_window: int | None = Field(default=None, alias="detectedContextWindow")
    structured_output_strength: str | None = Field(
        default=None,
        alias="structuredOutputStrength",
    )
    reasoning_mode: str | None = Field(default=None, alias="reasoningMode")
    api_mode: str | None = Field(default=None, alias="apiMode")
    reasoning_effort: str | None = Field(default=None, alias="reasoningEffort")
    timeout_seconds: float | None = Field(default=None, alias="timeoutSeconds")
    endpoint_capability_detection_enabled: bool | None = Field(
        default=None,
        alias="endpointCapabilityDetectionEnabled",
    )
    endpoint_capability_detection_timeout_seconds: float | None = Field(
        default=None,
        alias="endpointCapabilityDetectionTimeoutSeconds",
    )
    endpoint_capability_detection_ttl_seconds: float | None = Field(
        default=None,
        alias="endpointCapabilityDetectionTtlSeconds",
    )
    max_requests_per_minute: int | None = Field(default=None, alias="maxRequestsPerMinute")
    global_max_concurrency: int | None = Field(default=None, alias="globalMaxConcurrency")
    per_chapter_concurrency: int | None = Field(default=None, alias="perChapterConcurrency")
    min_per_chapter_concurrency: int | None = Field(default=None, alias="minPerChapterConcurrency")
    adaptive_per_chapter_concurrency: bool | None = Field(
        default=None,
        alias="adaptivePerChapterConcurrency",
    )
    max_input_tokens: int | None = Field(default=None, alias="maxInputTokens")
    reserved_output_tokens: int | None = Field(default=None, alias="reservedOutputTokens")
    max_output_tokens: int | None = Field(default=None, alias="maxOutputTokens")
    chunk_target_tokens: int | None = Field(default=None, alias="chunkTargetTokens")
    context_segments_before: int | None = Field(default=None, alias="contextSegmentsBefore")
    context_segments_after: int | None = Field(default=None, alias="contextSegmentsAfter")
    translation_memory_size: int | None = Field(default=None, alias="translationMemorySize")
    retry_max_attempts: int | None = Field(default=None, alias="retryMaxAttempts")
    duplicate_text_cache_enabled: bool | None = Field(
        default=None,
        alias="duplicateTextCacheEnabled",
    )
    duplicate_text_cache_min_chars: int | None = Field(
        default=None,
        alias="duplicateTextCacheMinChars",
    )
    dynamic_rate_control_enabled: bool | None = Field(
        default=None,
        alias="dynamicRateControlEnabled",
    )
    dynamic_rate_control_initial_global_concurrency: int | None = Field(
        default=None,
        alias="dynamicRateControlInitialGlobalConcurrency",
    )
    dynamic_rate_control_min_global_concurrency: int | None = Field(
        default=None,
        alias="dynamicRateControlMinGlobalConcurrency",
    )
    dynamic_rate_control_scale_up_success_streak: int | None = Field(
        default=None,
        alias="dynamicRateControlScaleUpSuccessStreak",
    )
    hard_global_max_in_flight: int | None = Field(
        default=None,
        alias="hardGlobalMaxInFlight",
    )
    hard_target_max_in_flight: int | None = Field(
        default=None,
        alias="hardTargetMaxInFlight",
    )
    hard_concurrency_acquire_timeout_seconds: float | None = Field(
        default=None,
        alias="hardConcurrencyAcquireTimeoutSeconds",
    )

    def merge_into(self, base: ProviderConfigRequest) -> ProviderConfigRequest:
        return base.merged_with(
            provider_name=self.provider_name,
            model_name=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            runtime_profile=self.runtime_profile,
            detected_context_window=self.detected_context_window,
            structured_output_strength=self.structured_output_strength,
            reasoning_mode=self.reasoning_mode,
            api_mode=self.api_mode,
            reasoning_effort=self.reasoning_effort,
            timeout_seconds=self.timeout_seconds,
            endpoint_capability_detection_enabled=self.endpoint_capability_detection_enabled,
            endpoint_capability_detection_timeout_seconds=self.endpoint_capability_detection_timeout_seconds,
            endpoint_capability_detection_ttl_seconds=self.endpoint_capability_detection_ttl_seconds,
            max_requests_per_minute=self.max_requests_per_minute,
            global_max_concurrency=self.global_max_concurrency,
            per_chapter_concurrency=self.per_chapter_concurrency,
            min_per_chapter_concurrency=self.min_per_chapter_concurrency,
            adaptive_per_chapter_concurrency=self.adaptive_per_chapter_concurrency,
            max_input_tokens=self.max_input_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
            max_output_tokens=self.max_output_tokens,
            chunk_target_tokens=self.chunk_target_tokens,
            context_segments_before=self.context_segments_before,
            context_segments_after=self.context_segments_after,
            translation_memory_size=self.translation_memory_size,
            retry_max_attempts=self.retry_max_attempts,
            duplicate_text_cache_enabled=self.duplicate_text_cache_enabled,
            duplicate_text_cache_min_chars=self.duplicate_text_cache_min_chars,
            dynamic_rate_control_enabled=self.dynamic_rate_control_enabled,
            dynamic_rate_control_initial_global_concurrency=self.dynamic_rate_control_initial_global_concurrency,
            dynamic_rate_control_min_global_concurrency=self.dynamic_rate_control_min_global_concurrency,
            dynamic_rate_control_scale_up_success_streak=self.dynamic_rate_control_scale_up_success_streak,
            hard_global_max_in_flight=self.hard_global_max_in_flight,
            hard_target_max_in_flight=self.hard_target_max_in_flight,
            hard_concurrency_acquire_timeout_seconds=self.hard_concurrency_acquire_timeout_seconds,
        )



def create_app(
    *,
    runtime_root: str | Path | None = None,
    frontend_root: str | Path | None = None,
    translation_provider: ProviderConfigRequest | None = None,
    translation_provider_profiles: dict[str, ProviderConfigRequest] | None = None,
    default_translation_profile_name: str | None = None,
) -> FastAPI:
    load_project_dotenv()

    project_root = Path(__file__).resolve().parents[2]
    resolved_runtime_root = Path(
        runtime_root
        or os.getenv("FANBOOK_RUNTIME_ROOT")
        or project_root / "temp" / ".fanbook-runtime"
    )
    resolved_frontend_root = Path(
        frontend_root
        or os.getenv("FANBOOK_FRONTEND_ROOT")
        or project_root / "frontend"
    )
    resolved_runtime_root.mkdir(parents=True, exist_ok=True)
    profile_set = _resolve_translation_provider_profile_set(
        translation_provider=translation_provider,
        translation_provider_profiles=translation_provider_profiles,
        default_translation_profile_name=default_translation_profile_name,
    )
    resolved_translation_provider = profile_set.default_provider

    provider_factory = TranslationProviderFactory()
    database = FanbookDatabase(resolved_runtime_root / "data" / "fanbook.db")
    storage_root = resolved_runtime_root / "storage"
    checkpoint_store = CheckpointStore(resolved_runtime_root)
    artifact_store = ArtifactStore(storage_root)
    book_service = BookService(database=database, storage_root=storage_root)
    translation_service = TranslationService(
        database=database,
        provider_factory=provider_factory,
        checkpoint_store=checkpoint_store,
        artifact_store=artifact_store,
    )
    export_service = ExportService(
        database=database,
        artifact_store=artifact_store,
    )
    report_service = ConsistencyReportService(
        database=database,
        artifact_store=artifact_store,
    )
    translation_runner = ThreadedTranslationJobRunner(
        database=database,
        translation_service=translation_service,
        checkpoint_store=checkpoint_store,
    )
    resume_service = TranslationResumeService(database, checkpoint_store)

    state = AppState(
        runtime_root=resolved_runtime_root,
        frontend_root=resolved_frontend_root,
        database=database,
        book_routes=BookRoutes(book_service),
        export_routes=ExportRoutes(export_service),
        report_service=report_service,
        translation_runner=translation_runner,
        resume_service=resume_service,
        provider_factory=provider_factory,
        translation_provider=resolved_translation_provider,
        default_translation_profile_name=profile_set.default_profile_name,
        translation_provider_profiles=profile_set.profiles,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        state.resume_service.recover_pending_jobs(runner=state.translation_runner)
        yield

    app = FastAPI(title="Fanbook", version="0.1.0", lifespan=lifespan)
    app.state.fanbook = state

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "runtime_root": str(state.runtime_root),
            "frontend_root": str(state.frontend_root),
            "translation_profile": state.default_translation_profile_name,
            "translation_provider": state.translation_provider.provider_name,
            "translation_model": state.translation_provider.model_name,
        }

    @app.get("/api/providers")
    def list_providers() -> dict[str, Any]:
        return {
            "default_profile_name": state.default_translation_profile_name,
            "providers": [
                {
                    "name": profile_name,
                    "profile_name": profile_name,
                    "provider_name": provider.provider_name,
                    "default_model_name": provider.model_name,
                    "runtime_profile": provider.runtime_profile,
                    "detected_context_window": provider.detected_context_window,
                    "structured_output_strength": provider.structured_output_strength,
                    "reasoning_mode": provider.reasoning_mode,
                    "api_mode": provider.api_mode,
                    "max_requests_per_minute": provider.max_requests_per_minute,
                    "global_max_concurrency": provider.global_max_concurrency,
                    "per_chapter_concurrency": provider.per_chapter_concurrency,
                    "min_per_chapter_concurrency": provider.min_per_chapter_concurrency,
                    "hard_global_max_in_flight": provider.hard_global_max_in_flight,
                    "hard_target_max_in_flight": provider.hard_target_max_in_flight,
                    "hard_concurrency_acquire_timeout_seconds": provider.hard_concurrency_acquire_timeout_seconds,
                    "requires_api_key": _translation_provider_requires_api_key(provider),
                    "env_managed": True,
                    "configured": _is_translation_provider_configured(provider),
                    "is_default": profile_name == state.default_translation_profile_name,
                }
                for profile_name, provider in state.translation_provider_profiles.items()
            ],
        }

    @app.post("/api/books")
    def create_book(payload: UploadBookPayload) -> JSONResponse:
        try:
            content = base64.b64decode(payload.content_base64.encode("utf-8"), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_upload", "message": f"Invalid base64 content: {exc}"},
            ) from exc

        result = state.book_routes.create_book(
            CreateBookRequest(
                filename=payload.filename,
                content=content,
                title=payload.title,
                source_language=payload.source_language,
            )
        )
        return _route_result_json(result)

    @app.get("/api/books/{book_id}")
    def get_book(book_id: int) -> JSONResponse:
        return _route_result_json(state.book_routes.get_book(book_id))

    @app.get("/api/books/{book_id}/resume")
    def get_resume_state(book_id: int) -> dict[str, Any]:
        state_view = state.resume_service.inspect(book_id, runner=state.translation_runner)
        return {
            "book_id": state_view.book_id,
            "job_id": state_view.job_id,
            "status": state_view.status,
            "can_resume": state_view.can_resume,
            "translated_segments": state_view.translated_segments,
            "total_segments": state_view.total_segments,
            "failed_segments": state_view.failed_segments,
            "remaining_segments": state_view.remaining_segments,
            "provider_profile_name": state_view.provider_profile_name,
            "provider_name": state_view.provider_name,
            "model_name": state_view.model_name,
            "error_summary": state_view.error_summary,
            "checkpoint": asdict(state_view.checkpoint) if state_view.checkpoint is not None else None,
        }

    @app.post("/api/books/{book_id}/translate")
    def start_translation(book_id: int, payload: StartTranslationPayload) -> dict[str, Any]:
        profile_name, provider = _active_translation_provider(state, payload.provider)
        handle = state.translation_runner.start(
            BackgroundTranslationRequest(
                book_id=book_id,
                provider_profile_name=profile_name,
                provider_name=provider.provider_name,
                model_name=provider.model_name,
                provider_options=provider.options_dict(),
            )
        )
        return {
            "book_id": handle.book_id,
            "job_id": handle.job_id,
            "status": handle.status,
            "provider_profile_name": handle.provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name,
            "started_at": handle.started_at,
            "thread_name": handle.thread_name,
        }

    @app.post("/api/books/{book_id}/resume")
    def resume_translation(book_id: int, payload: StartTranslationPayload) -> dict[str, Any]:
        profile_name, provider = _active_translation_provider(state, payload.provider)
        try:
            handle = state.resume_service.resume(
                book_id,
                runner=state.translation_runner,
                provider_profile_name=profile_name,
                provider_name=provider.provider_name,
                model_name=provider.model_name,
                provider_options=provider.options_dict(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "resume_not_ready", "message": str(exc)},
            ) from exc
        return {
            "book_id": handle.book_id,
            "job_id": handle.job_id,
            "status": handle.status,
            "provider_profile_name": handle.provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name,
            "started_at": handle.started_at,
            "thread_name": handle.thread_name,
        }

    @app.get("/api/books/{book_id}/exports/zh")
    def download_zh(book_id: int) -> FileResponse:
        return _download_export(state, book_id, bilingual=False)

    @app.get("/api/books/{book_id}/exports/bilingual")
    def download_bilingual(book_id: int) -> FileResponse:
        return _download_export(state, book_id, bilingual=True)

    @app.get("/api/books/{book_id}/export/zh")
    def download_zh_legacy(book_id: int) -> FileResponse:
        return _download_export(state, book_id, bilingual=False)

    @app.get("/api/books/{book_id}/export/bilingual")
    def download_bilingual_legacy(book_id: int) -> FileResponse:
        return _download_export(state, book_id, bilingual=True)

    @app.get("/api/books/{book_id}/reports/consistency")
    def download_consistency_report(book_id: int) -> FileResponse:
        return _download_consistency_report(state, book_id, markdown=False)

    @app.get("/api/books/{book_id}/reports/consistency.md")
    def download_consistency_report_markdown(book_id: int) -> FileResponse:
        return _download_consistency_report(state, book_id, markdown=True)

    @app.get("/")
    def index() -> FileResponse:
        return _serve_frontend_file(state.frontend_root, "")

    @app.get("/{asset_path:path}")
    def frontend(asset_path: str) -> FileResponse:
        if asset_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        return _serve_frontend_file(state.frontend_root, asset_path)

    return app



def _active_translation_provider(
    state: AppState,
    override_payload: ProviderOverridePayload | None = None,
) -> tuple[str, ProviderConfigRequest]:
    profile_name = state.default_translation_profile_name
    if override_payload is not None and override_payload.profile_name:
        requested_profile_name = normalize_translation_profile_name(
            override_payload.profile_name
        )
        provider = state.translation_provider_profiles.get(requested_profile_name)
        if provider is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_provider_profile",
                    "message": f"翻译配置档 '{override_payload.profile_name}' 不存在。",
                },
            )
        profile_name = requested_profile_name
    else:
        provider = state.translation_provider

    provider = (
        override_payload.merge_into(provider)
        if override_payload is not None
        else provider
    )
    _ensure_supported_provider(state.provider_factory, provider.provider_name)
    _ensure_translation_provider_is_configured(provider)
    return profile_name, provider



def _is_translation_provider_configured(provider: ProviderConfigRequest) -> bool:
    normalized = provider.provider_name.strip().lower()
    if normalized == "openai":
        return bool((provider.api_key or "").strip())
    return True


def _translation_provider_requires_api_key(provider: ProviderConfigRequest) -> bool:
    return provider.provider_name.strip().lower() == "openai"



def _ensure_translation_provider_is_configured(provider: ProviderConfigRequest) -> None:
    if _is_translation_provider_configured(provider):
        return
    raise HTTPException(
        status_code=500,
        detail={
            "code": "env_provider_not_configured",
            "message": "当前翻译配置档的 API 尚未配置完成，请先设置对应的 API key。",
        },
    )



def _ensure_supported_provider(
    provider_factory: TranslationProviderFactory,
    provider_name: str,
) -> None:
    if provider_name.strip().lower() not in provider_factory.available_providers():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_provider",
                "message": f"Provider '{provider_name}' is not supported.",
            },
        )


def _resolve_translation_provider_profile_set(
    *,
    translation_provider: ProviderConfigRequest | None,
    translation_provider_profiles: dict[str, ProviderConfigRequest] | None,
    default_translation_profile_name: str | None,
) -> TranslationProviderProfileSet:
    if translation_provider_profiles:
        profiles: dict[str, ProviderConfigRequest] = {}
        for profile_name, provider in translation_provider_profiles.items():
            normalized_name = normalize_translation_profile_name(profile_name)
            profiles[normalized_name] = provider
        resolved_default_name = normalize_translation_profile_name(
            default_translation_profile_name or next(iter(profiles))
        )
        if resolved_default_name not in profiles:
            resolved_default_name = next(iter(profiles))
        return TranslationProviderProfileSet(
            default_profile_name=resolved_default_name,
            profiles=profiles,
        )

    if translation_provider is not None:
        resolved_default_name = normalize_translation_profile_name(
            default_translation_profile_name
        )
        return TranslationProviderProfileSet(
            default_profile_name=resolved_default_name,
            profiles={resolved_default_name: translation_provider},
        )

    return build_env_translation_provider_profiles()



def _download_export(
    state: AppState,
    book_id: int,
    *,
    bilingual: bool,
) -> FileResponse:
    route_result = (
        state.export_routes.download_bilingual(book_id)
        if bilingual
        else state.export_routes.download_zh(book_id)
    )
    if route_result.status_code != 200:
        payload = route_result.payload
        if isinstance(payload, ErrorResponse):
            raise HTTPException(
                status_code=route_result.status_code,
                detail=asdict(payload),
            )
        raise HTTPException(status_code=route_result.status_code, detail="Export failed")

    payload = route_result.payload
    path = getattr(payload, "path", "")
    filename = getattr(payload, "filename", Path(path).name)
    media_type = getattr(payload, "media_type", "application/epub+zip")
    return FileResponse(path=path, filename=filename, media_type=media_type)


def _download_consistency_report(
    state: AppState,
    book_id: int,
    *,
    markdown: bool,
) -> FileResponse:
    try:
        download = state.report_service.get_download(book_id=book_id, markdown=markdown)
    except BookNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "book_not_found", "message": str(exc)},
        ) from exc
    except ConsistencyReportNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "consistency_report_not_ready", "message": str(exc)},
        ) from exc
    except ConsistencyReportServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "consistency_report_failed", "message": str(exc)},
        ) from exc

    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type=download.media_type,
    )



def _route_result_json(route_result: RouteResult[Any]) -> JSONResponse:
    payload = route_result.payload
    if isinstance(payload, ErrorResponse):
        return JSONResponse(status_code=route_result.status_code, content=asdict(payload))
    return JSONResponse(status_code=route_result.status_code, content=asdict(payload))



def _serve_frontend_file(frontend_root: Path, asset_path: str) -> FileResponse:
    frontend_root = frontend_root.resolve()
    requested = (frontend_root / asset_path).resolve()
    if requested.is_dir():
        requested = requested / "index.html"

    try:
        requested.relative_to(frontend_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if requested.exists() and requested.is_file():
        return FileResponse(requested)

    index_file = frontend_root / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Frontend assets are not available.")


app = create_app()








