package com.fanbook.export.application;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.export.domain.ExportArtifactStatus;
import com.fanbook.export.infrastructure.ExportArtifactRepository;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConsistencyReportService {

    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final StorageService storageService;
    private final ExportArtifactRepository artifactRepository;
    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    public ConsistencyReportService(
            BookRepository bookRepository,
            SegmentRepository segmentRepository,
            StorageService storageService,
            ExportArtifactRepository artifactRepository
    ) {
        this.bookRepository = bookRepository;
        this.segmentRepository = segmentRepository;
        this.storageService = storageService;
        this.artifactRepository = artifactRepository;
    }

    @Transactional
    public ExportArtifactEntity generateJson(Long bookId) {
        ReportStats stats = stats(bookId);
        try {
            byte[] content = objectMapper.writeValueAsBytes(Map.of(
                    "bookId", bookId,
                    "totalSegments", stats.totalSegments(),
                    "translatedSegments", stats.translatedSegments(),
                    "failedSegments", stats.failedSegments(),
                    "termWarnings", List.of()
            ));
            return store(bookId, ExportArtifactKind.CONSISTENCY_REPORT_JSON, "consistency.json", content);
        } catch (Exception exception) {
            throw new FanbookException(ErrorCode.EXPORT_FAILED, HttpStatus.INTERNAL_SERVER_ERROR, exception.getMessage());
        }
    }

    @Transactional
    public ExportArtifactEntity generateMarkdown(Long bookId) {
        ReportStats stats = stats(bookId);
        String markdown = """
                # Consistency Report

                - Book ID: %d
                - Total segments: %d
                - Translated segments: %d
                - Failed segments: %d
                - Term warnings: 0
                """.formatted(bookId, stats.totalSegments(), stats.translatedSegments(), stats.failedSegments());
        return store(bookId, ExportArtifactKind.CONSISTENCY_REPORT_MD, "consistency.md", markdown.getBytes(StandardCharsets.UTF_8));
    }

    @Transactional(readOnly = true)
    public ExportArtifactEntity requireReadyArtifact(Long bookId, ExportArtifactKind kind) {
        return artifactRepository.findFirstByBook_IdAndKindAndStatusOrderByCreatedAtDescIdDesc(bookId, kind, ExportArtifactStatus.READY)
                .filter(artifact -> artifact.getObjectKey() != null && storageService.exists(artifact.getObjectKey()))
                .orElseThrow(() -> new FanbookException(
                        ErrorCode.EXPORT_NOT_READY,
                        HttpStatus.CONFLICT,
                        "Report artifact '" + kind.name() + "' for book '" + bookId + "' is not ready."
                ));
    }

    private ReportStats stats(Long bookId) {
        if (!bookRepository.existsById(bookId)) {
            throw new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found.");
        }
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        int translated = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.TRANSLATED).count();
        int failed = (int) segments.stream().filter(segment -> segment.getStatus() == SegmentStatus.FAILED).count();
        return new ReportStats(segments.size(), translated, failed);
    }

    private ExportArtifactEntity store(Long bookId, ExportArtifactKind kind, String filename, byte[] content) {
        var book = bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found."));
        String objectKey = "reports/" + bookId + "/" + filename;
        storageService.put(objectKey, content);
        ExportArtifactEntity artifact = new ExportArtifactEntity(book, kind, ExportArtifactStatus.READY, filename);
        artifact.markReady(objectKey, content.length, sha256(content));
        return artifactRepository.save(artifact);
    }

    private static String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private record ReportStats(int totalSegments, int translatedSegments, int failedSegments) {
    }
}
