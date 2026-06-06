package com.fanbook.book.application;

import com.fanbook.auth.application.CurrentUser;
import com.fanbook.auth.application.CurrentUserProvider;
import com.fanbook.book.api.BookResponse;
import com.fanbook.book.api.BookDetailResponse;
import com.fanbook.book.api.BookListResponse;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.BookStatus;
import com.fanbook.book.domain.ChapterEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.ChapterRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.export.infrastructure.ExportArtifactRepository;
import com.fanbook.translation.domain.TranslationJobEntity;
import com.fanbook.translation.domain.TranslationJobStatus;
import com.fanbook.translation.infrastructure.TranslationJobRepository;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class BookApplicationService {

    private final EpubParser epubParser;
    private final StorageService storageService;
    private final BookRepository bookRepository;
    private final ChapterRepository chapterRepository;
    private final SegmentRepository segmentRepository;
    private final TranslationJobRepository jobRepository;
    private final ExportArtifactRepository artifactRepository;
    private final BookAccessService bookAccessService;
    private final CurrentUserProvider currentUserProvider;

    public BookApplicationService(
            EpubParser epubParser,
            StorageService storageService,
            BookRepository bookRepository,
            ChapterRepository chapterRepository,
            SegmentRepository segmentRepository,
            TranslationJobRepository jobRepository,
            ExportArtifactRepository artifactRepository,
            BookAccessService bookAccessService,
            CurrentUserProvider currentUserProvider
    ) {
        this.epubParser = epubParser;
        this.storageService = storageService;
        this.bookRepository = bookRepository;
        this.chapterRepository = chapterRepository;
        this.segmentRepository = segmentRepository;
        this.jobRepository = jobRepository;
        this.artifactRepository = artifactRepository;
        this.bookAccessService = bookAccessService;
        this.currentUserProvider = currentUserProvider;
    }

    @Transactional
    public BookResponse upload(String filename, byte[] content, String sourceLanguage) {
        return upload(filename, content, sourceLanguage, null);
    }

    @Transactional
    public BookResponse upload(String filename, byte[] content, String sourceLanguage, String titleOverride) {
        return upload(filename, content, sourceLanguage, titleOverride, null);
    }

    @Transactional
    public BookResponse uploadForCurrentUser(String filename, byte[] content, String sourceLanguage, String titleOverride) {
        CurrentUser currentUser = currentUserProvider.requireCurrentUser();
        if (currentUser.id() == null) {
            throw new FanbookException(ErrorCode.FORBIDDEN, HttpStatus.FORBIDDEN, "Book uploads require a local user account.");
        }
        return upload(filename, content, sourceLanguage, titleOverride, currentUser.id());
    }

    private BookResponse upload(String filename, byte[] content, String sourceLanguage, String titleOverride, Long ownerUserId) {
        ParsedBook parsed = parse(content);
        String safeFilename = filename == null || filename.isBlank() ? "uploaded.epub" : filename;
        String safeSourceLanguage = sourceLanguage == null || sourceLanguage.isBlank() ? "en" : sourceLanguage.trim();
        String safeTitle = titleOverride == null || titleOverride.isBlank() ? parsed.title() : titleOverride.trim();
        BookEntity book = bookRepository.save(new BookEntity(
                safeFilename,
                safeTitle,
                safeSourceLanguage,
                "books/pending/source.epub",
                BookStatus.PARSED,
                ownerUserId
        ));

        String objectKey = "books/" + book.getId() + "/source.epub";
        storageService.put(objectKey, content);
        book.updateSourceObjectKey(objectKey);

        List<SegmentEntity> segments = new ArrayList<>();
        for (ParsedChapter parsedChapter : parsed.chapters()) {
            ChapterEntity chapter = new ChapterEntity(
                    book,
                    parsedChapter.order(),
                    parsedChapter.title(),
                    parsedChapter.sourceDocPath()
            );
            chapter.updateProgress(parsedChapter.segments().size(), 0, 0);
            chapterRepository.save(chapter);
            for (ParsedSegment parsedSegment : parsedChapter.segments()) {
                segments.add(new SegmentEntity(
                        book,
                        chapter,
                        parsedSegment.order(),
                        parsedSegment.sourceText(),
                        parsedSegment.segmentType(),
                        SegmentStatus.PENDING,
                        parsedSegment.locatorJson(),
                        parsedSegment.sourceDigest()
                ));
            }
        }
        segmentRepository.saveAll(segments);
        return new BookResponse(book.getId(), book.getTitle(), book.getStatus().name(), parsed.chapters().size(), segments.size());
    }

    @Transactional(readOnly = true)
    public BookDetailResponse getBook(Long bookId) {
        BookEntity book = bookAccessService.requireAccessibleBook(bookId);
        return toDetail(book);
    }

    @Transactional(readOnly = true)
    public BookListResponse listBooks() {
        List<BookListResponse.BookListItemDto> books = bookAccessService.listAccessibleBooks().stream()
                .map(this::toListItem)
                .toList();
        BookListResponse.StatusCountsDto counts = new BookListResponse.StatusCountsDto(
                books.size(),
                (int) books.stream().filter(book -> "running".equals(book.status())).count(),
                (int) books.stream().filter(book -> "completed".equals(book.status())).count(),
                (int) books.stream().filter(book -> "failed".equals(book.status())).count()
        );
        return new BookListResponse(books, counts);
    }

    @Transactional
    public BookDetailResponse updateTranslatedTitle(Long bookId, String translatedTitle) {
        BookEntity book = bookAccessService.requireAccessibleBook(bookId);
        book.updateTranslatedTitle(translatedTitle == null || translatedTitle.isBlank() ? null : translatedTitle.trim());
        return toDetail(book);
    }

    private BookDetailResponse toDetail(BookEntity book) {
        List<ChapterEntity> chapters = chapterRepository.findByBookIdOrderByChapterOrderAsc(book.getId());
        BookDetailResponse.JobDto currentJob = jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(book.getId())
                .map(this::toJobDto)
                .orElse(null);
        List<BookDetailResponse.ArtifactDto> artifacts = Stream.of(
                        ExportArtifactKind.ZH_EPUB,
                        ExportArtifactKind.BILINGUAL_EPUB,
                        ExportArtifactKind.CONSISTENCY_REPORT_JSON,
                        ExportArtifactKind.CONSISTENCY_REPORT_MD
                )
                .map(kind -> artifactRepository.findFirstByBook_IdAndKindOrderByCreatedAtDescIdDesc(book.getId(), kind))
                .flatMap(Optional::stream)
                .sorted(Comparator.comparing(ExportArtifactEntity::getCreatedAt, Comparator.nullsLast(Comparator.reverseOrder())))
                .map(this::toArtifactDto)
                .toList();
        return new BookDetailResponse(
                toBookDto(book),
                currentJob,
                chapters.stream().map(this::toChapterDto).toList(),
                artifacts
        );
    }

    private BookListResponse.BookListItemDto toListItem(BookEntity book) {
        List<ChapterEntity> chapters = chapterRepository.findByBookIdOrderByChapterOrderAsc(book.getId());
        int totalSegments = chapters.stream().mapToInt(ChapterEntity::getTotalSegments).sum();
        int translatedSegments = chapters.stream().mapToInt(ChapterEntity::getTranslatedSegments).sum();
        int failedSegments = chapters.stream().mapToInt(ChapterEntity::getFailedSegments).sum();
        Optional<TranslationJobEntity> latestJob = jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(book.getId());
        double progress = latestJob.map(TranslationJobEntity::getProgress)
                .orElse(totalSegments == 0 ? 0 : (double) translatedSegments / totalSegments);
        String currentJobStatus = latestJob.map(job -> dashboardJobStatus(job.getStatus())).orElse(null);
        return new BookListResponse.BookListItemDto(
                book.getId(),
                book.getTitle(),
                book.getTranslatedTitle(),
                titleTranslationStatus(book),
                book.getFilename(),
                book.getSourceLanguage(),
                dashboardBookStatus(book, latestJob.orElse(null)),
                progress,
                totalSegments,
                translatedSegments,
                failedSegments,
                currentJobStatus,
                book.getCreatedAt(),
                book.getUpdatedAt()
        );
    }

    private BookDetailResponse.BookDto toBookDto(BookEntity book) {
        return new BookDetailResponse.BookDto(
                book.getId(),
                book.getTitle(),
                book.getTranslatedTitle(),
                titleTranslationStatus(book),
                book.getFilename(),
                book.getSourceLanguage(),
                dashboardBookStatus(book, jobRepository.findFirstByBookIdOrderByUpdatedAtDescIdDesc(book.getId()).orElse(null)),
                book.getCreatedAt(),
                book.getUpdatedAt()
        );
    }

    private BookDetailResponse.ChapterDto toChapterDto(ChapterEntity chapter) {
        return new BookDetailResponse.ChapterDto(
                chapter.getId(),
                chapter.getChapterOrder(),
                chapter.getTitle(),
                chapter.getTotalSegments(),
                chapter.getTranslatedSegments(),
                chapter.getFailedSegments()
        );
    }

    private BookDetailResponse.JobDto toJobDto(TranslationJobEntity job) {
        return new BookDetailResponse.JobDto(
                job.getId(),
                job.getBook().getId(),
                dashboardJobStatus(job.getStatus()),
                job.getProviderName(),
                job.getProviderName(),
                job.getModelName(),
                job.getProgress(),
                job.getTotalSegments(),
                job.getTranslatedSegments(),
                job.getFailedSegments(),
                null,
                job.getCreatedAt(),
                job.getUpdatedAt()
        );
    }

    private BookDetailResponse.ArtifactDto toArtifactDto(ExportArtifactEntity artifact) {
        return new BookDetailResponse.ArtifactDto(
                artifact.getId(),
                artifactKind(artifact.getKind()),
                artifact.getStatus().name().toLowerCase(),
                artifact.getFilename(),
                artifact.getSizeBytes(),
                artifact.getCreatedAt()
        );
    }

    private static String titleTranslationStatus(BookEntity book) {
        String translatedTitle = book.getTranslatedTitle();
        return translatedTitle == null || translatedTitle.isBlank() ? "pending" : "completed";
    }

    private static String dashboardBookStatus(BookEntity book, TranslationJobEntity latestJob) {
        if (latestJob != null) {
            String jobStatus = dashboardJobStatus(latestJob.getStatus());
            if ("running".equals(jobStatus) || "failed".equals(jobStatus) || "completed".equals(jobStatus)) {
                return jobStatus;
            }
        }
        return switch (book.getStatus()) {
            case TRANSLATING -> "running";
            case TRANSLATED, EXPORT_READY -> "completed";
            case FAILED -> "failed";
            default -> "pending";
        };
    }

    private static String dashboardJobStatus(TranslationJobStatus status) {
        return switch (status) {
            case QUEUED -> "pending";
            case RUNNING -> "running";
            case COMPLETED -> "completed";
            case FAILED, CANCELED -> "failed";
        };
    }

    private static String artifactKind(ExportArtifactKind kind) {
        return switch (kind) {
            case ZH_EPUB -> "zh";
            case BILINGUAL_EPUB -> "bilingual";
            case CONSISTENCY_REPORT_JSON, CONSISTENCY_REPORT_MD -> "consistency_report";
        };
    }

    private ParsedBook parse(byte[] content) {
        try {
            return epubParser.parse(content);
        } catch (EpubParserException exception) {
            throw new FanbookException(ErrorCode.INVALID_EPUB, HttpStatus.BAD_REQUEST, exception.getMessage());
        }
    }
}
