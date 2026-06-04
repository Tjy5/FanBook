package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.ai.infrastructure.MockAiTranslationProvider;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.ChunkDeliveryAction;
import com.fanbook.translation.infrastructure.TranslationChunkConsumer;
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
import org.springframework.http.HttpStatus;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class TranslationMessagingAcceptanceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_messaging_acceptance;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-messaging-acceptance-storage");
        registry.add("fanbook.ai.provider", () -> "acceptance");
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
    TranslationChunkConsumer consumer;

    @Autowired
    TranslationChunkStateService stateService;

    @Autowired
    TranslationJobAggregator aggregator;

    @Autowired
    CountingMockProvider providerSpy;

    @Autowired
    FakeTranslationChunkPublisher publisher;

    @BeforeEach
    void resetFakes() {
        providerSpy.reset();
        publisher.clear();
    }

    @Test
    void duplicateChunkMessageDoesNotTranslateTwice() {
        Fixture fixture = createJobWithOneChunk("counting");
        ChunkMessage message = ChunkMessage.start(fixture.jobId(), fixture.chunkId());

        assertThat(consumer.handleForTest(message)).isEqualTo(ChunkDeliveryAction.ACK);
        assertThat(consumer.handleForTest(message)).isEqualTo(ChunkDeliveryAction.ACK);

        assertThat(providerSpy.calls()).isEqualTo(1);
    }

    @Test
    void exhaustedChunkFailsJob() {
        Fixture fixture = createJobWithOneChunk("failing");

        consumer.handleForTest(ChunkMessage.start(fixture.jobId(), fixture.chunkId()));
        consumer.handleForTest(new ChunkMessage("1.0", fixture.jobId(), fixture.chunkId(), 2, "RETRY", "retry-2", OffsetDateTime.now()));
        consumer.handleForTest(new ChunkMessage("1.0", fixture.jobId(), fixture.chunkId(), 3, "RETRY", "retry-3", OffsetDateTime.now()));

        assertThat(jobRepository.findById(fixture.jobId()).orElseThrow().getStatus())
                .isEqualTo(TranslationJobStatus.FAILED);
    }

    @Test
    void canceledJobMessageIsAckedWithoutTranslation() {
        Fixture fixture = createJobWithOneChunk("counting");
        translationJobService.cancel(fixture.jobId());

        assertThat(consumer.handleForTest(ChunkMessage.start(fixture.jobId(), fixture.chunkId())))
                .isEqualTo(ChunkDeliveryAction.ACK);

        assertThat(providerSpy.calls()).isZero();
        assertThat(chunkRepository.findById(fixture.chunkId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.PENDING);
        assertThat(jobRepository.findById(fixture.jobId()).orElseThrow().getStatus())
                .isEqualTo(TranslationJobStatus.CANCELED);
    }

    @Test
    void aggregationDoesNotOverwriteCanceledJob() {
        Fixture fixture = createJobWithOneChunk("counting");
        translationJobService.cancel(fixture.jobId());
        stateService.markCompleted(fixture.chunkId());

        aggregator.aggregate(fixture.jobId());

        assertThat(jobRepository.findById(fixture.jobId()).orElseThrow().getStatus())
                .isEqualTo(TranslationJobStatus.CANCELED);
    }

    private Fixture createJobWithOneChunk(String providerName) {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest(providerName, "mock-translator"),
                "system"
        );
        var chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId());
        assertThat(chunks).hasSize(1);
        return new Fixture(job.jobId(), chunks.getFirst().getId());
    }

    private record Fixture(Long jobId, Long chunkId) {
    }

    @TestConfiguration
    static class AcceptanceConfig {
        @Bean
        @Primary
        CountingMockProvider countingMockProvider() {
            return new CountingMockProvider();
        }

        @Bean
        FailingProvider failingProvider() {
            return new FailingProvider();
        }

        @Bean
        @Primary
        FakeTranslationChunkPublisher fakeTranslationChunkPublisher() {
            return new FakeTranslationChunkPublisher();
        }
    }

    static class CountingMockProvider extends MockAiTranslationProvider {
        private int calls;

        @Override
        public String name() {
            return "counting";
        }

        @Override
        public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
            calls++;
            return super.translateChunk(request, modelName);
        }

        int calls() {
            return calls;
        }

        void reset() {
            calls = 0;
        }
    }

    static class FailingProvider extends MockAiTranslationProvider {
        @Override
        public String name() {
            return "failing";
        }

        @Override
        public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
            throw new FanbookException(ErrorCode.PROVIDER_NOT_CONFIGURED, HttpStatus.BAD_GATEWAY, "provider failed");
        }
    }
}
