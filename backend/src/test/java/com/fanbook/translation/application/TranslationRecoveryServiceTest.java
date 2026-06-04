package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.ActiveTranslationSessionEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationRecoveryServiceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_recovery_service;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-recovery-service-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    TranslationJobRepository jobRepository;

    @Autowired
    ActiveTranslationSessionRepository activeSessionRepository;

    @Autowired
    TranslationChunkStateService stateService;

    @Autowired
    TranslationRecoveryService recoveryService;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @BeforeEach
    void clearPublisher() {
        publisher.clear();
    }

    @Test
    void recoveryPublishesExpiredRunningChunk() {
        var job = createJobWithOneChunk();
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        stateService.tryAcquire(chunk.getId(), "worker-1");
        stateService.forceLeaseExpiredForTest(chunk.getId());

        recoveryService.recoverStaleChunks();

        assertThat(publisher.messages()).anySatisfy(message -> assertThat(message.dispatchReason()).isEqualTo("RECOVERY"));
    }

    @Test
    void cleanupDeletesCanceledSessionOnlyAfterRunningChunksFinish() {
        var job = createJobWithOneChunk();
        activeSessionRepository.saveAndFlush(new ActiveTranslationSessionEntity(job.bookId(), job.jobId()));
        var jobEntity = jobRepository.findById(job.jobId()).orElseThrow();
        jobEntity.markCanceled(OffsetDateTime.now());
        jobRepository.saveAndFlush(jobEntity);
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        stateService.tryAcquire(chunk.getId(), "worker-1");

        recoveryService.cleanupStaleSessions();

        assertThat(activeSessionRepository.findById(job.bookId())).isPresent();

        stateService.markCompleted(chunk.getId());
        recoveryService.cleanupStaleSessions();

        assertThat(activeSessionRepository.findById(job.bookId())).isEmpty();
    }

    private com.fanbook.translation.api.TranslationJobResponse createJobWithOneChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        return translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
    }

    @TestConfiguration
    static class PublisherConfig {
        @Bean
        @Primary
        FakeTranslationChunkPublisher fakeTranslationChunkPublisher() {
            return new FakeTranslationChunkPublisher();
        }
    }
}
