package com.fanbook.reader.api;

import com.fanbook.reader.application.ReaderApplicationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ReaderController {

    private final ReaderApplicationService service;

    public ReaderController(ReaderApplicationService service) {
        this.service = service;
    }

    @GetMapping("/api/books/{bookId}/reader/info")
    public ReaderInfoResponse info(@PathVariable Long bookId) {
        return service.info(bookId);
    }

    @GetMapping("/api/books/{bookId}/chapters")
    public ChapterListResponse chapters(@PathVariable Long bookId) {
        return service.chapters(bookId);
    }

    @GetMapping("/api/books/{bookId}/chapters/{chapterId}/segments")
    public ChapterSegmentResponse segments(
            @PathVariable Long bookId,
            @PathVariable Long chapterId,
            @RequestParam(defaultValue = "bilingual") String mode
    ) {
        return service.segments(bookId, chapterId, mode);
    }
}
