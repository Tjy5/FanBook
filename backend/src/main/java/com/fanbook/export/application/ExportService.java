package com.fanbook.export.application;

import com.fanbook.book.domain.BookEntity;
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
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ExportService {

    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final StorageService storageService;
    private final ExportArtifactRepository artifactRepository;

    public ExportService(
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
    public ExportArtifactEntity exportZh(Long bookId) {
        return export(bookId, ExportArtifactKind.ZH_EPUB, "zh.epub", false);
    }

    @Transactional
    public ExportArtifactEntity exportBilingual(Long bookId) {
        return export(bookId, ExportArtifactKind.BILINGUAL_EPUB, "bilingual.epub", true);
    }

    private ExportArtifactEntity export(Long bookId, ExportArtifactKind kind, String filename, boolean bilingual) {
        BookEntity book = bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found."));
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        if (segments.isEmpty() || segments.stream().anyMatch(segment -> segment.getStatus() != SegmentStatus.TRANSLATED || segment.getTranslatedText() == null)) {
            throw new FanbookException(ErrorCode.EXPORT_NOT_READY, HttpStatus.CONFLICT, "Book '" + bookId + "' is not fully translated.");
        }

        byte[] exported = rewriteEpub(storageService.read(book.getSourceObjectKey()), segments, bilingual);
        String objectKey = "exports/" + bookId + "/" + filename;
        storageService.put(objectKey, exported);

        ExportArtifactEntity artifact = new ExportArtifactEntity(book, kind, ExportArtifactStatus.READY, filename);
        artifact.markReady(objectKey, exported.length, sha256(exported));
        return artifactRepository.save(artifact);
    }

    private byte[] rewriteEpub(byte[] source, List<SegmentEntity> segments, boolean bilingual) {
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(source), StandardCharsets.UTF_8);
                 ZipOutputStream rewritten = new ZipOutputStream(out, StandardCharsets.UTF_8)) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    rewritten.putNextEntry(new ZipEntry(entry.getName()));
                    byte[] bytes = zip.readAllBytes();
                    if (!entry.isDirectory() && entry.getName().endsWith(".xhtml")) {
                        String text = new String(bytes, StandardCharsets.UTF_8);
                        for (SegmentEntity segment : segments.stream()
                                .sorted(Comparator.comparing((SegmentEntity segment) -> segment.getChapter().getId())
                                        .thenComparingInt(SegmentEntity::getSegmentOrder))
                                .toList()) {
                            String replacement = bilingual
                                    ? segment.getSourceText() + "\n" + segment.getTranslatedText()
                                    : segment.getTranslatedText();
                            text = text.replace(segment.getSourceText(), replacement);
                        }
                        bytes = text.getBytes(StandardCharsets.UTF_8);
                    }
                    rewritten.write(bytes);
                    rewritten.closeEntry();
                }
            }
            return out.toByteArray();
        } catch (Exception exception) {
            throw new FanbookException(ErrorCode.EXPORT_FAILED, HttpStatus.INTERNAL_SERVER_ERROR, exception.getMessage());
        }
    }

    private static String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }
}
