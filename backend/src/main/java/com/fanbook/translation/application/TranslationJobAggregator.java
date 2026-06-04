package com.fanbook.translation.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationJobAggregator {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final ActiveTranslationSessionRepository activeSessionRepository;
    private final int maxAttempts;

    public TranslationJobAggregator(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            ActiveTranslationSessionRepository activeSessionRepository,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttempts
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.activeSessionRepository = activeSessionRepository;
        this.maxAttempts = maxAttempts;
    }

    @Transactional
    public void aggregate(Long jobId) {
        TranslationJobEntity job = jobRepository.findById(jobId).orElseThrow();
        if (job.getStatus() == TranslationJobStatus.CANCELED) {
            return;
        }
        var chunks = chunkRepository.findByJobIdOrderByChunkOrderAsc(jobId);
        if (chunks.isEmpty()) {
            return;
        }
        long completed = chunks.stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.COMPLETED)
                .count();
        long exhausted = chunks.stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.FAILED && chunk.getAttemptCount() >= maxAttempts)
                .count();
        OffsetDateTime now = OffsetDateTime.now();
        if (completed == chunks.size()) {
            job.markCompleted(now);
            activeSessionRepository.deleteByJobId(jobId);
            return;
        }
        if (exhausted > 0) {
            job.markFailed(ErrorCode.CHUNK_RETRY_EXHAUSTED.value(), now);
            activeSessionRepository.deleteByJobId(jobId);
        }
    }
}
