package com.fanbook.translation.api;

import com.fanbook.auth.application.CurrentUserProvider;
import com.fanbook.translation.application.TranslationJobService;
import com.fanbook.translation.application.TranslationResumeService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TranslationJobController {

    private final TranslationJobService translationJobService;
    private final TranslationResumeService translationResumeService;
    private final CurrentUserProvider currentUserProvider;

    public TranslationJobController(
            TranslationJobService translationJobService,
            TranslationResumeService translationResumeService,
            CurrentUserProvider currentUserProvider
    ) {
        this.translationJobService = translationJobService;
        this.translationResumeService = translationResumeService;
        this.currentUserProvider = currentUserProvider;
    }

    @PostMapping("/api/books/{bookId}/translation-jobs")
    @ResponseStatus(HttpStatus.CREATED)
    public TranslationJobResponse start(
            @PathVariable Long bookId,
            @RequestBody(required = false) StartTranslationRequest request
    ) {
        return translationJobService.start(bookId, request, currentUserProvider.requireCurrentUser().username());
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
