package com.fanbook.ai.domain;

import java.util.List;

public record StructuredTranslationRequest(
        String sourceLanguage,
        String targetLanguage,
        String bookTitle,
        String chapterTitle,
        List<StructuredTranslationSourceItem> items
) {
}
