from io import BytesIO
import shutil
from pathlib import Path
from uuid import uuid4
import zipfile

from backend.api.routes.exports import ExportRoutes
from backend.domain.enums import ExportArtifactKind, ExportArtifactStatus, SegmentStatus
from backend.services.book_service import BookService
from backend.services.export_service import ExportService
from backend.services.translation_service import TranslationService
from backend.storage.artifact_store import ArtifactStore
from backend.storage.database import FanbookDatabase


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
      <h1 id="chapter-title">Chapter 1</h1>
      <p id="paragraph-1">Hello <em id="emphasis-1">world</em>.</p>
      <ol><li id="list-item-1">First item</li></ol>
      <aside epub:type="footnote" id="footnote-1">Footnote text</aside>
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


def build_services(root: Path) -> tuple[BookService, TranslationService, ExportService]:
    database = FanbookDatabase(root / "data" / "fanbook.db")
    storage_root = root / "storage"
    return (
        BookService(database=database, storage_root=storage_root),
        TranslationService(database=database),
        ExportService(
            database=database,
            artifact_store=ArtifactStore(storage_root),
        ),
    )


def assign_translated_texts(book_service: BookService, book_id: int) -> None:
    chapter = book_service.database.list_chapters(book_id)[0]
    segments = book_service.database.list_segments(chapter.id)
    replacements = [
        "第一章",
        "你好\n世界\n。",
        "第一项",
        "脚注译文",
    ]
    for segment, translated_text in zip(segments, replacements, strict=True):
        book_service.database.update_segment_translation(
            segment.id,
            translated_text=translated_text,
            status=SegmentStatus.TRANSLATED,
        )


def read_chapter_xhtml(epub_path: str | Path) -> str:
    with zipfile.ZipFile(epub_path, "r") as archive:
        return archive.read("OEBPS/ch1.xhtml").decode("utf-8")


def read_content_opf(epub_path: str | Path) -> str:
    with zipfile.ZipFile(epub_path, "r") as archive:
        return archive.read("OEBPS/content.opf").decode("utf-8")


def test_export_routes_build_ready_zh_and_bilingual_epubs() -> None:
    root = make_root()
    try:
        book_service, translation_service, export_service = build_services(root)
        created = book_service.create_book(
            filename="demo.epub",
            content=build_epub_bytes(),
        )
        translation_service.start_translation(created.book.id)
        assign_translated_texts(book_service, created.book.id)

        routes = ExportRoutes(export_service)
        zh_response = routes.download_zh(created.book.id)
        bilingual_response = routes.download_bilingual(created.book.id)

        assert zh_response.status_code == 200
        assert bilingual_response.status_code == 200

        zh_payload = zh_response.payload
        bilingual_payload = bilingual_response.payload
        assert zh_payload.artifact.kind == ExportArtifactKind.ZH.value
        assert zh_payload.artifact.status == ExportArtifactStatus.READY.value
        assert bilingual_payload.artifact.kind == ExportArtifactKind.BILINGUAL.value
        assert bilingual_payload.artifact.status == ExportArtifactStatus.READY.value
        assert Path(zh_payload.path).exists()
        assert Path(bilingual_payload.path).exists()

        zh_xhtml = read_chapter_xhtml(zh_payload.path)
        bilingual_xhtml = read_chapter_xhtml(bilingual_payload.path)
        zh_opf = read_content_opf(zh_payload.path)
        bilingual_opf = read_content_opf(bilingual_payload.path)

        assert "第一章" in zh_xhtml
        assert "你好" in zh_xhtml
        assert "世界" in zh_xhtml
        assert "第一项" in zh_xhtml
        assert "脚注译文" in zh_xhtml
        assert "ZH: Sample Book" in zh_opf
        assert "Chapter 1" not in zh_xhtml
        assert '<html xmlns="http://www.w3.org/1999/xhtml"' in zh_xhtml
        assert "xmlns:epub=\"http://www.idpf.org/2007/ops\"" in zh_xhtml
        assert "html:p" not in zh_xhtml
        assert "ns1:type" not in zh_xhtml

        assert "Chapter 1" in bilingual_xhtml
        assert "第一章" in bilingual_xhtml
        assert "Hello" in bilingual_xhtml
        assert "你好" in bilingual_xhtml
        assert "First item" in bilingual_xhtml
        assert "第一项" in bilingual_xhtml
        assert "ZH: Sample Book" in bilingual_opf
        assert '<html xmlns="http://www.w3.org/1999/xhtml"' in bilingual_xhtml
        assert "xmlns:epub=\"http://www.idpf.org/2007/ops\"" in bilingual_xhtml
        assert "html:p" not in bilingual_xhtml
        assert "ns1:type" not in bilingual_xhtml
        assert "fanbook-bilingual-source" in bilingual_xhtml
        assert "fanbook-bilingual-translation" in bilingual_xhtml
        assert "data-fanbook-bilingual-style=\"1\"" in bilingual_xhtml
        assert "fanbook-bilingual-source fanbook-bilingual-translation" not in bilingual_xhtml
        assert "fanbook-bilingual-translation fanbook-bilingual-source" not in bilingual_xhtml
        assert bilingual_xhtml.count('id="chapter-title"') == 1
        assert bilingual_xhtml.count('id="paragraph-1"') == 1
        assert bilingual_xhtml.count('id="emphasis-1"') == 1
        assert bilingual_xhtml.count('id="list-item-1"') == 1
        assert bilingual_xhtml.count('id="footnote-1"') == 1
    finally:
        cleanup_root(root)


def test_export_route_rejects_books_with_incomplete_translation() -> None:
    root = make_root()
    try:
        book_service, _, export_service = build_services(root)
        created = book_service.create_book(
            filename="demo.epub",
            content=build_epub_bytes(),
        )
        routes = ExportRoutes(export_service)

        response = routes.download_zh(created.book.id)

        assert response.status_code == 409
        assert getattr(response.payload, "code") == "export_not_ready"
    finally:
        cleanup_root(root)


def test_export_keeps_original_text_when_digest_does_not_match() -> None:
    root = make_root()
    try:
        book_service, translation_service, export_service = build_services(root)
        created = book_service.create_book(
            filename="demo.epub",
            content=build_epub_bytes(),
        )
        translation_service.start_translation(created.book.id)
        assign_translated_texts(book_service, created.book.id)

        chapter = book_service.database.list_chapters(created.book.id)[0]
        segments = book_service.database.list_segments(chapter.id)
        paragraph_segment = segments[1]
        paragraph_segment.extra.src_digest = "broken-digest"
        book_service.database.upsert_segment(paragraph_segment)

        response = ExportRoutes(export_service).download_zh(created.book.id)

        assert response.status_code == 200
        xhtml = read_chapter_xhtml(getattr(response.payload, "path"))
        assert "第一章" in xhtml
        assert "Hello" in xhtml
        assert "你好" not in xhtml
    finally:
        cleanup_root(root)

