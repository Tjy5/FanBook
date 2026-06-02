package com.fanbook.translation.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.api.StartTranslationRequest;
import com.fanbook.translation.api.TranslationJobResponse;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationJobService {

    private final SegmentRepository segmentRepository;
    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    public TranslationJobService(
            SegmentRepository segmentRepository,
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository
    ) {
        this.segmentRepository = segmentRepository;
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
    }

    @Transactional
    public TranslationJobResponse start(Long bookId, StartTranslationRequest request, String requestedBy) {
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        if (segments.isEmpty()) {
            throw new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found.");
        }

        String providerName = value(request == null ? null : request.providerName(), "mock");
        String modelName = value(request == null ? null : request.modelName(), "mock-translator");
        TranslationJobEntity job = new TranslationJobEntity(
                segments.getFirst().getBook(),
                TranslationJobStatus.QUEUED,
                providerName,
                modelName,
                value(requestedBy, "system")
        );
        job.updateProgress(segments.size(), 0, 0, 0);
        jobRepository.save(job);

        ChunkPlanner planner = new ChunkPlanner(6000, 40);
        int order = 1;
        for (List<SegmentEntity> chunkSegments : planner.plan(segments)) {
            List<Long> ids = chunkSegments.stream().map(SegmentEntity::getId).toList();
            int estimatedCharacters = chunkSegments.stream().mapToInt(segment -> segment.getSourceText().length()).sum();
            chunkRepository.save(new TranslationChunkEntity(
                    job,
                    job.getBook(),
                    chunkSegments.getFirst().getChapter(),
                    order++,
                    toJson(ids),
                    TranslationChunkStatus.PENDING,
                    estimatedCharacters
            ));
        }
        return toResponse(job);
    }

    @Transactional(readOnly = true)
    public TranslationJobResponse get(Long jobId) {
        return jobRepository.findById(jobId).map(this::toResponse)
                .orElseThrow(() -> new FanbookException(
                        ErrorCode.TRANSLATION_JOB_NOT_FOUND,
                        HttpStatus.NOT_FOUND,
                        "Translation job '" + jobId + "' was not found."
                ));
    }

    private TranslationJobResponse toResponse(TranslationJobEntity job) {
        return new TranslationJobResponse(
                job.getId(),
                job.getBook().getId(),
                job.getStatus().name(),
                job.getProviderName(),
                job.getModelName(),
                job.getProgress(),
                job.getTotalSegments(),
                job.getTranslatedSegments(),
                job.getFailedSegments()
        );
    }

    private static String value(String candidate, String fallback) {
        return candidate == null || candidate.isBlank() ? fallback : candidate;
    }

    private String toJson(List<Long> ids) {
        try {
            return objectMapper.writeValueAsString(ids);
        } catch (JsonProcessingException e) {
            throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.INTERNAL_SERVER_ERROR, "Failed to serialize segment ids.");
        }
    }
}
