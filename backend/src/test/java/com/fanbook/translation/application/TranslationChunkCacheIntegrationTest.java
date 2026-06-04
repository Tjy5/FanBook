package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.ai.infrastructure.MockAiTranslationProvider;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
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
class TranslationChunkCacheIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_chunk_cache;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-chunk-cache-storage");
        registry.add("fanbook.ai.provider", () -> "cache");
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    TranslationChunkStateService stateService;

    @Autowired
    TranslationChunkWorker worker;

    @Autowired
    CountingMockProvider providerSpy;

    @BeforeEach
    void resetProviderSpy() {
        providerSpy.reset();
    }

    @Test
    void secondTranslationOfSameDigestProviderAndModelUsesCache() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");

        executeOnlyChunk(book.bookId());
        executeOnlyChunk(book.bookId());

        assertThat(providerSpy.calls()).isEqualTo(1);
    }

    private void executeOnlyChunk(Long bookId) {
        var job = translationJobService.startWithoutDispatch(
                bookId,
                new StartTranslationRequest("cache-counting", "cache-model"),
                "system"
        );
        var chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId());
        assertThat(chunks).hasSize(1);
        var chunk = chunks.getFirst();
        assertThat(stateService.tryAcquire(chunk.getId(), "cache-test")).isTrue();

        worker.execute(chunk.getId());
    }

    @TestConfiguration
    static class CacheConfig {
        @Bean
        @Primary
        CountingMockProvider countingMockProvider() {
            return new CountingMockProvider();
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
            return "cache-counting";
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
}
