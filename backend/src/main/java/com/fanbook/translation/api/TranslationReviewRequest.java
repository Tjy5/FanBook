package com.fanbook.translation.api;

import java.util.List;

public record TranslationReviewRequest(
        String providerName,
        String modelName,
        Integer maxSegments,
        Integer minScore,
        List<String> warningCodes,
        Boolean applyChanges
) {
}
