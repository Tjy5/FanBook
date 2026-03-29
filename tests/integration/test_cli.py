from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

from backend.api.app import create_app
from backend.api.schemas.provider import ProviderConfigRequest
from backend.cli import main
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
    <dc:title>CLI Sample Book</dc:title>
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


def write_epub(path: Path) -> Path:
    path.write_bytes(build_epub_bytes())
    return path


def parse_kv_output(text: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip()
    return payload


class FailingProvider(TranslationProvider):
    default_model_name = "failing-v1"

    @property
    def name(self) -> str:
        return "failing"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise RuntimeError("synthetic failure")


class RecordingProvider(TranslationProvider):
    default_model_name = "recording-v1"

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


def test_cli_translate_status_and_export_workflow() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "sample.epub")

        def app_factory(*, runtime_root=None):
            return create_app(
                runtime_root=runtime_root,
                translation_provider=ProviderConfigRequest(provider_name="mock"),
            )

        stdout = StringIO()
        stderr = StringIO()
        exit_code = main(
            ["translate", str(epub_path), "--runtime-root", str(runtime_root)],
            out=stdout,
            err=stderr,
            app_factory=app_factory,
        )

        assert exit_code == 0
        assert stderr.getvalue() == ""
        translate_output = parse_kv_output(stdout.getvalue())
        book_id = int(translate_output["book_id"])
        assert translate_output["command"] == "translate"
        assert translate_output["final_status"] == "completed"
        assert Path(translate_output["export.zh"]).exists()
        assert Path(translate_output["export.bilingual"]).exists()
        assert Path(translate_output["report.consistency_report"]).exists()

        status_stdout = StringIO()
        status_exit_code = main(
            ["status", str(book_id), "--runtime-root", str(runtime_root)],
            out=status_stdout,
            err=StringIO(),
            app_factory=app_factory,
        )

        assert status_exit_code == 0
        status_output = parse_kv_output(status_stdout.getvalue())
        assert status_output["job_status"] == "completed"
        assert status_output["can_resume"] == "no"
        assert status_output["artifact.zh.status"] == "ready"
        assert status_output["artifact.bilingual.status"] == "ready"
        assert status_output["artifact.consistency_report.status"] == "ready"

        export_stdout = StringIO()
        export_exit_code = main(
            ["export", str(book_id), "--runtime-root", str(runtime_root), "--kind", "all"],
            out=export_stdout,
            err=StringIO(),
            app_factory=app_factory,
        )

        assert export_exit_code == 0
        export_output = parse_kv_output(export_stdout.getvalue())
        assert Path(export_output["export.zh"]).exists()
        assert Path(export_output["export.bilingual"]).exists()
        assert Path(export_output["report.consistency_report"]).exists()
    finally:
        cleanup_root(root)


def test_cli_interactive_menu_can_translate_then_exit() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "menu-sample.epub")

        def app_factory(*, runtime_root=None):
            return create_app(
                runtime_root=runtime_root,
                translation_provider=ProviderConfigRequest(provider_name="mock"),
            )

        stdout = StringIO()
        stderr = StringIO()
        stdin = StringIO(f"1\n{epub_path}\n1\n3\n1\n\n5\n")
        exit_code = main(
            ["--runtime-root", str(runtime_root)],
            out=stdout,
            err=stderr,
            inp=stdin,
            app_factory=app_factory,
        )

        assert exit_code == 0
        assert stderr.getvalue() == ""
        output = stdout.getvalue()
        parsed = parse_kv_output(output)
        assert "Fanbook CLI" in output
        assert "新手模式" in output
        assert parsed["command"] == "translate"
        assert parsed["final_status"] == "completed"
        assert Path(parsed["export.zh"]).exists()
        assert Path(parsed["export.bilingual"]).exists()
        assert parsed["selected_export_kind"] == "books"
        assert "report.consistency_report" not in parsed
        assert "已退出。" in output
    finally:
        cleanup_root(root)


def test_cli_interactive_menu_can_choose_profile_model_and_save_bilingual_next_to_source() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "menu-profile.epub")

        def app_factory(*, runtime_root=None):
            return create_app(
                runtime_root=runtime_root,
                translation_provider_profiles={
                    "fast": ProviderConfigRequest(provider_name="mock", model_name="fast-default"),
                    "cheap": ProviderConfigRequest(provider_name="mock", model_name="cheap-default"),
                },
                default_translation_profile_name="fast",
            )

        stdout = StringIO()
        stderr = StringIO()
        stdin = StringIO(f"1\n{epub_path}\n2\n2\nmenu-model\n2\n2\n\n5\n")
        exit_code = main(
            ["--runtime-root", str(runtime_root)],
            out=stdout,
            err=stderr,
            inp=stdin,
            app_factory=app_factory,
        )

        assert exit_code == 0
        assert stderr.getvalue() == ""
        parsed = parse_kv_output(stdout.getvalue())
        assert parsed["command"] == "translate"
        assert parsed["provider_profile_name"] == "cheap"
        assert parsed["model_name"] == "menu-model"
        assert parsed["selected_export_kind"] == "bilingual"
        assert parsed["final_status"] == "completed"
        assert "export.zh" not in parsed
        assert Path(parsed["export.bilingual"]).exists()
        assert Path(parsed["saved.export.bilingual"]).exists()
        assert Path(parsed["saved.export.bilingual"]).parent == epub_path.resolve().parent
    finally:
        cleanup_root(root)


def test_cli_interactive_menu_can_show_status_and_export() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "menu-status.epub")

        def app_factory(*, runtime_root=None):
            return create_app(
                runtime_root=runtime_root,
                translation_provider=ProviderConfigRequest(provider_name="mock"),
            )

        create_stdout = StringIO()
        create_exit_code = main(
            ["translate", str(epub_path), "--runtime-root", str(runtime_root)],
            out=create_stdout,
            err=StringIO(),
            app_factory=app_factory,
        )
        assert create_exit_code == 0

        menu_stdout = StringIO()
        menu_stderr = StringIO()
        menu_stdin = StringIO("2\n1\n\n4\n1\n4\n\n5\n")
        menu_exit_code = main(
            ["--runtime-root", str(runtime_root)],
            out=menu_stdout,
            err=menu_stderr,
            inp=menu_stdin,
            app_factory=app_factory,
        )

        assert menu_exit_code == 0
        assert menu_stderr.getvalue() == ""
        output = menu_stdout.getvalue()
        parsed = parse_kv_output(output)
        assert "查看进度 - 请选择书籍" in output
        assert "导出结果 - 请选择书籍" in output
        assert parsed["job_status"] == "completed"
        assert parsed["artifact.zh.status"] == "ready"
        assert parsed["command"] == "export"
        assert Path(parsed["export.zh"]).exists()
        assert Path(parsed["export.bilingual"]).exists()
        assert Path(parsed["report.consistency_report"]).exists()
    finally:
        cleanup_root(root)


def test_cli_interactive_menu_can_choose_profile_and_model_for_resume() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "menu-resume.epub")

        def app_factory(*, runtime_root=None):
            app = create_app(
                runtime_root=runtime_root,
                translation_provider_profiles={
                    "broken": ProviderConfigRequest(provider_name="failing"),
                    "recovery": ProviderConfigRequest(provider_name="recording", model_name="recovery-default"),
                },
                default_translation_profile_name="broken",
            )
            app.state.fanbook.provider_factory._providers["failing"] = FailingProvider
            app.state.fanbook.provider_factory._providers["recording"] = RecordingProvider
            return app

        failed_stdout = StringIO()
        failed_stderr = StringIO()
        failed_exit_code = main(
            ["translate", str(epub_path), "--runtime-root", str(runtime_root)],
            out=failed_stdout,
            err=failed_stderr,
            app_factory=app_factory,
        )

        assert failed_exit_code == 4
        failed_output = parse_kv_output(failed_stdout.getvalue())
        assert failed_output["final_status"] == "failed"

        menu_stdout = StringIO()
        menu_stderr = StringIO()
        menu_stdin = StringIO("3\n1\n2\n2\nresume-model\n1\n1\n\n5\n")
        menu_exit_code = main(
            ["--runtime-root", str(runtime_root)],
            out=menu_stdout,
            err=menu_stderr,
            inp=menu_stdin,
            app_factory=app_factory,
        )

        assert menu_exit_code == 0
        assert menu_stderr.getvalue() == ""
        parsed = parse_kv_output(menu_stdout.getvalue())
        assert parsed["command"] == "resume"
        assert parsed["provider_profile_name"] == "recovery"
        assert parsed["provider_name"] == "recording"
        assert parsed["model_name"] == "resume-model"
        assert parsed["selected_export_kind"] == "zh"
        assert parsed["final_status"] == "completed"
        assert Path(parsed["export.zh"]).exists()
        assert "export.bilingual" not in parsed
    finally:
        cleanup_root(root)


def test_cli_can_resume_after_failed_translation() -> None:
    root = make_root()
    try:
        runtime_root = root / "runtime"
        epub_path = write_epub(root / "resume.epub")

        def app_factory(*, runtime_root=None):
            app = create_app(
                runtime_root=runtime_root,
                translation_provider=ProviderConfigRequest(provider_name="failing"),
            )
            app.state.fanbook.provider_factory._providers["failing"] = FailingProvider
            app.state.fanbook.provider_factory._providers["recording"] = RecordingProvider
            return app

        failed_stdout = StringIO()
        failed_stderr = StringIO()
        failed_exit_code = main(
            ["translate", str(epub_path), "--runtime-root", str(runtime_root)],
            out=failed_stdout,
            err=failed_stderr,
            app_factory=app_factory,
        )

        assert failed_exit_code == 4
        failed_output = parse_kv_output(failed_stdout.getvalue())
        book_id = int(failed_output["book_id"])
        assert failed_output["final_status"] == "failed"
        assert failed_output["can_resume"] == "yes"
        assert "error:" in failed_stderr.getvalue()

        resume_stdout = StringIO()
        resume_stderr = StringIO()
        resume_exit_code = main(
            [
                "resume",
                str(book_id),
                "--runtime-root",
                str(runtime_root),
                "--provider",
                "recording",
                "--model",
                "resume-model",
            ],
            out=resume_stdout,
            err=resume_stderr,
            app_factory=app_factory,
        )

        assert resume_exit_code == 0
        assert resume_stderr.getvalue() == ""
        resume_output = parse_kv_output(resume_stdout.getvalue())
        assert resume_output["command"] == "resume"
        assert resume_output["provider_name"] == "recording"
        assert resume_output["model_name"] == "resume-model"
        assert resume_output["final_status"] == "completed"
        assert Path(resume_output["export.zh"]).exists()
        assert Path(resume_output["export.bilingual"]).exists()
    finally:
        cleanup_root(root)
