from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import Callable, Sequence, TextIO

if os.name != "nt":
    import termios
    import tty

from backend.api.app import AppState, create_app
from backend.api.schemas.provider import ProviderConfigRequest
from backend.config.env_provider import normalize_translation_profile_name
from backend.domain.enums import ExportArtifactKind, TranslationJobStatus
from backend.jobs.runner import (
    BackgroundTranslationHandle,
    BackgroundTranslationRequest,
    BackgroundTranslationSnapshot,
)
from backend.jobs.resume_service import ResumeState
from backend.services.book_service import (
    BookDetail,
    BookNotFoundError,
    CreatedBook,
    InvalidBookUploadError,
)
from backend.services.export_service import (
    ExportPreconditionError,
    ExportServiceError,
)
from backend.services.report_service import (
    ConsistencyReportNotReadyError,
    ConsistencyReportServiceError,
)

AppFactory = Callable[..., object]
TERMINAL_JOB_STATUSES = {
    TranslationJobStatus.COMPLETED,
    TranslationJobStatus.FAILED,
    TranslationJobStatus.CANCELED,
}
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_REVERSE = "\033[7m"


class CliError(Exception):
    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CliUsageError(CliError):
    exit_code = 2


class CliCommandError(CliError):
    exit_code = 3


class CliExecutionError(CliError):
    exit_code = 4


@dataclass(slots=True, frozen=True)
class MenuOption:
    key: str
    label: str
    description: str = ""
    value: str | int | None = None
    tone: str = "info"


@dataclass(slots=True, frozen=True)
class WaitResult:
    detail: BookDetail
    snapshot: BackgroundTranslationSnapshot | None
    resume_state: ResumeState


@dataclass(slots=True, frozen=True)
class InteractiveExportPlan:
    kind: str
    copy_dir: Path | None = None
    filename_hint: str | None = None


@dataclass(slots=True)
class FanbookCliFacade:
    state: AppState

    @property
    def book_service(self):
        return self.state.book_routes.book_service

    @property
    def export_service(self):
        return self.state.export_routes.export_service

    def list_books(self):
        try:
            return self.state.database.list_books()
        except Exception as exc:
            raise CliExecutionError(f"Failed to list books: {exc}") from exc

    def create_book_from_path(
        self,
        epub_path: str | Path,
        *,
        title: str | None = None,
        source_language: str = "en",
    ) -> CreatedBook:
        path = Path(epub_path)
        if not path.exists():
            raise CliUsageError(f"EPUB file was not found: {path}")
        if not path.is_file():
            raise CliUsageError(f"EPUB path is not a file: {path}")
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise CliUsageError(f"Failed to read EPUB file '{path}': {exc}") from exc
        try:
            return self.book_service.create_book(
                filename=path.name,
                content=content,
                title=title,
                source_language=source_language,
            )
        except InvalidBookUploadError as exc:
            raise CliUsageError(str(exc)) from exc
        except Exception as exc:
            raise CliExecutionError(f"Failed to create book from '{path}': {exc}") from exc

    def get_book_detail(self, book_id: int) -> BookDetail:
        try:
            return self.book_service.get_book(int(book_id))
        except BookNotFoundError as exc:
            raise CliCommandError(str(exc)) from exc
        except Exception as exc:
            raise CliExecutionError(f"Failed to load book '{book_id}': {exc}") from exc

    def inspect_resume(self, book_id: int) -> ResumeState:
        try:
            return self.state.resume_service.inspect(
                int(book_id),
                runner=self.state.translation_runner,
            )
        except Exception as exc:
            raise CliExecutionError(f"Failed to inspect resumable state for book '{book_id}': {exc}") from exc

    def resolve_provider(
        self,
        *,
        profile_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        runtime_profile: str | None = None,
    ) -> tuple[str, ProviderConfigRequest]:
        resolved_profile_name = self.state.default_translation_profile_name
        if profile_name:
            requested_profile_name = normalize_translation_profile_name(profile_name)
            provider = self.state.translation_provider_profiles.get(requested_profile_name)
            if provider is None:
                raise CliUsageError(f"Translation profile '{profile_name}' does not exist.")
            resolved_profile_name = requested_profile_name
        else:
            provider = self.state.translation_provider
        merged_provider = provider.merged_with(
            provider_name=provider_name,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            runtime_profile=runtime_profile,
        )
        self._ensure_supported_provider(merged_provider.provider_name)
        self._ensure_provider_is_configured(merged_provider)
        return resolved_profile_name, merged_provider

    def start_translation(
        self,
        *,
        book_id: int,
        provider_profile_name: str,
        provider: ProviderConfigRequest,
    ) -> BackgroundTranslationHandle:
        try:
            return self.state.translation_runner.start(
                BackgroundTranslationRequest(
                    book_id=int(book_id),
                    provider_profile_name=provider_profile_name,
                    provider_name=provider.provider_name,
                    model_name=provider.model_name,
                    provider_options=provider.options_dict(),
                )
            )
        except Exception as exc:
            raise CliExecutionError(f"Failed to start translation for book '{book_id}': {exc}") from exc

    def start_resume(
        self,
        *,
        book_id: int,
        provider_profile_name: str,
        provider: ProviderConfigRequest,
    ) -> BackgroundTranslationHandle:
        if self.state.translation_runner.has_active_job(int(book_id)):
            return self.start_translation(
                book_id=book_id,
                provider_profile_name=provider_profile_name,
                provider=provider,
            )
        resume_state = self.inspect_resume(int(book_id))
        if not resume_state.can_resume:
            raise CliCommandError(f"Book '{book_id}' does not have resumable work.")
        return self.start_translation(
            book_id=book_id,
            provider_profile_name=provider_profile_name,
            provider=provider,
        )

    def wait_for_job(
        self,
        *,
        book_id: int,
        job_id: int,
        poll_interval: float,
        out: TextIO,
    ) -> WaitResult:
        normalized_interval = max(0.1, float(poll_interval))
        last_marker: tuple[str, float, int, int, int] | None = None
        while True:
            detail = self.get_book_detail(book_id)
            job = detail.current_job
            if job is None:
                raise CliExecutionError(f"Book '{book_id}' does not have an active translation job.")
            snapshot = self.state.translation_runner.get_snapshot(job.id)
            translated_segments = snapshot.translated_segments if snapshot is not None else 0
            total_segments = snapshot.total_segments if snapshot is not None else 0
            failed_segments = snapshot.failed_segments if snapshot is not None else 0
            marker = (
                job.status.value,
                round(float(job.progress), 4),
                translated_segments,
                total_segments,
                failed_segments,
            )
            if marker != last_marker:
                _write_kv(
                    out,
                    {
                        "job_status": job.status.value,
                        "progress": _format_progress(job.progress),
                        "translated_segments": f"{translated_segments}/{total_segments}",
                        "failed_segments": str(failed_segments),
                    },
                )
                last_marker = marker
            if job.status in TERMINAL_JOB_STATUSES:
                return WaitResult(
                    detail=detail,
                    snapshot=snapshot,
                    resume_state=self.inspect_resume(book_id),
                )
            self.state.translation_runner.wait(job_id, timeout=normalized_interval)

    def collect_export_paths(
        self,
        *,
        book_id: int,
        kind: str,
    ) -> list[tuple[str, str]]:
        outputs: list[tuple[str, str]] = []
        normalized_kind = kind.strip().lower()
        if normalized_kind in {"zh", "books", "all"}:
            outputs.append(
                (
                    "export.zh",
                    self._get_export_path(book_id, ExportArtifactKind.ZH),
                )
            )
        if normalized_kind in {"bilingual", "books", "all"}:
            outputs.append(
                (
                    "export.bilingual",
                    self._get_export_path(book_id, ExportArtifactKind.BILINGUAL),
                )
            )
        if normalized_kind in {"consistency_report", "all"}:
            outputs.append(
                (
                    "report.consistency_report",
                    self._get_report_path(book_id, markdown=False),
                )
            )
            markdown_path = self._try_get_report_path(book_id, markdown=True)
            if markdown_path is not None:
                outputs.append(
                    (
                        "report.consistency_report_markdown",
                        markdown_path,
                    )
                )
        if not outputs:
            raise CliUsageError(f"Unsupported export kind '{kind}'.")
        return outputs

    def _get_export_path(
        self,
        book_id: int,
        kind: ExportArtifactKind,
    ) -> str:
        try:
            download = self.export_service.get_export_download(book_id=int(book_id), kind=kind)
        except BookNotFoundError as exc:
            raise CliCommandError(str(exc)) from exc
        except ExportPreconditionError as exc:
            raise CliCommandError(str(exc)) from exc
        except ExportServiceError as exc:
            raise CliExecutionError(str(exc)) from exc
        except Exception as exc:
            raise CliExecutionError(f"Failed to export '{kind.value}' for book '{book_id}': {exc}") from exc
        return download.path

    def _get_report_path(self, book_id: int, *, markdown: bool) -> str:
        try:
            return self.state.report_service.get_download(
                book_id=int(book_id),
                markdown=markdown,
            ).path
        except BookNotFoundError as exc:
            raise CliCommandError(str(exc)) from exc
        except ConsistencyReportNotReadyError as exc:
            raise CliCommandError(str(exc)) from exc
        except ConsistencyReportServiceError as exc:
            raise CliExecutionError(str(exc)) from exc
        except Exception as exc:
            raise CliExecutionError(
                f"Failed to load consistency report for book '{book_id}': {exc}"
            ) from exc

    def _try_get_report_path(self, book_id: int, *, markdown: bool) -> str | None:
        try:
            return self._get_report_path(book_id, markdown=markdown)
        except CliCommandError:
            return None

    def _ensure_supported_provider(self, provider_name: str) -> None:
        normalized_name = provider_name.strip().lower()
        if normalized_name not in self.state.provider_factory.available_providers():
            raise CliUsageError(f"Provider '{provider_name}' is not supported.")

    @staticmethod
    def _ensure_provider_is_configured(provider: ProviderConfigRequest) -> None:
        normalized_name = provider.provider_name.strip().lower()
        if normalized_name == "openai" and not (provider.api_key or "").strip():
            raise CliCommandError(
                "The selected translation provider requires an API key. Configure it in .env or pass --api-key."
            )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fanbook",
        description="Fanbook command line workflow for EPUB translation.",
    )
    parser.add_argument(
        "--runtime-root",
        default=None,
        help="Directory used for runtime data, storage, and checkpoints.",
    )
    subparsers = parser.add_subparsers(dest="command")

    runtime_parent = argparse.ArgumentParser(add_help=False)
    runtime_parent.add_argument(
        "--runtime-root",
        default=None,
        help="Directory used for runtime data, storage, and checkpoints.",
    )

    provider_parent = argparse.ArgumentParser(add_help=False)
    provider_parent.add_argument("--profile", default=None, help="Translation profile name override.")
    provider_parent.add_argument("--provider", dest="provider_name", default=None, help="Provider name override.")
    provider_parent.add_argument("--model", dest="model_name", default=None, help="Model name override.")
    provider_parent.add_argument("--api-key", dest="api_key", default=None, help="Provider API key override.")
    provider_parent.add_argument("--base-url", dest="base_url", default=None, help="Provider base URL override.")
    provider_parent.add_argument(
        "--runtime-profile",
        dest="runtime_profile",
        default=None,
        help="Runtime profile override.",
    )

    translate_parser = subparsers.add_parser(
        "translate",
        parents=[runtime_parent, provider_parent],
        help="Create a book from an EPUB file and run translation.",
    )
    translate_parser.add_argument("epub_path", help="Path to the EPUB file.")
    translate_parser.add_argument("--title", default=None, help="Optional book title override.")
    translate_parser.add_argument(
        "--source-language",
        default="en",
        help="Source language metadata stored with the book.",
    )
    translate_parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between status refreshes while waiting.",
    )
    translate_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Accepted for compatibility; the current in-process runner still waits to avoid losing work.",
    )
    translate_parser.set_defaults(handler=_handle_translate)

    resume_parser = subparsers.add_parser(
        "resume",
        parents=[runtime_parent, provider_parent],
        help="Resume translation for an existing book.",
    )
    resume_parser.add_argument("book_id", type=int, help="Book id.")
    resume_parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between status refreshes while waiting.",
    )
    resume_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Accepted for compatibility; the current in-process runner still waits to avoid losing work.",
    )
    resume_parser.set_defaults(handler=_handle_resume)

    status_parser = subparsers.add_parser(
        "status",
        parents=[runtime_parent],
        help="Show the current state for a book.",
    )
    status_parser.add_argument("book_id", type=int, help="Book id.")
    status_parser.set_defaults(handler=_handle_status)

    export_parser = subparsers.add_parser(
        "export",
        parents=[runtime_parent],
        help="Build or fetch export files for a translated book.",
    )
    export_parser.add_argument("book_id", type=int, help="Book id.")
    export_parser.add_argument(
        "--kind",
        choices=("zh", "bilingual", "consistency_report", "all"),
        default="all",
        help="Export artifact kind.",
    )
    export_parser.set_defaults(handler=_handle_export)

    menu_parser = subparsers.add_parser(
        "menu",
        parents=[runtime_parent],
        help="Open the beginner-friendly interactive menu.",
    )
    menu_parser.set_defaults(handler=None)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
    inp: TextIO | None = None,
    app_factory: AppFactory = create_app,
) -> int:
    normalized_argv = list(argv) if argv is not None else list(sys.argv[1:])
    parser = create_parser()
    args = parser.parse_args(normalized_argv)
    stdout = out or sys.stdout
    stderr = err or sys.stderr
    stdin = inp or sys.stdin
    try:
        app = app_factory(runtime_root=getattr(args, "runtime_root", None))
        state = getattr(getattr(app, "state", None), "fanbook", None)
        if not isinstance(state, AppState):
            raise CliExecutionError("CLI app factory did not provide a valid fanbook app state.")
        facade = FanbookCliFacade(state=state)
        if getattr(args, "handler", None) is None:
            return _run_interactive_menu(facade=facade, out=stdout, err=stderr, inp=stdin)
        return int(args.handler(args, facade, stdout, stderr))
    except CliError as exc:
        print(f"error: {exc.message}", file=stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("error: interrupted while waiting for the translation job.", file=stderr)
        return 130


def _handle_translate(
    args: argparse.Namespace,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
) -> int:
    created = facade.create_book_from_path(
        args.epub_path,
        title=args.title,
        source_language=args.source_language,
    )
    provider_profile_name, provider = facade.resolve_provider(
        profile_name=args.profile,
        provider_name=args.provider_name,
        model_name=args.model_name,
        api_key=args.api_key,
        base_url=args.base_url,
        runtime_profile=args.runtime_profile,
    )
    handle = facade.start_translation(
        book_id=created.book.id,
        provider_profile_name=provider_profile_name,
        provider=provider,
    )
    _write_kv(
        out,
        {
            "command": "translate",
            "epub_path": str(Path(args.epub_path).resolve()),
            "book_id": str(created.book.id),
            "job_id": str(handle.job_id),
            "provider_profile_name": provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name or "",
            "status": handle.status,
        },
    )
    return _finalize_translation_command(
        args=args,
        facade=facade,
        out=out,
        err=err,
        book_id=created.book.id,
        handle=handle,
        command_name="translate",
    )


def _handle_resume(
    args: argparse.Namespace,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
) -> int:
    provider_profile_name, provider = facade.resolve_provider(
        profile_name=args.profile,
        provider_name=args.provider_name,
        model_name=args.model_name,
        api_key=args.api_key,
        base_url=args.base_url,
        runtime_profile=args.runtime_profile,
    )
    handle = facade.start_resume(
        book_id=args.book_id,
        provider_profile_name=provider_profile_name,
        provider=provider,
    )
    _write_kv(
        out,
        {
            "command": "resume",
            "book_id": str(handle.book_id),
            "job_id": str(handle.job_id),
            "provider_profile_name": provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name or "",
            "status": handle.status,
        },
    )
    return _finalize_translation_command(
        args=args,
        facade=facade,
        out=out,
        err=err,
        book_id=handle.book_id,
        handle=handle,
        command_name="resume",
    )


def _handle_status(
    args: argparse.Namespace,
    facade: FanbookCliFacade,
    out: TextIO,
    _err: TextIO,
) -> int:
    detail = facade.get_book_detail(args.book_id)
    resume_state = facade.inspect_resume(args.book_id)
    snapshot = (
        facade.state.translation_runner.get_book_snapshot(args.book_id)
        if detail.current_job is not None
        else None
    )
    _write_status_output(
        out,
        detail=detail,
        snapshot=snapshot,
        resume_state=resume_state,
    )
    return 0


def _handle_export(
    args: argparse.Namespace,
    facade: FanbookCliFacade,
    out: TextIO,
    _err: TextIO,
) -> int:
    outputs = facade.collect_export_paths(book_id=args.book_id, kind=args.kind)
    _write_kv(out, {"command": "export", "book_id": str(args.book_id)})
    _write_kv(out, {label: path for label, path in outputs})
    return 0


def _run_interactive_menu(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
    inp: TextIO,
) -> int:
    while True:
        books = facade.list_books()
        resumable_count = sum(1 for book in books if facade.inspect_resume(book.id).can_resume)
        choice = _select_menu_option(
            inp=inp,
            out=out,
            title="Fanbook CLI",
            subtitle="新手模式",
            summary_lines=(
                f"运行目录: {facade.state.runtime_root}",
                f"已有书籍: {len(books)} | 可恢复任务: {resumable_count}",
            ),
            options=(
                MenuOption("1", "翻译一本书", "选择 EPUB 文件，直接翻译到完成", tone="success"),
                MenuOption("2", "查看进度", "查看某本书当前状态、章节进度和产物", tone="info"),
                MenuOption("3", "恢复翻译", "恢复失败或中断的任务", tone="warning"),
                MenuOption("4", "导出结果", "导出纯中文、双语版或一致性报告", tone="success"),
                MenuOption("5", "退出", "离开菜单", tone="error"),
            ),
            prompt="请选择操作 [1-5]: ",
        )
        if choice is None or choice == "5":
            print("已退出。", file=out)
            return 0
        try:
            if choice == "1":
                _run_interactive_translate(facade=facade, out=out, err=err, inp=inp)
            elif choice == "2":
                _run_interactive_status(facade=facade, out=out, inp=inp)
            elif choice == "3":
                _run_interactive_resume(facade=facade, out=out, err=err, inp=inp)
            else:
                _run_interactive_export(facade=facade, out=out, inp=inp)
        except CliError as exc:
            print(f"error: {exc.message}", file=err)
        _pause(inp, out)
        print("", file=out)


def _run_interactive_translate(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
    inp: TextIO,
) -> None:
    epub_path = _prompt_required_text(inp, out, "请输入 EPUB 文件路径: ")
    if epub_path is None:
        print("已取消翻译。", file=out)
        return
    source_path = _validate_cli_epub_path(epub_path)
    provider_selection = _prompt_translation_provider_selection(
        facade=facade,
        out=out,
        inp=inp,
        action_name="翻译一本书",
    )
    if provider_selection is None:
        print("已取消翻译。", file=out)
        return
    export_plan = _prompt_interactive_export_plan(
        out=out,
        inp=inp,
        action_name="翻译一本书",
        filename_hint=source_path.name,
        preferred_copy_dir=source_path.parent,
    )
    if export_plan is None:
        print("已取消翻译。", file=out)
        return
    provider_profile_name, provider = provider_selection
    created = facade.create_book_from_path(source_path)
    handle = facade.start_translation(
        book_id=created.book.id,
        provider_profile_name=provider_profile_name,
        provider=provider,
    )
    _write_kv(
        out,
        {
            "command": "translate",
            "epub_path": str(source_path.resolve()),
            "book_id": str(created.book.id),
            "job_id": str(handle.job_id),
            "provider_profile_name": provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name or "",
            "status": handle.status,
        },
    )
    interactive_args = argparse.Namespace(no_wait=False, poll_interval=0.5)
    _finalize_translation_command(
        args=interactive_args,
        facade=facade,
        out=out,
        err=err,
        book_id=created.book.id,
        handle=handle,
        command_name="translate",
        export_kind=export_plan.kind,
        copy_dir=export_plan.copy_dir,
        filename_hint=export_plan.filename_hint,
    )


def _run_interactive_status(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    inp: TextIO,
) -> None:
    book_id = _prompt_book_selection(
        facade=facade,
        out=out,
        inp=inp,
        action_name="查看进度",
    )
    if book_id is None:
        print("已取消查看。", file=out)
        return
    detail = facade.get_book_detail(book_id)
    resume_state = facade.inspect_resume(book_id)
    snapshot = (
        facade.state.translation_runner.get_book_snapshot(book_id)
        if detail.current_job is not None
        else None
    )
    _write_status_output(
        out,
        detail=detail,
        snapshot=snapshot,
        resume_state=resume_state,
    )


def _run_interactive_resume(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
    inp: TextIO,
) -> None:
    book_id = _prompt_book_selection(
        facade=facade,
        out=out,
        inp=inp,
        action_name="恢复翻译",
        predicate=lambda _detail, resume_state: resume_state.can_resume,
    )
    if book_id is None:
        print("已取消恢复。", file=out)
        return
    provider_selection = _prompt_translation_provider_selection(
        facade=facade,
        out=out,
        inp=inp,
        action_name="恢复翻译",
    )
    if provider_selection is None:
        print("已取消恢复。", file=out)
        return
    detail = facade.get_book_detail(book_id)
    export_plan = _prompt_interactive_export_plan(
        out=out,
        inp=inp,
        action_name="恢复翻译",
        filename_hint=detail.book.filename,
        preferred_copy_dir=None,
    )
    if export_plan is None:
        print("已取消恢复。", file=out)
        return
    provider_profile_name, provider = provider_selection
    handle = facade.start_resume(
        book_id=book_id,
        provider_profile_name=provider_profile_name,
        provider=provider,
    )
    _write_kv(
        out,
        {
            "command": "resume",
            "book_id": str(handle.book_id),
            "job_id": str(handle.job_id),
            "provider_profile_name": provider_profile_name,
            "provider_name": handle.provider_name,
            "model_name": handle.model_name or "",
            "status": handle.status,
        },
    )
    interactive_args = argparse.Namespace(no_wait=False, poll_interval=0.5)
    _finalize_translation_command(
        args=interactive_args,
        facade=facade,
        out=out,
        err=err,
        book_id=handle.book_id,
        handle=handle,
        command_name="resume",
        export_kind=export_plan.kind,
        copy_dir=export_plan.copy_dir,
        filename_hint=export_plan.filename_hint,
    )


def _prompt_translation_provider_selection(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    inp: TextIO,
    action_name: str,
) -> tuple[str, ProviderConfigRequest] | None:
    profiles = tuple(facade.state.translation_provider_profiles.items())
    if not profiles:
        return facade.resolve_provider()

    selected_index = 0
    if len(profiles) > 1:
        default_profile_name = facade.state.default_translation_profile_name
        selected = _select_menu_option(
            inp=inp,
            out=out,
            title=f"{action_name} - 选择配置档",
            subtitle="请选择翻译配置",
            summary_lines=(
                f"当前默认配置档: {default_profile_name}",
                "配置档可切换 provider、默认模型和运行参数。",
            ),
            options=tuple(
                MenuOption(
                    key=str(index),
                    label=(
                        f"{profile_name}（默认）"
                        if profile_name == default_profile_name
                        else profile_name
                    ),
                    description=(
                        f"{provider.provider_name} | 默认模型 "
                        f"{_format_model_label(provider.model_name)}"
                    ),
                    tone=("success" if profile_name == default_profile_name else "info"),
                )
                for index, (profile_name, provider) in enumerate(profiles, start=1)
            ),
            prompt=f"请选择翻译配置 [1-{len(profiles)}]: ",
            allow_cancel=True,
        )
        if selected is None:
            return None
        selected_index = int(selected) - 1

    profile_name, base_provider = profiles[selected_index]
    model_strategy = _select_menu_option(
        inp=inp,
        out=out,
        title=f"{action_name} - 模型设置",
        subtitle="请选择本次任务的模型",
        summary_lines=(
            f"配置档: {profile_name}",
            f"Provider: {base_provider.provider_name}",
            f"默认模型: {_format_model_label(base_provider.model_name)}",
            (
                f"Runtime profile: {base_provider.runtime_profile}"
                if base_provider.runtime_profile
                else "Runtime profile: 自动"
            ),
        ),
        options=(
            MenuOption("1", "使用配置档默认模型", "直接沿用当前配置档的模型设置", tone="success"),
            MenuOption("2", "手动输入模型名称", "只覆盖本次任务，不修改配置档", tone="info"),
        ),
        prompt="请选择模型策略 [1-2]: ",
        allow_cancel=True,
    )
    if model_strategy is None:
        return None
    model_name: str | None = None
    if model_strategy == "2":
        model_input = _prompt_required_text(inp, out, "请输入模型名称: ")
        if model_input is None:
            return None
        model_name = model_input.strip() or None
    return facade.resolve_provider(
        profile_name=profile_name,
        model_name=model_name,
    )


def _prompt_interactive_export_plan(
    *,
    out: TextIO,
    inp: TextIO,
    action_name: str,
    filename_hint: str,
    preferred_copy_dir: Path | None,
) -> InteractiveExportPlan | None:
    export_choice = _select_menu_option(
        inp=inp,
        out=out,
        title=f"{action_name} - 导出设置",
        subtitle="请选择翻译完成后需要保留的结果",
        summary_lines=(
            "中文和双语是两种 EPUB 产物；一致性报告用于排查术语和风格问题。",
        ),
        options=(
            MenuOption("1", "只导出纯中文版", "只生成中文 EPUB", tone="success"),
            MenuOption("2", "只导出双语对照版", "只生成双语 EPUB", tone="info"),
            MenuOption("3", "中文和双语都要", "生成两种 EPUB，不包含报告", tone="success"),
            MenuOption("4", "全部结果", "两种 EPUB 加一致性报告", tone="warning"),
        ),
        prompt="请选择导出结果 [1-4]: ",
        allow_cancel=True,
    )
    if export_choice is None:
        return None
    export_kind = {
        "1": "zh",
        "2": "bilingual",
        "3": "books",
        "4": "all",
    }[export_choice]

    if preferred_copy_dir is not None:
        save_choice = _select_menu_option(
            inp=inp,
            out=out,
            title=f"{action_name} - 保存位置",
            subtitle="请选择结果保存方式",
            summary_lines=(
                f"原书目录: {preferred_copy_dir.resolve()}",
                "运行目录中的内部产物会保留，方便后续查看状态和恢复任务。",
            ),
            options=(
                MenuOption("1", "只保留在运行目录", "适合继续让 CLI 管理这些产物", tone="info"),
                MenuOption("2", "额外复制到原书同目录", "翻译结束后在原 EPUB 旁边放结果文件", tone="success"),
                MenuOption("3", "额外复制到自定义目录", "手动指定另一个输出文件夹", tone="warning"),
            ),
            prompt="请选择保存方式 [1-3]: ",
            allow_cancel=True,
        )
    else:
        save_choice = _select_menu_option(
            inp=inp,
            out=out,
            title=f"{action_name} - 保存位置",
            subtitle="请选择结果保存方式",
            summary_lines=(
                "当前任务无法可靠推断最初导入 EPUB 的外部目录。",
                "如需额外保存到别处，可以手动指定导出目录。",
            ),
            options=(
                MenuOption("1", "只保留在运行目录", "适合继续让 CLI 管理这些产物", tone="info"),
                MenuOption("2", "额外复制到自定义目录", "手动指定另一个输出文件夹", tone="success"),
            ),
            prompt="请选择保存方式 [1-2]: ",
            allow_cancel=True,
        )
    if save_choice is None:
        return None

    copy_dir: Path | None = None
    if preferred_copy_dir is not None and save_choice == "2":
        copy_dir = preferred_copy_dir.resolve()
    elif (preferred_copy_dir is not None and save_choice == "3") or (preferred_copy_dir is None and save_choice == "2"):
        copy_dir_input = _prompt_required_text(inp, out, "请输入导出目录: ")
        if copy_dir_input is None:
            return None
        copy_dir = _prepare_output_directory(copy_dir_input)

    return InteractiveExportPlan(
        kind=export_kind,
        copy_dir=copy_dir,
        filename_hint=filename_hint,
    )


def _run_interactive_export(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    inp: TextIO,
) -> None:
    book_id = _prompt_book_selection(
        facade=facade,
        out=out,
        inp=inp,
        action_name="导出结果",
    )
    if book_id is None:
        print("已取消导出。", file=out)
        return
    choice = _select_menu_option(
        inp=inp,
        out=out,
        title="导出结果",
        subtitle="请选择导出类型",
        options=(
            MenuOption("1", "纯中文版", "只导出中文内容", tone="success"),
            MenuOption("2", "双语对照版", "原文和译文一起导出", tone="info"),
            MenuOption("3", "一致性报告", "导出一致性分析 JSON / Markdown", tone="warning"),
            MenuOption("4", "全部导出", "同时导出所有可用结果", tone="success"),
        ),
        prompt="请选择导出类型 [1-4]: ",
    )
    if choice is None:
        print("已取消导出。", file=out)
        return
    kind_map = {
        "1": "zh",
        "2": "bilingual",
        "3": "consistency_report",
        "4": "all",
    }
    outputs = facade.collect_export_paths(book_id=book_id, kind=kind_map[choice])
    _write_kv(out, {"command": "export", "book_id": str(book_id)})
    _write_kv(out, {label: path for label, path in outputs})


def _finalize_translation_command(
    *,
    args: argparse.Namespace,
    facade: FanbookCliFacade,
    out: TextIO,
    err: TextIO,
    book_id: int,
    handle: BackgroundTranslationHandle,
    command_name: str,
    export_kind: str = "all",
    copy_dir: Path | None = None,
    filename_hint: str | None = None,
) -> int:
    if getattr(args, "no_wait", False):
        print(
            "warning: --no-wait is not supported by the current in-process runner; continuing to wait for completion.",
            file=err,
        )
    wait_result = facade.wait_for_job(
        book_id=book_id,
        job_id=handle.job_id,
        poll_interval=args.poll_interval,
        out=out,
    )
    detail = wait_result.detail
    current_job = detail.current_job
    if current_job is None:
        raise CliExecutionError(f"{command_name} finished without a visible job record for book '{book_id}'.")

    if current_job.status is TranslationJobStatus.COMPLETED:
        outputs = facade.collect_export_paths(book_id=book_id, kind=export_kind)
        _write_kv(
            out,
            {
                "final_status": current_job.status.value,
                "progress": _format_progress(current_job.progress),
                "selected_export_kind": export_kind,
            },
        )
        _write_kv(out, {label: path for label, path in outputs})
        if copy_dir is not None:
            copied_outputs = _copy_outputs_to_directory(
                outputs,
                target_dir=copy_dir,
                filename_hint=filename_hint or f"book-{book_id}.epub",
            )
            _write_kv(out, {"saved_to_directory": str(copy_dir)})
            _write_kv(out, {f"saved.{label}": path for label, path in copied_outputs})
        return 0

    error_summary = current_job.error_summary or wait_result.resume_state.error_summary or ""
    _write_kv(
        out,
        {
            "final_status": current_job.status.value,
            "can_resume": _bool_text(wait_result.resume_state.can_resume),
            "error_summary": error_summary,
        },
    )
    raise CliExecutionError(
        f"{command_name} finished with status '{current_job.status.value}' for book '{book_id}'."
    )


def _write_status_output(
    out: TextIO,
    *,
    detail: BookDetail,
    snapshot: BackgroundTranslationSnapshot | None,
    resume_state: ResumeState,
) -> None:
    book = detail.book
    current_job = detail.current_job
    translated_segments = (
        snapshot.translated_segments
        if snapshot is not None
        else sum(chapter.translated_segments for chapter in detail.chapter_progress)
    )
    total_segments = (
        snapshot.total_segments
        if snapshot is not None
        else sum(chapter.total_segments for chapter in detail.chapter_progress)
    )
    failed_segments = (
        snapshot.failed_segments
        if snapshot is not None
        else sum(chapter.failed_segments for chapter in detail.chapter_progress)
    )
    payload = {
        "book_id": str(book.id),
        "title": book.title,
        "filename": book.filename,
        "source_language": book.source_language,
        "job_id": str(current_job.id) if current_job is not None else "",
        "job_status": current_job.status.value if current_job is not None else "missing",
        "provider_profile_name": (
            current_job.provider_profile_name if current_job is not None and current_job.provider_profile_name else ""
        ),
        "provider_name": current_job.provider_name if current_job is not None and current_job.provider_name else "",
        "model_name": current_job.model_name if current_job is not None and current_job.model_name else "",
        "progress": _format_progress(current_job.progress if current_job is not None else 0.0),
        "translated_segments": f"{translated_segments}/{total_segments}",
        "failed_segments": str(failed_segments),
        "can_resume": _bool_text(resume_state.can_resume),
    }
    _write_kv(out, payload)
    for chapter in detail.chapter_progress:
        print(
            (
                f"chapter.{chapter.chapter_order}: {chapter.chapter_title} | "
                f"translated {chapter.translated_segments}/{chapter.total_segments} | "
                f"failed {chapter.failed_segments}"
            ),
            file=out,
        )
    for artifact in detail.artifacts:
        print(
            f"artifact.{artifact.kind.value}.status: {artifact.status.value}",
            file=out,
        )
        print(
            f"artifact.{artifact.kind.value}.path: {artifact.path or ''}",
            file=out,
        )


def _prompt_book_selection(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
    inp: TextIO,
    action_name: str,
    predicate: Callable[[BookDetail, ResumeState], bool] | None = None,
) -> int | None:
    entries: list[tuple[int, BookDetail, ResumeState]] = []
    for book in facade.list_books():
        detail = facade.get_book_detail(book.id)
        resume_state = facade.inspect_resume(book.id)
        if predicate is not None and not predicate(detail, resume_state):
            continue
        entries.append((book.id, detail, resume_state))
    if not entries:
        _print_notice(out, f"当前没有可用于“{action_name}”的书籍。", tone="warning")
        return None
    if _supports_visual_menu(inp, out):
        visual_options = tuple(
            MenuOption(
                key=str(index),
                label=f"#{book_id} {_truncate(detail.book.title, 28)}",
                description=(
                    f"{detail.book.filename} | "
                    f"{detail.current_job.status.value if detail.current_job is not None else 'missing'}"
                    f"{' | 可恢复' if resume_state.can_resume else ''}"
                ),
                value=book_id,
                tone=("warning" if resume_state.can_resume else "info"),
            )
            for index, (book_id, detail, resume_state) in enumerate(entries, start=1)
        )
        selected = _select_menu_option(
            inp=inp,
            out=out,
            title=action_name,
            subtitle="请选择书籍",
            summary_lines=("按上下方向键选择，回车确认，Esc 返回",),
            options=visual_options,
            prompt=f"请选择书籍 [1-{len(entries)}]: ",
            allow_cancel=True,
        )
        if selected is None:
            return None
        for option in visual_options:
            if option.key == selected:
                return int(option.value) if option.value is not None else None
        return None
    _print_section(out, f"{action_name} - 请选择书籍")
    _render_book_table(entries, out=out)
    print("0. 返回上一级", file=out)
    choice = _prompt_choice(
        inp,
        out,
        f"请选择书籍 [0-{len(entries)}]: ",
        valid_choices={str(i) for i in range(0, len(entries) + 1)},
    )
    if choice is None or choice == "0":
        return None
    return entries[int(choice) - 1][0]


def _select_menu_option(
    *,
    inp: TextIO,
    out: TextIO,
    title: str,
    options: tuple[MenuOption, ...],
    prompt: str,
    subtitle: str | None = None,
    summary_lines: tuple[str, ...] = (),
    allow_cancel: bool = False,
) -> str | None:
    if _supports_visual_menu(inp, out):
        return _select_menu_option_visual(
            inp=inp,
            out=out,
            title=title,
            subtitle=subtitle,
            summary_lines=summary_lines,
            options=options,
            allow_cancel=allow_cancel,
        )
    _print_box_title(out, title, subtitle=subtitle)
    for line in summary_lines:
        print(line, file=out)
    if summary_lines:
        _print_divider(out)
    for option in options:
        prefix = f"{option.key}."
        label = f"{prefix} {option.label}"
        if option.description:
            label = f"{label}   {option.description}"
        print(label, file=out)
    if allow_cancel:
        print("0. 返回上一级", file=out)
    valid_choices = {option.key for option in options}
    if allow_cancel:
        valid_choices.add("0")
    choice = _prompt_choice(inp, out, prompt, valid_choices=valid_choices)
    if allow_cancel and (choice is None or choice == "0"):
        return None
    return choice


def _select_menu_option_visual(
    *,
    inp: TextIO,
    out: TextIO,
    title: str,
    subtitle: str | None,
    summary_lines: tuple[str, ...],
    options: tuple[MenuOption, ...],
    allow_cancel: bool,
) -> str | None:
    selected_index = 0
    while True:
        _render_visual_menu(
            out=out,
            title=title,
            subtitle=subtitle,
            summary_lines=summary_lines,
            options=options,
            selected_index=selected_index,
            allow_cancel=allow_cancel,
        )
        key = _read_tty_key(inp)
        if key in {"up", "k"}:
            selected_index = (selected_index - 1) % len(options)
            continue
        if key in {"down", "j"}:
            selected_index = (selected_index + 1) % len(options)
            continue
        if key in {"enter", "space"}:
            _clear_screen(out)
            return options[selected_index].key
        if allow_cancel and key in {"escape", "q"}:
            _clear_screen(out)
            return None
        if key in {option.key for option in options}:
            _clear_screen(out)
            return key


def _render_visual_menu(
    *,
    out: TextIO,
    title: str,
    subtitle: str | None,
    summary_lines: tuple[str, ...],
    options: tuple[MenuOption, ...],
    selected_index: int,
    allow_cancel: bool,
) -> None:
    _clear_screen(out)
    _print_box_title(out, title, subtitle=subtitle)
    for line in summary_lines:
        print(line, file=out)
    if summary_lines:
        _print_divider(out)
    print(_style("使用 ↑/↓ 选择，Enter 确认", out, color=ANSI_CYAN), file=out)
    if allow_cancel:
        print(_style("按 Esc 或 q 返回上一级", out, color=ANSI_YELLOW), file=out)
    _print_divider(out)
    for index, option in enumerate(options):
        is_selected = index == selected_index
        line = f" {option.key}. {option.label}"
        if option.description:
            line = f"{line}  {option.description}"
        print(_style_menu_line(line, out, tone=option.tone, selected=is_selected), file=out)


def _prompt_choice(
    inp: TextIO,
    out: TextIO,
    prompt: str,
    *,
    valid_choices: set[str],
) -> str | None:
    while True:
        value = _prompt_text(inp, out, prompt)
        if value is None:
            return None
        normalized = value.strip()
        if normalized in valid_choices:
            return normalized
        print("输入无效，请重新输入。", file=out)


def _prompt_required_text(
    inp: TextIO,
    out: TextIO,
    prompt: str,
) -> str | None:
    while True:
        value = _prompt_text(inp, out, prompt)
        if value is None:
            return None
        normalized = value.strip()
        if normalized:
            return normalized
        print("输入不能为空，请重新输入。", file=out)


def _prepare_output_directory(path_text: str | Path) -> Path:
    path = Path(path_text).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CliUsageError(f"Failed to prepare output directory '{path}': {exc}") from exc
    if not path.is_dir():
        raise CliUsageError(f"Output path is not a directory: {path}")
    return path.resolve()


def _copy_outputs_to_directory(
    outputs: list[tuple[str, str]],
    *,
    target_dir: Path,
    filename_hint: str,
) -> list[tuple[str, str]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[tuple[str, str]] = []
    for label, source in outputs:
        source_path = Path(source)
        target_path = _copied_output_path(
            label=label,
            source_path=source_path,
            target_dir=target_dir,
            filename_hint=filename_hint,
        )
        shutil.copy2(source_path, target_path)
        copied.append((label, str(target_path)))
    return copied


def _copied_output_path(
    *,
    label: str,
    source_path: Path,
    target_dir: Path,
    filename_hint: str,
) -> Path:
    stem = Path(filename_hint).stem.strip() or "translated-book"
    if label == "export.zh":
        return target_dir / f"{stem}.zh.epub"
    if label == "export.bilingual":
        return target_dir / f"{stem}.bilingual.epub"
    if label == "report.consistency_report":
        return target_dir / f"{stem}.consistency_report{source_path.suffix or '.json'}"
    if label == "report.consistency_report_markdown":
        return target_dir / f"{stem}.consistency_report{source_path.suffix or '.md'}"
    return target_dir / f"{stem}.{source_path.name}"


def _validate_cli_epub_path(epub_path: str | Path) -> Path:
    path = Path(epub_path)
    if not path.exists():
        raise CliUsageError(f"EPUB file was not found: {path}")
    if not path.is_file():
        raise CliUsageError(f"EPUB path is not a file: {path}")
    return path


def _format_model_label(model_name: str | None) -> str:
    normalized = str(model_name or "").strip()
    return normalized or "Provider 默认值"


def _prompt_text(
    inp: TextIO,
    out: TextIO,
    prompt: str,
) -> str | None:
    print(prompt, end="", file=out, flush=True)
    raw = inp.readline()
    if raw == "":
        return None
    print("", file=out)
    return raw.rstrip("\r\n")


def _pause(inp: TextIO, out: TextIO) -> None:
    print(_style("按回车继续...", out, color=ANSI_CYAN), end="", file=out, flush=True)
    inp.readline()
    print("", file=out)


def _render_interactive_menu(
    *,
    facade: FanbookCliFacade,
    out: TextIO,
) -> None:
    books = facade.list_books()
    resumable_count = 0
    for book in books:
        if facade.inspect_resume(book.id).can_resume:
            resumable_count += 1

    _print_box_title(out, "Fanbook CLI", subtitle="新手模式")
    print(f"运行目录: {facade.state.runtime_root}", file=out)
    print(f"已有书籍: {len(books)} | 可恢复任务: {resumable_count}", file=out)
    _print_divider(out)
    print(f"{_style('[1]', out, color=ANSI_GREEN, bold=True)} 翻译一本书   选择 EPUB 文件，直接翻译到完成", file=out)
    print(f"{_style('[2]', out, color=ANSI_CYAN, bold=True)} 查看进度     查看某本书当前状态、章节进度和产物", file=out)
    print(f"{_style('[3]', out, color=ANSI_YELLOW, bold=True)} 恢复翻译     恢复失败或中断的任务", file=out)
    print(f"{_style('[4]', out, color=ANSI_GREEN, bold=True)} 导出结果     导出纯中文、双语版或一致性报告", file=out)
    print(f"{_style('[5]', out, color=ANSI_RED, bold=True)} 退出         离开菜单", file=out)
    _print_divider(out)


def _render_book_table(
    entries: list[tuple[int, BookDetail, ResumeState]],
    *,
    out: TextIO,
) -> None:
    rows: list[tuple[str, str, str, str, str]] = []
    for index, (book_id, detail, resume_state) in enumerate(entries, start=1):
        current_job = detail.current_job
        job_status = current_job.status.value if current_job is not None else "missing"
        rows.append(
            (
                str(index),
                str(book_id),
                _truncate(detail.book.title, 26),
                job_status,
                "是" if resume_state.can_resume else "否",
            )
        )
    widths = [
        max(len("序号"), *(len(row[0]) for row in rows)),
        max(len("ID"), *(len(row[1]) for row in rows)),
        max(len("书名"), *(len(row[2]) for row in rows)),
        max(len("状态"), *(len(row[3]) for row in rows)),
        max(len("可恢复"), *(len(row[4]) for row in rows)),
    ]
    header = _format_row(("序号", "ID", "书名", "状态", "可恢复"), widths)
    print(header, file=out)
    print(_format_rule(widths), file=out)
    for row in rows:
        print(_format_row(row, widths), file=out)


def _print_box_title(out: TextIO, title: str, *, subtitle: str | None = None) -> None:
    lines = [title]
    if subtitle:
        lines.append(subtitle)
    width = max(len(line) for line in lines) + 4
    print("+" + "-" * width + "+", file=out)
    for line in lines:
        print(f"|  {_style(line, out, bold=True)}{' ' * (width - len(line) - 2)}|", file=out)
    print("+" + "-" * width + "+", file=out)


def _print_section(out: TextIO, title: str) -> None:
    print(_style(title, out, bold=True, color=ANSI_CYAN), file=out)
    _print_divider(out)


def _print_divider(out: TextIO) -> None:
    print("-" * 64, file=out)


def _print_notice(out: TextIO, message: str, *, tone: str = "info") -> None:
    color = {
        "info": ANSI_CYAN,
        "success": ANSI_GREEN,
        "warning": ANSI_YELLOW,
        "error": ANSI_RED,
    }.get(tone, ANSI_CYAN)
    print(_style(message, out, color=color), file=out)


def _format_row(values: tuple[str, str, str, str, str], widths: list[int]) -> str:
    return (
        f"{values[0]:<{widths[0]}}  "
        f"{values[1]:<{widths[1]}}  "
        f"{values[2]:<{widths[2]}}  "
        f"{values[3]:<{widths[3]}}  "
        f"{values[4]:<{widths[4]}}"
    )


def _format_rule(widths: list[int]) -> str:
    return "  ".join("-" * width for width in widths)


def _truncate(value: str, limit: int) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3] + "..."


def _style(
    text: str,
    stream: TextIO,
    *,
    color: str | None = None,
    bold: bool = False,
) -> str:
    if not _supports_ansi(stream):
        return text
    prefix = ""
    if bold:
        prefix += ANSI_BOLD
    if color:
        prefix += color
    if not prefix:
        return text
    return f"{prefix}{text}{ANSI_RESET}"


def _style_menu_line(text: str, stream: TextIO, *, tone: str, selected: bool) -> str:
    color = {
        "info": ANSI_CYAN,
        "success": ANSI_GREEN,
        "warning": ANSI_YELLOW,
        "error": ANSI_RED,
    }.get(tone)
    if not _supports_ansi(stream):
        prefix = "▶ " if selected else "  "
        return prefix + text
    prefix = ANSI_BOLD if selected else ""
    if selected:
        prefix += ANSI_REVERSE
    if color:
        prefix += color
    return f"{prefix}{'▶ ' if selected else '  '}{text}{ANSI_RESET}"


def _supports_ansi(stream: TextIO) -> bool:
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    if not is_tty:
        return False
    return os.getenv("TERM") is not None or os.name == "nt"


def _supports_visual_menu(inp: TextIO, out: TextIO) -> bool:
    return bool(getattr(inp, "isatty", lambda: False)()) and bool(
        getattr(out, "isatty", lambda: False)()
    )


def _clear_screen(out: TextIO) -> None:
    if _supports_ansi(out):
        print("\033[2J\033[H", end="", file=out, flush=True)
        return
    if getattr(out, "isatty", lambda: False)():
        print("\n" * 50, end="", file=out, flush=True)


def _read_tty_key(inp: TextIO) -> str:
    if os.name == "nt":
        import msvcrt

        while True:
            key = msvcrt.getwch()
            if key in {"\x00", "\xe0"}:
                extended = msvcrt.getwch()
                mapping = {
                    "H": "up",
                    "P": "down",
                    "K": "left",
                    "M": "right",
                }
                if extended in mapping:
                    return mapping[extended]
                continue
            if key in {"\r", "\n"}:
                return "enter"
            if key == " ":
                return "space"
            if key == "\x1b":
                return "escape"
            normalized = key.strip().lower()
            if normalized:
                return normalized
    fd = inp.fileno()
    original_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        first = inp.read(1)
        if first in {"\r", "\n"}:
            return "enter"
        if first == " ":
            return "space"
        if first == "\x1b":
            second = inp.read(1)
            if second == "[":
                third = inp.read(1)
                mapping = {
                    "A": "up",
                    "B": "down",
                    "C": "right",
                    "D": "left",
                }
                return mapping.get(third, "escape")
            return "escape"
        normalized = first.strip().lower()
        return normalized or ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_settings)


def _write_kv(stream: TextIO, payload: dict[str, str]) -> None:
    for key, value in payload.items():
        print(f"{key}: {value}", file=stream)


def _format_progress(value: float) -> str:
    return f"{max(0.0, min(1.0, float(value))) * 100:.0f}%"


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
