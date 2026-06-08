package com.fanbook.translation.application;

import com.fanbook.ai.application.ProviderFactory;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisRequest;
import com.fanbook.ai.domain.StructuredGlossaryAnalysisSourceItem;
import com.fanbook.ai.domain.StructuredGlossaryCandidateItem;
import com.fanbook.ai.domain.TranslationPromptProfile;
import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.api.GlossaryAnalysisRequest;
import com.fanbook.translation.api.GlossaryAnalysisResponse;
import com.fanbook.translation.api.GlossaryCandidateResponse;
import com.fanbook.translation.api.GlossaryImportResponse;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.config.TranslationPromptProperties;
import com.fanbook.translation.domain.TranslationGlossaryCandidateEntity;
import com.fanbook.translation.domain.TranslationGlossaryCandidateStatus;
import com.fanbook.translation.infrastructure.TranslationGlossaryCandidateRepository;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationGlossaryAnalysisService {

    private static final int DEFAULT_MAX_SEGMENTS = 120;
    private static final int HARD_MAX_SEGMENTS = 500;

    private final BookAccessService bookAccessService;
    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final ProviderFactory providerFactory;
    private final TranslationGlossaryCandidateRepository candidateRepository;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final TranslationPromptProperties promptProperties;

    public TranslationGlossaryAnalysisService(
            BookAccessService bookAccessService,
            BookRepository bookRepository,
            SegmentRepository segmentRepository,
            ProviderFactory providerFactory,
            TranslationGlossaryCandidateRepository candidateRepository,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            TranslationPromptProperties promptProperties
    ) {
        this.bookAccessService = bookAccessService;
        this.bookRepository = bookRepository;
        this.segmentRepository = segmentRepository;
        this.providerFactory = providerFactory;
        this.candidateRepository = candidateRepository;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.promptProperties = promptProperties;
    }

    @Transactional
    public GlossaryAnalysisResponse analyzeForCurrentUser(Long bookId, GlossaryAnalysisRequest request) {
        bookAccessService.requireAccessibleBook(bookId);
        return analyze(bookId, request);
    }

    @Transactional
    public GlossaryAnalysisResponse analyze(Long bookId, GlossaryAnalysisRequest request) {
        BookEntity book = bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found."));
        AnalysisOptions options = AnalysisOptions.from(request);
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId).stream()
                .filter(segment -> segment.getSourceText() != null && !segment.getSourceText().isBlank())
                .limit(options.maxSegments())
                .toList();
        List<StructuredGlossaryAnalysisSourceItem> items = segments.stream()
                .map(segment -> new StructuredGlossaryAnalysisSourceItem(segment.getId(), segment.getSourceText()))
                .toList();
        StructuredGlossaryAnalysisRequest providerRequest = new StructuredGlossaryAnalysisRequest(
                book.getSourceLanguage(),
                TranslationRuleSnapshotService.DEFAULT_TARGET_LANGUAGE,
                book.getTitle(),
                "Book glossary analysis",
                promptProfile(request == null ? null : request.promptProfile()),
                TranslationPreservationOptions.defaults(),
                items
        );
        var provider = providerFactory.getProvider(options.providerName());
        var result = provider.analyzeGlossary(providerRequest, options.modelName());
        List<CandidateDraft> drafts = normalize(result.candidates());
        int persisted = 0;
        if (options.persistCandidates()) {
            Map<Long, SegmentEntity> byId = segments.stream().collect(java.util.stream.Collectors.toMap(SegmentEntity::getId, java.util.function.Function.identity()));
            for (CandidateDraft draft : drafts) {
                upsertCandidate(book, byId.get(draft.segmentId()), draft);
                persisted++;
            }
        }
        List<GlossaryCandidateResponse> responses = options.persistCandidates()
                ? candidateRepository.findByBookIdAndStatusInOrderByIdAsc(
                        bookId,
                        List.of(
                                TranslationGlossaryCandidateStatus.CANDIDATE,
                                TranslationGlossaryCandidateStatus.ACCEPTED,
                                TranslationGlossaryCandidateStatus.CONFLICT
                        )
                ).stream().map(this::toResponse).toList()
                : drafts.stream().map(this::toResponse).toList();
        return new GlossaryAnalysisResponse(
                bookId,
                provider.name(),
                result.modelName(),
                items.size(),
                drafts.size(),
                persisted,
                responses
        );
    }

    @Transactional
    public GlossaryImportResponse acceptCandidatesForCurrentUser(Long bookId) {
        bookAccessService.requireAccessibleBook(bookId);
        List<TranslationGlossaryCandidateEntity> candidates = candidateRepository.findByBookIdAndStatusInOrderByIdAsc(
                bookId,
                List.of(TranslationGlossaryCandidateStatus.CANDIDATE, TranslationGlossaryCandidateStatus.CONFLICT)
        );
        int accepted = 0;
        int conflicts = 0;
        for (TranslationGlossaryCandidateEntity candidate : candidates) {
            if (candidate.getStatus() == TranslationGlossaryCandidateStatus.CONFLICT) {
                conflicts++;
                continue;
            }
            candidate.markAccepted();
            accepted++;
        }
        return new GlossaryImportResponse(
                bookId,
                accepted,
                conflicts,
                candidates.stream().map(this::toResponse).toList()
        );
    }

    private void upsertCandidate(BookEntity book, SegmentEntity segment, CandidateDraft draft) {
        boolean conflict = conflictsWithConfiguredGlossary(draft);
        candidateRepository.findFirstByBookIdAndSourceNormOrderByIdAsc(book.getId(), draft.sourceNorm())
                .ifPresentOrElse(
                        existing -> {
                            existing.mergeEvidence(draft.targetTerm(), draft.category(), draft.note(), segment);
                            if (conflict && existing.getStatus() != TranslationGlossaryCandidateStatus.ACCEPTED) {
                                existing.markConflict();
                            }
                        },
                        () -> candidateRepository.save(new TranslationGlossaryCandidateEntity(
                                book,
                                draft.sourceTerm(),
                                draft.sourceNorm(),
                                draft.targetTerm(),
                                draft.category(),
                                draft.note(),
                                conflict ? TranslationGlossaryCandidateStatus.CONFLICT : TranslationGlossaryCandidateStatus.CANDIDATE,
                                1,
                                segment
                        ))
                );
    }

    private boolean conflictsWithConfiguredGlossary(CandidateDraft draft) {
        if (draft.targetTerm() == null || draft.targetTerm().isBlank()) {
            return false;
        }
        return chunkPlanningProperties.glossary().stream()
                .filter(item -> TranslationGlossaryMerger.key(item.sourceTerm()).equals(draft.sourceNorm()))
                .anyMatch(item -> item.targetTerm() != null
                        && !item.targetTerm().isBlank()
                        && !item.targetTerm().trim().equals(draft.targetTerm()));
    }

    private List<CandidateDraft> normalize(List<StructuredGlossaryCandidateItem> rawCandidates) {
        Map<String, CandidateDraft> byKey = new LinkedHashMap<>();
        for (StructuredGlossaryCandidateItem raw : rawCandidates == null ? List.<StructuredGlossaryCandidateItem>of() : rawCandidates) {
            String source = value(raw.sourceTerm());
            if (source.isBlank() || source.length() > 256) {
                continue;
            }
            String key = TranslationGlossaryMerger.key(source);
            byKey.putIfAbsent(key, new CandidateDraft(
                    source,
                    key,
                    blankToNull(raw.targetTerm()),
                    blankToNull(raw.category()),
                    blankToNull(raw.note()),
                    raw.segmentId()
            ));
        }
        return List.copyOf(byKey.values());
    }

    private TranslationPromptProfile promptProfile(com.fanbook.translation.api.StartTranslationRequest.TranslationPromptProfileRequest request) {
        if (request == null) {
            return new TranslationPromptProfile(
                    promptProperties.name(),
                    promptProperties.version(),
                    promptProperties.styleInstruction(),
                    promptProperties.translationInstruction(),
                    promptProperties.reviewInstruction(),
                    promptProperties.analysisInstruction(),
                    promptProperties.preserveFormatting()
            );
        }
        return new TranslationPromptProfile(
                valueOrFallback(request.name(), promptProperties.name()),
                valueOrFallback(request.version(), promptProperties.version()),
                valueOrFallback(request.styleInstruction(), promptProperties.styleInstruction()),
                valueOrFallback(request.translationInstruction(), promptProperties.translationInstruction()),
                valueOrFallback(request.reviewInstruction(), promptProperties.reviewInstruction()),
                valueOrFallback(request.analysisInstruction(), promptProperties.analysisInstruction()),
                request.preserveFormatting() == null ? promptProperties.preserveFormatting() : request.preserveFormatting()
        );
    }

    private GlossaryCandidateResponse toResponse(TranslationGlossaryCandidateEntity candidate) {
        return new GlossaryCandidateResponse(
                candidate.getId(),
                candidate.getSourceTerm(),
                candidate.getTargetTerm(),
                candidate.getCategory(),
                candidate.getNote(),
                candidate.getStatus().name(),
                candidate.getEvidenceCount(),
                candidate.getFirstSegment() == null ? null : candidate.getFirstSegment().getId()
        );
    }

    private GlossaryCandidateResponse toResponse(CandidateDraft candidate) {
        return new GlossaryCandidateResponse(
                null,
                candidate.sourceTerm(),
                candidate.targetTerm(),
                candidate.category(),
                candidate.note(),
                TranslationGlossaryCandidateStatus.CANDIDATE.name(),
                1,
                candidate.segmentId()
        );
    }

    private static String value(String value) {
        return value == null ? "" : value.trim();
    }

    private static String blankToNull(String value) {
        String trimmed = value(value);
        return trimmed.isBlank() ? null : trimmed;
    }

    private static String valueOrFallback(String value, String fallback) {
        String trimmed = value(value);
        return trimmed.isBlank() ? fallback : trimmed;
    }

    private record AnalysisOptions(
            String providerName,
            String modelName,
            int maxSegments,
            boolean persistCandidates
    ) {
        static AnalysisOptions from(GlossaryAnalysisRequest request) {
            int maxSegments = request == null || request.maxSegments() == null ? DEFAULT_MAX_SEGMENTS : request.maxSegments();
            if (maxSegments < 0 || maxSegments > HARD_MAX_SEGMENTS) {
                throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.BAD_REQUEST, "maxSegments must be between 0 and " + HARD_MAX_SEGMENTS + ".");
            }
            return new AnalysisOptions(
                    valueOrFallback(request == null ? null : request.providerName(), "mock"),
                    valueOrFallback(request == null ? null : request.modelName(), "mock-translator"),
                    maxSegments,
                    request != null && Boolean.TRUE.equals(request.persistCandidates())
            );
        }
    }

    private record CandidateDraft(
            String sourceTerm,
            String sourceNorm,
            String targetTerm,
            String category,
            String note,
            Long segmentId
    ) {
    }
}
