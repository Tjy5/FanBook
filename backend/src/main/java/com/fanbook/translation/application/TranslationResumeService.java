package com.fanbook.translation.application;

import static com.fanbook.translation.domain.TranslationChunkStatus.FAILED;
import static com.fanbook.translation.domain.TranslationChunkStatus.PENDING;
import static com.fanbook.translation.domain.TranslationChunkStatus.RUNNING;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.api.TranslationJobResponse;
import com.fanbook.translation.config.TranslationRecoveryProperties;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class TranslationResumeService {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final TranslationJobService translationJobService;
    private final TranslationChunkPublisher chunkPublisher;
    private final TranslationRecoveryProperties recoveryProperties;
    private final TransactionTemplate transactionTemplate;

    public TranslationResumeService(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            TranslationJobService translationJobService,
            TranslationChunkPublisher chunkPublisher,
            TranslationRecoveryProperties recoveryProperties,
            TransactionTemplate transactionTemplate
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.translationJobService = translationJobService;
        this.chunkPublisher = chunkPublisher;
        this.recoveryProperties = recoveryProperties;
        this.transactionTemplate = transactionTemplate;
    }

    public TranslationJobResponse resume(Long bookId) {
        return transactionTemplate.execute(status -> {
            TranslationJobEntity job = latestJob(bookId);
            if (job.getStatus() == TranslationJobStatus.RUNNING && !isStale(job)) {
                throw new FanbookException(ErrorCode.JOB_STILL_RUNNING, HttpStatus.CONFLICT, "Job is still running.");
            }
            if (job.getStatus() == TranslationJobStatus.COMPLETED) {
                throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.CONFLICT, "Completed job cannot be resumed.");
            }

            job.markQueued();
            List<TranslationChunkEntity> chunks = chunkRepository.findByJobIdAndStatusInOrderByChunkOrderAsc(
                    job.getId(),
                    List.of(RUNNING, FAILED, PENDING)
            );
            chunks.forEach(TranslationChunkEntity::markPending);
            List<ChunkMessage> messages = chunks.stream()
                    .map(chunk -> ChunkMessage.start(job.getId(), chunk.getId()))
                    .toList();
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    chunkPublisher.publishAll(messages);
                }
            });
            return translationJobService.toResponse(job);
        });
    }

    private TranslationJobEntity latestJob(Long bookId) {
        return jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(bookId)
                .orElseThrow(() -> translationJobService.notFound("Book '" + bookId + "' does not have a translation job."));
    }

    private boolean isStale(TranslationJobEntity job) {
        OffsetDateTime startedAt = job.getStartedAt();
        if (startedAt == null) {
            return false;
        }
        return startedAt.isBefore(OffsetDateTime.now().minus(recoveryProperties.staleJobThreshold()));
    }
}
