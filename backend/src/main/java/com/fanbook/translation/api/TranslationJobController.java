package com.fanbook.translation.api;

import com.fanbook.translation.application.TranslationJobService;
import com.fanbook.translation.application.TranslationResumeService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TranslationJobController {

    private final TranslationJobService translationJobService;
    private final TranslationResumeService translationResumeService;

    public TranslationJobController(TranslationJobService translationJobService, TranslationResumeService translationResumeService) {
        this.translationJobService = translationJobService;
        this.translationResumeService = translationResumeService;
    }

    @PostMapping("/api/books/{bookId}/translation-jobs")
    @ResponseStatus(HttpStatus.CREATED)
    public TranslationJobResponse start(
            @PathVariable Long bookId,
            @RequestBody(required = false) StartTranslationRequest request,
            @RequestHeader(value = "X-Debug-User", required = false) String requestedBy
    ) {
        return translationJobService.start(bookId, request, requestedBy);
    }

    @GetMapping("/api/translation-jobs/{jobId}")
    public TranslationJobResponse get(@PathVariable Long jobId) {
        return translationJobService.get(jobId);
    }

    @PostMapping("/api/books/{bookId}/translation-jobs/resume")
    public TranslationJobResponse resume(@PathVariable Long bookId) {
        return translationResumeService.resume(bookId);
    }

    @PostMapping("/api/translation-jobs/{jobId}/cancel")
    public TranslationJobResponse cancel(@PathVariable Long jobId) {
        return translationJobService.cancel(jobId);
    }
}
