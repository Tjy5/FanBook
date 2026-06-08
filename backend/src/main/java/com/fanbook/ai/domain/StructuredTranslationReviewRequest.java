package com.fanbook.ai.domain;

import com.fanbook.translation.application.TranslationPreservationOptions;
import java.util.List;

public record StructuredTranslationReviewRequest(
        String sourceLanguage,
        String targetLanguage,
        String bookTitle,
        String chapterTitle,
        TranslationPromptProfile promptProfile,
        TranslationPreservationOptions preservation,
        List<StructuredTranslationGlossaryItem> glossary,
        List<StructuredTranslationReviewItem> items
) {
    public StructuredTranslationReviewRequest {
        promptProfile = promptProfile == null ? TranslationPromptProfile.defaults() : promptProfile;
        preservation = preservation == null ? TranslationPreservationOptions.defaults() : preservation;
        glossary = glossary == null ? List.of() : List.copyOf(glossary);
        items = items == null ? List.of() : List.copyOf(items);
    }

    public StructuredTranslationReviewRequest(
            String sourceLanguage,
            String targetLanguage,
            String bookTitle,
            String chapterTitle,
            List<StructuredTranslationGlossaryItem> glossary,
            List<StructuredTranslationReviewItem> items
    ) {
        this(sourceLanguage, targetLanguage, bookTitle, chapterTitle, null, null, glossary, items);
    }
}
