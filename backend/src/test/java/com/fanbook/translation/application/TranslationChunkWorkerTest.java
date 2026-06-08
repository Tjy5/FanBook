package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.FanbookException;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import java.util.List;
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
class TranslationChunkWorkerTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_chunk_worker;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-chunk-worker-storage");
        registry.add("fanbook.ai.provider", () -> "mock");
        registry.add("fanbook.translation.max-segments-per-chunk", () -> 2);
        registry.add("fanbook.translation.context-window-segments", () -> 2);
        registry.add("fanbook.translation.glossary-candidate-limit", () -> 6);
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
    TranslationChunkRepository chunkRepository;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    TranslationChunkStateService stateService;

    @Autowired
    TranslationChunkWorker worker;

    @Autowired
    CapturingProvider capturingProvider;

    @BeforeEach
    void resetProvider() {
        capturingProvider.reset();
    }

    @Test
    void translatesChunkUsingJobProviderAndModelWithoutCompletingChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "custom-model"),
                "system"
        );
        var chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId());
        var chunk = chunks.getFirst();

        for (TranslationChunkEntity pendingChunk : chunks) {
            execute(pendingChunk);
        }

        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.RUNNING);
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .allSatisfy(segment -> assertThat(segment.getTranslatedText()).startsWith("[zh] "));
    }

    @Test
    void sendsPriorSameChapterTranslationsAsContextForLaterChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("capture", "capture-model"),
                "system"
        );
        List<TranslationChunkEntity> chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId());
        assertThat(chunks).hasSize(2);

        execute(chunks.get(0));
        capturingProvider.clear();
        execute(chunks.get(1));

        StructuredTranslationRequest request = capturingProvider.lastRequest();
        assertThat(request.context())
                .extracting(context -> context.sourceText())
                .containsExactly("Chapter One", "Hello world.");
        assertThat(request.items())
                .extracting(item -> item.sourceText())
                .containsExactly("Alice went to Wonderland.");
        assertThat(request.glossary())
                .anySatisfy(item -> {
                    assertThat(item.sourceTerm()).isEqualTo("Alice");
                    assertThat(item.targetTerm()).isEqualTo("艾丽丝");
                })
                .anySatisfy(item -> assertThat(item.sourceTerm()).isEqualTo("Wonderland"));
    }

    @Test
    void preservesPunctuationOnlySegmentsWithoutProviderOutput() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>?</p>
                <p>Hello world.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("capture", "capture-model"),
                "system"
        );
        TranslationChunkEntity chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        execute(chunk);

        assertThat(capturingProvider.lastRequest().items())
                .extracting(item -> item.sourceText())
                .doesNotContain("?");
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .anySatisfy(segment -> {
                    if ("?".equals(segment.getSourceText())) {
                        assertThat(segment.getTranslatedText()).isEqualTo("?");
                    }
                });
    }

    @Test
    void sendsInlinePlaceholderTemplateAndStoresValidatedTranslation() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Inline alpha <em>bright</em> world.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("capture", "capture-model"),
                "system"
        );
        TranslationChunkEntity chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();

        execute(chunk);

        StructuredTranslationRequest request = capturingProvider.lastRequest();
        assertThat(request.items())
                .extracting(item -> item.sourceText())
                .contains("Inline alpha [id0]bright[id1] world.");
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .anySatisfy(segment -> assertThat(segment.getTranslatedText())
                        .isEqualTo("[zh] Inline alpha [id0]bright[id1] world."));
    }

    @Test
    void rejectsTranslationWhenInlinePlaceholdersAreMissing() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Inline beta <em>bright</em> world.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("capture", "capture-model"),
                "system"
        );
        TranslationChunkEntity chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        capturingProvider.dropInlinePlaceholders();

        assertThat(stateService.tryAcquire(chunk.getId(), "worker-test-" + chunk.getId())).isTrue();
        assertThatThrownBy(() -> worker.execute(chunk.getId()))
                .isInstanceOf(FanbookException.class)
                .hasMessageContaining("Inline placeholder validation failed");
    }

    private void execute(TranslationChunkEntity chunk) {
        assertThat(stateService.tryAcquire(chunk.getId(), "worker-test-" + chunk.getId())).isTrue();
        worker.execute(chunk.getId());
    }

    @TestConfiguration
    static class WorkerConfig {
        @Bean
        @Primary
        CapturingProvider capturingProvider() {
            return new CapturingProvider();
        }
    }

    static class CapturingProvider implements AiTranslationProvider {
        private StructuredTranslationRequest lastRequest;
        private boolean dropInlinePlaceholders;

        @Override
        public String name() {
            return "capture";
        }

        @Override
        public StructuredTranslationResult translateChunk(StructuredTranslationRequest request, String modelName) {
            lastRequest = request;
            List<StructuredTranslationItem> items = request.items().stream()
                    .map(item -> {
                        String translated = "[zh] " + item.sourceText();
                        if (dropInlinePlaceholders) {
                            translated = translated.replaceAll("\\[id\\d+\\]", "");
                        }
                        return new StructuredTranslationItem(item.segmentId(), translated);
                    })
                    .toList();
            return new StructuredTranslationResult(items, name(), modelName);
        }

        StructuredTranslationRequest lastRequest() {
            return lastRequest;
        }

        void clear() {
            lastRequest = null;
        }

        void dropInlinePlaceholders() {
            this.dropInlinePlaceholders = true;
        }

        void reset() {
            lastRequest = null;
            dropInlinePlaceholders = false;
        }
    }
}
