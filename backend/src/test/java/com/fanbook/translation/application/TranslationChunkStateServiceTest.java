package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationChunkStateServiceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:chunk_state_service;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/chunk-state-service-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    TranslationChunkStateService stateService;

    @Test
    void acquireMovesPendingChunkToRunningWithLease() {
        var job = createJobWithOneChunk();
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        boolean acquired = stateService.tryAcquire(chunk.getId(), "worker-1");

        var reloaded = chunkRepository.findById(chunk.getId()).orElseThrow();
        assertThat(acquired).isTrue();
        assertThat(reloaded.getStatus().name()).isEqualTo("RUNNING");
        assertThat(reloaded.getAttemptCount()).isEqualTo(1);
        assertThat(reloaded.getLockedUntil()).isAfter(java.time.OffsetDateTime.now());
        assertThat(reloaded.getWorkerId()).isEqualTo("worker-1");
    }

    @Test
    void acquireRejectsUnexpiredRunningChunk() {
        var job = createJobWithOneChunk();
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        assertThat(stateService.tryAcquire(chunk.getId(), "worker-1")).isTrue();

        assertThat(stateService.tryAcquire(chunk.getId(), "worker-2")).isFalse();
    }

    private com.fanbook.translation.api.TranslationJobResponse createJobWithOneChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        return translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
    }
}
