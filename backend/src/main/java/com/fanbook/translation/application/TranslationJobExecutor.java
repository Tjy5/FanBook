package com.fanbook.translation.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class TranslationJobExecutor {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final TranslationChunkWorker worker;
    private final TranslationChunkStateService stateService;
    private final TranslationJobAggregator aggregator;
    private final BookTranslationLock lock;
    private final TransactionTemplate transactionTemplate;
    private final int maxAttemptsPerChunk;

    public TranslationJobExecutor(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            TranslationChunkWorker worker,
            TranslationChunkStateService stateService,
            TranslationJobAggregator aggregator,
            BookTranslationLock lock,
            TransactionTemplate transactionTemplate,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttemptsPerChunk
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.worker = worker;
        this.stateService = stateService;
        this.aggregator = aggregator;
        this.lock = lock;
        this.transactionTemplate = transactionTemplate;
        this.maxAttemptsPerChunk = maxAttemptsPerChunk;
    }

    public void runJob(Long jobId) {
        Long bookId = requireBookId(jobId);
        boolean acquired = false;
        try {
            acquired = lock.acquire(bookId, jobId);
            if (!acquired) {
                markJobFailed(jobId, "Another translation job is already running for book " + bookId + ".");
                return;
            }

            markRunning(jobId);
            while (!isCanceled(jobId)) {
                Long chunkId = takeNextChunkId(jobId);
                if (chunkId == null) {
                    break;
                }
                if (!executeChunk(jobId, chunkId)) {
                    return;
                }
            }
            completeIfStillRunning(jobId);
        } catch (RuntimeException exception) {
            markJobFailed(jobId, exception.getMessage());
            throw exception;
        } finally {
            if (acquired) {
                lock.release(bookId, jobId);
            }
        }
    }

    private Long requireBookId(Long jobId) {
        return transactionTemplate.execute(status -> requireJob(jobId).getBook().getId());
    }

    private void markRunning(Long jobId) {
        transactionTemplate.executeWithoutResult(status -> requireJob(jobId).markRunning(OffsetDateTime.now()));
    }

    private Long takeNextChunkId(Long jobId) {
        return transactionTemplate.execute(status -> {
            List<TranslationChunkEntity> candidates = chunkRepository.findByJobIdAndStatusInOrderByChunkOrderAsc(
                    jobId,
                    List.of(TranslationChunkStatus.PENDING, TranslationChunkStatus.FAILED)
            );
            if (candidates.isEmpty()) {
                return null;
            }
            for (TranslationChunkEntity chunk : candidates) {
                if (chunk.getStatus() == TranslationChunkStatus.FAILED && chunk.getAttemptCount() >= maxAttemptsPerChunk) {
                    String message = "chunk_retry_exhausted: chunk " + chunk.getId() + " reached " + maxAttemptsPerChunk + " attempts.";
                    chunk.markFailed(ErrorCode.CHUNK_RETRY_EXHAUSTED.value(), message, OffsetDateTime.now());
                    requireJob(jobId).markFailed(message, OffsetDateTime.now());
                    return null;
                }
                return chunk.getId();
            }
            return null;
        });
    }

    private boolean executeChunk(Long jobId, Long chunkId) {
        if (!stateService.tryAcquire(chunkId, "executor-" + jobId)) {
            return false;
        }
        try {
            worker.execute(chunkId);
            stateService.markCompleted(chunkId);
            aggregator.aggregate(jobId);
        } catch (RuntimeException exception) {
            markChunkFailed(chunkId, codeValue(exception), exception.getMessage());
        }
        return true;
    }

    private void completeIfStillRunning(Long jobId) {
        transactionTemplate.executeWithoutResult(status -> {
            TranslationJobEntity job = requireJob(jobId);
            if (job.getStatus() == TranslationJobStatus.RUNNING) {
                job.markCompleted(OffsetDateTime.now());
            }
        });
    }

    private void markJobFailed(Long jobId, String message) {
        transactionTemplate.executeWithoutResult(status -> requireJob(jobId).markFailed(message, OffsetDateTime.now()));
    }

    private void markChunkFailed(Long chunkId, String code, String message) {
        transactionTemplate.executeWithoutResult(status -> {
            TranslationChunkEntity chunk = chunkRepository.findById(chunkId)
                    .orElseThrow(() -> notFound("Translation chunk '" + chunkId + "' was not found."));
            chunk.markFailed(code, message, OffsetDateTime.now());
        });
    }

    private boolean isCanceled(Long jobId) {
        return transactionTemplate.execute(status -> requireJob(jobId).getStatus() == TranslationJobStatus.CANCELED);
    }

    private TranslationJobEntity requireJob(Long jobId) {
        return jobRepository.findById(jobId)
                .orElseThrow(() -> notFound("Translation job '" + jobId + "' was not found."));
    }

    private static String codeValue(RuntimeException exception) {
        if (exception instanceof FanbookException fanbookException) {
            return fanbookException.code().value();
        }
        return ErrorCode.PROVIDER_REQUEST_FAILED.value();
    }

    private FanbookException notFound(String message) {
        return new FanbookException(ErrorCode.TRANSLATION_JOB_NOT_FOUND, HttpStatus.NOT_FOUND, message);
    }
}
