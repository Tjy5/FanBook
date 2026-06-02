package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationResumeServiceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_resume_service;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-resume-service-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationResumeService resumeService;

    @Autowired
    TranslationJobRepository jobRepository;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Test
    void resetsRunningChunksToPendingOnResume() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var jobResponse = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        var job = jobRepository.findById(jobResponse.jobId()).orElseThrow();
        job.markFailed("process interrupted", OffsetDateTime.now());
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.getId()).getFirst();
        chunk.markRunning(OffsetDateTime.now());
        jobRepository.flush();
        chunkRepository.flush();

        var resumed = resumeService.resume(book.bookId());

        assertThat(resumed.status()).isEqualTo("QUEUED");
        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus()).isEqualTo(TranslationChunkStatus.PENDING);
    }

    @Test
    void cancelMarksJobCanceled() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var jobResponse = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );

        var canceled = translationJobService.cancel(jobResponse.jobId());

        assertThat(canceled.status()).isEqualTo("CANCELED");
        assertThat(jobRepository.findById(jobResponse.jobId()).orElseThrow().getStatus()).isEqualTo(TranslationJobStatus.CANCELED);
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
