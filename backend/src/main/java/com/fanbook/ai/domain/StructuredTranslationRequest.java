package com.fanbook.ai.domain;

import com.fanbook.translation.application.TranslationPreservationOptions;
import java.util.List;

public record StructuredTranslationRequest(
        String sourceLanguage,
        String targetLanguage,
        String bookTitle,
        String chapterTitle,
        TranslationPromptProfile promptProfile,
        TranslationPreservationOptions preservation,
        List<StructuredTranslationContextItem> context,
        List<StructuredTranslationGlossaryItem> glossary,
        List<StructuredTranslationSourceItem> items
) {
    public StructuredTranslationRequest {
        promptProfile = promptProfile == null ? TranslationPromptProfile.defaults() : promptProfile;
        preservation = preservation == null ? TranslationPreservationOptions.defaults() : preservation;
        context = context == null ? List.of() : List.copyOf(context);
        glossary = glossary == null ? List.of() : List.copyOf(glossary);
        items = items == null ? List.of() : List.copyOf(items);
    }

    public StructuredTranslationRequest(
            String sourceLanguage,
            String targetLanguage,
            String bookTitle,
            String chapterTitle,
            List<StructuredTranslationContextItem> context,
            List<StructuredTranslationGlossaryItem> glossary,
            List<StructuredTranslationSourceItem> items
    ) {
        this(sourceLanguage, targetLanguage, bookTitle, chapterTitle, null, null, context, glossary, items);
    }

    public StructuredTranslationRequest(
            String sourceLanguage,
            String targetLanguage,
            String bookTitle,
            String chapterTitle,
            List<StructuredTranslationContextItem> context,
            List<StructuredTranslationSourceItem> items
    ) {
        this(sourceLanguage, targetLanguage, bookTitle, chapterTitle, context, List.of(), items);
    }

    public StructuredTranslationRequest(
            String sourceLanguage,
            String targetLanguage,
            String bookTitle,
            String chapterTitle,
            List<StructuredTranslationSourceItem> items
    ) {
        this(sourceLanguage, targetLanguage, bookTitle, chapterTitle, List.of(), List.of(), items);
    }
}
