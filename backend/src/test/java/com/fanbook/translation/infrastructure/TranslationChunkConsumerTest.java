package com.fanbook.translation.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.ChapterRepository;
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
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

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
    BookRepository bookRepository;

    @Autowired
    ChapterRepository chapterRepository;

    @Autowired
    TranslationChunkConsumer consumer;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @Autowired
    PlatformTransactionManager transactionManager;

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
        var completedJob = jobRepository.findById(job.jobId()).orElseThrow();
        assertThat(completedJob.getStatus()).isEqualTo(TranslationJobStatus.COMPLETED);
        assertThat(completedJob.getProgress()).isEqualTo(1.0);
        assertThat(completedJob.getTranslatedSegments()).isEqualTo(3);
        assertThat(chapterRepository.findByBookIdOrderByChapterOrderAsc(book.bookId()).getFirst().getTranslatedSegments())
                .isEqualTo(3);
        assertThat(bookRepository.findById(book.bookId()).orElseThrow().getStatus())
                .isEqualTo(BookStatus.TRANSLATED);
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
    void failedJobMessageIsAckedWithoutPaidProviderRetry() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("missing", "mock-translator"),
                "system"
        );
        var jobEntity = jobRepository.findById(job.jobId()).orElseThrow();
        jobEntity.markFailed("previous chunk exhausted retry budget", java.time.OffsetDateTime.now());
        jobRepository.saveAndFlush(jobEntity);
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        var action = consumer.handleForTest(ChunkMessage.start(job.jobId(), chunk.getId()));

        assertThat(action).isEqualTo(ChunkDeliveryAction.ACK);
        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.PENDING);
        assertThat(publisher.messages()).isEmpty();
    }

    @Test
    void exhaustedMultiSegmentBusinessFailureSplitsChunkAndPublishesChildren() {
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
        assertThat(publisher.messages())
                .hasSize(2)
                .allSatisfy(message -> {
                    assertThat(message.dispatchReason()).isEqualTo("START");
                    assertThat(message.jobId()).isEqualTo(job.jobId());
                });
        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.SUPERSEDED);
        assertThat(chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()))
                .filteredOn(child -> child.getParentChunk() != null && child.getParentChunk().getId().equals(chunk.getId()))
                .hasSize(2)
                .allSatisfy(child -> {
                    assertThat(child.getStatus()).isEqualTo(TranslationChunkStatus.PENDING);
                    assertThat(child.getDegradationDepth()).isEqualTo(1);
                });
        assertThat(jobRepository.findById(job.jobId()).orElseThrow().getStatus())
                .isNotEqualTo(TranslationJobStatus.FAILED);
    }

    @Test
    void exhaustedSingleSegmentBusinessFailureFailsJobWithoutPublishingRetry() {
        var book = bookApplicationService.upload("single.epub", MinimalEpubFactory.create("<p>Hello world.</p>"), "en");
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
        TransactionTemplate committedRead = new TransactionTemplate(transactionManager);
        committedRead.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        publisher.onPublish(message -> committedRead.execute(status -> {
            assertThat(chunkRepository.findById(message.chunkId()))
                    .isPresent()
                    .get()
                    .satisfies(publishedChunk -> {
                        assertThat(publishedChunk.getStatus()).isEqualTo(TranslationChunkStatus.PENDING);
                        assertThat(publishedChunk.getParentChunk().getId()).isEqualTo(chunk.getId());
                    });
            return null;
        }));

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
