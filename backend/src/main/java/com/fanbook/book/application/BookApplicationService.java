package com.fanbook.book.application;

import com.fanbook.book.api.BookResponse;
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
import java.util.ArrayList;
import java.util.List;
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

    public BookApplicationService(
            EpubParser epubParser,
            StorageService storageService,
            BookRepository bookRepository,
            ChapterRepository chapterRepository,
            SegmentRepository segmentRepository
    ) {
        this.epubParser = epubParser;
        this.storageService = storageService;
        this.bookRepository = bookRepository;
        this.chapterRepository = chapterRepository;
        this.segmentRepository = segmentRepository;
    }

    @Transactional
    public BookResponse upload(String filename, byte[] content, String sourceLanguage) {
        ParsedBook parsed = parse(content);
        String safeFilename = filename == null || filename.isBlank() ? "uploaded.epub" : filename;
        String safeSourceLanguage = sourceLanguage == null || sourceLanguage.isBlank() ? "en" : sourceLanguage.trim();
        BookEntity book = bookRepository.save(new BookEntity(
                safeFilename,
                parsed.title(),
                safeSourceLanguage,
                "books/pending/source.epub",
                BookStatus.PARSED
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

    private ParsedBook parse(byte[] content) {
        try {
            return epubParser.parse(content);
        } catch (EpubParserException exception) {
            throw new FanbookException(ErrorCode.INVALID_EPUB, HttpStatus.BAD_REQUEST, exception.getMessage());
        }
    }
}
