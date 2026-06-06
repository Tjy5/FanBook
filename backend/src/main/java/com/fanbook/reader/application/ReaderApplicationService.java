package com.fanbook.reader.application;

import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.ChapterEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.reader.api.ChapterListResponse;
import com.fanbook.reader.api.ChapterSegmentResponse;
import com.fanbook.reader.api.ReaderInfoResponse;
import com.fanbook.reader.infrastructure.SegmentNoteRepository;
import com.fanbook.translation.api.TranslationJobResponse;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReaderApplicationService {

    private final ChapterRepository chapterRepository;
    private final SegmentRepository segmentRepository;
    private final TranslationJobRepository jobRepository;
    private final SegmentNoteRepository noteRepository;
    private final BookAccessService bookAccessService;

    public ReaderApplicationService(
            ChapterRepository chapterRepository,
            SegmentRepository segmentRepository,
            TranslationJobRepository jobRepository,
            SegmentNoteRepository noteRepository,
            BookAccessService bookAccessService
    ) {
        this.chapterRepository = chapterRepository;
        this.segmentRepository = segmentRepository;
        this.jobRepository = jobRepository;
        this.noteRepository = noteRepository;
        this.bookAccessService = bookAccessService;
    }

    @Transactional(readOnly = true)
    public ReaderInfoResponse info(Long bookId) {
        BookEntity book = bookAccessService.requireAccessibleBook(bookId);
        TranslationJobResponse latestJob = jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(bookId)
                .map(this::toJobResponse)
                .orElse(null);
        return new ReaderInfoResponse(book.getId(), book.getTitle(), book.getSourceLanguage(), latestJob);
    }

    @Transactional(readOnly = true)
    public ChapterListResponse chapters(Long bookId) {
        bookAccessService.requireAccessibleBook(bookId);
        List<ChapterListResponse.ChapterSummary> chapters = chapterRepository.findByBookIdOrderByChapterOrderAsc(bookId).stream()
                .map(this::toChapterSummary)
                .toList();
        return new ChapterListResponse(chapters);
    }

    @Transactional(readOnly = true)
    public ChapterSegmentResponse segments(Long bookId, Long chapterId, String mode) {
        bookAccessService.requireAccessibleBook(bookId);
        ChapterEntity chapter = requireChapter(bookId, chapterId);
        List<ChapterSegmentResponse.ReaderSegment> segments = segmentRepository.findByChapterIdOrderBySegmentOrderAsc(chapterId).stream()
                .map(this::toReaderSegment)
                .toList();
        return new ChapterSegmentResponse(chapter.getId(), chapter.getTitle(), segments);
    }

    private ChapterListResponse.ChapterSummary toChapterSummary(ChapterEntity chapter) {
        List<SegmentEntity> segments = segmentRepository.findByChapterIdOrderBySegmentOrderAsc(chapter.getId());
        int totalSegments = segments.size();
        int translatedSegments = (int) segments.stream()
                .filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED)
                .count();
        double progress = totalSegments == 0 ? 0 : (double) translatedSegments / totalSegments;
        return new ChapterListResponse.ChapterSummary(
                chapter.getId(),
                chapter.getChapterOrder(),
                chapter.getTitle(),
                totalSegments,
                translatedSegments,
                progress
        );
    }

    private ChapterSegmentResponse.ReaderSegment toReaderSegment(SegmentEntity segment) {
        return new ChapterSegmentResponse.ReaderSegment(
                segment.getId(),
                segment.getSegmentOrder(),
                segment.getSegmentType().name(),
                segment.getSourceText(),
                segment.getTranslatedText(),
                segment.getStatus().name(),
                noteRepository.countBySegmentId(segment.getId())
        );
    }

    private TranslationJobResponse toJobResponse(TranslationJobEntity job) {
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

    private ChapterEntity requireChapter(Long bookId, Long chapterId) {
        ChapterEntity chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Chapter '" + chapterId + "' was not found."));
        if (!chapter.getBook().getId().equals(bookId)) {
            throw new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Chapter '" + chapterId + "' was not found in book '" + bookId + "'.");
        }
        return chapter;
    }
}
