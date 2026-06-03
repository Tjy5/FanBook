package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
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
class TranslationJobExecutorIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_job_executor;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-job-executor-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationJobExecutor executor;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    TranslationJobRepository jobRepository;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Test
    void executesQueuedJobWithMockProvider() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );

        executor.runJob(job.jobId());

        var completed = translationJobService.get(job.jobId());
        assertThat(completed.status()).isEqualTo("COMPLETED");
        assertThat(completed.progress()).isEqualTo(1.0);
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .allSatisfy(segment -> {
                    assertThat(segment.getStatus().name()).isEqualTo("TRANSLATED");
                    assertThat(segment.getTranslatedText()).startsWith("[zh] ");
                });
        assertThat(chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()))
                .allSatisfy(chunk -> assertThat(chunk.getStatus()).isEqualTo(TranslationChunkStatus.COMPLETED));
    }

    @Test
    void failsJobWhenFailedChunkExhaustsRetryBudget() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        for (int i = 0; i < 3; i++) {
            OffsetDateTime now = OffsetDateTime.now();
            chunk.markRunning(now);
            chunk.markFailed("provider_request_failed", "boom", now);
        }
        chunkRepository.saveAndFlush(chunk);

        executor.runJob(job.jobId());

        var failedJob = jobRepository.findById(job.jobId()).orElseThrow();
        var exhaustedChunk = chunkRepository.findById(chunk.getId()).orElseThrow();
        assertThat(failedJob.getStatus()).isEqualTo(TranslationJobStatus.FAILED);
        assertThat(failedJob.getErrorSummary()).contains("chunk_retry_exhausted");
        assertThat(exhaustedChunk.getStatus()).isEqualTo(TranslationChunkStatus.FAILED);
        assertThat(exhaustedChunk.getAttemptCount()).isEqualTo(3);
        assertThat(exhaustedChunk.getLastErrorCode()).isEqualTo("chunk_retry_exhausted");
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
