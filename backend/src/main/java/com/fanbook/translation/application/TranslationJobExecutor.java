package com.fanbook.translation.application;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.ai.application.StructuredTranslationValidator;
import com.fanbook.ai.domain.AiTranslationProvider;
import com.fanbook.ai.domain.StructuredTranslationGlossaryItem;
import com.fanbook.ai.domain.StructuredTranslationItem;
import com.fanbook.ai.domain.StructuredTranslationRequest;
import com.fanbook.ai.domain.StructuredTranslationSourceItem;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.lock.BookTranslationLock;
import com.fanbook.translation.config.TranslationChunkPlanningProperties;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class TranslationJobExecutor {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final SegmentRepository segmentRepository;
    private final AiTranslationProvider provider;
    private final StructuredTranslationValidator validator;
    private final BookTranslationLock lock;
    private final TransactionTemplate transactionTemplate;
    private final int maxAttemptsPerChunk;
    private final TranslationChunkPlanningProperties chunkPlanningProperties;
    private final TranslationRuleSnapshotService ruleSnapshotService;
    private final TranslationTextProtector textProtector;
    private final TranslationGlossaryBuilder glossaryBuilder = new TranslationGlossaryBuilder();
    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    public TranslationJobExecutor(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            SegmentRepository segmentRepository,
            AiTranslationProvider provider,
            StructuredTranslationValidator validator,
            BookTranslationLock lock,
            TransactionTemplate transactionTemplate,
            TranslationChunkPlanningProperties chunkPlanningProperties,
            TranslationRuleSnapshotService ruleSnapshotService,
            TranslationTextProtector textProtector,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttemptsPerChunk
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.segmentRepository = segmentRepository;
        this.provider = provider;
        this.validator = validator;
        this.lock = lock;
        this.transactionTemplate = transactionTemplate;
        this.chunkPlanningProperties = chunkPlanningProperties;
        this.ruleSnapshotService = ruleSnapshotService;
        this.textProtector = textProtector;
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
                TranslationChunkEntity chunk = takeNextChunk(jobId);
                if (chunk == null) {
                    break;
                }
                executeChunk(jobId, chunk);
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

    private TranslationChunkEntity takeNextChunk(Long jobId) {
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
                chunk.markRunning(OffsetDateTime.now());
                return chunk;
            }
            return null;
        });
    }

    private void executeChunk(Long jobId, TranslationChunkEntity chunk) {
        try {
            ChunkWork work = buildChunkWork(chunk);
            var result = provider.translateChunk(work.request());
            validator.validate(work.segmentIds(), result);
            transactionTemplate.executeWithoutResult(status -> {
                Map<Long, String> translatedById = result.items().stream()
                        .collect(Collectors.toMap(StructuredTranslationItem::segmentId, StructuredTranslationItem::translatedText));
                for (SegmentEntity segment : segmentRepository.findAllById(work.segmentIds())) {
                    segment.markTranslated(textProtector.postProcess(translatedById.get(segment.getId())));
                }
                TranslationChunkEntity managedChunk = chunkRepository.findById(chunk.getId())
                        .orElseThrow(() -> notFound("Translation chunk '" + chunk.getId() + "' was not found."));
                managedChunk.markCompleted(OffsetDateTime.now());
                refreshProgress(jobId);
            });
        } catch (RuntimeException exception) {
            markChunkFailed(chunk.getId(), codeValue(exception), exception.getMessage());
        }
    }

    private ChunkWork buildChunkWork(TranslationChunkEntity chunk) {
        List<Long> segmentIds = parseSegmentIds(chunk.getSegmentIdsJson());
        return transactionTemplate.execute(status -> {
            TranslationChunkEntity managedChunk = chunkRepository.findById(chunk.getId())
                    .orElseThrow(() -> notFound("Translation chunk '" + chunk.getId() + "' was not found."));
            List<SegmentEntity> segments = segmentRepository.findAllById(segmentIds);
            Map<Long, SegmentEntity> segmentById = segments.stream()
                    .collect(Collectors.toMap(SegmentEntity::getId, Function.identity()));
            TranslationRuleSnapshotData snapshot = ruleSnapshotService.dataForJob(managedChunk.getJob());
            List<StructuredTranslationSourceItem> items = segmentIds.stream()
                    .map(id -> {
                        SegmentEntity segment = segmentById.get(id);
                        if (segment == null) {
                            throw new FanbookException(
                                    ErrorCode.STRUCTURED_OUTPUT_INVALID,
                                    HttpStatus.INTERNAL_SERVER_ERROR,
                                    "Missing segment '" + id + "' for translation chunk '" + chunk.getId() + "'."
                            );
                        }
                        return new StructuredTranslationSourceItem(id, segment.getSourceText());
                    })
                    .toList();
            SegmentEntity first = segmentById.get(segmentIds.getFirst());
            List<StructuredTranslationGlossaryItem> glossary = glossaryBuilder.build(
                    snapshot.glossary(),
                    requestTexts(first, items),
                    chunkPlanningProperties.glossaryCandidateLimit()
            );
            return new ChunkWork(
                    segmentIds,
                    new StructuredTranslationRequest(
                            first.getBook().getSourceLanguage(),
                            snapshot.targetLanguage(),
                            first.getBook().getTitle(),
                            first.getChapter().getTitle(),
                            snapshot.promptProfile(),
                            snapshot.preservation(),
                            List.of(),
                            glossary,
                            items
                    )
            );
        });
    }

    private static List<String> requestTexts(SegmentEntity first, List<StructuredTranslationSourceItem> items) {
        List<String> texts = new java.util.ArrayList<>();
        texts.add(first.getBook().getTitle());
        texts.add(first.getChapter().getTitle());
        items.forEach(item -> texts.add(item.sourceText()));
        return texts;
    }

    private void refreshProgress(Long jobId) {
        TranslationJobEntity job = requireJob(jobId);
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(job.getBook().getId());
        int translated = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED).count();
        int failed = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.FAILED).count();
        int total = segments.size();
        double progress = total == 0 ? 0 : (double) (translated + failed) / total;
        job.updateProgress(total, translated, failed, progress);
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

    private List<Long> parseSegmentIds(String segmentIdsJson) {
        try {
            return objectMapper.readValue(segmentIdsJson, new TypeReference<List<Long>>() {
            });
        } catch (Exception exception) {
            throw new FanbookException(
                    ErrorCode.STRUCTURED_OUTPUT_INVALID,
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Invalid chunk segment id JSON."
            );
        }
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

    private record ChunkWork(List<Long> segmentIds, StructuredTranslationRequest request) {
    }
}
