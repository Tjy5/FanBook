package com.fanbook.translation.application;

import com.fanbook.translation.api.TranslationJobResponse;
import com.fanbook.translation.domain.TranslationChunkEntity;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationResumeService {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final TranslationJobService translationJobService;

    public TranslationResumeService(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            TranslationJobService translationJobService
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.translationJobService = translationJobService;
    }

    @Transactional
    public TranslationJobResponse resume(Long bookId) {
        var latest = jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(bookId)
                .orElseThrow(() -> translationJobService.notFound("Book '" + bookId + "' does not have a translation job."));
        chunkRepository.findByJobIdOrderByChunkOrderAsc(latest.getId()).stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.RUNNING)
                .forEach(TranslationChunkEntity::markPending);
        if (latest.getStatus() == TranslationJobStatus.FAILED) {
            latest.markQueued();
        }
        return translationJobService.toResponse(latest);
    }
}
