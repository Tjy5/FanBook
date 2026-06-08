package com.fanbook.export.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.application.TranslationJobExecutor;
import com.fanbook.translation.application.TranslationJobService;
import com.fanbook.translation.domain.TranslationGlossaryCandidateEntity;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import com.fanbook.translation.infrastructure.TranslationGlossaryCandidateRepository;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class ExportServiceIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:export_service;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/export-service-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
        registry.add("fanbook.translation.glossary[0].source-term", () -> "Alice");
        registry.add("fanbook.translation.glossary[0].target-term", () -> "艾丽丝");
        registry.add("fanbook.translation.glossary[0].category", () -> "person");
        registry.add("fanbook.translation.glossary[0].note", () -> "Use this name consistently.");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationJobExecutor translationJobExecutor;

    @Autowired
    ExportService exportService;

    @Autowired
    ConsistencyReportService reportService;

    @Autowired
    StorageService storageService;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    TranslationGlossaryCandidateRepository glossaryCandidateRepository;

    @Test
    void exportsTranslatedBookAfterMockTranslation() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportZh(book.bookId());

        assertThat(artifact.getKind()).isEqualTo(ExportArtifactKind.ZH_EPUB);
        assertThat(artifact.getObjectKey()).isEqualTo("exports/" + book.bookId() + "/zh.epub");
        assertThat(exportService.requireReadyArtifact(book.bookId(), ExportArtifactKind.ZH_EPUB).getId())
                .isEqualTo(artifact.getId());
        Map<String, String> zip = unzipText(storageService.read(artifact.getObjectKey()));
        assertThat(zip.get("OEBPS/chapter1.xhtml")).contains("[zh] Hello world.");
        assertThat(zip.get("OEBPS/chapter1.xhtml")).contains("<title>Chapter One</title>");
    }

    @Test
    void exportsTranslatedBookByLocatorWithoutGlobalTextReplacement() throws Exception {
        var epub = MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Hello world.</p>
                <p>The phrase Hello world. appears inside this sentence.</p>
                """);
        var book = bookApplicationService.upload("demo.epub", epub, "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportZh(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("OEBPS/chapter1.xhtml");
        assertThat(chapter).contains("[zh] Hello world.");
        assertThat(chapter).contains("[zh] The phrase Hello world. appears inside this sentence.");
        assertThat(chapter).doesNotContain("The phrase [zh] Hello world. appears inside this sentence.");
    }

    @Test
    void exportsBilingualBookByInsertingTranslatedSiblingElements() throws Exception {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportBilingual(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("OEBPS/chapter1.xhtml");
        assertThat(chapter).contains("<p>Hello world.</p><p>[zh] Hello world.</p>");
        assertThat(chapter).contains("<p>Alice went to Wonderland.</p><p>[zh] Alice went to Wonderland.</p>");
    }

    @Test
    void exportsHtmlSpineDocumentAfterTranslation() throws Exception {
        var book = bookApplicationService.upload("html.epub", htmlSpineEpub("""
                <h1>Chapter One</h1>
                <p><img src="cover.png"></p>
                <p>Hello <em>bright</em> world.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportZh(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("chapter.html");
        assertThat(chapter).contains("[zh] Hello ");
        assertThat(chapter).contains("<em>bright</em>");
        assertThat(chapter).doesNotContain("[id0]");
    }

    @Test
    void exportsLongParagraphPartsBackIntoOneLocatedElement() throws Exception {
        String longParagraph = longParagraph();
        var epub = MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>%s</p>
                """.formatted(longParagraph));
        var book = bookApplicationService.upload("demo.epub", epub, "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportZh(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("OEBPS/chapter1.xhtml");
        assertThat(chapter).contains("<p>[zh] This sentence gives the parser a natural boundary for semantic splitting.");
        assertThat(chapter).contains("</p>");
        assertThat(chapter).doesNotContain("</p><p>[zh] This sentence gives the parser");
    }

    @Test
    void exportsInlineMarkupByRestoringPlaceholderStructure() throws Exception {
        var epub = MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Hello <em>bright</em> <strong>world</strong> and <a href="https://example.test">Alice</a>.</p>
                """);
        var book = bookApplicationService.upload("demo.epub", epub, "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportZh(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("OEBPS/chapter1.xhtml");
        assertThat(chapter).contains("<em>bright</em>");
        assertThat(chapter).contains("<strong>world</strong>");
        assertThat(chapter).contains("<a href=\"https://example.test\">Alice</a>");
        assertThat(chapter).contains("[zh] Hello ");
        assertThat(chapter).doesNotContain("[id0]");
    }

    @Test
    void exportsBilingualInlineMarkupWithSourceAndTranslatedSiblings() throws Exception {
        var epub = MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Hello <em>bright</em> world.</p>
                """);
        var book = bookApplicationService.upload("demo.epub", epub, "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var artifact = exportService.exportBilingual(book.bookId());

        String chapter = unzipText(storageService.read(artifact.getObjectKey())).get("OEBPS/chapter1.xhtml");
        assertThat(chapter).contains("<p>Hello <em>bright</em> world.</p><p>[zh] Hello <em>bright</em> world.</p>");
        assertThat(chapter).doesNotContain("[id0]");
    }

    @Test
    void generatesJsonConsistencyReport() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var report = reportService.generateJson(book.bookId());

        String json = new String(storageService.read(report.getObjectKey()), StandardCharsets.UTF_8);
        assertThat(json).contains("\"bookId\":" + book.bookId());
        assertThat(json).contains("\"translatedSegments\":3");
        assertThat(json).contains("\"qualityScore\"");
        assertThat(json).contains("\"segmentScores\"");
        assertThat(json).contains("\"warnings\"");
        assertThat(json).contains("\"termWarnings\"");
        assertThat(json).contains("\"source_repeated_in_translation\"");
        assertThat(json).contains("\"english_residue\"");
        assertThat(json).contains("\"glossary_term_missing\"");
    }

    @Test
    void generatesReportWarningsFromAcceptedGlossaryCandidates() {
        var book = bookApplicationService.upload("accepted-glossary.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Wonderland shimmered softly.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());
        var segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId());
        glossaryCandidateRepository.saveAndFlush(new TranslationGlossaryCandidateEntity(
                segments.getFirst().getBook(),
                "Wonderland",
                "wonderland",
                "仙境",
                "place",
                "Accepted strict place name.",
                TranslationGlossaryCandidateStatus.ACCEPTED,
                1,
                segments.get(1)
        ));

        var report = reportService.generateJson(book.bookId());

        String json = new String(storageService.read(report.getObjectKey()), StandardCharsets.UTF_8);
        assertThat(json).contains("\"glossary_term_missing\"");
        assertThat(json).contains("Wonderland -> 仙境");
    }

    @Test
    void generatesMarkdownConsistencyReportWithWarnings() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        translationJobExecutor.runJob(job.jobId());

        var report = reportService.generateMarkdown(book.bookId());

        String markdown = new String(storageService.read(report.getObjectKey()), StandardCharsets.UTF_8);
        assertThat(markdown).contains("- Warnings:");
        assertThat(markdown).contains("- Quality score:");
        assertThat(markdown).contains("## Segment Scores");
        assertThat(markdown).contains("## Warnings");
        assertThat(markdown).contains("source_repeated_in_translation");
        assertThat(markdown).contains("glossary_term_missing");
    }

    private static Map<String, String> unzipText(byte[] content) throws Exception {
        Map<String, String> result = new HashMap<>();
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(content), StandardCharsets.UTF_8)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!entry.isDirectory()) {
                    result.put(entry.getName(), new String(zip.readAllBytes(), StandardCharsets.UTF_8));
                }
            }
        }
        return result;
    }

    private static String longParagraph() {
        return "This sentence gives the parser a natural boundary for semantic splitting. ".repeat(80).trim();
    }

    private static byte[] htmlSpineEpub(String bodyContent) {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (java.util.zip.ZipOutputStream zip = new java.util.zip.ZipOutputStream(output, StandardCharsets.UTF_8)) {
                entry(zip, "META-INF/container.xml", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                          <rootfiles>
                            <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
                          </rootfiles>
                        </container>
                        """);
                entry(zip, "content.opf", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <package version="2.0" xmlns="http://www.idpf.org/2007/opf">
                          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                            <dc:title>HTML Demo</dc:title>
                          </metadata>
                          <manifest>
                            <item id="chapter" href="chapter.html" media-type="text/html"/>
                          </manifest>
                          <spine>
                            <itemref idref="chapter"/>
                          </spine>
                        </package>
                        """);
                entry(zip, "chapter.html", """
                        <!DOCTYPE html>
                        <html>
                          <head>
                            <meta charset="UTF-8">
                            <link href="book.css" rel="stylesheet" type="text/css">
                          </head>
                          <body>
                            %s
                          </body>
                        </html>
                        """.formatted(bodyContent));
            }
            return output.toByteArray();
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private static void entry(java.util.zip.ZipOutputStream zip, String name, String content) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    @TestConfiguration
    static class LockConfig {
        @Bean
        @Primary
        BookTranslationLock inMemoryBookTranslationLock() {
            return new BookTranslationLock() {
                private final Map<Long, Long> locks = new ConcurrentHashMap<>();

                @Override
                public boolean acquire(Long bookId, Long jobId) {
                    return locks.putIfAbsent(bookId, jobId) == null;
                }

                @Override
                public void release(Long bookId, Long jobId) {
                    locks.remove(bookId, jobId);
                }
            };
        }
    }
}
