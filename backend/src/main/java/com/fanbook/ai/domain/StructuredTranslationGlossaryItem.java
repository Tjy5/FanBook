package com.fanbook.ai.domain;

public record StructuredTranslationGlossaryItem(
        String sourceTerm,
        String targetTerm,
        String category,
        String note
) {
}
