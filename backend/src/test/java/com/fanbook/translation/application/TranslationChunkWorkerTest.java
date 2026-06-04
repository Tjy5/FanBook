package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
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

    @Test
    void translatesChunkUsingJobProviderAndModelWithoutCompletingChunk() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("mock", "custom-model"),
                "system"
        );
        var chunk = chunkRepository.findByJobIdOrderByChunkOrderAsc(job.jobId()).getFirst();
        assertThat(stateService.tryAcquire(chunk.getId(), "worker-test")).isTrue();

        worker.execute(chunk.getId());

        assertThat(chunkRepository.findById(chunk.getId()).orElseThrow().getStatus())
                .isEqualTo(TranslationChunkStatus.RUNNING);
        assertThat(segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()))
                .allSatisfy(segment -> assertThat(segment.getTranslatedText()).startsWith("[zh] "));
    }
}
