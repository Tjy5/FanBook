package com.fanbook.export.api;

import com.fanbook.common.storage.StorageService;
import com.fanbook.export.application.ConsistencyReportService;
import com.fanbook.export.application.ExportService;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
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
        var artifact = exportService.exportZh(bookId);
        return download(artifact.getFilename(), "application/epub+zip", storageService.read(artifact.getObjectKey()));
    }

    @GetMapping("/api/books/{bookId}/exports/bilingual")
    public ResponseEntity<ByteArrayResource> bilingual(@PathVariable Long bookId) {
        var artifact = exportService.exportBilingual(bookId);
        return download(artifact.getFilename(), "application/epub+zip", storageService.read(artifact.getObjectKey()));
    }

    @GetMapping("/api/books/{bookId}/reports/consistency")
    public ResponseEntity<ByteArrayResource> reportJson(@PathVariable Long bookId) {
        var artifact = reportService.generateJson(bookId);
        return download(artifact.getFilename(), MediaType.APPLICATION_JSON_VALUE, storageService.read(artifact.getObjectKey()));
    }

    @GetMapping("/api/books/{bookId}/reports/consistency.md")
    public ResponseEntity<ByteArrayResource> reportMarkdown(@PathVariable Long bookId) {
        var artifact = reportService.generateMarkdown(bookId);
        return download(artifact.getFilename(), "text/markdown", storageService.read(artifact.getObjectKey()));
    }

    private static ResponseEntity<ByteArrayResource> download(String filename, String mediaType, byte[] content) {
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(MediaType.parseMediaType(mediaType))
                .body(new ByteArrayResource(content));
    }
}
