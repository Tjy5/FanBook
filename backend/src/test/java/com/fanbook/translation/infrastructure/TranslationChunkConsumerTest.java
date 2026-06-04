package com.fanbook.translation.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.application.ChunkMessage;
import com.fanbook.translation.application.FakeTranslationChunkPublisher;
import com.fanbook.translation.application.TranslationJobService;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
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
class TranslationChunkConsumerTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_chunk_consumer;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-chunk-consumer-storage");
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
    SegmentRepository segmentRepository;

    @Autowired
    TranslationChunkConsumer consumer;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @BeforeEach
    void clearPublisher() {
        publisher.clear();
    }

    @Test
    void consumerCompletesAcquiredChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "mock-translator"),
                "system"
        );
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        var action = consumer.handleForTest(ChunkMessage.start(job.jobId(), chunk.getId()));

        assertThat(action).isEqualTo(ChunkDeliveryAction.ACK);
        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.COMPLETED);
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .allSatisfy(segment -> assertThat(segment.getTranslatedText()).startsWith("[zh] "));
    }

    @Test
    void businessFailurePublishesRetryAfterMarkingChunkFailed() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("missing", "mock-translator"),
                "system"
        );
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        var action = consumer.handleForTest(ChunkMessage.start(job.jobId(), chunk.getId()));

        assertThat(action).isEqualTo(ChunkDeliveryAction.ACK);
        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.FAILED);
        assertThat(publisher.messages())
                .anySatisfy(message -> assertThat(message.dispatchReason()).isEqualTo("RETRY"));
    }

    @Test
    void exhaustedBusinessFailureFailsJobWithoutPublishingRetry() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("missing", "mock-translator"),
                "system"
        );
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        chunk.markRunning(java.time.OffsetDateTime.now());
        chunk.markFailed("provider_not_found", "missing", java.time.OffsetDateTime.now());
        chunk.markRunning(java.time.OffsetDateTime.now());
        chunk.markFailed("provider_not_found", "missing", java.time.OffsetDateTime.now());
        chunkRepository.saveAndFlush(chunk);

        var action = consumer.handleForTest(new ChunkMessage(
                "1.0",
                job.jobId(),
                chunk.getId(),
                3,
                "RETRY",
                "retry-exhausted",
                java.time.OffsetDateTime.now()
        ));

        assertThat(action).isEqualTo(ChunkDeliveryAction.ACK);
        assertThat(publisher.messages()).isEmpty();
        assertThat(jobRepository.findById(job.jobId()).orElseThrow().getStatus())
                .isEqualTo(TranslationJobStatus.FAILED);
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
