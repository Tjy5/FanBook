package com.fanbook.translation.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Service
public class TranslationRecoveryService {

    private final TranslationChunkRepository chunkRepository;
    private final TranslationJobRepository jobRepository;
    private final ActiveTranslationSessionRepository activeSessionRepository;
    private final TranslationChunkStateService stateService;
    private final TranslationChunkDegradationService degradationService;
    private final TranslationJobAggregator aggregator;
    private final TranslationChunkPublisher chunkPublisher;
    private final int maxAttempts;

    public TranslationRecoveryService(
            TranslationChunkRepository chunkRepository,
            TranslationJobRepository jobRepository,
            ActiveTranslationSessionRepository activeSessionRepository,
            TranslationChunkStateService stateService,
            TranslationChunkDegradationService degradationService,
            TranslationJobAggregator aggregator,
            TranslationChunkPublisher chunkPublisher,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttempts
    ) {
        this.chunkRepository = chunkRepository;
        this.jobRepository = jobRepository;
        this.activeSessionRepository = activeSessionRepository;
        this.stateService = stateService;
        this.degradationService = degradationService;
        this.aggregator = aggregator;
        this.chunkPublisher = chunkPublisher;
        this.maxAttempts = maxAttempts;
    }

    @Scheduled(fixedDelayString = "${fanbook.translation.recovery.scan-delay:60s}")
    public void scan() {
        recoverStaleChunks();
        cleanupStaleSessions();
    }

    @Transactional
    public void recoverStaleChunks() {
        OffsetDateTime now = OffsetDateTime.now();
        List<ChunkMessage> recoveryMessages = new ArrayList<>();
        for (var chunk : chunkRepository.findByStatusAndLockedUntilBefore(TranslationChunkStatus.RUNNING, now)) {
            if (chunk.getAttemptCount() >= maxAttempts) {
                List<ChunkMessage> degradedMessages = degradationService.degrade(chunk.getId());
                if (!degradedMessages.isEmpty()) {
                    recoveryMessages.addAll(degradedMessages);
                    continue;
                }
                stateService.markFailed(
                        chunk.getId(),
                        ErrorCode.CHUNK_RETRY_EXHAUSTED.value(),
                        "Stale chunk exhausted retry budget."
                );
                aggregator.aggregate(chunk.getJob().getId());
                continue;
            }
            recoveryMessages.add(new ChunkMessage(
                    "1.0",
                    chunk.getJob().getId(),
                    chunk.getId(),
                    chunk.getAttemptCount() + 1,
                    "RECOVERY",
                    "recovery-" + chunk.getId(),
                    now
            ));
        }
        publishAfterCommit(recoveryMessages);
    }

    @Transactional
    public void cleanupStaleSessions() {
        for (var job : jobRepository.findByStatus(TranslationJobStatus.CANCELED)) {
            if (chunkRepository.countByJobIdAndStatus(job.getId(), TranslationChunkStatus.RUNNING) == 0) {
                activeSessionRepository.deleteByJobId(job.getId());
            }
        }
    }

    private void publishAfterCommit(List<ChunkMessage> messages) {
        if (messages.isEmpty()) {
            return;
        }
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            chunkPublisher.publishAll(messages);
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                chunkPublisher.publishAll(messages);
            }
        });
    }
}
