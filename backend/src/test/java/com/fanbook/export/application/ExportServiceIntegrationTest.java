package com.fanbook.export.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.application.TranslationJobExecutor;
import com.fanbook.translation.application.TranslationJobService;
import java.io.ByteArrayInputStream;
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
        Map<String, String> zip = unzipText(storageService.read(artifact.getObjectKey()));
        assertThat(zip.get("OEBPS/chapter1.xhtml")).contains("[zh] Hello world.");
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
