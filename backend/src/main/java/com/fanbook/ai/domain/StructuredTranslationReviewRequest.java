package com.fanbook.ai.domain;

import java.util.List;

public record StructuredTranslationReviewRequest(
        String sourceLanguage,
        String targetLanguage,
        String bookTitle,
        String chapterTitle,
        List<StructuredTranslationGlossaryItem> glossary,
        List<StructuredTranslationReviewItem> items
) {
    public StructuredTranslationReviewRequest {
        glossary = glossary == null ? List.of() : List.copyOf(glossary);
        items = items == null ? List.of() : List.copyOf(items);
    }
}
