package com.fanbook.ai.domain;

import java.util.List;

public record StructuredTranslationReviewItem(
        Long segmentId,
        String sourceText,
        String translatedText,
        int qualityScore,
        List<String> warnings
) {
    public StructuredTranslationReviewItem {
        warnings = warnings == null ? List.of() : List.copyOf(warnings);
    }
}
