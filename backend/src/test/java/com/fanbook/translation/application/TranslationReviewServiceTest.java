package com.fanbook.translation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.ai.domain.StructuredTranslationResult;
import com.fanbook.ai.infrastructure.MockAiTranslationProvider;
import com.fanbook.book.application.BookApplicationService;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.testsupport.MinimalEpubFactory;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.api.TranslationReviewRequest;
import com.fanbook.translation.domain.ActiveTranslationSessionEntity;
import com.fanbook.translation.domain.TranslationGlossaryCandidateEntity;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationGlossaryCandidateRepository;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
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
class TranslationReviewServiceTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:translation_review_service;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/translation-review-service-storage");
        registry.add("fanbook.ai.provider", () -> "review-capture");
        registry.add("fanbook.translation.max-segments-per-chunk", () -> 10);
    }

    @Autowired
    BookApplicationService bookApplicationService;

    @Autowired
    TranslationJobService translationJobService;

    @Autowired
    TranslationJobExecutor executor;

    @Autowired
    TranslationReviewService reviewService;

    @Autowired
    SegmentRepository segmentRepository;

    @Autowired
    TranslationChunkRepository chunkRepository;

    @Autowired
    ActiveTranslationSessionRepository activeSessionRepository;

    @Autowired
    TranslationGlossaryCandidateRepository glossaryCandidateRepository;

    @Autowired
    CapturingReviewProvider provider;

    @BeforeEach
    void resetProvider() {
        provider.reset();
    }

    @Test
    void previewsRiskSegmentsWithoutCallingProvider() {
        Long bookId = translatedBookWithRiskSegments();

        var response = reviewService.review(
                segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId).getFirst().getBook(),
                new TranslationReviewRequest("review-capture", "review-model", 1, 80, List.of("source_repeated_in_translation"), false)
        );

        assertThat(response.applied()).isFalse();
        assertThat(response.candidateSegments()).isGreaterThanOrEqualTo(1);
        assertThat(response.selectedSegments()).isEqualTo(1);
        assertThat(response.reviewedSegments()).isZero();
        assertThat(provider.reviewCalls()).isZero();
    }

    @Test
    void reviewsOnlyBudgetedRiskSegmentsAndWritesBackChangedTranslations() {
        Long bookId = translatedBookWithRiskSegments();
        var book = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId).getFirst().getBook();

        var response = reviewService.review(
                book,
                new TranslationReviewRequest("review-capture", "review-model", 1, 80, List.of("source_repeated_in_translation"), true)
        );

        assertThat(response.applied()).isTrue();
        assertThat(response.selectedSegments()).isEqualTo(1);
        assertThat(response.reviewedSegments()).isEqualTo(1);
        assertThat(response.updatedSegments()).isEqualTo(1);
        assertThat(provider.reviewCalls()).isEqualTo(1);
        assertThat(provider.lastRequest().items()).hasSize(1);
        assertThat(provider.lastRequest().items().getFirst().warnings()).contains("source_repeated_in_translation");
        assertThat(segmentRepository.findById(response.segments().getFirst().segmentId()).orElseThrow().getTranslatedText())
                .startsWith("[reviewed] ");
    }

    @Test
    void rejectsWriteReviewWhileTranslationSessionIsActiveButAllowsPreview() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create(), "en");
        var job = translationJobService.startWithoutDispatch(book.bookId(), new StartTranslationRequest("review-capture", "review-model"), "system");
        activeSessionRepository.saveAndFlush(new ActiveTranslationSessionEntity(book.bookId(), job.jobId()));
        assertThat(activeSessionRepository.findById(book.bookId())).isPresent();

        var entity = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId()).getFirst().getBook();
        var preview = reviewService.review(
                entity,
                new TranslationReviewRequest("review-capture", "review-model", 1, 80, null, false)
        );
        assertThat(preview.applied()).isFalse();

        assertThatThrownBy(() -> reviewService.review(
                entity,
                new TranslationReviewRequest("review-capture", "review-model", 1, 80, null, true)
        ))
                .isInstanceOf(FanbookException.class)
                .hasMessageContaining("active translation");
        assertThat(job.status()).isEqualTo("QUEUED");
    }

    @Test
    void previewUsesAcceptedGlossaryCandidatesWhenSelectingSegments() {
        var book = bookApplicationService.upload("glossary.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Wonderland shimmered softly.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("review-capture", "review-model"),
                "system"
        );
        executor.runJob(job.jobId());
        var segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId());
        segments.get(1).markTranslated("这里没有使用固定地名。");
        segmentRepository.saveAndFlush(segments.get(1));
        glossaryCandidateRepository.saveAndFlush(new TranslationGlossaryCandidateEntity(
                segments.getFirst().getBook(),
                "Wonderland",
                "wonderland",
                "仙境",
                "place",
                "Accepted strict place name.",
                TranslationGlossaryCandidateStatus.ACCEPTED,
                1,
                segments.get(1)
        ));
        provider.reset();
        activeSessionRepository.deleteByJobId(job.jobId());

        var response = reviewService.review(
                segments.getFirst().getBook(),
                new TranslationReviewRequest("review-capture", "review-model", 5, 80, List.of("glossary_term_missing"), false)
        );

        assertThat(response.applied()).isFalse();
        assertThat(response.candidateSegments()).isEqualTo(1);
        assertThat(response.selectedSegments()).isEqualTo(1);
        assertThat(response.segments().getFirst().warnings()).contains("glossary_term_missing");
        assertThat(provider.reviewCalls()).isZero();
    }

    private Long translatedBookWithRiskSegments() {
        var book = bookApplicationService.upload("demo.epub", MinimalEpubFactory.create("""
                <h1>Chapter One</h1>
                <p>Alice went to Wonderland and met a very curious guide.</p>
                <p>The river was quiet under the silver bridge.</p>
                <p>Everything was already acceptable.</p>
                """), "en");
        var job = translationJobService.startWithoutDispatch(
                book.bookId(),
                new StartTranslationRequest("review-capture", "review-model"),
                "system"
        );
        executor.runJob(job.jobId());
        var segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(book.bookId());
        segments.get(1).markTranslated(segments.get(1).getSourceText() + " 爱丽丝去了仙境。");
        segments.get(2).markTranslated("This translation keeps several English words around bridge and river.");
        segments.get(3).markTranslated("这段已经可接受。");
        segmentRepository.saveAll(segments);
        provider.reset();
        activeSessionRepository.deleteByJobId(job.jobId());
        return book.bookId();
    }

    @TestConfiguration
    static class ReviewConfig {
        @Bean
        @Primary
        CapturingReviewProvider capturingReviewProvider() {
            return new CapturingReviewProvider();
        }

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

    static class CapturingReviewProvider extends MockAiTranslationProvider {
        private int reviewCalls;
        private StructuredTranslationReviewRequest lastRequest;

        @Override
        public String name() {
            return "review-capture";
        }

        @Override
        public StructuredTranslationResult reviewTranslations(StructuredTranslationReviewRequest request, String modelName) {
            reviewCalls++;
            lastRequest = request;
            return super.reviewTranslations(request, modelName);
        }

        int reviewCalls() {
            return reviewCalls;
        }

        StructuredTranslationReviewRequest lastRequest() {
            return lastRequest;
        }

        void reset() {
            reviewCalls = 0;
            lastRequest = null;
        }
    }
}
