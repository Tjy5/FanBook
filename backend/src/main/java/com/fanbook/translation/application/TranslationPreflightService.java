package com.fanbook.translation.application;

import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.api.TranslationPreflightResponse;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationPreflightService {

    private final BookAccessService bookAccessService;
    private final SegmentRepository segmentRepository;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final TranslationRuntimeSafetyService runtimeSafetyService;

    public TranslationPreflightService(
            BookAccessService bookAccessService,
            SegmentRepository segmentRepository,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            TranslationRuntimeSafetyService runtimeSafetyService
    ) {
        this.bookAccessService = bookAccessService;
        this.segmentRepository = segmentRepository;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.runtimeSafetyService = runtimeSafetyService;
    }

    @Transactional(readOnly = true)
    public TranslationPreflightResponse preflightForCurrentUser(Long bookId, StartTranslationRequest request) {
        bookAccessService.requireAccessibleBook(bookId);
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        if (segments.isEmpty()) {
            throw new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found.");
        }
        ChunkPlanner planner = new ChunkPlanner(
                chunkPlanningProperties.chunkTargetCharacters(),
                chunkPlanningProperties.maxSegmentsPerChunk()
        );
        int estimatedChunks = planner.plan(segments).size();
        TranslationRuntimeProfile profile = runtimeSafetyService.profile(
                request == null ? null : request.providerName(),
                request == null ? null : request.modelName()
        );
        long estimatedMinimumRuntimeSeconds = profile.realProvider()
                ? estimatedChunks * profile.minRequestIntervalSeconds()
                : 0;
        return new TranslationPreflightResponse(
                bookId,
                profile.providerName(),
                profile.modelName(),
                profile.configured(),
                profile.realProvider(),
                profile.safeToStart(),
                profile.paidSafetyLevel(),
                segments.size(),
                estimatedChunks,
                profile.endpoint(),
                profile.usesChatCompletions(),
                profile.thinkingMode(),
                profile.jsonMode(),
                profile.maxConcurrency(),
                profile.minRequestIntervalSeconds(),
                profile.requestTimeoutSeconds(),
                profile.messagingPrefetch(),
                profile.messagingConcurrency(),
                profile.messagingListenerAutoStartup(),
                profile.chunkTargetCharacters(),
                profile.maxSegmentsPerChunk(),
                profile.maxAttemptsPerChunk(),
                estimatedMinimumRuntimeSeconds,
                profile.warnings(),
                profile.recommendations()
        );
    }
}
