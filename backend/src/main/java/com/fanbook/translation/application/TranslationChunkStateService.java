package com.fanbook.translation.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.translation.config.TranslationRecoveryProperties;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import java.time.OffsetDateTime;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationChunkStateService {

    private final TranslationChunkRepository chunkRepository;
    private final TranslationRecoveryProperties recoveryProperties;
    private final int maxAttempts;

    public TranslationChunkStateService(
            TranslationChunkRepository chunkRepository,
            TranslationRecoveryProperties recoveryProperties,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttempts
    ) {
        this.chunkRepository = chunkRepository;
        this.recoveryProperties = recoveryProperties;
        this.maxAttempts = maxAttempts;
    }

    @Transactional
    public boolean tryAcquire(Long chunkId, String workerId) {
        OffsetDateTime now = OffsetDateTime.now();
        OffsetDateTime lockedUntil = now.plus(recoveryProperties.chunkLease());
        return chunkRepository.acquireLease(chunkId, now, lockedUntil, workerId, maxAttempts) == 1;
    }

    @Transactional
    public void markCompleted(Long chunkId) {
        requireChunk(chunkId).markCompleted(OffsetDateTime.now());
    }

    @Transactional
    public void markFailed(Long chunkId, String errorCode, String errorMessage) {
        requireChunk(chunkId).markFailed(errorCode, errorMessage, OffsetDateTime.now());
    }

    @Transactional(readOnly = true)
    public int currentAttempt(Long chunkId) {
        return requireChunk(chunkId).getAttemptCount();
    }

    @Transactional
    void forceLeaseExpiredForTest(Long chunkId) {
        requireChunk(chunkId).forceLeaseExpired(OffsetDateTime.now().minusSeconds(1));
    }

    private TranslationChunkEntity requireChunk(Long chunkId) {
        return chunkRepository.findById(chunkId)
                .orElseThrow(() -> new FanbookException(
                        ErrorCode.TRANSLATION_JOB_NOT_FOUND,
                        HttpStatus.NOT_FOUND,
                        "Translation chunk '" + chunkId + "' was not found."
                ));
    }
}
