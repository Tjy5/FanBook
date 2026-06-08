package com.fanbook.translation.application;

import com.fanbook.ai.application.ProviderFactory;
import com.fanbook.ai.application.StructuredTranslationValidator;
import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationReviewItem;
import com.fanbook.ai.domain.StructuredTranslationReviewRequest;
import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.application.SegmentInlineMarkup;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.api.TranslationReviewResponse;
import com.fanbook.translation.api.TranslationReviewSegmentResponse;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationReviewService {

    private static final int DEFAULT_MAX_SEGMENTS = 20;
    private static final int HARD_MAX_SEGMENTS = 100;
    private static final int DEFAULT_MIN_SCORE = 80;
    private static final List<String> DEFAULT_WARNING_CODES = List.of(
            "source_repeated_in_translation",
            "english_residue",
            "suspicious_length_ratio",
            "glossary_term_missing",
            "preserved_token_missing",
            "placeholder_mismatch"
    );

    private final BookAccessService bookAccessService;
    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final ProviderFactory providerFactory;
    private final StructuredTranslationValidator validator;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final ActiveTranslationSessionRepository activeSessionRepository;
    private final TranslationRuleSnapshotService ruleSnapshotService;
    private final TranslationQualityAnalyzer qualityAnalyzer = new TranslationQualityAnalyzer();
    private final TranslationGlossaryBuilder glossaryBuilder = new TranslationGlossaryBuilder();

    public TranslationReviewService(
            BookAccessService bookAccessService,
            BookRepository bookRepository,
            SegmentRepository segmentRepository,
            ProviderFactory providerFactory,
            StructuredTranslationValidator validator,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            ActiveTranslationSessionRepository activeSessionRepository,
            TranslationRuleSnapshotService ruleSnapshotService
    ) {
        this.bookAccessService = bookAccessService;
        this.bookRepository = bookRepository;
        this.segmentRepository = segmentRepository;
        this.providerFactory = providerFactory;
        this.validator = validator;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.activeSessionRepository = activeSessionRepository;
        this.ruleSnapshotService = ruleSnapshotService;
    }

    @Transactional
    public TranslationReviewResponse reviewForCurrentUser(
            Long bookId,
            com.fanbook.translation.api.TranslationReviewRequest request
    ) {
        BookEntity book = bookAccessService.requireAccessibleBook(bookId);
        return review(book, request);
    }

    @Transactional
    public TranslationReviewResponse review(
            BookEntity book,
            com.fanbook.translation.api.TranslationReviewRequest request
    ) {
        Long bookId = book.getId();
        BookEntity managedBook = bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(
                        ErrorCode.BOOK_NOT_FOUND,
                        HttpStatus.NOT_FOUND,
                        "Book '" + bookId + "' was not found."
                ));
        ReviewOptions options = ReviewOptions.from(request);
        if (options.applyChanges() && activeSessionRepository.existsById(bookId)) {
            throw new FanbookException(
                    ErrorCode.BOOK_TRANSLATION_IN_PROGRESS,
                    HttpStatus.CONFLICT,
                    "Book already has active translation."
            );
        }
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        TranslationRuleSnapshotData snapshot = ruleSnapshotService.dataForBook(managedBook);
        var analysis = qualityAnalyzer.analyze(segments, snapshot.glossary(), snapshot.preservation());
        Map<Long, TranslationQualityAnalyzer.SegmentQualityScore> scoreBySegmentId = analysis.segmentScores().stream()
                .collect(Collectors.toMap(TranslationQualityAnalyzer.SegmentQualityScore::segmentId, Function.identity()));
        List<ReviewCandidate> candidates = segments.stream()
                .map(segment -> candidate(segment, scoreBySegmentId.get(segment.getId()), options.warningCodes()))
                .flatMap(List::stream)
                .filter(candidate -> candidate.score() < options.minScore() || hasSelectedWarning(candidate.warnings(), options.warningCodes()))
                .sorted(Comparator
                        .comparingInt(ReviewCandidate::score)
                        .thenComparing((ReviewCandidate candidate) -> -candidate.warnings().size())
                        .thenComparing(ReviewCandidate::originalOrder))
                .toList();
        List<ReviewCandidate> selected = candidates.stream()
                .limit(options.maxSegments())
                .toList();
        if (!options.applyChanges() || selected.isEmpty()) {
            return response(bookId, options, candidates.size(), selected, List.of(), Map.of());
        }

        List<StructuredTranslationReviewItem> items = selected.stream()
                .map(candidate -> new StructuredTranslationReviewItem(
                        candidate.segment().getId(),
                        SegmentInlineMarkup.providerSourceText(candidate.segment()),
                        candidate.segment().getTranslatedText(),
                        candidate.score(),
                        candidate.warnings()
                ))
                .toList();
        List<StructuredTranslationGlossaryItem> glossary = glossary(managedBook, items, snapshot);
        StructuredTranslationReviewRequest providerRequest = new StructuredTranslationReviewRequest(
                managedBook.getSourceLanguage(),
                snapshot.targetLanguage(),
                managedBook.getTitle(),
                "Selected risk segments",
                snapshot.promptProfile(),
                snapshot.preservation(),
                glossary,
                items
        );
        var provider = providerFactory.getProvider(options.providerName());
        var result = provider.reviewTranslations(providerRequest, options.modelName());
        List<Long> selectedIds = selected.stream().map(candidate -> candidate.segment().getId()).toList();
        validator.validate(selectedIds, result);
        Map<Long, StructuredTranslationItem> reviewedById = result.items().stream()
                .collect(Collectors.toMap(StructuredTranslationItem::segmentId, Function.identity()));
        Map<Long, Boolean> updatedById = selected.stream()
                .collect(Collectors.toMap(candidate -> candidate.segment().getId(), candidate -> {
                    String reviewed = reviewedById.get(candidate.segment().getId()).translatedText().trim();
                    validateInlinePlaceholders(candidate.segment(), reviewed);
                    boolean changed = !reviewed.equals(candidate.segment().getTranslatedText());
                    candidate.segment().markTranslated(reviewed);
                    return changed;
        }));
        segmentRepository.saveAll(selected.stream().map(ReviewCandidate::segment).toList());
        return response(bookId, options, candidates.size(), selected, selectedIds, updatedById);
    }

    private List<StructuredTranslationGlossaryItem> glossary(
            BookEntity book,
            List<StructuredTranslationReviewItem> items,
            TranslationRuleSnapshotData snapshot
    ) {
        List<String> texts = new ArrayList<>();
        texts.add(book.getTitle());
        items.forEach(item -> {
            texts.add(item.sourceText());
            texts.add(item.translatedText());
        });
        return glossaryBuilder.build(
                snapshot.glossary(),
                texts,
                chunkPlanningProperties.glossaryCandidateLimit()
        );
    }

    private static List<ReviewCandidate> candidate(
            SegmentEntity segment,
            TranslationQualityAnalyzer.SegmentQualityScore score,
            Set<String> selectedWarningCodes
    ) {
        if (segment.getStatus() != SegmentStatus.TRANSLATED
                || segment.getTranslatedText() == null
                || segment.getTranslatedText().isBlank()
                || score == null) {
            return List.of();
        }
        List<String> reviewableWarnings = score.reasons().stream()
                .filter(DEFAULT_WARNING_CODES::contains)
                .filter(reason -> selectedWarningCodes.isEmpty() || selectedWarningCodes.contains(reason))
                .toList();
        if (score.score() >= 100 && reviewableWarnings.isEmpty()) {
            return List.of();
        }
        return List.of(new ReviewCandidate(segment, score.score(), reviewableWarnings, score.reasons(), segment.getId()));
    }

    private static boolean hasSelectedWarning(List<String> warnings, Set<String> selectedWarningCodes) {
        if (selectedWarningCodes.isEmpty()) {
            return false;
        }
        return warnings.stream().anyMatch(selectedWarningCodes::contains);
    }

    private static TranslationReviewResponse response(
            Long bookId,
            ReviewOptions options,
            int candidateSegments,
            List<ReviewCandidate> selected,
            List<Long> reviewedIds,
            Map<Long, Boolean> updatedById
    ) {
        Set<Long> reviewed = Set.copyOf(reviewedIds);
        List<TranslationReviewSegmentResponse> segmentResponses = selected.stream()
                .map(candidate -> new TranslationReviewSegmentResponse(
                        candidate.segment().getId(),
                        candidate.segment().getSegmentOrder(),
                        candidate.score(),
                        candidate.allReasons(),
                        reviewed.contains(candidate.segment().getId()),
                        updatedById.getOrDefault(candidate.segment().getId(), false)
                ))
                .toList();
        int updated = (int) updatedById.values().stream().filter(Boolean::booleanValue).count();
        return new TranslationReviewResponse(
                bookId,
                options.providerName(),
                options.modelName(),
                options.applyChanges(),
                options.minScore(),
                options.maxSegments(),
                List.copyOf(options.warningCodes()),
                candidateSegments,
                selected.size(),
                reviewedIds.size(),
                updated,
                segmentResponses
        );
    }

    private record ReviewCandidate(
            SegmentEntity segment,
            int score,
            List<String> warnings,
            List<String> allReasons,
            Long originalOrder
    ) {
    }

    private record ReviewOptions(
            String providerName,
            String modelName,
            int maxSegments,
            int minScore,
            Set<String> warningCodes,
            boolean applyChanges
    ) {
        private static ReviewOptions from(com.fanbook.translation.api.TranslationReviewRequest request) {
            String providerName = value(request == null ? null : request.providerName(), "mock");
            String modelName = value(request == null ? null : request.modelName(), "mock-translator");
            int maxSegments = value(request == null ? null : request.maxSegments(), DEFAULT_MAX_SEGMENTS);
            int minScore = value(request == null ? null : request.minScore(), DEFAULT_MIN_SCORE);
            if (maxSegments < 0 || maxSegments > HARD_MAX_SEGMENTS) {
                throw new FanbookException(
                        ErrorCode.INVALID_REQUEST,
                        HttpStatus.BAD_REQUEST,
                        "maxSegments must be between 0 and " + HARD_MAX_SEGMENTS + "."
                );
            }
            if (minScore < 0 || minScore > 100) {
                throw new FanbookException(
                        ErrorCode.INVALID_REQUEST,
                        HttpStatus.BAD_REQUEST,
                        "minScore must be between 0 and 100."
                );
            }
            Set<String> warningCodes = request == null || request.warningCodes() == null
                    ? new LinkedHashSet<>(DEFAULT_WARNING_CODES)
                    : request.warningCodes().stream()
                    .filter(code -> code != null && !code.isBlank())
                    .collect(Collectors.toCollection(LinkedHashSet::new));
            boolean applyChanges = request == null || request.applyChanges() == null || request.applyChanges();
            return new ReviewOptions(providerName, modelName, maxSegments, minScore, warningCodes, applyChanges);
        }

        private static String value(String candidate, String fallback) {
            return candidate == null || candidate.isBlank() ? fallback : candidate;
        }

        private static int value(Integer candidate, int fallback) {
            return candidate == null ? fallback : candidate;
        }
    }

    private static void validateInlinePlaceholders(SegmentEntity segment, String translated) {
        SegmentInlineMarkup.PlaceholderValidation validation = SegmentInlineMarkup.validateTranslatedText(
                translated,
                segment.getLocatorJson()
        );
        if (!validation.valid()) {
            throw new FanbookException(
                    ErrorCode.STRUCTURED_OUTPUT_INVALID,
                    HttpStatus.BAD_GATEWAY,
                    "Inline placeholder validation failed for segment '" + segment.getId() + "': " + validation.message()
            );
        }
    }
}
