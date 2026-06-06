package com.fanbook.export.api;

import com.fanbook.common.storage.StorageService;
import com.fanbook.export.application.ConsistencyReportService;
import com.fanbook.export.application.ExportService;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ExportController {

    private final ExportService exportService;
    private final ConsistencyReportService reportService;
    private final StorageService storageService;

    public ExportController(
            ExportService exportService,
            ConsistencyReportService reportService,
            StorageService storageService
    ) {
        this.exportService = exportService;
        this.reportService = reportService;
        this.storageService = storageService;
    }

    @GetMapping("/api/books/{bookId}/exports/zh")
    public ResponseEntity<ByteArrayResource> zh(@PathVariable Long bookId) {
        var artifact = exportService.requireReadyArtifactForCurrentUser(bookId, ExportArtifactKind.ZH_EPUB);
        return download(artifact.getFilename(), "application/epub+zip", storageService.read(artifact.getObjectKey()));
    }

    @PostMapping("/api/books/{bookId}/exports/zh")
    public ExportArtifactResponse generateZh(@PathVariable Long bookId) {
        return toResponse(exportService.exportZhForCurrentUser(bookId));
    }

    @GetMapping("/api/books/{bookId}/exports/bilingual")
    public ResponseEntity<ByteArrayResource> bilingual(@PathVariable Long bookId) {
        var artifact = exportService.requireReadyArtifactForCurrentUser(bookId, ExportArtifactKind.BILINGUAL_EPUB);
        return download(artifact.getFilename(), "application/epub+zip", storageService.read(artifact.getObjectKey()));
    }

    @PostMapping("/api/books/{bookId}/exports/bilingual")
    public ExportArtifactResponse generateBilingual(@PathVariable Long bookId) {
        return toResponse(exportService.exportBilingualForCurrentUser(bookId));
    }

    @GetMapping("/api/books/{bookId}/reports/consistency")
    public ResponseEntity<ByteArrayResource> reportJson(@PathVariable Long bookId) {
        var artifact = reportService.requireReadyArtifactForCurrentUser(bookId, ExportArtifactKind.CONSISTENCY_REPORT_JSON);
        return download(artifact.getFilename(), MediaType.APPLICATION_JSON_VALUE, storageService.read(artifact.getObjectKey()));
    }

    @PostMapping("/api/books/{bookId}/reports/consistency")
    public ExportArtifactResponse generateReportJson(@PathVariable Long bookId) {
        return toResponse(reportService.generateJsonForCurrentUser(bookId));
    }

    @GetMapping("/api/books/{bookId}/reports/consistency.md")
    public ResponseEntity<ByteArrayResource> reportMarkdown(@PathVariable Long bookId) {
        var artifact = reportService.requireReadyArtifactForCurrentUser(bookId, ExportArtifactKind.CONSISTENCY_REPORT_MD);
        return download(artifact.getFilename(), "text/markdown", storageService.read(artifact.getObjectKey()));
    }

    @PostMapping("/api/books/{bookId}/reports/consistency.md")
    public ExportArtifactResponse generateReportMarkdown(@PathVariable Long bookId) {
        return toResponse(reportService.generateMarkdownForCurrentUser(bookId));
    }

    private static ResponseEntity<ByteArrayResource> download(String filename, String mediaType, byte[] content) {
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.parseMediaType(mediaType))
                .body(new ByteArrayResource(content));
    }

    private static ExportArtifactResponse toResponse(ExportArtifactEntity artifact) {
        return new ExportArtifactResponse(
                artifact.getId(),
                artifact.getBook().getId(),
                artifact.getKind().name(),
                artifact.getStatus().name(),
                artifact.getFilename(),
                artifact.getSizeBytes(),
                artifact.getChecksum()
        );
    }
}
