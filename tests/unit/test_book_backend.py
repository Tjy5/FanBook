from io import BytesIO
import shutil
from pathlib import Path
from uuid import uuid4
import zipfile

from backend.api.routes.books import BookRoutes
from backend.api.schemas.book import CreateBookRequest
from backend.domain.enums import ExportArtifactKind, ExportArtifactStatus, SegmentStatus, SegmentType, TranslationJobStatus
from backend.domain.models import ExportArtifact
from backend.services.book_service import BookService, InvalidBookUploadError
from backend.storage.database import FanbookDatabase


RUNTIME_ROOT = Path("temp/.codex_runtime_test")
RUNTIME_ROOT.mkdir(exist_ok=True)


def make_root() -> Path:
    root = RUNTIME_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_service(root: Path) -> BookService:
    database = FanbookDatabase(root / 'data' / 'fanbook.db')
    return BookService(database=database, storage_root=root / 'storage')


def cleanup_root(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def build_epub_bytes(*, missing_container: bool = False, missing_spine: bool = False) -> bytes:
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
  {spine}
</package>
""".format(
        spine='' if missing_spine else '<spine><itemref idref="ch1"/></spine>'
    )
    chapter_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head>
    <title>Chapter One</title>
  </head>
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
    with zipfile.ZipFile(buffer, mode='w') as archive:
        archive.writestr(
            'mimetype',
            'application/epub+zip',
            compress_type=zipfile.ZIP_STORED,
        )
        if not missing_container:
            archive.writestr('META-INF/container.xml', container_xml)
        archive.writestr('OEBPS/content.opf', content_opf)
        archive.writestr('OEBPS/ch1.xhtml', chapter_xhtml)
    return buffer.getvalue()


def test_create_book_persists_upload_and_initial_job() -> None:
    root = make_root()
    try:
        service = build_service(root)
        epub_bytes = build_epub_bytes()

        created = service.create_book(
            filename='demo.epub',
            content=epub_bytes,
        )

        assert created.book.id > 0
        assert created.book.title == 'Sample Book'
        assert created.book.translated_title is None
        assert created.book.title_translation_status == 'pending'
        assert Path(created.book.source_path).read_bytes() == epub_bytes
        job = service.database.get_latest_translation_job(created.book.id)
        assert job is not None
        assert job.status is TranslationJobStatus.PENDING

        chapters = service.database.list_chapters(created.book.id)
        assert len(chapters) == 1
        assert chapters[0].title == 'Chapter 1'
        assert chapters[0].source_doc_path == 'OEBPS/ch1.xhtml'

        segments = service.database.list_segments(chapters[0].id)
        assert [segment.segment_type for segment in segments] == [
            SegmentType.TITLE,
            SegmentType.PARAGRAPH,
            SegmentType.LIST_ITEM,
            SegmentType.FOOTNOTE,
        ]
        paragraph = segments[1]
        assert paragraph.status is SegmentStatus.PENDING
        assert paragraph.extra.doc_path == 'OEBPS/ch1.xhtml'
        assert paragraph.extra.block_path == '/html[1]/body[1]/section[1]/p[1]'
        assert paragraph.extra.slot == 'mixed'
        assert paragraph.extra.parts == [
            {'slot': 'text', 'path': '/html[1]/body[1]/section[1]/p[1]'},
            {'slot': 'text', 'path': '/html[1]/body[1]/section[1]/p[1]/em[1]'},
            {'slot': 'tail', 'path': '/html[1]/body[1]/section[1]/p[1]/em[1]'},
        ]
        assert paragraph.extra.src_digest
    finally:
        cleanup_root(root)


def test_get_book_aggregates_progress_and_artifacts() -> None:
    root = make_root()
    try:
        service = build_service(root)
        created = service.create_book(filename='novel.epub', content=build_epub_bytes())

        chapter = service.database.list_chapters(created.book.id)[0]
        segments = service.database.list_segments(chapter.id)
        segments[0].translated_text = '第一章'
        segments[0].status = SegmentStatus.TRANSLATED
        service.database.upsert_segment(segments[0])

        segments[1].status = SegmentStatus.FAILED
        service.database.upsert_segment(segments[1])

        service.database.upsert_export_artifact(
            ExportArtifact(
                book_id=created.book.id,
                kind=ExportArtifactKind.ZH,
                status=ExportArtifactStatus.PENDING,
            )
        )

        detail = service.get_book(created.book.id)

        assert detail.book.id == created.book.id
        assert detail.current_job is not None
        assert len(detail.chapter_progress) == 1
        assert detail.chapter_progress[0].translated_segments == 1
        assert detail.chapter_progress[0].failed_segments == 1
        assert detail.chapter_progress[0].total_segments == 4
        assert len(detail.artifacts) == 1
    finally:
        cleanup_root(root)


def test_create_book_rejects_invalid_epub_payloads() -> None:
    root = make_root()
    try:
        service = build_service(root)

        try:
            service.create_book(filename='broken.epub', content=b'not-a-zip')
        except InvalidBookUploadError:
            pass
        else:
            raise AssertionError('Expected InvalidBookUploadError for a non-zip EPUB payload.')

        try:
            service.create_book(
                filename='missing-spine.epub',
                content=build_epub_bytes(missing_spine=True),
            )
        except InvalidBookUploadError:
            pass
        else:
            raise AssertionError('Expected InvalidBookUploadError for an EPUB without a spine.')

        uploads_root = service.storage_root / 'uploads'
        assert not uploads_root.exists()
        assert service.database.get_book(1) is None
    finally:
        cleanup_root(root)


def test_routes_return_validation_errors() -> None:
    root = make_root()
    try:
        routes = BookRoutes(build_service(root))

        bad_extension = routes.create_book(
            CreateBookRequest(filename='demo.txt', content=b'not-an-epub')
        )
        empty_upload = routes.create_book(
            CreateBookRequest(filename='demo.epub', content=b'')
        )
        invalid_epub = routes.create_book(
            CreateBookRequest(filename='broken.epub', content=b'not-a-zip')
        )

        assert bad_extension.status_code == 400
        assert getattr(bad_extension.payload, 'code') == 'invalid_upload'
        assert empty_upload.status_code == 400
        assert getattr(empty_upload.payload, 'code') == 'invalid_upload'
        assert invalid_epub.status_code == 400
        assert getattr(invalid_epub.payload, 'code') == 'invalid_upload'
    finally:
        cleanup_root(root)

