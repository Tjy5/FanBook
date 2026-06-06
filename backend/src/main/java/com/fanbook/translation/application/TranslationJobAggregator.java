package com.fanbook.translation.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.domain.ChapterEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.translation.domain.TranslationChunkStatus;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.ActiveTranslationSessionRepository;
import com.fanbook.translation.infrastructure.TranslationChunkRepository;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TranslationJobAggregator {

    private final TranslationJobRepository jobRepository;
    private final TranslationChunkRepository chunkRepository;
    private final SegmentRepository segmentRepository;
    private final ChapterRepository chapterRepository;
    private final ActiveTranslationSessionRepository activeSessionRepository;
    private final int maxAttempts;

    public TranslationJobAggregator(
            TranslationJobRepository jobRepository,
            TranslationChunkRepository chunkRepository,
            SegmentRepository segmentRepository,
            ChapterRepository chapterRepository,
            ActiveTranslationSessionRepository activeSessionRepository,
            @Value("${fanbook.translation.max-attempts-per-chunk:3}") int maxAttempts
    ) {
        this.jobRepository = jobRepository;
        this.chunkRepository = chunkRepository;
        this.segmentRepository = segmentRepository;
        this.chapterRepository = chapterRepository;
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
        refreshProgress(job);
        long completed = chunks.stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.COMPLETED)
                .count();
        long exhausted = chunks.stream()
                .filter(chunk -> chunk.getStatus() == TranslationChunkStatus.FAILED && chunk.getAttemptCount() >= maxAttempts)
                .count();
        OffsetDateTime now = OffsetDateTime.now();
        if (completed == chunks.size()) {
            job.markCompleted(now);
            job.getBook().markStatus(BookStatus.TRANSLATED);
            activeSessionRepository.deleteByJobId(jobId);
            return;
        }
        if (exhausted > 0) {
            job.markFailed(ErrorCode.CHUNK_RETRY_EXHAUSTED.value(), now);
            job.getBook().markStatus(BookStatus.FAILED);
            activeSessionRepository.deleteByJobId(jobId);
        }
    }

    private void refreshProgress(TranslationJobEntity job) {
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(job.getBook().getId());
        int translated = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED).count();
        int failed = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.FAILED).count();
        int total = segments.size();
        double progress = total == 0 ? 0 : (double) (translated + failed) / total;
        job.updateProgress(total, translated, failed, progress);

        Map<Long, List<SegmentEntity>> byChapter = segments.stream()
                .collect(Collectors.groupingBy(segment -> segment.getChapter().getId()));
        List<ChapterEntity> chapters = chapterRepository.findByBookIdOrderByChapterOrderAsc(job.getBook().getId());
        for (ChapterEntity chapter : chapters) {
            List<SegmentEntity> chapterSegments = byChapter.getOrDefault(chapter.getId(), List.of());
            int chapterTranslated = (int) chapterSegments.stream().filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED).count();
            int chapterFailed = (int) chapterSegments.stream().filter(segment -> segment.getStatus() == SegmentStatus.FAILED).count();
            chapter.updateProgress(chapterSegments.size(), chapterTranslated, chapterFailed);
        }
    }
}
